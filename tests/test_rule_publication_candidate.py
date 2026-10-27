"""Candidate-only state machine, authority scope and real isolated SQLite transactions."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone,timedelta
import json,sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from parkweave.rule_publication_candidate import CandidateConfig,CandidatePermit,MockPrincipal,Scope,CandidateRepository,CandidateEngine,Command,Draft,Denied,Conflict
from parkweave.rule_publication_candidate_api import create_candidate_app
from test_v1_contracts import service

SCOPE=Scope(park_id='park-a',org_id='org-a',service_id='candidate-intake')
VALID={'valid_from':'2019-01-01T00:00:00+00:00','valid_until':'2099-01-01T00:00:00+00:00','timezone':'UTC'}
ROLES={'fixture-a':'enterprise_operator','prep-specialist-fixture-a':'park_specialist','mock-publisher':'resource_admin','mock-executor':'service_executor','mock-other-org':'enterprise_operator'}
ACTIONS={'fixture-a':['READ','SAVE','SUBMIT','RETURN_DRAFT'],'prep-specialist-fixture-a':['READ','REVIEW','REJECT'],'mock-publisher':['READ','PUBLISH','WITHDRAW'],'mock-executor':['READ'],'mock-other-org':['READ','SAVE']}

def config():
    return CandidateConfig(enabled_for_isolated_tests=True,principals=[MockPrincipal(id=id,role=role) for id,role in ROLES.items()],permits=[CandidatePermit(id='permit-'+id,principal_id=id,scope=SCOPE if id!='mock-other-org' else Scope(park_id='park-a',org_id='org-b',service_id='candidate-intake'),actions=actions,validity=VALID) for id,actions in ACTIONS.items()])

def draft(version=1,text='SYNTHETIC fixed source',**change):
    spec=service();spec.update(publication='DRAFT',reviewer_id=None,service_id=SCOPE.service_id,revision=str(version),eligibility={'kind':'MANUAL'},validity=VALID)
    spec.update(change)
    if 'source_refs' not in change:spec['source_refs'][0]['revision']=str(version)
    return Draft.model_validate({'spec':spec,'sources':[{'ref':spec['source_refs'][0],'text':text,'validity':VALID}]})

@pytest.fixture
def candidate(tmp_path):
    now=[datetime(2026,10,7,tzinfo=timezone.utc)];repo=CandidateRepository(tmp_path/'rules.candidate.sqlite3');engine=CandidateEngine(config(),repo,lambda:now[0]);return engine,repo,now

def cmd(e,action,actor=None,view=None,key=None,**extras):
    import uuid
    actor=actor or ('prep-specialist-fixture-a' if action in ('REVIEW','REJECT') else 'mock-publisher' if action in ('PUBLISH','WITHDRAW') else 'fixture-a')
    x=view or e.read(actor,SCOPE)
    body={'action':action,'expected_revision':x['revision'],'expected_content_sha256':x['content_sha256'],'reason':'SYNTHETIC explicit '+action,**extras}
    if action=='PUBLISH' and 'publish_validity' not in extras:body['publish_validity']=VALID
    return e.command(actor,SCOPE,key or uuid.uuid4().hex,Command.model_validate(body))

def published(e):
    cmd(e,'SAVE',draft=draft());cmd(e,'SUBMIT');cmd(e,'REVIEW');return cmd(e,'PUBLISH')

def stable(repo):
    with repo.connect() as c:return {t:[dict(r) for r in c.execute('SELECT * FROM '+t+' ORDER BY rowid')] for t in ('candidate_rules','candidate_events','candidate_releases','candidate_assessments')}

def test_default_disabled_no_repository_and_explicit_configuration_required(tmp_path):
    app=TestClient(create_candidate_app());assert not app.get('/api/candidate/status').json()['candidate_demo']
    assert app.get('/api/candidate/park-a/org-a/candidate-intake',headers={'X-Mock-Actor':'fixture-a'}).status_code==403
    assert '候选流程未启用' in app.get('/').text and list(tmp_path.iterdir())==[]
    with pytest.raises(ValueError):CandidateConfig(enabled_for_isolated_tests=True)
    with pytest.raises(ValueError):CandidateEngine(config())

def test_review_and_candidate_release_are_separate_and_no_eligibility_confirmation(candidate):
    e,r,n=candidate;cmd(e,'SAVE',draft=draft());cmd(e,'SUBMIT')
    with pytest.raises(Conflict):cmd(e,'PUBLISH')
    cmd(e,'REVIEW');x=e.read('mock-publisher',SCOPE);assert x['state']=='REVIEWED' and not x['candidate_available'] and not x['releases']
    cmd(e,'PUBLISH');x=e.read('fixture-a',SCOPE);assert x['candidate_available'] and len(x['history'])==4
    assert x['qualification_truth']=='UNKNOWN' and not x['business_publication'] and not x['deployment_enabled']
    assert x['releases'][0]['scope']==SCOPE.model_dump() and x['releases'][0]['reviewer_id']!=x['releases'][0]['publisher_id']
    with pytest.raises(sqlite3.IntegrityError):
        with r.connect(write=True) as c:c.execute('DELETE FROM candidate_events')

@pytest.mark.parametrize('actor,action',[('fixture-a','REVIEW'),('fixture-a','PUBLISH'),('prep-specialist-fixture-a','PUBLISH'),('mock-publisher','REVIEW'),('mock-executor','SAVE'),('mock-other-org','SAVE'),('unknown','SAVE')])
def test_wrong_role_or_scope_denied_without_side_effect(candidate,actor,action):
    e,r,n=candidate;cmd(e,'SAVE',draft=draft());before=stable(r)
    payload=Command(action=action,expected_revision=1,expected_content_sha256=e.read('fixture-a',SCOPE)['content_sha256'],reason='SYNTHETIC denied',draft=draft(2) if action=='SAVE' else None,publish_validity=VALID if action=='PUBLISH' else None)
    with pytest.raises(Denied):e.command(actor,SCOPE,'denied-key',payload)
    assert stable(r)==before

def test_submission_return_rejection_modification_requires_fresh_review(candidate):
    e,r,n=candidate;cmd(e,'SAVE',draft=draft());cmd(e,'SUBMIT')
    with pytest.raises(Conflict):cmd(e,'SAVE',draft=draft(2))
    cmd(e,'RETURN_DRAFT');cmd(e,'SAVE',draft=draft(2));cmd(e,'SUBMIT');cmd(e,'REJECT')
    with pytest.raises(Conflict):cmd(e,'PUBLISH')
    with pytest.raises(Conflict):cmd(e,'SUBMIT')
    cmd(e,'SAVE',draft=draft(3,text='SYNTHETIC corrected source'));cmd(e,'SUBMIT');cmd(e,'REVIEW');cmd(e,'PUBLISH')
    assert e.read('fixture-a',SCOPE)['content_version']==3

def test_modify_withdraw_and_reload_preserve_history_stale_assessments(candidate):
    e,r,n=candidate;published(e);x=e.read('fixture-a',SCOPE);e.assess('fixture-a',SCOPE,x['revision'],x['source_sha256'])
    cmd(e,'SAVE',draft=draft(2,text='SYNTHETIC new revision'));x=e.read('fixture-a',SCOPE)
    assert x['state']=='DRAFT' and x['releases'][0]['state']=='SUPERSEDED' and x['assessments'][0]['state']=='STALE'
    with pytest.raises(Conflict):cmd(e,'PUBLISH')
    cmd(e,'SUBMIT');cmd(e,'REVIEW');cmd(e,'PUBLISH');x=e.read('fixture-a',SCOPE);e.assess('fixture-a',SCOPE,x['revision'],x['source_sha256']);cmd(e,'WITHDRAW')
    fresh=CandidateEngine(config(),CandidateRepository(r.path),lambda:n[0]);x=fresh.read('fixture-a',SCOPE)
    assert x['state']=='WITHDRAWN' and not x['candidate_available'] and len(x['releases'])==2 and len(x['history'])==9
    assert all(a['state']=='STALE' and a['current_truth']=='UNKNOWN' for a in x['assessments'])
    assert x['releases'][1]['draft']['sources'][0]['text']=='SYNTHETIC new revision'

def test_same_key_concurrency_version_conflicts_and_cross_object_key(candidate):
    e,r,n=candidate;key='initial-key';x=e.read('fixture-a',SCOPE)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:cmd(e,'SAVE',draft=draft(),view=x,key=key),range(2)))
    assert results[0]==results[1] and len(e.read('fixture-a',SCOPE)['history'])==1
    with pytest.raises(Conflict):cmd(e,'SAVE',draft=draft(2),view=x)
    with pytest.raises(Conflict):cmd(e,'SAVE',draft=draft(2),key=key)
    x=e.read('fixture-a',SCOPE)
    with ThreadPoolExecutor(2) as pool:
        def write(text):
            try:return cmd(e,'SAVE',draft=draft(2,text),view=x)['revision']
            except Conflict:return 'CONFLICT'
        result=list(pool.map(write,['SYNTHETIC parallel1','SYNTHETIC parallel2']))
    assert sorted(map(str,result))==['2','CONFLICT']

def test_source_expiry_and_current_permission_revoke(candidate):
    e,r,n=candidate;short={**VALID,'valid_until':'2027-01-01T00:00:00+00:00'}
    d=draft(validity=short);d.sources[0].validity=d.spec.validity
    cmd(e,'SAVE',draft=d);cmd(e,'SUBMIT');cmd(e,'REVIEW');cmd(e,'PUBLISH',publish_validity=short)
    x=e.read('fixture-a',SCOPE);e.assess('fixture-a',SCOPE,x['revision'],x['source_sha256'])
    n[0]=datetime(2027,1,1,tzinfo=timezone.utc);x=e.read('fixture-a',SCOPE)
    assert x['availability_reason']=='EXPIRED_SOURCE' and not x['candidate_available'] and x['assessments'][0]['state']=='STALE'
    assert x['qualification_truth']=='UNKNOWN'
    n[0]=datetime(2099,1,1,tzinfo=timezone.utc)
    with pytest.raises(Denied):e.read('fixture-a',SCOPE)

@pytest.mark.parametrize('principal',['prep-specialist-fixture-a','mock-publisher'])
def test_reviewer_or_publisher_revocation_invalidates_candidate_and_current_replay(candidate,principal):
    e,r,n=candidate;published(e);x=e.read('fixture-a',SCOPE);e.assess('fixture-a',SCOPE,x['revision'],x['source_sha256'])
    cfg=config();cfg.revision=2;next(p for p in cfg.permits if p.principal_id==principal).active=False;e.replace_test_contract(cfg)
    x=e.read('fixture-a',SCOPE);assert not x['candidate_available'] and x['assessments'][0]['state']=='STALE'
    assert x['availability_reason']=='CURRENT_REVIEW_OR_PUBLISH_AUTHORITY_MISSING'
    with pytest.raises(Denied):e.read(principal,SCOPE)

def test_current_authority_checks_before_replay_and_self_review_publish_denied(candidate):
    e,r,n=candidate;x=e.read('fixture-a',SCOPE);cmd(e,'SAVE',draft=draft(),view=x,key='saved-key')
    cfg=config();next(p for p in cfg.permits if p.principal_id=='fixture-a').active=False;e.replace_test_contract(cfg);before=stable(r)
    with pytest.raises(Denied):cmd(e,'SAVE',draft=draft(),view=x,key='saved-key')
    assert stable(r)==before
    e.replace_test_contract(config());cmd(e,'SUBMIT');cfg=config()
    next(p for p in cfg.principals if p.id=='fixture-a').role='park_specialist';next(p for p in cfg.permits if p.principal_id=='fixture-a').actions=['READ','REVIEW'];e.replace_test_contract(cfg)
    with pytest.raises(Denied):cmd(e,'REVIEW',actor='fixture-a')
    e.replace_test_contract(config());cmd(e,'REVIEW');cfg=config()
    next(p for p in cfg.principals if p.id=='prep-specialist-fixture-a').role='resource_admin';next(p for p in cfg.permits if p.principal_id=='prep-specialist-fixture-a').actions=['READ','PUBLISH'];e.replace_test_contract(cfg)
    with pytest.raises(Denied):cmd(e,'PUBLISH',actor='prep-specialist-fixture-a')

def test_publication_cannot_broaden_scope_source_or_validity(candidate):
    e,r,n=candidate;cmd(e,'SAVE',draft=draft());cmd(e,'SUBMIT');cmd(e,'REVIEW');before=stable(r)
    with pytest.raises(Conflict):cmd(e,'PUBLISH',publish_validity={**VALID,'valid_until':'2100-01-01T00:00:00+00:00'})
    with pytest.raises(ValueError):draft(publication='REVIEWED_SYNTHETIC',reviewer_id='fixture-a')
    with pytest.raises(ValueError):
        d=draft().model_dump();d['sources'][0]['ref']['revision']='wrong';Draft.model_validate(d)
    assert stable(r)==before

def test_atomic_rollback_and_foreign_legacy_database_refusal(candidate,tmp_path):
    e,r,n=candidate;cmd(e,'SAVE',draft=draft());before=stable(r)
    with r.connect(write=True) as c:c.execute("CREATE TRIGGER fail_event BEFORE INSERT ON candidate_events BEGIN SELECT RAISE(ABORT,'SYNTHETIC event failure'); END")
    with pytest.raises(sqlite3.IntegrityError):cmd(e,'SAVE',draft=draft(2))
    assert stable(r)==before
    foreign=tmp_path/'legacy.candidate.sqlite3'
    with sqlite3.connect(foreign) as c:c.execute('CREATE TABLE legacy_data(value TEXT)');c.execute("INSERT INTO legacy_data VALUES('KEEP')")
    with pytest.raises(Conflict):CandidateRepository(foreign)
    with sqlite3.connect(foreign) as c:assert c.execute('SELECT * FROM legacy_data').fetchall()==[('KEEP',)]
    with pytest.raises(ValueError):CandidateRepository(tmp_path/'deployment.sqlite3')

def test_api_scope_actor_and_unknown_body_fail_closed(candidate):
    e,r,n=candidate;api=TestClient(create_candidate_app(e));base='/api/candidate/park-a/org-a/candidate-intake';before=stable(r)
    assert api.get(base,headers={'X-Mock-Actor':'mock-other-org'}).status_code==403
    assert api.get('/api/candidate/bad!scope/org-a/candidate-intake',headers={'X-Mock-Actor':'fixture-a'}).status_code==422
    body={'action':'SAVE','expected_revision':0,'reason':'SYNTHETIC','draft':draft().model_dump(mode='json'),'actor_id':'mock-publisher'}
    assert api.post(base+'/commands',headers={'X-Mock-Actor':'fixture-a','Idempotency-Key':'invalid'},json=body).status_code==422
    assert stable(r)==before
    body.pop('actor_id');r1=api.post(base+'/commands',headers={'X-Mock-Actor':'fixture-a','Idempotency-Key':'first'},json=body);assert r1.status_code==200
    assert api.get(base,headers={'X-Mock-Actor':'fixture-a'}).json()['state']=='DRAFT'


def test_foreign_database_with_valid_marker_refused_without_schema_or_byte_changes(tmp_path):
    import hashlib
    p=tmp_path/'foreign.candidate.sqlite3'
    with sqlite3.connect(p) as c:
        c.execute('CREATE TABLE candidate_meta(namespace TEXT PRIMARY KEY,version INTEGER)');c.execute("INSERT INTO candidate_meta VALUES('ISOLATED_SYNTHETIC_CANDIDATE',1)")
        c.execute('CREATE TABLE legacy(value TEXT)');c.execute("INSERT INTO legacy VALUES('KEEP')")
    before=hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(Conflict):CandidateRepository(p)
    assert hashlib.sha256(p.read_bytes()).hexdigest()==before
    with sqlite3.connect(p) as c:assert c.execute('SELECT * FROM legacy').fetchall()==[('KEEP',)]

def test_source_version_cannot_be_rewritten(candidate):
    e,r,n=candidate;cmd(e,'SAVE',draft=draft());before=stable(r)
    d=draft(2,text='SYNTHETIC changed bytes');d.spec.source_refs[0].revision='1';d.sources[0].ref.revision='1'
    with pytest.raises(Conflict):cmd(e,'SAVE',draft=d)
    assert stable(r)==before


def test_mock_factory_requires_both_flags_and_never_opens_deployment_store(tmp_path,monkeypatch):
    from scripts.rule_candidate_demo import configured_mock_app
    path=tmp_path/'explicit.candidate.sqlite3'
    monkeypatch.setenv('PARKWEAVE_CANDIDATE_TEST_DB',str(path))
    monkeypatch.delenv('PARKWEAVE_CANDIDATE_ENABLE_TESTS',raising=False)
    assert not TestClient(configured_mock_app()).get('/api/candidate/status').json()['candidate_demo']
    assert not path.exists()
    monkeypatch.setenv('PARKWEAVE_CANDIDATE_ENABLE_TESTS','ISOLATED_SYNTHETIC_CANDIDATE')
    monkeypatch.delenv('PARKWEAVE_CANDIDATE_TEST_DB')
    assert not TestClient(configured_mock_app()).get('/api/candidate/status').json()['candidate_demo']
    assert not path.exists()


def test_same_actor_key_cannot_cross_objects_even_with_explicit_scope_permit(candidate):
    e,r,n=candidate;cmd(e,'SAVE',draft=draft(),key='object-bound')
    other=Scope(park_id='park-a',org_id='org-a',service_id='candidate-other')
    cfg=config();cfg.permits.append(CandidatePermit(id='other-object',principal_id='fixture-a',scope=other,actions=['READ','SAVE'],validity=VALID));e.replace_test_contract(cfg)
    before=stable(r);d=draft(service_id=other.service_id)
    with pytest.raises(Conflict):e.command('fixture-a',other,'object-bound',Command(action='SAVE',expected_revision=0,reason='SYNTHETIC other object',draft=d))
    assert stable(r)==before and e.read('fixture-a',other)['state']=='NOT_CREATED'


def test_replaying_old_publish_returns_receipt_without_restoring_withdrawn_release(candidate):
    e,r,n=candidate;cmd(e,'SAVE',draft=draft());cmd(e,'SUBMIT');cmd(e,'REVIEW')
    view=e.read('mock-publisher',SCOPE);receipt=cmd(e,'PUBLISH',view=view,key='published-once');cmd(e,'WITHDRAW');before=stable(r)
    assert cmd(e,'PUBLISH',view=view,key='published-once')==receipt
    assert stable(r)==before and not e.read('fixture-a',SCOPE)['candidate_available']
    assert e.read('fixture-a',SCOPE)['state']=='WITHDRAWN'


def test_rejected_source_revision_only_change_cannot_bypass_required_correction(candidate):
    e,r,n=candidate;cmd(e,'SAVE',draft=draft());cmd(e,'SUBMIT');cmd(e,'REJECT');before=stable(r)
    with pytest.raises(Conflict):cmd(e,'SAVE',draft=draft(2))
    assert stable(r)==before and e.read('fixture-a',SCOPE)['state']=='REJECTED'
    cmd(e,'SAVE',draft=draft(2,text='SYNTHETIC corrected actual source content'))
    assert e.read('fixture-a',SCOPE)['state']=='DRAFT'
