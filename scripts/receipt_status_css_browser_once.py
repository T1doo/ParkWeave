"""Exact run24/attempt1: real sandboxed Chrome CSS states, synthetic GET replay only."""
import hashlib,json,os,signal,socket,sys,tempfile,threading,time,traceback
from contextlib import contextmanager
from scripts import fictional_park_browser_once as base
from scripts.fictional_park_restart_browser_once import installed_font_environment, verify_rendered_font
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from datetime import datetime,timedelta,timezone
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=None;PRIVATE=None;LAST_PAGE=None
REPORT={'kind':'REAL_BROWSER_UI_CSS_WITH_SYNTHETIC_GET_REPLAY','status':'RUNNING','stage':'START',
        'business_POSTs':0,'business_API':False,'database':False,'real_model_calls':0,'screen_reader_announcement':'NOT_TESTED',
        'UI_work_cleanup_limit_seconds':90,'publication_absolute_limit_seconds':360,'scope':'CSS_ONLY_NOT_AT35_OR_BUSINESS_RECOVERY',
        'requests':[],'browser_requests':[],'browser_errors':[],'checks':[],'cleanup_errors':[]}
START=0
def expired(signum,frame):raise TimeoutError('90-second UI work/cleanup deadline')
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
        if len(REPORT['requests'])>40:raise RuntimeError('40 GET replay allowance exhausted')
        if path in ('/before','/after'):
            content=(PRIVATE/(path[1:]+'.html')).read_bytes();kind='text/html; charset=utf-8';code=200
        elif path=='/api/run-access/status':
            content=b'{"enabled":false,"read_available":false,"scope":"SYNTHETIC_CSS_GET_REPLAY_DISABLED"}';kind='application/json';code=200
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

METRICS="""() => {const e=document.getElementById('receipt-submit-status'),s=getComputedStyle(e),r=e.getBoundingClientRect();return {exists:!!e,ariaLive:e.getAttribute('aria-live'),text:e.textContent,height:r.height,width:r.width,paddingTop:s.paddingTop,paddingBottom:s.paddingBottom,marginTop:s.marginTop,marginBottom:s.marginBottom,borderLeft:s.borderLeftWidth,background:s.backgroundColor,display:s.display,overflowX:s.overflowX,overflowY:s.overflowY,clientHeight:e.clientHeight,scrollHeight:e.scrollHeight,pageOverflow:document.documentElement.scrollWidth>innerWidth,withinViewport:r.left>=0&&r.right<=innerWidth,verticallyVisible:r.top>=0&&r.bottom<=innerHeight};}"""
def metrics(page,label,empty):
    page.locator('#receipt-summary' if empty else '#receipt-submit-status').scroll_into_view_if_needed(timeout=15000)
    m=page.evaluate(METRICS);m.update(label=label,viewport=page.viewport_size);REPORT['checks'].append(m)
    assert m['exists'] and m['ariaLive']=='polite' and m['display']!='none',m
    if empty:
        assert m['text']=='' and m['height']==0 and all(m[k]=='0px' for k in ('paddingTop','paddingBottom','marginTop','marginBottom','borderLeft')),m
        assert m['background']=='rgba(0, 0, 0, 0)',m
    else:
        assert m['text'] and m['height']>28 and m['borderLeft']=='3px' and m['paddingTop']=='14px',m
        assert m['scrollHeight']<=m['clientHeight']+1 and m['withinViewport'] and m['verticallyVisible'] and not m['pageOverflow'],m
    return m
def screenshot(page,name):
    page.locator('#receipt-submit-status' if page.locator('#receipt-submit-status').text_content() else '#receipt-summary').scroll_into_view_if_needed(timeout=15000)
    if name=='03-after-unknown-narrow.png':verify_rendered_font(page,REPORT)
    page.screenshot(path=str(OUT/name))
def open_receipt(browser,base,variant,width):
    global MODE,LAST_PAGE
    MODE='initial';context=browser.new_context(viewport=dict(width=width,height=1000),service_workers='block')
    def boundary(route):
        request=route.request;p=urlsplit(request.url);allowed=p.netloc==urlsplit(base).netloc and request.method=='GET' and len(REPORT['browser_requests'])<40
        REPORT['browser_requests'].append(dict(method=request.method,path=p.path,allowed=allowed))
        if allowed:route.continue_()
        else:
            REPORT.setdefault('violations',[]).append(dict(method=request.method,path=p.path))
            if request.method=='POST':REPORT['business_POSTs']+=1
            route.abort()
    context.route('**/*',boundary)
    page=context.new_page();LAST_PAGE=page;page.on('pageerror',lambda e:REPORT['browser_errors'].append(str(e)))
    response=page.goto(base+'/'+variant,wait_until='load',timeout=15000)
    assert response.status==200 and response.body()==(PRIVATE/(variant+'.html')).read_bytes()
    page.locator('#token').fill('SYNTHETIC_UI_REPLAY_SESSION')
    page.locator('[data-tab=collaboration]').click()
    page.evaluate('(id)=>loadReceipt(id)',H['step'])
    assert page.locator('#receipt-detail').is_visible()
    return context,page
