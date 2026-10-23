"""Run30/attempt1: original dispatch/receipt index presentation, no product backend."""
import hashlib,json,os,signal,socket,subprocess,sys,tempfile,threading,time,traceback
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from scripts import fictional_park_browser_once as base
from scripts.fictional_park_restart_browser_once import installed_font_environment,verify_rendered_font
from scripts.visual_owned_launch import atomic_report,supervise

ROOT=Path(__file__).resolve().parents[1]
REPORT=dict(scope='REAL_CHROME_ORIGINAL_PAGES_PRESENTATION_NO_BACKEND',status='RUNNING',stage='START',
    product_API=False,database=False,real_model_calls=0,business_POSTs=0,requests=[],browser_requests=[],
    checks=[],font_observations=[],page_errors=[],violations=[],unexpected_GET=[],cleanup_errors=[])
OUT=None;PRIVATE=None;PAGE=None;START=0
CHECKPOINT=None
ENTERED=threading.Event();RELEASE=threading.Event()
BASELINE_SHA='4b57962c606fa07844fcc7c04976d55532826616'
SOURCE_SHA256='88f551c01ed4e86c9a12985e59117bc69f4ece2206e8588c474c8d84dcd40f15'
PUBLIC_FILES=frozenset(('01-before-dispatch-index-1200.png','02-after-dispatch-index-1200.png',
 '03-before-receipt-index-1200.png','04-after-receipt-index-1200.png',
 '05-before-dispatch-index-390.png','06-after-dispatch-index-390.png',
 '07-before-receipt-index-390.png','08-after-receipt-index-390.png','failure-visual.png','result.json'))
FIXTURES={};PHASE={'dispatch':'SUCCESS','receipt':'SUCCESS'}

def presentation_contract(before,after):
    import re
    normalize=lambda b:re.sub(rb'<style>[\s\S]*?</style>',b'<STYLE>',b,count=1)
    expected=normalize(before);actual=normalize(after)
    start=actual.index(b'\n// List reads do not authorize a write');end=actual.index(b'\nfunction clearPlanMaterialNavigation(',start)
    actual=actual[:start]+actual[end:]
    for kind,name in [('dispatch','clearDispatch'),('receipt','clearReceipts')]:
        actual=actual.replace(('function '+name+"(preservePlan=false){clearCollaborationList('"+kind+"');").encode(),('function '+name+'(preservePlan=false){').encode(),1)
        marker=("$('"+kind+"-list').onclick=").encode()
        old=next(line for line in expected.splitlines() if line.startswith(marker))
        new=("$('"+kind+"-list').onclick=()=>readCollaborationList('"+kind+"');").encode()
        assert actual.count(new)==1;actual=actual.replace(new,old,1)
        added=('<p id="'+kind+'-list-status" class="collaboration-list-status" role="status" aria-live="polite"></p>').encode()
        assert actual.count(added)==1;actual=actual.replace(added,b'',1)
    assert actual==expected,'all code and HTML outside exact list read/presentation changes must remain identical'

def timeout(*_):raise TimeoutError('90s visual work and cleanup deadline')

def checkpoint():
    if CHECKPOINT is None:return
    REPORT.setdefault('phase_timeline',[]).append(dict(stage=REPORT['stage'],seconds=time.monotonic()-START,error_type=REPORT.get('error_type')))
    try:atomic_report(CHECKPOINT,REPORT)
    except Exception as error:REPORT.setdefault('checkpoint_errors',[]).append(dict(type=type(error).__name__,errno=getattr(error,'errno',None)))

def stage(name):
    REPORT['stage']=name;checkpoint()

