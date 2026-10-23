"""Run40/attempt1 candidate: resource and guide presentation; no product backend."""
import hashlib,json,math,os,signal,socket,subprocess,sys,tempfile,threading,time,traceback
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
BASELINE_SHA='a105a5bf1a7bc7fb064dcfba7a1159eadc9cd134'
SOURCE_SHA256='7798e0e5c08462fd98cc20382d9e429a57a58ca61bbe95513c32065c7d755884'
GUIDE_SHA256='966f175764bdf323eea9c6e87f520c584da6ae03243b5c0396e492ce76a1af8c'
PNG_FILES=('01-resource-fieldset-1200.png','02-resource-fieldset-390.png',
    '03-resource-records-1200.png','04-resource-records-390.png','05-guide-entry-1200.png',
    '06-guide-entry-390.png','07-guide-invalid-390.png','08-guide-ready-390.png')
PUBLIC_FILES=frozenset(PNG_FILES+('failure-visual.png','result.json'))
EXPECTED_CHANGED_PATHS=frozenset((
    '.github/workflows/fictional-park-browser-once.yml','scripts/workspace_visual_browser_once.py',
    'scripts/fictional_park_font_once.py','docs/F2/evidence/eng057-job-shards.json',
    'docs/demo/evidence/task-desk-20261023/run40/README.md',
    'docs/demo/evidence/task-desk-20261023/run40/preflight.json',
    'docs/demo/evidence/task-desk-20261023/run40/SHA256SUMS'))
FIXTURE_SUMMARY='合成界面复放 · 无真实业务、身份或授权'
FIXTURE_LABEL='SYNTHETIC UI_STATE_FIXTURE / READ_ONLY_RESPONSE_FIXTURE · 静态交互复放，非真实业务、身份或授权。'


def presentation_contract(reviewed,current,guide=False):
    expected=GUIDE_SHA256 if guide else SOURCE_SHA256
    assert hashlib.sha256(reviewed).hexdigest()==expected,'reviewed page fingerprint mismatch'
    assert current==reviewed,'current product page must equal the exact reviewed candidate'


def validate_source_listing(parent,changed,dirty):
    assert parent==BASELINE_SHA,'exact reviewed direct parent required'
    assert len(changed)==len(set(changed)) and set(changed)==EXPECTED_CHANGED_PATHS,'unreviewed commit paths'
    assert not dirty,'tracked or untracked workspace changes refused'


def source_contract():
    parent=subprocess.check_output(['git','rev-parse','HEAD^'],cwd=ROOT,text=True).strip()
    assert parent==BASELINE_SHA,'exact reviewed direct parent required'
    changed=subprocess.check_output(['git','diff','--name-only',BASELINE_SHA,'HEAD'],cwd=ROOT,text=True).splitlines()
    validate_source_listing(parent,changed,subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True))
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
        if len(REPORT['requests'])>=40:raise RuntimeError('40 GET allowance exhausted')
        if path in ('/current','/','/guide'):
            body=(PRIVATE/('guide.html' if path=='/guide' else 'current.html')).read_bytes();kind='text/html; charset=utf-8';code=200
        elif path in RESOURCE_REPLIES:
            RESOURCE_READS[path]=RESOURCE_READS.get(path,0)+1
            if RESOURCE_READS[path]>RESOURCE_LIMITS[path]:
                REPORT['unexpected_GET'].append(path);body=b'{}';code=404
            else:body=json.dumps(RESOURCE_REPLIES[path],ensure_ascii=False).encode();code=200
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
        allowed=(a.scheme,a.netloc)==(b.scheme,b.netloc) and request.method=='GET' and len(REPORT['browser_requests'])+1<40
        REPORT['browser_requests'].append(dict(method=request.method,path=a.path,allowed=allowed))
        if allowed:route.continue_()
        else:
            REPORT['violations'].append(dict(method=request.method,path=a.path))
            if request.method=='POST':REPORT['business_POSTs']+=1
            route.abort()
    context.route('**/*',boundary);page=context.new_page();PAGE=page
    context.on('page',lambda new_page:new_page.on('pageerror',lambda error:REPORT['page_errors'].append(str(error))))
    page.on('pageerror',lambda error:REPORT['page_errors'].append(str(error)))
    response=page.goto(origin+path,wait_until='load',timeout=15000)
    assert response.status==200 and response.body()==(PRIVATE/('guide.html' if path=='/guide' else 'current.html')).read_bytes()
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


