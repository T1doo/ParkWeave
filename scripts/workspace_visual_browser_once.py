"""Run42/attempt1 candidate: isolated template UI and stable guide button; no product backend."""
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
BASELINE_SHA='4406f5f254bb53e53ca08ba8bd50ea228e36b67e'
SOURCE_SHA256='7798e0e5c08462fd98cc20382d9e429a57a58ca61bbe95513c32065c7d755884'
GUIDE_SHA256='966f175764bdf323eea9c6e87f520c584da6ae03243b5c0396e492ce76a1af8c'
TEMPLATE_SHA256='69882b775d78f571f3a1a70aeff1a38c4ae178df0e97f62cd9b4956b69b2e010'
ISOLATED_ENTRY_SOURCES={'src/parkweave/template_isolated_app.py':'22eaee2712d5a5e83d7c9dbd397272d8d7dfdfe45b84438d2c31b06448bde27a','src/parkweave/template_candidate_api.py':'dc6522606369b9b06714491602649b006cde0fee9a0cbcbcae14946ab619bec4'}
PNG_FILES=('01-template-entry-1200.png','02-template-entry-390.png','03-template-fields-1200.png',
    '04-template-fields-390.png','05-template-return-1200.png','06-template-return-390.png','07-guide-stable-390.png')
PUBLIC_FILES=frozenset(PNG_FILES+('failure-visual.png','result.json'))
EXPECTED_CHANGED_PATHS=frozenset((
    '.github/workflows/fictional-park-browser-once.yml','scripts/workspace_visual_browser_once.py',
    'scripts/fictional_park_font_once.py','docs/F2/evidence/eng057-job-shards.json',
    'docs/demo/evidence/task-desk-20261023/run42/README.md',
    'docs/demo/evidence/task-desk-20261023/run42/preflight.json',
    'docs/demo/evidence/task-desk-20261023/run42/SHA256SUMS'))
FIXTURE_SUMMARY='合成界面复放 · 无真实业务、身份或授权'
FIXTURE_LABEL='SYNTHETIC UI_STATE_FIXTURE / READ_ONLY_RESPONSE_FIXTURE · 静态交互复放，非真实业务、身份或授权。'