def require_operation_time(seconds):
    if time.monotonic()-START+seconds+5>=90:raise TimeoutError('insufficient original operation time and cleanup reserve')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        path=urlsplit(self.path).path;row=dict(method='GET',path=path);REPORT['requests'].append(row)
        if len(REPORT['requests'])>40:raise RuntimeError('40 GET allowance exhausted')
        if path in ('/before','/after'):
            body=(PRIVATE/(path[1:]+'.html')).read_bytes();kind='text/html; charset=utf-8';code=200
        elif path=='/api/run-access/status':
            body=b'{"enabled":false,"read_available":false,"scope":"PRESENTATION_REPLAY_DISABLED"}';kind='application/json';code=200
        elif path in ('/api/service-dispatches','/api/executor-receipts'):
            key='dispatch' if path=='/api/service-dispatches' else 'receipt';phase=PHASE[key];row['fixture_phase']=phase
            if phase=='LOADING':
                ENTERED.set()
                if not RELEASE.wait(15):raise TimeoutError('controlled list loading was not released')
            value=FIXTURES[key+'_list'];code=200
            if phase=='EMPTY':value={**value,'items':[],'has_older_records':True,'access_filtered':1}
            elif phase=='DENIED':value={'detail':'SYNTHETIC_FAULT_CURRENT_READ_REFUSED'};code=403
            elif phase=='ERROR':value={'detail':'SYNTHETIC_FAULT_SERVER_FAILURE'};code=500
            elif phase=='MALFORMED':value={**value,'items':None}
            elif phase=='BLOCKED_FAULT':value={**value,'items':[{**value['items'][0],'case_cancelled':True,'case_reconciling':True,'case_write_blocked':True}]}
            body=json.dumps(value,ensure_ascii=False).encode();kind='application/json; charset=utf-8'
        elif path=='/api/preparations/'+FIXTURES['dispatch']['preparation_id']+'/dispatch':
            body=json.dumps(FIXTURES['dispatch'],ensure_ascii=False).encode();kind='application/json; charset=utf-8';code=200
        elif path=='/api/executor-receipts/'+FIXTURES['receipt']['step']['id']:
            body=json.dumps(FIXTURES['receipt'],ensure_ascii=False).encode();kind='application/json; charset=utf-8';code=200
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
        stage('CHROME_SANDBOX');require_operation_time(15)
        try:
            browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=font_env,timeout=15000)
        except BaseException as error:
            REPORT['status']='FAIL';REPORT['error_type']=type(error).__name__;REPORT['error']=str(error)
            checkpoint() # Preserve the primary launch failure before SDK teardown.
            raise
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
    require_operation_time(30)
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
    require_operation_time(5 if font else 1)
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
    require_operation_time(15)
    page.evaluate('() => window.scrollTo(0,0)');page.screenshot(path=str(OUT/name),full_page=True,timeout=15000)

def load_fixtures():
    path=ROOT/'docs/F2/evidence/no-model-tail-20261022/run21/result.json';raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='f311b24f3d77931e1e07b8c5c59f7a5613893b609bfc61f4b31038d7181db9e7'
    old=json.loads(raw);d=old['accepted_dispatch'];r=old['acknowledged_receipt'];step=r['step']
    FIXTURES.update(dispatch=d,receipt=r,
      dispatch_list=dict(scope='SYNTHETIC_INTERNAL_DISPATCH_ONLY',role=d['role'],items=[dict(id=d['dispatch_id'],preparation_id=d['preparation_id'],goal=d['goal'])],has_older_records=False,access_filtered=0),
      receipt_list=dict(scope='SYNTHETIC_ASSIGNED_EXECUTOR_RECEIPT_ONLY',role=r['role'],items=[dict(id=step['id'],goal=step['goal'],state=step['state'],revision=step['revision'],case_cancelled=r['case_cancelled'],case_reconciling=r['case_reconciling'],case_write_blocked=r['case_write_blocked'])],has_older_records=False,access_filtered=0))
    REPORT['historical_fixture']=dict(file=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),case_id=d['case_id'],dispatch_id=d['dispatch_id'],receipt_step_id=step['id'],scope='Run21 exact archived details projected to the existing minimal index DTO contract; not an archived original HTTP list response or current authorization. Controlled EMPTY/403/500/malformed/blocked states are explicit FAULT injection only.')