def visible_in_viewport(page,ids):
    rows=page.evaluate("""ids=>ids.map(id=>{const e=$(id),r=e.getBoundingClientRect();return {id,
        visible:!!e.getClientRects().length,top:r.top,bottom:r.bottom,height:innerHeight,text:e.textContent}})""",ids)
    assert all(r['visible'] and 0<=r['top'] and r['bottom']<=r['height'] for r in rows),rows
    return rows


def capture(page,name):
    require_operation_time(15)
    assert name in PUBLIC_FILES and name.endswith('.png')
    assert page.locator('[data-visual-fixture] > summary').evaluate("e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth}")
    page.screenshot(path=str(OUT/name),timeout=15000,full_page=False)


def compose_fixture(page,selector):
    # Only after raw native/geometry measurements. This is screenshot framing,
    # never the oracle for browser navigation landing or original target focus.
    page.evaluate("""selector=>{const n=document.querySelector('[data-visual-fixture]'),target=document.querySelector(selector);
        if(!n||!target)throw Error('fixture composition target missing');if(target.tagName==='FIELDSET')target.querySelector('legend').after(n);else target.prepend(n);target.scrollIntoView({block:'start',behavior:'instant'});} """,selector)
    REPORT.setdefault('screenshot_composition',[]).append(dict(selector=selector,scope='Move only the explicit fixture marker, then frame original section; not native landing proof'))


def dispatch_frame_delta(rows,height):
    margin=16
    assert height==1000 and rows,'original viewport and required framing nodes must exist'
    assert all(isinstance(r[k],(int,float)) and not isinstance(r[k],bool) and math.isfinite(r[k]) for r in rows for k in ('top','bottom'))
    assert all(r['bottom']>r['top'] for r in rows),'required framing node is not visible'
    minimum=math.ceil(max(r['bottom'] for r in rows)-(height-margin))
    maximum=math.floor(min(r['top'] for r in rows)-margin)
    assert minimum<=maximum,'complete markers, warnings and records do not fit the unchanged viewport'
    return minimum if minimum>0 else maximum if maximum<0 else 0


RESOURCE_READS={}
RESOURCE_NAME='合成资源：园区联合培训资料整理与设备说明核对'
RESOURCE_MEMBER=dict(resource_name=RESOURCE_NAME,purpose='长中文合成记录：须本人核对，外部未受理',starts_at='2026-10-23T10:00:00Z',ends_at='2026-10-23T11:00:00Z',quantity=1,state='CONFIRMED')
RESOURCE_REPLIES={
    '/api/synthetic-resources':dict(server_time='2026-10-23T09:00:00Z',items=[dict(id='ui-resource-1',name=RESOURCE_NAME,capacity=3,revision=1,buffer_seconds=60,enabled=True,open_from='2026-10-23T00:00:00Z',open_until='2026-10-24T00:00:00Z',source=dict(kind='SYNTHETIC',id='ui-source-1',revision=1,statement='静态交互复放，非真实可用性'))]),
    '/api/resource-bundles':dict(actor_id='SYNTHETIC_UI_ACTOR',items=[dict(id='ui-combination-1',state='CONFIRMED',members=[dict(RESOURCE_MEMBER,id='ui-member-'+str(i),resource_name=RESOURCE_NAME+' · '+str(i)) for i in range(1,4)])]),
    '/api/plan-approval/status':dict(enabled=False,approval_scope=None,source_reapproval_enabled=False,plan_replacement_enabled=False,known_not_started_enabled=False,p3_closure_enabled=False,production_execution_enabled=False,formal_release=False,role='enterprise_operator')}
