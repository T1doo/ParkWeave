"""Independent PG/API/CLI oracle. All values/doc excerpts/mock outputs synthetic."""
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
import httpx
import psycopg
import pytest
from parkweave.store import Conflict,Store
from parkweave.fact_review_store import assess
from parkweave.candidate_review import MockCandidateModel
from test_facts_heartbeat import fact
from test_worker_gateway import runtime,auth,worker

FIELDS=['region','employees','service_need']

@pytest.fixture(autouse=True)
def forbid_provider_sockets(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('provider socket forbidden in SYNTHETIC R3 tests')
    monkeypatch.setattr(httpx.HTTPTransport,'handle_request',forbidden)

def candidate(value,field='region',revision='1',origin='DOCUMENT_EVIDENCE',expired=False):
    return fact(value,'synthetic-source',field,expired)|{'origin':origin,'source_ref':{'id':'synthetic-source','kind':'SYNTHETIC','revision':revision}}

def submit(fixture,items=None,key='candidate-review',fields=FIELDS):
    store,owner,tokens,client=fixture
    response=client.post('/api/runs',headers=auth(tokens,key=key),json={'goal':'SYNTHETIC three-field candidate review','action':'facts.assess','fact_fields':fields,'candidate_review':True,'fact_candidates':items or []})
    assert response.status_code==202,response.text
    return response.json()['run_id']

def view(fixture,run,user='fixture-a'):
    return fixture[3].get('/api/runs/'+run+'/fact-review',headers=auth(fixture[2],user))

def execute(fixture,run):
    store=fixture[0];claim=store.claim('candidate-worker');assert str(claim['id'])==run;assess(store,claim)

def answer(fixture,run,body,key='answer'):
    return fixture[3].post('/api/runs/'+run+'/clarifications',headers=auth(fixture[2],key=key),json=body)

def test_normal_cli_source_projection_questions_and_independent_hash(fixture):
    store,owner,tokens,client=fixture
    items=[candidate('合成甲',revision='1',origin='USER_STATEMENT'),candidate('合成乙',revision='2'),candidate(12,'employees')]
    run=submit(fixture,items)
    from parkweave.process_env import minimal_environment
    import os
    proc=subprocess.run([sys.executable,'-m','parkweave.worker','--once'],env=minimal_environment(os.environ,PARKWEAVE_DSN=store.dsn),capture_output=True,text=True,timeout=10)
    assert proc.returncode==0,(proc.stdout,proc.stderr)
    result=view(fixture,run).json();doc=result['document']
    assert hashlib.sha256(json.dumps(doc,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()==result['sha256']
    assert [(x['field'],x['state'],x['reason']) for x in doc['results']]==[('region','UNKNOWN','CONFLICT'),('employees','UNKNOWN','UNVERIFIED'),('service_need','UNKNOWN','MISSING')]
    assert [x['field'] for x in doc['necessary_questions']]==FIELDS and all(q['required'] for q in doc['necessary_questions'])
    region=doc['results'][0]['evidence']
    assert {x['origin'] for x in region}=={'USER_STATEMENT','DOCUMENT_EVIDENCE','MODEL_CANDIDATE'}
    assert {(x['source_ref']['revision'],x['value']) for x in region}=={('1','合成甲'),('2','合成乙')}
    assert all(x['verification']=='UNVERIFIED' for r in doc['results'] for x in r['evidence'])
    assert doc['qualification_decision']=='NOT_EVALUATED' and doc['external_acceptance']=='NOT_SUBMITTED' and doc['offline_fulfillment']=='NO_EVIDENCE'
    with owner.connect() as c:
        r=c.execute('SELECT * FROM runs WHERE id=%s',(run,)).fetchone();op=c.execute('SELECT * FROM operations WHERE run_id=%s',(run,)).fetchone()
        assert r['state']=='SUCCEEDED' and r['success_scope']=='CANDIDATES_REVIEWED_UNVERIFIED' and op['state']=='VERIFIED'
        assert op['receipt']['review_sha256']==result['sha256']
        assert c.execute('SELECT count(*) n FROM fact_assertions').fetchone()['n']==0
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==0

def test_existing_assertion_history_not_promoted_or_overwritten(fixture):
    store,owner,tokens,client=fixture
    saved=client.post('/api/facts',headers=auth(tokens,key='old'),json=fact('合成甲')).json()['fact_id']
    with owner.connect() as c:before=c.execute('SELECT * FROM fact_assertions WHERE id=%s',(saved,)).fetchone()
    run=submit(fixture,[candidate('合成乙')]);execute(fixture,run)
    doc=view(fixture,run).json()['document'];assert doc['results'][0]['reason']=='CONFLICT'
    assert any(x.get('fact_id')==saved for x in doc['results'][0]['evidence'])
    with owner.connect() as c:assert c.execute('SELECT * FROM fact_assertions WHERE id=%s',(saved,)).fetchone()==before

def test_expired_source_and_empty_fields_unknown(fixture):
    run=submit(fixture,[candidate('旧合成',expired=True)]);execute(fixture,run)
    assert [r['reason'] for r in view(fixture,run).json()['document']['results']]==['EXPIRED','MISSING','MISSING']

@pytest.mark.parametrize('user',['fixture-b','fixture-c'])
def test_cross_org_park_review_and_answer_denied(fixture,user):
    run=submit(fixture);execute(fixture,run);review=view(fixture,run).json()
    assert view(fixture,run,user).status_code==403
    assert fixture[3].post('/api/runs/'+run+'/clarifications',headers=auth(fixture[2],user),json={'review_sha256':review['sha256'],'decision':'CANCEL'}).status_code==403

def test_current_read_write_and_role_intersection(fixture):
    store,owner,tokens,client=fixture;run=submit(fixture);execute(fixture,run);review=view(fixture,run).json()
    owner.revoke_field('fixture-a','region','WRITE')
    assert answer(fixture,run,{'review_sha256':review['sha256'],'decision':'ANSWER','answers':[fact('合成补充')]}).status_code==403
    assert view(fixture,run).status_code==200
    owner.revoke_field('fixture-a','region','READ');assert view(fixture,run).status_code==403
    assert client.get('/api/runs/'+run,headers=auth(tokens)).status_code==403

def test_assigned_status_role_never_reads_candidates(fixture):
    store,owner,tokens,client=fixture;run=submit(fixture);execute(fixture,run)
    with owner.connect() as c:
        c.execute("UPDATE principals SET role='park_specialist',org_id='org-a' WHERE id='fixture-b'")
        c.execute("INSERT INTO capability_grants VALUES('fixture-b','READ',true,1,'park-a','org-a') ON CONFLICT(principal_id,capability) DO UPDATE SET org_id='org-a'")
    owner.assign_status('fixture-b',run)
    assert client.get('/api/runs/'+run,headers=auth(tokens,'fixture-b')).json()['visibility']=='ASSIGNED_STATUS_ONLY'
    assert view(fixture,run,'fixture-b').status_code==403

@pytest.mark.parametrize('capability',['READ','WRITE'])
def test_queued_revoke_no_review_side_effect(fixture,capability):
    store,owner,*_=fixture;run=submit(fixture);owner.revoke_field('fixture-a','employees',capability);execute(fixture,run)
    with owner.connect() as c:
        assert c.execute('SELECT state FROM runs WHERE id=%s',(run,)).fetchone()['state']=='FAILED'
        assert c.execute('SELECT count(*) n FROM fact_reviews').fetchone()['n']==0

def test_revocation_after_mock_projection_rechecked(fixture):
    store,owner,*_=fixture;run=submit(fixture,[candidate('合成')])
    class RevokingModel(MockCandidateModel):
        def propose(self,evidence):owner.revoke_field('fixture-a','region','WRITE');return super().propose(evidence)
    assess(store,store.claim('mock'),RevokingModel())
    with owner.connect() as c:assert c.execute('SELECT count(*) n FROM fact_reviews').fetchone()['n']==0

@pytest.mark.parametrize('control',['pause','cancel'])
def test_control_during_mock_wait_old_fence_cannot_publish(fixture,control):
    store,owner,tokens,client=fixture;run=submit(fixture,[candidate('合成')]);claim=store.claim('old-mock')
    class ControlledModel(MockCandidateModel):
        def propose(self,evidence):
            assert client.post('/api/runs/'+run+'/'+control,headers=auth(tokens)).status_code==200
            return super().propose(evidence)
    with pytest.raises(Conflict):assess(store,claim,ControlledModel())
    with owner.connect() as c:assert c.execute('SELECT count(*) n FROM fact_reviews').fetchone()['n']==0
    if control=='pause':
        assert client.post('/api/runs/'+run+'/resume',headers=auth(tokens)).status_code==200
        execute(fixture,run);assert view(fixture,run).status_code==200
    else:assert store.claim('cancelled') is None

def test_mock_value_disagrees_preserve_source_and_stays_unknown(fixture):
    run=submit(fixture,[candidate('来源自述')])
    class DisagreeingModel(MockCandidateModel):
        def propose(self,evidence):
            output=json.loads(super().propose(evidence));output[0]['value']='模型另一个候选';return json.dumps(output)
    assess(fixture[0],fixture[0].claim('disagree'),DisagreeingModel())
    result=view(fixture,run).json()['document']['results'][0]
    assert result['state']=='UNKNOWN' and result['reason']=='CONFLICT'
    assert {(x['origin'],x['value']) for x in result['evidence']}=={('DOCUMENT_EVIDENCE','来源自述'),('MODEL_CANDIDATE','模型另一个候选')}

def test_clarification_append_only_lineage_retry_conflict_and_cancel(fixture):
    store,owner,*_=fixture;parent=submit(fixture,[candidate('甲',revision='1')]);execute(fixture,parent);original=view(fixture,parent).json()
    body={'review_sha256':original['sha256'],'decision':'ANSWER','answers':[fact('乙','synthetic-source')|{'source_ref':{'id':'synthetic-source','kind':'SYNTHETIC','revision':'2'}}]}
    first=answer(fixture,parent,body);assert first.status_code==202
    child=first.json()['run_id'];assert answer(fixture,parent,body).json()==first.json()
    assert answer(fixture,parent,body|{'decision':'CANCEL','answers':[]}).status_code==409
    assert answer(fixture,parent,body|{'review_sha256':'0'*64},key='wrong-parent').status_code==409
    execute(fixture,child);new=view(fixture,child).json()
    assert new['document']['results'][0]['reason']=='CONFLICT'
    assert {x['source_ref']['revision'] for x in new['document']['results'][0]['evidence']}=={'1','2'}
    assert original['document']==view(fixture,parent).json()['document'] and original['sha256']==view(fixture,parent).json()['sha256']
    cancelled=answer(fixture,parent,{'review_sha256':original['sha256'],'decision':'CANCEL'},key='cancel')
    assert cancelled.status_code==202 and cancelled.json()['run_id'] is None
    assert answer(fixture,parent,{'review_sha256':original['sha256'],'decision':'CANCEL'},key='cancel').json()==cancelled.json()
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==2
        assert c.execute('SELECT count(*) n FROM fact_reviews').fetchone()['n']==2
        assert c.execute('SELECT count(*) n FROM fact_followups').fetchone()['n']==2

def test_missing_answer_becomes_only_unverified_not_known(fixture):
    parent=submit(fixture);execute(fixture,parent);review=view(fixture,parent).json()
    reply=answer(fixture,parent,{'review_sha256':review['sha256'],'decision':'ANSWER','answers':[fact(7,field='employees')]})
    child=reply.json()['run_id'];execute(fixture,child)
    results=view(fixture,child).json()['document']['results'];assert results[1]['state']=='UNKNOWN' and results[1]['reason']=='UNVERIFIED'
    assert all(x['origin'] in ('USER_STATEMENT','MODEL_CANDIDATE') for x in results[1]['evidence'])

def test_answer_retry_rechecks_grants_and_rejects_out_of_review_field(fixture):
    store,owner,*_=fixture;parent=submit(fixture,fields=['region']);execute(fixture,parent);review=view(fixture,parent).json()
    assert answer(fixture,parent,{'review_sha256':review['sha256'],'decision':'ANSWER','answers':[fact(1,field='employees')]}).status_code==409
    body={'review_sha256':review['sha256'],'decision':'ANSWER','answers':[fact('补充')]}
    assert answer(fixture,parent,body).status_code==202
    owner.revoke_field('fixture-a','region','WRITE')
    assert answer(fixture,parent,body).status_code==403

def test_cancel_queued_child_no_review_and_no_change_parent(fixture):
    parent=submit(fixture);execute(fixture,parent);review=view(fixture,parent).json()
    child=answer(fixture,parent,{'review_sha256':review['sha256'],'decision':'ANSWER','answers':[fact('补充')]}).json()['run_id']
    assert fixture[3].post('/api/runs/'+child+'/cancel',headers=auth(fixture[2])).status_code==200
    assert fixture[0].claim('cancelled-child') is None
    assert view(fixture,parent).json()['document']==review['document']
    with fixture[1].connect() as c:assert c.execute('SELECT count(*) n FROM fact_reviews').fetchone()['n']==1

def test_review_transaction_failure_restart_fence_and_immutable_history(fixture):
    store,owner,*_=fixture;run=submit(fixture);old=store.claim('interrupted')
    with pytest.raises(RuntimeError):assess(store,old,fail_before_commit=True)
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM fact_reviews').fetchone()['n']==0
        assert c.execute('SELECT state FROM operations WHERE run_id=%s',(run,)).fetchone()['state']=='PREPARED'
        c.execute("UPDATE runs SET lease_until=clock_timestamp()-interval '1 second' WHERE id=%s",(run,))
    fresh=store.claim('recovery');assess(store,fresh)
    with pytest.raises(Conflict):assess(store,old)
    for table in ('fact_reviews','fact_followups'):
        for verb in ('UPDATE '+table+' SET '+('sha256=sha256' if table=='fact_reviews' else 'fingerprint=fingerprint'),'DELETE FROM '+table):
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                with store.connect() as c:c.execute(verb)
    before=view(fixture,run).json();owner.migrate();assert view(fixture,run).json()==before

@pytest.mark.parametrize('mutation',['source','verified','field','duplicate-json','nonfinite'])
def test_invalid_mock_projection_never_persisted(fixture,mutation):
    store,owner,*_=fixture;run=submit(fixture,[candidate('合成')])
    class BadModel(MockCandidateModel):
        def propose(self,evidence):
            raw=super().propose(evidence);parsed=json.loads(raw)
            if mutation=='source':parsed[0]['source_ref']['revision']='forged'
            elif mutation=='verified':parsed[0]['verification']='VERIFIED'
            elif mutation=='field':parsed[0]['field']='employees';parsed[0]['value']=1;parsed[0]['unit']='people'
            elif mutation=='duplicate-json':return raw.replace('"field": "region"','"field": "region", "field": "employees"')
            elif mutation=='nonfinite':return '[NaN]'
            return json.dumps(parsed)
    assess(store,store.claim('bad-mock'),BadModel())
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM fact_reviews').fetchone()['n']==0
        assert c.execute('SELECT receipt FROM operations WHERE run_id=%s',(run,)).fetchone()['receipt']['reason']=='INVALID_CANDIDATE_PROJECTION'

@pytest.mark.parametrize('change',[{'origin':'MODEL_CANDIDATE'},{'verification':'VERIFIED'},{'field':'new_field'},{'source_ref':{'id':'real','kind':'AUTHORIZED_REAL','revision':'1'}}])
def test_untrusted_candidate_contract_rejects_origin_promotion_new_field_real_source(fixture,change):
    response=fixture[3].post('/api/runs',headers=auth(fixture[2]),json={'goal':'SYNTHETIC','action':'facts.assess','fact_fields':FIELDS,'candidate_review':True,'fact_candidates':[candidate('x')|change]})
    assert response.status_code==422

def test_concurrent_clarification_same_key_one_child(fixture):
    store,owner,tokens,client=fixture;parent=submit(fixture);execute(fixture,parent);review=view(fixture,parent).json()
    from parkweave.fact_review_store import followup
    from parkweave.domain import ClarificationInput
    body=ClarificationInput.model_validate({'review_sha256':review['sha256'],'decision':'ANSWER','answers':[fact('合成')]})
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:followup(store,tokens['fixture-a'],parent,'shared-key',body),range(4)))
    assert len({r['run_id'] for r in results})==1
    with owner.connect() as c:assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==2