def presentation_contract(reviewed,current,page='web.html'):
    fingerprints={'web.html':SOURCE_SHA256,'park_demo_web.html':GUIDE_SHA256,'template_candidate_web.html':TEMPLATE_SHA256}
    assert page in fingerprints,'only exact reviewed original pages permitted'
    expected=fingerprints[page]
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
    for name in ['web.html','park_demo_web.html','template_candidate_web.html']:
        path='src/parkweave/'+name;current=(ROOT/path).read_bytes()
        reviewed=subprocess.check_output(['git','show',BASELINE_SHA+':'+path],cwd=ROOT)
        presentation_contract(reviewed,current,name);pages[name]=current
    for path,digest in ISOLATED_ENTRY_SOURCES.items():
        reviewed=subprocess.check_output(['git','show',BASELINE_SHA+':'+path],cwd=ROOT)
        assert (ROOT/path).read_bytes()==reviewed and hashlib.sha256(reviewed).hexdigest()==digest,'isolated entry source changed'
    return pages,dict(reviewed_product_sha=BASELINE_SHA,current_web_sha256=SOURCE_SHA256,
        current_guide_sha256=GUIDE_SHA256,current_template_sha256=TEMPLATE_SHA256,isolated_entry_sources=ISOLATED_ENTRY_SOURCES,
        isolated_entry_scope="Static replay of original /template bytes only; factory/API/engine not started or enabled",product_pages_identical_to_reviewed_baseline=True,
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
        if path in ('/current','/','/guide','/template'):
            body=(PRIVATE/('guide.html' if path=='/guide' else 'template.html' if path=='/template' else 'current.html')).read_bytes();kind='text/html; charset=utf-8';code=200
        elif path in FIXTURE_REPLIES:
            FIXTURE_READS[path]=FIXTURE_READS.get(path,0)+1
            if FIXTURE_READS[path]>FIXTURE_LIMITS[path]:
                REPORT['unexpected_GET'].append(path);body=b'{}';code=404
            else:body=json.dumps(FIXTURE_REPLIES[path],ensure_ascii=False).encode();code=200
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
    assert response.status==200 and response.body()==(PRIVATE/('guide.html' if path=='/guide' else 'template.html' if path=='/template' else 'current.html')).read_bytes()
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


FIXTURE_READS={}
FIXTURE_REPLIES={'/api/template-candidate/status':dict(enabled_for_isolated_tests=False,isolated_personas=[],isolated_principals=[],registered_goals=['LOCAL_MATERIAL_PREPARATION'],namespace='ISOLATED_SYNTHETIC_TEMPLATE_CANDIDATE',candidate_demo=False,business_publication=False,deployment_enabled=False,new_grants=False,automatic_execution=False,case_goal_completed=False,contract_revision=1,compatible_publication_only=False)}
FIXTURE_LIMITS={'/api/template-candidate/status':2}
TEMPLATE_FIXTURE=r"""() => {
 const f=window.__templateVisual={sentinel:crypto.randomUUID()};
 f.draft='SYNTHETIC 界面复放：为园区联合培训准备资料，不是正式事项或资格结论。';
 const goals=['LOCAL_MATERIAL_PREPARATION','SYNTHETIC_EXTERNAL_AUTHORITY_APPROVAL'];
 renderPlanning({plan_id:null,request_intent:{current_request:f.draft,required_goals:goals,planning_constraints:{excluded_roles:['service_executor'],additional_requirements:['SYNTHETIC 待人工核对的附加条件，不自动判为满足']}},current:{state:'PARTIAL',preparation_revision:1,partial_offer:{can_adopt:true,step_ids:['P1'],waiting_step_ids:['P2'],manual_goals:['SYNTHETIC_EXTERNAL_AUTHORITY_APPROVAL']},steps:[]},service_case_plan:{can_adopt_partial:true}});
 f.fields={};for(const id of ['consumer-release','consumer-reviewer','consumer-goal','consumer-need-summary','consumer-material-outline','consumer-need-source','consumer-outline-source','consumer-exclude-owner','consumer-exclude-specialist','consumer-exclude-executor','consumer-additional','consumer-plan-reason','consumer-partial-confirm']){
  if(['consumer-need-summary','consumer-material-outline'].includes(id))$(id).value=f.draft;
  f.fields[id]={value:$(id).value,checked:$(id).checked};
 }
 f.goals=[...document.querySelectorAll('[data-consumer-goal]')].map(e=>[e.dataset.consumerGoal,e.checked]);
 f.snapshot=()=>JSON.stringify({fields:Object.fromEntries(Object.keys(f.fields).map(id=>[id,{value:$(id).value,checked:$(id).checked,disabled:$(id).disabled}])),goals:[...document.querySelectorAll('[data-consumer-goal]')].map(e=>({goal:e.dataset.consumerGoal,checked:e.checked,disabled:e.disabled})),cp,planningView,confirmed,instance,catalog,handle:adoptionHandle,storage:Object.keys(localStorage).sort().map(k=>[k,localStorage.getItem(k)])});
 f.mode=mode=>{cp=mode?{state:mode,action:'CREATE',key:'SYNTHETIC_VISUAL_ONLY',body:{goal:f.draft},fields:structuredClone(f.fields),goals:structuredClone(f.goals)}:null;buttons();f.cp=cp;f.body=cp?.body;f.before=f.snapshot();};
 f.same=()=>({sentinel:f.sentinel,cpSame:cp===f.cp,bodySame:cp?.body===f.body,snapshotSame:f.snapshot()===f.before});
 f.mode(null);window.__sameTemplateDocument=f.sentinel;
}"""


def request_counts():return (len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])


def rectangles(page,selectors):
    return page.evaluate("""selectors=>selectors.map(selector=>{const e=document.querySelector(selector);if(!e)throw Error('required node missing '+selector);const r=e.getBoundingClientRect();return {selector,visible:!!e.getClientRects().length,left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height,viewportWidth:innerWidth,viewportHeight:innerHeight}})""",selectors)


def bounded_rectangles(rows,viewport=False):
    assert all(x['visible'] and x['width']>0 and x['height']>0 and 0<=x['left']<x['right']<=x['viewportWidth'] for x in rows),rows
    if viewport:assert all(0<=x['top']<x['bottom']<=x['viewportHeight'] for x in rows),rows


def frame_required(page,selectors):
    require_operation_time(5);counts=request_counts();viewport=dict(page.viewport_size)
    rows=rectangles(page,selectors);delta=dispatch_frame_delta(rows,1000)
    page.evaluate('delta=>window.scrollBy({top:delta,behavior:"instant"})',delta)
    rows=rectangles(page,selectors);bounded_rectangles(rows,True)
    assert all(16<=x['top'] and x['bottom']<=984 for x in rows),rows
    assert counts==request_counts() and dict(page.viewport_size)==viewport
    REPORT.setdefault('screenshot_framing',[]).append(dict(selectors=selectors,scroll_delta=delta,rectangles=rows))


