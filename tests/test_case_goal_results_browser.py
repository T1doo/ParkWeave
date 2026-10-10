"""Actual HTTP/PostgreSQL/Chromium for owner-only goal output evidence."""
import json,os,socket,subprocess,sys,threading,time
from pathlib import Path
from uuid import uuid4
import pytest,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from parkweave.process_env import minimal_environment
from test_case_goal_results import link_fixture,receipt_fixture,preparation_fixture,start,complete,snapshot,get,GOALS,verified,save
OUT=Path('.runtime/case-goal-results/browser')

@pytest.fixture
def goal_page(link_fixture):
 f=link_fixture;listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
 server=uvicorn.Server(uvicorn.Config(create_app(f[0]),host='127.0.0.1',port=port,log_level='warning',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
 try:
  end=time.monotonic()+10
  while not server.started and thread.is_alive() and time.monotonic()<end:time.sleep(.02)
  assert server.started
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(f'http://127.0.0.1:{port}/')
   try:yield f,page,errors
   finally:context.close();browser.close()
  assert not errors,errors
 finally:server.should_exit=True;thread.join(10);listener.close();assert not thread.is_alive()

def open_case(page,f,p):
 page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadServiceCasePlan(id)',p['preparation_id']);page.wait_for_function('()=>servicePlanView!==null');assert page.locator('#goal-results-panel').is_visible()
def settle(page):page.wait_for_function('()=>!document.getElementById("goal-results-read").disabled')
def read_page(page):page.locator('#goal-results-read').click();settle(page);page.wait_for_function('()=>goalResultView!==null')
def wait_held(page,held):
 end=time.monotonic()+10
 while not held and time.monotonic()<end:page.wait_for_timeout(20)
 assert held

def test_full_original_multi_output_read_cold_page_three_widths_and_privacy(goal_page):
 f,page,_=goal_page;p,g,d,s=complete(f,local=True);open_case(page,f,p);before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));read_page(page)
 assert page.locator('[data-goal-state="LOCAL_OUTPUT_VERIFIED"]').count()==5
 x=page.evaluate('goalResultView');assert x==get(f,p).json();assert x['results'][3]['actual_output']['receipt_id']==s['current_receipt']['id'];assert 'PRIVATE_GOAL_RECEIPT' not in page.locator('#goal-results-items').inner_text()
 assert '原Case全部履约' in page.locator('#goal-results-status').inner_text();assert requests and set(requests)=={'GET'} and snapshot(f)==before
 OUT.mkdir(parents=True,exist_ok=True)
 for width in (1200,390,320):
  page.set_viewport_size({'width':width,'height':1000});page.locator('#goal-results-panel').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'goals-{width}.png'))
 before=snapshot(f);requests.clear();page.reload();open_case(page,f,p);read_page(page);assert page.evaluate('goalResultView')==x and set(requests)=={'GET'} and snapshot(f)==before
 assert page.evaluate('JSON.stringify({...localStorage})')=='{}'

def test_only_original_explicit_verify_changes_result_and_navigation_is_original_get(goal_page):
 f,page,_=goal_page;p=start(f);open_case(page,f,p);before=snapshot(f);read_page(page);assert page.locator('[data-goal-state="AWAITING_OWNER_VERIFICATION"]').count()==1 and snapshot(f)==before
 page.locator('#service-plan-reason').fill('SYNTHETIC original explicit owner verification');page.locator('[data-service-action="VERIFY"]').first.click();page.wait_for_function('()=>servicePlanPending===null&&servicePlanView.steps[0].state==="VERIFIED"');read_page(page);assert page.locator('[data-goal-state="LOCAL_OUTPUT_VERIFIED"]').count()==1
 before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#goal-results-items button').click();page.wait_for_function('()=>preparationView!==null');assert requests and set(requests)=={'GET'} and snapshot(f)==before

def test_unsupported_current_goal_is_literal_text_and_original_goal_remains_history(goal_page):
 f,page,_=goal_page;p=start(f);verified(f,p,'P1');goal='<img src=x onerror="window.GOAL_XSS=1">';assert save(f,p,goals=[GOALS[0],goal]).status_code==200;open_case(page,f,p);before=snapshot(f);read_page(page)
 assert page.locator('[data-goal-state="UNSUPPORTED"]').count()==1 and goal in page.locator('#goal-results-items').inner_text();assert page.locator('#goal-results-items img,#goal-results-items script').count()==0 and not page.evaluate('window.GOAL_XSS||false');assert '原采用目标仍保留为历史' in page.locator('#goal-results-items').inner_text();assert snapshot(f)==before

