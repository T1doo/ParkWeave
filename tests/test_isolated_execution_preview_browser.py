"""Original bounded-planning panel: real PG/HTTP/Chromium, no automatic POST."""
import json,os,socket,subprocess,sys,threading,time
from pathlib import Path
import pytest,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from parkweave.process_env import minimal_environment
from test_isolated_execution_preview import preparation_fixture,setup,snapshot,add,read,execute,body
from test_case_goal_results_browser import wait_held
OUT=Path('.runtime/isolated-execution-preview/browser')

@pytest.fixture
def preview_page(preparation_fixture,tmp_path):
 f=preparation_fixture;p,e=setup(f,tmp_path);listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
 server=uvicorn.Server(uvicorn.Config(create_app(f[0]),host='127.0.0.1',port=port,log_level='warning',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
 try:
  end=time.monotonic()+10
  while not server.started and thread.is_alive() and time.monotonic()<end:time.sleep(.02)
  assert server.started
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda x:errors.append(str(x)));page.goto(f'http://127.0.0.1:{port}/')
   try:yield f,p,e,page,errors
   finally:context.close();browser.close()
  assert not errors,errors
 finally:server.should_exit=True;thread.join(10);listener.close();assert not thread.is_alive()


def open_page(page,f,p):
 page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadPlan(id)',p['preparation_id']);page.wait_for_function('()=>planView!==null');page.locator('#bounded-planning-read').click();page.wait_for_function('()=>executionPreviewView!==null');assert page.locator('#execution-preview-panel').is_visible()


def lost(page,f,p):
 posted=[]
 def lose(route):
  if route.request.method!='POST':route.continue_();return
  r=route.fetch();assert r.status==201;posted.append(dict(key=route.request.headers['idempotency-key'],body=route.request.post_data_json,result=r.json()['result']));route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/execution-preview',lose);page.locator('#execution-preview-run').click();page.wait_for_function('()=>executionPreviewHandle!==null&&!executionPreviewSubmitting&&document.getElementById("execution-preview-error").textContent!==""');assert len(posted)==1
 storage=page.evaluate('JSON.stringify({...localStorage})');assert 'PRIVATE_PREVIEW' not in storage and f[2]['fixture-a'] not in storage;rows=json.loads(page.evaluate('localStorage.getItem(executionPreviewStorage)'));assert set(rows[0])=={'preparation','key','revision','source','expires'};return storage,posted[0]


def recovered(page):page.wait_for_function('()=>executionPreviewView!==null&&executionPreviewView.status==="COMMITTED"')


def test_original_page_lost_result_warm_cold_new_page_get_only_three_widths(preview_page):
 f,p,e,page,errors=preview_page;open_page(page,f,p);before=snapshot(f);storage,post=lost(page,f,p);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#execution-preview-recover').click();recovered(page)
 assert snapshot(f)==before and set(requests)=={'GET'} and page.evaluate('executionPreviewView.result.id')==post['result']['id']
 page.reload();assert page.locator('#token').input_value()=='';open_page(page,f,p);recovered(page);assert snapshot(f)==before and set(requests)=={'GET'}
 new=page.context.new_page();new.goto(page.url);page.close();page=new;requests=[];page.on('request',lambda r:requests.append(r.method));open_page(page,f,p);recovered(page)
 assert snapshot(f)==before and set(requests)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==storage
 assert page.locator('#execution-preview-run').is_disabled() and 'PRIVATE_PREVIEW' not in page.locator('#execution-preview-result').inner_text()
 OUT.mkdir(parents=True,exist_ok=True)
 for width in (1200,390,320):
  page.set_viewport_size({'width':width,'height':1000});page.locator('#execution-preview-panel').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.locator('#execution-preview-panel').screenshot(path=str(OUT/f'execution-preview-{width}.png'))
 page.locator('#execution-preview-release').click();page.wait_for_function('()=>executionPreviewHandle===null&&executionPreviewView!==null');assert page.evaluate('JSON.stringify({...localStorage})')=='{}' and snapshot(f)==before and set(requests)=={'GET'} and not errors
 (OUT/'original-page-recovery.json').write_text(json.dumps(dict(actual_http=True,actual_postgresql=True,actual_registered_commands=4,formal_snapshot_unchanged=True,warm_cold_new_page_get_only=True,opaque_fields=5,no_private_text_or_token=True,three_widths=[1200,390,320],model_calls=0),indent=2)+'\n')


@pytest.mark.parametrize('target',['case','identity','draft'])
def test_late_actual_execution_never_replaces_new_context(preview_page,tmp_path,target):
 f,p,e,page,errors=preview_page;open_page(page,f,p);p2,_=setup_other(f);held=[]
 def hold(route):
  if route.request.method!='POST':route.continue_();return
  r=route.fetch();assert r.status==201;held.append((route,r))
 page.route('**/api/preparations/'+p['preparation_id']+'/execution-preview',hold);page.locator('#execution-preview-run').click();wait_held(page,held)
 if target=='case':open_page(page,f,p2)
 elif target=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
 else:page.locator('#request-current').fill('SYNTHETIC NEW PREVIEW DRAFT');page.locator('#request-current').dispatch_event('input')
 page.locator('#execution-preview-result').evaluate('(e)=>e.textContent="SYNTHETIC NEW PREVIEW CONTEXT"');before=snapshot(f);held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(150)
 assert page.locator('#execution-preview-result').inner_text()=='SYNTHETIC NEW PREVIEW CONTEXT' and snapshot(f)==before and not errors
 if target=='case':assert page.evaluate('executionPreviewView.preparation_id')==p2['preparation_id']


def setup_other(f):
 from test_preparation import create
 from test_request_intents import save
 p,_,_=create(f);r=save(f,p,goals=['LOCAL_MATERIAL_PREPARATION']);p={**p,'revision':r.json()['revision']}
 for slot in ['need_summary','material_outline']:p=add(f,p,slot,'SYNTHETIC other private material').json()
 return p,None


@pytest.mark.parametrize('cap',['READ','PREPARE','EXECUTE'])
def test_revocation_during_unknown_clears_all_private_projection_preserves_opaque_handle(preview_page,cap):
 f,p,e,page,errors=preview_page;open_page(page,f,p);storage,post=lost(page,f,p)
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True);table='preparation_grants' if cap=='PREPARE' else 'capability_grants';c.execute('UPDATE '+table+" SET active=false WHERE principal_id='fixture-a' AND capability=%s",(cap,))
 before=snapshot(f);page.locator('#execution-preview-recover').click();page.wait_for_function('()=>executionPreviewView===null&&planView===null')
 assert page.locator('#execution-preview-panel').is_hidden() and page.locator('#execution-preview-result').inner_text()=='' and page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==before and not errors


