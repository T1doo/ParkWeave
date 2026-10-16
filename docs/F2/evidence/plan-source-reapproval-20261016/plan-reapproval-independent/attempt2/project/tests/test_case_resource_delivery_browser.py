"""Actual HTTP/PostgreSQL/Chromium first same-Case resource delivery."""
import hashlib,json,socket,threading,time
from pathlib import Path
from uuid import uuid4
import pytest,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from test_case_resource_delivery import prepared,preview,quoted,submit,effects
from test_case_resources import link_fixture
from test_preparation import preparation_fixture,headers
from test_executor_receipts import receipt_fixture
from test_resource_bundles import bundle,states
from test_resource_bundles_browser import open_resources,choose

OUT=Path('.runtime/case-resource-delivery/browser')
@pytest.fixture
def delivery_page(link_fixture):
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

def ready_page(f,page):
 p=prepared(f);hs,d=bundle(f);open_resources(page,f);choose(page,hs);page.locator('#delivery-case').fill(p['preparation_id']);page.locator('#delivery-preview').click();page.wait_for_function('()=>deliveryQuote!==null');return p,hs,d

def settled(page):page.wait_for_function('()=>!deliveryBusy')
def lose(route):
 response=route.fetch();assert response.status==201;route.abort('failed')

@pytest.mark.parametrize('n',[3,8])
def test_actual_case_capacity_http_page_independent_read_and_widths(delivery_page,n):
 f,page,_=delivery_page;p=prepared(f);hs,d=bundle(f,n);open_resources(page,f);choose(page,hs);page.locator('#delivery-case').fill(p['preparation_id']);page.locator('#delivery-preview').click();page.wait_for_function('()=>deliveryQuote!==null');assert effects(f)==[0]*5
 page.locator('#delivery-confirm').click();settled(page);page.wait_for_function('()=>document.querySelector("#delivery-result").dataset.state==="CURRENT"');assert states(f,hs)==['CONFIRMED']*n and effects(f)==[1,n,1,1,1]
 assert page.evaluate('deliveryHandles().length')==0
 OUT.mkdir(parents=True,exist_ok=True)
 for width in (1200,390,320):
  page.set_viewport_size({'width':width,'height':950});page.locator('#delivery-panel').scroll_into_view_if_needed();assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/f'case-{n}-{width}.png'))


def test_committed_lost_response_cold_get_only_no_private_body(delivery_page):
 f,page,_=delivery_page;p,hs,d=ready_page(f,page);path='**/api/preparations/'+p['preparation_id']+'/resource-delivery';page.route(path,lose);page.locator('#delivery-confirm').click();settled(page)
 assert effects(f)==[1,3,1,1,1] and page.locator('#bundle-confirm').is_disabled() and page.locator('#resource-hold').is_disabled()
 raw=page.evaluate('JSON.stringify({...localStorage})');assert f[2]['fixture-a'] not in raw and 'members' not in raw and 'reason' not in raw
 assert page.evaluate('deliveryHandles().length')==1;seen=[];page.on('request',lambda r:seen.append((r.method,r.url)));page.reload();open_resources(page,f);page.locator('#delivery-recover').click();settled(page);page.wait_for_function('()=>deliveryHandles().length===0');assert not any(m=='POST' for m,u in seen) and effects(f)==[1,3,1,1,1]


@pytest.mark.parametrize('bad',['corrupt','not-observed','revoked','id-array','key-array','actor-number'])
def test_unknown_storage_and_withdrawn_read_preserve_handles_no_writes(delivery_page,bad):
 f,page,_=delivery_page;p,hs,d=ready_page(f,page);key=str(uuid4());name='parkweave.case-resource-delivery.v1.fixture-a.'+key;h={'actor':'fixture-a','id':p['preparation_id'],'key':key}
 if bad=='id-array':h['id']=[h['id']]
 if bad=='key-array':h['key']=[h['key']]
 if bad=='actor-number':h['actor']=7
 if bad=='revoked':
  assert submit(f,p,quoted(f,p,d),key).status_code==201
  with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
 page.evaluate('([n,v])=>localStorage.setItem(n,v)',[name,'{' if bad=='corrupt' else json.dumps(h)]);page.evaluate('bundleControls()');before=effects(f);page.locator('#delivery-recover').click();settled(page)
 assert page.evaluate('(n)=>localStorage.getItem(n)!==null',name) and effects(f)==before and page.locator('#bundle-confirm').is_disabled() and page.locator('#delivery-confirm').is_disabled()
 if bad=='revoked':assert page.locator('#delivery-result').inner_text()=='' and page.locator('#resource-hold-items').inner_text()==''


@pytest.mark.parametrize('target',['case','identity','draft'])
def test_late_http_result_does_not_fill_current_private_view(delivery_page,target):
 f,page,_=delivery_page;p,hs,d=ready_page(f,page);responses=[]
 def delay(route):responses.append((route,route.fetch()))
 page.route('**/api/preparations/'+p['preparation_id']+'/resource-delivery',delay);page.locator('#delivery-confirm').click()
 end=time.monotonic()+10
 while not responses and time.monotonic()<end:page.wait_for_timeout(20)
 assert responses and effects(f)==[1,3,1,1,1]
 if target=='case':page.locator('#delivery-case').fill(str(uuid4()))
 elif target=='identity':open_resources(page,f,'fixture-b')
 else:page.locator('#resource-purpose').fill('SYNTHETIC different draft');page.locator('#resource-purpose').dispatch_event('input')
 route,response=responses.pop();route.fulfill(response=response);settled(page);page.wait_for_timeout(150)
 assert page.locator('#delivery-result').inner_text()=='' and page.evaluate('deliveryHandles().length')==1


def test_owned_api_process_restart_reads_committed_case_delivery_without_post(delivery_page,tmp_path):
    import os,subprocess,sys
    from parkweave.process_env import minimal_environment
    f,page,_=delivery_page;p=prepared(f);hs,d=bundle(f);pids=[];active=None
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
            proc.terminate();proc.wait(timeout=5);raise AssertionError('owned API readiness deadline')
        try:
            active=start();page.goto(f'http://127.0.0.1:{port}/');open_resources(page,f);choose(page,hs)
            page.locator('#delivery-case').fill(p['preparation_id']);page.locator('#delivery-preview').click();page.wait_for_function('()=>deliveryQuote!==null');page.route('**/api/preparations/'+p['preparation_id']+'/resource-delivery',lose);page.locator('#delivery-confirm').click();settled(page)
            assert effects(f)==[1,3,1,1,1];active.terminate();active.wait(timeout=5);active=None
            active=start();assert pids[0]!=pids[1];page.reload();open_resources(page,f)
            requests=[];page.on('request',lambda r:requests.append((r.method,r.url)))
            page.locator('#delivery-recover').click();settled(page);page.wait_for_function('()=>deliveryHandles().length===0')
            assert requests and all(m=='GET' for m,u in requests) and effects(f)==[1,3,1,1,1]
            OUT.mkdir(parents=True,exist_ok=True)
            (OUT/'api-restart.json').write_text(json.dumps({'cold_api_process_restart':True,'different_process_ids':True,'postgresql_history_retained':True,'recovery_all_get':True,'duplicate_effects':0},indent=2)+'\n')
        finally:
            if active is not None and active.poll() is None:active.terminate();active.wait(timeout=5)
