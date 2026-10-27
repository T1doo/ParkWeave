"""Owned HTTP/PG/Chromium, actual Case source bundle operations and cold recovery."""
import json,socket,threading,time,os,subprocess,sys
from pathlib import Path
from uuid import uuid4
import pytest,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from parkweave.process_env import minimal_environment
from test_case_fact_bundle import preparation_fixture,setup,get,command,body,document,period,register,choose,snapshot,recover
OUT=Path('.runtime/case-fact-bundle/browser')

@pytest.fixture
def bundle_page(preparation_fixture):
 f=preparation_fixture;listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1];server=uvicorn.Server(uvicorn.Config(create_app(f[0]),host='127.0.0.1',port=port,log_level='warning',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
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
 page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',p['preparation_id']);page.locator('#fb-read').click();page.wait_for_function('()=>fbView!==null&&!fbBusy')
def settled(page):page.wait_for_function('()=>!fbBusy')
def fill_source(page,kind='REGISTER_DOCUMENT',field='region',value='地区甲'):
 page.locator('#fb-kind').select_option(kind);page.locator('#fb-field').select_option(field)
 if kind=='REGISTER_DOCUMENT':page.locator('#fb-quote').fill(value)
 else:page.locator('#fb-value').fill(value);page.locator('#fb-note').fill('SYNTHETIC PRIVATE_BROWSER_ASSUMPTION')
 p=period();page.locator('#fb-from').fill(p['valid_from']);page.locator('#fb-until').fill(p['valid_until']);page.locator('#fb-purpose').check();page.locator('#fb-reason').fill('SYNTHETIC PRIVATE_BROWSER_REASON')
def unknown(f,page,p,action='REGISTER_DOCUMENT'):
 open_case(page,f,p);fill_source(page,action);path='**/api/preparations/'+p['preparation_id']+'/fact-bundle/commands'
 def lose(route):r=route.fetch();assert r.status==200;route.abort('failed')
 page.route(path,lose);page.locator('#fb-save').click();settled(page);assert page.evaluate('fbHandles().length')==1;return path

def test_full_real_browser_document_to_original_choice_lock_conflict_unlock_withdraw_three_widths(bundle_page):
 f,page,_=bundle_page;p=setup(f);open_case(page,f,p);fill_source(page);page.locator('#fb-save').click();settled(page);page.wait_for_function('()=>fbView.entries.length===1&&fbHandles().length===0');e=page.evaluate('fbView.entries[0]');assert e['source']['value']=='地区甲';assert '资料摘录' in page.locator('#fb-entries').inner_text()
 page.locator('#prep-refresh').click();page.wait_for_function('()=>caseFactView!==null');selectors=page.locator('#case-fact-fields select[data-fact-field]')
 for field in ('region','employees','service_need'):
  value=e['id'] if field=='region' else next(x['id'] for x in page.evaluate('caseFactView.sources') if x['field_name']==field);page.locator('select[data-fact-field="'+field+'"]').select_option(value)
 page.locator('#case-fact-purpose').check();page.locator('#case-fact-confirm-reason').fill('SYNTHETIC explicit selected document for Case');page.locator('#case-fact-confirm').click();page.wait_for_function('()=>caseFactPending===null&&caseFactView?.state==="CURRENT"');page.locator('#material-draft-read').click();page.wait_for_function('()=>materialDraftView!==null&&!materialDraftLoading');assert page.locator('#material-draft-form').is_hidden() and '仅限本人' in page.locator('#material-draft-status').inner_text() and 'OWNER_CASE_ONLY' not in page.locator('#material-draft-error').inner_text();page.locator('#fb-read').click();settled(page);page.locator('#fb-reason').fill('SYNTHETIC preserve explicit source choice');page.locator('[data-fb-action="LOCK"]').first.click();settled(page);assert page.evaluate('!!fbView.locks.region')
 page.locator('#fb-reason').fill('SYNTHETIC withdrawal before unlock');page.locator('[data-fb-action="WITHDRAW"]').click();settled(page);assert '人工锁' in page.locator('#fb-error').inner_text();assert page.evaluate('fbView.entries[0].active')
 page.locator('#fb-reason').fill('SYNTHETIC explicit unlock');page.locator('[data-fb-action="UNLOCK"]').click();settled(page);assert not page.evaluate('fbView.locks.region');page.locator('#fb-reason').fill('SYNTHETIC preserve historical source');page.locator('[data-fb-action="WITHDRAW"]').click();settled(page);assert page.evaluate('fbView.entries[0].active===false&&fbHandles().length===0')
 page.locator('#prep-refresh').click();page.wait_for_function('()=>caseFactView!==null');page.locator('#fb-read').click();settled(page);fill_source(page,'REGISTER_ASSUMPTION','employees','999');page.locator('#fb-save').click();settled(page);assert page.evaluate('fbView.entries[1].state==="UNKNOWN"&&!fbView.entries[1].eligible_for_case_selection')
 OUT.mkdir(parents=True,exist_ok=True)
 for width in (1200,390,320):
  page.set_viewport_size({'width':width,'height':1000});page.locator('#fact-bundle-panel').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'full-{width}.png'))

