"""Original local adapter and simulated enterprise commands in discarded PG shadows."""
from uuid import UUID,uuid4
from pathlib import Path
OUT=Path('.runtime/p4-receipt-execution-preview/api')
import pytest
from parkweave import receipt_execution_preview as p4,isolated_local_execution as local,executor_receipts as er,dispatch_execution_preview as dp
from parkweave.api import create_app
from test_isolated_run_access import access_fixture,approved
from test_executor_receipts import receipt_fixture
from test_isolated_execution_preview import preparation_fixture,snapshot,execute as p1_execute
from test_resource_execution_preview import setup as p2_setup,execute as p2_execute
from test_dispatch_execution_preview import execute as p3_execute
from test_preparation import headers

@pytest.fixture
def receipt_preview_fixture(access_fixture,tmp_path):
    a=access_fixture;f=a[0];p,p1,p2=p2_setup(f,tmp_path)
    approved((f,p,a[2],a[3],a[4]))
    local.IsolatedLocalExecutor(a[2],enabled_for_isolated_tests=True).attach_store(f[0])
    p3=dp.DispatchExecutionPreview(f[0],(tmp_path/'previous-p3').resolve(),enabled_for_synthetic_preview=True);p3.attach_store(f[0])
    e=p4.ReceiptExecutionPreview(f[0],(tmp_path/'receipt-preview').resolve(),enabled_for_synthetic_preview=True);e.attach_store(f[0])
    return f,p,p1,p2,p3,e,a

def read(f,p,key=None,user='fixture-a'):
    return f[3].get('/api/preparations/'+p['preparation_id']+'/receipt-execution-preview'+('/recovery/'+key if key else ''),headers=headers(f[2],user))
def body(f,p,decision='ACKNOWLEDGE'):
    r=read(f,p);assert r.status_code==200,r.text;x=r.json();return dict(expected_preparation_revision=x['preparation_revision'],expected_request_revision=x['request_revision'],expected_source_sha256=x['current_source_sha256'],review_decision=decision)
def execute(f,p,b=None,key=None,user='fixture-a'):
    return f[3].post('/api/preparations/'+p['preparation_id']+'/receipt-execution-preview',headers=headers(f[2],user,key or uuid4().hex),json=b or body(f,p))

@pytest.mark.parametrize('decision',['ACKNOWLEDGE','REQUEST_CHANGES'])
def test_original_adapter_submit_simulated_review_and_previous_bytes_unchanged(receipt_preview_fixture,monkeypatch,decision):
    f,p,p1,p2,p3,e,a=receipt_preview_fixture
    assert p1_execute(f,p).status_code==p2_execute(f,p).status_code==p3_execute(f,p).status_code==201
    previous=[x.path.read_bytes() for x in (p1,p2,p3)];before=snapshot(f);calls=[];connections=[];original=local.IsolatedLocalExecutor.generate
    def generated(adapter,store,c,row,parent):
        assert c._raw.execute('SHOW search_path').fetchone()['search_path']=='pg_temp'
        assert {r['relname'] for r in c._raw.execute("SELECT relname FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")}==set(p4.TABLES)
        calls.append('generate');connections.append(c._raw);return original(adapter,store,c,row,parent)
    monkeypatch.setattr(local.IsolatedLocalExecutor,'generate',generated)
    r=execute(f,p,body(f,p,decision));assert r.status_code==201,r.text;d=r.json()['result'];art=d['artifact']
    assert calls==['generate'] and all(c.closed for c in connections)
    assert art['p4_state']==('LOCAL_ACKNOWLEDGED' if decision=='ACKNOWLEDGE' else 'CHANGES_REQUESTED')
    assert [x['action'] for x in art['p4_events']]==['CREATE','SUBMIT',decision]
    assert len(art['p4_receipts'])==1 and art['p4_receipts'][0]['adapter_execution']['report']['adapter_id']==local.ADAPTER_ID
    assert len(art['outbox'])==4 and all(x['state']=='PENDING' for x in art['outbox']) and not art['notices']
    assert d['not_previewed']==['P5'] and d['required_goals']==['LOCAL_CASE_RECORD_RECHECK','外部正式成果'] and d['formal_writes']==0 and not d['case_goal_completed']
    assert snapshot(f)==before and [x.path.read_bytes() for x in (p1,p2,p3)]==previous


