"""Independent literal projection, original page and actual owned PG restart."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import json,os,socket,subprocess,sys,tempfile,time
import pytest,psycopg
from playwright.sync_api import sync_playwright
from conftest import fixture,pg
from test_negative_journal import preparation_fixture,receipt_fixture,link_fixture,real_f,clone_existing_resource
from test_service_case_steps import setup,GOALS,adopt,read,command,business,step,verified
from test_case_goal_results import complete,snapshot,get
from test_service_plan_manual_lock import stored,lock
from test_service_plan_recovery import recover
from test_service_plan_recovery_browser import goal_page,open_case,lost,wait_recovered
from test_preparation import headers
from test_new_enterprise_local_chain import actual_http
from parkweave.api import create_app
from parkweave import case_fact_clarifications as facts
from parkweave.process_env import minimal_environment
from test_registered_local_revision import patch_body
OUT=Path('/workspace/ParkWeave/.runtime/independent-registered-local-revision-projection-final-review/independent-evidence')
SHA='d12afaa6258dd89a539e3a859b965ca9441e2111'

def write(name,data):
    OUT.mkdir(parents=True,exist_ok=True);(OUT/(name+'.json')).write_text(json.dumps(dict(exact_sha=SHA,model_calls=0,**data),indent=2)+'\n')

def test_fresh_original320_page_all_case_and_real_old_key_get_only(goal_page):
    f,page,errors=goal_page;p=setup(f,GOALS[3]);clones=clone_existing_resource(f,130)
    page.set_viewport_size(dict(width=320,height=1000));open_case(page,f,p)
    h,storage,posted=lost(page,f,p,'ADOPT');original=deepcopy(stored(f,p));assert original['dependency_manifest']['collections']['resources']['known'] is False
    with f[1].connect() as c:c.execute('DELETE FROM synthetic_resource_grants WHERE principal_id=%s AND resource_id=ANY(%s)',('fixture-a',clones))
    before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_case(page,f,p);wait_recovered(page)
    view=page.evaluate('servicePlanView');ids={s['id'] for s in original['steps']}
    assert set(view['change_impact']['affected'])==ids and view['change_impact']['preserved']==[] and view['change_impact']['unknown_scope']=='THIS_CASE'
    assert '需处理 4 个受影响步骤；保留 0 个未受影响步骤' in page.locator('#service-plan-coverage').inner_text()
    assert view['read_only'] and not view['can_adopt'] and page.locator('[data-service-action]').count()==0
    assert requests and set(requests)=={'GET'} and snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==storage
    assert 'PRIVATE_' not in page.locator('#service-case-plan-detail').inner_text() and all(v not in storage for v in f[2].values())
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');OUT.mkdir(parents=True,exist_ok=True);page.locator('#service-case-plan-detail').scroll_into_view_if_needed();page.screenshot(path=str(OUT/'fresh-all-case-320.png'))
    page.locator('#service-plan-release').click();page.wait_for_function('()=>servicePlanRecoveryHandle===null&&servicePlanView?.can_adopt&&!servicePlanView.read_only')
    assert set(page.evaluate('servicePlanView.change_impact.affected'))==ids and page.evaluate('servicePlanView.change_impact.preserved')==[]
    page.unroute('**/api/preparations/'+p['preparation_id']+'/service-case-plan')
    page.locator('#service-plan-reason').fill('SYNTHETIC independent fresh explicit local adoption');page.locator('#service-plan-adopt').click();page.wait_for_function('()=>servicePlanPending===null&&servicePlanView?.revision===2')
    now=stored(f,p);assert set(now['events'][-1]['local_revision']['affected'])==ids and now['events'][-1]['local_revision']['preserved']==[]
    assert now['events'][:-1]==original['events'] and [s['id'] for s in now['steps']]==[s['id'] for s in original['steps']]
    committed=snapshot(f);old=recover(f,p,h['key']);assert old.status_code==200 and old.json()['status']=='COMMITTED' and snapshot(f)==committed
    page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadServiceCasePlan(id).catch(servicePlanError)',p['preparation_id']);page.wait_for_function('()=>servicePlanView===null')
    assert page.locator('#service-case-plan-detail').is_hidden() and 'PRIVATE_' not in page.locator('#service-case-plan-detail').inner_text() and snapshot(f)==committed and not errors
    write('fresh-original-page',dict(actual_http=True,pg=True,chromium=True,width=320,literal_affected=4,literal_preserved=0,old_committed_key_get_only=True,old_handle_expiry_unchanged=True,no_read_writes=True,no_private_token_or_reason_in_handle_or_cold_page=True,cross_enterprise_private_view_cleared=True,explicit_original_page_local_adopt=True,history_stable_ids_preserved=True))

@pytest.mark.parametrize('change',['resource','run-access'])
def test_independent_literal_partition_locked_owner_and_cas(real_f,change):
    f=real_f;p,*_=complete(f,local=True)
    upstream=('P1',) if change=='resource' else ('P1','P2');affected=('P2','P3','P4','P5') if change=='resource' else ('P3','P4','P5')
    for a in upstream:assert lock(f,p,a).status_code==200
    assert lock(f,p,'P3').status_code==200;original=deepcopy(stored(f,p))
    if change=='resource':clone_existing_resource(f,1)
    else:
        with f[1].connect() as c:c.execute('INSERT INTO run_assignments(run_id,principal_id,park_id,org_id,active) VALUES(%s,%s,%s,%s,true)',(p['run_id'],'unassigned','park-a','org-a'))
    view=read(f,p).json();ids={s['adapter_id']:s['id'] for s in view['steps']}
    assert set(view['change_impact']['affected'])=={ids[a] for a in affected} and set(view['change_impact']['preserved'])=={ids[a] for a in upstream}
    assert step(view,'P3')['state']=='LOCK_CONFLICT' and not view['can_adopt'];before_business=business(f)
    denied=adopt(f,p,patch_body(f,p));assert denied.status_code==409 and stored(f,p)['events']==original['events']
    assert command(f,p,'P3','UNLOCK').status_code==200;body=patch_body(f,p);before=stored(f,p);key=uuid4().hex
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda k:adopt(f,p,body,k),[key,uuid4().hex]))
    assert sorted(r.status_code for r in rs)==[201,409];now=stored(f,p);assert now['revision']==before['revision']+1 and now['events'][:-1]==before['events']
    for a in upstream:assert next(s for s in now['steps'] if s['adapter_id']==a)==next(s for s in original['steps'] if s['adapter_id']==a)
    accepted=next(r.json() for r in rs if r.status_code==201);actual_key=accepted['event']['request_key'];current=snapshot(f)
    recovered=recover(f,p,actual_key);assert recovered.status_code==200 and recovered.json()['status']=='COMMITTED' and snapshot(f)==current
    assert adopt(f,p,body,actual_key).json()['event']==accepted['event'] and snapshot(f)==current
    assert adopt(f,p,{**body,'reason':'SYNTHETIC distinct retry body'},actual_key).status_code==409 and snapshot(f)==current
    assert business(f)==before_business
    for a in affected:verified(f,p,a)
    assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED' and business(f)==before_business
    write('literal-'+change,dict(actual_http=True,pg=True,literal_affected=list(affected),literal_preserved=list(upstream),missed_updates=0,wrong_changes=0,affected_lock_refused=True,explicit_unlock_required=True,unaffected_original_locks_preserved=True,cas_statuses=[201,409],same_key_same_body_no_new_event=True,changed_body_rejected=True,old_key_get_only=True,explicit_original_verifies=len(affected),old_history_and_business_preserved=True))

@pytest.fixture
def exclusive_case(tmp_path):
    import pgserver,conftest
    data=Path(tempfile.mkdtemp(prefix='pw-independent-local-revision-restart-'))/'data';server=pgserver.get_server(data,cleanup_mode='stop')
    server._case_fact_fixture_cluster=facts.capture_fixture_cluster(server.get_uri(),data.resolve())
    with psycopg.connect(server.get_uri(),autocommit=True) as c:c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
    generator=conftest.fixture.__wrapped__(server,None)
    try:
        f=next(generator);f=preparation_fixture.__wrapped__(f);f=receipt_fixture.__wrapped__(f);f=link_fixture.__wrapped__(f);yield f,server
    finally:generator.close();server.cleanup();assert not (data/'postmaster.pid').exists()

def start_owned_api(f,page,port,log):
    env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PYTHONPATH=str(Path.cwd()/'src'),PYTHONDONTWRITEBYTECODE='1')
    proc=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],env=env,stdout=log,stderr=log)
    end=time.monotonic()+10
    while proc.poll() is None and time.monotonic()<end:
        try:
            r=page.request.get(f'http://127.0.0.1:{port}/health',timeout=500)
            if r.ok and r.json()['process_id']==proc.pid:return proc
        except Exception:pass
        time.sleep(.02)
    if proc.poll() is None:proc.terminate();proc.wait(5)
    raise AssertionError('independent owned API readiness deadline')

def test_actual_owned_postgresql_restart_old_local_key_cold_browser_get_only(exclusive_case):
    f,server=exclusive_case
    with actual_http(create_app(f[0])) as (client,requests):
        live=(*f[:3],client);p,*_=complete(live,local=True);clone_existing_resource(live,1)
    original=deepcopy(stored(f,p));old_pid=server.get_pid()
    with f[1].connect() as c:before_identity=facts._migration_identity(c)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    OUT.mkdir(parents=True,exist_ok=True);active=None;pids=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        with (OUT/'owned-pg-api-restart.log').open('w') as log:
            try:
                active=start_owned_api(f,page,port,log);pids.append(active.pid);page.goto(f'http://127.0.0.1:{port}/');open_case(page,f,p);h,storage,posted=lost(page,f,p,'ADOPT');committed=snapshot(f)
                active.terminate();active.wait(5);active=None
                from pgserver._commands import pg_ctl
                pg_ctl(['-w','-m','fast','stop'],pgdata=server.pgdata,user=server.system_user,timeout=10,env=minimal_environment(os.environ));assert not (server.pgdata/'postmaster.pid').exists();server.ensure_postgres_running()
                with f[1].connect() as c:after_identity=facts._migration_identity(c)
                assert server.get_pid()!=old_pid and before_identity['postmaster_start']!=after_identity['postmaster_start']
                assert all(before_identity[k]==after_identity[k] for k in ('system_identifier','database_oid','database_name','data_directory','owner_name'))
                active=start_owned_api(f,page,port,log);pids.append(active.pid);assert pids[0]!=pids[1]
                page.reload();methods=[];page.on('request',lambda r:methods.append(r.method));open_case(page,f,p);wait_recovered(page)
                assert methods and set(methods)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==committed
                assert page.evaluate('servicePlanRecoveryHandle.key')==h['key'] and page.evaluate('servicePlanView.plan_id')==original['id']
                assert page.evaluate('servicePlanView.events.at(-1).id')==posted['result']['command_receipt']['id'] and page.evaluate('servicePlanView.read_only')
                endpoint=f'http://127.0.0.1:{port}/api/preparations/'+p['preparation_id']
                rec=page.request.get(endpoint+'/service-case-plan/command-recovery',headers=headers(f[2],key=h['key']));assert rec.status==200 and rec.json()['status']=='COMMITTED'
                goal=page.request.get(endpoint+'/goal-results',headers=headers(f[2]));assert goal.status==200 and goal.json()['state']=='UNVERIFIED'
                assert page.request.get(endpoint+'/plan-approval',headers=headers(f[2])).status==403
                assert not page.request.get(f'http://127.0.0.1:{port}/api/plan-approval/status',headers=headers(f[2])).json()['enabled']
                assert snapshot(f)==committed and not errors
                write('actual-owned-pg-api-restart',dict(actual_http=True,pg=True,chromium=True,own_postgresql_stop_start=True,old_pg_pid=old_pid,new_pg_pid=server.get_pid(),postmaster_start_changed=True,same_database_oid_system_id_and_data=True,api_pids=pids,different_api_pids=True,same_origin=True,original_key_COMMITTED=True,cold_browser_get_only=True,original_handle_unchanged=True,no_read_sql_business_write=True,new_approval_write_enabled=False,no_fixture_capability_reissued=True,stale_original_outputs_UNVERIFIED=True))
            finally:
                if active is not None and active.poll() is None:active.terminate();active.wait(5)
                context.close();browser.close()
