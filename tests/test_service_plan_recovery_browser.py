"""Real loopback HTTP/PG/Chromium: bounded original plan handles, no unknown POST replay."""
import json,os,socket,subprocess,sys,time
from pathlib import Path
from uuid import uuid4
import pytest
from parkweave.process_env import minimal_environment
from test_service_plan_recovery import link_fixture,receipt_fixture,preparation_fixture,setup,adopt,command,read,step,GOALS,snapshot,recover,adopt_body,save,accepted
from test_case_goal_results_browser import goal_page,open_case,wait_held
from test_preparation import headers
OUT=Path('.runtime/service-plan-cold-recovery/browser')

def prep(f,action):
 p=setup(f,GOALS[0])
 if action!='ADOPT':
  row=adopt(f,p).json()
  if action=='RETRY':assert command(f,p,'P1','REPORT_FAILURE',row=row).status_code==200
 return p

def lost(page,f,p,action):
 captured=[]
 def lose(route):
  if route.request.method!='POST':route.continue_();return
  r=route.fetch();assert r.status in (200,201);captured.append(dict(key=route.request.headers['idempotency-key'],body=route.request.post_data_json,result=r.json()));route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/service-case-plan'+('' if action=='ADOPT' else '/commands'),lose)
 page.locator('#service-plan-reason').fill('SYNTHETIC PRIVATE_UNKNOWN_STEP_REASON')
 page.locator('#service-plan-adopt' if action=='ADOPT' else '[data-service-action="'+action+'"]').first.click();page.wait_for_function('()=>servicePlanPending?.stage==="UNCERTAIN"');assert len(captured)==1
 stored=page.evaluate('JSON.stringify({...localStorage})');h=json.loads(next(iter(json.loads(stored).values())));assert set(h)=={'v','id','key','actor','case','run','action','plan','step','revision','expires'} and h['key']==captured[0]['key'];assert 'PRIVATE_' not in stored and f[2]['fixture-a'] not in stored and h['actor']==page.evaluate('servicePlanView.actor_ref');return h,stored,captured[0]

def wait_recovered(page):page.wait_for_function('()=>servicePlanRecoveryHandle?.observed&&!servicePlanRecoveryChecking&&servicePlanPending===null')
def open_again(page,f,p):open_case(page,f,p);wait_recovered(page)

@pytest.mark.parametrize('action',['ADOPT','BEGIN','REPORT_FAILURE','RETRY','VERIFY'])
def test_five_actual_committed_lost_responses_warm_get_cold_reload_and_new_page_get_only(goal_page,action):
 f,page,errors=goal_page;p=prep(f,action);open_case(page,f,p);h,stored,posted=lost(page,f,p,action);before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#service-plan-retry').click();wait_recovered(page)
 assert requests and set(requests)=={'GET'} and snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==stored;assert page.locator('#service-plan-reason').input_value()=='SYNTHETIC PRIVATE_UNKNOWN_STEP_REASON' and page.locator('#service-plan-reason').is_disabled();assert page.evaluate('servicePlanView.read_only') and page.locator('[data-service-action]').count()==0
 page.reload();assert page.locator('#token').input_value()=='';open_again(page,f,p);assert page.evaluate('servicePlanRecoveryHandle.key')==h['key'] and page.evaluate('servicePlanRecoveryHandle.expires')==h['expires'];assert 'PRIVATE_UNKNOWN_STEP_REASON' not in page.locator('#service-case-plan-detail').inner_text();assert snapshot(f)==before and set(requests)=={'GET'}
 url=page.url;new=page.context.new_page();new.on('pageerror',lambda e:errors.append(str(e)));new.goto(url);assert new.locator('#token').input_value()=='';page.close();page=new;requests=[];page.on('request',lambda r:requests.append(r.method));open_again(page,f,p);assert page.evaluate('JSON.stringify({...localStorage})')==stored and snapshot(f)==before and set(requests)=={'GET'}
 page.locator('#service-plan-retry').click();wait_recovered(page);assert snapshot(f)==before;page.evaluate("()=>document.getElementById('service-plan-reason').value='SYNTHETIC new unsent draft'");page.locator('#service-plan-retry').click();wait_recovered(page);assert page.locator('#service-plan-reason').input_value()=='SYNTHETIC new unsent draft' and snapshot(f)==before
 if action=='ADOPT':
  OUT.mkdir(parents=True,exist_ok=True)
  for width in (1200,390,320):page.set_viewport_size({'width':width,'height':1000});page.locator('#service-case-plan-detail').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'recovery-{width}.png'))
 page.locator('#service-plan-release').click();page.wait_for_function('()=>servicePlanRecoveryHandle===null&&servicePlanView!==null&&!servicePlanView.read_only');assert page.evaluate('JSON.stringify({...localStorage})')=='{}' and page.locator('#service-plan-reason').input_value()=='SYNTHETIC new unsent draft' and snapshot(f)==before and set(requests)=={'GET'} and not errors
 # Explicit same-key repetition remains idempotent; recovery itself never issued it.
 suffix='' if action=='ADOPT' else '/commands';response=page.request.post(page.url.rstrip('/')+'/api/preparations/'+p['preparation_id']+'/service-case-plan'+suffix,headers=headers(f[2],key=h['key']),data=posted['body']);assert response.status in (200,201) and response.json()['command_receipt']['id']==posted['result']['command_receipt']['id'] and snapshot(f)==before