def test_owned_new_api_pid_recovers_original_artifact_without_reissuing_permissions(preview_page,tmp_path):
 f,p,e,page,errors=preview_page
 factory=tmp_path/'preview_factory.py';factory.write_text('import os\nfrom parkweave.api import create_app\nfrom parkweave.store import Store\nfrom parkweave.isolated_execution_preview import IsolatedExecutionPreview\ndef app():\n s=Store(os.environ["PARKWEAVE_DSN"])\n IsolatedExecutionPreview(s,os.environ["PARKWEAVE_PREVIEW_ROOT"],enabled_for_synthetic_preview=True).attach_store(s)\n return create_app(s)\n')
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_PREVIEW_ROOT=str(e.root),PYTHONPATH=os.pathsep.join([str(tmp_path),str(Path.cwd()/'src')]))
 cmd=[sys.executable,'-m','uvicorn','preview_factory:app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'];pids=[];active=None
 with (tmp_path/'owned-preview-api.log').open('w') as log:
  def start():
   proc=subprocess.Popen(cmd,env=env,stdout=log,stderr=log);pids.append(proc.pid);end=time.monotonic()+10
   while proc.poll() is None and time.monotonic()<end:
    try:
     r=page.request.get(f'http://127.0.0.1:{port}/health',timeout=500)
     if r.ok and r.json()['process_id']==proc.pid:return proc
    except Exception:pass
    time.sleep(.05)
   proc.terminate();proc.wait(5);raise AssertionError('owned preview API readiness deadline')
  try:
   active=start();page.goto(f'http://127.0.0.1:{port}/');open_page(page,f,p);storage,post=lost(page,f,p);before=snapshot(f);active.terminate();active.wait(5);active=None;active=start();assert pids[0]!=pids[1]
   page.reload();requests=[];page.on('request',lambda r:requests.append(r.method));open_page(page,f,p);recovered(page)
   assert page.evaluate('executionPreviewView.result')==post['result'] and snapshot(f)==before and set(requests)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==storage and not errors
   OUT.mkdir(parents=True,exist_ok=True);(OUT/'actual-api-restart.json').write_text(json.dumps(dict(different_api_pids=pids,actual_http=True,same_postgresql=True,original_namespace=True,original_artifact_hash=True,original_key_get_only=True,no_permission_reissued=True,formal_writes=0,model_calls=0),indent=2)+'\n')
  finally:
   if active is not None and active.poll() is None:active.terminate();active.wait(5)


