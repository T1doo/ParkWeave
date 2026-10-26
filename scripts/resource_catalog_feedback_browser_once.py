"""Prepared run48/attempt1: exact paired resource UI, synthetic GETs, no backend."""
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
REPORT=dict(scope='REAL_CHROME_RESOURCE_CATALOG_PRESENTATION_SIMULATED_GET_ONLY',status='RUNNING',stage='START',
    product_API=False,database=False,real_model_calls=0,business_POSTs=0,requests=[],browser_requests=[],
    checks=[],font_observations=[],page_errors=[],violations=[],unexpected_GET=[],cleanup_errors=[])
OUT=None;PRIVATE=None;PAGE=None;START=0;CHECKPOINT=None
BASELINE_SHA='f6d9077ecae7166fde43b1a39a50c34a9509c5b3'
BEFORE_SHA='dc0df5aa40f3a8e400da7dfc9fb3ab01eb725406'
PAGE_SHA256='c52acb4262a6f530ea97f9f0e5c29c16688622c68a7e3e798ec96622202fbee3'
BEFORE_SHA256='81939da2c779849e6e4785e28d283f6519afd554f94f475376b286e45c20cc37'
PNG_FILES=('01-before-ready-1200.png','02-after-ready-1200.png','03-before-ready-390.png',
    '04-after-ready-390.png','05-after-loading-1200.png','06-after-empty-1200.png',
    '07-after-error-390.png','08-after-denied-390.png')
PUBLIC_FILES=frozenset(PNG_FILES+('failure-visual.png','result.json'))
EXPECTED_CHANGED_PATHS=frozenset(('.github/workflows/fictional-park-browser-once.yml',
    'scripts/resource_catalog_feedback_browser_once.py','scripts/fictional_park_font_once.py'))
FIXTURE_LABEL='模拟界面回放 · 无业务权限／非真实资源／未执行预约'
ROW=dict(id='00000000-0000-4000-8000-000000000061',name='合成园区共享空间：长名称与中文来源的可读性核对（不是可用性或真实预约证明）',
    capacity=3,revision=1,buffer_seconds=300,enabled=True,
    source=dict(kind='SYNTHETIC',id='fixture-visual-catalog-only',revision=1,statement='虚构目录，只为核对界面；外部未受理，无线下履约。'),
    open_from='2026-10-26T00:00:00Z',open_until='2026-10-27T00:00:00Z')
FIXTURES=dict(resource=ROW)
FIXTURE_LIMITS={'/before':2,'/after':2,'/api/synthetic-resources':7,'/api/resource-bundles':5,'/api/plan-approval/status':5,'/api/run-access/status':4}
FIXTURE_READS={};FIXTURE_LOCK=threading.Lock();RELEASE=threading.Event();PHASE='READY';HOLD=False

def presentation_contract(before,after):
    assert hashlib.sha256(before).hexdigest()==BEFORE_SHA256,'exact reviewed before page required'
    assert hashlib.sha256(after).hexdigest()==PAGE_SHA256,'exact reviewed candidate page required'

def validate_source_listing(parent,changed,dirty):
    assert parent==BASELINE_SHA,'exact reviewed direct parent required'
    assert len(changed)==len(set(changed)) and set(changed)==EXPECTED_CHANGED_PATHS,'unreviewed commit paths'
    assert not dirty,'tracked or untracked workspace changes refused'

def source_contract():
    parent=subprocess.check_output(['git','rev-parse','HEAD^'],cwd=ROOT,text=True).strip()
    changed=subprocess.check_output(['git','diff','--name-only',BASELINE_SHA,'HEAD'],cwd=ROOT,text=True).splitlines()
    validate_source_listing(parent,changed,subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True))
    path='src/parkweave/web.html';after=(ROOT/path).read_bytes()
    before=subprocess.check_output(['git','show',BEFORE_SHA+':'+path],cwd=ROOT)
    reviewed=subprocess.check_output(['git','show',BASELINE_SHA+':'+path],cwd=ROOT)
    presentation_contract(before,after);assert after==reviewed,'candidate product source drift'
    return {'before':before,'after':after},dict(reviewed_product_sha=BASELINE_SHA,before_sha=BEFORE_SHA,
        before_sha256=BEFORE_SHA256,page_sha256=PAGE_SHA256,exact_changed_paths=sorted(changed),
        simulated_response_sha256=hashlib.sha256(json.dumps(ROW,sort_keys=True).encode()).hexdigest(),
        scope='Original resource entry over declared simulated GET responses; no API factory, PG or real authority')

