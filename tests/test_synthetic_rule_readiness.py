"""Mechanical development simulation, original owned PG facts + mock review chain."""
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from uuid import UUID,uuid4
import sqlite3
import pytest
from parkweave import synthetic_rule_readiness as sr, preparation as prep
from parkweave.domain import Rule
from parkweave.rule_publication_candidate import CandidateConfig,CandidatePermit,MockPrincipal,CandidateRepository,CandidateEngine,Scope,Command,Draft,sha
from parkweave.store import Denied,Conflict
from test_preparation import preparation_fixture,filled,headers
from test_case_fact_clarifications_integration import post_fact,declare,fact_read,authority,business,confirm_body
from test_v1_contracts import service

VALID=dict(valid_from='2026-01-01T00:00:00+00:00',valid_until='2099-01-01T00:00:00+00:00',timezone='UTC')
SCOPE=Scope(park_id='park-a',org_id='org-a',service_id=prep.SERVICE)

def engine(tmp_path, rule=None):
    people=[('fixture-a','enterprise_operator',['READ','SAVE','SUBMIT']),('mock-reviewer','park_specialist',['READ','REVIEW']),('mock-publisher','resource_admin',['READ','PUBLISH','WITHDRAW'])]
    cfg=CandidateConfig(enabled_for_isolated_tests=True,principals=[MockPrincipal(id=x,role=r) for x,r,a in people],permits=[CandidatePermit(id='permit-'+x,principal_id=x,scope=SCOPE,actions=a,validity=VALID) for x,r,a in people])
    e=CandidateEngine(cfg,CandidateRepository(tmp_path/'source.candidate.sqlite3'))
    spec=service();spec.update(service_id=prep.SERVICE,publication='DRAFT',reviewer_id=None,validity=VALID,eligibility=rule or dict(kind='EQ',field='employees',expected=17))
    draft=Draft(spec=spec,sources=[dict(ref=spec['source_refs'][0],text='SYNTHETIC deliberately finite eligibility rule',validity=VALID)])
    for action,actor in [('SAVE','fixture-a'),('SUBMIT','fixture-a'),('REVIEW','mock-reviewer'),('PUBLISH','mock-publisher')]:
        v=e.read(actor,SCOPE);data=Command(action=action,expected_revision=v['revision'],expected_content_sha256=v['content_sha256'],reason='SYNTHETIC explicit '+action,draft=draft if action=='SAVE' else None,publish_validity=VALID if action=='PUBLISH' else None)
        e.command(actor,SCOPE,uuid4().hex,data)
    return e

@pytest.fixture
def simulation(preparation_fixture,tmp_path):
    f=preparation_fixture;p=filled(f);r=declare(f,p);assert r.status_code==200;r=r.json()
    selected={name:post_fact(f,name,value,'simulation-'+name) for name,value in [('region','REGION_A'),('employees',17),('service_need','NEED_A')]}
    b=confirm_body(f,r,selected);res=f[3].post('/api/preparations/'+r['preparation_id']+'/fact-clarifications/confirm',headers=headers(f[2],key=uuid4().hex),json=b);assert res.status_code==200,res.text
    p=res.json();e=engine(tmp_path);release=e.read('fixture-a',SCOPE)['releases'][0]
    binding=sr.RuleBinding(binding_id='rule-a',scope=SCOPE,release_id=release['id'],content_sha256=release['content_sha256'],region='REGION_A',epoch=1)
    journal=sr.SimulationJournal(tmp_path/'results.synthetic-readiness.sqlite3');a=sr.SyntheticRuleReadiness(f[0],f[1],e,journal,bindings=[binding],enabled_for_isolated_tests=True)
    context=sr.Context(binding_id='rule-a',as_of=datetime.now(timezone.utc).isoformat())
    return f,p,e,a,context

def read(v):
    f,p,e,a,context=v
    return a.read(f[2]['fixture-a'],UUID(p['preparation_id']),context)

def assess(v,key=None):
    f,p,e,a,context=v;current=read(v)
    data=sr.Assess(context=context,expected_preparation_revision=current['preparation_revision'],expected_source_sha256=current['source_sha256'],reason='SYNTHETIC explicit rule simulation')
    return a.assess(f[2]['fixture-a'],UUID(p['preparation_id']),key or uuid4().hex,data),data