@pytest.mark.parametrize('cap',['READ','PREPARE','EXECUTE'])
def test_actual_revoke_clears_private_unknown_view_keeps_handle_and_restored_authority_cold_recovers(goal_page,cap):
 f,page,errors=goal_page;p=prep(f,'VERIFY');open_case(page,f,p);h,stored,_=lost(page,f,p,'VERIFY')
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True)
  table='preparation_grants' if cap=='PREPARE' else 'capability_grants';c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
 before=snapshot(f);page.locator('#service-plan-retry').click();page.wait_for_function('()=>servicePlanView===null&&servicePlanRecoveryHandle===null');assert page.locator('#service-case-plan-detail').is_hidden() and page.locator('#service-plan-reason').input_value()=='' and '访问权已失效' in page.locator('#page-feedback').inner_text() and page.evaluate('JSON.stringify({...localStorage})')==stored and snapshot(f)==before and not errors
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute('UPDATE '+table+" SET active=true WHERE principal_id='fixture-a' AND capability=%s",(cap,))
 before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_again(page,f,p);assert page.evaluate('servicePlanRecoveryHandle.key')==h['key'] and snapshot(f)==before and set(requests)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==stored

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_cold_other_identity_never_uses_original_actor_handle_or_sees_private_reason(goal_page,user):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,stored,_=lost(page,f,p,'BEGIN');before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append((r.method,r.headers.get('idempotency-key'))));page.locator('#token').fill(f[2][user]);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadServiceCasePlan(id).catch(servicePlanError)',p['preparation_id']);page.wait_for_timeout(200)
 assert page.evaluate('servicePlanRecoveryHandle') is None and 'PRIVATE_UNKNOWN_STEP_REASON' not in page.locator('#service-case-plan-detail').inner_text();assert all(method=='GET' and key!=h['key'] for method,key in requests) and snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==stored and not errors

@pytest.mark.parametrize('target',['identity','case'])
@pytest.mark.parametrize('denied',[False,True])
def test_late_actual_recovery200_or403_does_not_clear_new_identity_or_case(goal_page,target,denied):
 f,page,errors=goal_page;p=prep(f,'VERIFY');p2=prep(f,'BEGIN');open_case(page,f,p);h,stored,_=lost(page,f,p,'VERIFY');held=[]
 def hold(route):
  if not route.request.headers.get('idempotency-key'):route.continue_();return
  held.append((route,None if denied else route.fetch()))
 page.route('**/service-case-plan/command-recovery',hold);page.locator('#service-plan-retry').click();wait_held(page,held)
 if target=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
 else:open_case(page,f,p2)
 page.locator('#page-feedback').evaluate('(e)=>e.textContent="SYNTHETIC NEW_CONTEXT"')
 if denied:
  with f[1].connect() as c:f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
 before=snapshot(f);route,r=held[0]
 if denied:r=route.fetch();assert r.status==403
 else:assert r.status==200
 route.fulfill(response=r);page.wait_for_timeout(150);assert page.locator('#page-feedback').inner_text()=='SYNTHETIC NEW_CONTEXT' and snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==stored and not errors
 if target=='case':assert page.evaluate('servicePlanView.preparation_id')==p2['preparation_id']

