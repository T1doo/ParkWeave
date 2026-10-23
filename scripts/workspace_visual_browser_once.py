"""Run29/attempt1: original collaboration/receipt/goal presentation, no product backend."""
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
BASELINE_SHA='aa6b2fb7e92853ea4b22d163260b309bb7992f74'
SOURCE_SHA256='ca6c39622746c88ef602aba8b56f95845c2b978a6a6dea68ab8275d86e705362'
PUBLIC_FILES=frozenset(('01-before-collaboration-390.png','02-after-collaboration-390.png',
 '03-before-dispatch-390.png','04-after-dispatch-390.png','05-before-receipt-390.png',
 '06-after-receipt-390.png','07-before-goals-txt-390.png','08-after-goals-txt-390.png',
 'failure-visual.png','result.json'))
FIXTURES={}

def presentation_contract(source):
    import re
    text=source.decode()
    text=re.sub(r'<style>[\s\S]*?</style>','<STYLE>',text,count=1)
    pattern=r'<div role="group" class="workflow-tools" data-workflow-tools="[^"]+" aria-label="[^"]+">([\s\S]*?)</div>'
    return re.sub(pattern,r'\1',text).encode()

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
        elif path=='/api/preparations':
            body=json.dumps(FIXTURES['list'],ensure_ascii=False).encode();kind='application/json; charset=utf-8';code=200
        elif path=='/api/preparations/'+FIXTURES['goal']['preparation_id']+'/goal-results':
            body=json.dumps(FIXTURES['goal'],ensure_ascii=False).encode();kind='application/json; charset=utf-8';code=200
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
    paths={
      'run21':('docs/F2/evidence/no-model-tail-20261022/run21/result.json','f311b24f3d77931e1e07b8c5c59f7a5613893b609bfc61f4b31038d7181db9e7'),
      'run23':('docs/F2/evidence/again-role-readback-20261022/run23/result.json','0ef683ef62243d49b397abcf064a4714ec7cacfb5f42726d2c1c676b00cf8952'),
      'TXT':('docs/F2/evidence/no-model-tail-20261022/run21/p5-unverified-case-record-pack.txt','02c87cebbfa2c60737f6cfbfeb60628181241f2c5b5399433d4b13400cae9bdd')}
    data={};REPORT['historical_fixtures']={}
    for key,(name,sha) in paths.items():
        raw=(ROOT/name).read_bytes();assert hashlib.sha256(raw).hexdigest()==sha
        data[key]=raw.decode() if key=='TXT' else json.loads(raw)
        REPORT['historical_fixtures'][key]=dict(file=name,sha256=sha,bytes=len(raw))
    old=data['run21'];preps=[p['preparation'] for p in data['run23']['fresh_roles'][0]['preparations']]
    assert len(preps)==2 and len({p['id'] for p in preps})==2
    FIXTURES.update(dispatch=old['accepted_dispatch'],receipt=old['acknowledged_receipt'],
      goal=old['exports'][0]['goal_results'],TXT=data['TXT'],
      list=dict(role='enterprise_operator',items=preps))
    assert FIXTURES['dispatch']['case_id']==FIXTURES['receipt']['step']['case_id']==FIXTURES['goal']['case_id']
    assert FIXTURES['goal']['case_id'] not in {p['case_id'] for p in preps}
    REPORT['fixture_scope']='Archived SYNTHETIC VIEW_REPLAY; run23 list is a separate scenario from run21 details, not a new connected business walk or current authority/health. List response is a field-preserving projection of two archived full preparation DTOs. Goal UI binding context is derived from its exact archived response, not a full plan DTO or valid session.'

