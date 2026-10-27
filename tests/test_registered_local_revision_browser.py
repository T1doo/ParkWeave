"""Original page, actual HTTP/PG/Chromium, durable ADOPT local revision recovery."""
import json,os,socket,subprocess,sys,time
from pathlib import Path
import pytest
from parkweave.process_env import minimal_environment
from test_registered_local_revision import (link_fixture,receipt_fixture,preparation_fixture,
    complete,add_resource,stored,read,step,snapshot,patch_body,patch,command,GOALS)
from test_service_case_steps import setup
from test_service_plan_manual_lock import lock
from test_service_plan_recovery_browser import goal_page,open_case,lost,wait_recovered,wait_held
from test_case_goal_results_browser import read_page
OUT=Path('.runtime/registered-local-revision/browser')


def changed(f,p):
    add_resource(f);x=read(f,p).json();assert x['local_revision_required'] and x['can_adopt'];return x


def test_original_page_local_patch_unknown_response_cold_recovery_and_explicit_checks(goal_page):
    f,page,errors=goal_page;p,g,d,s=complete(f,local=True);assert lock(f,p,'P1').status_code==200;old=stored(f,p)
    changed(f,p);open_case(page,f,p);assert '局部修订' in page.locator('#service-plan-adopt').inner_text()
    assert page.evaluate('servicePlanView.change_impact.preserved')==[old['steps'][0]['id']]
    h,storage,posted=lost(page,f,p,'ADOPT');assert posted['body']['local_revision'] is True and h['plan']==old['id'] and h['revision']==old['revision']
    assert posted['result']['command_receipt']['revision']==old['revision']+1 and posted['result']['plan_id']==old['id']
    before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#service-plan-retry').click();wait_recovered(page)
    assert snapshot(f)==before and set(requests)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==storage
    page.reload();open_case(page,f,p);wait_recovered(page);assert snapshot(f)==before and set(requests)=={'GET'}
    new=page.context.new_page();new.goto(page.url);page.close();page=new;requests=[];page.on('request',lambda r:requests.append(r.method));open_case(page,f,p);wait_recovered(page)
    assert snapshot(f)==before and set(requests)=={'GET'} and 'PRIVATE_EXPLICIT_LOCAL_PATCH' not in page.locator('#service-case-plan-detail').inner_text()
    assert page.evaluate('servicePlanView.steps.map(s=>s.id)')==[z['id'] for z in old['steps']] and page.locator('[data-service-action]').count()==0
    page.locator('#service-plan-release').click();page.wait_for_function('()=>servicePlanView!==null&&!servicePlanView.read_only&&servicePlanRecoveryHandle===null')
    assert page.evaluate('JSON.stringify({...localStorage})')=='{}' and page.evaluate('servicePlanView.steps[0].manually_locked')
    for a in ('P2','P3','P4','P5'):
        page.locator('#service-plan-reason').fill('SYNTHETIC explicit revised dependency verification '+a)
        page.locator('[data-service-adapter="'+a+'"] [data-service-action="VERIFY"]').click()
        page.wait_for_function('(a)=>servicePlanPending===null&&servicePlanView.steps.find(s=>s.adapter_id===a).state==="VERIFIED"',arg=a)
    read_page(page);assert page.evaluate('goalResultView.state')=='LOCAL_OUTPUTS_VERIFIED' and not page.evaluate('goalResultView.case_goal_completed')
    assert stored(f,p)['events'][:len(old['events'])]==old['events'] and stored(f,p)['steps'][0]==old['steps'][0]
    OUT.mkdir(parents=True,exist_ok=True)
    for width in (1200,390,320):
        page.set_viewport_size({'width':width,'height':1000});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'local-revision-{width}.png'))
    (OUT/'original-page-local-revision.json').write_text(json.dumps(dict(actual_http=True,persistent_postgresql=True,adopt_same_plan=True,stable_steps=True,unchanged_history=True,unaffected_lock_preserved=True,hot_cold_new_page_get_only=True,explicit_verify_count=4,case_goal_completed=False,missed_updates=0,wrong_changes=0,model_calls=0),indent=2)+'\n')
    assert not errors


