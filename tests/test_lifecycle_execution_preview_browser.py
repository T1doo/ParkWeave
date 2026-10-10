"""Real loopback HTTP/PostgreSQL/P5 page: cold read and explicit local intent."""
import json,socket,threading,time
from pathlib import Path
import pytest,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from test_lifecycle_execution_preview import lifecycle_fixture,receipt_preview_fixture,access_fixture,receipt_fixture,preparation_fixture,snapshot,read,body,execute
from test_isolated_execution_preview_browser import wait_held
OUT=Path('.runtime/p5-local-case-preview/browser')
@pytest.fixture
def lifecycle_page(lifecycle_fixture):
    f,p,_,_,_,_,e,a=lifecycle_fixture;listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_app(f[0]),host='127.0.0.1',port=port,log_level='warning',access_log=False));thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    try:
        end=time.monotonic()+10
        while not server.started and thread.is_alive() and time.monotonic()<end:time.sleep(.02)
        assert server.started
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda x:errors.append(str(x)));page.goto(f'http://127.0.0.1:{port}/')
            try:yield f,p,e,page,errors,a
            finally:context.close();browser.close()
        assert not errors,errors
    finally:server.should_exit=True;thread.join(10);listener.close();assert not thread.is_alive()
def open_page(page,f,p):
    page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadPlan(id)',p['preparation_id']);page.wait_for_function('()=>planView!==null');page.locator('#bounded-planning-read').click();page.wait_for_function('()=>lifecycleExecutionPreviewView!==null')
    assert page.locator('#lifecycle-execution-preview-panel').is_visible()
def lose(page,p):
    posted=[]
    def route(r):
        if r.request.method!='POST':r.continue_();return
        response=r.fetch();assert response.status==201;posted.append(response.json()['result']);r.abort('failed')
    page.route('**/api/preparations/'+p['preparation_id']+'/lifecycle-execution-preview',route);page.locator('#lifecycle-execution-preview-run').click()
    page.wait_for_function('()=>lifecycleExecutionPreviewHandle!==null&&!lifecycleExecutionPreviewSubmitting&&document.getElementById("lifecycle-execution-preview-error").textContent!==""')
    assert len(posted)==1;return posted[0]
@pytest.mark.parametrize('mode',['REVALIDATE','REVALIDATE_CLOSE','REVALIDATE_CLOSE_REOPEN'])
def test_real_page_explicit_sequence_cold_get_and_local_state_three_widths(lifecycle_page,mode):
    f,p,e,page,errors,a=lifecycle_page;open_page(page,f,p)
    assert page.locator('#lifecycle-execution-preview-sequence').input_value()=='REVALIDATE'
    page.locator('#lifecycle-execution-preview-sequence').select_option(mode);before=snapshot(f);post=lose(page,p);storage=page.evaluate('JSON.stringify({...localStorage})')
    assert f[2]['fixture-a'] not in storage and 'PRIVATE_PREVIEW' not in storage and mode not in storage
    requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);page.wait_for_function('()=>lifecycleExecutionPreviewView?.status==="COMMITTED"')
    assert set(requests)=={'GET'} and page.evaluate('lifecycleExecutionPreviewView.result')==post and snapshot(f)==before
    text=page.locator('#lifecycle-execution-preview-result').inner_text();assert '外部正式成果' in text and 'Case未完成' in text and '正式Case/权限/通知写入0' in text and 'PRIVATE_PREVIEW' not in text
    if mode.endswith('REOPEN'):assert '当前校验 false' in text and 'cycle 2' in text and 'REOPENED' in text
    else:assert 'WAITING_CONFIRMATION' in text and '当前校验 true' in text
    assert page.locator('#lifecycle-execution-preview-sequence').is_disabled() and page.locator('#lifecycle-execution-preview-run').is_disabled()
    for width in (1200,390,320):
        page.set_viewport_size({'width':width,'height':1000});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');OUT.mkdir(parents=True,exist_ok=True);page.locator('#lifecycle-execution-preview-panel').screenshot(path=str(OUT/(mode+'-'+str(width)+'.png')))
    assert page.evaluate('JSON.stringify({...localStorage})')==storage

def test_request_changes_page_preserves_unresolved_p4_refusal(lifecycle_page):
    f,p,e,page,errors,a=lifecycle_page;open_page(page,f,p);page.locator('#lifecycle-execution-preview-decision').select_option('REQUEST_CHANGES');page.locator('#lifecycle-execution-preview-sequence').select_option('REVALIDATE_CLOSE');post=lose(page,p)
    assert post['state']=='FAILED' and post['artifact']['p4_state']=='CHANGES_REQUESTED';page.reload();open_page(page,f,p);page.wait_for_function('()=>lifecycleExecutionPreviewView?.status==="COMMITTED"');text=page.locator('#lifecycle-execution-preview-result').inner_text();assert '不会自动补ACK或关闭' in text and 'P5 FAILED' in text