def template_marker(page):
    page.evaluate("""([summary,text])=>{const n=document.createElement('details');n.dataset.visualFixture='true';n.style.cssText='padding:8px;border:1px dashed #b2a16e;background:#fff6dc;color:#614b19;font-size:12px;line-height:1.5';const s=document.createElement('summary');s.textContent=summary;const p=document.createElement('p');p.textContent=text;n.append(s,p);$('banner').after(n)}""",['候选未启用 · '+FIXTURE_SUMMARY,FIXTURE_LABEL])

    assert page.locator('[data-visual-fixture]>summary').inner_text()=='候选未启用 · '+FIXTURE_SUMMARY

def template_safety(page):
    assert page.locator('#banner').inner_text()=='候选未启用：没有显式隔离合同，审核发布与新建事项均不可用。'
    assert page.evaluate('()=>status.enabled_for_isolated_tests===false&&status.isolated_personas.length===0&&instance===null&&catalog===null&&confirmed===null&&view===null')
    assert page.locator('[data-template-action]:not(:disabled)').count()==0
    for name in ['consumer-create','consumer-resume','consumer-confirm','consumer-save-request','consumer-adopt','consumer-adoption-finalize']:
        assert page.locator('#'+name).is_disabled(),name


def native_template_link(page,link,target,first,method):
    require_operation_time(15);counts=request_counts()
    before=page.evaluate('()=>({hash:location.hash,history:history.length,sentinel:window.__sameTemplateDocument,proof:window.__templateVisual.same()})')
    assert before['hash']!='#'+target
    locator=page.locator(link)
    if method=='mouse':locator.click(timeout=15000)
    else:locator.focus();page.keyboard.press('Enter')
    page.wait_for_function('target=>location.hash==="#"+target',arg=target,timeout=15000)
    at=page.evaluate('()=>({hash:location.hash,history:history.length,sentinel:window.__sameTemplateDocument,active:document.activeElement.id,focusVisible:document.activeElement.matches(":focus-visible"),heading:(()=>{const e=document.activeElement.querySelector(":scope>h2");if(!e)return null;const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:innerWidth,height:innerHeight}})(),proof:window.__templateVisual.same()})')
    assert at['sentinel']==before['sentinel'] and at['active']==target and at['history'] in (before['history'],before['history']+1),dict(before=before,at=at)
    heading=at['heading'];assert heading and 0<=heading['top']<heading['bottom']<=heading['height'] and 0<=heading['left']<heading['right']<=heading['width'],at
    if method=='Enter':assert at['focusVisible'],at
    assert all(at['proof'][k] for k in ['cpSame','bodySame','snapshotSame']),at
    # Back retains a forward entry; the next native anchor may replace it rather than grow length.
    page.keyboard.press('Tab');tab=page.evaluate("()=>({id:document.activeElement.id,focusVisible:document.activeElement.matches(':focus-visible')})");assert tab==dict(id=first,focusVisible=True),tab
    page.go_back(timeout=15000,wait_until='load')
    page.wait_for_function('hash=>location.hash===hash',arg=before['hash'],timeout=15000)
    after=page.evaluate('()=>({hash:location.hash,sentinel:window.__sameTemplateDocument,proof:window.__templateVisual.same()})')
    assert after['sentinel']==before['sentinel'] and all(after['proof'][k] for k in ['cpSame','bodySame','snapshotSame']) and counts==request_counts(),after
    REPORT.setdefault('template_navigation',[]).append(dict(method=method,target=target,landed=at,after_back=after,subsequent_Tab=tab,request_delta=0))