RESOURCE_LIMITS={'/api/synthetic-resources':2,'/api/resource-bundles':4,'/api/plan-approval/status':4}


def request_counts():return (len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])


def rectangles(page,selectors):
    return page.evaluate("""selectors=>selectors.map(selector=>{const e=document.querySelector(selector);if(!e)throw Error('required node missing '+selector);const r=e.getBoundingClientRect();return {selector,visible:!!e.getClientRects().length,left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height,viewportWidth:innerWidth,viewportHeight:innerHeight}})""",selectors)


def bounded_rectangles(rows,viewport=False):
    assert all(x['visible'] and x['width']>0 and x['height']>0 and 0<=x['left']<x['right']<=x['viewportWidth'] for x in rows),rows
    if viewport:assert all(0<=x['top']<x['bottom']<=x['viewportHeight'] for x in rows),rows


def frame_required(page,selectors):
    # Original nodes remain untouched; move the explicit fixture marker only.
    require_operation_time(5);counts=request_counts();viewport=dict(page.viewport_size)
    rows=rectangles(page,selectors)
    delta=dispatch_frame_delta(rows,1000)
    page.evaluate('delta=>window.scrollBy({top:delta,behavior:"instant"})',delta)
    rows=rectangles(page,selectors);bounded_rectangles(rows,True)
    assert all(16<=x['top'] and x['bottom']<=984 for x in rows),rows
    assert counts==request_counts() and dict(page.viewport_size)==viewport,'framing must not request or resize'
    REPORT.setdefault('screenshot_framing',[]).append(dict(selectors=selectors,scroll_delta=delta,rectangles=rows))


def resource_breakpoints(page,width):
    counts=request_counts();viewport=dict(page.viewport_size);scroll=page.evaluate('()=>({x:scrollX,y:scrollY})')
    try:
        for w in (899,900,390):
            page.set_viewport_size(dict(width=w,height=1000))
            rows=rectangles(page,['.resource-pair','#bundle-panel','#delivery-panel','#combination-items'])
            bounded_rectangles(rows)
            a,b,d,i=rows
            if w>=900:assert a['right']+8<=b['left'] and abs(a['top']-b['top'])<2,rows
            else:assert a['bottom']<=b['top'] and abs(a['left']-b['left'])<2,rows
            assert abs(d['left']-a['left'])<2 and abs(i['left']-a['left'])<2 and d['width']>=a['width'] and i['width']>=a['width'],rows
            REPORT.setdefault('resource_breakpoints',[]).append(dict(width=w,rows=rows,scope='geometry only, not PNG'))
    finally:
        page.set_viewport_size(viewport);page.evaluate('p=>scrollTo({left:p.x,top:p.y,behavior:"instant"})',scroll)
    assert dict(page.viewport_size)==viewport and page.evaluate('()=>({x:scrollX,y:scrollY})')==scroll
    assert counts==request_counts()


