"""Original P4 page with real loopback HTTP/PG/Chromium and cold GET recovery."""
import json,socket,threading,time
from pathlib import Path
import pytest,uvicorn
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from test_receipt_execution_preview import receipt_preview_fixture,access_fixture,receipt_fixture,preparation_fixture,snapshot,read,execute,body
from test_resource_execution_preview import setup as p2_setup
from test_isolated_run_access import approved
from test_isolated_execution_preview_browser import wait_held
OUT=Path('.runtime/p4-receipt-execution-preview/browser')
@pytest.fixture
def receipt_page(receipt_preview_fixture):
 f,p,_,_,_,e,a=receipt_preview_fixture;listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
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
    page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('input')
    page.evaluate('(id)=>loadPlan(id)',p['preparation_id']);page.wait_for_function('()=>planView!==null')
    page.locator('#bounded-planning-read').click();page.wait_for_function('()=>receiptExecutionPreviewView!==null')
    assert page.locator('#receipt-execution-preview-panel').is_visible()


def lost(page,f,p):
    posted=[]
    def lose(route):
        if route.request.method!='POST':route.continue_();return
        r=route.fetch();assert r.status==201;posted.append(dict(key=route.request.headers['idempotency-key'],result=r.json()['result']));route.abort('failed')
    page.route('**/api/preparations/'+p['preparation_id']+'/receipt-execution-preview',lose)
    page.locator('#receipt-execution-preview-run').click()
    page.wait_for_function('()=>receiptExecutionPreviewHandle!==null&&!receiptExecutionPreviewSubmitting&&document.getElementById("receipt-execution-preview-error").textContent!==""')
    assert len(posted)==1
    storage=page.evaluate('JSON.stringify({...localStorage})')
    assert f[2]['fixture-a'] not in storage and 'PRIVATE_PREVIEW' not in storage
    rows=json.loads(page.evaluate('localStorage.getItem(receiptExecutionPreviewStorage)'))
    assert set(rows[0])=={'preparation','key','revision','source','expires'}
    return storage,posted[0]


def recovered(page):page.wait_for_function('()=>receiptExecutionPreviewView?.status==="COMMITTED"')


def test_original_page_lost_reply_cold_recovery_no_post_all_goals_three_widths(receipt_page):
    f,p,e,page,errors,a=receipt_page;open_page(page,f,p);before=snapshot(f);storage,post=lost(page,f,p);requests=[]
    page.on('request',lambda r:requests.append(r.method));page.reload();assert page.locator('#token').input_value()==''
    open_page(page,f,p);recovered(page)
    assert set(requests)=={'GET'} and page.evaluate('receiptExecutionPreviewView.result')==post['result'] and snapshot(f)==before
    assert page.evaluate('JSON.stringify({...localStorage})')==storage
    text=page.locator('#receipt-execution-preview-result').inner_text()
    assert 'P5' in text and 'P4 LOCAL_ACKNOWLEDGED' in text and '外部正式成果' in text and 'SNAPSHOT_MATCH' in text and '正式Case/分派/回执/通知写入0' in text
    assert 'PRIVATE_PREVIEW' not in text and page.locator('#receipt-execution-preview-run').is_disabled()
    for width in (1200,390,320):
        page.set_viewport_size({'width':width,'height':1000});page.locator('#receipt-execution-preview-panel').scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        OUT.mkdir(parents=True,exist_ok=True);page.locator('#receipt-execution-preview-panel').screenshot(path=str(OUT/('accepted-'+str(width)+'.png')))
    page.locator('#receipt-execution-preview-release').click();page.wait_for_function('()=>receiptExecutionPreviewHandle===null&&receiptExecutionPreviewView!==null')
    assert page.evaluate('JSON.stringify({...localStorage})')=='{}' and set(requests)=={'GET'} and snapshot(f)==before and not errors


