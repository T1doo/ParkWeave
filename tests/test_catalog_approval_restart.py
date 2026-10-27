"""Real new configured API PIDs and own ephemeral PG restart, consumed proof only."""
import json,os,socket,subprocess,sys,tempfile,threading,time
from pathlib import Path
from uuid import uuid4
from contextlib import contextmanager
import pytest,psycopg,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from parkweave.process_env import minimal_environment
from parkweave import case_fact_clarifications as facts
from parkweave.store import Denied
from test_catalog_approval_coordination import setup
from test_service_plan_approval import link_fixture,receipt_fixture,preparation_fixture,ledger
from test_case_resource_delivery import effects
from test_case_resource_delivery_browser import lose,settled
from test_service_case_steps import verified
from test_resource_bundles_browser import open_resources,choose
from test_preparation import headers
OUT=Path('.runtime/catalog-approval-coordination/restart')

@pytest.fixture
def own_case(tmp_path):
    import pgserver
    import conftest
    data=Path(tempfile.mkdtemp(prefix='pw-catalog-approval-restart-'))/'data'
    pg=pgserver.get_server(data,cleanup_mode='stop')
    pg._case_fact_fixture_cluster=facts.capture_fixture_cluster(pg.get_uri(),data.resolve())
    with psycopg.connect(pg.get_uri(),autocommit=True) as c:c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
    generator=conftest.fixture.__wrapped__(pg,None)
    try:
        f=next(generator);f=preparation_fixture.__wrapped__(f);f=receipt_fixture.__wrapped__(f);f=link_fixture.__wrapped__(f)
        yield f,pg
    finally:
        generator.close();pg.cleanup()
        assert not (data/'postmaster.pid').exists()

@contextmanager
def actual_page_server(f,port):
    listener=socket.socket();listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);listener.bind(('127.0.0.1',port))
    server=uvicorn.Server(uvicorn.Config(create_app(f[0]),host='127.0.0.1',port=port,log_level='warning',access_log=False))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    try:
        end=time.monotonic()+10
        while not server.started and thread.is_alive() and time.monotonic()<end:time.sleep(.02)
        assert server.started;yield
    finally:
        server.should_exit=True;thread.join(10);listener.close();assert not thread.is_alive()


def start_api(f,page,port,log):
    env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PYTHONPATH=str(Path.cwd()/'src'),PYTHONDONTWRITEBYTECODE='1')
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],env=env,stdout=log,stderr=log)
    end=time.monotonic()+10
    while proc.poll() is None and time.monotonic()<end:
        try:
            r=page.request.get(f'http://127.0.0.1:{port}/health',timeout=500)
            if r.ok and r.json()['process_id']==proc.pid:return proc
        except Exception:pass
        time.sleep(.02)
    if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
    raise AssertionError('owned new API readiness failed')


def identity(f):
    with f[1].connect() as c:return facts._migration_identity(c)


