"""Run26/attempt1: original pages, presentation review, no product backend."""
import hashlib,json,os,signal,socket,tempfile,threading,time,traceback
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from scripts import fictional_park_browser_once as base
from scripts.fictional_park_restart_browser_once import installed_font_environment,verify_rendered_font

ROOT=Path(__file__).resolve().parents[1]
REPORT=dict(scope='REAL_CHROME_ORIGINAL_PAGES_PRESENTATION_NO_BACKEND',status='RUNNING',stage='START',
    product_API=False,database=False,real_model_calls=0,business_POSTs=0,requests=[],browser_requests=[],
    checks=[],font_observations=[],page_errors=[],violations=[],unexpected_GET=[],cleanup_errors=[])
OUT=None;PRIVATE=None;PAGE=None;START=0
ENTERED=threading.Event();RELEASE=threading.Event()
DENIED='/api/preparations/00000000-0000-4000-8000-000000000001/entry'
SOURCE={
 'workspace':('web.html',b'/* Workspace refinement: presentation only;', '1174b0f0d835cd46f6562db9360fb8e4d680701c43300c2cefe7042077b02d33'),
 'guide':('park_demo_web.html',b'/* Same visual system as the original workspace;', '48dc8a8dec295b6fe11ec373ff18b90e4a1dab147a28c62ebe43f9385f12f402')}
PUBLIC_FILES=frozenset(('01-before-service-wide.png','02-after-service-wide.png','03-before-historical-plan-wide.png',
 '04-after-historical-plan-wide.png','05-before-guide-wide.png','06-after-guide-wide.png',
 '07-after-historical-plan-narrow.png','08-after-guide-narrow.png','failure-visual.png','result.json'))

def timeout(*_):raise TimeoutError('90s visual work and cleanup deadline')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        path=urlsplit(self.path).path;row=dict(method='GET',path=path);REPORT['requests'].append(row)
        if len(REPORT['requests'])>40:raise RuntimeError('40 GET allowance exhausted')
        if path in ('/before','/after','/before-guide','/after-guide'):
            body=(PRIVATE/(path[1:]+'.html')).read_bytes();kind='text/html; charset=utf-8';code=200
        elif path=='/api/run-access/status':
            body=b'{"enabled":false,"read_available":false,"scope":"PRESENTATION_REPLAY_DISABLED"}';kind='application/json';code=200
        elif path==DENIED:
            ENTERED.set()
            if not RELEASE.wait(15):raise TimeoutError('controlled refusal was not released')
            body=b'{"detail":"record unavailable or authorization denied"}';kind='application/json';code=403
        elif path=='/favicon.ico':body=b'';kind='image/x-icon';code=204
        else:
            REPORT['unexpected_GET'].append(path);body=b'{}';kind='application/json';code=404
        row['status']=code
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)
    def do_POST(self):REPORT['business_POSTs']+=1;self.send_error(405,'No writes in presentation review')

@contextmanager
def owned_browser(font_env):
    with sync_playwright() as pw:
        REPORT['stage']='CHROME_SANDBOX'
        browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=font_env,timeout=15000)
        try:yield browser
        except BaseException:
            if PAGE is not None and not PAGE.is_closed():
                try:PAGE.screenshot(path=str(OUT/'failure-visual.png'),timeout=5000)
                except BaseException as e:REPORT['failure_screenshot_error']=type(e).__name__
            raise
        finally:
            try:browser.close();REPORT['browser_close']='CLOSED'
            except Exception as e:REPORT['cleanup_errors'].append('browser:'+type(e).__name__)

def open_page(browser,origin,path,width):
    global PAGE
    context=browser.new_context(viewport={'width':width,'height':1000},service_workers='block')
    def boundary(route):
        request=route.request;a=urlsplit(request.url);b=urlsplit(origin)
        allowed=(a.scheme,a.netloc)==(b.scheme,b.netloc) and request.method=='GET' and len(REPORT['browser_requests'])<40
        REPORT['browser_requests'].append(dict(method=request.method,path=a.path,allowed=allowed))
        if allowed:route.continue_()
        else:
            REPORT['violations'].append(dict(method=request.method,path=a.path))
            if request.method=='POST':REPORT['business_POSTs']+=1
            route.abort()
    context.route('**/*',boundary);page=context.new_page();PAGE=page
    page.on('pageerror',lambda error:REPORT['page_errors'].append(str(error)))
    response=page.goto(origin+path,wait_until='load',timeout=15000)
    assert response.status==200 and response.body()==(PRIVATE/(path[1:]+'.html')).read_bytes()
    return context,page