def resource_observation(page,width):
    page.locator('[data-tab="resource"]').click(timeout=15000)
    assert page.locator('#resource').is_visible()
    page.locator('#resource-catalog').click(timeout=15000)
    page.wait_for_function("() => !$('resource-form').hidden && bundleActor==='SYNTHETIC_UI_ACTOR'",timeout=15000)
    assert '外部未受理' in page.locator('.resource-preparation>.notice').inner_text()
    fields=['resource-start','resource-end','resource-search-from','resource-search-until']
    for name in fields:
        field=page.locator('#'+name);assert field.get_attribute('type')=='datetime-local' and field.input_value()
        field.focus();assert field.evaluate('e=>document.activeElement===e')
    geometry=rectangles(page,['#resource-form','#resource-form>fieldset']+['#'+x for x in fields])
    bounded_rectangles(geometry)
    fieldset=geometry[1]
    assert all(fieldset['left']<=x['left']<x['right']<=fieldset['right'] for x in geometry[4:]),geometry
    if width==1200:assert geometry[1]['width']>=geometry[0]['width']-2,geometry
    REPORT.setdefault('resource_form',[]).append(dict(width=width,rows=geometry,datetime_scope='native datetime-local controls/value/focus, not OS picker interaction'))
    assert page.locator('#resource-hold').is_disabled()
    compose_fixture(page,'#resource-form>fieldset')
    fieldset_selectors=['[data-visual-fixture]','#resource-form>fieldset>legend','#resource-form>fieldset>p','#resource-form>fieldset>label:has(#resource-search-from)','#resource-form>fieldset>label:has(#resource-search-until)','#resource-search-from','#resource-search-until','#resource-alternatives']
    frame_required(page,fieldset_selectors)
    observe(page,'resource-fieldset-'+str(width),True)
    capture(page,'01-resource-fieldset-1200.png' if width==1200 else '02-resource-fieldset-390.png')
    # Read through the original button and renderer, not an injected renderer call.
    page.locator('#bundle-mine').click(timeout=15000)
    page.wait_for_function("()=>$('combination-items').querySelectorAll('.combination-result').length===1",timeout=15000)
    card=page.locator('#combination-items>.combination-result')
    assert card.locator('p').count()==4 and '3条占位均本地合成确认' in card.inner_text()
    assert card.locator('.boundary-note').inner_text()=='组合仅为本地合成记录。真实预约未确认，外部未受理，无线下履约。'
    assert card.locator('[data-combination-cancel]').count()==1
    if width==1200:resource_breakpoints(page,width)
    # Static Case warnings are original explanatory text, not a Case permission proof.
    delivery=page.locator('#delivery-panel');assert '资格请求不是事实或批准' in delivery.inner_text() and '旧占用及全部历史保留' in delivery.inner_text()
    assert page.locator('#delivery-confirm').is_disabled() and page.locator('#delivery-reapproval').is_disabled()
    REPORT.setdefault('resource_case_warning',[]).append(dict(width=width,text=delivery.inner_text(),scope='original static warnings and disabled gates, no Case read/action/permission acceptance'))
    compose_fixture(page,'#combination-items')
    frame_required(page,['[data-visual-fixture]','#combination-items>.combination-result'])
    observe(page,'resource-records-'+str(width),True)
    capture(page,'03-resource-records-1200.png' if width==1200 else '04-resource-records-390.png')


def guide_status(page,tone,fragment):
    page.wait_for_function("([tone,fragment])=>$('status').dataset.tone===tone&&$('status').textContent.includes(fragment)",arg=[tone,fragment],timeout=15000)
    row=page.locator('#status').evaluate("e=>({tone:e.dataset.tone,text:e.textContent,color:getComputedStyle(e).color,background:getComputedStyle(e).backgroundColor,role:e.getAttribute('role')})")
    assert row['role']=='status'
    REPORT.setdefault('guide_status',[]).append(row)
    return row


