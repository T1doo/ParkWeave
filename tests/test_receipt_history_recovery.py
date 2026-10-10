"""Three actual owned PIDs: original issuer, exited old API, fresh GET-only API."""
from contextlib import contextmanager
from datetime import timedelta
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

import httpx
import pytest
from parkweave.process_env import minimal_environment
from parkweave import receipt_history_recovery as history, isolated_execution_preview as ep
from parkweave.store import Store
from test_isolated_execution_preview import snapshot

OUT = Path('.runtime/p4-history-api-recovery/api')
ROOT = Path.cwd()
ISSUER = '''
import json,os,time,hashlib,signal
from pathlib import Path
from datetime import timedelta
from conftest import pg,fixture
from test_receipt_execution_preview import receipt_preview_fixture,access_fixture,receipt_fixture,preparation_fixture,snapshot,body
from test_new_enterprise_local_chain import actual_http
from test_preparation import headers
from parkweave.api import create_app
from parkweave import receipt_history_recovery as history,isolated_execution_preview as ep
BASE=Path(os.environ['PARKWEAVE_HISTORY_TEST_DIR'])
def private(name,data):
 p=BASE/name;p.write_text(json.dumps(data));p.chmod(0o600)
def schema(f):
 with f[1].connect() as c:return ep._normal({n:c.execute(q).fetchall() for n,q in dict(columns="SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",indexes="SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",grants="SELECT grantee,table_name,privilege_type FROM information_schema.table_privileges WHERE table_schema='public' ORDER BY grantee,table_name,privilege_type").items()})
def test_owned_issuer(receipt_preview_fixture):
 f,p,p1,p2,p3,e,a=receipt_preview_fixture
 key='history-'+os.environ['PARKWEAVE_HISTORY_DECISION']
 before=snapshot(f);columns=schema(f)
 with actual_http(create_app(f[0])) as (client,requests):
  r=client.post('/api/preparations/'+p['preparation_id']+'/receipt-execution-preview',headers=headers(f[2],key=key),json=body(f,p,os.environ['PARKWEAVE_HISTORY_DECISION']))
  assert r.status_code==201,r.text
  original=r.json()['result']
 assert snapshot(f)==before and schema(f)==columns
 with history.ReceiptHistoryAuthority(f[0],e,BASE/'history.sock',enabled_for_isolated_tests=True) as authority:
  private('ready.json',dict(issuer_pid=os.getpid(),generation=authority.generation,namespace=e.namespace,app_dsn=f[0].dsn,owner_dsn=f[1].dsn,tokens=f[2],preparation=p,key=key,result=original,source_business=ep._normal(before),schema=columns,paths=[str(x.path) for x in (p1,p2,p3,e)]+[str(a[2].repository.path)],original_commit_actual_http=True))
  deadline=time.monotonic()+110;seen=None
  while not (BASE/'stop').exists() and time.monotonic()<deadline:
   control=BASE/'control.json'
   if control.exists():
    command=json.loads(control.read_text())
    if command['id']!=seen:
     if command['gate']=='lease':a[3][0]+=timedelta(minutes=11)
     elif command['gate']=='provider':f[0]._isolated_local_execution=None
     elif command['gate']=='proof':a[2].proof=None
     elif command['gate']=='other_key_response':
      original_reply=authority._reply
      authority._reply=lambda request:original_reply({**request,'key':key})
     else:raise ValueError('closed observer control')
     seen=command['id'];private('control-ack.json',dict(id=seen))
   time.sleep(.02)
  assert (BASE/'stop').exists(),'owned issuer control timed out'
 private('closed.json',dict(issuer_pid=os.getpid(),authority_closed=True,formal_business=ep._normal(snapshot(f)),schema=schema(f)))
'''
FACTORY = '''
import os,json
from pathlib import Path
from parkweave.api import create_app
from parkweave.store import Store
from parkweave import receipt_history_recovery as h,case_fact_clarifications as facts
 def_placeholder
'''.replace(' def_placeholder', '''def app():
 s=Store(os.environ['PARKWEAVE_DSN'])
 assert not facts._fixture_databases and not facts._fixture_clusters
 assert getattr(s,'_isolated_run_access',None) is None
 h.ReceiptHistoryClient(s,os.environ['PARKWEAVE_HISTORY_SOCKET'],authority_pid=int(os.environ['PARKWEAVE_HISTORY_PID']),authority_generation=os.environ['PARKWEAVE_HISTORY_GENERATION'],namespace=os.environ['PARKWEAVE_HISTORY_NAMESPACE'],enabled_for_isolated_tests=True).attach_store(s)
 app=create_app(s)
 @app.middleware('http')
 async def count(request,call_next):
  p=Path(os.environ['PARKWEAVE_HISTORY_NETWORK'])
  with p.open('a') as out:out.write(request.method+' '+request.url.path+'\\n')
  return await call_next(request)
 return app
''')

