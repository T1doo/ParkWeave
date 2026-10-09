"""Actual loopback HTTP, original DOM/Chromium and isolated PG bundle commands."""
import json,hashlib,socket,threading,time
from pathlib import Path
from uuid import uuid4
import pytest,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from test_resource_bundles import bundle,write,states,totals,recovery
from test_resource_combinations import pair_fixture
from test_preparation import headers

OUT=Path('.runtime/resource-bundles/browser')

@pytest.fixture
def bundle_page(pair_fixture):
    f=pair_fixture;listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_app(f[0]),host='127.0.0.1',port=port,log_level='warning',access_log=False))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    try:
        end=time.monotonic()+10
        while not server.started and thread.is_alive() and time.monotonic()<end:time.sleep(.02)
        assert server.started
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx=browser.new_context();page=ctx.new_page();errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)));page.goto(f'http://127.0.0.1:{port}/')
            try:yield f,page,errors
            finally:ctx.close();browser.close()
        assert not errors,errors
    finally:
        server.should_exit=True;thread.join(timeout=10);listener.close();assert not thread.is_alive()

def open_resources(page,f,user='fixture-a'):
    page.locator('#token').fill(f[2][user]);page.locator('#token').dispatch_event('change')
    page.locator('[data-tab="resource"]').click();page.locator('#resource-catalog').click()
    page.wait_for_function('()=>bundleActor!==null')

def choose(page,hs):
    page.locator('#resource-mine').click()
    for h in hs:page.locator('[data-combination-hold="'+h['id']+'"]').check()

def settled(page):page.wait_for_function('()=>!bundleBusy')

