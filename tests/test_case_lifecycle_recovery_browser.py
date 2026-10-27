"""Cold unknown local Case commands over actual HTTP, Chromium and PostgreSQL."""
import json,hashlib,socket,threading,time,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
import pytest,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from parkweave.process_env import minimal_environment
from test_case_lifecycle_recovery import snapshot,recover
from test_case_lifecycle import built,closed,read,act,counts
from test_case_resources import link_fixture
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture

OUT=Path('.runtime/lifecycle-recovery/browser')
@pytest.fixture
def lifecycle_page(link_fixture):
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


def open_case(page,f,p,user='fixture-a'):
 page.locator('#token').fill(f[2][user]);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadLocalCase(id)',p['preparation_id']);page.wait_for_function('()=>localCaseView!==null')


def settled(page):page.wait_for_function('()=>!localCaseRecoveryBusy')
def lose(route):
 response=route.fetch();assert response.status==200;route.abort('failed')


@pytest.mark.parametrize('action',['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN'])
def test_true_three_actions_and_exact_get_receipts_at_three_widths(lifecycle_page,action):
 f,page,_=lifecycle_page
 if action=='REOPEN':p,g,d,s,row=closed(f)
 else:
  p,g,d,s=built(f)
  if action=='CLOSE_LOCAL_RECORD':assert act(f,p,read(f,p).json(),'REVALIDATE').status_code==200
 open_case(page,f,p);prior=counts(f);page.locator('#local-case-reason').fill('SYNTHETIC PRIVATE_LIFECYCLE_REASON <script>private</script>')
 button={'REVALIDATE':'#local-case-validate','CLOSE_LOCAL_RECORD':'#local-case-close','REOPEN':'#local-case-reopen'}[action];page.locator(button).click();settled(page);page.wait_for_function('()=>localCaseHandles().length===0');assert counts(f)[1]==prior[1]+1
 assert '原' in page.locator('#local-case-recovery-status').inner_text() and not page.evaluate('localCaseView.case_goal_completed')
 OUT.mkdir(parents=True,exist_ok=True)
 for width in (1200,390,320):
  page.set_viewport_size({'width':width,'height':950});page.locator('#local-case-detail').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'{action}-{width}.png'))


@pytest.mark.parametrize('action',['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN'])
def test_committed_lost_reply_cold_refresh_uses_get_only_and_opaque_storage(lifecycle_page,action):
 f,page,_=lifecycle_page
 if action=='REOPEN':p,g,d,s,row=closed(f)
 else:
  p,g,d,s=built(f)
  if action=='CLOSE_LOCAL_RECORD':assert act(f,p,read(f,p).json(),'REVALIDATE').status_code==200
 open_case(page,f,p);page.locator('#local-case-reason').fill('SYNTHETIC PRIVATE_LIFECYCLE_REASON');path='**/api/preparations/'+p['preparation_id']+'/local-case/commands';page.route(path,lose)
 button={'REVALIDATE':'#local-case-validate','CLOSE_LOCAL_RECORD':'#local-case-close','REOPEN':'#local-case-reopen'}[action];page.locator(button).click();settled(page)
 assert page.evaluate('localCaseHandles().length')==1
 for bid in ('local-case-validate','local-case-close','local-case-reopen'):assert page.locator('#'+bid).is_disabled()
 raw=page.evaluate('JSON.stringify({...localStorage})');assert f[2]['fixture-a'] not in raw and 'PRIVATE_LIFECYCLE_REASON' not in raw and 'action' not in raw and 'sha256' not in raw
 before=snapshot(f);requests=[];page.on('request',lambda r:requests.append((r.method,r.url)));page.reload();open_case(page,f,p);page.locator('#local-case-recover').click();settled(page);page.wait_for_function('()=>localCaseHandles().length===0');assert all(m=='GET' for m,u in requests) and snapshot(f)==before