def index_feedback(page,kind,phase,expected):
    require_operation_time(15);PHASE[kind]=phase
    page.locator('#'+kind+'-list').click(timeout=15000)
    page.wait_for_function("([kind,state])=>document.getElementById(kind+'-list-status').dataset.state===state",arg=[kind,expected],timeout=15000)
    status=page.locator('#'+kind+'-list-status');assert status.is_visible() and status.inner_text()
    assert page.locator('#'+kind+'-list').is_enabled() and page.locator('#'+kind+'-items').get_attribute('aria-busy')=='false'
    count=page.locator('#'+kind+'-items>button').count()
    assert count==(1 if expected=='READY' else 0)
    if phase=='EMPTY':assert '范围' in status.inner_text() and '更早' in page.locator('#'+kind+'-items').inner_text() and '读取条件' in page.locator('#'+kind+'-items').inner_text()
    if phase=='DENIED':assert page.evaluate('dispatchView===null&&receiptView===null')
    REPORT.setdefault('feedback_faults',[]).append(dict(kind=kind,phase=phase,state=expected,width=page.viewport_size['width'],text=status.inner_text(),cards=count,scope='CONTROLLED_PRESENTATION_FAULT_NOT_A_REAL_UPSTREAM_AUTHORITY_DECISION'))

def presentation(page,component,variant,width):
    require_operation_time(30);kind=component
    page.evaluate("() => {clearPreparation();clearReceipts();$('service').hidden=true;$('collaboration').hidden=false;$('resource').hidden=true;document.body.dataset.workspace='collaboration';$('token').value='VIEW_REPLAY_NO_AUTHORITY';}")
    PHASE[kind]='SUCCESS'
    if variant=='after':ENTERED.clear();RELEASE.clear();PHASE[kind]='LOADING'
    page.locator('#'+kind+'-list').click(timeout=15000)
    if variant=='after':
        assert ENTERED.wait(15),'original list GET did not enter the owned fixture'
        status=page.locator('#'+kind+'-list-status');assert status.get_attribute('data-state')=='LOADING' and status.inner_text()
        assert page.locator('#'+kind+'-list').is_disabled() and page.locator('#'+kind+'-items').get_attribute('aria-busy')=='true'
        REPORT.setdefault('loading',[]).append(dict(kind=kind,width=width,state='LOADING',button_disabled=True,aria_busy=True))
        RELEASE.set()
        page.wait_for_function("kind=>document.getElementById(kind+'-list-status').dataset.state==='READY'",arg=kind,timeout=15000)
    else:page.wait_for_function("kind=>document.querySelectorAll('#'+kind+'-items>button').length===1",arg=kind,timeout=15000)
    target=page.locator('#'+kind+'-items');button=target.locator(':scope>button');assert button.count()==1
    item=FIXTURES[kind+'_list']['items'][0];text=button.inner_text()
    assert item['id'] in text and item['goal'] in text
    if kind=='dispatch':assert item['preparation_id'] in text
    if variant=='after':
        assert '含历史' in text and '只读打开' in text
        assert '进入原记录后核对' in text if kind=='dispatch' else '企业已本地核对回执' in text
        focus=button;focus.focus();page.keyboard.press('Tab');page.keyboard.press('Shift+Tab')
        assert focus.evaluate("e=>document.activeElement===e&&e.matches(':focus-visible')&&getComputedStyle(e).outlineWidth==='3px'")
    target.evaluate("(e,label)=>{const n=document.createElement('p');n.className='notice';n.dataset.presentationReplay='true';n.textContent='SYNTHETIC VIEW_REPLAY · '+label+'索引；既有归档记录的合同投影，不是当前身份、责任或办理权限。';e.prepend(n)}",kind)
    target.evaluate('(e)=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-24)')
    observe(page,variant+'-'+kind+'-index-'+str(width),True)
    ids=target.locator(':scope>button').evaluate_all("es=>es.map(e=>({text:e.textContent,disabled:e.disabled}))")
    REPORT.setdefault('indexes',[]).append(dict(kind=kind,variant=variant,width=width,original_DTO=FIXTURES[kind+'_list'],visible_cards=ids,read_only=True))
    number={(1200,'dispatch'):1,(1200,'receipt'):3,(390,'dispatch'):5,(390,'receipt'):7}[(width,kind)]+(variant=='after')
    require_operation_time(15);target.screenshot(path=str(OUT/(str(number).zfill(2)+'-'+variant+'-'+kind+'-index-'+str(width)+'.png')),timeout=15000)
    if variant=='after':
        old=len(REPORT['requests']);button.click(timeout=15000)
        name='dispatch-detail' if kind=='dispatch' else 'receipt-detail'
        page.locator('#'+name).wait_for(state='visible',timeout=15000)
        actual=page.evaluate('JSON.parse(JSON.stringify('+('dispatchView' if kind=='dispatch' else 'receiptView')+'))')
        assert actual==FIXTURES[kind]
        expected='/api/preparations/'+item['preparation_id']+'/dispatch' if kind=='dispatch' else '/api/executor-receipts/'+item['id']
        assert [x['path'] for x in REPORT['requests'][old:]]==[expected]
        REPORT.setdefault('original_open_reads',[]).append(dict(kind=kind,width=width,path=expected,original_DTO_equal=True))
        if kind=='receipt':
            old=len(REPORT['requests']);button.click(timeout=15000)
            page.wait_for_function('() => receiptView!==null',timeout=15000)
            assert page.evaluate('receiptView.step.id')==item['id'] and [x['path'] for x in REPORT['requests'][old:]]==[expected]
            REPORT.setdefault('retained_receipt_reopen',[]).append(dict(width=width,exact_path=expected,note='Same retained visible card can reopen after detail generation changes; A-to-B separately covered by Node oracle.'))
        for phase,state in [('EMPTY','EMPTY'),('DENIED','DENIED'),('SUCCESS','READY')]:index_feedback(page,kind,phase,state)
        if width==1200:index_feedback(page,kind,'ERROR','ERROR')
        if width==390:index_feedback(page,kind,'MALFORMED','ERROR')
        if width==390 and kind=='receipt':
            index_feedback(page,kind,'BLOCKED_FAULT','READY');card=page.locator('#receipt-items>button')
            assert all(x in card.inner_text() for x in ('已取消','核对中','新办理暂停','企业已本地核对'))
            card.scroll_into_view_if_needed(timeout=15000);observe(page,'after-receipt-controlled-blocked-390',True)
            REPORT['blocked_fault_scope']='Injected list metadata only, not a real cancellation or upstream record change; original state remains LOCAL_ACKNOWLEDGED alongside all three warnings.'
    PHASE[kind]='SUCCESS'