def test_actual_reviewed_source_authorized_facts_true_and_no_business_mutation(simulation):
    f,p,e,a,context=simulation;oldbusiness=business(f);oldauthority=authority(f)
    v=read(simulation);assert v['result']['synthetic_simulated_condition_truth']=='TRUE';assert v['rule_review_status']=='SYNTHETIC_REVIEWED'
    assert v['result']['fact_authenticity']=='USER_ASSERTED_UNVERIFIED' and not v['formal_review'] and not v['business_publication'] and v['qualification_truth']=='UNKNOWN'
    record,data=assess(simulation,'original');assert record['result']==v['result']
    assert a.assess(f[2]['fixture-a'],UUID(p['preparation_id']),'original',data)==record
    recovered=a.recover(f[2]['fixture-a'],UUID(p['preparation_id']),'original',context);assert recovered['status']=='COMMITTED' and not recovered['automatically_replayed']
    assert business(f)==oldbusiness and authority(f)==oldauthority
    with pytest.raises(Conflict):a.assess(f[2]['fixture-a'],UUID(p['preparation_id']),'original',data.model_copy(update={'reason':'different'}))
    with a.journal.connect() as c:assert c.execute('SELECT count(*) FROM simulation_assessments').fetchone()[0]==1

@pytest.mark.parametrize('target',['fixture-b','fixture-c','prep-specialist-fixture-a'])
def test_cross_identity_denies_without_journal_write(simulation,target):
    f,p,e,a,context=simulation
    with pytest.raises(Denied):a.read(f[2][target],UUID(p['preparation_id']),context)
    with a.journal.connect() as c:assert c.execute('SELECT count(*) FROM simulation_assessments').fetchone()[0]==0

@pytest.mark.parametrize('change',['conflict','fact-expiry','region','as-of','review-revoked','publisher-revoked','withdraw','execute','field-write'])
def test_changes_unknown_preserve_historical_truth(simulation,change):
    f,p,e,a,context=simulation;record,data=assess(simulation,'saved')
    if change=='conflict':post_fact(f,'employees',3,'conflicting-new-source')
    elif change=='fact-expiry':
        a_context=context.model_copy(update={'as_of':'2098-01-01T00:00:00+00:00'});simulation=(f,p,e,a,a_context)
    elif change=='region':a.bindings=(a.bindings[0].model_copy(update={'region':'REGION_B','epoch':2}),)
    elif change=='as-of':simulation=(f,p,e,a,context.model_copy(update={'as_of':'2099-01-01T00:00:00+00:00'}))
    elif change in ('review-revoked','publisher-revoked'):
        cfg=e._config.model_copy(deep=True);next(x for x in cfg.permits if x.principal_id==('mock-reviewer' if change=='review-revoked' else 'mock-publisher')).active=False;e.replace_test_contract(cfg)
    elif change=='withdraw':
        v=e.read('mock-publisher',SCOPE);e.command('mock-publisher',SCOPE,'withdraw',Command(action='WITHDRAW',expected_revision=v['revision'],expected_content_sha256=v['content_sha256'],reason='SYNTHETIC withdraw'))
    else:
        with f[1].connect() as c:
            if change=='execute':c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
            else:c.execute("UPDATE field_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='WRITE' AND field_name='employees'")
    v=read(simulation);assert v['result']['synthetic_simulated_condition_truth']=='UNKNOWN'
    assert v['history'][0]['result']['synthetic_simulated_condition_truth']=='TRUE' and v['history'][0]['current_truth']=='UNKNOWN'
    assert v['history'][0]['receipt_sha256']==record['receipt_sha256']

@pytest.mark.parametrize('table',['candidate_rules','candidate_releases'])
def test_source_tamper_never_self_approves(simulation,table):
    f,p,e,a,context=simulation
    with e.repository.connect(write=True) as c:
        if table=='candidate_rules':
            row=c.execute('SELECT * FROM candidate_rules').fetchone();draft=__import__('json').loads(row['draft']);draft['spec']['eligibility']['expected']=999;c.execute('UPDATE candidate_rules SET draft=?,content_sha=?',(__import__('json').dumps(draft),sha(draft)))
        else:
            row=c.execute('SELECT * FROM candidate_releases').fetchone();payload=__import__('json').loads(row['payload']);payload['draft']['spec']['eligibility']['expected']=999;payload['content_sha256']=sha(payload['draft']);c.execute('UPDATE candidate_releases SET payload=?',(__import__('json').dumps(payload),))
    with pytest.raises(Conflict):read(simulation)

@pytest.mark.parametrize('capability',['READ','PREPARE','FIELD_READ'])
def test_current_scope_revocation_denies(simulation,capability):
    f,p,e,a,context=simulation
    with f[1].connect() as c:
        if capability=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif capability=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        else:c.execute("UPDATE field_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ' AND field_name='employees'")
    with pytest.raises(Denied):read(simulation)