@pytest.mark.parametrize('action',['REGISTER_DOCUMENT','REGISTER_ASSUMPTION','WITHDRAW','LOCK','UNLOCK'])
def test_lost_post_cold_refresh_reauth_only_get_exact_historical_recovery(bundle_page,action):
 f,page,_=bundle_page;p=setup(f)
 if action in ('WITHDRAW','LOCK','UNLOCK'):
  v,e=register(f,p)
 if action in ('LOCK','UNLOCK'):
  v=get(f,p).json();selected={x['field_name']:x['id'] for x in v['asserted_sources']};selected['region']=e['id'];assert choose(f,p,selected).status_code==200
 if action=='UNLOCK':
  v=get(f,p).json();assert command(f,p,body(v,'LOCK',field='region',assertion_id=e['id'],assertion_revision=1,assertion_fingerprint=e['fingerprint'])).status_code==200
 open_case(page,f,p);path='**/api/preparations/'+p['preparation_id']+'/fact-bundle/commands'
 def lose(route):r=route.fetch();assert r.status==200;route.abort('failed')
 page.route(path,lose)
 if action.startswith('REGISTER_'):fill_source(page,action);button='#fb-save'
 else:page.locator('#fb-reason').fill('SYNTHETIC PRIVATE_BROWSER_REASON');button='[data-fb-action="'+action+'"]'
 page.locator(button).first.click();settled(page);assert page.evaluate('fbHandles().length')==1 and page.locator('#fb-save').is_disabled();raw=page.evaluate('JSON.stringify({...localStorage})');assert f[2]['fixture-a'] not in raw and all(s not in raw for s in ('PRIVATE_BROWSER','source_sha256','reason','note','body'))
 before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_case(page,f,p);page.locator('#fb-recover').click();settled(page);page.wait_for_function('()=>fbHandles().length===0');assert requests and all(x=='GET' for x in requests) and snapshot(f)==before

@pytest.mark.parametrize('bad',['corrupt','extra-body','overflow','unknown','revoked'])
def test_storage_or_current_revoke_keeps_handle_and_never_post(bundle_page,bad):
 f,page,_=bundle_page;p=setup(f);open_case(page,f,p);key=str(uuid4());name='parkweave.case-fact-bundle-recovery.v1.fixture-a.'+key;h=dict(actor='fixture-a',id=p['preparation_id'],key=key);x={name:'{' if bad=='corrupt' else json.dumps(h|({'body':'SYNTHETIC PRIVATE'} if bad=='extra-body' else {}))}
 if bad=='overflow':
  for _ in range(8):k=str(uuid4());x['parkweave.case-fact-bundle-recovery.v1.fixture-a.'+k]=json.dumps(h|dict(key=k))
 page.evaluate('(x)=>{for(const [n,v] of Object.entries(x))localStorage.setItem(n,v);fbControls();}',x)
 if bad=='revoked':
  with f[1].connect() as c:c.execute("UPDATE field_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND field_name='region' AND capability='READ'")
 before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#fb-recover').click();settled(page);assert 'POST' not in requests and snapshot(f)==before;assert page.evaluate('(n)=>localStorage.getItem(n)!==null',name)
 if bad=='revoked':assert page.locator('#fb-entries').inner_text()=='' and page.locator('#prep-summary').inner_text()=='' and '原句柄保留' in page.locator('#page-feedback').inner_text()
 else:assert page.locator('#fb-save').is_disabled()

@pytest.mark.parametrize('target',['identity','case','draft'])
def test_late_post_success_preserves_new_context_or_draft_and_opaque_handle(bundle_page,target):
 f,page,_=bundle_page;p=setup(f);open_case(page,f,p);fill_source(page);held=[]
 def delay(route):held.append((route,route.fetch()))
 page.route('**/api/preparations/'+p['preparation_id']+'/fact-bundle/commands',delay);page.locator('#fb-save').click();end=time.monotonic()+10
 while not held and time.monotonic()<end:page.wait_for_timeout(20)
 assert held
 if target=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input');page.locator('#fb-status').evaluate('(e)=>e.textContent="SYNTHETIC NEW_IDENTITY"')
 elif target=='case':p2=setup(f);page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',p2['preparation_id']);page.locator('#fb-read').click();settled(page);page.locator('#fb-status').evaluate('(e)=>e.textContent="SYNTHETIC NEW_CASE"')
 else:page.locator('#fb-reason').fill('SYNTHETIC NEW_DRAFT')
 route,r=held[0];route.fulfill(response=r);page.wait_for_timeout(150);assert page.evaluate('fbHandles().length')==1
 if target=='draft':assert page.locator('#fb-reason').input_value()=='SYNTHETIC NEW_DRAFT'
 else:assert 'SYNTHETIC NEW_' in page.locator('#fb-status').inner_text()

