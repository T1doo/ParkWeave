"""Run36/attempt1: reviewed task surfaces and navigation; no product backend."""
import hashlib,json,os,queue,signal,socket,subprocess,sys,tempfile,threading,time,traceback
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
BASELINE_SHA='de673276e91dd0e41d6fec5d035bb65da1eca1e1'
SOURCE_SHA256='b87bda8886b9ad2d23929650953609b2e909a7599099a2d7db458939396f6250'
GUIDE_SHA256='1d1aefb15eda9ef9107220e8c72e8a1b864d0eac1b6a46c0e3203cca7508163e'
SCENES=('entry','catalog-ready')
PUBLIC_FILES=frozenset(tuple(f'{offset+i+1:02}-current-{scene}-{width}.png'
    for width,offset in ((1200,0),(390,2)) for i,scene in enumerate(SCENES))+('failure-visual.png','result.json'))
EXPECTED_CHANGED_PATHS=frozenset((
    '.github/workflows/fictional-park-browser-once.yml','scripts/workspace_visual_browser_once.py',
    'scripts/fictional_park_font_once.py','docs/F2/evidence/eng057-job-shards.json',
    'docs/demo/evidence/task-desk-20261023/run36/README.md',
    'docs/demo/evidence/task-desk-20261023/run36/preflight.json',
    'docs/demo/evidence/task-desk-20261023/run36/SHA256SUMS'))
CATALOG_REPLIES=queue.Queue(maxsize=1)
FIXTURE_SUMMARY='合成界面复放 · 无真实业务、身份或授权'
FIXTURE_LABEL='SYNTHETIC UI_STATE_FIXTURE / READ_ONLY_RESPONSE_FIXTURE · 静态交互复放，非真实业务、身份或授权。'
FIXTURE_SERVICE=dict(service_id='synthetic-ui-service',version=1,name='合成资料整理',
    source=dict(kind='SYNTHETIC',statement='只读界面夹具，不代表资格确认或外部受理'))


def presentation_contract(reviewed,current,guide=False):
    expected=GUIDE_SHA256 if guide else SOURCE_SHA256
    assert hashlib.sha256(reviewed).hexdigest()==expected,'reviewed page fingerprint mismatch'
    assert current==reviewed,'current product page must equal the exact reviewed candidate'


def source_contract():
    parent=subprocess.check_output(['git','rev-parse','HEAD^'],cwd=ROOT,text=True).strip()
    assert parent==BASELINE_SHA,'exact reviewed direct parent required'
    changed=subprocess.check_output(['git','diff','--name-only',BASELINE_SHA,'HEAD'],cwd=ROOT,text=True).splitlines()
    assert len(changed)==len(set(changed)) and set(changed)==EXPECTED_CHANGED_PATHS,'unreviewed commit paths'
    assert not subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT),'tracked workspace changes refused'
    pages={}
    for name,guide in [('web.html',False),('park_demo_web.html',True)]:
        path='src/parkweave/'+name;current=(ROOT/path).read_bytes()
        reviewed=subprocess.check_output(['git','show',BASELINE_SHA+':'+path],cwd=ROOT)
        presentation_contract(reviewed,current,guide);pages[name]=current
    return pages,dict(reviewed_product_sha=BASELINE_SHA,current_web_sha256=SOURCE_SHA256,
        current_guide_sha256=GUIDE_SHA256,product_pages_identical_to_reviewed_baseline=True,
        exact_changed_paths=sorted(changed),scope='CURRENT candidate only; no old-run pixels or script-permutation claim')


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
        if path=='/current':
            body=(PRIVATE/'current.html').read_bytes();kind='text/html; charset=utf-8';code=200
        elif path=='/api/preparation-catalog':
            try:fixture=CATALOG_REPLIES.get_nowait()
            except queue.Empty:
                REPORT['unexpected_GET'].append(path);body=b'{}';kind='application/json';code=404
            else:
                fixture['started'].set()
                if not fixture['release'].wait(5):
                    REPORT['violations'].append(dict(path=path,reason='controlled fixture release missed5s'))
                    body=b'{}';code=504
                else:body=fixture['body'];code=200
                kind='application/json'
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
    if row['width']>=1100 and row['nav'] and label.startswith('current'):
        assert row['nav']['right']+16<=row['content']['left'],row
    if font:
        verify_rendered_font(page,REPORT)
        REPORT['font_observations'].append(dict(label=label,width=row['width'],nodes=REPORT['installed_CJK_font']['visible_node_font_usage']))
    return row

