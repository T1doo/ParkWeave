"""Actual HTTP/PostgreSQL/Chromium opportunities; no mock business store."""
import json,socket,threading,time,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
import pytest,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from parkweave.process_env import minimal_environment
from test_case_opportunities import preparation_fixture,filled,add,body,entry,post,get,imported,business
OUT=Path('.runtime/case-opportunities/browser')

@pytest.fixture
def opportunity_page(preparation_fixture):
 f=preparation_fixture;listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
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
 page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',p['preparation_id']);page.locator('#opp-read').click();page.wait_for_function('()=>oppView!==null&&!oppBusy')
def settled(page):page.wait_for_function('()=>!oppBusy')
def fill_import(page,title='SYNTHETIC browser pending opportunity',note='SYNTHETIC PRIVATE_OPPORTUNITY_NOTE'):
 page.locator('#opportunity-panel details').first.locator('summary').click() if not page.locator('#opp-title').is_visible() else None
 page.locator('#opp-title').fill(title);page.locator('#opp-note').fill(note);page.locator('#opp-purpose').check();page.locator('#opp-reason').fill('SYNTHETIC private explicit reason')
def lose(route):r=route.fetch();assert r.status==200;route.abort('failed')
def unknown_import(f,page,p):
 open_case(page,f,p);fill_import(page);path='**/api/preparations/'+p['preparation_id']+'/opportunities/commands';page.route(path,lose);page.locator('#opp-import-save').click();settled(page);assert page.evaluate('oppHandles().length')==1;return path


def test_full_manual_import_refresh_ignore_dedup_withdraw_new_generation_three_widths(opportunity_page):
 f,page,_=opportunity_page;p=filled(f);open_case(page,f,p);fill_import(page);before=business(f);page.locator('#opp-import-save').click();settled(page);page.wait_for_function('()=>oppView.cards.length===1&&oppHandles().length===0');assert business(f)==before
 add(f,p,text='SYNTHETIC changed material after import');page.locator('#opp-read').click();settled(page);assert not page.evaluate('oppView.cards[0].source_binding_current');page.locator('#opp-reason').fill('SYNTHETIC refresh source');page.locator('#opp-refresh').click();settled(page);assert page.evaluate('oppView.cards[0].source_binding_current')
 page.locator('#opp-reason').fill('SYNTHETIC ignore this generation');page.locator('[data-opp-action="IGNORE"]').click();settled(page);assert page.evaluate('oppView.cards[0].state')=='IGNORED'
 family=page.evaluate('oppView.cards[0].entry.family_id');page.locator('#opp-family').select_option(family);page.locator('#opp-generation').fill('1');fill_import(page);page.locator('#opp-import-save').click();settled(page);assert page.evaluate('oppView.cards.length===1&&oppView.cards[0].state==="IGNORED"')
 page.locator('#opp-reason').fill('SYNTHETIC withdraw this original generation');page.locator('[data-opp-action="WITHDRAW"]').click();settled(page);assert page.evaluate('oppView.cards[0].state')=='WITHDRAWN'
 page.locator('#opp-generation').fill('2');fill_import(page,title='SYNTHETIC revised opportunity',note='SYNTHETIC new explicit source generation');page.locator('#opp-import-save').click();settled(page);assert page.evaluate('oppView.cards.length===2&&oppView.cards[0].state==="WITHDRAWN"&&oppView.cards[1].state==="PENDING_REVIEW"');assert not page.evaluate('oppView.case_goal_completed')
 OUT.mkdir(parents=True,exist_ok=True)
 for width in (1200,390,320):
  page.set_viewport_size({'width':width,'height':950});page.locator('#opportunity-panel').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'full-{width}.png'))

@pytest.mark.parametrize('action',['IMPORT','REFRESH','IGNORE','WITHDRAW'])
def test_lost_reply_cold_refresh_reauth_uses_only_get_opaque_handle(opportunity_page,action):
 f,page,_=opportunity_page;p=filled(f)
 if action!='IMPORT':p,x,e=imported(f,p)
 if action=='REFRESH':add(f,p,text='SYNTHETIC changed original source')
 open_case(page,f,p);path='**/api/preparations/'+p['preparation_id']+'/opportunities/commands';page.route(path,lose)
 if action=='IMPORT':fill_import(page);button='#opp-import-save'
 else:page.locator('#opp-reason').fill('SYNTHETIC PRIVATE_OPPORTUNITY_REASON');button='#opp-refresh' if action=='REFRESH' else '[data-opp-action="'+action+'"]'
 page.locator(button).click();settled(page);assert page.evaluate('oppHandles().length')==1 and page.locator('#opp-import-save').is_disabled();raw=page.evaluate('JSON.stringify({...localStorage})');assert f[2]['fixture-a'] not in raw and 'PRIVATE_OPPORTUNITY' not in raw and 'reason' not in raw and 'sha256' not in raw and 'entry' not in raw
 before=business(f,True);requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_case(page,f,p);page.locator('#opp-recover').click();settled(page);page.wait_for_function('()=>oppHandles().length===0');assert requests and all(m=='GET' for m in requests) and business(f,True)==before