@pytest.mark.parametrize('bad',['receipt','history','key','actor','case'])
def test_forged_recovery_never_discards_unknown_handle(bundle_page,bad):
 f,page,_=bundle_page;p=setup(f);path=unknown(f,page,p);page.unroute(path);h=page.evaluate('fbHandles()[0]');real=recover(f,p,h['key']).json();fake=json.loads(json.dumps(real))
 if bad=='receipt':fake.pop('receipt')
 elif bad=='history':fake['current']['history']=[]
 elif bad=='key':fake['receipt']['request_key']=str(uuid4())
 elif bad=='actor':fake['actor_id']='fixture-b'
 else:fake['case_id']=str(uuid4())
 page.route('**/api/preparations/'+p['preparation_id']+'/fact-bundle/recovery/*',lambda r:r.fulfill(status=200,json=fake));before=snapshot(f);page.locator('#fb-recover').click();settled(page);assert page.evaluate('fbHandles().length')==1 and page.locator('#fb-save').is_disabled() and snapshot(f)==before
 page.unroute('**/api/preparations/'+p['preparation_id']+'/fact-bundle/recovery/*');page.locator('#fb-recover').click();settled(page);assert page.evaluate('fbHandles().length')==0 and snapshot(f)==before


def test_quota_failure_sends_no_post_and_assumption_markup_not_executed(bundle_page):
 f,page,_=bundle_page;p=setup(f);open_case(page,f,p);fill_source(page);page.evaluate('()=>{window.oldSet=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new DOMException("quota","QuotaExceededError")}}');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#fb-save').click();settled(page);assert 'POST' not in requests and snapshot(f)==before
 page.evaluate('()=>{Storage.prototype.setItem=window.oldSet}');page.locator('#fb-kind').select_option('REGISTER_ASSUMPTION');fill_source(page,'REGISTER_ASSUMPTION','region','<img src=x onerror="window.BUNDLE_XSS=1">');page.locator('#fb-save').click();settled(page);assert '<img' in page.locator('#fb-entries').inner_text();assert page.locator('#fb-entries img,#fb-entries script').count()==0 and not page.evaluate('window.BUNDLE_XSS||false')


@pytest.mark.parametrize('denied',[False,True])
def test_late_recovery_or_denial_does_not_clear_new_draft(bundle_page,denied):
 f,page,_=bundle_page;p=setup(f);path=unknown(f,page,p);page.unroute(path);held=[]
 def delay(route):held.append((route,route.fetch()))
 page.route('**/api/preparations/'+p['preparation_id']+'/fact-bundle/recovery/*',delay);page.locator('#fb-recover').click();end=time.monotonic()+10
 while not held and time.monotonic()<end:page.wait_for_timeout(20)
 assert held;page.locator('#fb-reason').fill('SYNTHETIC NEW_DRAFT_AFTER_GET');route,r=held[0]
 if denied:route.fulfill(status=403,json={'detail':'SYNTHETIC old denial'})
 else:route.fulfill(response=r)
 settled(page);assert page.locator('#fb-reason').input_value()=='SYNTHETIC NEW_DRAFT_AFTER_GET';assert page.evaluate('fbHandles().length')==1 and page.locator('#fb-entries').count()==1 and page.locator('#fb-save').is_disabled()


def test_browser_codepoint_quote_preserves_exact_whitespace_after_emoji(bundle_page):
 from test_preparation import add,read as prep_read
 f,page,_=bundle_page;p=setup(f);p=add(f,prep_read(f,p).json()['preparation']|dict(preparation_id=p['preparation_id']),'material_outline','SYNTHETIC 😀 地区甲  / 17').json();open_case(page,f,p);fill_source(page,value=' 地区甲 ');page.locator('#fb-save').click();settled(page);assert page.evaluate('fbHandles().length')==0;v=get(f,p).json();e=v['entries'][0];assert e['source']['value']==' 地区甲 ' and e['material']['excerpt']==' 地区甲 ';assert e['source']['start']==len('SYNTHETIC 😀') and e['source']['end']-e['source']['start']==len(' 地区甲 ')


def test_owned_api_process_restart_same_pg_get_only_original_bundle_recovery(bundle_page,tmp_path):
 f,page,_=bundle_page;p=setup(f);active=None;pids=[]
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
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
   active=start();page.goto(f'http://127.0.0.1:{port}/');unknown(f,page,p);active.terminate();active.wait(5);active=None;active=start();assert pids[0]!=pids[1];page.reload();open_case(page,f,p);before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#fb-recover').click();settled(page);page.wait_for_function('()=>fbHandles().length===0');assert requests and all(m=='GET' for m in requests) and snapshot(f)==before
   OUT.mkdir(parents=True,exist_ok=True);(OUT/'api-restart.json').write_text(json.dumps({'different_owned_processes':True,'same_persistent_postgresql_history':True,'recovery_get_only':True,'duplicate_effects':0},indent=2)+'\n')
  finally:
   if active is not None and active.poll() is None:active.terminate();active.wait(5)
