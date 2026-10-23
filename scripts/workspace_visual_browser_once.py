"""Run28/attempt1: original content presentation, no product backend."""
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
DENIED='/api/preparations/00000000-0000-4000-8000-000000000001/entry'
BASELINE_SHA='82db2929f4b3e7ec9f0065c42febfff6a9be9a37'
SOURCE={
 'workspace':('web.html','f740106eef67c603a56cbeb1280c8dd71a5a954af93df026f1336a20cf0ad31d'),
 'guide':('park_demo_web.html','ae8e7f929a56e8029cb58540b4ce01768d1a319321c429320a26ae69c5fccef5')}
PUBLIC_FILES=frozenset(('01-before-plan-wide.png','02-after-plan-wide.png','03-before-plan-narrow.png',
 '04-after-plan-narrow.png','05-before-guide-wide.png','06-after-guide-wide.png',
 '07-guide-error-narrow.png','08-guide-success-narrow.png','failure-visual.png','result.json'))

def business_script(source):
    script=source.split(b'<script>',1)[1].split(b'</script>',1)[0]
    start=script.index(b'function renderServiceCasePlan(');end=script.index(b'\nasync function loadServiceCasePlan',start)
    script=script[:start]+b'<CASE_PLAN_PRESENTATION>'+script[end:]
    start=script.index(b'function clearServiceCasePlan(');end=script.index(b'\n',start)
    return script[:start]+b'<CASE_PLAN_PRESENTATION_CLEAR>'+script[end:]

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