def guide_observation(page,context,origin,width):
    counts=request_counts()
    assert page.locator('aside>.notice').inner_text()=='所有确认、接单与回执只是模拟业务记录，不是正式来源、资格批准或真实履约。'
    assert page.locator('#workspace-open').is_disabled()
    for selector in ['.guide-session','.guide-roles','.guide-inputs','.guide-fill-actions','.guide-process','#sessions','#workspace-open']:
        bounded_rectangles(rectangles(page,[selector]))
    page.evaluate('()=>scrollTo(0,0)')
    entry=rectangles(page,['aside>.notice','.guide-session>label:has(#sessions)','#sessions','.guide-session>small','#workspace-open'])
    bounded_rectangles(entry,True);REPORT.setdefault('guide_entry',[]).append(dict(width=width,rows=entry))
    observe(page,'guide-entry-'+str(width),True)
    capture(page,'05-guide-entry-1200.png' if width==1200 else '06-guide-entry-390.png')
    neutral=guide_status(page,'neutral','等待选择')
    page.locator('#sessions').set_input_files(dict(name='invalid-synthetic.json',mimeType='application/json',buffer=b'{}'))
    error=guide_status(page,'error','未上传或使用')
    assert page.locator('button:not(:disabled)').count()==0
    if width==390:
        compose_fixture(page,'.guide-session');frame_required(page,['[data-visual-fixture]','#sessions','#workspace-open','#status'])
        capture(page,'07-guide-invalid-390.png')
    # Synthetic six-role input exists only in this context's memory; no real identities/credentials.
    payload={name:str(i)*43 for i,name in enumerate(['enterprise','specialist','executor','second_enterprise','second_specialist','second_executor'])}
    page.locator('#sessions').set_input_files(dict(name='synthetic-six-role-local-only.json',mimeType='application/json',buffer=json.dumps(payload).encode()))
    ready=guide_status(page,'success','不会自动办理')
    assert page.locator('button:not(:disabled)').count()==1
    assert len({(r['color'],r['background']) for r in [neutral,error,ready]})==3
    if width==390:
        compose_fixture(page,'.guide-session');frame_required(page,['[data-visual-fixture]','#sessions','#workspace-open','#status'])
        capture(page,'08-guide-ready-390.png')
    # Genuine original same-origin window.open; capture its real response bytes.
    responses=[];context.on('response',lambda response:responses.append(response))
    with page.expect_popup(timeout=15000) as opened:page.locator('#workspace-open').click(timeout=15000)
    popup=opened.value
    try:
        popup.wait_for_load_state('load',timeout=15000)
        assert popup.url==origin+'/'
        response=next(r for r in responses if r.url==origin+'/' and r.request.is_navigation_request())
        assert response.status==200 and response.body()==(PRIVATE/'current.html').read_bytes()
        popup.wait_for_function("()=>typeof $==='function'&&!!$('request-current')",timeout=15000)
        page.locator('[data-role="enterprise"]').click(timeout=15000)
        popup.wait_for_load_state('networkidle',timeout=15000)
        assert popup.locator('#token').input_value()==payload['enterprise']
        # Readiness/role GETs are separate from the four zero-request fill actions.
        fills=request_counts();popup.evaluate("()=>{window.__visualSubmitCount=0;document.addEventListener('submit',()=>window.__visualSubmitCount++,true)}")
        for name in ['fill-goal','fill-request','fill-need','fill-outline']:
            page.locator('#'+name).click(timeout=15000)
            if name=='fill-goal':assert popup.locator('#goal').input_value()==popup.locator('#prep-goal').input_value() and '6台设备' in popup.locator('#goal').input_value()
            elif name=='fill-request':assert '6台设备' in popup.locator('#request-current').input_value() and len(popup.locator('#plan-required-goals').input_value().splitlines())==5 and not popup.locator('#request-local-goal').is_checked()
            elif name=='fill-need':assert popup.locator('#prep-slot').input_value()=='need_summary' and '6台设备' in popup.locator('#prep-text').input_value()
            else:assert popup.locator('#prep-slot').input_value()=='material_outline' and '同用途通用资料目录' in popup.locator('#prep-text').input_value()
            assert fills==request_counts() and popup.evaluate('()=>window.__visualSubmitCount')==0
        # Long fill controls remain original and keyboard-focusable, no clipping/hiding.
        buttons=rectangles(page,['#'+x for x in ['fill-goal','fill-request','fill-need','fill-outline']]);bounded_rectangles(buttons)
        REPORT.setdefault('guide_cross_window',[]).append(dict(width=width,source_web_sha256=SOURCE_SHA256,same_origin_popup=True,role='synthetic enterprise',fill_actions=4,fill_request_delta=0,submit_events=0,scope='real DOM only; no Case/Run created, no business acceptance',long_buttons=buttons))
    finally:popup.close()
    # Controlled null-return branch, not native popup-blocker acceptance. Restore even on failure.
    page.evaluate('()=>{window.__visualNativeOpen=window.open;window.open=()=>null}')
    try:
        page.locator('#workspace-open').click(timeout=15000);guide_status(page,'error','没有提交业务')
        assert page.locator('[data-role="enterprise"]').is_disabled()
    finally:page.evaluate('()=>{window.open=window.__visualNativeOpen;delete window.__visualNativeOpen}')
    # Native keyboard details, restore every original open flag.
    original=page.locator('.guide-process>details').evaluate_all('xs=>xs.map(e=>e.open)')
    for index in range(3):
        detail=page.locator('.guide-process>details').nth(index);summary=detail.locator('summary');page.keyboard.press('Tab');summary.focus()
        assert summary.evaluate("e=>document.activeElement===e&&e.matches(':focus-visible')")
        summary.press('Enter',timeout=15000);assert detail.evaluate('e=>e.open')!=original[index]
        summary.press('Space',timeout=15000);assert detail.evaluate('e=>e.open')==original[index]
    assert page.locator('.guide-process>details').evaluate_all('xs=>xs.map(e=>e.open)')==original
    REPORT.setdefault('guide_details',[]).append(dict(width=width,original_open=original,Enter_Space_restored=True,scope='native keyboard actions, no PNG'))
    REPORT.setdefault('guide_scope',[]).append(dict(width=width,requests_including_root_popup_and_role_GET=len(REPORT['browser_requests'])-counts[1],file_selection='set_input_files; not OS chooser',popup_refusal='controlled original window.open null-return branch',all_steps_business_POST=0))