def test_original_page_failed_missing_input_then_explicit_source_repair_keeps_old_failure(preview_page):
 from test_preparation import create
 from test_request_intents import save
 f,full,e,page,errors=preview_page;p,_,_=create(f);p={**p,'revision':save(f,p,goals=['LOCAL_MATERIAL_PREPARATION']).json()['revision']}
 p=add(f,p,'need_summary','SYNTHETIC one preview input').json();open_page(page,f,p);before=snapshot(f);page.locator('#execution-preview-run').click();page.wait_for_function('()=>executionPreviewView?.result?.state==="FAILED"&&!executionPreviewSubmitting')
 assert '输入核对失败' in page.locator('#execution-preview-result').inner_text() and snapshot(f)==before;old=page.evaluate('executionPreviewView.result')
 page.locator('#execution-preview-release').click();page.wait_for_function('()=>executionPreviewHandle===null')
 p=add(f,p,'material_outline','SYNTHETIC repaired actual source').json();before=snapshot(f);open_page(page,f,p);page.locator('#execution-preview-run').click();page.wait_for_function('()=>executionPreviewView?.result?.state==="SUCCEEDED"&&!executionPreviewSubmitting')
 h=page.evaluate('executionPreviewView.history');assert len(h)==2 and h[0]['document']==old and h[0]['source_state']=='STALE' and snapshot(f)==before and not errors


@pytest.mark.parametrize('damage',['expired','extra','oversized'])
def test_malformed_or_expired_handle_never_used_as_execution_or_credential(preview_page,damage):
 f,p,e,page,errors=preview_page;open_page(page,f,p);storage,post=lost(page,f,p);h=page.evaluate('executionPreviewHandle')
 if damage=='expired':h['expires']=0
 elif damage=='extra':h['token']='SYNTHETIC POISON TOKEN'
 else:h['key']='x'*700
 page.evaluate('(h)=>localStorage.setItem(executionPreviewStorage,JSON.stringify([h]))',h);page.reload();requests=[];page.on('request',lambda r:requests.append((r.method,r.url)));before=snapshot(f);open_page(page,f,p)
 assert page.evaluate('executionPreviewHandle') is None and all(method=='GET' and '/recovery/' not in url for method,url in requests) and snapshot(f)==before and not errors


@pytest.mark.parametrize('damage',['key','source','revision'])
def test_wrong_original_response_proof_is_not_rendered(preview_page,damage):
 f,p,e,page,errors=preview_page;open_page(page,f,p);storage,post=lost(page,f,p);before=snapshot(f)
 def wrong(route):
  r=route.fetch();assert r.status==200;x=r.json()
  if damage=='key':x['result']['request_key']='synthetic-wrong-key'
  elif damage=='source':x['result']['binding']['source_sha256']='0'*64
  else:x['result']['binding']['preparation_revision']+=1
  route.fulfill(status=200,json=x)
 page.route('**/execution-preview/recovery/*',wrong);page.locator('#execution-preview-recover').click();page.wait_for_function('()=>document.getElementById("execution-preview-error").textContent.includes("证明不匹配")')
 assert page.evaluate('executionPreviewView') is None and page.locator('#execution-preview-result').inner_text()=='' and page.locator('#execution-preview-run').is_disabled() and page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==before and not errors