@pytest.mark.parametrize('target',['identity','case','draft','plan'])
@pytest.mark.parametrize('denied',[False,True])
def test_late_actual_get_or_denial_preserves_new_identity_case_draft_or_plan(goal_page,target,denied):
 f,page,_=goal_page;p=start(f);open_case(page,f,p);held=[]
 def delay(route):held.append((route,route.fetch()))
 path='**/api/preparations/'+p['preparation_id']+'/goal-results';page.route(path,delay);page.locator('#goal-results-read').click();wait_held(page,held)
 if target=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
 elif target=='case':p2=start(f);open_case(page,f,p2)
 elif target=='plan':verified(f,p,'P1');page.evaluate('(id)=>loadServiceCasePlan(id)',p['preparation_id']);page.wait_for_function('()=>servicePlanView.steps[0].state==="VERIFIED"')
 else:page.locator('#service-plan-reason').fill('SYNTHETIC newer draft')
 page.locator('#goal-results-status').evaluate('(e)=>e.textContent="SYNTHETIC NEW_CONTEXT"');before=snapshot(f);route,r=held[0]
 if denied:route.fulfill(status=403,json={'detail':'SYNTHETIC prior denial'})
 else:route.fulfill(response=r)
 page.wait_for_timeout(150);assert page.locator('#goal-results-status').inner_text()=='SYNTHETIC NEW_CONTEXT' and page.evaluate('goalResultView') is None and snapshot(f)==before
 if target=='draft':assert page.locator('#service-plan-reason').input_value()=='SYNTHETIC newer draft';settle(page)

def test_late_first_reader_cannot_replace_newer_read(goal_page):
 f,page,_=goal_page;p=start(f);open_case(page,f,p);held=[];path='**/api/preparations/'+p['preparation_id']+'/goal-results'
 def delay(route):
  response=route.fetch()
  if not held:held.append((route,response))
  else:route.fulfill(response=response)
 page.route(path,delay);page.locator('#goal-results-read').click();wait_held(page,held);page.evaluate('()=>readGoalResults()');settle(page);page.wait_for_function('()=>goalResultView!==null');current=page.evaluate('goalResultView');before=snapshot(f)
 held[0][0].fulfill(status=403,json={'detail':'SYNTHETIC old reader denial'});page.wait_for_timeout(150);assert page.evaluate('goalResultView')==current and snapshot(f)==before

def test_current_actual_revoke_clears_private_result_and_original_views(goal_page):
 f,page,_=goal_page;p=start(f);verified(f,p,'P1');open_case(page,f,p);read_page(page)
 with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
 before=snapshot(f);page.locator('#goal-results-read').click();page.wait_for_function('()=>goalResultView===null&&servicePlanView===null');assert page.locator('#goal-results-items').inner_text()=='' and page.locator('#goal-results-panel').is_hidden() and '访问权已失效' in page.locator('#page-feedback').inner_text();assert snapshot(f)==before

@pytest.mark.parametrize('bad',['case_id','run_id','plan_id','plan_revision','preparation_revision','request_revision','scope','read_only','case_goal_completed'])
def test_mismatched_response_never_displays_current_result(goal_page,bad):
 f,page,_=goal_page;p=start(f);open_case(page,f,p);x=get(f,p).json()
 if bad.endswith('revision'):x[bad]+=1
 elif bad=='read_only':x[bad]=False
 elif bad=='case_goal_completed':x[bad]=True
 else:x[bad]=str(uuid4())
 page.route('**/api/preparations/'+p['preparation_id']+'/goal-results',lambda r:r.fulfill(status=200,json=x));before=snapshot(f);page.locator('#goal-results-read').click();settle(page);assert page.evaluate('goalResultView') is None and page.locator('#goal-results-items').inner_text()=='' and '不匹配' in page.locator('#goal-results-error').inner_text() and snapshot(f)==before

def test_owned_api_process_restart_same_pg_recovers_output_references_with_get_only(goal_page,tmp_path):
 f,page,_=goal_page;p,g,d,s=complete(f);active=None;pids=[]
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
   active=start_api();page.goto(f'http://127.0.0.1:{port}/');open_case(page,f,p);read_page(page);original=page.evaluate('goalResultView');active.terminate();active.wait(5);active=None;active=start_api();assert pids[0]!=pids[1]
   page.reload();open_case(page,f,p);before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));read_page(page);assert page.evaluate('goalResultView')==original and set(requests)=={'GET'} and snapshot(f)==before
   OUT.mkdir(parents=True,exist_ok=True);(OUT/'api-restart.json').write_text(json.dumps(dict(different_owned_processes=True,same_persistent_postgresql=True,goal_result_reads_get_only=True,duplicate_business_writes=0),indent=2)+'\n')
  finally:
   if active is not None and active.poll() is None:active.terminate();active.wait(5)