def presentation(page,component,variant,width):
    require_operation_time(30)
    page.evaluate("""() => {clearPreparation();clearDispatch();clearReceipts();clearServiceCasePlan();
      document.querySelectorAll('[data-presentation-replay]').forEach(e=>e.remove());
      $('service').hidden=true;$('collaboration').hidden=true;$('resource').hidden=true;
      $('token').value='VIEW_REPLAY_NO_AUTHORITY';}""")
    if component=='collaboration':
        page.evaluate("() => {$('collaboration').hidden=false;document.body.dataset.workspace='collaboration';}")
        page.locator('#prep-list').click(timeout=15000)
        page.wait_for_function("() => document.querySelectorAll('#prep-items>button').length===2",timeout=15000)
        panel=page.locator('#collaboration');scenario='run23 · 两个历史资料事项'
        for row in FIXTURES['list']['items']:
            assert row['id'] in page.locator('#prep-items').text_content() and row['case_id'] in page.locator('#prep-items').text_content()
    elif component=='dispatch':
        page.evaluate('(x) => renderDispatch(x)',FIXTURES['dispatch'])
        assert page.evaluate('JSON.parse(JSON.stringify(dispatchView))')==FIXTURES['dispatch']
        panel=page.locator('#dispatch-detail');scenario='run21 · 历史已接单分派'
        assert page.locator('#dispatch-receipt').is_visible()
    elif component=='receipt':
        page.evaluate('(x) => renderReceipt(x)',FIXTURES['receipt'])
        assert page.evaluate('JSON.parse(JSON.stringify(receiptView))')==FIXTURES['receipt']
        panel=page.locator('#receipt-detail');scenario='run21 · 历史企业本地核对回执'
        assert page.locator('#receipt-ack').is_disabled() and page.locator('#receipt-correct').is_disabled() and page.locator('#receipt-reopen').is_enabled()
        assert FIXTURES['receipt']['current_receipt']['source_sha256'] in page.locator('#receipt-current').text_content()
    else:
        x=FIXTURES['goal']
        page.evaluate("""async x => {servicePlanId=x.preparation_id;
          servicePlanView={role:'enterprise_operator',read_only:false,case_id:x.case_id,run_id:x.run_id,
          plan_id:x.plan_id,revision:x.plan_revision,preparation_revision:x.preparation_revision,request_revision:x.request_revision,
          actor_ref:await coldDigest({actor_id:x.actor_id})};
          $('service-case-plan-detail').hidden=false;$('goal-results-panel').hidden=false;}""",x)
        page.locator('#goal-results-read').click(timeout=15000)
        page.wait_for_function('() => goalResultView!==null',timeout=15000)
        assert page.evaluate('JSON.parse(JSON.stringify(goalResultView))')==x
        assert page.locator('#case-record-pack-download').is_disabled()
        page.locator('#case-record-pack-generate').click(timeout=15000)
        page.wait_for_function("() => !$('case-record-pack-output').hidden&&!caseRecordPackBusy",timeout=15000)
        actual=page.locator('#case-record-pack-text').input_value()
        assert actual==FIXTURES['TXT'],'original formatter and strict projection must reproduce the complete archived TXT'
        assert page.locator('#case-record-pack-text').get_attribute('readonly') is not None and page.locator('#case-record-pack-download').is_enabled()
        panel=page.locator('#goal-results-panel');scenario='run21 · 原P5尚待企业VERIFY的目标与核对包'
        REPORT.setdefault('TXT_replay',[]).append(dict(variant=variant,width=width,bytes=len(actual.encode()),sha256=hashlib.sha256(actual.encode()).hexdigest(),scope='Original generator over exact archived GET response; not new authenticated export or download'))
    assert panel.is_visible()
    panel.evaluate("""(e,label) => {const n=document.createElement('p');n.dataset.presentationReplay='true';n.className='notice';n.textContent='SYNTHETIC VIEW_REPLAY · '+label+'；仅历史视图，不是当前业务、有效身份或授权。';e.prepend(n)}""",scenario)
    projection=panel.evaluate("""e=>({text:e.textContent,controls:[...e.querySelectorAll('button,input,textarea,select')].map(b=>({id:b.id,type:b.type,text:b.tagName==='BUTTON'?b.textContent:null,value:b.value,disabled:b.disabled,hidden:b.hidden,readOnly:b.readOnly||false,dataset:{...b.dataset}}))})""")
    rows=REPORT.setdefault('presentation_projections',[])
    first=next((r for r in rows if r['component']==component),None)
    if first:assert first['projection']==projection,'original text, IDs, values, hidden and disabled controls must match before/after and widths'
    row=dict(component=component,variant=variant,width=width,projection=projection,projection_sha256=hashlib.sha256(json.dumps(projection,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    panel.evaluate('(e)=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-24)')
    observe(page,variant+'-'+component+'-'+str(width),True)
    if variant=='after':
        tools=panel.locator('.workflow-tools')
        geometry=tools.evaluate_all("""els=>els.map(e=>({name:e.getAttribute('aria-label'),buttons:[...e.querySelectorAll(':scope>button')].filter(b=>b.getClientRects().length).map(b=>{const r=b.getBoundingClientRect();return {id:b.id,disabled:b.disabled,left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width}})}))""")
        for group in geometry:
            assert group['name']
            for a,b in zip(group['buttons'],group['buttons'][1:]):assert b['top']>=a['bottom']+9 or b['left']>=a['right']+9
        row['named_tool_geometry']=geometry
        if component=='goals-txt':
            colors=panel.locator('#goal-results-items>article').evaluate_all("""els=>els.map(e=>({state:e.dataset.goalState,text:e.querySelector('p').textContent,color:getComputedStyle(e.querySelector('p')).color,background:getComputedStyle(e.querySelector('p')).backgroundColor}))""")
            assert all(c['color']==('rgb(49, 94, 63)' if c['state']=='LOCAL_OUTPUT_VERIFIED' else 'rgb(23, 62, 53)') for c in colors)
            row['goal_state_colors']=colors
        focus=panel.locator('button:visible:not(:disabled)').first
        focus.focus();page.keyboard.press('Tab');page.keyboard.press('Shift+Tab')
        assert focus.evaluate('(e)=>document.activeElement===e')
        key=focus.evaluate("e=>({id:e.id,visible:e.matches(':focus-visible'),outline:getComputedStyle(e).outlineWidth,method:'real Tab then Shift+Tab roundtrip from an initial programmatic focus'})")
        assert key['visible'] and key['outline']=='3px';row['keyboard_focus']=key
    rows.append(row)
    if width==390:
        number={'collaboration':1,'dispatch':3,'receipt':5,'goals-txt':7}[component]+(variant=='after')
        require_operation_time(15);panel.screenshot(path=str(OUT/(str(number).zfill(2)+'-'+variant+'-'+component+'-390.png')),timeout=15000)

def run_flow(started):
    global OUT,PRIVATE,START
    os.umask(0o077);START=started;server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='29')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        load_fixtures()
        parent=subprocess.check_output(['git','rev-parse','HEAD^'],cwd=ROOT,text=True).strip()
        assert parent==BASELINE_SHA,'exact reviewed direct parent baseline required'
        after=(ROOT/'src/parkweave/web.html').read_bytes()
        before=subprocess.check_output(['git','show',BASELINE_SHA+':src/parkweave/web.html'],cwd=ROOT)
        assert hashlib.sha256(before).hexdigest()==SOURCE_SHA256
        assert presentation_contract(before)==presentation_contract(after)
        assert before.split(b'<script>',1)[1]==after.split(b'<script>',1)[1]
        REPORT['source_binding']=dict(baseline_sha=BASELINE_SHA,before_sha256=SOURCE_SHA256,after_sha256=hashlib.sha256(after).hexdigest(),
          complete_script_identical=True,outside_CSS_and_seven_static_groups_identical=True)
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
                    for component in ('collaboration','dispatch','receipt','goals-txt'):
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
        source=base.require_hosted(os.environ,run_number='29')
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