def schema(owner):
    with owner.connect() as c:return c.execute("SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position").fetchall()


def test_same_key_concurrency_fingerprint_cas_and_real_http_cold_objects(receipt_preview_fixture):
    from concurrent.futures import ThreadPoolExecutor
    from parkweave.store import Store
    from test_new_enterprise_local_chain import actual_http
    f,p,_,_,_,e,a=receipt_preview_fixture;b=body(f,p);key=uuid4().hex;before=snapshot(f);columns=schema(f[1])
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:e.execute(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),key,p4.Execute(**b)),range(2)))
    assert results[0]['result']==results[1]['result'] and len(read(f,p).json()['history'])==1
    data=e.path.read_bytes();s=Store(f[0].dsn);a[2].attach_store(s);f[0]._isolated_local_execution.attach_store(s)
    p4.ReceiptExecutionPreview(s,e.root,enabled_for_synthetic_preview=True).attach_store(s)
    with actual_http(create_app(s)) as (client,requests):
        r=client.get('/api/preparations/'+p['preparation_id']+'/receipt-execution-preview/recovery/'+key,headers=headers(f[2]));assert r.status_code==200 and r.json()['result']==results[0]['result'];assert {x['method'] for x in requests}=={'GET'}
    assert execute(f,p,{**b,'review_decision':'REQUEST_CHANGES'},key).status_code==409
    assert execute(f,p,{**b,'expected_request_revision':b['expected_request_revision']+1}).status_code==409
    assert e.path.read_bytes()==data and snapshot(f)==before and schema(f[1])==columns


@pytest.mark.parametrize('change',['executor_read','assignment','reviewer_grant','owner_execute','hold','adapter','proof','lease'])
def test_current_qualification_precedes_original_history_and_replay(receipt_preview_fixture,change):
    from datetime import timedelta
    f,p,_,_,_,e,a=receipt_preview_fixture;b=body(f,p);key=uuid4().hex;assert execute(f,p,b,key).status_code==201
    if change=='adapter':f[0]._isolated_local_execution=None
    elif change=='proof':a[2].proof=None
    elif change=='lease':a[3][0]+=timedelta(minutes=11)
    else:
        with f[1].connect() as c:
            if change=='executor_read':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
            elif change=='assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a' AND run_id=%s",(p['run_id'],))
            elif change=='reviewer_grant':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
            elif change=='owner_execute':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
            else:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    before=snapshot(f);data=e.path.read_bytes();assert read(f,p,key).status_code==execute(f,p,b,key).status_code==403
    assert e.path.read_bytes()==data and snapshot(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-a','prep-specialist-fixture-a'])
def test_wrong_role_tenant_cannot_execute_or_read(receipt_preview_fixture,user):
    f,p,_,_,_,e,_=receipt_preview_fixture;b=body(f,p);before=snapshot(f);assert read(f,p,user=user).status_code==execute(f,p,b,user=user).status_code==403 and snapshot(f)==before


@pytest.mark.parametrize('bad',['old_hash','material'])
def test_actual_submit_then_original_review_rejects_old_hash_or_material_preserves_history(receipt_preview_fixture,monkeypatch,bad):
    from parkweave import preparation as prep
    from parkweave.store import digest
    f,p,_,_,_,e,_=receipt_preview_fixture;before=snapshot(f);command=er.command;generated=[];token_factory=p4.secrets.token_urlsafe
    def capture(*args,**kwargs):
        token=token_factory(*args,**kwargs);generated.append(token);return token
    monkeypatch.setattr(p4.secrets,'token_urlsafe',capture)
    def intercept(store,token,id,key,data):
        if type(data) is er.Command and data.action=='ACKNOWLEDGE':
            if bad=='old_hash':data=data.model_copy(update={'receipt_sha256':'0'*64})
            else:
                c=store.connection._raw;parent=c.execute('SELECT * FROM preparations').fetchone();hashed=c.execute('SELECT token_hash FROM principals WHERE id=%s',(parent['owner_id'],)).fetchone()['token_hash'];owner=next(t for t in generated if digest(t)==hashed)
                prep.command(store,owner,parent['id'],uuid4().hex,prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=parent['revision'],slot='need_summary',text='SYNTHETIC new original material after execution',source_kind='USER_STATEMENT',source_label='SYNTHETIC version2'))
        return command(store,token,id,key,data)
    monkeypatch.setattr(er,'command',intercept);key=uuid4().hex;r=execute(f,p,key=key);assert r.status_code==201,r.text;old=r.json()['result'];art=old['artifact']
    assert old['state']=='FAILED' and art['p4_state']=='FAILED' and [x['action'] for x in art['p4_events']]==['CREATE','SUBMIT'] and len(art['p4_receipts'])==1 and art['p4_steps'][0]['state']=='RECEIPT_RECORDED'
    assert not art['local_current_at_execution'] and snapshot(f)==before
    monkeypatch.undo();assert execute(f,p).json()['result']['artifact']['p4_state']=='LOCAL_ACKNOWLEDGED' and read(f,p,key).json()['result']==old and snapshot(f)==before