def fixture_response(uri):
    with FIXTURE_LOCK:
        count=FIXTURE_READS.get(uri,0)+1;FIXTURE_READS[uri]=count;phase,hold=PHASE,HOLD
    if uri=='/favicon.ico' and count<=4:return 204,'image/x-icon',b''
    if uri not in FIXTURE_LIMITS or count>FIXTURE_LIMITS[uri]:
        REPORT['unexpected_GET'].append(uri);return 404,'application/json',b'{}'
    if uri in ('/before','/after'):return 200,'text/html; charset=utf-8',(PRIVATE/(uri[1:]+'.html')).read_bytes()
    if uri=='/api/synthetic-resources':
        if hold and not RELEASE.wait(30):raise TimeoutError('held synthetic catalog response not released')
        if phase in ('ERROR','DENIED'):return (500 if phase=='ERROR' else 403),'application/json',b'{}'
        value=dict(server_time='2026-10-26T12:00:00Z',items=[] if phase=='EMPTY' else [ROW])
    elif uri=='/api/resource-bundles':value=dict(actor_id='SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY',items=[])
    elif uri=='/api/run-access/status':value=dict(enabled=False,read_available=False,role=None,can_approve=False,can_revoke=False,actual_run_access=False,deployment_enabled=False)
    else:value=dict(enabled=False,approval_scope=None,source_reapproval_enabled=False,
        plan_replacement_enabled=False,known_not_started_enabled=False,p3_closure_enabled=False)
    return 200,'application/json',json.dumps(value,ensure_ascii=False).encode()

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

def phase(value,hold=False):
    global PHASE,HOLD
    assert value in ('READY','EMPTY','ERROR','DENIED')
    with FIXTURE_LOCK:PHASE,HOLD=value,hold
    if hold:RELEASE.clear()
    else:RELEASE.set()

def capture(page,name,state,variant,width):
    require_operation_time(15);assert name in PNG_FILES
    page.locator('#resource-catalog').evaluate('(e)=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-48)')
    page.wait_for_function("() => document.getAnimations().every(a=>a.playState==='finished')",timeout=15000)
    row=observe(page,variant+'-'+state+'-'+str(width),True)
    row['state']=state;row['image']=name
    row['status']=page.locator('#resource-catalog-status').evaluate("e=>({state:e.dataset.state,text:e.textContent,role:e.getAttribute('role'),live:e.getAttribute('aria-live'),atomic:e.getAttribute('aria-atomic'),color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor})") if variant=='after' else None
    if row['status']:
        row['status']['contrast']=contrast(row['status']['color'],row['status']['background']);assert row['status']['contrast']>=4.5
    row['regions']=page.locator('#resource-catalog-status,.resource-catalog-card,[data-visual-fixture]').evaluate_all("els=>els.map(e=>{const r=e.getBoundingClientRect();return {id:e.id,kind:e.className,left:r.left,right:r.right,top:r.top,bottom:r.bottom}})")
    assert all(r['left']>=0 and r['right']<=width and r['top']>=0 and r['bottom']<=1000 for r in row['regions']),row['regions']
    assert page.locator('[data-visual-fixture]').inner_text()==FIXTURE_LABEL
    assert page.locator('#token').input_value()=='SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY'
    label=page.locator('[data-visual-fixture]').bounding_box();assert label
    picture=page.screenshot(path=str(OUT/name),mask=[page.locator('#token')],timeout=15000)
    after_label=page.locator('[data-visual-fixture]').bounding_box();assert after_label
    row['marker_bounds']=dict(before=label,after=after_label)
    assert all(abs(label[k]-after_label[k])<=.5 for k in label),'marker moved across original PNG capture'
    # Read this exact unedited PNG back in an off-DOM canvas; never paint a label
    # into the output. A DOM rectangle alone did not prove run47 image06 pixels.
    import base64
    pixels=page.evaluate("""async ({png,box})=>{
        const bytes=Uint8Array.from(atob(png),c=>c.charCodeAt(0));
        const bitmap=await createImageBitmap(new Blob([bytes],{type:'image/png'}));
        try{const canvas=document.createElement('canvas');canvas.width=bitmap.width;canvas.height=bitmap.height;
            const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(bitmap,0,0);
            const x=Math.ceil(box.x+3),y=Math.ceil(box.y+3),width=Math.floor(box.width-6),height=Math.floor(box.height-6);
            if(width<1||height<1||x<0||y<0||x+width>canvas.width||y+height>canvas.height)throw Error('marker PNG bounds');
            const data=ctx.getImageData(x,y,width,height).data;let dark=0,white=0;
            for(let i=0;i<data.length;i+=4){if(data[i]===23&&data[i+1]===50&&data[i+2]===77&&data[i+3]===255)dark++;
                if(data[i]>=235&&data[i+1]>=235&&data[i+2]>=235&&data[i+3]===255)white++;}
            return {area:width*height,dark,white,pngWidth:canvas.width,pngHeight:canvas.height};
        }finally{bitmap.close();}
    }""",dict(png=base64.b64encode(picture).decode('ascii'),box=label))
    validate_marker_pixels(pixels,width);row['marker_PNG_pixels']=pixels


def validate_marker_pixels(value,width):
    assert type(value) is dict and set(value)=={'area','dark','white','pngWidth','pngHeight'}
    assert all(type(n) is int for n in value.values())
    assert value['pngWidth']==width and value['pngHeight']==1000
    area=value['area'];assert 0<area<=width*1000
    assert 0<=value['dark']<=area and 0<=value['white']<=area-value['dark']
    assert value['dark']>=area*.5 and value['white']>=max(10,area*.002),'simulated marker not proven in original PNG'

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