@pytest.mark.parametrize('damage',['expired','future','extra','missing','oversized'])
def test_expired_or_malformed_handle_not_used_for_cold_recovery(goal_page,damage):
 f,page,errors=goal_page;p=prep(f,'VERIFY');open_case(page,f,p);h,stored,_=lost(page,f,p,'VERIFY')
 name=next(iter(json.loads(stored)))
 if damage=='expired':h['expires']=0
 elif damage=='future':h['expires']=999999999999999
 elif damage=='extra':h['body']='SYNTHETIC private forbidden'
 elif damage=='missing':del h['expires']
 raw='x'*641 if damage=='oversized' else json.dumps(h);page.evaluate('([name,raw])=>localStorage.setItem(name,raw)',[name,raw]);before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.headers.get('idempotency-key')));open_case(page,f,p);assert page.evaluate('servicePlanRecoveryHandle') is None and page.evaluate('JSON.stringify({...localStorage})')=='{}' and h['key'] not in requests and snapshot(f)==before and not errors

@pytest.mark.parametrize('kind',['unavailable','capacity'])
def test_no_post_when_original_handle_cannot_be_saved(goal_page,kind):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p)
 if kind=='unavailable':page.evaluate("()=>{Storage.prototype.setItem=function(){throw Error('SYNTHETIC unavailable')}}")
 else:page.evaluate("()=>{for(let n=0;n<8;n++){const h={v:1,id:crypto.randomUUID(),key:crypto.randomUUID(),actor:servicePlanView.actor_ref,case:crypto.randomUUID(),run:crypto.randomUUID(),action:'ADOPT',plan:null,step:null,revision:0,expires:Date.now()+86400000};localStorage.setItem(servicePlanRecoveryName(h),JSON.stringify(h));}}")
 before=snapshot(f);stored=page.evaluate('JSON.stringify({...localStorage})');requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#service-plan-reason').fill('SYNTHETIC unsent');page.locator('[data-service-action="BEGIN"]').click();page.wait_for_timeout(100);assert all(method=='GET' for method in requests) and '尚未发送' in page.locator('#service-plan-error').inner_text() and page.evaluate('servicePlanPending') is None and page.evaluate('JSON.stringify({...localStorage})')==stored and snapshot(f)==before and not errors

def test_actual_unknown_handle_same_parameters_do_not_extend_expiry(goal_page):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,stored,_=lost(page,f,p,'BEGIN');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method))
 value=page.evaluate("()=>{const original=Date.now;Date.now=()=>original()+1000;try{const h=rememberServicePlanHandle(servicePlanPending,servicePlanView);return {expires:h.expires,raw:JSON.stringify({...localStorage})}}finally{Date.now=original}}")
 assert value['expires']==h['expires'] and value['raw']==stored and requests==[] and snapshot(f)==before and not errors

def test_cold_source_and_request_replacement_keeps_history_unverified_without_read_write(goal_page):
 f,page,errors=goal_page;p=prep(f,'VERIFY');open_case(page,f,p);h,stored,_=lost(page,f,p,'VERIFY');assert save(f,p,goals=[GOALS[0],GOALS[1]],text='SYNTHETIC original request changed').status_code==200;before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_again(page,f,p);assert page.evaluate('servicePlanView.state')=='BLOCKED' and snapshot(f)==before and set(requests)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==stored and not errors