@pytest.mark.parametrize('restart_pg',[False,True])
def test_consumed_approval_survives_real_new_api_pids_and_pg_restart_get_only(own_case,restart_pg):
    f,pg=own_case;p,hs,data,bridge,protocol=setup(f)
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    OUT.mkdir(parents=True,exist_ok=True);base=f'http://127.0.0.1:{port}';active=None;pids=[];old_pg_pid=pg.get_pid();before_identity=identity(f)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page()
        try:
            with actual_page_server(f,port):
                page.goto(base);open_resources(page,f);choose(page,hs);page.locator('#delivery-case').fill(p['preparation_id']);page.locator('#delivery-preview').click();page.wait_for_function('()=>deliveryQuote!==null')
                page.locator('#plan-approval-propose').click();page.wait_for_function('()=>!planApprovalBusy&&planApprovalSelected?.state==="PROPOSED"')
                page.locator('#plan-approval-approve').click();page.wait_for_function('()=>!planApprovalBusy&&planApprovalSelected?.current_available')
                page.route('**/api/preparations/'+p['preparation_id']+'/resource-delivery',lose)
                page.locator('#delivery-confirm').click();settled(page);assert effects(f)==[1,3,1,1,1]
                saved=page.evaluate('deliveryHandles()[0]');assert saved and page.evaluate('planApprovalHandles().length')==0
                verified(f,p,'P2')
            original=ledger(f,p);assert original['events'][-1]['action']=='CONSUME'
            endpoint=base+'/api/preparations/'+p['preparation_id']+'/resource-delivery/recovery/'+saved['key']
            with (OUT/('owned-api-'+str(restart_pg)+'-'+uuid4().hex+'.log')).open('w') as log:
                try:
                    active=start_api(f,page,port,log);pids.append(active.pid)
                    r=page.request.get(endpoint,headers=headers(f[2]));assert r.status==200,r.text();receipt=r.json()['receipt'];assert receipt['plan_approval']['consumption_event_id']==original['events'][-1]['id']
                    active.terminate();active.wait(timeout=5);active=None
                    if restart_pg:
                        from pgserver._commands import pg_ctl
                        pg_ctl(['-w','-m','fast','stop'],pgdata=pg.pgdata,user=pg.system_user,timeout=10,env=minimal_environment(os.environ))
                        assert not (pg.pgdata/'postmaster.pid').exists()
                        pg.ensure_postgres_running()
                    after_identity=identity(f)
                    assert all(before_identity[k]==after_identity[k] for k in ('system_identifier','database_oid','database_name','data_directory','owner_name'))
                    if restart_pg:
                        assert pg.get_pid()!=old_pg_pid and after_identity['postmaster_start']!=before_identity['postmaster_start']
                        with pytest.raises(Denied):bridge.read(f[0],f[2]['fixture-a'],__import__('uuid').UUID(p['preparation_id']))
                    assert ledger(f,p)==original and effects(f)==[1,3,1,1,1]
                    active=start_api(f,page,port,log);pids.append(active.pid);assert pids[0]!=pids[1]
                    requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_resources(page,f)
                    page.locator('#delivery-recover').click();settled(page);page.wait_for_function('()=>deliveryHandles().length===0')
                    assert requests and set(requests)=={'GET'}
                    r=page.request.get(endpoint,headers=headers(f[2]));assert r.status==200 and r.json()['receipt']==receipt
                    for suffix in ('service-case-plan','goal-results'):
                        r=page.request.get(base+'/api/preparations/'+p['preparation_id']+'/'+suffix,headers=headers(f[2]));assert r.status==200,r.text()
                    r=page.request.get(base+'/api/preparations/'+p['preparation_id']+'/plan-approval',headers=headers(f[2]));assert r.status==403
                    assert not page.request.get(base+'/api/plan-approval/status',headers=headers(f[2])).json()['enabled']
                    with f[1].connect() as c:c.execute("UPDATE synthetic_resource_combination_receipts SET payload=payload-'plan_approval' WHERE request_key=%s",(saved['key'],))
                    assert page.request.get(endpoint,headers=headers(f[2])).status==409
                    assert ledger(f,p)==original and effects(f)==[1,3,1,1,1]
                    record={'api_pids':pids,'different_api_pids':True,'old_pg_pid':old_pg_pid,'new_pg_pid':pg.get_pid(),'pg_restarted':restart_pg,'pg_start_changed':before_identity['postmaster_start']!=after_identity['postmaster_start'],'system_identifier_unchanged':True,'database_oid_unchanged':True,'ledger_head_receipt_association_retained_before_negative':True,'cold_browser_recovery_get_only':True,'consumed_proof_read_without_reissuing_fixture_capability':True,'new_approval_write_enabled':False,'old_fixture_capability_after_pg_restart':'DENIED' if restart_pg else 'NOT_RESTARTED','tampered_consumption_receipt_refused':True,'effects':[1,3,1,1,1]}
                    (OUT/('restart-'+str(restart_pg)+'.json')).write_text(json.dumps(record,indent=2)+'\n')
                finally:
                    if active is not None and active.poll() is None:active.terminate();active.wait(timeout=5)
        finally:context.close();browser.close()
