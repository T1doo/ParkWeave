"""Run34/attempt1: entry and pending-receipt visual refinement; no product backend."""
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
BASELINE_SHA='f3f67f6e1a936172d7646508d9e768ada3313aa2'
SOURCE_SHA256='c9072217785ea44e362f7f36e3ee101d960781595881253d0586a5ae13fc22d3'
GUIDE_SHA256='f79d265b3e941dc976ddcb2c66c692cff24eabb2a4e82ba1f874a0f674cfb62d'
PUBLIC_FILES=frozenset(tuple(f'{i:02}-{variant}-{scene}-{width}.png'
    for width,offset in ((1200,0),(390,4))
    for scene,part in (('entry',0),('receipt',2))
    for variant,i in (('before',offset+part+1),('after',offset+part+2)))+('failure-visual.png','result.json'))
FIXTURES={}

def presentation_contract(before,after,guide=False):
    import re
    normalize=lambda b:re.sub(rb'<style>[\s\S]*?</style>',b'<STYLE>',b,count=1)
    expected=normalize(before);actual=normalize(after)
    if guide:
        label='<label for="scenario">演示事项</label>'.encode()
        assert actual.count(label)==1;actual=actual.replace(label,b'',1)
    else:
        # Only these intact original top-level sections move into the task desk.
        ids=(b'existing-preparation-entry',b'formal-preparation-entry',b'template-instance-entry',b'service')
        blocks=[]
        for name in ids:
            match=re.search(rb'<section id="'+name+rb'"[^\n]*\n',expected)
            assert match is not None
            blocks.append(match.group(0))
        service=blocks[3];first=service.index(b'<article id="cold-entry">')
        cut=service.index('<hr><h2>服务资料准备</h2>'.encode())
        assert service.endswith(b'</section>\n')
        # Prioritize the already-supported ordinary prep path, keeping every
        # original subtree and warning. No optional consumer is activated.
        ordinary=service[:first]+service[cut+4:-len(b'</section>\n')]+b'<hr>'+service[first:cut]+b'</section>\n'
        old=b''.join(blocks)
        new=blocks[2]+b'<div class="entry-workbench">\n'+ordinary+blocks[0]+blocks[1]+b'</div>\n'
        assert expected.count(old)==1 and actual.count(new)==1
        actual=actual.replace(new,old,1)
    assert expected==actual,'only CSS, the exact intact section permutation/wrapper and scenario label are allowed'
    assert before.split(b'<script>',1)[1]==after.split(b'<script>',1)[1]

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
        if path in ('/before','/after','/guide-after'):
            body=(PRIVATE/(path[1:]+'.html')).read_bytes();kind='text/html; charset=utf-8';code=200
        elif path=='/api/run-access/status':
            body=b'{"enabled":false,"read_available":false,"scope":"PRESENTATION_REPLAY_DISABLED"}';kind='application/json';code=200
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
    if row['width']>=1100 and row['nav'] and label.startswith('after'):
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
    old=json.loads(raw);FIXTURES['receipt']=old['submitted_receipt']
    assert FIXTURES['receipt']['step']['state']=='RECEIPT_RECORDED' and not FIXTURES['receipt']['can_submit']
    REPORT['historical_fixture']=dict(file=str(path.relative_to(ROOT)),sha256=hashlib.sha256(raw).hexdigest(),
        field='submitted_receipt',scope='Exact archived SYNTHETIC executor receipt pending enterprise acknowledgement; original renderer replay only, not current health/identity/authority or a new business request.')