@pytest.mark.parametrize('n',[3,8])
def test_actual_confirm_read_cancel_and_three_widths(bundle_page,n):
    f,page,_=bundle_page;hs,d=bundle(f,n);open_resources(page,f);choose(page,hs)
    assert page.locator('#bundle-confirm').is_enabled();page.locator('#bundle-confirm').click();settled(page)
    page.wait_for_function('()=>document.querySelector(".combination-result")?.dataset.state==="CONFIRMED"')
    assert states(f,hs)==['CONFIRMED']*n and totals(f)==[1,n,1]
    shots=[];OUT.mkdir(parents=True,exist_ok=True)
    for width in (1200,390,320):
        page.set_viewport_size({'width':width,'height':950});page.locator('#bundle-panel').scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        dest=OUT/(f'bundle-{n}-'+str(width)+'.png');page.screenshot(path=str(dest));shots.append({'file':dest.name,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
    (OUT/(f'browser-{n}.json')).write_text(json.dumps({'actual_http_pg':True,'members':n,'screenshots':shots},indent=2)+'\n')
    page.locator('[data-combination-cancel]').click();settled(page)
    page.wait_for_function('()=>document.querySelector(".combination-result")?.dataset.state==="CANCELLED"')
    assert states(f,hs)==['RELEASED']*n and totals(f)==[1,n,2]
    assert page.evaluate('bundleHandles().length')==0

def lose_post(route):
    if route.request.method=='POST':response=route.fetch();assert response.status==201;route.abort('failed')
    else:route.continue_()

def test_post_committed_lost_reply_cold_reload_only_get_and_private_storage(bundle_page):
    f,page,_=bundle_page;hs,d=bundle(f);open_resources(page,f);choose(page,hs)
    page.route('**/api/resource-bundles',lose_post);page.locator('#bundle-confirm').click();settled(page)
    assert states(f,hs)==['CONFIRMED']*3 and totals(f)==[1,3,1]
    raw=page.evaluate('JSON.stringify({...localStorage})');assert f[2]['fixture-a'] not in raw and 'SYNTHETIC private' not in raw and 'members' not in raw
    assert page.locator('#bundle-confirm').is_disabled()
    page.reload();open_resources(page,f);requests=[];page.on('request',lambda r:requests.append((r.method,r.url)))
    page.locator('#bundle-recover').click();settled(page)
    page.wait_for_function('()=>bundleHandles().length===0')
    assert requests and all(m=='GET' for m,u in requests) and totals(f)==[1,3,1]
    assert page.locator('.combination-result').get_attribute('data-state')=='CONFIRMED'

@pytest.mark.parametrize('kind',['unobserved','corrupt','eight'])
def test_unknown_or_corrupt_handle_never_unblocks_or_posts(bundle_page,kind):
    f,page,_=bundle_page;hs,d=bundle(f);open_resources(page,f)
    key=str(uuid4());h={'actor':'fixture-a','id':None,'key':key,'operation':'CONFIRM'}
    entries={('parkweave.resource-bundle-recovery.v1.fixture-a.'+key):'{' if kind=='corrupt' else json.dumps(h)}
    if kind=='eight':
        for _ in range(7):
            k=str(uuid4());entries['parkweave.resource-bundle-recovery.v1.fixture-a.'+k]=json.dumps({**h,'key':k})
    page.evaluate('entries=>{for(const [k,v] of Object.entries(entries))localStorage.setItem(k,v);bundleControls()}',entries)
    before=page.evaluate('JSON.stringify({...localStorage})');requests=[];page.on('request',lambda r:requests.append((r.method,r.url)))
    page.locator('#bundle-recover').click();settled(page);assert page.evaluate('JSON.stringify({...localStorage})')==before
    assert page.locator('#bundle-confirm').is_disabled() and all(m=='GET' for m,u in requests)
    assert states(f,hs)==['HELD']*3 and totals(f)==[0,0,0]

@pytest.mark.parametrize('target',['identity','draft'])
def test_late_commit_never_fills_new_context_and_handle_survives(bundle_page,target):
    f,page,_=bundle_page;hs,d=bundle(f);open_resources(page,f);choose(page,hs);held=[]
    def delay(route):
        if route.request.method=='POST':held.append((route,route.fetch()))
        else:route.continue_()
    page.route('**/api/resource-bundles',delay);page.locator('#bundle-confirm').click()
    for _ in range(100):
        page.wait_for_timeout(20)
        if held:break
    assert held
    if target=='identity':open_resources(page,f,'fixture-b')
    else:page.locator('#resource-purpose').fill('SYNTHETIC changed draft')
    held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(100)
    assert page.locator('.combination-result').count()==0 and page.evaluate('bundleHandles().length')==1
    assert states(f,hs)==['CONFIRMED']*3
    if target=='draft':assert page.locator('#bundle-recover').is_enabled()

def test_recovery_failure_after_committed_success_retains_handle(bundle_page):
    f,page,_=bundle_page;hs,d=bundle(f);open_resources(page,f);choose(page,hs)
    page.route('**/api/resource-bundles/recovery/*',lambda r:r.fulfill(status=409,content_type='application/json',body='{"detail":"SYNTHETIC recovery conflict"}'))
    page.locator('#bundle-confirm').click();settled(page)
    assert totals(f)==[1,3,1] and page.evaluate('bundleHandles().length')==1 and page.locator('#bundle-confirm').is_disabled()

def test_withdrawal_clears_private_view_and_read_recovery_does_not_write(bundle_page):
    f,page,_=bundle_page;hs,d=bundle(f);open_resources(page,f);choose(page,hs)
    page.route('**/api/resource-bundles',lose_post);page.locator('#bundle-confirm').click();settled(page)
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND resource_id=%s AND capability='READ'",(__import__('parkweave.resource_holds',fromlist=['RESOURCE_ID']).RESOURCE_ID,))
    page.locator('#bundle-recover').click();settled(page)
    assert page.locator('.combination-result').count()==0 and 'SYNTHETIC private' not in page.locator('#resource').inner_text()
    assert page.evaluate('bundleHandles().length')==1 and totals(f)==[1,3,1]

@pytest.mark.parametrize('user',['fixture-b','fixture-c'])
def test_actual_http_cross_tenant_and_duplicate_key(bundle_page,user):
    f,page,_=bundle_page;hs,d=bundle(f);key=uuid4().hex;base=page.url.rstrip('/')
    bad=page.request.post(base+'/api/resource-bundles',headers=headers(f[2],user,key),data=d);assert bad.status==403 and totals(f)==[0,0,0]
    for _ in range(2):assert page.request.post(base+'/api/resource-bundles',headers=headers(f[2],key=key),data=d).status==201
    assert totals(f)==[1,3,1] and states(f,hs)==['CONFIRMED']*3

def test_actual_http_stale_third_rule_refuses_every_member(bundle_page):
    f,page,_=bundle_page;hs,d=bundle(f);open_resources(page,f);choose(page,hs)
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET revision=revision+1 WHERE id=%s',(__import__('parkweave.resource_holds',fromlist=['RESOURCE_ID']).RESOURCE_ID,))
    page.locator('#bundle-confirm').click();settled(page)
    assert totals(f)==[0,0,0] and states(f,hs)==['HELD']*3 and page.evaluate('bundleHandles().length')==0

def test_owned_api_process_restart_reads_committed_bundle_without_post(bundle_page,tmp_path):
    import os,subprocess,sys
    from parkweave.process_env import minimal_environment
    f,page,_=bundle_page;hs,d=bundle(f);pids=[];active=None
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
            page.route('**/api/resource-bundles',lose_post);page.locator('#bundle-confirm').click();settled(page)
            assert totals(f)==[1,3,1];active.terminate();active.wait(timeout=5);active=None
            active=start();assert pids[0]!=pids[1];page.reload();open_resources(page,f)
            requests=[];page.on('request',lambda r:requests.append((r.method,r.url)))
            page.locator('#bundle-recover').click();settled(page);page.wait_for_function('()=>bundleHandles().length===0')
            assert requests and all(m=='GET' for m,u in requests) and totals(f)==[1,3,1]
            OUT.mkdir(parents=True,exist_ok=True)
            (OUT/'api-restart.json').write_text(json.dumps({'cold_api_process_restart':True,'different_process_ids':True,'postgresql_history_retained':True,'recovery_all_get':True,'duplicate_effects':0},indent=2)+'\n')
        finally:
            if active is not None and active.poll() is None:active.terminate();active.wait(timeout=5)
