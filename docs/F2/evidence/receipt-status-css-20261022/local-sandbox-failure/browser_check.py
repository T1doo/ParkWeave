"""One real sandboxed Chromium CSS check; synthetic GET replay, no business API/PG."""
import hashlib,json,os,signal,socket,sys,threading,time,traceback
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from datetime import datetime,timedelta,timezone
from playwright.sync_api import sync_playwright

OUT=Path(__file__).resolve().parent
ROOT=Path('/workspace/ParkWeave')
REPORT={'kind':'REAL_BROWSER_UI_CSS_WITH_SYNTHETIC_GET_REPLAY','status':'RUNNING','stage':'START',
        'business_POSTs':0,'business_API':False,'database':False,'screen_reader_announcement':'NOT_TESTED',
        'requests':[],'browser_requests':[],'browser_errors':[],'checks':[],'cleanup_errors':[]}
START=time.monotonic()
def expired(signum,frame):raise TimeoutError('90-second absolute CSS browser deadline')
signal.signal(signal.SIGALRM,expired);signal.alarm(90)
def uid(n):return '00000000-0000-4000-8000-'+str(n).zfill(12)
H=dict(v=1,action='SUBMIT',actor='a'*64,preparation=uid(1),case=uid(2),run=uid(3),step=uid(4),key=uid(5),revision=1,preparation_revision=4)
REC=dict(id=uid(7),step_id=H['step'],actor_id='executor-a',source_kind='SYNTHETIC',source_sha256='b'*64,
         version=1,source_label='SYNTHETIC GET 回放样式夹具',text='仅核对回执提示的真实浏览器呈现，不代表业务提交。',created_at='2026-10-22T00:00:00+00:00')
STEP=dict(id=H['step'],executor_id='executor-a',preparation_id=H['preparation'],case_id=H['case'],run_id=H['run'],
          preparation_revision=4,revision=1,state='AWAITING_RECEIPT',goal='合成人工办理回执 · GET 回放样式核对')
VIEW=dict(scope='SYNTHETIC_ASSIGNED_EXECUTOR_RECEIPT_ONLY',role='service_executor',actor_ref=H['actor'],can_submit=True,
          is_current_step=True,dependency='CURRENT',step=STEP,current_receipt=None,receipt_history=[],history=[],
          assignment_contract='CASE_STEP_ASSIGNMENT_V1',assignment_valid_until=(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat())
PROOF=dict(scope=VIEW['scope'],actor_ref=H['actor'],step_id=H['step'],preparation_id=H['preparation'],case_id=H['case'],
           run_id=H['run'],expected_revision=1,preparation_revision=4,request_key=H['key'],historical_only=True,
           read_only=True,automatically_replayed=False,case_goal_completed=False,status='COMMITTED',
           event=dict(id=uid(6),action='SUBMIT',revision=2,receipt_id=REC['id'],receipt_version=1,receipt_sha256=REC['source_sha256']))
CURRENT={**VIEW,'step':{**STEP,'revision':2,'state':'RECEIPT_RECORDED'},'can_submit':False,'current_receipt':REC,
         'receipt_history':[REC],'history':[dict(action='SUBMIT',revision=2,payload=dict(step_id=H['step'],actor_id='executor-a',receipt_id=REC['id'],receipt_sha256=REC['source_sha256']))]}
MODE='initial'
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        path=urlsplit(self.path).path;REPORT['requests'].append(dict(method='GET',path=path,mode=MODE))
        if path in ('/before','/after'):
            content=(OUT/(path[1:]+'.html')).read_bytes();kind='text/html; charset=utf-8';code=200
        elif path=='/api/executor-receipts/'+H['step']+'/submit-recovery':
            value=PROOF if MODE=='committed' else {**PROOF,'status':'NOT_OBSERVED','event':None}
            content=json.dumps(value,ensure_ascii=False).encode();kind='application/json';code=200
        elif path=='/api/executor-receipts/'+H['step']:
            content=json.dumps(CURRENT if MODE=='committed' else VIEW,ensure_ascii=False).encode();kind='application/json';code=200
        elif path=='/favicon.ico':content=b'';kind='image/x-icon';code=204
        else:
            REPORT.setdefault('unexpected_GET',[]).append(path);content=b'{}';kind='application/json';code=404
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(content)))
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(content)
    def do_POST(self):
        REPORT['business_POSTs']+=1;REPORT['requests'].append(dict(method='POST',path=urlsplit(self.path).path))
        self.send_error(405,'No writes in CSS replay')

