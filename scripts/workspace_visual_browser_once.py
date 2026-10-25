"""Run45/attempt1: paired record details; historical synthetic views, no backend."""
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
REPORT=dict(scope='REAL_CHROME_RECORD_DETAILS_PAIRED_PRESENTATION_NO_BACKEND',status='RUNNING',stage='START',
    product_API=False,database=False,real_model_calls=0,business_POSTs=0,requests=[],browser_requests=[],
    checks=[],font_observations=[],page_errors=[],violations=[],unexpected_GET=[],cleanup_errors=[])
OUT=None;PRIVATE=None;PAGE=None;START=0;CHECKPOINT=None
BASELINE_SHA='baa294e5ea3894b9b54e34b8e586aef5b72300c8'
BEFORE_SHA='aef270c81545161cce694b3e24b36cf90896816a'
PAGE_NAME='web.html'
PAGE_SHA256='ea2619e143893d6b6560526d689a05bdd17215d8490da4ae7c2add8afa18a5f1'
BEFORE_SHA256='7798e0e5c08462fd98cc20382d9e429a57a58ca61bbe95513c32065c7d755884'
PNG_FILES=tuple(f'{i:02d}-{variant}-{component}-{width}.png'
    for i,(component,width,variant) in enumerate(
        ((c,w,v) for c in ('dispatch','receipt') for w in (1200,390) for v in ('before','after')),1))
PUBLIC_FILES=frozenset(PNG_FILES+('failure-visual.png','result.json'))
EXPECTED_CHANGED_PATHS=frozenset(('.github/workflows/fictional-park-browser-once.yml',
    'scripts/workspace_visual_browser_once.py','scripts/fictional_park_font_once.py'))
FIXTURE_LABEL='SYNTHETIC VIEW_REPLAY · run21历史合成视图；不是当前业务、有效身份、授权或履约证明。'
FIXTURE_PATH='docs/F2/evidence/no-model-tail-20261022/run21/result.json'
FIXTURE_SHA256='f311b24f3d77931e1e07b8c5c59f7a5613893b609bfc61f4b31038d7181db9e7'
FIXTURES={}

def presentation_contract(before,after):
    assert hashlib.sha256(before).hexdigest()==BEFORE_SHA256,'exact reviewed parent page required'
    assert hashlib.sha256(after).hexdigest()==PAGE_SHA256,'exact reviewed candidate page required'
    assert before.split(b'<script>',1)[1]==after.split(b'<script>',1)[1],'complete original script required'

def validate_source_listing(parent,changed,dirty):
    assert parent==BASELINE_SHA,'exact reviewed direct parent required'
    assert len(changed)==len(set(changed)) and set(changed)==EXPECTED_CHANGED_PATHS,'unreviewed commit paths'
    assert not dirty,'tracked or untracked workspace changes refused'

def source_contract():
    parent=subprocess.check_output(['git','rev-parse','HEAD^'],cwd=ROOT,text=True).strip()
    changed=subprocess.check_output(['git','diff','--name-only',BASELINE_SHA,'HEAD'],cwd=ROOT,text=True).splitlines()
    validate_source_listing(parent,changed,subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True))
    path='src/parkweave/'+PAGE_NAME;current=(ROOT/path).read_bytes()
    before=subprocess.check_output(['git','show',BEFORE_SHA+':'+path],cwd=ROOT)
    reviewed=subprocess.check_output(['git','show',BASELINE_SHA+':'+path],cwd=ROOT)
    presentation_contract(before,current);assert current==reviewed,'candidate product page drift'
    raw=(ROOT/FIXTURE_PATH).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==FIXTURE_SHA256,'historical synthetic fixture changed'
    data=json.loads(raw);FIXTURES.update(dispatch=data['accepted_dispatch'],receipt=data['acknowledged_receipt'])
    assert FIXTURES['dispatch']['case_id']==FIXTURES['receipt']['step']['case_id'],'paired historical Case required'
    return {'before':before,'after':current},dict(reviewed_product_sha=BASELINE_SHA,before_sha=BEFORE_SHA,
        page=PAGE_NAME,before_sha256=BEFORE_SHA256,page_sha256=PAGE_SHA256,exact_changed_paths=sorted(changed),
        fixture_path=FIXTURE_PATH,fixture_sha256=FIXTURE_SHA256,complete_script_identical=True,
        scope='Original renderer over exact archived synthetic DTOs; no app factory/API/PG or real authority')


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