def presentation(page,variant,width):
    global PAGE
    require_operation_time(30)
    page.locator('#token').fill('SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY')
    page.locator('[data-tab="resource"]').click()
    page.evaluate("label=>{const p=document.createElement('p');p.dataset.visualFixture='true';p.className='visual-fixture-label';p.textContent=label;p.style.cssText='display:block!important;visibility:visible!important;opacity:1!important;position:static!important;box-sizing:border-box!important;margin:12px 0!important;padding:12px 14px!important;border:2px solid #17324d!important;border-radius:6px!important;background:#17324d!important;color:#fff!important;font:600 13px/1.8 system-ui,sans-serif!important;overflow-wrap:anywhere!important';$('resource-catalog-view').before(p);}",FIXTURE_LABEL)
    phase('READY',hold=variant=='after' and width==1200)
    page.locator('#resource-catalog').click()
    if variant=='after' and width==1200:
        try:
            page.wait_for_function("()=>$('resource-catalog-status').dataset.state==='LOADING'&&$('resource-catalog-view').getAttribute('aria-busy')==='true'",timeout=15000)
            capture(page,'05-after-loading-1200.png','LOADING',variant,width)
        finally:RELEASE.set()
    page.wait_for_function("()=>bundleActor==='SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY'",timeout=15000)
    assert page.locator('#resource-form').is_visible()
    button=page.locator('#resource-catalog');button.focus();page.keyboard.press('Tab');page.keyboard.press('Shift+Tab')
    focus=button.evaluate("e=>({active:document.activeElement===e,visible:e.matches(':focus-visible'),outline:getComputedStyle(e).outlineWidth})")
    assert focus==dict(active=True,visible=True,outline='3px'),focus
    REPORT.setdefault('paired_focus',[]).append(dict(variant=variant,width=width,focus=focus))
    ready=('01' if width==1200 else '03') if variant=='before' else ('02' if width==1200 else '04')
    if variant=='after':
        assert page.locator('#resource-catalog-status').get_attribute('data-state')=='READY'
        card=page.locator('.resource-catalog-card');assert card.count()==1
        text=card.inner_text();assert all(str(v) in text for v in (ROW['name'],ROW['source']['statement'],ROW['open_from'],ROW['open_until']))
        geometry=card.bounding_box();assert geometry and geometry['x']>=0 and geometry['x']+geometry['width']<=width
    capture(page,f'{ready}-{variant}-ready-{width}.png','READY',variant,width)
    if variant=='before':return
    states=[('EMPTY','06-after-empty-1200.png')] if width==1200 else [('ERROR','07-after-error-390.png'),('DENIED','08-after-denied-390.png')]
    for state,name in states:
        stage(state+'_'+str(width));phase(state);page.locator('#resource-catalog').click()
        page.wait_for_function("s=>$('resource-catalog-status').dataset.state===s&&$('resource-catalog-view').getAttribute('aria-busy')==='false'",arg=state,timeout=15000)
        if state=='EMPTY':page.wait_for_function("()=>bundleActor==='SYNTHETIC_VIEW_REPLAY_NO_AUTHORITY'",timeout=15000)
        assert not page.locator('#resource-form').is_visible()
        if state=='DENIED':assert page.locator('#resource-catalog-view').inner_text()==''
        capture(page,name,state,variant,width)



def timeout(*_):raise TimeoutError('90s visual work and cleanup deadline')


def checkpoint():
    if CHECKPOINT is None:return
    REPORT.setdefault('phase_timeline',[]).append(dict(stage=REPORT['stage'],seconds=time.monotonic()-START,error_type=REPORT.get('error_type')))
    try:atomic_report(CHECKPOINT,REPORT)
    except Exception as error:REPORT.setdefault('checkpoint_errors',[]).append(dict(type=type(error).__name__,errno=getattr(error,'errno',None)))


def stage(name):
    REPORT['stage']=name;checkpoint()


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


def require_operation_time(seconds):
    if time.monotonic()-START+seconds+5>=90:raise TimeoutError('insufficient original operation time and cleanup reserve')


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
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='48')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        pages,binding=source_contract();REPORT['source_binding']=binding
        for variant,data in pages.items():(PRIVATE/(variant+'.html')).write_bytes(data)
        REPORT['fixture_scope']='Declared simulated resource GET responses through original entries; not real API, authority, availability, business or recovery'
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
                        presentation(page,variant,width)
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
        RELEASE.set()
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
        source=base.require_hosted(os.environ,run_number='48')
        report['source_sha']=source
        private=Path(tempfile.mkdtemp(prefix='parkweave-visual-supervisor-'))
        state=private/'worker-state.json'
        owned=supervise([sys.executable,'-B','-m','scripts.resource_catalog_feedback_browser_once','--owned-worker',str(state)],
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