@pytest.mark.parametrize('bad',['corrupt','not-observed','id-array','extra-body','overflow','revoked'])
def test_unknown_or_bad_handles_never_send_post_or_disclose_revoked_private_view(lifecycle_page,bad):
 f,page,_=lifecycle_page;p,g,d,s=built(f);open_case(page,f,p);key=str(uuid4());name='parkweave.local-case-recovery.v1.fixture-a.'+key;h={'actor':'fixture-a','id':p['preparation_id'],'key':key}
 if bad=='id-array':h['id']=[h['id']]
 if bad=='extra-body':h['body']='PRIVATE_LIFECYCLE_REASON'
 if bad=='revoked':
  assert act(f,p,read(f,p).json(),'REVALIDATE',key=key).status_code==200
  with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
 entries={name:'{' if bad=='corrupt' else json.dumps(h)}
 if bad=='overflow':
  for _ in range(8):k=str(uuid4());entries['parkweave.local-case-recovery.v1.fixture-a.'+k]=json.dumps({**h,'key':k})
 page.evaluate('(entries)=>{for(const [n,v] of Object.entries(entries))localStorage.setItem(n,v);localCaseRecoveryControls();}',entries)
 before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#local-case-recover').click();settled(page)
 assert page.evaluate('(name)=>localStorage.getItem(name)!==null',name) and snapshot(f)==before and 'POST' not in requests
 if bad=='revoked':assert page.locator('#local-case-summary').inner_text()=='' and page.locator('#local-case-history').inner_text()==''
 else:assert page.locator('#local-case-validate').is_disabled()


@pytest.mark.parametrize('target',['identity','case','draft'])
def test_late_success_keeps_original_handle_without_filling_new_private_view(lifecycle_page,target):
 f,page,_=lifecycle_page;p,g,d,s=built(f);open_case(page,f,p);page.locator('#local-case-reason').fill('SYNTHETIC private original');responses=[]
 def delay(route):responses.append((route,route.fetch()))
 page.route('**/api/preparations/'+p['preparation_id']+'/local-case/commands',delay);page.locator('#local-case-validate').click()
 end=time.monotonic()+10
 while not responses and time.monotonic()<end:page.wait_for_timeout(20)
 assert responses
 if target=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
 elif target=='case':page.evaluate('()=>clearLocalCase()')
 else:page.locator('#local-case-reason').fill('SYNTHETIC different draft')
 before=page.locator('#local-case-summary').inner_text();route,response=responses.pop();route.fulfill(response=response);settled(page);page.wait_for_timeout(100)
 assert page.locator('#local-case-summary').inner_text()==before and page.evaluate('localCaseHandles().length')==1
 if target=='draft':assert page.locator('#local-case-reason').input_value()=='SYNTHETIC different draft'


def test_refused_reply_lost_does_not_retry_post(lifecycle_page):
 f,page,_=lifecycle_page;p,g,d,s=built(f);open_case(page,f,p);page.locator('#local-case-reason').fill('SYNTHETIC stale source')
 with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET revision=revision+1')
 def lose_refusal(route):response=route.fetch();assert response.status==409;route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/local-case/commands',lose_refusal);page.locator('#local-case-validate').click();settled(page);assert counts(f)==[0,0] and page.evaluate('localCaseHandles().length')==1
 page.locator('#local-case-recover').click();settled(page);assert page.evaluate('localCaseHandles().length')==1 and counts(f)==[0,0]


