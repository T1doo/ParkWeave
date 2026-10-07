from parkweave.process_env import minimal_environment
"""Real HTTP API + independent CLI workers + PG; no test-only execution ledger."""
import json
import os
import socket
import subprocess
import sys
import time
import uuid
import httpx
import pytest
from parkweave.gateway import ExecutionGateway
from parkweave.store import Store,Conflict


@pytest.fixture
def runtime(fixture,tmp_path):
    store,owner,tokens,_=fixture
    with owner.connect() as c:
        c.execute('GRANT SELECT,INSERT,UPDATE ON fixture_effects TO parkweave_app')
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    env=minimal_environment(os.environ,PARKWEAVE_DSN=store.dsn,PARKWEAVE_MODE='FAULT_INJECTION')
    log=(tmp_path/'api.log').open('w+')
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory',
                           '--host','127.0.0.1','--port',str(port)],env=env,stdout=log,stderr=log)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=5) as api:
            for _ in range(100):
                try:
                    if api.get('/health').status_code==200:break
                except httpx.TransportError:pass
                if proc.poll() is not None:raise RuntimeError('API exited during start')
                time.sleep(.05)
            else:raise RuntimeError('API startup timeout')
            yield api,owner,tokens,env
    finally:
        proc.terminate();proc.wait(timeout=10);log.close()


def auth(tokens,user='fixture-a',key=None):
    return {'Authorization':'Bearer '+tokens[user],'Idempotency-Key':key or uuid.uuid4().hex}


def enqueue(runtime,action='fault.record'):
    api,owner,tokens,env=runtime
    r=api.post('/api/runs',headers=auth(tokens),json={'goal':'合成：正常执行网关恢复核对','action':action})
    assert r.status_code==202,r.text
    return r.json()['run_id']


def worker(runtime,*extra,expected=0):
    result=subprocess.run([sys.executable,'-m','parkweave.worker','--once','--lease-seconds','1',*extra],
                          env=runtime[3],capture_output=True,text=True,timeout=10)
    assert result.returncode==expected,(result.stdout,result.stderr)
    return result


def read(runtime,run):
    return runtime[0].get('/api/runs/'+run,headers=auth(runtime[2])).json()


def oracle(owner,run):
    with owner.connect() as c:
        return c.execute('SELECT r.state,r.control_intent,o.state operation_state,o.receipt,o.id operation_id,r.fence '
                         'FROM runs r JOIN operations o ON o.run_id=r.id WHERE r.id=%s',(run,)).fetchone()


def count_effect(owner):
    with owner.connect() as c:
        row=c.execute('SELECT count(*) n,coalesce(sum(dispatch_count),0) sends FROM fixture_effects').fetchone()
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==0
        return row


def test_real_api_worker_unknown_reconcile_outbox_and_no_duplicate(runtime):
    api,owner,tokens,env=runtime;run=enqueue(runtime)
    worker(runtime)
    r=read(runtime,run)
    assert r['state']=='RECONCILING' and r['operation']['state']=='OUTCOME_UNKNOWN'
    assert r['case'] is None and r['success_scope'] is None
    assert api.post('/api/runs/'+run+'/reconcile',headers=auth(tokens)).status_code==200
    worker(runtime)
    r=read(runtime,run)
    assert r['state']=='SUCCEEDED' and r['success_scope']=='FAULT_INJECTION_EFFECT_KNOWN'
    assert r['operation']['receipt']['source']=='FAULT_INJECTION'
    worker(runtime);assert count_effect(owner)=={'n':1,'sends':1}
    with owner.connect() as c:
        projection=c.execute('SELECT payload FROM run_projection WHERE run_id=%s',(run,)).fetchone()
        assert projection['payload']['state']=='SUCCEEDED'


@pytest.mark.parametrize('intent,terminal',[('cancel','CANCELLED'),('pause','PAUSED')])
def test_real_worker_crash_old_callback_control_and_effect_visibility(runtime,intent,terminal):
    api,owner,tokens,env=runtime;run=enqueue(runtime)
    worker(runtime,'--fault-stage','after-effect',expected=75)
    previous=oracle(owner,run);old={'id':uuid.UUID(run),'fence':previous['fence']}
    assert previous['operation_state']=='DISPATCHED' and count_effect(owner)['sends']==1
    assert api.post('/api/runs/'+run+'/'+intent,headers=auth(tokens)).status_code==200
    r=read(runtime,run);assert r['state']=='RECONCILING' and r['success_scope'] is None
    worker(runtime)
    r=read(runtime,run)
    assert r['state']==terminal and r['operation']['state']=='VERIFIED'
    assert r['control_intent']==intent.upper() and r['operation']['receipt']['effect']=='SIMULATED_RECORD'
    with pytest.raises(Conflict):
        ExecutionGateway(Store(env['PARKWEAVE_DSN'],mode='FAULT_INJECTION')).record(old,r['operation']['receipt'])
    assert api.post('/api/runs/'+run+'/resume',headers=auth(tokens)).status_code==409
    assert count_effect(owner)=={'n':1,'sends':1}