# Four separate contexts load both exact pages twice. No business endpoint exists.
FIXTURE_LIMITS={'/before':2,'/after':2}
FIXTURE_READS={}

def fixture_response(uri):
    if uri=='/favicon.ico':
        count=FIXTURE_READS.get(uri,0)+1;FIXTURE_READS[uri]=count
        if count<=4:return 204,'image/x-icon',b''
    elif uri in FIXTURE_LIMITS:
        count=FIXTURE_READS.get(uri,0)+1;FIXTURE_READS[uri]=count
        if count<=FIXTURE_LIMITS[uri]:
            return 200,'text/html; charset=utf-8',(PRIVATE/(uri[1:]+'.html')).read_bytes()
    REPORT['unexpected_GET'].append(uri)
    return 404,'application/json',b'{}'

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def do_GET(self):
        row=dict(method='GET',path=self.path);REPORT['requests'].append(row)
        if len(REPORT['requests'])>=40:raise RuntimeError('40 GET allowance exhausted')
        code,kind,body=fixture_response(self.path);row['status']=code
        self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers();self.wfile.write(body)
    def do_POST(self):REPORT['business_POSTs']+=1;self.send_error(405,'No writes in presentation review')

def open_page(browser,origin,variant,width):
    global PAGE
    require_operation_time(30)
    context=browser.new_context(viewport={'width':width,'height':1000},service_workers='block')
    def boundary(route):
        request=route.request;a=urlsplit(request.url);b=urlsplit(origin)
        uri=a.path+('?' + a.query if a.query else '')
        allowed=((a.scheme,a.netloc)==(b.scheme,b.netloc) and not a.username and not a.password
            and request.method=='GET' and len(REPORT['browser_requests'])+1<40
            and uri in set(FIXTURE_LIMITS)|{'/favicon.ico'})
        REPORT['browser_requests'].append(dict(method=request.method,path=uri,allowed=allowed))
        if allowed:route.continue_()
        else:
            REPORT['violations'].append(dict(method=request.method,path=uri))
            if request.method=='POST':REPORT['business_POSTs']+=1
            route.abort()
    context.route('**/*',boundary);page=context.new_page();PAGE=page
    context.on('page',lambda new_page:new_page.on('pageerror',lambda error:REPORT['page_errors'].append(str(error))))
    page.on('pageerror',lambda error:REPORT['page_errors'].append(str(error)))
    page.set_default_timeout(15000)
    response=page.goto(origin+'/'+variant,wait_until='load',timeout=15000)
    assert response.status==200 and response.body()==(PRIVATE/(variant+'.html')).read_bytes()
    page.wait_for_load_state('networkidle',timeout=15000)  # Settle optional favicon before exact request deltas.
    return context,page

def request_counts():return (len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])

def contrast(first,second):
    import re
    def luminance(value):
        match=re.fullmatch(r'rgb\((\d+), (\d+), (\d+)\)',value)
        assert match,'opaque computed RGB required'
        channels=[int(x)/255 for x in match.groups()]
        assert all(0<=x<=1 for x in channels)
        linear=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in channels]
        return sum(x*w for x,w in zip(linear,(.2126,.7152,.0722)))
    low,high=sorted((luminance(first),luminance(second)))
    return (high+.05)/(low+.05)