def mark_fixture(page):
    page.evaluate("""([summary,text])=>{
        const n=document.createElement('details');n.dataset.visualFixture='true';
        n.style.cssText='margin:0 0 12px;padding:8px 10px;border:1px dashed #b2a16e;border-radius:8px;background:#fff6dc;color:#614b19;font-size:12px;line-height:1.5';
        const s=document.createElement('summary');s.textContent=summary;s.style.cssText='cursor:pointer;min-height:24px';
        const p=document.createElement('p');p.textContent=text;p.style.cssText='margin:8px 0 0;overflow-wrap:anywhere';
        n.append(s,p);$('prep-catalog').before(n);
    }""",[FIXTURE_SUMMARY,FIXTURE_LABEL])
    marker=page.locator('[data-visual-fixture="true"]')
    assert marker.count()==1 and marker.locator('summary').is_visible()
    assert marker.locator('summary').inner_text()==FIXTURE_SUMMARY
    assert marker.locator('p').text_content()==FIXTURE_LABEL


def current_shot(page,scene,width):
    require_operation_time(15)
    assert page.locator('[data-visual-fixture] > summary').evaluate("e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth}")
    offset=0 if width==1200 else 2;number=offset+SCENES.index(scene)+1
    page.screenshot(path=str(OUT/f'{number:02}-current-{scene}-{width}.png'),timeout=15000,full_page=False)


def visible_in_viewport(page,ids):
    rows=page.evaluate("""ids=>ids.map(id=>{const e=$(id),r=e.getBoundingClientRect();return {id,
        visible:!!e.getClientRects().length,top:r.top,bottom:r.bottom,height:innerHeight,text:e.textContent}})""",ids)
    assert all(r['visible'] and 0<=r['top'] and r['bottom']<=r['height'] for r in rows),rows
    return rows


def surface_observation(page,label,ready=False):
    row=page.evaluate("""() => {
        const box=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}};
        const surface=selector=>{const e=document.querySelector(selector),s=getComputedStyle(e);let p=e,bg=s.backgroundColor;
            while(p&&['transparent','rgba(0, 0, 0, 0)'].includes(bg)){p=p.parentElement;if(p)bg=getComputedStyle(p).backgroundColor;}
            return {selector,box:box(e),background:bg,color:s.color,border:s.borderTopColor,borderWidth:s.borderTopWidth,overflow:s.overflow};};
        const regions=['body','.workspace-nav','.session-panel','.primary-entry-heading','.primary-entry-panel','#secondary-entry-group','#existing-preparation-entry','#formal-preparation-entry'].map(surface);
        const button=$('prep-create').querySelector('button'),help=$('prep-create').querySelector('small');
        return {width:innerWidth,regions,help:{text:help.textContent,display:getComputedStyle(help).display,box:box(help),button:box(button),form:box($('prep-create'))}};
    }""")
    row['label']=label;REPORT.setdefault('surface_observations',[]).append(row)
    regions={r['selector']:r for r in row['regions']}
    assert regions['.primary-entry-panel']['box']['bottom']+16<=regions['#secondary-entry-group']['box']['top'],row
    assert regions['body']['background']!=regions['.workspace-nav']['background'],row
    assert regions['.primary-entry-heading']['background']!=regions['.primary-entry-panel']['background'],row
    assert regions['.primary-entry-panel']['background']!=regions['#secondary-entry-group']['background'],row
    assert regions['#existing-preparation-entry']['background']!=regions['.primary-entry-panel']['background'],row
    if ready:
        h=row['help'];assert h['text']=='创建新的Case和运行，不复制上一事项材料。' and h['display']=='block',h
        assert h['box']['top']>=h['button']['bottom'] and h['box']['height']>0,h
        assert h['form']['left']<=h['box']['left']<h['box']['right']<=h['form']['right'] and h['box']['bottom']<=h['form']['bottom'],h