METRICS="""() => {const e=document.getElementById('receipt-submit-status'),s=getComputedStyle(e),r=e.getBoundingClientRect();return {exists:!!e,ariaLive:e.getAttribute('aria-live'),text:e.textContent,height:r.height,width:r.width,paddingTop:s.paddingTop,paddingBottom:s.paddingBottom,marginTop:s.marginTop,marginBottom:s.marginBottom,borderLeft:s.borderLeftWidth,background:s.backgroundColor,display:s.display,overflowX:s.overflowX,overflowY:s.overflowY,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight,pageOverflow:document.documentElement.scrollWidth>innerWidth,withinViewport:r.left>=0&&r.right<=innerWidth};}"""
def metrics(page,label,empty):
    m=page.evaluate(METRICS);m.update(label=label,viewport=page.viewport_size);REPORT['checks'].append(m)
    assert m['exists'] and m['ariaLive']=='polite' and m['display']!='none',m
    if empty:
        assert m['text']=='' and m['height']==0 and all(m[k]=='0px' for k in ('paddingTop','paddingBottom','marginTop','marginBottom','borderLeft')),m
        assert m['background']=='rgba(0, 0, 0, 0)',m
    else:
        assert m['text'] and m['height']>28 and m['borderLeft']=='3px' and m['paddingTop']=='14px',m
        assert m['scrollHeight']<=m['clientHeight']+1 and m['withinViewport'] and not m['pageOverflow'],m
    return m
def screenshot(page,name):
    page.locator('#receipt-detail').scroll_into_view_if_needed(timeout=15000)
    page.screenshot(path=str(OUT/name))
def open_receipt(browser,base,variant,width):
    global MODE
    MODE='initial';context=browser.new_context(viewport=dict(width=width,height=1000),service_workers='block')
    def boundary(route):
        request=route.request;p=urlsplit(request.url);allowed=p.netloc==urlsplit(base).netloc and request.method=='GET'
        REPORT['browser_requests'].append(dict(method=request.method,path=p.path,allowed=allowed))
        if allowed:route.continue_()
        else:
            REPORT.setdefault('violations',[]).append(dict(method=request.method,path=p.path))
            if request.method=='POST':REPORT['business_POSTs']+=1
            route.abort()
    context.route('**/*',boundary)
    page=context.new_page();page.on('pageerror',lambda e:REPORT['browser_errors'].append(str(e)))
    response=page.goto(base+'/'+variant,wait_until='load',timeout=15000)
    assert response.status==200 and response.body()==(OUT/(variant+'.html')).read_bytes()
    page.locator('#token').fill('SYNTHETIC_UI_REPLAY_SESSION')
    page.locator('[data-tab=collaboration]').click()
    page.evaluate('(id)=>loadReceipt(id)',H['step'])
    assert page.locator('#receipt-detail').is_visible()
    return context,page
def fill_handle(page):
    page.evaluate("""h=>{h.expires=Date.now()+600000;const n=receiptSubmitStorage+h.actor+'.'+h.step;localStorage.setItem(n,JSON.stringify(h));receiptSubmitHandle=receiptSubmitRead(receiptView);receiptSubmitControls();}""",H)