def fill_handle(page):
    page.evaluate("""h=>{h.expires=Date.now()+600000;const n=receiptSubmitStorage+h.actor+'.'+h.step;localStorage.setItem(n,JSON.stringify(h));receiptSubmitHandle=receiptSubmitRead(receiptView);receiptSubmitControls();}""",H)

PUBLIC_FILES=frozenset(('01-before-empty-desktop.png','02-after-empty-desktop.png','03-after-unknown-narrow.png','04-after-recovered-narrow.png','05-after-cleared-narrow.png','failure-receipt-status.png','result.json'))

@contextmanager
def browser_session(font_env):
    # Capture and close while the Playwright transport is still alive. Preserve
    # the primary error even if either evidence capture or browser close fails.
    with sync_playwright() as pw:
        REPORT['stage']='SANDBOXED_BROWSER_LAUNCH'
        browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=font_env,timeout=15000)
        try:
            yield browser
        except BaseException:
            if OUT is not None and LAST_PAGE is not None and not LAST_PAGE.is_closed():
                try:LAST_PAGE.screenshot(path=str(OUT/'failure-receipt-status.png'),timeout=5000)
                except BaseException as shot_error:REPORT['failure_screenshot_error']=type(shot_error).__name__
            raise
        finally:
            try:browser.close();REPORT['browser_close']='CLOSED'
            except Exception as e:REPORT['cleanup_errors'].append('browser:'+type(e).__name__)

def main():
    global OUT,PRIVATE,LAST_PAGE,START,MODE
    os.umask(0o077);START=time.monotonic()
    server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='24')
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-css-replay-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        after=(ROOT/'src/parkweave/web.html').read_bytes();rule=b'#receipt-submit-status:empty{margin:0;padding:0;border:0;background:transparent}\n'
        assert after.count(rule)==1;before=after.replace(rule,b'',1)
        assert hashlib.sha256(before).hexdigest()=='1a009ce52a31e463643cf5768ae474fcbeb78c15e9fe3443e1976f6155745bb4'
        assert hashlib.sha256(after).hexdigest()=='1174b0f0d835cd46f6562db9360fb8e4d680701c43300c2cefe7042077b02d33'
        assert before.split(b'</style>',1)[1]==after.split(b'</style>',1)[1]
        REPORT['source_binding']=dict(before_sha256=hashlib.sha256(before).hexdigest(),after_sha256=hashlib.sha256(after).hexdigest(),outside_style_identical=True,exact_rule=rule.decode())
        for name,data in (('before',before),('after',after)):(PRIVATE/(name+'.html')).write_bytes(data)
        font_env=dict(os.environ)
        for key,name in (('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')):
            directory=PRIVATE/name;directory.mkdir(mode=0o700);font_env[key]=str(directory)
        font_env=installed_font_environment(font_env,PRIVATE/'fontconfig',REPORT,extra_text=json.dumps([VIEW,CURRENT,PROOF],ensure_ascii=False))
        signal.signal(signal.SIGALRM,expired);signal.alarm(max(1,int(90-(time.monotonic()-START))))
        REPORT['stage']='LOOPBACK_SERVER';server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        with browser_session(font_env) as browser:
            base.resource.verify_sandbox(browser,REPORT)
            REPORT['browser_version']=browser.version
            REPORT['real_browser']=True
            REPORT['stage']='BEFORE_EMPTY';context,page=open_receipt(browser,origin,'before',1200)
            m=page.evaluate(METRICS);assert m['text']=='' and m['height']==28 and m['borderLeft']=='3px',m
            REPORT['checks'].append(dict(label='before-empty',**m));screenshot(page,'01-before-empty-desktop.png');context.close()
            for width in (1200,390):
                REPORT['stage']='AFTER_'+str(width);context,page=open_receipt(browser,origin,'after',width)
                metrics(page,'after-empty',True)
                if width==1200:screenshot(page,'02-after-empty-desktop.png')
                fill_handle(page);page.locator('#receipt-submit-recover').click();page.wait_for_function('() => !receiptSubmitBusy',timeout=15000)
                assert page.evaluate('receiptSubmitProof===null&&receiptSubmitHandle!==null')
                assert '待核对' in metrics(page,'after-unknown',False)['text']
                if width==390:screenshot(page,'03-after-unknown-narrow.png')
                MODE='committed';page.locator('#receipt-submit-recover').click();page.wait_for_function('() => !receiptSubmitBusy',timeout=15000)
                assert page.evaluate('receiptSubmitProof!==null')
                page.locator('#receipt-submit-release').click();page.wait_for_function('() => !receiptSubmitBusy',timeout=15000)
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
    except BaseException as e:
        REPORT['status']='FAIL';REPORT['error_type']=type(e).__name__;REPORT['error']=str(e);traceback.print_exc()
    finally:
        signal.alarm(0)
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
    return base.finish_report(REPORT,[],OUT,started=START,allowed_names=PUBLIC_FILES)

if __name__=='__main__':raise SystemExit(main())