@pytest.mark.parametrize('target',['case','identity'])
def test_late_actual_local_adoption_response_never_replaces_new_context(goal_page,target):
    f,page,errors=goal_page;p,g,d,s=complete(f);p2=setup(f,GOALS[0]);changed(f,p);open_case(page,f,p);held=[]
    def hold(route):
        if route.request.method!='POST':route.continue_();return
        r=route.fetch();assert r.status==201;held.append((route,r))
    page.route('**/api/preparations/'+p['preparation_id']+'/service-case-plan',hold)
    page.locator('#service-plan-reason').fill('SYNTHETIC PRIVATE_LATE_LOCAL_PATCH');page.locator('#service-plan-adopt').click();wait_held(page,held)
    storage=page.evaluate('JSON.stringify({...localStorage})')
    if target=='case':open_case(page,f,p2)
    else:page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
    page.locator('#page-feedback').evaluate('(e)=>e.textContent="SYNTHETIC NEW_PATCH_CONTEXT"');before=snapshot(f)
    held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(150)
    assert page.locator('#page-feedback').inner_text()=='SYNTHETIC NEW_PATCH_CONTEXT' and snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==storage
    if target=='case':assert page.evaluate('servicePlanView.preparation_id')==p2['preparation_id']
    assert not errors


@pytest.mark.parametrize('cap',['READ','PREPARE','EXECUTE'])
def test_actual_local_patch_unknown_recovery_rechecks_authority_and_clears_private_view(goal_page,cap):
    f,page,errors=goal_page;p,g,d,s=complete(f);changed(f,p);open_case(page,f,p);h,storage,_=lost(page,f,p,'ADOPT')
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True);table='preparation_grants' if cap=='PREPARE' else 'capability_grants';c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
    before=snapshot(f);page.locator('#service-plan-retry').click();page.wait_for_function('()=>servicePlanView===null')
    assert page.locator('#service-case-plan-detail').is_hidden() and page.locator('#service-plan-reason').input_value()=='' and snapshot(f)==before
    assert page.evaluate('JSON.stringify({...localStorage})')==storage and not errors


def test_owned_api_restart_recovers_local_adoption_same_pg_and_original_handle_with_get_only(goal_page,tmp_path):
    f,page,errors=goal_page;p,g,d,s=complete(f);changed(f,p);old=stored(f,p);active=None;pids=[]
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PYTHONPATH=str(Path.cwd()/'src'))
    cmd=[sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log']
    with (tmp_path/'owned-local-revision-api.log').open('w') as log:
        def start_api():
            proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=log);pids.append(proc.pid);end=time.monotonic()+10
            while proc.poll() is None and time.monotonic()<end:
                try:
                    r=page.request.get(f'http://127.0.0.1:{port}/health',timeout=500)
                    if r.ok and r.json()['process_id']==proc.pid:return proc
                except Exception:pass
                time.sleep(.05)
            proc.terminate();proc.wait(5);raise AssertionError('owned revision API readiness deadline')
        try:
            active=start_api();page.goto(f'http://127.0.0.1:{port}/');open_case(page,f,p);h,storage,posted=lost(page,f,p,'ADOPT');before=snapshot(f)
            active.terminate();active.wait(5);active=None;active=start_api();assert pids[0]!=pids[1]
            page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_case(page,f,p);wait_recovered(page)
            assert page.evaluate('servicePlanRecoveryHandle.key')==h['key'] and page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==before and set(requests)=={'GET'}
            assert page.evaluate('servicePlanView.plan_id')==old['id'] and page.evaluate('servicePlanView.events.at(-1).id')==posted['result']['command_receipt']['id'] and not errors
            OUT.mkdir(parents=True,exist_ok=True);(OUT/'owned-api-restart.json').write_text(json.dumps(dict(different_owned_processes=True,same_origin=True,same_postgresql=True,stable_plan_id=True,adopt_revision_increment=True,unknown_command_get_only=True,duplicate_business_writes=0),indent=2)+'\n')
        finally:
            if active is not None and active.poll() is None:active.terminate();active.wait(5)