def breakpoint_observation(page):
    require_operation_time(5)
    before=(len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])
    scroll=page.evaluate('()=>({x:scrollX,y:scrollY})');viewport=dict(page.viewport_size)
    try:
        page.set_viewport_size({'width':1060,'height':1000})
        row=page.evaluate("""() => {
            const box=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}};
            const n=document.querySelector('.workspace-nav');return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,
                bodyDisplay:getComputedStyle(document.body).display,direction:getComputedStyle(n).flexDirection,
                nav:box(n),session:box(document.querySelector('.session-panel')),buttons:[...n.querySelectorAll('button')].map(e=>({tab:e.dataset.tab,...box(e)}))};
        }""")
        REPORT['breakpoint_1060']=row
        assert row['width']==1060 and row['documentWidth']<=1060 and row['bodyDisplay']=='block' and row['direction']=='row',row
        buttons=row['buttons'];assert [b['tab'] for b in buttons]==['service','collaboration','resource'],row
        assert max(b['top'] for b in buttons)-min(b['top'] for b in buttons)<=1,row
        assert all(a['right']<=b['left'] for a,b in zip(buttons,buttons[1:])),row
        assert row['nav']['left']<=buttons[0]['left'] and buttons[-1]['right']<=row['nav']['right'] and row['session']['top']>=row['nav']['bottom'],row
    finally:
        page.set_viewport_size(viewport);page.evaluate('p=>window.scrollTo(p.x,p.y)',scroll)
    assert before==(len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])
    REPORT['breakpoint_1060']['request_delta']=0


def queue_catalog(ready=False,held=False):
    data=dict(scope='SYNTHETIC_LOCAL_PREPARATION_ONLY',services=[FIXTURE_SERVICE] if ready else [],
        reviewers=[dict(id='SYNTHETIC_REVIEWER')] if ready else [],required_slots=['need_summary','material_outline'])
    fixture=dict(body=json.dumps(data,ensure_ascii=False).encode(),started=threading.Event(),release=threading.Event())
    if not held:fixture['release'].set()
    CATALOG_REPLIES.put_nowait(fixture);return fixture


def catalog_observation(page,width):
    require_operation_time(30)
    held=queue_catalog(held=True)
    try:
        page.locator('#prep-catalog').click(timeout=15000)
        observed_by=time.monotonic()+2
        while not held['started'].is_set():
            remaining=observed_by-time.monotonic()
            assert remaining>0,'catalog request not observed'
            # Pump sync Playwright so a queued route callback can reach the server.
            page.wait_for_timeout(min(20,remaining*1000))
        assert time.monotonic()<=observed_by,'catalog request observation exceeded2s'
        assert page.locator('#prep-catalog').is_disabled()
        assert page.locator('#prep-catalog-view').get_attribute('aria-busy')=='true'
        assert page.locator('#prep-catalog-status').get_attribute('data-state')=='LOADING'
        held['release'].set()
        page.wait_for_function("()=>$('prep-catalog-status').dataset.state==='EMPTY'",timeout=15000)
        assert page.locator('#prep-create').is_hidden() and '暂无可用服务' in page.locator('#prep-catalog-status').inner_text()
        assert page.locator('#prep-catalog-view').get_attribute('aria-busy')=='false'
        queue_catalog(ready=True);page.locator('#prep-catalog').click(timeout=15000)
        page.wait_for_function("()=>$('prep-catalog-status').dataset.state==='READY'",timeout=15000)
        assert page.locator('#prep-create').is_visible() and not page.locator('#prep-catalog').is_disabled()
        assert page.locator('#prep-catalog-status').get_attribute('aria-live')=='polite'
        assert page.locator('#prep-catalog').get_attribute('aria-describedby')=='prep-catalog-status'
        assert page.locator('#prep-reviewer option').count()==1
        page.locator('#prep-goal').fill('SYNTHETIC：整理本次企业资料，尚未提交。')
        page.locator('[data-visual-fixture]').evaluate("e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-16)")
        viewport=visible_in_viewport(page,['prep-catalog-status','prep-create'])
        observe(page,'current-catalog-ready-'+str(width),True)
        surface_observation(page,'catalog-ready-'+str(width),True)
        REPORT.setdefault('catalog_feedback',[]).append(dict(width=width,states=['LOADING','EMPTY','READY'],
            scope='READ_ONLY_RESPONSE_FIXTURE, exact original GET handler, no form submission or backend',viewport=viewport))
        current_shot(page,'catalog-ready',width)
    finally:held['release'].set()