def test_duplicate_original_submit_and_review_one_execution_and_no_manual_fallback(receipt_preview_fixture,monkeypatch):
    from parkweave.store import Conflict,Denied
    f,p,_,_,_,e,_=receipt_preview_fixture;before=snapshot(f);command=er.command;ids=[];generated=local.IsolatedLocalExecutor.generate;calls=[]
    def generate(*args,**kw):calls.append('actual');return generated(*args,**kw)
    def repeat(store,token,id,key,data):
        first=command(store,token,id,key,data);again=command(store,token,id,key,data)
        assert first['current_receipt']['id']==again['current_receipt']['id'];ids.append(first['current_receipt']['adapter_execution']['report']['execution_id'])
        if type(data) is local.ExecuteLocal:
            with pytest.raises(Conflict):command(store,token,id,uuid4().hex,er.Command(action='SUBMIT',expected_revision=first['step']['revision'],text='SYNTHETIC hand written replacement',source_kind='SYNTHETIC',source_label='SYNTHETIC'))
        for query in ('COMMIT','SELECT * FROM public.service_step_receipts','INSERT INTO dispatch_notices VALUES(%s,%s)',"INSERT INTO service_step_receipts VALUES('manual')"):
            with pytest.raises(Denied):store.connection.execute(query)
        with pytest.raises(Denied):store.connection.cursor(row_factory=dict).execute('SELECT 1')
        with pytest.raises(Denied):store.connection.commit()
        assert not hasattr(store.connection.execute('SELECT * FROM principals WHERE id=%s',(first['step']['owner_id'],)),'execute') and not hasattr(store.connection.info,'dsn')
        return again
    monkeypatch.setattr(local.IsolatedLocalExecutor,'generate',generate);monkeypatch.setattr(er,'command',repeat);r=execute(f,p);assert r.status_code==201,r.text
    assert calls==['actual'] and len(set(ids))==1 and len(r.json()['result']['artifact']['p4_events'])==3 and snapshot(f)==before


