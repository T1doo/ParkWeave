"""Actual loopback HTTP/PostgreSQL/Chromium for original decision locks."""
import json,os,socket,subprocess,sys,time
from pathlib import Path
import pytest
from parkweave.process_env import minimal_environment
from test_service_plan_manual_lock import (link_fixture,receipt_fixture,preparation_fixture,start,lock,
    command,read,step,stored,GOALS,save,snapshot,preparation_act)
from test_service_plan_recovery_browser import (goal_page,open_case,lost,wait_recovered,wait_held,
    damage_handle,assert_handle_refused)
OUT=Path('.runtime/service-plan-manual-lock/browser')


@pytest.mark.parametrize('action',['LOCK','UNLOCK'])
def test_actual_lost_lock_response_hot_cold_and_new_page_get_only(goal_page,action):
    f,page,errors=goal_page;p=start(f)
    if action=='UNLOCK':assert lock(f,p).status_code==200
    open_case(page,f,p);h,storage,posted=lost(page,f,p,action);before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method))
    page.locator('#service-plan-retry').click();wait_recovered(page);assert snapshot(f)==before and set(requests)=={'GET'} and page.evaluate('servicePlanView.event') is None
    page.reload();open_case(page,f,p);wait_recovered(page);assert page.evaluate('servicePlanRecoveryHandle.action')==action and page.evaluate('JSON.stringify({...localStorage})')==storage
    new=page.context.new_page();new.goto(page.url);page.close();page=new;requests=[];page.on('request',lambda r:requests.append(r.method));open_case(page,f,p);wait_recovered(page)
    assert snapshot(f)==before and set(requests)=={'GET'} and 'PRIVATE_UNKNOWN_STEP_REASON' not in page.locator('#service-case-plan-detail').inner_text()
    assert page.locator('[data-service-action]').count()==0
    page.locator('#service-plan-release').click();page.wait_for_function('()=>servicePlanView!==null&&!servicePlanView.read_only')
    assert page.evaluate('JSON.stringify({...localStorage})')=='{}' and page.evaluate('servicePlanView.steps[0].manually_locked')==(action=='LOCK') and snapshot(f)==before and set(requests)=={'GET'} and not errors


def test_actual_conflict_shows_history_and_requires_explicit_unlock_before_new_plan(goal_page):
    f,page,errors=goal_page;p=start(f,GOALS[1]);old=stored(f,p);open_case(page,f,p)
    page.locator('#service-plan-reason').fill('SYNTHETIC protect original verification');page.locator('[data-service-action="LOCK"]').click();page.wait_for_function('()=>servicePlanPending===null&&servicePlanView.steps[0].manually_locked')
    assert save(f,p,goals=[GOALS[0]],text='SYNTHETIC changed original request').status_code==200
    page.locator('#service-plan-read').click();page.wait_for_function('()=>servicePlanView?.steps[0].state==="LOCK_CONFLICT"')
    assert '人工锁冲突' in page.locator('#service-plan-steps').inner_text() and page.locator('#service-plan-adopt').is_hidden()
    assert page.locator('[data-service-action="UNLOCK"]').count()==1 and page.locator('[data-service-action="VERIFY"]').count()==0
    assert stored(f,p)['steps'][0]['verified_sources']==old['steps'][0]['verified_sources']
    OUT.mkdir(parents=True,exist_ok=True)
    for width in (1200,390,320):
        page.set_viewport_size({'width':width,'height':1000});page.locator('#service-case-plan-detail').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'lock-conflict-{width}.png'))
    before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_case(page,f,p)
    assert page.evaluate('servicePlanView.steps[0].state')=='LOCK_CONFLICT' and snapshot(f)==before and set(requests)=={'GET'}
    page.locator('#service-plan-reason').fill('SYNTHETIC explicit unlock for changed request');page.locator('[data-service-action="UNLOCK"]').click();page.wait_for_function('()=>servicePlanPending===null&&servicePlanView.can_adopt')
    assert page.evaluate('servicePlanView.steps[0].state')=='BLOCKED'
    page.locator('#service-plan-reason').fill('SYNTHETIC explicitly adopt new version');page.locator('#service-plan-adopt').click();page.wait_for_function('()=>servicePlanPending===null&&servicePlanView.history.length===1')
    assert page.evaluate('servicePlanView.plan_id')!=old['id'] and stored(f,p)['history'][0]['steps'][0]['verified_sources']==old['steps'][0]['verified_sources'] and not errors