@pytest.mark.parametrize('bad',['corrupt','unknown','overflow','body','revoked'])
def test_bad_or_unknown_storage_and_current_revoke_never_send_post(opportunity_page,bad):
 f,page,_=opportunity_page;p=filled(f)
 if bad=='revoked':p,x,e=imported(f,p);key=e['request_key']
 else:key=str(uuid4())
 # Legacy API keys may be hex; browser-only storage is canonical UUID.
 if bad=='revoked':
  r=post(f,p,body(get(f,p).json(),'REFRESH'),key=str(uuid4()));assert r.status_code==200;key=r.json()['receipt']['request_key']
 open_case(page,f,p);h={'actor':'fixture-a','id':p['preparation_id'],'key':key};name='parkweave.case-opportunity-recovery.v1.fixture-a.'+key
 if bad=='body':h['body']='SYNTHETIC private body'
 entries={name:'{' if bad=='corrupt' else json.dumps(h)}
 if bad=='overflow':
  for _ in range(8):k=str(uuid4());entries['parkweave.case-opportunity-recovery.v1.fixture-a.'+k]=json.dumps({**h,'key':k})
 page.evaluate('(entries)=>{for(const [n,v] of Object.entries(entries))localStorage.setItem(n,v);oppControls();}',entries)
 if bad=='revoked':
  with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
 before=business(f,True);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#opp-recover').click();settled(page);assert 'POST' not in requests and business(f,True)==before and page.evaluate('(n)=>localStorage.getItem(n)!==null',name)
 if bad=='revoked':assert page.locator('#opp-cards').inner_text()=='' and page.locator('#prep-summary').inner_text()==''
 else:assert page.locator('#opp-import-save').is_disabled()

@pytest.mark.parametrize('target',['identity','case','draft'])
def test_late_committed_reply_never_fills_new_identity_case_or_draft(opportunity_page,target):
 f,page,_=opportunity_page;p=filled(f);open_case(page,f,p);fill_import(page);held=[]
 def delay(route):held.append((route,route.fetch()))
 page.route('**/api/preparations/'+p['preparation_id']+'/opportunities/commands',delay);page.locator('#opp-import-save').click();end=time.monotonic()+10
 while not held and time.monotonic()<end:page.wait_for_timeout(20)
 assert held
 if target=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
 elif target=='case':p2=filled(f);page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',p2['preparation_id']);page.locator('#opp-read').click();settled(page)
 else:page.locator('#opp-note').fill('SYNTHETIC new current private draft')
 before=page.locator('#prep-summary').inner_text();cards=page.locator('#opp-cards').inner_text();r,x=held.pop();r.fulfill(response=x);settled(page);page.wait_for_timeout(100);assert page.locator('#prep-summary').inner_text()==before and page.locator('#opp-cards').inner_text()==cards and page.evaluate('oppHandles().length')==1
 if target=='draft':assert page.locator('#opp-note').input_value()=='SYNTHETIC new current private draft'

@pytest.mark.parametrize('bad',['receipt','history','key','actor','case'])
def test_missing_or_wrong_original_proof_retains_unknown_handle(opportunity_page,bad):
 f,page,_=opportunity_page;p=filled(f);unknown_import(f,page,p);path='**/api/preparations/'+p['preparation_id']+'/opportunities/recovery/*'
 def wrong(route):
  r=route.fetch();x=r.json()
  if bad=='receipt':x.pop('receipt')
  elif bad=='history':x['current']['history']=[]
  elif bad=='key':x['receipt']['request_key']=str(uuid4())
  elif bad=='actor':x['current']['actor_id']='fixture-b'
  else:x['case_id']=str(uuid4());x['current']['case_id']=x['case_id']
  route.fulfill(status=200,content_type='application/json',body=json.dumps(x))
 page.route(path,wrong);before=business(f,True);page.locator('#opp-recover').click();settled(page);assert page.evaluate('oppHandles().length')==1 and business(f,True)==before and page.locator('#opp-import-save').is_disabled();page.unroute(path);page.locator('#opp-recover').click();settled(page);page.wait_for_function('()=>oppHandles().length===0');assert business(f,True)==before