def test_owned_api_restart_same_origin_pg_cold_unknown_handle_get_only(goal_page,tmp_path):
 f,page,errors=goal_page;p=prep(f,'BEGIN');active=None;pids=[]
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PYTHONPATH=str(Path.cwd()/'src'));cmd=[sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log']
 with (tmp_path/'owned-api.log').open('w') as log:
  def start_api():
   proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=log);pids.append(proc.pid);end=time.monotonic()+10
   while proc.poll() is None and time.monotonic()<end:
    try:
     r=page.request.get(f'http://127.0.0.1:{port}/health',timeout=500)
     if r.ok and r.json()['process_id']==proc.pid:return proc
    except Exception:pass
    time.sleep(.05)
   proc.terminate();proc.wait(5);raise AssertionError('owned API readiness deadline')
  try:
   active=start_api();page.goto(f'http://127.0.0.1:{port}/');open_case(page,f,p);h,stored,posted=lost(page,f,p,'BEGIN');before=snapshot(f);active.terminate();active.wait(5);active=None;active=start_api();assert pids[0]!=pids[1]
   page.reload();assert page.locator('#token').input_value()=='';requests=[];page.on('request',lambda r:requests.append(r.method));open_again(page,f,p);assert page.evaluate('servicePlanRecoveryHandle.key')==h['key'] and page.evaluate('JSON.stringify({...localStorage})')==stored and set(requests)=={'GET'} and snapshot(f)==before and not errors
   assert page.evaluate('servicePlanView.events.at(-1).id')==posted['result']['command_receipt']['id'];OUT.mkdir(parents=True,exist_ok=True);(OUT/'api-restart.json').write_text(json.dumps(dict(different_owned_processes=True,same_origin=True,same_persistent_postgresql=True,unknown_command_get_only=True,duplicate_business_writes=0),indent=2)+'\n')
  finally:
   if active is not None and active.poll() is None:active.terminate();active.wait(5)

def test_not_observed_cold_handle_no_replay_explicit_new_adopt_wins_cas_late_original409(goal_page):
 f,page,errors=goal_page;p=prep(f,'ADOPT');open_case(page,f,p);captured=[];path='/api/preparations/'+p['preparation_id']+'/service-case-plan'
 def delay(route):
  if route.request.method!='POST':route.continue_();return
  captured.append(dict(key=route.request.headers['idempotency-key'],body=route.request.post_data_json));route.abort('failed')
 page.route('**'+path,delay);page.locator('#service-plan-reason').fill('SYNTHETIC PRIVATE_DELAYED_ADOPT');page.locator('#service-plan-adopt').click();page.wait_for_function('()=>servicePlanPending?.stage==="UNCERTAIN"');assert len(captured)==1;stored=page.evaluate('JSON.stringify({...localStorage})');before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_again(page,f,p);assert '未观察到' in page.locator('#service-plan-feedback').inner_text() and page.evaluate('servicePlanView.plan_id') is None and snapshot(f)==before and set(requests)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==stored
 page.unroute('**'+path,delay);page.locator('#service-plan-release').click();page.wait_for_function('()=>servicePlanRecoveryHandle===null&&servicePlanView?.can_adopt');page.locator('#service-plan-reason').fill('SYNTHETIC new explicit adopt');page.locator('#service-plan-adopt').click();page.wait_for_function('()=>servicePlanView?.plan_id&&!servicePlanPending');assert requests.count('POST')==1;committed=snapshot(f)
 # Test sender delivers the original captured request late; the page never replays it.
 original=captured[0];r=page.request.post(page.url.rstrip('/')+path,headers=headers(f[2],key=original['key']),data=original['body']);assert r.status==409 and snapshot(f)==committed;assert recover(f,p,original['key']).json()['status']=='NOT_OBSERVED' and snapshot(f)==committed and not errors