@pytest.mark.parametrize('target',['report','receipt','actor','decision','goals','outbox'])
def test_body_only_rehash_does_not_replace_full_independent_proof(receipt_preview_fixture,target):
    import json,sqlite3
    from parkweave import isolated_execution_preview as ep,preparation as prep
    f,p,_,_,_,e,_=receipt_preview_fixture;key=uuid4().hex;d=execute(f,p,key=key).json()['result'];before=snapshot(f)
    if target=='report':d['artifact']['p4_receipts'][0]['adapter_execution']['report']['execution_id']=str(uuid4())
    elif target=='receipt':d['artifact']['p4_receipts'][0]['source_sha256']='0'*64
    elif target=='actor':d['artifact']['p4_events'][2]['actor_id']=d['artifact']['executor_id']
    elif target=='decision':d['review_decision']='REQUEST_CHANGES'
    elif target=='goals':d['required_goals']=[]
    else:d['artifact']['outbox'][0]['state']='DELIVERED'
    d['sha256']=ep._sha({k:v for k,v in d.items() if k!='sha256'})
    with sqlite3.connect(e.path) as db:
        db.execute('DROP TRIGGER immutable_update');db.execute('UPDATE previews SET document=?',(prep.canonical(d),));db.execute("CREATE TRIGGER immutable_update BEFORE UPDATE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END")
    assert read(f,p).status_code==read(f,p,key).status_code==409 and snapshot(f)==before


def test_actual_source_change_keeps_old_history_stale_and_requires_explicit_new_attempt(receipt_preview_fixture):
    from test_isolated_execution_preview import add
    f,p,_,_,_,e,_=receipt_preview_fixture;key=uuid4().hex;old=execute(f,p,key=key).json()['result'];p=add(f,p,text='SYNTHETIC original new material version').json();before=snapshot(f);data=e.path.read_bytes()
    assert read(f,p,key).json()['result']==old and read(f,p).json()['history'][0]['source_state']=='STALE' and e.path.read_bytes()==data
    new=execute(f,p).json()['result'];assert new['binding']['source_sha256']!=old['binding']['source_sha256'] and new['artifact']['p1']['preparation_id']!=old['artifact']['p1']['preparation_id'] and snapshot(f)==before


def test_postcommit_lost_response_recovers_get_no_second_execution(receipt_preview_fixture,monkeypatch):
    from parkweave import isolated_execution_preview as ep
    f,p,_,_,_,e,_=receipt_preview_fixture;b=body(f,p);key=uuid4().hex;original=e.execute
    def lost(*args,**kw):original(*args,**kw);raise ep.Unavailable('SYNTHETIC committed response lost')
    before=snapshot(f);monkeypatch.setattr(e,'execute',lost);assert execute(f,p,b,key).status_code==503;monkeypatch.undo()
    data=e.path.read_bytes();r=read(f,p,key);assert r.json()['status']=='COMMITTED' and len(r.json()['history'])==1 and e.path.read_bytes()==data and snapshot(f)==before


def test_shadow_projection_failure_not_outer_commit_and_formal_uuid_default_off(receipt_preview_fixture,monkeypatch):
    from parkweave.isolated_run_access import ProjectionPending
    from parkweave.store import Store
    from fastapi.testclient import TestClient
    f,p,_,_,_,e,_=receipt_preview_fixture;b=body(f,p);before=snapshot(f);original=p4.IsolatedRunAccessBridge.command
    def fail(self,*args,**kw):original(self,*args,**kw);raise ProjectionPending()
    monkeypatch.setattr(p4.IsolatedRunAccessBridge,'command',fail);key=uuid4().hex;r=execute(f,p,b,key);assert r.status_code==503 and 'decision_committed' not in r.json() and read(f,p,key).json()['status']=='NOT_OBSERVED' and snapshot(f)==before
    monkeypatch.undo();d=execute(f,p,b).json()['result'];step=d['artifact']['p4_steps'][0];receipt=d['artifact']['p4_receipts'][0]
    assert f[3].get('/api/executor-receipts/'+step['id'],headers=headers(f[2])).status_code==403
    assert f[3].post('/api/executor-receipts/'+step['id']+'/commands',headers=headers(f[2],key=uuid4().hex),json={'action':'ACKNOWLEDGE','expected_revision':3,'receipt_sha256':receipt['source_sha256'],'reason':'SYNTHETIC formal consume denied'}).status_code==403
    with TestClient(create_app(Store(f[0].dsn))) as api:assert api.get('/api/preparations/'+p['preparation_id']+'/receipt-execution-preview',headers=headers(f[2])).status_code==403
    for extra in ({'text':'manual'},{'decision':'ACCEPT'},{'review_decision':'REOPEN'},{'role':'enterprise_operator'}):assert execute(f,p,{**b,**extra}).status_code==422
    assert snapshot(f)==before