NAVIGATION_FIXTURE_SCRIPT="""() => {
    if(prepCommandPending||activeEntryWriteFlow||entryWriteRequests.size||objectionLock())throw Error('original state not empty');
    const pending={context:prepContext(),state:'UNKNOWN',key:'11111111-1111-4111-8111-111111111111',
        path:'/api/preparations/22222222-2222-4222-8222-222222222222/commands',
        body:{action:'ADD_EVIDENCE',expected_revision:1,text:'SYNTHETIC UI_STATE_FIXTURE, not a sent command'}};
    prepCommandPending=pending;
    const snapshot=()=>{const copy=document.body.cloneNode(true);copy.querySelector('#page-feedback').replaceChildren();
        copy.querySelector('#page-feedback').removeAttribute('data-tone');
        return JSON.stringify({DOM:copy.innerHTML,workspace:document.body.dataset.workspace,
            controls:[...document.querySelectorAll('input,textarea,select,button')].map(e=>({id:e.id,value:e.value,checked:e.checked,disabled:e.disabled})),
            pending:prepCommandPending});};
    window.__parkVisualFixture={pending,serialized:JSON.stringify(pending),snapshot,before:snapshot()};
    return {scope:'UI_STATE_FIXTURE only; no real failed request, case identity or authority',generic_requests:entryWriteRequests.size,active_flow:!!activeEntryWriteFlow};
}"""
NAVIGATION_COMPARE_SCRIPT="""() => {
    const f=window.__parkVisualFixture;if(!f||prepCommandPending!==f.pending||JSON.stringify(prepCommandPending)!==f.serialized)throw Error('fixture identity or body changed');
    if(f.snapshot()!==f.before)throw Error('protected page/controls changed during refused navigation');
    return {same_original_object:true,same_key_body_context:true,protected_DOM_and_controls_equal:true,feedback:$('page-feedback').textContent};
}"""
NAVIGATION_RELEASE_SCRIPT="""() => {
    const f=window.__parkVisualFixture;if(!f||prepCommandPending!==f.pending||JSON.stringify(prepCommandPending)!==f.serialized)throw Error('cannot release unknown state');
    prepCommandPending=null;delete window.__parkVisualFixture;
}"""


def navigation_observation(page,width):
    require_operation_time(30)
    fixture=page.evaluate(NAVIGATION_FIXTURE_SCRIPT)
    before=(len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])
    page.locator('[data-tab="resource"]').click(timeout=15000)
    page.wait_for_function("()=>$('page-feedback').textContent==='请先核对当前材料操作结果'",timeout=15000)
    proof=page.evaluate(NAVIGATION_COMPARE_SCRIPT)
    assert before==(len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])
    assert page.locator('#page-feedback').get_attribute('data-tone')=='error'
    page.keyboard.press('Shift+Tab');page.keyboard.press('Tab')
    focus=page.evaluate("""() => {
        const f=document.activeElement,c=document.querySelector('[data-tab][aria-current=page]');
        const style=e=>{const s=getComputedStyle(e);return {background:s.backgroundColor,color:s.color,outline:s.outlineColor,outlineWidth:s.outlineWidth,outlineStyle:s.outlineStyle,boxShadow:s.boxShadow}};
        return {focused:f.dataset.tab,current:c.dataset.tab,workspace:document.body.dataset.workspace,focusVisible:f.matches(':focus-visible'),focusedStyle:style(f),currentStyle:style(c)};
    }""")
    assert focus['focused']=='resource' and focus['current']==focus['workspace']=='service' and focus['focusVisible'],focus
    assert focus['focusedStyle']['outlineStyle']!='none' and float(focus['focusedStyle']['outlineWidth'].removesuffix('px'))>=2,focus
    assert focus['focusedStyle']['background']!=focus['currentStyle']['background'],focus
    assert page.evaluate(NAVIGATION_COMPARE_SCRIPT)==proof
    page.evaluate('()=>window.scrollTo(0,0)');viewport=visible_in_viewport(page,['page-feedback'])
    observe(page,'current-navigation-refused-'+str(width),True)
    page.evaluate(NAVIGATION_RELEASE_SCRIPT)
    for name in ('resource','collaboration','service'):
        page.locator('[data-tab="'+name+'"]').click(timeout=15000)
        assert page.evaluate("name=>document.body.dataset.workspace===name&&['service','collaboration','resource'].every(id=>$(id).hidden===(id!==name))",name)
        assert page.locator('[data-tab][aria-current="page"]').get_attribute('data-tab')==name
    assert before==(len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])
    REPORT.setdefault('navigation_feedback',[]).append(dict(width=width,fixture=fixture,proof=proof,
        request_delta=0,viewport=viewport,keyboard_focus=focus,fixture_released_by_exact_object=True,normal_three_workspace_navigation=True))