@pytest.mark.parametrize('kind,expected,want',[('EQ',17,'TRUE'),('EQ',3,'FALSE'),('EXISTS',None,'TRUE'),('MANUAL',None,'UNKNOWN')])
def test_finite_three_values(kind,expected,want):
    fields={} if kind=='MANUAL' else dict(field='employees')
    if expected is not None:fields['expected']=expected
    node=Rule(kind=kind,**fields);row=dict(id='a',field_name='employees',value=17,unit='people',valid_from=VALID['valid_from'],valid_until=VALID['valid_until'],revision=1,fingerprint='a'*64,source_ref=dict(id='s',kind='SYNTHETIC',revision='1'))
    result=sr.evaluate(node,{'sources':[row]},[dict(field='employees',assertion_id='a')],{'a':True},datetime.now(timezone.utc))
    assert result['synthetic_simulated_condition_truth']==want and result['qualification_truth']=='UNKNOWN'

@pytest.mark.parametrize('which',['missing','expired','conflict','purpose'])
def test_unknown_never_coerced(which):
    row=dict(id='a',field_name='employees',value=17,unit='people',valid_from=VALID['valid_from'],valid_until=VALID['valid_until'],revision=1,fingerprint='a'*64,source_ref=dict(id='s',kind='SYNTHETIC',revision='1'));rows=[] if which=='missing' else [row]
    if which=='conflict':rows.append(dict(row,id='b',value=3))
    result=sr.evaluate(Rule(kind='EQ',field='employees',expected=17),{'sources':rows},[dict(field='employees',assertion_id='a')],{'a':which!='expired','b':True},datetime.now(timezone.utc),purpose_current=which!='purpose')
    assert result['synthetic_simulated_condition_truth']=='UNKNOWN'

def test_journal_append_only_and_foreign_refused(tmp_path):
    j=sr.SimulationJournal(tmp_path/'a.synthetic-readiness.sqlite3')
    with j.connect(write=True) as c:c.execute("INSERT INTO simulation_assessments VALUES('a','k','p','f','{}')")
    with pytest.raises(sqlite3.IntegrityError):
        with j.connect(write=True) as c:c.execute('DELETE FROM simulation_assessments')
    with pytest.raises(Denied):sr.SyntheticRuleReadiness(None,None)

def test_real_false_from_original_reviewed_different_mechanical_rule(simulation,tmp_path):
    f,p,old,a,context=simulation
    path=tmp_path/'false-source';path.mkdir();e=engine(path,dict(kind='EQ',field='employees',expected=3));release=e.read('fixture-a',SCOPE)['releases'][0]
    b=sr.RuleBinding(binding_id='rule-false',scope=SCOPE,release_id=release['id'],content_sha256=release['content_sha256'],region='REGION_A',epoch=1)
    other=sr.SyntheticRuleReadiness(f[0],f[1],e,sr.SimulationJournal(path/'false.synthetic-readiness.sqlite3'),bindings=[b],enabled_for_isolated_tests=True)
    context=sr.Context(binding_id='rule-false',as_of=context.as_of)
    v=other.read(f[2]['fixture-a'],UUID(p['preparation_id']),context)
    assert v['result']['synthetic_simulated_condition_truth']=='FALSE' and v['result']['conditions'][0]['reason']=='SYNTHETIC_MECHANICAL_MISMATCH'
    assert not v['formal_review'] and v['qualification_truth']=='UNKNOWN'

def test_conflicting_region_not_in_expression_stays_unknown_even_after_owner_selection(simulation):
    f,p,e,a,context=simulation
    post_fact(f,'region','REGION_B','region-conflict')
    current=fact_read(f,p).json();selected={x['field_name']:x['id'] for x in current['sources'] if x['value'] in ('REGION_A',17,'NEED_A')}
    data=confirm_body(f,p,selected);response=f[3].post('/api/preparations/'+p['preparation_id']+'/fact-clarifications/confirm',headers=headers(f[2],key=uuid4().hex),json=data);assert response.status_code==200,response.text
    v=read(simulation);assert v['sources']['purpose_status']['state']=='CURRENT'
    assert v['result']['synthetic_simulated_condition_truth']=='UNKNOWN' and v['sources']['current_block']=='CONFLICTING_EVIDENCE'