def test_unobserved_unknown_key_refuses_new_post_and_release(lifecycle_page):
    f,p,e,page,errors,a=lifecycle_page;open_page(page,f,p);before=snapshot(f);requests=[]
    page.route('**/api/preparations/'+p['preparation_id']+'/lifecycle-execution-preview',lambda r:r.abort('failed') if r.request.method=='POST' else r.continue_());page.locator('#lifecycle-execution-preview-run').click();page.wait_for_function('()=>lifecycleExecutionPreviewHandle!==null&&!lifecycleExecutionPreviewSubmitting')
    page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);page.wait_for_function('()=>lifecycleExecutionPreviewView?.status==="NOT_OBSERVED"')
    storage=page.evaluate('JSON.stringify({...localStorage})');page.locator('#lifecycle-execution-preview-release').click();page.wait_for_function('()=>document.getElementById("plan-error").textContent!==""')
    assert page.evaluate('JSON.stringify({...localStorage})')==storage and page.locator('#lifecycle-execution-preview-run').is_disabled() and snapshot(f)==before and set(requests)=={'GET'}

def test_current_revocation_clears_private_page_and_keeps_handle(lifecycle_page):
    f,p,e,page,errors,a=lifecycle_page;open_page(page,f,p);lose(page,p);storage=page.evaluate('JSON.stringify({...localStorage})')
    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    page.locator('#lifecycle-execution-preview-recover').click();page.wait_for_function('()=>lifecycleExecutionPreviewView===null&&planView===null')
    assert page.locator('#lifecycle-execution-preview-panel').is_hidden() and page.locator('#lifecycle-execution-preview-result').inner_text()=='' and page.evaluate('JSON.stringify({...localStorage})')==storage

@pytest.mark.parametrize('change',['token','draft'])
def test_late_real_success_does_not_fill_changed_identity_or_draft(lifecycle_page,change):
    f,p,e,page,errors,a=lifecycle_page;open_page(page,f,p);held=[]
    def hold(route):
        if route.request.method!='POST':route.continue_();return
        response=route.fetch();assert response.status==201;held.append((route,response))
    page.route('**/api/preparations/'+p['preparation_id']+'/lifecycle-execution-preview',hold);page.locator('#lifecycle-execution-preview-run').click();wait_held(page,held)
    if change=='token':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
    else:page.locator('#request-current').fill('SYNTHETIC new draft');page.locator('#request-current').dispatch_event('input')
    route,response=held[0];route.fulfill(response=response);page.wait_for_timeout(200)
    assert page.evaluate('lifecycleExecutionPreviewView') is None and page.locator('#lifecycle-execution-preview-result').inner_text()==''
    assert page.evaluate('lifecycleExecutionPreviewHandles().length')==1

@pytest.mark.parametrize('poison',['other_history','wrong_key','namespace','unknown','not_observed_result','duplicate_history','object_key_order'])
def test_original_recovery_reply_exact_unique_history_or_preserve_unknown(lifecycle_page,poison):
    f,p,e,page,errors,a=lifecycle_page;open_page(page,f,p);first=lose(page,p);storage=page.evaluate('JSON.stringify({...localStorage})')
    second=execute(f,p,body(f,p,'REVALIDATE_CLOSE')).json()['result']
    def route(r):
        response=r.fetch();x=response.json()
        if poison=='other_history':x['history']=[{'document':second,'source_state':'SNAPSHOT_MATCH'}]
        elif poison=='wrong_key':x['result']['request_key']=second['request_key']
        elif poison=='namespace':x['result']['namespace']='wrong'
        elif poison=='unknown':x['status']='UNKNOWN'
        elif poison=='not_observed_result':x['status']='NOT_OBSERVED'
        elif poison=='duplicate_history':x['history'].append({'document':first,'source_state':'SNAPSHOT_MATCH'})
        else:
            def reorder(v):
                if isinstance(v,dict):return {k:reorder(v[k]) for k in reversed(list(v))}
                if isinstance(v,list):return [reorder(n) for n in v]
                return v
            x['result']=reorder(x['result'])
        r.fulfill(status=200,content_type='application/json',body=json.dumps(x))
    page.route('**/lifecycle-execution-preview/recovery/**',route);page.locator('#lifecycle-execution-preview-recover').click()
    if poison=='object_key_order':page.wait_for_function('()=>lifecycleExecutionPreviewView?.status==="COMMITTED"');assert page.evaluate('lifecycleExecutionPreviewView.result')==first
    else:
        page.wait_for_function('()=>lifecycleExecutionPreviewView===null&&document.getElementById("lifecycle-execution-preview-error").textContent!==""')
        assert page.locator('#lifecycle-execution-preview-result').inner_text()=='' and page.locator('#lifecycle-execution-preview-run').is_disabled()
    assert page.evaluate('JSON.stringify({...localStorage})')==storage


def test_corrupt_pending_storage_stays_unknown_and_never_posts(lifecycle_page):
    f,p,e,page,errors,a=lifecycle_page;open_page(page,f,p);raw='[{"key":"unknown-only"}]';page.evaluate('(raw)=>localStorage.setItem(lifecycleExecutionPreviewStorage,raw)',raw);requests=[];page.on('request',lambda r:requests.append(r.method));page.reload()
    page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input');page.evaluate('(id)=>loadPlan(id)',p['preparation_id']);page.wait_for_function('()=>planView!==null');page.locator('#bounded-planning-read').click();page.wait_for_function('()=>document.getElementById("bounded-planning-error").textContent!==""')
    assert page.evaluate('localStorage.getItem(lifecycleExecutionPreviewStorage)')==raw and set(requests)=={'GET'} and page.locator('#lifecycle-execution-preview-run').is_disabled()