def test_actual_expiry_recovery_after_crash_does_not_dispatch_again(runtime):
    api,owner,tokens,env=runtime;run=enqueue(runtime)
    worker(runtime,'--fault-stage','after-effect',expected=75)
    old=oracle(owner,run)['fence']
    time.sleep(1.1)  # real DB clock expiry, no manual database state mutation
    worker(runtime)
    r=read(runtime,run);assert r['state']=='SUCCEEDED'
    assert oracle(owner,run)['fence']>old and count_effect(owner)['sends']==1


def test_crash_without_observed_effect_stays_unknown_and_stops_automatic_queries(runtime):
    api,owner,tokens,env=runtime;run=enqueue(runtime)
    worker(runtime,'--fault-stage','after-dispatch',expected=75)
    # Control while pending dispatch both fences old worker and requests a query.
    assert api.post('/api/runs/'+run+'/cancel',headers=auth(tokens)).status_code==200
    for _ in range(3):
        worker(runtime);time.sleep(1.05)
    before=oracle(owner,run)['fence'];worker(runtime)
    assert oracle(owner,run)['fence']==before  # exhausted three bounded observations
    r=read(runtime,run)
    assert r['state']=='RECONCILING' and r['operation']['state']=='OUTCOME_UNKNOWN'
    assert r['control_intent']=='CANCEL' and count_effect(owner)=={'n':0,'sends':0}
    assert api.post('/api/runs/'+run+'/reconcile',headers=auth(tokens)).status_code==200
    worker(runtime)
    assert oracle(owner,run)['fence']>before and read(runtime,run)['state']=='RECONCILING'
    assert count_effect(owner)['sends']==0


@pytest.mark.parametrize('stage',[None,'after-effect'])
def test_real_worker_revocation_before_dispatch_and_after_effect(runtime,stage):
    api,owner,tokens,env=runtime;run=enqueue(runtime)
    if stage:worker(runtime,'--fault-stage',stage,expected=75)
    result=subprocess.run([sys.executable,'-m','parkweave.cli','revoke','--principal','fixture-a'],
                          env=dict(env,PARKWEAVE_DSN=owner.dsn),capture_output=True,timeout=10)
    assert result.returncode==0
    if stage:time.sleep(1.1)
    worker(runtime)
    row=oracle(owner,run)
    assert row['operation_state']==('VERIFIED' if stage else 'FAILED_SAFE')
    assert count_effect(owner)['sends']==(1 if stage else 0)
    assert api.get('/api/runs/'+run,headers=auth(tokens)).status_code==403
    assert api.post('/api/runs/'+run+'/reconcile',headers=auth(tokens)).status_code==403
    assert api.post('/api/runs',headers=auth(tokens),json={'goal':'x','action':'fault.record'}).status_code==403


@pytest.mark.parametrize('user',['fixture-b','fixture-c'])
def test_real_gateway_scope_read_cancel_and_manual_reconcile(runtime,user):
    api,owner,tokens,env=runtime;run=enqueue(runtime);worker(runtime)
    for path in [run,run+'/cancel',run+'/reconcile']:
        r=api.get('/api/runs/'+path,headers=auth(tokens,user)) if '/' not in path else api.post('/api/runs/'+path,headers=auth(tokens,user))
        assert r.status_code==403
    assert read(runtime,run)['state']=='RECONCILING' and count_effect(owner)['sends']==1


def test_local_and_fixture_use_same_worker_gateway(runtime):
    run=enqueue(runtime,'case.create');worker(runtime)
    r=read(runtime,run)
    assert r['state']=='SUCCEEDED' and r['case']['state']=='NEEDS_INPUT'
    assert r['success_scope']=='LOCAL_CASE_CREATED'