def run_flow(started):
    global OUT,PRIVATE,START
    os.umask(0o077);START=started;server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='30')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        load_fixtures()
        parent=subprocess.check_output(['git','rev-parse','HEAD^'],cwd=ROOT,text=True).strip()
        assert parent==BASELINE_SHA,'exact reviewed direct parent baseline required'
        after=(ROOT/'src/parkweave/web.html').read_bytes()
        before=subprocess.check_output(['git','show',BASELINE_SHA+':src/parkweave/web.html'],cwd=ROOT)
        assert hashlib.sha256(before).hexdigest()==SOURCE_SHA256;presentation_contract(before,after)
        REPORT['source_binding']=dict(baseline_sha=BASELINE_SHA,before_sha256=SOURCE_SHA256,after_sha256=hashlib.sha256(after).hexdigest(),
          list_read_feedback_and_presentation_changes=True,all_other_HTML_and_business_script_identical=True)
        for variant,data in [('before',before),('after',after)]: (PRIVATE/(variant+'.html')).write_bytes(data)
        env=dict(os.environ)
        for key,name in [('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')]:
            p=PRIVATE/name;p.mkdir(mode=0o700);env[key]=str(p)
        env=installed_font_environment(env,PRIVATE/'fontconfig',REPORT)
        signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(90-(time.monotonic()-START))))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
        with owned_browser(env) as browser:
            base.resource.verify_sandbox(browser,REPORT);REPORT['browser_version']=browser.version
            for width in (1200,390):
                for variant in ('before','after'):
                    stage(variant.upper()+'_PRESENTATION_'+str(width));context,page=open_page(browser,origin,'/'+variant,width)
                    for component in ('dispatch','receipt'):
                        stage(variant.upper()+'_'+component.upper()+'_'+str(width));presentation(page,component,variant,width)
                    context.close()
            assert len(REPORT['requests'])<40 and len(REPORT['browser_requests'])<40
            assert not any(REPORT[k] for k in ('page_errors','violations','unexpected_GET','business_POSTs'))
            REPORT['status']='PASS';stage('COMPLETE')
    except BaseException as error:
        REPORT['status']='FAIL'
        if 'error' in REPORT and (REPORT['error_type'],REPORT['error'])!=(type(error).__name__,str(error)):
            REPORT.setdefault('later_errors',[]).append(dict(type=type(error).__name__,error=str(error)))
        REPORT.setdefault('error_type',type(error).__name__);REPORT.setdefault('error',str(error));traceback.print_exc()
        checkpoint()
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
        REPORT['worker_final']=True;checkpoint()
    return 0 if REPORT['status']=='PASS' and not REPORT.get('checkpoint_errors') else 1