@pytest.mark.parametrize('method',['GET','POST'])
@pytest.mark.parametrize('damage',['changed','expired'])
def test_persisted_handle_and_ttl_rechecked_after_actual_reply(preview_page,method,damage):
 f,p,e,page,errors=preview_page;open_page(page,f,p);held=[]
 if method=='GET':lost(page,f,p)
 def hold(route):
  if route.request.method!=method:route.continue_();return
  r=route.fetch();assert r.status==(200 if method=='GET' else 201);held.append((route,r))
 page.route('**/execution-preview'+('/recovery/*' if method=='GET' else ''),hold)
 page.locator('#execution-preview-recover' if method=='GET' else '#execution-preview-run').click();wait_held(page,held);h=page.evaluate('executionPreviewHandle');before=snapshot(f)
 if damage=='changed':
  h['source']='0'*64;page.evaluate('(h)=>localStorage.setItem(executionPreviewStorage,JSON.stringify([h]))',h)
 else:page.evaluate('(expiry)=>{Date.now=()=>expiry+1}',h['expires'])
 held[0][0].fulfill(response=held[0][1]);page.wait_for_function('()=>!executionPreviewSubmitting&&document.getElementById("execution-preview-error").textContent!==""')
 assert '已持久保存' not in page.locator('#execution-preview-error').inner_text() and 'hash ' not in page.locator('#execution-preview-result').inner_text() and page.locator('#execution-preview-run').is_disabled() and snapshot(f)==before and not errors
 if damage=='changed':
  saved=page.evaluate('localStorage.getItem(executionPreviewStorage)');page.locator('#execution-preview-release').click();page.wait_for_function('()=>document.getElementById("page-feedback").textContent.includes("句柄或期限已变化")');assert page.evaluate('localStorage.getItem(executionPreviewStorage)')==saved


def test_eight_unknown_handles_preserved_ninth_send_refused(preview_page):
 from uuid import uuid4
 f,p,e,page,errors=preview_page;open_page(page,f,p);handles=[dict(preparation=str(uuid4()),key=uuid4().hex,revision=1,source='1'*64,expires=int(time.time()*1000)+3600000) for _ in range(8)]
 page.evaluate('(h)=>localStorage.setItem(executionPreviewStorage,JSON.stringify(h))',handles);saved=page.evaluate('localStorage.getItem(executionPreviewStorage)');requests=[];page.on('request',lambda r:requests.append(r.method));before=snapshot(f)
 page.locator('#execution-preview-run').click();page.wait_for_function('()=>document.getElementById("page-feedback").textContent.includes("容量")')
 assert 'POST' not in requests and page.evaluate('localStorage.getItem(executionPreviewStorage)')==saved and snapshot(f)==before and read(f,p).json()['history']==[] and not errors


def test_late_actual_forbidden_recovery_never_clears_new_identity_context(preview_page):
 f,p,e,page,errors=preview_page;open_page(page,f,p);storage,post=lost(page,f,p)
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
 held=[]
 def hold(route):
  r=route.fetch();assert r.status==403;held.append((route,r))
 page.route('**/execution-preview/recovery/*',hold);page.locator('#execution-preview-recover').click();wait_held(page,held);page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input');page.locator('#execution-preview-result').evaluate('(e)=>e.textContent="SYNTHETIC NEW IDENTITY VIEW"');before=snapshot(f)
 held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(150);assert page.locator('#execution-preview-result').inner_text()=='SYNTHETIC NEW IDENTITY VIEW' and page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==before and not errors