def test_real_new_api_process_cannot_reconstruct_issued_proof_or_leak_saved_history(receipt_preview_fixture,tmp_path):
    import os,socket,subprocess,sys,time,json
    from pathlib import Path
    import httpx
    from parkweave.process_env import minimal_environment
    f,p,_,_,_,e,_=receipt_preview_fixture;key=uuid4().hex;assert execute(f,p,key=key).status_code==201;data=e.path.read_bytes();before=snapshot(f)
    factory=tmp_path/'p4_factory.py';factory.write_text('import os\nfrom parkweave.api import create_app\nfrom parkweave.store import Store\nfrom parkweave.receipt_execution_preview import ReceiptExecutionPreview\ndef app():\n s=Store(os.environ["PARKWEAVE_DSN"])\n ReceiptExecutionPreview(s,os.environ["PARKWEAVE_PREVIEW_ROOT"],enabled_for_synthetic_preview=True).attach_store(s)\n return create_app(s)\n')
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_PREVIEW_ROOT=str(e.root),PYTHONPATH=os.pathsep.join([str(tmp_path),str(Path.cwd()/'src')]))
    with (tmp_path/'owned-new-api.log').open('w') as log:
        process=subprocess.Popen([sys.executable,'-m','uvicorn','p4_factory:app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],env=env,stdout=log,stderr=log)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=2) as client:
                deadline=time.monotonic()+10;ready=False
                while process.poll() is None and time.monotonic()<deadline:
                    try:ready=client.get('/health').json()['process_id']==process.pid
                    except (httpx.HTTPError,ValueError,KeyError):pass
                    if ready:break
                    time.sleep(.03)
                assert ready and process.pid!=os.getpid()
                r=client.get('/api/preparations/'+p['preparation_id']+'/receipt-execution-preview/recovery/'+key,headers=headers(f[2]));assert r.status_code==403 and 'history' not in r.json() and 'result' not in r.json()
            assert e.path.read_bytes()==data and snapshot(f)==before
        finally:
            if process.poll() is None:process.terminate();process.wait(5)
    OUT.mkdir(parents=True,exist_ok=True)
    # Private safe note; public copy is selected after frozen and independent runs.
    (OUT/'new-process-proof-refusal.json').write_text(json.dumps(dict(actual_http=True,parent_pid=os.getpid(),owned_new_api_pid=process.pid,new_process_current_proof_absent=True,status=403,original_saved_bytes_unchanged=True,permissions_reissued=False,grant_or_assignment_repair=False,all_public_business_values_unchanged=True,owned_api_closed=True),indent=2)+'\n')


def test_outer_lease_expires_during_actual_execution_no_artifact_or_formal_write(receipt_preview_fixture,monkeypatch):
    from datetime import timedelta
    f,p,_,_,_,e,a=receipt_preview_fixture;b=body(f,p);key=uuid4().hex;before=snapshot(f);original=e._execute
    def expire(*args,**kw):
        result=original(*args,**kw);assert result['p4_state']=='LOCAL_ACKNOWLEDGED';a[3][0]+=timedelta(minutes=11);return result
    monkeypatch.setattr(e,'_execute',expire);assert execute(f,p,b,key).status_code==403 and snapshot(f)==before
    import sqlite3
    with sqlite3.connect(e.path) as db:assert db.execute('SELECT count(*) FROM previews').fetchone()[0]==0