def presentation(page,component,variant,width):
    require_operation_time(30)
    before=request_counts()
    page.evaluate("""() => {clearPreparation();clearDispatch();clearReceipts();clearServiceCasePlan();
        document.querySelectorAll('[data-visual-fixture]').forEach(e=>e.remove());
        $('service').hidden=true;$('collaboration').hidden=true;$('resource').hidden=true;
        $('token').value='SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY';}""")
    value=FIXTURES[component]
    if component=='dispatch':
        page.evaluate('(x)=>renderDispatch(x)',value)
        assert page.evaluate('JSON.parse(JSON.stringify(dispatchView))')==value
        assert page.locator('#dispatch-receipt').is_visible()
    else:
        page.evaluate('(x)=>renderReceipt(x)',value)
        assert page.evaluate('JSON.parse(JSON.stringify(receiptView))')==value
        assert page.locator('#receipt-ack').is_disabled() and page.locator('#receipt-correct').is_disabled()
        assert page.locator('#receipt-reopen').is_enabled()
        assert value['current_receipt']['source_sha256'] in page.locator('#receipt-current').text_content()
    panel=page.locator('#'+component+'-detail');assert panel.is_visible()
    panel.evaluate("""(e,text)=>{const n=document.createElement('p');n.dataset.visualFixture='true';
        n.className='notice';n.textContent=text;e.prepend(n)}""",FIXTURE_LABEL)
    projection=panel.evaluate("""e=>{const clone=e.cloneNode(true);clone.querySelectorAll('.record-action-title').forEach(n=>n.remove());
        return {originalText:clone.textContent,controls:[...e.querySelectorAll('button,input,textarea,select')].map(b=>({id:b.id,
        type:b.type,text:b.tagName==='BUTTON'?b.textContent:null,value:b.value,disabled:b.disabled,hidden:b.hidden,
        readOnly:b.readOnly||false,dataset:{...b.dataset}}))}}""")
    rows=REPORT.setdefault('presentation_projections',[])
    first=next((r for r in rows if r['component']==component),None)
    if first:assert first['projection']==projection,'original text and control states must match both versions and widths'
    row=dict(component=component,variant=variant,width=width,projection=projection,
        projection_sha256=hashlib.sha256(json.dumps(projection,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
    if variant=='after':
        assert panel.locator('.record-detail-heading').count()==1 and panel.locator('.record-history-panel').count()==1
    focus=panel.locator('button:visible:not(:disabled)').first
    focus.focus();page.keyboard.press('Tab');page.keyboard.press('Shift+Tab')
    key=focus.evaluate("""e=>({id:e.id,active:document.activeElement===e,visible:e.matches(':focus-visible'),
        outline:getComputedStyle(e).outlineWidth,method:'real Tab then Shift+Tab after initial focus'})""")
    assert key['active'] and key['visible'] and key['outline']=='3px',key
    if first:assert first['keyboard_focus']==key,'paired screenshots require the same observed keyboard focus'
    row['keyboard_focus']=key
    page.wait_for_function("id=>document.getElementById(id).getAnimations({subtree:true}).length===0",arg=component+'-detail',timeout=15000)
    row['settled_styles']=panel.locator('button:visible').evaluate_all("""els=>els.map(e=>({id:e.id,disabled:e.disabled,
        color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor,
        animations:e.getAnimations().length}))""")
    assert all(x['animations']==0 for x in row['settled_styles'])
    geometry=panel.evaluate("""e=>{const rect=n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,
        top:r.top,bottom:r.bottom,height:r.height}};return {panel:rect(e),
        controls:[...e.querySelectorAll('button,input,textarea,select')].filter(n=>n.getClientRects().length).map(n=>({id:n.id,...rect(n)})),
        notices:[...e.querySelectorAll('.notice')].filter(n=>n.textContent.trim()&&n.getClientRects().length).map(rect)}}""")
    assert geometry['panel']['left']>=0 and geometry['panel']['right']<=width,geometry
    assert all(x['left']>=geometry['panel']['left'] and x['right']<=geometry['panel']['right'] for x in geometry['controls']+geometry['notices']),geometry
    if variant=='after':
        fields=panel.locator('form:is(#dispatch-offer,#dispatch-decision,#receipt-submit,#receipt-decisions) :is(input,textarea,select)').evaluate_all("""els=>els.map(e=>({id:e.id,disabled:e.disabled,
            visible:!!e.getClientRects().length,focused:e===document.activeElement,border:getComputedStyle(e).borderTopColor,
            inner:getComputedStyle(e).backgroundColor,outer:getComputedStyle(e.closest('form')).backgroundColor}))""")
        for field in fields:
            if not field['disabled'] and not field['focused']:
                field['inner_contrast']=contrast(field['border'],field['inner'])
                field['outer_contrast']=contrast(field['border'],field['outer'])
                assert min(field['inner_contrast'],field['outer_contrast'])>=3,field
        row['form_boundaries']=fields # Hidden controls are computed-only, never claimed visible pixels.
    row['geometry']=geometry
    panel.evaluate('(e)=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-24)')
    observe(page,variant+'-'+component+'-'+str(width),True)
    assert request_counts()==before,'render/focus/screenshot preparation must add zero requests'
    row['request_delta']=0;rows.append(row)
    require_operation_time(15)
    number=(0 if component=='dispatch' else 4)+(0 if width==1200 else 2)+(1 if variant=='before' else 2)
    name=f'{number:02d}-{variant}-{component}-{width}.png';assert name in PNG_FILES
    assert panel.locator('[data-visual-fixture]').inner_text()==FIXTURE_LABEL
    # This driver uses only an explicit synthetic value and clips this panel.
    # Never apply a page-wide password mask at coordinates outside its clip.
    assert page.locator('#token').input_value()=='SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY'
    assert panel.locator('#token').count()==0
    assert panel.evaluate("""e=>{const a=e.getBoundingClientRect(),b=document.getElementById('token').getBoundingClientRect();
        return b.bottom<=a.top||b.top>=a.bottom||b.right<=a.left||b.left>=a.right}""")
    panel.screenshot(path=str(OUT/name),timeout=15000)


def startup_resources(label):
    """Two small read-only Linux snapshots; not a resource-causality verdict.

    Per-file byte limits bound diagnostic input. Existing worker/overall clocks
    still bound execution; these reads do not create a new deadline or retry.
    """
    assert label in ('BEFORE_CHROME_LAUNCH','AFTER_CHROME_READY','AFTER_CHROME_LAUNCH_ERROR')
    row=dict(label=label,seconds=round(time.monotonic()-START,6),scope='HOST_READ_ONLY_RESOURCE_OBSERVATION',errors=[])
    def failed(name,error):
        code=getattr(error,'errno',None)
        row['errors'].append(dict(metric=name,type=type(error).__name__,errno=code if type(code) is int and 0<=code<=65535 else None))
    for name,path,limit in (('load','/proc/loadavg',256),('memory','/proc/meminfo',8192),
            ('pressure_cpu','/proc/pressure/cpu',512),('pressure_memory','/proc/pressure/memory',512),
            ('pressure_io','/proc/pressure/io',512)):
        try:
            with open(path,'rb') as stream:raw=stream.read(limit+1)
            assert len(raw)<=limit,'diagnostic byte limit'
            text=raw.decode('ascii')
            if name=='load':
                values=[float(x) for x in text.split()[:3]]
                assert len(values)==3 and all(0<=x<=1000000 for x in values)
                row['load_1_5_15_minutes']=values
            elif name=='memory':
                values={}
                for line in text.splitlines():
                    key,_,value=line.partition(':')
                    if key not in ('MemTotal','MemAvailable','MemFree','SwapTotal','SwapFree'):continue
                    parts=value.split();assert len(parts)==2 and parts[1]=='kB'
                    number=int(parts[0]);assert 0<=number<2**64 and key not in values;values[key]=number
                assert 'MemTotal' in values and 'MemAvailable' in values
                row['memory_kib']=values
            else:
                values={}
                for line in text.splitlines():
                    parts=line.split();assert len(parts)==5 and parts[0] in ('some','full') and parts[0] not in values
                    fields=dict(part.split('=',1) for part in parts[1:]);assert set(fields)=={'avg10','avg60','avg300','total'}
                    averages={key:float(fields[key]) for key in ('avg10','avg60','avg300')}
                    assert all(0<=value<=100 for value in averages.values())
                    total=int(fields['total']);assert 0<=total<2**64
                    values[parts[0]]=dict(averages,total_us=total)
                assert 'some' in values;row[name]=values
        except Exception as error:failed(name,error)
    try:
        info=os.statvfs(os.environ['RUNNER_TEMP'])
        assert info.f_frsize>0 and info.f_bavail>=0 and info.f_blocks>=0
        row['runner_temp_space_bytes']=dict(available=info.f_frsize*info.f_bavail,total=info.f_frsize*info.f_blocks)
    except Exception as error:failed('runner_temp_space',error)
    rows=REPORT.setdefault('startup_resources',[]);assert len(rows)<2
    rows.append(row)


@contextmanager
def owned_browser(font_env):
    with sync_playwright() as pw:
        stage('CHROME_SANDBOX');startup_resources('BEFORE_CHROME_LAUNCH');require_operation_time(15)
        try:
            browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=font_env,timeout=15000)
        except BaseException as error:
            REPORT['status']='FAIL';REPORT['error_type']=type(error).__name__;REPORT['error']=str(error)
            startup_resources('AFTER_CHROME_LAUNCH_ERROR')
            checkpoint() # Preserve the primary launch failure before SDK teardown.
            raise
        try:
            startup_resources('AFTER_CHROME_READY')
            yield browser
        except BaseException:
            if PAGE is not None and not PAGE.is_closed():
                try:PAGE.screenshot(path=str(OUT/'failure-visual.png'),timeout=5000)
                except BaseException as e:REPORT['failure_screenshot_error']=type(e).__name__
            raise
        finally:
            try:browser.close();REPORT['browser_close']='CLOSED'
            except Exception as e:REPORT['cleanup_errors'].append('browser:'+type(e).__name__)


def observe(page,label,font=False):
    require_operation_time(5 if font else 1)
    row=page.evaluate("""() => {const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}};return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,visibleButtons:[...document.querySelectorAll('button')].filter(e=>e.getClientRects().length).map(e=>({id:e.id,height:e.getBoundingClientRect().height,disabled:e.disabled})),nav:document.querySelector('.workspace-nav')?rect(document.querySelector('.workspace-nav')):null,content:document.querySelector('.session-panel')?rect(document.querySelector('.session-panel')):null}}""")
    row['label']=label;REPORT['checks'].append(row)
    assert row['documentWidth']<=row['width'] and row['height']<12000,row
    assert all(x['height']>=44 for x in row['visibleButtons']),row
    if row['width']>=1100 and row['nav'] and label.startswith('current'):
        assert row['nav']['right']+16<=row['content']['left'],row
    if font:
        verify_rendered_font(page,REPORT)
        REPORT['font_observations'].append(dict(label=label,width=row['width'],nodes=REPORT['installed_CJK_font']['visible_node_font_usage']))
    return row


def run_flow(started):
    global OUT,PRIVATE,START
    os.umask(0o077);START=started;server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='45')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        pages,binding=source_contract();REPORT['source_binding']=binding
        for variant,data in pages.items():(PRIVATE/(variant+'.html')).write_bytes(data)
        REPORT['fixture_scope']='Exact archived synthetic dispatch/receipt DTOs through original renderers; visual replay, not new business activity, health, permissions or cold recovery'
        env=dict(os.environ)
        for key,name in [('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')]:
            p=PRIVATE/name;p.mkdir(mode=0o700);env[key]=str(p)
        env=installed_font_environment(env,PRIVATE/'fontconfig',REPORT,extra_text=FIXTURE_LABEL+json.dumps(FIXTURES,ensure_ascii=False))
        signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(90-(time.monotonic()-START))))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
        with owned_browser(env) as browser:
            base.resource.verify_sandbox(browser,REPORT);REPORT['browser_version']=browser.version
            for width in (1200,390):
                for variant in ('before','after'):
                    stage(variant.upper()+'_PRESENTATION_'+str(width));context,page=open_page(browser,origin,variant,width)
                    try:
                        for component in ('dispatch','receipt'):
                            stage(variant.upper()+'_'+component.upper()+'_'+str(width));presentation(page,component,variant,width)
                    finally:context.close()
            assert {uri:FIXTURE_READS.get(uri,0) for uri in FIXTURE_LIMITS}==FIXTURE_LIMITS,'exact GET fixture totals'
            assert FIXTURE_READS.get('/favicon.ico',0)<=4
            assert {p.name for p in OUT.glob('*.png')}==set(PNG_FILES)
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
        source=base.require_hosted(os.environ,run_number='45')
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