def test_owned_api_process_restart_recovers_original_event_with_get_only(lifecycle_page,tmp_path):
 f,page,_=lifecycle_page;p,g,d,s=built(f);pids=[];active=None
 with socket.socket() as reserved:reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
 env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PYTHONPATH=str(Path.cwd()/'src'))
 commands=[sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log']
 with (tmp_path/'owned-api.log').open('w') as log:
  def start():
   proc=subprocess.Popen(commands,env=env,stdout=log,stderr=log);pids.append(proc.pid);end=time.monotonic()+10
   while proc.poll() is None and time.monotonic()<end:
    try:
     r=page.request.get(f'http://127.0.0.1:{port}/health',timeout=500)
     if r.ok and r.json()['process_id']==proc.pid:return proc
    except Exception:pass
    time.sleep(.05)
   proc.terminate();proc.wait(5);raise AssertionError('owned API readiness deadline')
  try:
   active=start();page.goto(f'http://127.0.0.1:{port}/');open_case(page,f,p);page.locator('#local-case-reason').fill('SYNTHETIC cold API event');page.route('**/api/preparations/'+p['preparation_id']+'/local-case/commands',lose);page.locator('#local-case-validate').click();settled(page);assert counts(f)==[1,1]
   active.terminate();active.wait(5);active=None;active=start();assert pids[0]!=pids[1];page.reload();open_case(page,f,p);requests=[];page.on('request',lambda r:requests.append(r.method));before=snapshot(f);page.locator('#local-case-recover').click();settled(page);page.wait_for_function('()=>localCaseHandles().length===0');assert requests and all(m=='GET' for m in requests) and snapshot(f)==before
   OUT.mkdir(parents=True,exist_ok=True);(OUT/'api-restart.json').write_text(json.dumps({'different_owned_processes':True,'same_persistent_postgresql_history':True,'recovery_get_only':True,'duplicate_effects':0},indent=2)+'\n')
  finally:
   if active is not None and active.poll() is None:active.terminate();active.wait(5)


def test_storage_failure_blocks_post_and_recovered_action_restores_current_controls(lifecycle_page):
 f,page,_=lifecycle_page;p,g,d,s=built(f);open_case(page,f,p);page.locator('#local-case-reason').fill('SYNTHETIC explicit reason');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method))
 page.evaluate("()=>{window.savedCaseSet=Storage.prototype.setItem;Storage.prototype.setItem=function(n,v){if(n.startsWith(localCaseStorage))throw new DOMException('synthetic quota','QuotaExceededError');return window.savedCaseSet.call(this,n,v);};}")
 page.locator('#local-case-validate').click();settled(page);assert 'POST' not in requests and snapshot(f)==before and page.locator('#local-case-validate').is_enabled()
 page.evaluate('()=>{Storage.prototype.setItem=window.savedCaseSet;}');page.locator('#local-case-validate').click();settled(page);page.wait_for_function('()=>localCaseHandles().length===0');assert page.locator('#local-case-close').is_enabled() and page.locator('#local-case-reopen').is_disabled();assert page.locator('#local-case-validate').is_enabled()==page.evaluate('()=>localCaseView.can_revalidate')


def test_bad_recovery_scope_preserves_original_handle_and_no_new_post(lifecycle_page):
 f,page,_=lifecycle_page;p,g,d,s=built(f);open_case(page,f,p);page.locator('#local-case-reason').fill('SYNTHETIC exact original');post='**/api/preparations/'+p['preparation_id']+'/local-case/commands';get='**/api/preparations/'+p['preparation_id']+'/local-case/recovery/*';page.route(post,lose);page.locator('#local-case-validate').click();settled(page);assert page.evaluate('localCaseHandles().length')==1
 def wrong_scope(route):response=route.fetch();body=response.json();body['case_id']=str(uuid4());body['current']['case_id']=body['case_id'];route.fulfill(status=200,content_type='application/json',body=json.dumps(body))
 page.route(get,wrong_scope);before=snapshot(f);page.locator('#local-case-recover').click();settled(page);assert page.evaluate('localCaseHandles().length')==1 and snapshot(f)==before
 page.unroute(get);page.locator('#local-case-recover').click();settled(page);page.wait_for_function('()=>localCaseHandles().length===0');assert snapshot(f)==before


def test_late_denial_does_not_clear_new_case_private_view(lifecycle_page):
 f,page,_=lifecycle_page;p,g,d,s=built(f);open_case(page,f,p);page.locator('#local-case-reason').fill('SYNTHETIC original action');held=[]
 def reject(route):held.append(route)
 page.route('**/api/preparations/'+p['preparation_id']+'/local-case/commands',reject);page.locator('#local-case-validate').click()
 end=time.monotonic()+5
 while not held and time.monotonic()<end:page.wait_for_timeout(20)
 assert held;page.locator('#local-case-reason').fill('SYNTHETIC current draft');before=page.locator('#local-case-summary').inner_text();held.pop().fulfill(status=403,content_type='application/json',body='{"detail":"SYNTHETIC original request denied"}');settled(page);page.wait_for_timeout(100)
 assert page.locator('#local-case-summary').inner_text()==before and page.locator('#local-case-reason').input_value()=='SYNTHETIC current draft' and page.evaluate('localCaseHandles().length')==1 and counts(f)==[0,0]