def wait_for(check, process=None, seconds=15):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if check():return
        if process is not None and process.poll() is not None:break
        time.sleep(.03)
    raise AssertionError('owned process readiness not confirmed; private log preserved')

@pytest.fixture
def issuer(request):
    with tempfile.TemporaryDirectory(prefix='pw-p4-history-') as temp:
        base=Path(temp);(base/'issuer_test.py').write_text(ISSUER);(base/'history_factory.py').write_text(FACTORY)
        decision=getattr(request,'param','ACKNOWLEDGE');case=OUT/(request.node.name.replace('/','_'));case.mkdir(parents=True,exist_ok=True)
        env=minimal_environment(os.environ,PYTHONPATH=os.pathsep.join([str(ROOT/'src'),str(ROOT/'tests'),str(ROOT)]),PARKWEAVE_HISTORY_TEST_DIR=str(base),PARKWEAVE_HISTORY_DECISION=decision)
        basetemp=tempfile.mkdtemp(prefix='pw-service-plan-recovery-')
        with (case/'owned-issuer-private.log').open('w') as log:
            child=subprocess.Popen([sys.executable,'-m','pytest',str(base/'issuer_test.py'),'-q','--basetemp='+basetemp,'--junitxml='+str(case/'owned-issuer-junit.xml')],env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            try:
                wait_for(lambda:(base/'ready.json').exists(),child,30);data=json.loads((base/'ready.json').read_text());assert data['issuer_pid']==child.pid!=os.getpid()
                yield base,data,child,case
            finally:
                (base/'stop').touch()
                try:child.wait(15)
                except subprocess.TimeoutExpired:child.terminate();child.wait(5)
                assert child.returncode==0,'owned issuer fault preserved'
                assert not Path('/proc',str(child.pid)).exists()
                # Root fixture PG finalizer closes its actually owned temporary cluster.
                for p in case.rglob('*'):
                    if p.is_file():p.chmod(0o600)

@contextmanager
def api_process(issuer,port=None):
    base,data,child,case=issuer
    if port is None:
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    network=base/('network-'+uuid4().hex+'.txt');network.touch(mode=0o600)
    env=minimal_environment(os.environ,PYTHONPATH=os.pathsep.join([str(ROOT/'src'),str(base)]),PARKWEAVE_DSN=data['app_dsn'],PARKWEAVE_HISTORY_SOCKET=str(base/'history.sock'),PARKWEAVE_HISTORY_PID=str(child.pid),PARKWEAVE_HISTORY_GENERATION=data['generation'],PARKWEAVE_HISTORY_NAMESPACE=data['namespace'],PARKWEAVE_HISTORY_NETWORK=str(network))
    with (case/('owned-api-'+str(port)+'-'+uuid4().hex+'.log')).open('w') as log:
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','history_factory:app','--factory','--host','127.0.0.1','--port',str(port),'--no-access-log','--log-level','warning'],env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        client=httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=8)
        def ready():
            try:r=client.get('/health');return r.status_code==200 and r.json()['process_id']==proc.pid
            except httpx.HTTPError:return False
        try:
            wait_for(ready,proc);assert proc.pid not in (os.getpid(),child.pid)
            yield client,proc,port,network
        finally:
            client.close();proc.terminate()
            try:proc.wait(10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(5)
            assert not Path('/proc',str(proc.pid)).exists()


def get(client,data,key=None,user='fixture-a'):
    path='/api/preparations/'+data['preparation']['preparation_id']+'/receipt-execution-history'
    if key is not None:path+='/recovery/'+key
    return client.get(path,headers={'Authorization':'Bearer '+data['tokens'][user]})

def business(data):return ep._normal(snapshot((None,Store(data['owner_dsn']))))
def bytes_all(data):return [Path(p).read_bytes() for p in data['paths']]
def note(case,name,data):(case/(name+'-safe.json')).write_text(json.dumps(data,indent=2)+'\n')

def schema(data):
    with Store(data['owner_dsn']).connect() as c:
        return ep._normal({n:c.execute(q).fetchall() for n,q in dict(columns="SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",indexes="SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",grants="SELECT grantee,table_name,privilege_type FROM information_schema.table_privileges WHERE table_schema='public' ORDER BY grantee,table_name,privilege_type").items()})


def test_actual_http_rejects_another_legitimate_original_key_reply(issuer):
    base,d,authority,case=issuer;before=business(d);saved=bytes_all(d)
    id=uuid4().hex;(base/'control.json').write_text(json.dumps(dict(id=id,gate='other_key_response')))
    wait_for(lambda:(base/'control-ack.json').exists() and json.loads((base/'control-ack.json').read_text())['id']==id,authority)
    with api_process(issuer) as (client,api,_,network):
        assert get(client,d,d['key']).json()['result']==d['result']
        response=get(client,d,'never-sent')
        assert response.status_code==503 and 'result' not in response.json() and 'history' not in response.json()
        assert {line.split()[0] for line in network.read_text().splitlines()}=={'GET'}
    assert bytes_all(d)==saved and business(d)==before
    note(case,'wrong-key-response',dict(actual_http=True,original_authority_legitimate_other_key_reply=True,report_hash_or_proof_fabrication=False,unknown_key_status=503,no_result_leak=True,five_logs_and_business_unchanged=True))

@pytest.mark.parametrize('issuer',['ACKNOWLEDGE','REQUEST_CHANGES'],indirect=True)
def test_actual_old_api_exits_new_pid_reads_exact_history_no_proof_transfer(issuer):
    base,d,authority,case=issuer;before=bytes_all(d);assert business(d)==d['source_business'] and schema(d)==d['schema']
    with api_process(issuer) as (client,old,port,net):
        original=get(client,d,d['key']);assert original.status_code==200 and original.json()['result']==d['result'];old_pid=old.pid
    assert old.poll() is not None and not Path('/proc',str(old_pid)).exists() and authority.poll() is None
    with api_process(issuer,port) as (client,new,_,net):
        assert new.pid!=old_pid
        for _ in range(3):
            r=get(client,d,d['key']);assert r.status_code==200 and r.json()['result']==d['result'] and r.json()['read_only'] is True and r.json()['automatically_replayed'] is False
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(4) as pool:
            responses=list(pool.map(lambda _:get(client,d,d['key']),range(4)))
        assert all(r.status_code==200 and r.json()['result']==d['result'] for r in responses)
        unknown=get(client,d,'never-sent');assert unknown.status_code==200 and unknown.json()['status']=='NOT_OBSERVED'
        assert {line.split()[0] for line in net.read_text().splitlines()}=={'GET'}
    assert bytes_all(d)==before and business(d)==d['source_business'] and schema(d)==d['schema']
    note(case,'cross-api-pid',dict(issuer_pid=authority.pid,old_api_pid=old_pid,new_api_pid=new.pid,old_confirmed_exited_before_new=True,issuer_continuously_alive=True,new_api_proof_registries_empty=True,original_commit_actual_http=True,exact_result_preserved=True,repeated_get=3,concurrent_get=4,unknown_key='NOT_OBSERVED',automatically_replayed=False,all_five_logs_bytes_unchanged=True,formal_business_schema_and_privileges_unchanged=True,scope='API client replacement only; original issuer restart NOT_ACCEPTED'))

@pytest.mark.parametrize('gate',['owner_read','owner_execute','specialist','executor','assignment','hold','lease','provider','proof'])
def test_current_original_qualification_denies_new_api_history(issuer,gate):
    base,d,authority,case=issuer
    with api_process(issuer) as (client,old,port,_):assert get(client,d,d['key']).status_code==200
    assert old.poll() is not None
    if gate in ('lease','provider','proof'):
        id=uuid4().hex;p=base/'control.json';p.write_text(json.dumps(dict(id=id,gate=gate)));p.chmod(0o600)
        wait_for(lambda:(base/'control-ack.json').exists() and json.loads((base/'control-ack.json').read_text())['id']==id,authority)
    else:
        with Store(d['owner_dsn']).connect() as c:
            if gate.startswith('owner_'):c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a','READ' if gate=='owner_read' else 'EXECUTE'))
            elif gate=='specialist':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
            elif gate=='executor':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
            elif gate=='assignment':c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
            else:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    before=business(d);saved=bytes_all(d)
    with api_process(issuer,port) as (client,new,_,_):
        for _ in range(2):
            r=get(client,d,d['key']);assert r.status_code==403 and 'history' not in r.json() and 'result' not in r.json()
    assert business(d)==before and bytes_all(d)==saved
    note(case,'qualification-'+gate,dict(actual_new_api_pid=new.pid,old_api_pid=old.pid,gate=gate,status=403,history_not_leaked=True,all_logs_unchanged=True,formal_business_unchanged=True,proof_or_grants_reissued=False))

@pytest.mark.parametrize('user',['fixture-b','fixture-c','executor-a','prep-specialist-fixture-a'])
def test_history_wrong_actor_cross_tenant_and_existing_write_gates(issuer,user):
    _,d,_,case=issuer;saved=bytes_all(d);before=business(d)
    with api_process(issuer) as (client,_,_,_):
        assert get(client,d,d['key'],user).status_code==403
        path='/api/preparations/'+d['preparation']['preparation_id']
        auth={'Authorization':'Bearer '+d['tokens']['fixture-a'],'Idempotency-Key':'no-replay'}
        assert client.post(path+'/receipt-execution-history',headers=auth,json={}).status_code==405
        assert client.get(path+'/receipt-execution-preview/recovery/'+d['key'],headers=auth).status_code==403
        assert client.post(path+'/receipt-execution-preview',headers=auth,json={'expected_preparation_revision':1,'expected_request_revision':1,'expected_source_sha256':'0'*64}).status_code==403
    assert business(d)==before and bytes_all(d)==saved


def test_material_version_changed_old_history_remains_exact_stale(issuer):
    _,d,_,case=issuer
    from parkweave import preparation as prep
    f=Store(d['app_dsn'])
    p=d['preparation'];prep.command(f,d['tokens']['fixture-a'],p['preparation_id'],uuid4().hex,prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=p['revision'],slot='need_summary',text='SYNTHETIC newer original material',source_kind='USER_STATEMENT',source_label='SYNTHETIC version2'))
    saved=bytes_all(d);before=business(d)
    with api_process(issuer) as (client,_,_,_):
        r=get(client,d,d['key']);assert r.status_code==200 and r.json()['result']==d['result'] and r.json()['history'][0]['source_state']=='STALE'
    assert business(d)==before and bytes_all(d)==saved


def test_issuer_pid_exits_new_api_does_not_reissue_or_replay(issuer):
    base,d,authority,case=issuer;saved=bytes_all(d)
    with api_process(issuer) as (client,_,_,_):
        assert get(client,d,d['key']).status_code==200
        (base/'stop').touch();authority.wait(15);assert authority.returncode==0 and not Path('/proc',str(authority.pid)).exists()
        r=get(client,d,d['key']);assert r.status_code==503 and 'history' not in r.json()
        assert bytes_all(d)==saved
    closed=json.loads((base/'closed.json').read_text());assert closed['formal_business']==d['source_business'] and closed['schema']==d['schema']
    note(case,'issuer-exit',dict(actual_issuer_pid=authority.pid,issuer_confirmed_gone=True,current_api_get=503,no_restart_or_proof_reissue=True,all_logs_unchanged=True,formal_business_before_teardown_unchanged=True))


def test_poisoned_body_is_not_repaired_or_returned_by_fresh_api(issuer):
    import sqlite3
    from parkweave import preparation as prep
    _,d,_,case=issuer;path=Path(d['paths'][3]);before=business(d)
    with sqlite3.connect(path) as db:
        raw=db.execute('SELECT document FROM previews').fetchone()[0];doc=json.loads(raw)
        doc['artifact']['p4_receipts'][0]['adapter_execution']['report']['execution_id']=str(uuid4())
        doc['sha256']=ep._sha({k:v for k,v in doc.items() if k!='sha256'})
        db.execute('DROP TRIGGER immutable_update');db.execute('UPDATE previews SET document=?',(prep.canonical(doc),));db.execute("CREATE TRIGGER immutable_update BEFORE UPDATE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END")
    saved=bytes_all(d)
    with api_process(issuer) as (client,_,_,_):
        r=get(client,d,d['key']);assert r.status_code==409 and 'result' not in r.json() and 'history' not in r.json()
    assert bytes_all(d)==saved and business(d)==before
    note(case,'poisoned-body',dict(actual_fresh_api=True,single_body_rehashed=True,status=409,poisoned_bytes_preserved_without_repair=True,formal_business_unchanged=True))


def test_closed_socket_protocol_and_client_identity_do_not_create_authority(issuer):
    _,d,authority,case=issuer;before=business(d);saved=bytes_all(d)
    base=issuer[0];store=Store(d['app_dsn']);client=history.ReceiptHistoryClient(store,base/'history.sock',authority_pid=authority.pid,authority_generation=d['generation'],namespace=d['namespace'],enabled_for_isolated_tests=True);client.attach_store(store)
    from parkweave.store import Denied
    with pytest.raises(Denied):history.ReceiptHistoryClient(store,base/'history.sock',authority_pid=authority.pid,authority_generation='0',namespace=d['namespace'],enabled_for_isolated_tests=True)
    with pytest.raises(Denied):history.ReceiptHistoryClient(store,base/'history.sock',authority_pid=authority.pid,authority_generation=d['generation'],namespace=d['namespace'])
    request=dict(version=1,operation='SUBMIT',preparation=d['preparation']['preparation_id'],key=d['key'],token=d['tokens']['fixture-a'],binding=client.binding)
    for op in ('SUBMIT','ACKNOWLEDGE','APPROVE','EXECUTE','READ'):
        request['operation']=op
        payload={**request,'text':'SYNTHETIC forbidden manual input'} if op=='READ' else request
        with socket.socket(socket.AF_UNIX) as conn:
            conn.settimeout(3);conn.connect(str(base/'history.sock'));history._send(conn,payload,history.REQUEST_LIMIT);assert history._receive(conn,history.RESPONSE_LIMIT)=={'status':403}
    with socket.socket(socket.AF_UNIX) as conn:
        import struct
        conn.settimeout(3);conn.connect(str(base/'history.sock'));conn.sendall(struct.pack('!I',history.REQUEST_LIMIT+1));assert history._receive(conn,history.RESPONSE_LIMIT)=={'status':403}
    (base/'history.sock').chmod(0o666)
    try:
        with pytest.raises(Denied):client.read(store,d['tokens']['fixture-a'],d['preparation']['preparation_id'],d['key'])
    finally:(base/'history.sock').chmod(0o600)
    client.binding['namespace']=str(uuid4())
    with pytest.raises(Denied):client.read(store,d['tokens']['fixture-a'],d['preparation']['preparation_id'],d['key'])
    assert bytes_all(d)==saved and business(d)==before
    note(case,'closed-transport',dict(non_read_operations=4,extra_read_fields_and_oversized_frame=403,wrong_process_generation_rejected=True,default_disabled=True,unsafe_socket_rejected=True,wrong_namespace_rejected=True,formal_business_and_log_bytes_unchanged=True))