@pytest.mark.parametrize('action',['LOCK','UNLOCK'])
@pytest.mark.parametrize('target',['case','identity'])
def test_late_original_lock_post_does_not_replace_new_context(goal_page,action,target):
    f,page,errors=goal_page;p=start(f);p2=start(f)
    if action=='UNLOCK':assert lock(f,p).status_code==200
    open_case(page,f,p);held=[]
    def hold(route):
        if route.request.method!='POST':route.continue_();return
        r=route.fetch();assert r.status==200;held.append((route,r))
    page.route('**/service-case-plan/commands',hold);page.locator('#service-plan-reason').fill('SYNTHETIC PRIVATE_LOCK_POST');page.locator('[data-service-action="'+action+'"]').click();wait_held(page,held)
    storage=page.evaluate('JSON.stringify({...localStorage})')
    if target=='case':open_case(page,f,p2)
    else:page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
    page.locator('#page-feedback').evaluate('(e)=>e.textContent="SYNTHETIC NEW_LOCK_CONTEXT"');before=snapshot(f);held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(150)
    assert page.locator('#page-feedback').inner_text()=='SYNTHETIC NEW_LOCK_CONTEXT' and page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==before and not errors
    if target=='case':assert page.evaluate('servicePlanView.preparation_id')==p2['preparation_id']


@pytest.mark.parametrize('action',['LOCK','UNLOCK'])
def test_actual_revoked_lock_unknown_recovery_clears_private_view_preserves_handle(goal_page,action):
    f,page,errors=goal_page;p=start(f)
    if action=='UNLOCK':assert lock(f,p).status_code==200
    open_case(page,f,p);h,storage,_=lost(page,f,p,action)
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
    before=snapshot(f);page.locator('#service-plan-retry').click();page.wait_for_function('()=>servicePlanView===null')
    assert page.locator('#service-case-plan-detail').is_hidden() and page.locator('#service-plan-reason').input_value()=='' and snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==storage and not errors


@pytest.mark.parametrize('action',['LOCK','UNLOCK'])
def test_expired_hot_lock_handle_clears_prior_private_event_and_does_not_request(goal_page,action):
    f,page,errors=goal_page;p=start(f)
    if action=='UNLOCK':assert lock(f,p).status_code==200
    open_case(page,f,p);h,_,_=lost(page,f,p,action);damage_handle(page,h,'expired');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#service-plan-retry').click()
    assert_handle_refused(page,f,before,'SYNTHETIC PRIVATE_UNKNOWN_STEP_REASON');assert requests==[] and page.evaluate('servicePlanView.event') is None and not errors


@pytest.mark.parametrize('action',['LOCK','UNLOCK'])
def test_owned_api_restart_same_origin_pg_preserves_original_lock_unknown_get_only(goal_page,tmp_path,action):
    f,page,errors=goal_page;p=start(f);active=None;pids=[]
    if action=='UNLOCK':assert lock(f,p).status_code==200
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PYTHONPATH=str(Path.cwd()/'src'))
    cmd=[sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log']
    with (tmp_path/'owned-lock-api.log').open('w') as log:
        def start_api():
            proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=log);pids.append(proc.pid);end=time.monotonic()+10
            while proc.poll() is None and time.monotonic()<end:
                try:
                    r=page.request.get(f'http://127.0.0.1:{port}/health',timeout=500)
                    if r.ok and r.json()['process_id']==proc.pid:return proc
                except Exception:pass
                time.sleep(.05)
            proc.terminate();proc.wait(5);raise AssertionError('owned lock API readiness deadline')
        try:
            active=start_api();page.goto(f'http://127.0.0.1:{port}/');open_case(page,f,p);h,storage,posted=lost(page,f,p,action);before=snapshot(f)
            active.terminate();active.wait(5);active=None;active=start_api();assert pids[0]!=pids[1]
            page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_case(page,f,p);wait_recovered(page)
            assert page.evaluate('servicePlanRecoveryHandle.key')==h['key'] and page.evaluate('JSON.stringify({...localStorage})')==storage and set(requests)=={'GET'} and snapshot(f)==before and not errors
            assert page.evaluate('servicePlanView.events.at(-1).id')==posted['result']['command_receipt']['id']
            OUT.mkdir(parents=True,exist_ok=True);(OUT/('api-restart-'+action.lower()+'.json')).write_text(json.dumps(dict(different_owned_processes=True,same_origin=True,same_persistent_postgresql=True,action=action,unknown_command_get_only=True,duplicate_business_writes=0),indent=2)+'\n')
        finally:
            if active is not None and active.poll() is None:active.terminate();active.wait(5)