@pytest.mark.parametrize('user,adapter',[('prep-specialist-fixture-a','P1'),('executor-a','P3')])
def test_original_assigned_specialist_and_executor_cold_own_handle_recovery_get_only(goal_page,user,adapter):
 f,page,errors=goal_page;p=setup(f,GOALS[2]);assert adopt(f,p).status_code==201
 if user=='executor-a':accepted(f,p)
 def open_role():
  page.locator('#token').fill(f[2][user]);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadServiceCasePlan(id)',p['preparation_id']);page.wait_for_function('()=>servicePlanView!==null')
 open_role();page.locator('[data-service-adapter="'+adapter+'"] [data-service-action="BEGIN"]').wait_for();captured=[]
 def lose(route):
  if route.request.method!='POST':route.continue_();return
  r=route.fetch();assert r.status==200;captured.append(dict(key=route.request.headers['idempotency-key'],event=r.json()['command_receipt']['id']));route.abort('failed')
 page.route('**/service-case-plan/commands',lose);page.locator('#service-plan-reason').fill('SYNTHETIC PRIVATE_ORIGINAL_ROLE');page.locator('[data-service-adapter="'+adapter+'"] [data-service-action="BEGIN"]').click();page.wait_for_function('()=>servicePlanPending?.stage==="UNCERTAIN"');assert len(captured)==1;stored=page.evaluate('JSON.stringify({...localStorage})');h=json.loads(next(iter(json.loads(stored).values())));assert h['actor']!=read(f,p).json()['actor_ref'] and 'PRIVATE_' not in stored and f[2][user] not in stored;before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_role();wait_recovered(page);assert page.evaluate('servicePlanRecoveryHandle.key')==captured[0]['key'] and page.evaluate('servicePlanView.events.at(-1).id')==captured[0]['event'] and snapshot(f)==before and set(requests)=={'GET'} and 'PRIVATE_ORIGINAL_ROLE' not in page.locator('#service-case-plan-detail').inner_text() and not errors

@pytest.mark.parametrize('target',['identity','case'])
@pytest.mark.parametrize('denied',[False,True])
def test_late_actual_original_post200_or403_keeps_new_context_and_original_cold_handle(goal_page,target,denied):
 f,page,errors=goal_page;p=prep(f,'BEGIN');p2=prep(f,'BEGIN');open_case(page,f,p);held=[]
 def hold(route):
  if route.request.method!='POST':route.continue_();return
  held.append((route,None if denied else route.fetch()))
 page.route('**/service-case-plan/commands',hold);page.locator('#service-plan-reason').fill('SYNTHETIC PRIVATE_LATE_POST');page.locator('[data-service-action="BEGIN"]').click();wait_held(page,held);assert page.evaluate('servicePlanPending.stage')=='SUBMITTING';stored=page.evaluate('JSON.stringify({...localStorage})');assert 'PRIVATE_' not in stored
 if target=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
 else:open_case(page,f,p2)
 page.locator('#page-feedback').evaluate('(e)=>e.textContent="SYNTHETIC NEW_POST_CONTEXT"')
 if denied:
  with f[1].connect() as c:f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
 before=snapshot(f);route,r=held[0]
 if denied:r=route.fetch();assert r.status==403
 else:assert r.status==200
 route.fulfill(response=r);page.wait_for_timeout(150);assert page.locator('#page-feedback').inner_text()=='SYNTHETIC NEW_POST_CONTEXT' and snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==stored and not errors
 if target=='case':assert page.evaluate('servicePlanView.preparation_id')==p2['preparation_id']

@pytest.mark.parametrize('damage',['case','run','action','revision','plan','step'])
def test_cold_handle_metadata_cannot_rebind_original_event_or_enable_writes(goal_page,damage):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,stored,_=lost(page,f,p,'BEGIN');name=next(iter(json.loads(stored)))
 if damage in ('case','run','plan','step'):h[damage]=str(uuid4())
 elif damage=='action':h['action']='REPORT_FAILURE'
 else:h['revision']+=1
 raw=json.dumps(h,separators=(',',':'));page.evaluate('([name,raw])=>localStorage.setItem(name,raw)',[name,raw]);before=snapshot(f);page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadServiceCasePlan(id)',p['preparation_id']);page.wait_for_function('()=>servicePlanRecoveryHandle!==null&&!servicePlanRecoveryChecking');assert not page.evaluate('servicePlanRecoveryHandle.observed||false') and page.evaluate('servicePlanView.read_only') and page.locator('[data-service-action]').count()==0 and set(requests)=={'GET'} and snapshot(f)==before and page.evaluate('(name)=>localStorage.getItem(name)',name)==raw and not errors