def presentation(page,scene,variant,width):
    require_operation_time(30)
    if scene=='entry':panel=page.locator('#service')
    else:
        page.evaluate("""x=>{clearPreparation();clearDispatch();clearReceipts();
            $('service').hidden=true;$('collaboration').hidden=true;$('resource').hidden=true;
            $('token').value='VIEW_REPLAY_NO_AUTHORITY';renderReceipt(x);}""",FIXTURES['receipt'])
        assert page.evaluate('JSON.parse(JSON.stringify(receiptView))')==FIXTURES['receipt']
        panel=page.locator('#receipt-detail')
        assert page.locator('#receipt-submit-button').is_disabled()
        assert '待企业核对' in page.locator('#receipt-summary').inner_text()
        assert FIXTURES['receipt']['current_receipt']['source_sha256'] in page.locator('#receipt-current').inner_text()
        panel.evaluate("""e=>{const n=document.createElement('p');n.className='notice';n.textContent='SYNTHETIC VIEW_REPLAY · 归档执行者回执待企业核对，仅历史视图，不是当前身份、业务或授权。';e.prepend(n)}""")
    projection=panel.evaluate("""e=>{const walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT),text=[];while(walker.nextNode()){const s=walker.currentNode.textContent;if(s.trim())text.push(s)}return {text_nodes:text.sort(),controls:[...e.querySelectorAll('button,input,textarea,select')].map(b=>({id:b.id,form:b.form?.id||null,tag:b.tagName,type:b.type,text:b.tagName==='BUTTON'?b.textContent:null,value:b.value,disabled:b.disabled,hidden:b.hidden,readOnly:b.readOnly||false,dataset:{...b.dataset}})).sort((a,b)=>JSON.stringify(a).localeCompare(JSON.stringify(b)))}}""")
    rows=REPORT.setdefault('presentation_projections',[])
    first=next((r for r in rows if r['scene']==scene),None)
    if first:assert first['projection']==projection,'original text, values, gates and control identity differ'
    row=dict(scene=scene,variant=variant,width=width,projection=projection)
    if scene=='receipt':panel.evaluate('e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-16)')
    observe(page,variant+'-'+scene+'-'+str(width),True)
    if variant=='after':
        focus=panel.locator('button:visible:not(:disabled)').first
        focus.focus();page.keyboard.press('Tab');page.keyboard.press('Shift+Tab')
        assert focus.evaluate("e=>document.activeElement===e&&e.matches(':focus-visible')&&getComputedStyle(e).outlineWidth==='3px'")
        row['keyboard_focus']='real Tab / Shift+Tab roundtrip with 3px visible outline'
        if scene=='receipt':
            colors=page.locator('#receipt-summary').evaluate("e=>({color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor,text:e.textContent})")
            assert colors['background']=='rgb(242, 246, 245)' and colors['color']=='rgb(55, 84, 74)'
            row['pending_summary_neutral']=colors
        page.emulate_media(reduced_motion='reduce')
        assert focus.evaluate("e=>getComputedStyle(e).transitionDuration==='0s'&&getComputedStyle(e).animationName==='none'")
        page.emulate_media(reduced_motion='no-preference');row['reduced_motion']='transitions and animation disabled'
    rows.append(row)
    number=(0 if width==1200 else 4)+(0 if scene=='entry' else 2)+(1 if variant=='before' else 2)
    require_operation_time(15)
    if scene=='entry':page.evaluate('() => window.scrollTo(0,0)')
    else:panel.evaluate('e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-16)')
    if variant=='after':
        ids=['prep-catalog'] if scene=='entry' else ['receipt-summary','receipt-refresh']
        viewport=page.evaluate("""ids=>ids.map(id=>{const e=document.getElementById(id),r=e.getBoundingClientRect();return {id,top:r.top,bottom:r.bottom,visible:!!e.getClientRects().length,height:innerHeight}})""",ids)
        assert all(x['visible'] and x['top']>=0 and x['bottom']<=x['height'] for x in viewport),viewport
        row['core_task_first_viewport']=viewport
        if scene=='entry':
            warning=page.locator('#service > h2').nth(1).evaluate("e=>{const p=e.nextElementSibling,r=p.getBoundingClientRect();return {text:p.textContent,top:r.top,bottom:r.bottom,height:innerHeight}}")
            assert '资格未判定，外部服务未受理' in warning['text']
            assert 0<=warning['top'] and warning['bottom']<=warning['height'],warning
            row['ordinary_entry_warning_visible']=warning
    target=page if scene=='entry' else panel
    kwargs={'full_page':False} if scene=='entry' else {}
    target.screenshot(path=str(OUT/f'{number:02}-{variant}-{scene}-{width}.png'),timeout=15000,**kwargs)


def guide_observation(browser,origin,width):
    context,page=open_page(browser,origin,'/guide-after',width)
    try:
        assert page.locator('label[for="scenario"]').inner_text()=='演示事项'
        assert page.locator('#workspace-open').is_disabled()
        assert page.locator('#status').get_attribute('data-tone')=='neutral'
        page.locator('#sessions').set_input_files(dict(name='invalid.json',mimeType='application/json',buffer=b'{'))
        page.wait_for_function("()=>$('status').dataset.tone==='error'",timeout=15000)
        assert page.locator('#workspace-open').is_disabled() and page.locator('#status').inner_text()
        color=page.locator('#status').evaluate('e=>getComputedStyle(e).color')
        assert color=='rgb(141, 55, 46)'
        observe(page,'after-guide-error-'+str(width),True)
        REPORT.setdefault('guide_DOM_only',[]).append(dict(width=width,label='explicit scenario label',status='ERROR',disabled=True,screenshot=False))
    finally:context.close()

def run_flow(started):
    global OUT,PRIVATE,START
    os.umask(0o077);START=started;server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='34')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        load_fixtures()
        parent=subprocess.check_output(['git','rev-parse','HEAD^'],cwd=ROOT,text=True).strip()
        assert parent==BASELINE_SHA,'exact reviewed direct parent baseline required'
        after=(ROOT/'src/parkweave/web.html').read_bytes()
        before=subprocess.check_output(['git','show',BASELINE_SHA+':src/parkweave/web.html'],cwd=ROOT)
        assert hashlib.sha256(before).hexdigest()==SOURCE_SHA256;presentation_contract(before,after)
        guide_before=subprocess.check_output(['git','show',BASELINE_SHA+':src/parkweave/park_demo_web.html'],cwd=ROOT)
        guide_after=(ROOT/'src/parkweave/park_demo_web.html').read_bytes()
        assert hashlib.sha256(guide_before).hexdigest()==GUIDE_SHA256;presentation_contract(guide_before,guide_after,True)
        (PRIVATE/'guide-after.html').write_bytes(guide_after)
        REPORT['source_binding']=dict(baseline_sha=BASELINE_SHA,before_sha256=SOURCE_SHA256,after_sha256=hashlib.sha256(after).hexdigest(),guide_before_sha256=GUIDE_SHA256,guide_after_sha256=hashlib.sha256(guide_after).hexdigest(),complete_scripts_identical=True,allowed_markup_changes='exact ordinary prep promotion, intact service/recovery/source section permutation and wrapper; one scenario label',all_other_markup_identical=True)
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
                    for component in ('entry','receipt'):
                        stage(variant.upper()+'_'+component.upper()+'_'+str(width));presentation(page,component,variant,width)
                    context.close()
                guide_observation(browser,origin,width)
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
        signal.alarm(0)
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
        source=base.require_hosted(os.environ,run_number='34')
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