def test_late_recovery_or_denial_preserves_new_draft_and_original_handle(opportunity_page):
 f,page,_=opportunity_page;p=filled(f);unknown_import(f,page,p);held=[];path='**/api/preparations/'+p['preparation_id']+'/opportunities/recovery/*'
 def delay(route):held.append(route)
 page.route(path,delay);page.locator('#opp-recover').click();end=time.monotonic()+10
 while not held and time.monotonic()<end:page.wait_for_timeout(20)
 assert held;page.locator('#opp-note').fill('SYNTHETIC different current draft');before=page.locator('#prep-summary').inner_text();held.pop().fulfill(status=403,content_type='application/json',body='{"detail":"SYNTHETIC original denial"}');settled(page);page.wait_for_timeout(100);assert page.locator('#prep-summary').inner_text()==before and page.locator('#opp-note').input_value()=='SYNTHETIC different current draft' and page.evaluate('oppHandles().length')==1


def test_storage_failure_prevents_post_and_lost_refusal_stays_unknown(opportunity_page):
 f,page,_=opportunity_page;p=filled(f);open_case(page,f,p);fill_import(page);requests=[];page.on('request',lambda r:requests.append(r.method));before=business(f,True)
 page.evaluate("()=>{window.oppOriginalSet=Storage.prototype.setItem;Storage.prototype.setItem=function(n,v){if(n.startsWith(oppStorage))throw new DOMException('synthetic quota','QuotaExceededError');return window.oppOriginalSet.call(this,n,v);};}")
 page.locator('#opp-import-save').click();settled(page);assert 'POST' not in requests and business(f,True)==before
 page.evaluate('()=>Storage.prototype.setItem=window.oppOriginalSet');add(f,p,text='SYNTHETIC actual source changed before request')
 def refused(route):r=route.fetch();assert r.status==409;route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/opportunities/commands',refused);page.locator('#opp-import-save').click();settled(page);assert page.evaluate('oppHandles().length')==1;before=business(f,True);page.locator('#opp-recover').click();settled(page);assert page.evaluate('oppHandles().length')==1 and business(f,True)==before


def test_owned_api_process_restart_same_pg_get_only_recovers_original_import(opportunity_page,tmp_path):
 f,page,_=opportunity_page;p=filled(f);active=None;pids=[]
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PYTHONPATH=str(Path.cwd()/'src'));cmd=[sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log']
 with (tmp_path/'owned-api.log').open('w') as log:
  def start():
   proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=log);pids.append(proc.pid);end=time.monotonic()+10
   while proc.poll() is None and time.monotonic()<end:
    try:
     r=page.request.get(f'http://127.0.0.1:{port}/health',timeout=500)
     if r.ok and r.json()['process_id']==proc.pid:return proc
    except Exception:pass
    time.sleep(.05)
   proc.terminate();proc.wait(5);raise AssertionError('owned API readiness deadline')
  try:
   active=start();page.goto(f'http://127.0.0.1:{port}/');unknown_import(f,page,p);active.terminate();active.wait(5);active=None;active=start();assert pids[0]!=pids[1];page.reload();open_case(page,f,p);before=business(f,True);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#opp-recover').click();settled(page);page.wait_for_function('()=>oppHandles().length===0');assert requests and all(m=='GET' for m in requests) and business(f,True)==before
   OUT.mkdir(parents=True,exist_ok=True);(OUT/'api-restart.json').write_text(json.dumps({'different_owned_processes':True,'same_persistent_postgresql_history':True,'recovery_get_only':True,'duplicate_effects':0},indent=2)+'\n')
  finally:
   if active is not None and active.poll() is None:active.terminate();active.wait(5)


def test_imported_html_and_script_are_literal_text_without_dom_execution(opportunity_page):
 f,page,_=opportunity_page;p=filled(f);open_case(page,f,p);payload='<img src=x onerror="window.opportunityInjected=true">';fill_import(page,title='SYNTHETIC '+payload,note='<script>window.opportunityInjected=true</script> SYNTHETIC literal source');page.locator('#opp-import-save').click();settled(page);page.wait_for_function('()=>oppHandles().length===0');assert payload in page.locator('#opp-cards').inner_text() and page.locator('#opp-cards img,#opp-cards script').count()==0 and page.evaluate('window.opportunityInjected') is None