def template_breakpoints(page):
    counts=request_counts();viewport=dict(page.viewport_size);scroll=page.evaluate('()=>({x:scrollX,y:scrollY})')
    try:
        for width in [700,899,900]:
            page.set_viewport_size(dict(width=width,height=1000))
            row=page.evaluate("""()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,session:getComputedStyle(document.querySelector('.consumer-session')).gridTemplateColumns,draft:getComputedStyle(document.querySelector('.consumer-draft')).display,draftColumns:getComputedStyle(document.querySelector('.consumer-draft')).gridTemplateColumns})""")
            assert row['documentWidth']<=width
            assert len(row['session'].split())==(1 if width<=700 else 2),row
            assert row['draft']==('grid' if width>=900 else 'block'),row
            if width>=900:assert len(row['draftColumns'].split())==2,row
            bounded_rectangles(rectangles(page,['.consumer-session','.consumer-draft','.consumer-return','.consumer-plan','#consumer-partial-label']))
            REPORT.setdefault('template_breakpoints_geometry_only',[]).append(row)
    finally:page.set_viewport_size(viewport);page.evaluate('p=>scrollTo({left:p.x,top:p.y,behavior:"instant"})',scroll)
    assert dict(page.viewport_size)==viewport and page.evaluate('()=>({x:scrollX,y:scrollY})')==scroll and counts==request_counts()


def template_observation(page,width):
    page.wait_for_function('()=>status!==null',timeout=15000);template_safety(page);template_marker(page)
    page.evaluate('()=>scrollTo(0,0)')
    bounded_rectangles(rectangles(page,['body>h1','#banner','.template-entry-nav']),True)
    observe(page,'template-entry-'+str(width),True);capture(page,'01-template-entry-1200.png' if width==1200 else '02-template-entry-390.png')
    page.evaluate(TEMPLATE_FIXTURE);template_safety(page)
    for link,target,first in [('a[href="#template-consumer-workspace"]','template-consumer-workspace','consumer-token'),('a[href="#template-governance-workspace"]','template-governance-workspace','template-actor')]:
        for method in ['mouse','Enter']:native_template_link(page,link,target,first,method)
    for mode in ['SUBMITTING','UNKNOWN']:
        guard_counts=request_counts()
        page.evaluate('mode=>window.__templateVisual.mode(mode)',mode);template_safety(page)
        rows=page.evaluate("""()=>Object.keys(window.__templateVisual.fields).map(id=>({id,disabled:$(id).disabled,color:getComputedStyle($(id)).color,background:getComputedStyle($(id)).backgroundColor}))""")
        assert all(r['disabled'] for r in rows),rows
        native_template_link(page,'a[href="#template-consumer-workspace"]','template-consumer-workspace','consumer-token','Enter')
        # Controlled DOM mutation on a disabled draft tests the original restore handler, not native typing.
        page.evaluate("()=>{$('consumer-goal').value='SYNTHETIC rejected visual edit';$('consumer-goal').dispatchEvent(new Event('input',{bubbles:true}))}")
        assert page.evaluate('()=>window.__templateVisual.same().snapshotSame') and guard_counts==request_counts()
        REPORT.setdefault('template_pending_guards',[]).append(dict(width=width,state=mode,disabled=rows,original_object_body_draft_preserved=True,request_delta=0,scope='transparent client UI-state only; no actual submitted request/permission'))
    if width==1200:template_breakpoints(page)
    # Long original PARTIAL checkbox is measured/font-read without a dedicated PNG or real eligibility claim.
    page.locator('#consumer-partial-label').evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})")
    partial=rectangles(page,['#consumer-partial-label']);bounded_rectangles(partial,True)
    assert not page.locator('#consumer-partial-confirm').is_checked() and page.locator('#consumer-partial-confirm').is_disabled()
    observe(page,'template-long-partial-label-geometry-only-'+str(width),True)
    REPORT.setdefault('template_partial_label_geometry_only',[]).append(dict(width=width,rows=partial,scope='renderer fixture, not a real partial offer or authorization'))
    compose_fixture(page,'.consumer-draft>fieldset:first-of-type')
    frame_required(page,['[data-visual-fixture]','.consumer-draft>fieldset:nth-of-type(1)','.consumer-draft>fieldset:nth-of-type(2)'])
    observe(page,'template-fields-'+str(width),True);capture(page,'03-template-fields-1200.png' if width==1200 else '04-template-fields-390.png')
    compose_fixture(page,'.consumer-return');frame_required(page,['.consumer-return'])
    observe(page,'template-return-'+str(width),True);capture(page,'05-template-return-1200.png' if width==1200 else '06-template-return-390.png')
    template_safety(page)


def rgba_color(value):
    import re
    m=re.fullmatch(r'rgba?\(([^)]+)\)',value);assert m,value
    numbers=[float(n.strip()) for n in m[1].split(',')];assert len(numbers) in (3,4) and (len(numbers)==3 or numbers[3]==1),value
    assert all(0<=n<=255 for n in numbers[:3]);return numbers[:3]