def damage_handle(page,h,kind):
 name=page.evaluate('(h)=>servicePlanRecoveryName(h)',h)
 if kind=='expired':page.evaluate('(expiry)=>{window.realRecoveryNow=Date.now;Date.now=()=>expiry+1}',h['expires']);return
 if kind=='missing':page.evaluate('(name)=>localStorage.removeItem(name)',name);return
 if kind=='malformed':page.evaluate('(name)=>localStorage.setItem(name,"SYNTHETIC broken")',name);return
 changed={**h,'key':str(uuid4())};page.evaluate('([name,h])=>localStorage.setItem(name,JSON.stringify(h))',[name,changed])

def assert_handle_refused(page,f,before,draft):
 page.wait_for_function('()=>servicePlanRecoveryHandle===null&&!servicePlanRecoveryChecking&&servicePlanPending===null');assert page.evaluate('servicePlanView.read_only') and page.locator('[data-service-action]').count()==0 and page.locator('#goal-results-read').is_disabled() and page.locator('#service-plan-reason').input_value()==draft and snapshot(f)==before;assert '原提交结果仍待人工核对' in page.locator('#service-plan-feedback').inner_text()

@pytest.mark.parametrize('kind',['expired','missing','malformed','changed'])
@pytest.mark.parametrize('entry',['button','write_guard','release'])
def test_hot_strict_handle_revalidation_before_get_or_release_no_requests(goal_page,kind,entry):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,_,_=lost(page,f,p,'BEGIN')
 if entry=='release':page.locator('#service-plan-retry').click();wait_recovered(page)
 draft='SYNTHETIC new unsent safe draft';page.evaluate('(draft)=>document.getElementById("service-plan-reason").value=draft',draft);damage_handle(page,h,kind);stored=page.evaluate('JSON.stringify({...localStorage})');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append((r.method,r.headers.get('idempotency-key'))))
 if entry=='button':page.locator('#service-plan-retry').click()
 elif entry=='release':page.locator('#service-plan-release').click()
 else:page.evaluate('()=>servicePlanWrite("BEGIN",servicePlanView.steps[0].id)')
 assert_handle_refused(page,f,before,draft);assert requests==[] and not errors
 assert page.evaluate('JSON.stringify({...localStorage})')==(stored if kind=='changed' else '{}')
 # Explicit read is the only transition back to current original plan state.
 if kind!='changed':page.locator('#service-plan-read').click();page.wait_for_function('()=>servicePlanView!==null&&!servicePlanView.read_only');assert page.locator('#service-plan-reason').input_value()==draft and all(m=='GET' for m,k in requests) and snapshot(f)==before

@pytest.mark.parametrize('kind',['expired','missing','malformed','changed'])
@pytest.mark.parametrize('method',['GET','POST'])
def test_real_inflight_recovery_or_original_post_revalidates_handle_before_accepting200(goal_page,kind,method):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);held=[]
 if method=='GET':h,_,_=lost(page,f,p,'BEGIN')
 def hold(route):
  if route.request.method!=method or (method=='GET' and not route.request.headers.get('idempotency-key')):route.continue_();return
  r=route.fetch();assert r.status==200;held.append((route,r))
 page.route('**/service-case-plan/'+('command-recovery' if method=='GET' else 'commands'),hold)
 if method=='GET':page.locator('#service-plan-retry').click()
 else:page.locator('#service-plan-reason').fill('SYNTHETIC PRIVATE_INFLIGHT_POST');page.locator('[data-service-action="BEGIN"]').click()
 wait_held(page,held)
 if method=='POST':h=page.evaluate('servicePlanRecoveryHandle')
 draft='SYNTHETIC keep changed unsent draft';page.evaluate('(draft)=>document.getElementById("service-plan-reason").value=draft',draft);damage_handle(page,h,kind);stored=page.evaluate('JSON.stringify({...localStorage})');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));route,r=held[0];route.fulfill(response=r);assert_handle_refused(page,f,before,draft);assert requests==[] and page.evaluate('JSON.stringify({...localStorage})')==(stored if kind=='changed' else '{}') and not errors