def observe(page,label,font=False):
    row=page.evaluate("""() => {const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}};return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,visibleButtons:[...document.querySelectorAll('button')].filter(e=>e.getClientRects().length).map(e=>({id:e.id,height:e.getBoundingClientRect().height,disabled:e.disabled})),nav:document.querySelector('.workspace-nav')?rect(document.querySelector('.workspace-nav')):null,content:document.querySelector('.session-panel')?rect(document.querySelector('.session-panel')):null}}""")
    row['label']=label;REPORT['checks'].append(row)
    assert row['documentWidth']<=row['width'] and row['height']<12000,row
    assert all(x['height']>=44 for x in row['visibleButtons']),row
    if row['width']>=1040 and row['nav'] and label.startswith('after'):
        assert row['nav']['right']+16<=row['content']['left'],row
    if font:
        verify_rendered_font(page,REPORT)
        REPORT['font_observations'].append(dict(label=label,width=row['width'],nodes=REPORT['installed_CJK_font']['visible_node_font_usage']))
    return row

def shot(page,name):
    page.evaluate('() => window.scrollTo(0,0)');page.screenshot(path=str(OUT/name),full_page=True,timeout=15000)

def historical_plan(page,variant,width):
    # Reuse an exact already-public synthetic observation. This is a rendering
    # replay, never a current authority/health response or business restoration.
    file=ROOT/'docs/F2/evidence/again-role-readback-20261022/run23/result.json'
    raw=file.read_bytes();assert hashlib.sha256(raw).hexdigest()=='0ef683ef62243d49b397abcf064a4714ec7cacfb5f42726d2c1c676b00cf8952'
    plan=json.loads(raw)['fresh_roles'][0]['plans'][0]
    REPORT['historical_fixture']=dict(source='run23 fresh_roles[0].plans[0]',sha256=hashlib.sha256(raw).hexdigest(),
        case_id=plan['case_id'],run_id=plan['run_id'],plan_id=plan['plan_id'],purpose='HISTORICAL_SYNTHETIC_VIEW_REPLAY_ONLY_NOT_CURRENT_HEALTH')
    page.evaluate('(x) => {servicePlanId=x.preparation_id;renderServiceCasePlan(x)}',plan)
    panel=page.locator('#service-case-plan-detail');assert panel.is_visible()
    text=panel.text_content();fingerprint=hashlib.sha256(text.encode()).hexdigest()
    rows=REPORT.setdefault('historical_rendering',[])
    if rows:assert rows[0]['text_sha256']==fingerprint
    ids=page.locator('#service-plan-steps > article').evaluate_all('(els) => els.map(e=>e.dataset.serviceStepId)')
    assert ids==[s['id'] for s in plan['steps']]
    rows.append(dict(variant=variant,width=width,text_sha256=fingerprint,step_ids=ids,source_state=plan['state']))
    page.evaluate("() => window.scrollTo(0,document.getElementById('service-case-plan-detail').getBoundingClientRect().top+scrollY-24)")
    observe(page,variant+'-historical-plan-'+str(width),True)
    name='07-after-historical-plan-narrow.png' if width==390 else ('03-before-historical-plan-wide.png' if variant=='before' else '04-after-historical-plan-wide.png')
    panel.screenshot(path=str(OUT/name),timeout=15000)