@pytest.mark.parametrize('target',['case','identity','draft'])
def test_late_response_cannot_restore_changed_context(receipt_page,tmp_path,target):
    f,p,e,page,errors,a=receipt_page;open_page(page,f,p);other,_,_=p2_setup(f,tmp_path);approved((f,other,a[2],a[3],a[4]));held=[]
    def hold(route):
        if route.request.method!='POST':route.continue_();return
        r=route.fetch();assert r.status==201;held.append((route,r))
    page.route('**/api/preparations/'+p['preparation_id']+'/receipt-execution-preview',hold)
    page.locator('#receipt-execution-preview-run').click();wait_held(page,held)
    if target=='case':open_page(page,f,other)
    elif target=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
    else:page.locator('#request-current').fill('SYNTHETIC NEW DRAFT');page.locator('#request-current').dispatch_event('input')
    page.locator('#receipt-execution-preview-result').evaluate('(e)=>e.textContent="SYNTHETIC NEW CONTEXT"');before=snapshot(f)
    held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(150)
    assert page.locator('#receipt-execution-preview-result').inner_text()=='SYNTHETIC NEW CONTEXT' and snapshot(f)==before and not errors


def test_executor_revocation_on_unknown_clears_private_view_retains_only_opaque_handle(receipt_page):
    f,p,e,page,errors,a=receipt_page;open_page(page,f,p);storage,_=lost(page,f,p)
    with f[1].connect() as c:
        f[1].lock_principal(c,'executor-a',exclusive=True)
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
    before=snapshot(f);page.locator('#receipt-execution-preview-recover').click();page.wait_for_function('()=>receiptExecutionPreviewView===null&&planView===null')
    assert page.locator('#receipt-execution-preview-panel').is_hidden() and page.locator('#receipt-execution-preview-result').inner_text()==''
    assert page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==before and not errors




def test_request_changes_cold_history_never_auto_regenerates_or_acknowledges(receipt_page):
 from test_isolated_execution_preview import add
 f,p,e,page,errors,a=receipt_page;open_page(page,f,p);page.locator('#receipt-execution-preview-decision').select_option('REQUEST_CHANGES');storage,post=lost(page,f,p)
 old=post['result'];assert old['artifact']['p4_state']=='CHANGES_REQUESTED' and not old['artifact']['local_current_at_execution']
 p=add(f,p,text='SYNTHETIC original material after request changes').json();before=snapshot(f);data=e.path.read_bytes();requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);recovered(page)
 assert page.evaluate('receiptExecutionPreviewView.result')==old and page.evaluate('receiptExecutionPreviewView.history[0].source_state')=='STALE' and set(requests)=={'GET'} and e.path.read_bytes()==data and snapshot(f)==before
 text=page.locator('#receipt-execution-preview-result').inner_text();assert 'CHANGES_REQUESTED' in text and '尚未核对' in text and 'STALE' in text and '外部正式成果' in text and '材料服务交付' in text and 'P5' in text
 assert page.locator('#receipt-execution-preview-decision').is_disabled() and page.evaluate('JSON.stringify({...localStorage})')==storage and not errors
 page.set_viewport_size({'width':320,'height':1000});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');OUT.mkdir(parents=True,exist_ok=True);page.locator('#receipt-execution-preview-panel').screenshot(path=str(OUT/'changes-stale-320.png'))


def test_never_sent_original_key_only_get_not_observed(receipt_page):
 f,p,e,page,errors,a=receipt_page;open_page(page,f,p);before=snapshot(f);posts=[]
 def abort(route):
  if route.request.method!='POST':route.continue_();return
  posts.append(route.request.headers['idempotency-key']);route.abort('failed')
 page.route('**/api/preparations/'+p['preparation_id']+'/receipt-execution-preview',abort);page.locator('#receipt-execution-preview-run').click();page.wait_for_function('()=>receiptExecutionPreviewHandle!==null&&!receiptExecutionPreviewSubmitting&&document.getElementById("receipt-execution-preview-error").textContent!==""');assert len(posts)==1
 requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);page.wait_for_function('()=>receiptExecutionPreviewView?.status==="NOT_OBSERVED"')
 assert set(requests)=={'GET'} and len(posts)==1 and page.locator('#receipt-execution-preview-run').is_disabled() and snapshot(f)==before and not errors