def run_flow(started):
    global OUT,PRIVATE,START
    os.umask(0o077);START=started;server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='40')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        pages,binding=source_contract();REPORT['source_binding']=binding
        (PRIVATE/'current.html').write_bytes(pages['web.html']);(PRIVATE/'guide.html').write_bytes(pages['park_demo_web.html'])
        REPORT['fixture_scope']='Transparent read-only HTTP response and client UI-state fixtures; not live business or permission acceptance'
        env=dict(os.environ)
        for key,name in [('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')]:
            p=PRIVATE/name;p.mkdir(mode=0o700);env[key]=str(p)
        env=installed_font_environment(env,PRIVATE/'fontconfig',REPORT,extra_text=FIXTURE_SUMMARY+FIXTURE_LABEL+RESOURCE_NAME+RESOURCE_MEMBER['purpose'])
        signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(90-(time.monotonic()-START))))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
        with owned_browser(env) as browser:
            base.resource.verify_sandbox(browser,REPORT);REPORT['browser_version']=browser.version
            for width in (1200,390):
                stage('RESOURCE_'+str(width));context,page=open_page(browser,origin,'/current',width)
                try:
                    mark_fixture(page)
                    page.locator('#token').fill('SYNTHETIC_UI_STATE_FIXTURE');page.keyboard.press('Tab')
                    page.wait_for_load_state('networkidle',timeout=15000)
                    resource_observation(page,width)
                finally:context.close()
                stage('GUIDE_'+str(width));context,page=open_page(browser,origin,'/guide',width)
                try:
                    # Marker is explicitly non-product; all product bytes and actions remain original.
                    page.evaluate("([summary,text])=>{const d=document.createElement('details');d.dataset.visualFixture='true';const h=document.createElement('summary');h.textContent=summary;const p=document.createElement('p');p.textContent=text;d.append(h,p);document.querySelector('aside').prepend(d)}",[FIXTURE_SUMMARY,FIXTURE_LABEL])
                    guide_observation(page,context,origin,width)
                finally:context.close()
            assert RESOURCE_READS==RESOURCE_LIMITS,'each exact resource GET must be consumed'
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
        source=base.require_hosted(os.environ,run_number='40')
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