def test_missing_original_purpose_cannot_be_forged_by_context(preparation_fixture,tmp_path):
    f=preparation_fixture;p=filled(f);post_fact(f,'employees',17,'missing-region-employees');post_fact(f,'service_need','NEED_A','missing-region-need');e=engine(tmp_path);release=e.read('fixture-a',SCOPE)['releases'][0]
    b=sr.RuleBinding(binding_id='rule-a',scope=SCOPE,release_id=release['id'],content_sha256=release['content_sha256'],region='REGION_A',epoch=1)
    a=sr.SyntheticRuleReadiness(f[0],f[1],e,sr.SimulationJournal(tmp_path/'missing.synthetic-readiness.sqlite3'),bindings=[b],enabled_for_isolated_tests=True)
    v=a.read(f[2]['fixture-a'],UUID(p['preparation_id']),sr.Context(binding_id='rule-a',as_of=datetime.now(timezone.utc).isoformat()))
    assert v['result']['synthetic_simulated_condition_truth']=='UNKNOWN' and v['result']['conditions'][0]['reason']=='MISSING_EVIDENCE'

def test_same_key_concurrent_one_receipt_and_event_failure_full_journal_rollback(simulation):
    from concurrent.futures import ThreadPoolExecutor
    f,p,e,a,context=simulation;v=read(simulation);data=sr.Assess(context=context,expected_preparation_revision=v['preparation_revision'],expected_source_sha256=v['source_sha256'],reason='SYNTHETIC explicit concurrent simulation')
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(lambda _:a.assess(f[2]['fixture-a'],UUID(p['preparation_id']),'same-key',data),range(2)))
    assert results[0]==results[1]
    with a.journal.connect(write=True) as c:c.execute("CREATE TRIGGER fail_insert BEFORE INSERT ON simulation_assessments BEGIN SELECT RAISE(ABORT,'SYNTHETIC event failure'); END")
    with pytest.raises(sqlite3.IntegrityError):a.assess(f[2]['fixture-a'],UUID(p['preparation_id']),'fails',data)
    with a.journal.connect() as c:assert c.execute('SELECT count(*) FROM simulation_assessments').fetchone()[0]==1
    recovered=a.recover(f[2]['fixture-a'],UUID(p['preparation_id']),'fails',context);assert recovered['status']=='NOT_OBSERVED' and not recovered['automatically_replayed']

@pytest.mark.parametrize('change',['CANCELLED','RECONCILING','LOCAL_RECORD_CLOSED'])
def test_closed_or_cancelled_case_new_assessment_denied_history_kept(simulation,change):
    f,p,e,a,context=simulation;record,data=assess(simulation,'before-block')
    with f[1].connect() as c:
        if change=='LOCAL_RECORD_CLOSED':
            c.execute("INSERT INTO case_local_lifecycles(preparation_id,case_id,state,revision,cycle,verified_snapshot,verified_sha256) VALUES(%s,%s,%s,1,1,'{}',repeat('a',64))",(UUID(p['preparation_id']),UUID(p['case_id']),change))
        else:c.execute('UPDATE cases SET state=%s WHERE id=%s',(change,UUID(p['case_id'])))
    with pytest.raises(Conflict):a.assess(f[2]['fixture-a'],UUID(p['preparation_id']),'after-block',data)
    v=read(simulation);assert v['result']['synthetic_simulated_condition_truth']=='UNKNOWN' and v['history'][0]['result']==record['result']

def test_real_source_revision_epoch_evolution_old_key_preserved(simulation):
    f,p,e,a,context=simulation;record,data=assess(simulation,'old-release-key');old_release=a.bindings[0].release_id
    view=e.read('fixture-a',SCOPE);draft=deepcopy(view['draft']);draft['spec']['revision']='2';draft['spec']['eligibility']['expected']=3
    draft['spec']['source_refs'][0]['revision']='2';draft['sources'][0]['ref']['revision']='2';draft['sources'][0]['text']='SYNTHETIC explicitly revised mechanical comparison'
    for action,actor in [('SAVE','fixture-a'),('SUBMIT','fixture-a'),('REVIEW','mock-reviewer'),('PUBLISH','mock-publisher')]:
        view=e.read(actor,SCOPE)
        e.command(actor,SCOPE,uuid4().hex,Command(action=action,expected_revision=view['revision'],expected_content_sha256=view['content_sha256'],reason='SYNTHETIC new reviewed version',draft=Draft.model_validate(draft) if action=='SAVE' else None,publish_validity=VALID if action=='PUBLISH' else None))
    old=read(simulation);assert old['result']['synthetic_simulated_condition_truth']=='UNKNOWN' and old['history'][0]['current_truth']=='UNKNOWN'
    assert a.assess(f[2]['fixture-a'],UUID(p['preparation_id']),'old-release-key',data)==record
    assert a.recover(f[2]['fixture-a'],UUID(p['preparation_id']),'old-release-key',context)['receipt']['id']==record['id']
    new_release=e.read('fixture-a',SCOPE)['releases'][-1];assert new_release['id']!=old_release
    a.bindings=(a.bindings[0].model_copy(update={'release_id':new_release['id'],'content_sha256':new_release['content_sha256'],'epoch':2}),)
    new=read(simulation);assert new['result']['synthetic_simulated_condition_truth']=='FALSE' and new['history'][0]['current_truth']=='UNKNOWN'
    assert new['history'][0]['result']==record['result'] and new['sources']['binding']['epoch']==2

