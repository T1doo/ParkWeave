"""P3 original commands on real PG, exact source qualifications, no formal writes."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import UUID,uuid4
import json,secrets,sqlite3
import pytest
from fastapi.testclient import TestClient
from parkweave import dispatch_execution_preview as dp,isolated_execution_preview as ep
from parkweave import service_dispatches as sd,executor_receipts as er,preparation as prep,bounded_planning as planning
from parkweave.store import Store,Denied,digest
from parkweave.api import create_app
from test_resource_execution_preview import setup as p2_setup,execute as p2_execute
from test_isolated_execution_preview import preparation_fixture,snapshot,execute as p1_execute,add
from test_executor_receipts import receipt_fixture
from test_isolated_run_access import access_fixture
from test_preparation import headers


def setup(f,tmp_path,slots=2,goals=None):
    p,p1,p2=p2_setup(f,tmp_path,slots,goals)
    # Explicit original synthetic fixture qualification; preview runtime never does this.
    if 'executor-a' not in f[2]:
        token=secrets.token_urlsafe(32);f[2]['executor-a']=token
        with f[1].connect() as c:
            c.execute("INSERT INTO principals VALUES('executor-a',%s,'park-a','org-a','service_executor',true)",(digest(token),))
            c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES('executor-a','READ','park-a','org-a')")
    f[1].assign_status('executor-a',UUID(p['run_id']),active=True)
    engine=dp.DispatchExecutionPreview(f[0],(tmp_path/('dispatch-preview-'+uuid4().hex)).resolve(),enabled_for_synthetic_preview=True)
    engine.attach_store(f[0]);return p,p1,p2,engine


def read(f,p,key=None,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/dispatch-execution-preview'+('/recovery/'+key if key else ''),headers=headers(f[2],user))


def body(f,p,decision='ACCEPT'):
    r=read(f,p);assert r.status_code==200,r.text;x=r.json();return dict(expected_preparation_revision=x['preparation_revision'],expected_request_revision=x['request_revision'],expected_source_sha256=x['current_source_sha256'],decision=decision)


def execute(f,p,b=None,key=None,user='fixture-a'):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/dispatch-execution-preview',headers=headers(f[2],user,key or uuid4().hex),json=b or body(f,p))


@pytest.mark.parametrize('decision',['ACCEPT','DECLINE'])
def test_original_dispatch_events_receipt_and_complete_enqueue_shadow_closure(receipt_fixture,tmp_path,monkeypatch,decision):
    f=receipt_fixture;p,p1,p2,e=setup(f,tmp_path);assert p1_execute(f,p).status_code==p2_execute(f,p).status_code==201
    old1=p1.path.read_bytes();old2=p2.path.read_bytes();before=snapshot(f);calls=[];connections=[]
    from parkweave import dispatch_notices as notices
    for module,name in ((sd,'offer'),(sd,'command'),(notices,'enqueue')):
        original=getattr(module,name)
        def observe(*args,_name=name,_original=original,**kwargs):
            proxy=args[0].connection if _name!='enqueue' else args[0];c=proxy._raw;connections.append(c)
            assert c.execute('SHOW search_path').fetchone()['search_path']=='pg_temp'
            assert {r['relname'] for r in c.execute("SELECT relname FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")}==set(dp.TABLES)
            calls.append(_name);return _original(*args,**kwargs)
        monkeypatch.setattr(module,name,observe)
    r=execute(f,p,body(f,p,decision));assert r.status_code==201,r.text;x=r.json()['result'];a=x['artifact']
    assert calls==['offer','enqueue','command','enqueue'] and all(c.closed for c in connections)
    assert x['state']=='SUCCEEDED' and a['p3_state']==('ACCEPTED' if decision=='ACCEPT' else 'DECLINED')
    assert [v['action'] for v in a['dispatch_events']]==['OFFER',decision]
    assert a['dispatch_events'][1]['actor_id']==a['executor_id'] and a['dispatch_events'][0]['actor_id']==a['p1']['reviewer_id']
    assert len(a['outbox'])==4 and all(o['state']=='PENDING' for o in a['outbox']) and not a['notices']
    assert len(a['steps'])==len(a['receipt_events'])==(1 if decision=='ACCEPT' else 0)
    assert a['p1']['case_id']==a['links'][0]['case_id']!=p['case_id'] and a['offers'][0]['preparation_sha256']==a['p1']['review_sha256']
    assert x['not_previewed']==['P4','P5'] and x['required_goals']==['LOCAL_CASE_RECORD_RECHECK','外部正式成果']
    assert x['binding']['participants']['executor_id']=='executor-a' and x['formal_writes']==0 and not x['new_grants'] and not x['case_goal_completed']
    assert snapshot(f)==before and p1.path.read_bytes()==old1 and p2.path.read_bytes()==old2
    dp.DispatchExecutionPreview(f[0],e.root,enabled_for_synthetic_preview=True).attach_store(f[0]);assert read(f,p).json()['history'][0]['document']==x


def test_offer_then_actual_material_version_change_rejects_accept_and_keeps_offer_history(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path);before=snapshot(f);original=sd.offer
    def replace_after_offer(store,token,id,key,data):
        result=original(store,token,id,key,data)
        c=store.connection._raw;owner=c.execute('SELECT * FROM preparations WHERE id=%s',(id,)).fetchone()['owner_id']
        # Only this disposable synthetic owner's fixture token is rotated;
        # the material change itself goes through original ADD_EVIDENCE.
        synthetic_token=secrets.token_urlsafe(32);c.execute('UPDATE principals SET token_hash=%s WHERE id=%s',(digest(synthetic_token),owner))
        prep.command(store,synthetic_token,id,uuid4().hex,prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=result['preparation_revision'],slot='need_summary',text='SYNTHETIC changed material version',source_kind='USER_STATEMENT',source_label='SYNTHETIC v2'))
        return result
    monkeypatch.setattr(sd,'offer',replace_after_offer);r=execute(f,p);assert r.status_code==201,r.text;x=r.json()['result'];a=x['artifact']
    assert x['state']=='FAILED' and a['p3_state']=='FAILED' and [e['action'] for e in a['dispatch_events']]==['OFFER']
    assert not a['steps'] and not a['receipt_events'] and len(a['outbox'])==2 and a['offers'][0]['state']=='OFFERED' and snapshot(f)==before
    monkeypatch.setattr(sd,'offer',original);assert execute(f,p).json()['result']['artifact']['p3_state']=='ACCEPTED'
    assert read(f,p).json()['history'][0]['document']==x and len(read(f,p).json()['history'])==2


@pytest.mark.parametrize('change',['executor_read','assignment','wrong_run','reviewer_read','reviewer_grant','reviewer_identity','executor_identity','owner_execute','hold'])
def test_original_qualification_revocation_precedes_replay_and_cold_get(receipt_fixture,tmp_path,change):
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;assert execute(f,p,b,key).status_code==201
    with f[1].connect() as c:
        actor='prep-specialist-fixture-a' if change.startswith('reviewer') else 'executor-a'
        if change in ('executor_read','reviewer_read'):c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=\'READ\'',(actor,))
        elif change in ('assignment','wrong_run'):c.execute('UPDATE run_assignments SET active=false WHERE principal_id=%s AND run_id=%s',(actor,p['run_id']))
        elif change=='reviewer_grant':c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(actor,))
        elif change.endswith('identity'):c.execute('UPDATE principals SET active=false WHERE id=%s',(actor,))
        elif change=='owner_execute':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        else:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    before=snapshot(f);old=e.path.read_bytes();assert read(f,p,key).status_code==execute(f,p,b,key).status_code==403 and snapshot(f)==before and e.path.read_bytes()==old


@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-a','prep-specialist-fixture-a'])
def test_other_tenant_role_cannot_preview_or_recover(receipt_fixture,tmp_path,user):
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f)
    assert read(f,p,user=user).status_code==execute(f,p,b,user=user).status_code==403 and snapshot(f)==before


def test_same_key_concurrent_decision_mismatch_cas_and_actual_new_store_get(receipt_fixture,tmp_path):
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f)
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:e.execute(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),key,dp.Execute(**b)),range(2)))
    assert results[0]['result']==results[1]['result'] and len(read(f,p).json()['history'])==1
    s=Store(f[0].dsn);dp.DispatchExecutionPreview(s,e.root,enabled_for_synthetic_preview=True).attach_store(s)
    with TestClient(create_app(s)) as client:
        r=client.get('/api/preparations/'+p['preparation_id']+'/dispatch-execution-preview/recovery/'+key,headers=headers(f[2]));assert r.json()['result']==results[0]['result'] and r.json()['automatically_replayed'] is False
    assert execute(f,p,{**b,'decision':'DECLINE'},key).status_code==409
    assert execute(f,p,{**b,'expected_request_revision':b['expected_request_revision']+1}).status_code==409 and snapshot(f)==before


def test_closed_sql_formal_uuid_consumption_drift_and_default_off(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path);b=body(f,p);original=sd.command
    def check(store,*args,**kwargs):
        for q in ('SELECT * FROM public.service_dispatches','SET search_path TO public','SELECT set_config(%s,%s,true)','COMMIT',"INSERT INTO service_step_receipts VALUES('fake')",'INSERT INTO dispatch_notices VALUES(%s,%s)'):
            with pytest.raises(Denied):store.connection.execute(q)
        assert not hasattr(store.connection,'commit') and not hasattr(store,'dsn');return original(store,*args,**kwargs)
    monkeypatch.setattr(sd,'command',check);x=execute(f,p,b).json()['result'];monkeypatch.setattr(sd,'command',original);before=snapshot(f);a=x['artifact']
    assert f[3].get('/api/service-dispatches/'+a['offers'][0]['dispatch_id'],headers=headers(f[2])).status_code==403
    assert f[3].get('/api/executor-receipts/'+a['steps'][0]['id'],headers=headers(f[2])).status_code==403
    assert f[3].post('/api/service-dispatches/'+a['offers'][0]['dispatch_id']+'/commands',headers=headers(f[2],'executor-a',uuid4().hex),json={'action':'ACCEPT','expected_revision':1,'reason':'SYNTHETIC'}).status_code==403
    with TestClient(create_app(Store(f[0].dsn))) as client:assert client.get('/api/preparations/'+p['preparation_id']+'/dispatch-execution-preview',headers=headers(f[2])).status_code==403
    for extra in ({'executor_id':'executor-a'},{'sql':'SELECT 1'},{'role':'service_executor'},{'decision':'SUBMIT'}):assert execute(f,p,{**b,**extra}).status_code==422
    monkeypatch.setitem(planning.ACTIONS,'P3',[{**dp.P3_ACTIONS[0],'commands':['UNKNOWN']},dp.P3_ACTIONS[1]])
    assert read(f,p).json()['execution_available'] is False and execute(f,p).status_code==409 and snapshot(f)==before


def test_proof_body_rehash_cannot_replace_acceptance_event_or_goals(receipt_fixture,tmp_path):
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path);x=execute(f,p).json()['result']
    with sqlite3.connect(e.path) as db:db.row_factory=sqlite3.Row;row=dict(db.execute('SELECT * FROM previews').fetchone())
    for target in ('event','step','outbox','decision','goals'):
        doc=json.loads(row['document'])
        if target=='event':doc['artifact']['dispatch_events'][1]['actor_id']='fixture-a'
        elif target=='step':doc['artifact']['steps']=[]
        elif target=='outbox':doc['artifact']['outbox']=[]
        elif target=='decision':doc['decision']='DECLINE'
        else:doc['required_goals']=[]
        doc['sha256']=ep._sha({k:v for k,v in doc.items() if k!='sha256'})
        with pytest.raises(Exception,match='proof unavailable'):e._document({**row,'document':json.dumps(doc)})
    assert read(f,p).json()['history'][0]['document']==x


def test_lost_after_commit_get_exact_and_temp_infrastructure_fault_no_artifact(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f);key=uuid4().hex;original=sd.command;connections=[]
    def fail(store,*args,**kwargs):
        result=original(store,*args,**kwargs);connections.append(store.connection._raw);raise ep.Unavailable('SYNTHETIC after shadow accept')
    monkeypatch.setattr(sd,'command',fail);assert execute(f,p,b,key).status_code==503 and all(c.closed for c in connections)
    assert read(f,p,key).json()['status']=='NOT_OBSERVED' and snapshot(f)==before
    monkeypatch.setattr(sd,'command',original);compare=e._comparison;count=[]
    def response(*args):
        count.append(1)
        if len(count)==2:raise ep.Unavailable('SYNTHETIC after committed artifact')
        return compare(*args)
    monkeypatch.setattr(e,'_comparison',response);assert execute(f,p,b,key).status_code==503
    assert read(f,p,key).json()['status']=='COMMITTED' and read(f,p,key).json()['result']['artifact']['p3_state']=='ACCEPTED' and snapshot(f)==before


def test_material_source_change_retains_old_stale_result_explicit_new_binding(receipt_fixture,tmp_path):
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;x=execute(f,p,b,key).json()['result'];p=add(f,p,text='SYNTHETIC source v2').json();before=snapshot(f)
    assert execute(f,p,b).status_code==409 and read(f,p,key).json()['result']==x
    assert read(f,p).json()['history'][0]['source_state']=='STALE' and execute(f,p).json()['result']['binding']['preparation_revision']!=x['binding']['preparation_revision'] and snapshot(f)==before


@pytest.mark.parametrize('cause',['p1','p2'])
def test_failed_prior_actual_steps_do_not_offer_dispatch(receipt_fixture,tmp_path,cause):
    from parkweave import resource_combinations as rc
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path,slots=1 if cause=='p1' else 2)
    if cause=='p2':
        with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET enabled=false WHERE id=%s',(rc.SECOND_RESOURCE_ID,))
    before=snapshot(f);r=execute(f,p);assert r.status_code==201,r.text;x=r.json()['result'];a=x['artifact']
    assert x['state']=='FAILED' and a['p3_state']=='NOT_EXECUTED' and 'P3' in x['not_previewed'] and not a['offers'] and not a['dispatch_events'] and not a['outbox'] and snapshot(f)==before


@pytest.mark.parametrize('cause',['missing','multiple','wrong_run'])
def test_exact_run_unique_existing_assignment_required_without_repair(receipt_fixture,tmp_path,cause):
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path)
    if cause=='multiple':f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
    else:
        f[1].assign_status('executor-a',UUID(p['run_id']),active=False)
        if cause=='wrong_run':
            other,_,_,_=setup(f,tmp_path)
            assert other['run_id']!=p['run_id']
    before=snapshot(f);old=e.path.read_bytes()
    assert read(f,p).status_code==403 and snapshot(f)==before and e.path.read_bytes()==old


def test_sqlite_commit_fault_and_uncooperative_source_change_never_save_false_current(receipt_fixture,tmp_path,monkeypatch):
    from parkweave import resource_holds as rh
    f=receipt_fixture;p,_,_,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f);database=e._database
    class FailCommit:
        def __init__(self,db):self.db=db
        def execute(self,*args):return self.db.execute(*args)
        def commit(self):raise ep.Unavailable('SYNTHETIC SQLite fault')
    @contextmanager
    def failed():
        with database() as db:yield FailCommit(db)
    monkeypatch.setattr(e,'_database',failed);assert execute(f,p,b,key).status_code==503
    monkeypatch.setattr(e,'_database',database);assert read(f,p,key).json()['status']=='NOT_OBSERVED' and snapshot(f)==before
    original=e._execute;changed=[]
    def mutate(*args):
        result=original(*args)
        with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET revision=revision+1 WHERE id=%s',(rh.RESOURCE_ID,))
        changed.append(snapshot(f));return result
    monkeypatch.setattr(e,'_execute',mutate);assert execute(f,p,b,key).status_code==409
    assert read(f,p,key).json()['status']=='NOT_OBSERVED' and snapshot(f)==changed[0]


def test_managed_original_executor_lease_expiry_at_sqlite_wait_denies_commit_and_recovery(access_fixture,tmp_path,monkeypatch):
    from datetime import timedelta
    from threading import Event
    from test_isolated_run_access import approved
    from test_request_intents import save
    from parkweave import resource_combinations as rc,resource_execution_preview as rp
    a=access_fixture;approved(a);f,p,bridge,now,_=a;rc.seed_synthetic(f[1])
    p={**p,'revision':save(f,p,goals=['LOCAL_INTERNAL_ACCEPTANCE']).json()['revision']}
    e=dp.DispatchExecutionPreview(f[0],(tmp_path/'managed-p3-preview').resolve(),enabled_for_synthetic_preview=True);e.attach_store(f[0])
    b=body(f,p);key=uuid4().hex;before=snapshot(f);entered=Event();database=e._database
    @contextmanager
    def observed():
        with database() as db:
            db.set_trace_callback(lambda q:entered.set() if q=='BEGIN EXCLUSIVE' else None);yield db
    monkeypatch.setattr(e,'_database',observed);blocker=sqlite3.connect(e.path);blocker.execute('BEGIN IMMEDIATE')
    try:
        with ThreadPoolExecutor(1) as pool:
            pending=pool.submit(execute,f,p,b,key)
            assert entered.wait(5) and not pending.done();now[0]+=timedelta(minutes=11);blocker.rollback();r=pending.result(timeout=15)
        assert r.status_code==403 and snapshot(f)==before
        with sqlite3.connect(e.path) as db:assert db.execute('SELECT count(*) FROM previews').fetchone()[0]==0
        assert read(f,p,key).status_code==403
    finally:blocker.close()