server=None;thread=None;browser=None
try:
    REPORT['stage']='LOOPBACK_SERVER';server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base='http://127.0.0.1:'+str(server.server_port)
    with sync_playwright() as pw:
        REPORT['stage']='SANDBOXED_BROWSER_LAUNCH'
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,chromium_sandbox=True,args=['--enable-automation'],timeout=15000)
        REPORT['browser_version']=browser.version
        args=browser.new_browser_cdp_session().send('Browser.getBrowserCommandLine')['arguments']
        assert not any(x.split('=')[0] in {'--no-sandbox','--disable-setuid-sandbox','--disable-seccomp-filter-sandbox','--disable-namespace-sandbox','--disable-gpu-sandbox','--no-zygote','--disable-web-security'} for x in args)
        REPORT['chrome_arguments']=args
        REPORT['stage']='BEFORE_EMPTY';context,page=open_receipt(browser,base,'before',1200)
        m=page.evaluate(METRICS);assert m['text']=='' and m['height']==28 and m['borderLeft']=='3px',m
        REPORT['checks'].append(dict(label='before-empty',**m));screenshot(page,'01-before-empty-desktop.png');context.close()
        for width in (1200,390):
            REPORT['stage']='AFTER_'+str(width);context,page=open_receipt(browser,base,'after',width)
            metrics(page,'after-empty',True)
            if width==1200:screenshot(page,'02-after-empty-desktop.png')
            fill_handle(page);page.locator('#receipt-submit-recover').click();page.wait_for_function('!receiptSubmitBusy',timeout=15000)
            assert page.evaluate('receiptSubmitProof===null&&receiptSubmitHandle!==null')
            assert '待核对' in metrics(page,'after-unknown',False)['text']
            if width==390:screenshot(page,'03-after-unknown-narrow.png')
            MODE='committed';page.locator('#receipt-submit-recover').click();page.wait_for_function('!receiptSubmitBusy',timeout=15000)
            assert page.evaluate('receiptSubmitProof!==null')
            page.locator('#receipt-submit-release').click();page.wait_for_function('!receiptSubmitBusy',timeout=15000)
            assert page.evaluate('receiptSubmitHandle===null&&!receiptSubmitStoredPending()')
            assert metrics(page,'after-recovered',False)['text']=='已核对原人工提交并读取当前回执；未重发提交、核对或步骤验证。'
            if width==390:screenshot(page,'04-after-recovered-narrow.png')
            page.evaluate('clearReceipts()');page.evaluate('(x)=>{receiptId=x.step.id;renderReceipt(x)}',CURRENT)
            metrics(page,'after-cleared',True)
            if width==390:screenshot(page,'05-after-cleared-narrow.png')
            context.close()
        assert REPORT['business_POSTs']==0 and not REPORT['browser_errors'] and not REPORT.get('unexpected_GET') and not REPORT.get('violations')
        assert time.monotonic()-START<90
        REPORT['status']='PASS';REPORT['stage']='COMPLETE'
        browser.close();browser=None
except BaseException as e:
    REPORT['status']='FAIL';REPORT['error_type']=type(e).__name__;REPORT['error']=str(e);traceback.print_exc()
finally:
    signal.alarm(0)
    if browser:
        try:browser.close()
        except Exception as e:REPORT['cleanup_errors'].append('browser:'+type(e).__name__)
    if server:
        try:
            port=server.server_port;server.shutdown();server.server_close();thread.join(timeout=5);assert not thread.is_alive()
            try:
                with socket.create_connection(('127.0.0.1',port),timeout=.3):raise AssertionError('owned loopback listener remains')
            except ConnectionRefusedError:REPORT['listener_after_cleanup']='REFUSED'
        except Exception as e:REPORT['cleanup_errors'].append('server:'+type(e).__name__)
    if REPORT['cleanup_errors']:REPORT['status']='FAIL'
    REPORT['elapsed_seconds']=time.monotonic()-START
    if REPORT['elapsed_seconds']>90:
        REPORT['status']='FAIL';REPORT['deadline_exceeded']=True
    (OUT/'result.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=REPORT['status'],stage=REPORT['stage'],POSTs=REPORT['business_POSTs'],checks=len(REPORT['checks']),elapsed_seconds=REPORT['elapsed_seconds'],cleanup_errors=REPORT['cleanup_errors'])))
sys.exit(0 if REPORT['status']=='PASS' else 1)