def test_region_selected_expired_at_business_date_even_while_other_facts_current(simulation):
    from test_case_fact_clarifications_integration import fact_body
    f,p,e,a,context=simulation;now=datetime.now(timezone.utc)
    body=fact_body('region','REGION_A','short-region');body['validity']['valid_until']=(now+timedelta(hours=1)).isoformat()
    response=f[3].post('/api/facts',headers=headers(f[2],key=uuid4().hex),json=body);assert response.status_code==201,response.text
    current=fact_read(f,p).json();selected={x['field_name']:x['id'] for x in current['sources']};selected['region']=response.json()['fact_id']
    data=confirm_body(f,p,selected);response=f[3].post('/api/preparations/'+p['preparation_id']+'/fact-clarifications/confirm',headers=headers(f[2],key=uuid4().hex),json=data);assert response.status_code==200,response.text
    v=a.read(f[2]['fixture-a'],UUID(p['preparation_id']),context.model_copy(update={'as_of':(now+timedelta(days=2)).isoformat()}))
    assert v['sources']['purpose_status']['state']=='CURRENT' and v['sources']['region_condition']['truth']=='UNKNOWN'
    assert v['result']['synthetic_simulated_condition_truth']=='UNKNOWN'

@pytest.mark.parametrize('corruption',['missing-trigger','noop-trigger','extra-column','extra-table'])
def test_retained_simulation_journal_invalid_schema_refused_before_any_ddl(tmp_path,corruption):
    path=tmp_path/'retained.synthetic-readiness.sqlite3';sr.SimulationJournal(path)
    with sqlite3.connect(path) as c:
        if corruption=='missing-trigger':c.execute('DROP TRIGGER simulation_immutable_update')
        elif corruption=='noop-trigger':
            c.execute('DROP TRIGGER simulation_immutable_update');c.execute('CREATE TRIGGER simulation_immutable_update BEFORE UPDATE ON simulation_assessments BEGIN SELECT 1; END')
        elif corruption=='extra-column':c.execute('ALTER TABLE simulation_assessments ADD COLUMN foreign_column TEXT')
        else:c.execute('CREATE TABLE foreign_table(value TEXT)')
    before=path.read_bytes()
    with pytest.raises(Conflict):sr.SimulationJournal(path)
    assert path.read_bytes()==before

def test_assessment_requires_nonblank_explicit_reason():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):sr.Assess(context=sr.Context(binding_id='x',as_of=datetime.now(timezone.utc).isoformat()),expected_preparation_revision=1,expected_source_sha256='0'*64,reason='  ')

def test_missing_current_rule_source_preserves_committed_journal_get_only(simulation):
    f,p,e,a,context=simulation;record,data=assess(simulation,'saved-before-source-loss')
    with e.repository.connect(write=True) as c:c.execute('DELETE FROM candidate_releases')
    recovered=a.recover(f[2]['fixture-a'],UUID(p['preparation_id']),'saved-before-source-loss',context)
    assert recovered['status']=='COMMITTED' and recovered['receipt']['id']==record['id']
    assert recovered['receipt']['result']==record['result'] and recovered['receipt']['current_truth']=='UNKNOWN'
    assert recovered['current']['result']['synthetic_simulated_condition_truth']=='UNKNOWN'
    assert recovered['current']['current_source_unavailable'] is True and not recovered['automatically_replayed']
    with pytest.raises(Conflict):a.assess(f[2]['fixture-a'],UUID(p['preparation_id']),'new-after-source-loss',data)
    cfg=e._config.model_copy(deep=True);next(x for x in cfg.permits if x.principal_id=='fixture-a').active=False;e.replace_test_contract(cfg)
    with pytest.raises(Denied):a.recover(f[2]['fixture-a'],UUID(p['preparation_id']),'saved-before-source-loss',context)