def test_current_migration_is_idempotent_preserves_existing_records(fixture):
    store,owner,tokens,client=fixture
    r=client.post('/api/runs',headers=auth(tokens),json={'goal':'合成迁移保留'});run=r.json()['run_id']
    store.finish(store.claim('fixture'))
    before=store.read(tokens['fixture-a'],run)
    owner.migrate();owner.migrate()
    assert store.read(tokens['fixture-a'],run)==before
    assert client.get('/health').json()['schema']==21


def test_invalid_receipt_rejected_by_actual_worker_gateway(runtime):
    from psycopg.types.json import Jsonb
    api,owner,tokens,env=runtime;run=enqueue(runtime)
    worker(runtime,'--fault-stage','after-effect',expected=75)
    with owner.connect() as c:
        row=c.execute('SELECT receipt FROM fixture_effects').fetchone()['receipt']
        row['org_id']='org-b'
        c.execute('UPDATE fixture_effects SET receipt=%s',(Jsonb(row),))  # corrupt simulated remote data, not Run state
    assert api.post('/api/runs/'+run+'/reconcile',headers=auth(tokens)).status_code==200
    worker(runtime)
    r=read(runtime,run)
    assert r['state']=='FAILED' and r['operation']['state']=='EFFECT_KNOWN_INVALID'
    assert r['success_scope'] is None and count_effect(owner)['sends']==1


def test_upgrade_legacy_database_preserves_business_history(pg):
    from pathlib import Path
    import psycopg
    from psycopg.conninfo import make_conninfo
    from psycopg.types.json import Jsonb
    db='upgrade_'+uuid.uuid4().hex
    with psycopg.connect(pg.get_uri(),autocommit=True) as c:
        c.execute(psycopg.sql.SQL('CREATE DATABASE {}').format(psycopg.sql.Identifier(db)))
    owner=Store(make_conninfo(pg.get_uri(),dbname=db));run,op,case=uuid.uuid4(),uuid.uuid4(),uuid.uuid4()
    receipt={'case_id':str(case),'source':'LOCAL_DATABASE','verified':True,'success_scope':'LOCAL_CASE_CREATED'}
    try:
        with owner.connect() as c:
            c.execute(Path('src/parkweave/schema.sql').read_text())  # exact legacy migration001
        owner.seed({'fixture-a':'synthetic-upgrade-fixture-only'})
        with owner.connect() as c:
            c.execute("INSERT INTO runs(id,principal_id,park_id,org_id,namespace,request_key,fingerprint,input,state,success_scope) "
                      "VALUES(%s,'fixture-a','park-a','org-a','SYNTHETIC','legacy','legacy',%s,'SUCCEEDED','LOCAL_CASE_CREATED')",
                      (run,Jsonb({'goal':'合成：历史记录'})))
            c.execute("INSERT INTO operations VALUES(%s,%s,'case.create','VERIFIED',%s)",(op,run,Jsonb(receipt)))
            c.execute("INSERT INTO cases VALUES(%s,%s,'park-a','org-a','合成：历史记录','NEEDS_INPUT','SYNTHETIC','NOT_SUBMITTED','NO_EVIDENCE')",(case,run))
        owner.migrate();owner.migrate()
        with owner.connect() as c:
            assert c.execute('SELECT max(version) version FROM schema_version').fetchone()['version']==21
            assert c.execute('SELECT id,state,receipt FROM operations').fetchone()=={'id':op,'state':'VERIFIED','receipt':receipt}
            assert c.execute('SELECT id,state FROM cases').fetchone()=={'id':case,'state':'NEEDS_INPUT'}
            assert c.execute('SELECT state,control_intent FROM runs').fetchone()=={'state':'SUCCEEDED','control_intent':'CONTINUE'}
            c.execute('INSERT INTO schema_version VALUES(22)')
        with pytest.raises(Conflict):owner.migrate()
        with owner.connect() as c:assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==1
    finally:
        with psycopg.connect(pg.get_uri(),autocommit=True) as c:
            c.execute(psycopg.sql.SQL('DROP DATABASE {}').format(psycopg.sql.Identifier(db)))


def test_default_worker_cannot_dispatch_explicit_fixture_action(runtime):
    api,owner,tokens,env=runtime;run=enqueue(runtime)
    result=subprocess.run([sys.executable,'-m','parkweave.worker','--once'],
                          env=dict(env,PARKWEAVE_MODE='LOCAL'),capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(result.stdout,result.stderr)
    assert read(runtime,run)['state']=='QUEUED' and count_effect(owner)=={'n':0,'sends':0}
    worker(runtime)
    assert read(runtime,run)['operation']['state']=='OUTCOME_UNKNOWN' and count_effect(owner)['sends']==1