def main():
    global OUT,PRIVATE,START
    os.umask(0o077);START=time.monotonic();server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='26')
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        REPORT['source_binding']={}
        for name,(file,marker,expected) in SOURCE.items():
            after=(ROOT/'src/parkweave'/file).read_bytes();assert after.count(marker)==1
            prefix,tail=after.split(marker,1);before=prefix+b'</style>'+tail.split(b'</style>',1)[1]
            assert hashlib.sha256(before).hexdigest()==expected
            assert before.split(b'</style>',1)[1]==after.split(b'</style>',1)[1]
            REPORT['source_binding'][name]=dict(before_sha256=expected,after_sha256=hashlib.sha256(after).hexdigest(),outside_style_identical=True)
            for variant,data in [('before',before),('after',after)]:
                (PRIVATE/(variant+('-guide' if name=='guide' else '')+'.html')).write_bytes(data)
        env=dict(os.environ)
        for key,name in [('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')]:
            p=PRIVATE/name;p.mkdir(mode=0o700);env[key]=str(p)
        env=installed_font_environment(env,PRIVATE/'fontconfig',REPORT)
        signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(90-(time.monotonic()-START))))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
        with owned_browser(env) as browser:
            base.resource.verify_sandbox(browser,REPORT);REPORT['browser_version']=browser.version
            for variant in ('before','after'):
                REPORT['stage']=variant.upper()+'_WORKSPACE_WIDE';context,page=open_page(browser,origin,'/'+variant,1200)
                observe(page,variant+'-service-wide',True);shot(page,'01-before-service-wide.png' if variant=='before' else '02-after-service-wide.png')
                if variant=='after':
                    for tab in ('collaboration','resource'):
                        page.locator('[data-tab='+tab+']').click();assert page.locator('#'+tab).is_visible()
                        assert page.locator('[data-tab='+tab+']').get_attribute('aria-current')=='page'
                        observe(page,'after-'+tab+'-wide',True)
                    page.locator('[data-tab=service]').click();page.locator('#existing-preparation-id').fill('00000000-0000-4000-8000-000000000001')
                    page.locator('#token').fill('SYNTHETIC_PRESENTATION_REPLAY_SESSION');page.locator('#existing-preparation-read').click()
                    page.wait_for_function("() => document.getElementById('existing-preparation-status').textContent.includes('正在只读核对')",timeout=15000)
                    REPORT['loading_text']=page.locator('#existing-preparation-status').text_content();assert ENTERED.wait(5)
                    RELEASE.set();page.wait_for_function("() => document.getElementById('existing-preparation-status').textContent.length>0&&!document.getElementById('existing-preparation-status').textContent.includes('正在只读核对')",timeout=15000)
                    REPORT['refusal_text']=page.locator('#existing-preparation-status').text_content();assert page.locator('#prep-detail').is_hidden()
                    observe(page,'after-controlled403-wide')
                    page.locator('#existing-preparation-read').focus();page.keyboard.press('Tab')
                    REPORT['keyboard_focus']=page.evaluate("() => ({id:document.activeElement.id,outline:getComputedStyle(document.activeElement).outlineWidth,visible:document.activeElement.matches(':focus-visible')})")
                    assert REPORT['keyboard_focus']['visible'] and REPORT['keyboard_focus']['outline']=='3px'
                    page.locator('#token').fill('')
                    page.locator('[data-tab=service]').click()
                historical_plan(page,variant,1200)
                context.close()
            REPORT['stage']='AFTER_WORKSPACE_NARROW';context,page=open_page(browser,origin,'/after',390)
            for tab in ('service','collaboration','resource'):
                page.locator('[data-tab='+tab+']').click();observe(page,'after-'+tab+'-narrow',True)
            page.locator('[data-tab=service]').click();historical_plan(page,'after',390);context.close()
            for variant in ('before','after'):
                REPORT['stage']=variant.upper()+'_GUIDE_WIDE';context,page=open_page(browser,origin,'/'+variant+'-guide',1200)
                assert all(page.locator('[data-role='+role+']').is_disabled() for role in ('enterprise','specialist','executor'))
                observe(page,variant+'-guide-wide',True);shot(page,'05-before-guide-wide.png' if variant=='before' else '06-after-guide-wide.png');context.close()
            REPORT['stage']='AFTER_GUIDE_NARROW';context,page=open_page(browser,origin,'/after-guide',390)
            page.locator('#sessions').set_input_files(dict(name='not-a-session.json',mimeType='application/json',buffer=b'{}'))
            page.wait_for_function("() => document.getElementById('status').textContent.includes('不是本次演示')",timeout=15000)
            REPORT['invalid_file_text']=page.locator('#status').text_content();assert page.locator('#workspace-open').is_disabled()
            observe(page,'after-guide-invalid-file-narrow',True);shot(page,'08-after-guide-narrow.png');context.close()
            assert len(REPORT['requests'])<40 and len(REPORT['browser_requests'])<40
            assert not any(REPORT[k] for k in ('page_errors','violations','unexpected_GET','business_POSTs'))
            REPORT['status']='PASS';REPORT['stage']='COMPLETE'
    except BaseException as error:
        REPORT['status']='FAIL';REPORT['error_type']=type(error).__name__;REPORT['error']=str(error);traceback.print_exc()
    finally:
        signal.alarm(0);RELEASE.set()
        if server:
            try:
                port=server.server_port;server.shutdown();server.server_close();thread.join(timeout=5);assert not thread.is_alive()
                try:
                    with socket.create_connection(('127.0.0.1',port),timeout=.3):raise AssertionError('owned listener remains')
                except ConnectionRefusedError:REPORT['listener_after_cleanup']='REFUSED'
            except Exception as error:REPORT['cleanup_errors'].append('server:'+type(error).__name__)
        REPORT['elapsed_seconds']=time.monotonic()-START
        if REPORT['cleanup_errors'] or REPORT.get('browser_close')!='CLOSED' or REPORT.get('listener_after_cleanup')!='REFUSED' or REPORT['elapsed_seconds']>90:REPORT['status']='FAIL'
    return base.finish_report(REPORT,[],OUT,started=START,allowed_names=PUBLIC_FILES)

if __name__=='__main__':raise SystemExit(main())