def worker_main(path):
    global CHECKPOINT
    hand=json.loads(sys.stdin.buffer.readline(4096))
    if hand['parent_pid']!=os.getppid() or hand['worker_pid']!=os.getpid() or not 0<=time.monotonic()-hand['started']<85:
        raise RuntimeError('owned worker handshake refused')
    CHECKPOINT=Path(path)
    return run_flow(hand['started'])

def main():
    started=time.monotonic();os.umask(0o077)
    report=dict(REPORT);public=None
    try:
        source=base.require_hosted(os.environ,run_number='30')
        report['source_sha']=source
        private=Path(tempfile.mkdtemp(prefix='parkweave-visual-supervisor-'))
        state=private/'worker-state.json'
        owned=supervise([sys.executable,'-B','-m','scripts.workspace_visual_browser_once','--owned-worker',str(state)],
            env=dict(os.environ),cwd=ROOT,directory=private,started=started)
        report['owned_launch']=owned
        if state.exists():
            if state.stat().st_size>2*1024*1024:raise RuntimeError('owned worker report exceeds2MiB')
            report=json.loads(state.read_text())
        report['owned_launch']=owned
        if (private/'worker-output.log').exists():
            with (private/'worker-output.log').open('rb') as stream:output=stream.read(256*1024+1)
            report['worker_output_truncated']=len(output)>256*1024
            output=output[:256*1024]
            report['worker_output_captured_sha256']=hashlib.sha256(output).hexdigest()
            report['worker_output_text']=output.decode('utf-8',errors='backslashreplace')
        if report.get('source_sha')!=source or not report.get('worker_final') or report.get('worker_output_truncated') or owned['status']!='CLEANUP_CONFIRMED' or owned['operation_status']!='PASS':
            report['status']='FAIL';report.setdefault('error_type','OwnedWorkerFailure');report.setdefault('error','Owned worker failed or its process scope could not be confirmed closed')
        report['work_and_cleanup_seconds']=time.monotonic()-started
        if report['work_and_cleanup_seconds']>90:report['status']='FAIL'
        candidate=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate'
        if not candidate.exists():candidate.mkdir(mode=0o700,exist_ok=False)
        public=candidate
    except BaseException as error:
        report['status']='FAIL';report.setdefault('error_type',type(error).__name__);report.setdefault('error',str(error));traceback.print_exc()
    return base.finish_report(report,[],public,started=started,allowed_names=PUBLIC_FILES)

if __name__=='__main__':raise SystemExit(worker_main(sys.argv[2]) if len(sys.argv)==3 and sys.argv[1]=='--owned-worker' else main())