def secondary_observation(page,width):
    require_operation_time(30)
    detail=page.locator('#simple-input-controls');summary=detail.locator('summary')
    assert not detail.evaluate('e=>e.open')
    summary.focus();page.keyboard.press('Enter');assert detail.evaluate('e=>e.open')
    page.keyboard.press('Space');assert not detail.evaluate('e=>e.open')
    page.keyboard.press('Enter');assert detail.evaluate('e=>e.open')
    assert summary.evaluate("e=>document.activeElement===e&&e.matches(':focus-visible')&&getComputedStyle(e).outlineWidth==='3px'")
    assert page.locator('#intake').is_visible()
    assert '不代表外部受理或线下履约' in page.locator('#simple-input-entry > p').inner_text()
    assert '此入口由服务端单独启用' in page.locator('#cold-entry > p').first.inner_text()
    assert page.locator('#template-input-recover').is_disabled()
    page.emulate_media(reduced_motion='reduce')
    assert summary.evaluate("e=>getComputedStyle(e).transitionDuration==='0s'&&getComputedStyle(e).animationName==='none'")
    page.emulate_media(reduced_motion='no-preference')
    page.locator('#secondary-entry-group').evaluate("e=>window.scrollTo(0,e.getBoundingClientRect().top+scrollY-16)")
    observe(page,'current-secondary-entry-'+str(width),True)
    REPORT.setdefault('secondary_entry',[]).append(dict(width=width,native_keyboard='Enter open / Space close / Enter open',
        focus_outline='3px visible',reduced_motion=True,original_warnings_present=True,template_recovery_disabled=True,
        screenshot_scope='no extra PNG; font observations only actual viewport nodes'))


def run_flow(started):
    global OUT,PRIVATE,START
    os.umask(0o077);START=started;server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='36')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        pages,binding=source_contract();REPORT['source_binding']=binding
        (PRIVATE/'current.html').write_bytes(pages['web.html'])
        REPORT['fixture_scope']='Transparent read-only HTTP response and client UI-state fixtures; not live business or permission acceptance'
        env=dict(os.environ)
        for key,name in [('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')]:
            p=PRIVATE/name;p.mkdir(mode=0o700);env[key]=str(p)
        env=installed_font_environment(env,PRIVATE/'fontconfig',REPORT,extra_text=FIXTURE_SUMMARY+FIXTURE_LABEL+json.dumps(FIXTURE_SERVICE,ensure_ascii=False)+'SYNTHETIC：整理本次企业资料，尚未提交。')
        signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(90-(time.monotonic()-START))))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
        with owned_browser(env) as browser:
            base.resource.verify_sandbox(browser,REPORT);REPORT['browser_version']=browser.version
            for width in (1200,390):
                stage('CURRENT_ENTRY_'+str(width));context,page=open_page(browser,origin,'/current',width)
                try:
                    mark_fixture(page)
                    assert page.locator('#prep-catalog').is_visible() and page.locator('#prep-create').is_hidden()
                    visible_in_viewport(page,['prep-catalog'])
                    surface_observation(page,'entry-'+str(width))
                    observe(page,'current-entry-'+str(width),True);current_shot(page,'entry',width)
                    stage('CURRENT_CATALOG_'+str(width));catalog_observation(page,width)
                    if width==1200:
                        stage('BREAKPOINT_1060');breakpoint_observation(page)
                    stage('CURRENT_NAVIGATION_'+str(width));navigation_observation(page,width)
                    stage('CURRENT_SECONDARY_'+str(width));secondary_observation(page,width)
                finally:context.close()
            assert CATALOG_REPLIES.empty()
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
        source=base.require_hosted(os.environ,run_number='36')
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