def contrast_ratio(foreground,background):
    def luminance(channels):
        values=[n/255 for n in channels];values=[n/12.92 if n<=.04045 else ((n+.055)/1.055)**2.4 for n in values]
        return sum(n*w for n,w in zip(values,[.2126,.7152,.0722]))
    low,high=sorted([luminance(rgba_color(foreground)),luminance(rgba_color(background))]);return (high+.05)/(low+.05)


GUIDE_BUTTON_STYLE="""()=>{const e=$('workspace-open'),s=getComputedStyle(e);return {color:s.color,background:s.backgroundColor,opacity:s.opacity,disabled:e.disabled,transitionDuration:s.transitionDuration,transitionProperty:s.transitionProperty,animations:e.getAnimations({subtree:true}).map(a=>({playState:a.playState,currentTime:a.currentTime,duration:a.effect.getTiming().duration}))}}"""


def guide_stable_observation(page):
    page.evaluate("([summary,text])=>{const d=document.createElement('details');d.dataset.visualFixture='true';const h=document.createElement('summary');h.textContent=summary;const p=document.createElement('p');p.textContent=text;d.append(h,p);document.querySelector('aside').prepend(d)}",[FIXTURE_SUMMARY,FIXTURE_LABEL])
    payload={name:str(i)*43 for i,name in enumerate(['enterprise','specialist','executor','second_enterprise','second_specialist','second_executor'])}
    page.locator('#sessions').set_input_files(dict(name='synthetic-six-role-local-only.json',mimeType='application/json',buffer=json.dumps(payload).encode()))
    page.wait_for_function("()=>$('status').dataset.tone==='success'&&!$('workspace-open').disabled",timeout=15000)
    # Keep the original transition intact and wait for its actual completion.
    page.wait_for_function("()=>$('workspace-open').getAnimations({subtree:true}).every(a=>a.playState==='finished'||a.playState==='idle')",timeout=15000)
    page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    compose_fixture(page,'.guide-session');frame_required(page,['[data-visual-fixture]','#sessions','#workspace-open','#status'])
    before=page.evaluate(GUIDE_BUTTON_STYLE);assert not before['disabled'] and before['opacity']=='1' and not before['animations'],before
    ratio=contrast_ratio(before['color'],before['background']);assert ratio>=4.5,(before,ratio)
    observe(page,'guide-stable-enabled-button-390',True);capture(page,'07-guide-stable-390.png')
    after=page.evaluate(GUIDE_BUTTON_STYLE);assert after==before,(before,after)
    REPORT['guide_stable_button']=dict(before=before,after=after,contrast_ratio=ratio,viewport=dict(page.viewport_size),scope='actual stable computed state around PNG; not causation proof for old08 frame or full accessibility')


def run_flow(started):
    global OUT,PRIVATE,START
    os.umask(0o077);START=started;server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='42')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        pages,binding=source_contract();REPORT['source_binding']=binding
        (PRIVATE/'current.html').write_bytes(pages['web.html']);(PRIVATE/'guide.html').write_bytes(pages['park_demo_web.html']);(PRIVATE/'template.html').write_bytes(pages['template_candidate_web.html'])
        REPORT['fixture_scope']='Transparent closed-status UI projection and client renderer fixtures; not create_isolated_template_app execution, business or permission acceptance'
        env=dict(os.environ)
        for key,name in [('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')]:
            p=PRIVATE/name;p.mkdir(mode=0o700);env[key]=str(p)
        env=installed_font_environment(env,PRIVATE/'fontconfig',REPORT,extra_text=FIXTURE_SUMMARY+FIXTURE_LABEL+pages['template_candidate_web.html'].decode('utf-8'))
        signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(90-(time.monotonic()-START))))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
        with owned_browser(env) as browser:
            base.resource.verify_sandbox(browser,REPORT);REPORT['browser_version']=browser.version
            for width in (1200,390):
                stage('TEMPLATE_'+str(width));context,page=open_page(browser,origin,'/template',width)
                try:template_observation(page,width)
                finally:context.close()
            stage('GUIDE_STABLE_390');context,page=open_page(browser,origin,'/guide',390)
            try:guide_stable_observation(page)
            finally:context.close()
            assert FIXTURE_READS==FIXTURE_LIMITS,'each exact closed template status GET must be consumed'
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
        source=base.require_hosted(os.environ,run_number='42')
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