def historical_plan(page,variant,width):
    require_operation_time(30)
    # Exact historical synthetic view only. No current health or authority claim.
    file=ROOT/'docs/F2/evidence/again-role-readback-20261022/run23/result.json'
    raw=file.read_bytes();assert hashlib.sha256(raw).hexdigest()=='0ef683ef62243d49b397abcf064a4714ec7cacfb5f42726d2c1c676b00cf8952'
    plan=json.loads(raw)['fresh_roles'][0]['plans'][0]
    REPORT['historical_fixture']=dict(source='run23 fresh_roles[0].plans[0]',sha256=hashlib.sha256(raw).hexdigest(),
        case_id=plan['case_id'],run_id=plan['run_id'],plan_id=plan['plan_id'],purpose='HISTORICAL_SYNTHETIC_VIEW_REPLAY_ONLY_NOT_CURRENT_HEALTH')
    page.evaluate('(x) => {servicePlanId=x.preparation_id;renderServiceCasePlan(x)}',plan)
    panel=page.locator('#service-case-plan-detail');assert panel.is_visible()
    assert page.evaluate('JSON.parse(JSON.stringify(servicePlanView))')==plan
    projection=page.locator('#service-plan-steps > article').evaluate_all("""els=>els.map(e=>({id:e.dataset.serviceStepId,adapter:e.dataset.serviceAdapter,
      name:e.querySelector('strong').textContent,paragraphs:[...e.children].filter(n=>n.tagName==='P'&&!n.classList.contains('service-step-reference')).map(n=>n.textContent),
      full_id:e.querySelector('.service-step-reference code')?.textContent||e.querySelector('small').textContent.replace('稳定步骤编号 ',''),
      buttons:[...e.querySelectorAll('button')].map(b=>({text:b.textContent,disabled:b.disabled,step:b.dataset.serviceStep||null,action:b.dataset.serviceAction||null,open:b.dataset.serviceOpen||null}))}))""")
    assert [x['id'] for x in projection]==[x['id'] for x in plan['steps']]
    assert all(x['full_id']==x['id'] for x in projection)
    fingerprint=hashlib.sha256(json.dumps(projection,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    rows=REPORT.setdefault('historical_rendering',[])
    if rows:assert rows[0]['projection_sha256']==fingerprint
    page.evaluate("() => window.scrollTo(0,document.getElementById('service-case-plan-detail').getBoundingClientRect().top+scrollY-24)")
    observation=observe(page,variant+'-historical-plan-'+str(width),True)
    row=dict(variant=variant,width=width,projection_sha256=fingerprint,step_ids=[x['id'] for x in projection],source_state=plan['state'],document_height=observation['height'],font_scope='visible checked nodes near the plan heading; not every ID/action or whole panel glyph')
    if variant=='after':
        require_operation_time(30)
        contract=page.locator('details[data-plan-disclosure=contract]');history=page.locator('#service-plan-history-details')
        assert not contract.evaluate('(e)=>e.open') and not history.evaluate('(e)=>e.open')
        assert contract.locator('summary').is_visible() and history.locator('summary').is_visible()
        outside=page.locator('#service-plan-coverage').evaluate("e=>[...e.children].filter(n=>n.tagName!=='DETAILS').map(n=>n.textContent).join(' / ')")
        assert '正式服务发布、审批及原Case真实目标完成仍未证明' in outside
        for item in plan.get('current_preview',{}).get('goal_coverage',[]):
            if item['status']!='SUPPORTED_PREVIEW':assert item['goal'] in outside
        geometry=page.locator('#service-plan-steps > article').evaluate_all("""els=>els.map(e=>{const r=e.querySelector('.service-step-reference').getBoundingClientRect(),a=e.querySelector('.service-step-actions').getBoundingClientRect(),buttons=[...e.querySelectorAll('.service-step-actions>button')].map(b=>{const r=b.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}});return {reference_bottom:r.bottom,actions_top:a.top,buttons}})""")
        for card in geometry:
            assert card['actions_top']>=card['reference_bottom']+9
            for a,b in zip(card['buttons'],card['buttons'][1:]):assert b['top']>=a['bottom']+9 or b['left']>=a['right']+9
        reads=len(REPORT['requests']);browser_reads=len(REPORT['browser_requests'])
        contract.locator('summary').focus();page.keyboard.press('Enter');assert contract.evaluate('(e)=>e.open')
        focus=contract.locator('summary').evaluate("e=>({visible:e.matches(':focus-visible'),outline:getComputedStyle(e).outlineWidth})")
        assert focus['visible'] and focus['outline']=='3px'
        expanded=contract.inner_text()
        for item in plan.get('current_preview',{}).get('goal_coverage',[]):
            if item['status']=='SUPPORTED_PREVIEW':assert item['goal'] in expanded
        history.locator('summary').click(timeout=15000);assert history.evaluate('(e)=>e.open')
        expanded_history=history.inner_text()
        for event in plan.get('events',[]):assert ('计划版本 '+str(event['revision'])) in expanded_history
        preview_articles=contract.locator(':scope > article').all_text_contents();history_text=page.locator('#service-plan-history').text_content()
        for index,original in enumerate(preview_articles):assert contract.locator(':scope > article').nth(index).inner_text()==original
        assert page.locator('#service-plan-history').is_visible()
        contract.locator('summary').click(timeout=15000);history.locator('summary').click(timeout=15000)
        assert not contract.evaluate('(e)=>e.open') and not history.evaluate('(e)=>e.open')
        assert len(REPORT['requests'])==reads and len(REPORT['browser_requests'])==browser_reads
        row.update(disclosures_expanded_and_closed=True,disclosure_GETs=0,geometry=geometry,keyboard_focus=focus)
        REPORT['keyboard_focus']=focus
    else:
        preview_articles=page.locator('#service-plan-coverage > article').all_text_contents();history_text=page.locator('#service-plan-history').text_content()
    if rows:
        assert preview_articles==rows[0]['rendered_preview_articles'] and history_text==rows[0]['rendered_history_text']
    row.update(rendered_preview_articles=preview_articles,rendered_history_text=history_text,rendered_history_sha256=hashlib.sha256(history_text.encode()).hexdigest())
    rows.append(row)
    if width==390 and variant=='after':
        before=next(x for x in rows if x['width']==390 and x['variant']=='before')
        assert row['document_height']<before['document_height']
        REPORT['narrow_height_change']=dict(before=before['document_height'],after=row['document_height'],saved=before['document_height']-row['document_height'])
    page.evaluate("() => window.scrollTo(0,document.getElementById('service-case-plan-detail').getBoundingClientRect().top+scrollY-24)")
    name={('before',1200):'01-before-plan-wide.png',('after',1200):'02-after-plan-wide.png',('before',390):'03-before-plan-narrow.png',('after',390):'04-after-plan-narrow.png'}[(variant,width)]
    panel.screenshot(path=str(OUT/name),timeout=15000)

def guide_state(page,label,tone):
    status=page.locator('#status');assert status.is_visible() and status.get_attribute('data-tone')==tone
    value=status.evaluate("e=>({text:e.textContent,color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor,height:e.clientHeight,scrollHeight:e.scrollHeight,width:e.clientWidth,scrollWidth:e.scrollWidth})")
    assert value['color']=={'neutral':'rgb(82, 99, 93)','error':'rgb(141, 55, 46)','success':'rgb(40, 91, 61)'}[tone]
    assert value['text'] and value['scrollHeight']<=value['height'] and value['scrollWidth']<=value['width']
    REPORT.setdefault('guide_states',[]).append(dict(label=label,tone=tone,**value));observe(page,label,True)

def run_flow(started):
    global OUT,PRIVATE,START
    os.umask(0o077);START=started;server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='28')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        REPORT['source_binding']={}
        parent=subprocess.check_output(['git','rev-parse','HEAD^'],cwd=ROOT,text=True).strip()
        assert parent==BASELINE_SHA,'exact reviewed direct parent baseline required'
        for name,(file,expected) in SOURCE.items():
            after=(ROOT/'src/parkweave'/file).read_bytes()
            before=subprocess.check_output(['git','show',BASELINE_SHA+':src/parkweave/'+file],cwd=ROOT)
            assert hashlib.sha256(before).hexdigest()==expected
            if name=='workspace':assert business_script(before)==business_script(after)
            REPORT['source_binding'][name]=dict(baseline_sha=BASELINE_SHA,before_sha256=expected,after_sha256=hashlib.sha256(after).hexdigest(),
                presentation_changes=True,business_script_unchanged_except_case_plan_render_and_clear=(name=='workspace'))
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
            for width in (1200,390):
                for variant in ('before','after'):
                    stage(variant.upper()+'_HISTORICAL_PLAN_'+str(width));context,page=open_page(browser,origin,'/'+variant,width)
                    historical_plan(page,variant,width);context.close()
            for variant in ('before','after'):
                stage(variant.upper()+'_GUIDE_WIDE');context,page=open_page(browser,origin,'/'+variant+'-guide',1200)
                assert all(page.locator('[data-role='+role+']').is_disabled() for role in ('enterprise','specialist','executor'))
                if variant=='after':guide_state(page,'guide-neutral-wide','neutral')
                else:observe(page,'before-guide-wide',True)
                shot(page,'05-before-guide-wide.png' if variant=='before' else '06-after-guide-wide.png');context.close()
            stage('AFTER_GUIDE_NARROW');context,page=open_page(browser,origin,'/after-guide',390)
            page.locator('#sessions').set_input_files(dict(name='not-a-session.json',mimeType='application/json',buffer=b'{}'))
            page.wait_for_function("() => document.getElementById('status').dataset.tone==='error'",timeout=15000)
            assert page.locator('#workspace-open').is_disabled();guide_state(page,'guide-invalid-file-narrow','error');shot(page,'07-guide-error-narrow.png')
            roles=('enterprise','specialist','executor','second_enterprise','second_specialist','second_executor')
            memory_file=json.dumps({role:str(i)*43 for i,role in enumerate(roles)}).encode()
            REPORT['guide_success_scope']='FORMAT_VALID_SYNTHETIC_MEMORY_FILE_ONLY_NOT_A_REAL_SESSION_OR_AUTHORITY'
            page.locator('#sessions').set_input_files(dict(name='SYNTHETIC-memory-only.json',mimeType='application/json',buffer=memory_file))
            page.wait_for_function("() => document.getElementById('status').dataset.tone==='success'",timeout=15000)
            assert page.locator('#workspace-open').is_enabled() and all(page.locator('[data-role='+role+']').is_disabled() for role in roles[:3])
            guide_state(page,'guide-memory-file-success-narrow','success');shot(page,'08-guide-success-narrow.png')
            REPORT['guide_event_scope']='Synthetic pagehide dispatched to the original listener and programmatic input clear; not real navigation, bfcache or native chooser cancellation'
            page.evaluate("() => window.dispatchEvent(new Event('pagehide'))")
            assert page.locator('#workspace-open').is_disabled();guide_state(page,'guide-injected-pagehide-neutral-narrow','neutral')
            page.locator('#sessions').set_input_files([]);guide_state(page,'guide-programmatic-selection-cleared-neutral-narrow','neutral');context.close()
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
        source=base.require_hosted(os.environ,run_number='28')
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
