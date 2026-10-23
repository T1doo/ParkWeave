"""Run38/attempt1 candidate: native return paths and collaboration; no product backend."""
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
BASELINE_SHA='86bd185ddc33da4e617e2ebaa540d074d000e454'
SOURCE_SHA256='9711354a500e0940f1be9677b38e9d35d68e03a5485aa0ba4c9bd8d43ab30aa2'
GUIDE_SHA256='1d1aefb15eda9ef9107220e8c72e8a1b864d0eac1b6a46c0e3203cca7508163e'
PNG_FILES=('01-service-entry-1200.png','02-service-entry-390.png',
    '03-native-existing-390.png','04-native-formal-390.png','05-collaboration-empty-1200.png',
    '06-collaboration-records-1200.png','07-collaboration-records-390.png','08-collaboration-denied-390.png')
PUBLIC_FILES=frozenset(PNG_FILES+('failure-visual.png','result.json'))
EXPECTED_CHANGED_PATHS=frozenset((
    '.github/workflows/fictional-park-browser-once.yml','scripts/workspace_visual_browser_once.py',
    'scripts/fictional_park_font_once.py','docs/F2/evidence/eng057-job-shards.json',
    'docs/demo/evidence/task-desk-20261023/run38/README.md',
    'docs/demo/evidence/task-desk-20261023/run38/preflight.json',
    'docs/demo/evidence/task-desk-20261023/run38/SHA256SUMS'))
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
        if path=='/current':
            body=(PRIVATE/'current.html').read_bytes();kind='text/html; charset=utf-8';code=200
        elif path in LIST_PATHS.values():
            name=next(k for k,v in LIST_PATHS.items() if v==path)
            try:fixture=LIST_REPLIES[name].get_nowait()
            except queue.Empty:
                REPORT['unexpected_GET'].append(path);body=b'{}';kind='application/json';code=404
            else:
                fixture['started'].set()
                if not fixture['release'].wait(5):
                    REPORT['violations'].append(dict(path=path,reason='controlled fixture release missed5s'))
                    body=b'{}';code=504
                else:body=fixture['body'];code=fixture['code']
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


def visible_in_viewport(page,ids):
    rows=page.evaluate("""ids=>ids.map(id=>{const e=$(id),r=e.getBoundingClientRect();return {id,
        visible:!!e.getClientRects().length,top:r.top,bottom:r.bottom,height:innerHeight,text:e.textContent}})""",ids)
    assert all(r['visible'] and 0<=r['top'] and r['bottom']<=r['height'] for r in rows),rows
    return rows


NAVIGATION_WORKSPACE_SCRIPT="""() => ({
    workspace:{present:document.body.hasAttribute('data-workspace'),value:document.body.getAttribute('data-workspace')},
    current:[...document.querySelectorAll('[data-tab][aria-current=page]')].map(e=>e.dataset.tab),
    panels:['service','collaboration','resource'].map(id=>({id,hidden:$(id).hidden}))})
"""


def assert_navigation_workspace(before,after):
    assert before['workspace'] in ({'present':False,'value':None},{'present':True,'value':'service'}),before
    assert before['current']==['service'],before
    assert before['panels']==[dict(id=name,hidden=name!='service') for name in ('service','collaboration','resource')],before
    assert after==before,dict(before=before,after=after)


RETURN_LINKS=(('existing-preparation-jump','existing-preparation-entry','existing-preparation-id'),
    ('formal-preparation-jump','formal-preparation-entry','formal-preparation-check'))
LIST_PATHS={'dispatch':'/api/service-dispatches','receipt':'/api/executor-receipts'}
LIST_REPLIES={kind:queue.Queue(maxsize=1) for kind in LIST_PATHS}
FIXTURE_GOAL='合成界面夹具：为星河制造整理园区联合培训材料，等待本人核对原记录'

def request_counts():return (len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])

def same_document_snapshot(page):
    return page.evaluate("""() => ({hash:location.hash,history:history.length,
        active:document.activeElement.id,workspace:document.body.getAttribute('data-workspace'),
        epochs:[tiEpoch,templateEntryGeneration]})""")


def entry_observation(page,width):
    require_operation_time(5)
    row=page.evaluate("""() => {const box=e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right}};
        return {width:innerWidth,links:box(document.querySelector('.return-entry-links')),
            primary:box(document.querySelector('.primary-entry-heading')),firstAction:box($('prep-catalog')),
            documentFirstActionTop:$('prep-catalog').getBoundingClientRect().top+scrollY,
            existingTop:$('existing-preparation-entry').getBoundingClientRect().top+scrollY,
            formalTop:$('formal-preparation-entry').getBoundingClientRect().top+scrollY};} """)
    assert row['links']['top']<row['primary']['top']<row['firstAction']['top'],row
    assert 0<=row['firstAction']['top']<row['firstAction']['bottom']<=1000,row
    REPORT.setdefault('entry_geometry',[]).append(row)
    observe(page,'current-return-entry-'+str(width),True)
    capture(page,'01-service-entry-1200.png' if width==1200 else '02-service-entry-390.png')


def capture(page,name):
    require_operation_time(15)
    assert name in PUBLIC_FILES and name.endswith('.png')
    assert page.locator('[data-visual-fixture] > summary').evaluate("e=>{const r=e.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth}")
    page.screenshot(path=str(OUT/name),timeout=15000,full_page=False)


def compose_fixture(page,selector):
    # Only after raw native/geometry measurements. This is screenshot framing,
    # never the oracle for browser navigation landing or original target focus.
    page.evaluate("""selector=>{const n=document.querySelector('[data-visual-fixture]'),target=document.querySelector(selector);
        if(!n||!target)throw Error('fixture composition target missing');target.prepend(n);target.scrollIntoView({block:'start',behavior:'instant'});} """,selector)
    REPORT.setdefault('screenshot_composition',[]).append(dict(selector=selector,scope='Move only the explicit fixture marker, then frame original section; not native landing proof'))


def native_return(page,link,target,first,method,*,shot=None):
    require_operation_time(15)
    assert not page.evaluate('()=>!!activeEntryWriteFlow||entryWriteRequests.size>0||!!receiptLocalPending')
    before=same_document_snapshot(page);counts=request_counts()
    assert before['hash']!='#'+target
    document_token=page.evaluate("()=>{window.__returnDocument=window.__returnDocument||{id:crypto.randomUUID()};window.__beforeReturnDocument=window.__returnDocument;return window.__returnDocument.id;}")
    if method=='mouse':page.locator('#'+link).click(timeout=15000)
    else:page.locator('#'+link).focus();page.keyboard.press('Enter')
    page.wait_for_function('id=>location.hash==="#"+id',arg=target,timeout=15000)
    landed=same_document_snapshot(page)
    assert landed['active']==target and landed['workspace']==before['workspace'],landed
    assert landed['epochs']==[x+1 for x in before['epochs']],landed
    assert page.evaluate('token=>!!window.__returnDocument&&!!window.__beforeReturnDocument&&window.__returnDocument===window.__beforeReturnDocument&&window.__returnDocument.id===token',document_token)
    raw=page.locator('#'+target).evaluate("e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height,heading:e.querySelector('h2').textContent,warning:e.querySelector('p').textContent}}")
    assert raw['height']>0 and -1<=raw['top']<1000,raw
    page.keyboard.press('Tab');tab=page.evaluate('()=>document.activeElement.id');assert tab==first,(target,tab)
    if shot:
        compose_fixture(page,'#'+target)
        visible_in_viewport(page,[target])
        observe(page,'current-return-target-'+target,True);capture(page,shot)
        # Restore marker to the original preparation position before Back.
        page.evaluate("()=>$('prep-catalog').before(document.querySelector('[data-visual-fixture]'))")
    page.go_back(wait_until='load',timeout=15000)
    page.wait_for_function('hash=>location.hash===hash',arg=before['hash'],timeout=15000)
    restored=same_document_snapshot(page)
    assert restored['workspace']==before['workspace'] and restored['epochs']==landed['epochs'],restored
    assert page.evaluate('token=>!!window.__returnDocument&&!!window.__beforeReturnDocument&&window.__returnDocument===window.__beforeReturnDocument&&window.__returnDocument.id===token',document_token)
    assert counts==request_counts(),'same-document return navigation made a request'
    REPORT.setdefault('return_navigation',[]).append(dict(width=page.viewport_size['width'],link=link,method=method,
        before=before,landed=landed,raw_native_target=raw,next_Tab=tab,back=restored,request_delta=0,
        scope='Actual mouse/Enter/Tab/Back; no target.focus, hash assignment or scroll used to establish native landing'))


RETURN_FIXTURE_INSTALL="""mode => {
    if(prepCommandPending||receiptLocalPending||activeEntryWriteFlow||entryWriteRequests.size)throw Error('nonempty original write state');
    const f={mode,pending:{context:prepContext(),state:'UNKNOWN',key:'11111111-1111-4111-8111-111111111111',
        body:{action:'ADD_EVIDENCE',expected_revision:1,text:'SYNTHETIC UI_STATE_FIXTURE, never sent'}},
        flow:{kind:'SYNTHETIC_UI_STATE_FIXTURE',requests:new Map()},op:{kind:'SYNTHETIC_UI_STATE_FIXTURE',path:'/api/runs/22222222-2222-4222-8222-222222222222'},
        map:entryWriteRequests,draft:$('prep-text').value,goal:$('prep-goal').value};
    $('prep-text').value='SYNTHETIC original unsent draft';$('prep-goal').value='SYNTHETIC original unsent goal';
    if(mode==='prep-unknown')prepCommandPending=f.pending;
    else if(mode==='receipt-unknown')receiptLocalPending=f.pending;
    else if(mode==='active-flow')activeEntryWriteFlow=f.flow;
    else if(mode==='retained-lease')entryWriteRequests.set('SYNTHETIC_UI_STATE_FIXTURE',f.op);
    else throw Error('unknown fixture mode');
    f.body=f.pending.body;f.context=f.pending.context;f.flowRequests=f.flow.requests;
    f.snapshot=()=>{const copy=document.body.cloneNode(true);for(const id of ['result','page-feedback','receipt-local-execution-error']){copy.querySelector('#'+id).replaceChildren();copy.querySelector('#'+id).removeAttribute('data-tone');}
        return JSON.stringify({DOM:copy.innerHTML,controls:[...document.querySelectorAll('input,textarea,select,button')].map(e=>({id:e.id,value:e.value,checked:e.checked,disabled:e.disabled,hidden:e.hidden})),
        pending:prepCommandPending,receipt:receiptLocalPending,flow:activeEntryWriteFlow,flowRequestEntries:[...f.flow.requests],flowRequestSize:f.flow.requests.size,ops:[...entryWriteRequests],
        workspace:document.body.getAttribute('data-workspace'),panels:['service','collaboration','resource'].map(id=>[id,$(id).hidden])});};
    f.serialized=JSON.stringify(f.pending);f.before=f.snapshot();window.__returnStateFixture=f;return {mode,scope:'Explicit client UI state only; no request, business identity or authority'};
}"""
RETURN_FIXTURE_COMPARE="""() => {
    const f=window.__returnStateFixture;if(!f||f.map!==entryWriteRequests||f.pending.body!==f.body||f.pending.context!==f.context||f.flow.requests!==f.flowRequests||JSON.stringify(f.pending)!==f.serialized||f.snapshot()!==f.before)throw Error('original pending/draft/control state changed');
    if(f.mode==='prep-unknown'&&prepCommandPending!==f.pending||f.mode==='receipt-unknown'&&receiptLocalPending!==f.pending||f.mode==='active-flow'&&activeEntryWriteFlow!==f.flow||f.mode==='retained-lease'&&entryWriteRequests.get('SYNTHETIC_UI_STATE_FIXTURE')!==f.op)throw Error('fixture object reference changed');
    return {same_pending_reference_and_body:true,same_drafts_controls_and_workspace:true,same_flow_Map_op_reference:true};
}"""
RETURN_FIXTURE_RELEASE="""() => {
    const f=window.__returnStateFixture;
    if(!f||f.snapshot()!==f.before)throw Error('cannot release changed state');
    if(f.mode==='prep-unknown'){if(prepCommandPending!==f.pending)throw Error('pending changed');prepCommandPending=null;}
    if(f.mode==='receipt-unknown'){if(receiptLocalPending!==f.pending)throw Error('receipt changed');receiptLocalPending=null;}
    if(f.mode==='active-flow'){if(activeEntryWriteFlow!==f.flow)throw Error('flow changed');activeEntryWriteFlow=null;}
    if(f.mode==='retained-lease'){if(entryWriteRequests.get('SYNTHETIC_UI_STATE_FIXTURE')!==f.op)throw Error('op changed');entryWriteRequests.delete('SYNTHETIC_UI_STATE_FIXTURE');}
    $('prep-text').value=f.draft;$('prep-goal').value=f.goal;delete window.__returnStateFixture;
}"""


def return_guard_observation(page):
    require_operation_time(15)
    for mode in ('prep-unknown','active-flow','retained-lease','receipt-unknown'):
        fixture=page.evaluate(RETURN_FIXTURE_INSTALL,mode)
        try:
            for link,target,first in RETURN_LINKS:
                for method in ('mouse','Enter'):
                    if mode=='prep-unknown':
                        native_return(page,link,target,first,method)
                        proof=page.evaluate(RETURN_FIXTURE_COMPARE)
                        detail=dict(native_observation_index=len(REPORT['return_navigation'])-1)
                    else:
                        before=same_document_snapshot(page);counts=request_counts()
                        assert before['hash']!='#'+target
                        if method=='mouse':page.locator('#'+link).click(timeout=15000)
                        else:page.locator('#'+link).focus();page.keyboard.press('Enter')
                        after=same_document_snapshot(page);proof=page.evaluate(RETURN_FIXTURE_COMPARE)
                        assert after['hash']==before['hash'] and after['history']==before['history'] and after['active']!=target,(mode,before,after)
                        expected=before['epochs'] if mode=='receipt-unknown' else [x+1 for x in before['epochs']]
                        assert after['epochs']==expected,(mode,before,after)
                        assert counts==request_counts()
                        feedback=page.locator('#receipt-local-execution-error' if mode=='receipt-unknown' else '#page-feedback').text_content()
                        expected_feedback='本地执行结果未知；请先使用原请求重试。切换页面或角色会清除此身份的私有请求状态。' if mode=='receipt-unknown' else '请先在原入口核对尚未确定的操作；原请求编号与草稿保留，可使用原入口只读恢复。'
                        assert feedback==expected_feedback,feedback
                        detail=dict(before=before,after=after,feedback=feedback)
                    REPORT.setdefault('return_state_guards',[]).append(dict(fixture=fixture,link=link,method=method,proof=proof,
                        default_navigation='ALLOWED_LOCATION_ONLY' if mode=='prep-unknown' else 'PREVENTED',request_delta=0,**detail))
        finally:page.evaluate(RETURN_FIXTURE_RELEASE)


def queue_list(kind,state,held=False):
    ids=['11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222']
    rows=[dict(id=id,preparation_id=('33333333-3333-4333-8333-333333333333' if i==0 else '44444444-4444-4444-8444-444444444444'),
        goal=FIXTURE_GOAL,state='LOCAL_ACKNOWLEDGED' if i==0 else 'SYNTHETIC_UNMAPPED',case_cancelled=i==0,case_write_blocked=i==0) for i,id in enumerate(ids)]
    data=dict(role='enterprise_operator',scope='SYNTHETIC_INTERNAL_DISPATCH_ONLY' if kind=='dispatch' else 'SYNTHETIC_ASSIGNED_EXECUTOR_RECEIPT_ONLY',items=rows if state=='READY' else [])
    fixture=dict(code=403 if state=='DENIED' else 200,body=json.dumps(data,ensure_ascii=False).encode(),started=threading.Event(),release=threading.Event())
    if not held:fixture['release'].set()
    LIST_REPLIES[kind].put_nowait(fixture);return fixture


def read_list_fixture(page,kind,state,*,held=False):
    require_operation_time(15)
    fixture=queue_list(kind,state,held)
    before=request_counts()
    visible_before=page.locator('#'+kind+'-items > button').count()
    pre_response=None
    try:
        page.locator('#'+kind+'-list').click(timeout=15000)
        if held:
            observed_by=time.monotonic()+2
            while not fixture['started'].is_set():
                remaining=observed_by-time.monotonic();assert remaining>0,'list fixture request not observed'
                page.wait_for_timeout(min(20,remaining*1000))
            assert page.locator('#'+kind+'-list').is_disabled()
            assert page.locator('#'+kind+'-list-status').get_attribute('data-state')=='LOADING'
            assert page.locator('#'+kind+'-items').get_attribute('aria-busy')=='true'
            pre_response=page.evaluate("()=>({dispatchCards:$('dispatch-items').children.length,receiptCards:$('receipt-items').children.length,viewsAlreadyEmpty:preparationView===null&&dispatchView===null&&receiptView===null})")
            fixture['release'].set()
        page.wait_for_function('x=>$(x.kind+"-list-status").dataset.state===x.state',arg=dict(kind=kind,state=state),timeout=15000)
        assert not page.locator('#'+kind+'-list').is_disabled()
        assert page.locator('#'+kind+'-items').get_attribute('aria-busy')=='false'
        after=request_counts();assert after[0]-before[0]==1 and after[1]-before[1]==1 and after[2]==before[2]
        assert REPORT['requests'][-1]['path']==LIST_PATHS[kind] and REPORT['requests'][-1]['status']==fixture['code']
        REPORT.setdefault('list_response_fixtures',[]).append(dict(kind=kind,state=state,status=fixture['code'],loading_observed=held,cards_before_click=visible_before,pre_response=pre_response,server_GET_delta=1,browser_GET_delta=1,POST_delta=0))
    finally:fixture['release'].set()


def collaboration_geometry(page,label):
    row=page.evaluate("""() => {const box=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}};
        const lanes=[...document.querySelectorAll('.collaboration-lane')];return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,
            header:box(document.querySelector('.collaboration-heading')),primary:box(document.querySelector('.collaboration-preparation')),
            grid:getComputedStyle(document.querySelector('.collaboration-lanes')).gridTemplateColumns,
            lanes:lanes.map(e=>({box:box(e),readButton:{id:e.querySelector('button').id,...box(e.querySelector('button'))},listDisplay:getComputedStyle(e.querySelector('.actions')).display,listColumns:getComputedStyle(e.querySelector('.actions')).gridTemplateColumns})),
            buttons:[...document.querySelectorAll('#collaboration button')].filter(e=>e.getClientRects().length).map(e=>({id:e.id,...box(e)}))};} """)
    row['label']=label;REPORT.setdefault('collaboration_geometry',[]).append(row)
    assert row['documentWidth']<=row['width'] and row['header']['bottom']<=row['primary']['top']<row['lanes'][0]['box']['top'],row
    a,b=[r['box'] for r in row['lanes']]
    if row['width']>=900:assert abs(a['top']-b['top'])<=1 and a['right']<b['left'],row
    else:assert a['bottom']<b['top'],row
    assert [r['readButton']['id'] for r in row['lanes']]==['dispatch-list','receipt-list'],row
    assert all(r['listDisplay']=='grid' and len(r['listColumns'].split())==1 for r in row['lanes']),row
    assert all(r['height']>=44 for r in row['buttons']),row
    if row['width']==390:
        for lane in row['lanes']:
            button=lane['readButton']
            assert button['id'] in ('dispatch-list','receipt-list') and button['width']>=lane['box']['width']-40,row
    return row


def collaboration_records(page,kind):
    cards=page.locator('#'+kind+'-items > button');assert cards.count()==2
    rows=[]
    for i in range(2):
        card=cards.nth(i);expected=('11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222')[i]
        assert card.get_attribute('data-list-record-id')==expected
        text=card.inner_text();assert FIXTURE_GOAL in text and expected in text
        other=('22222222-2222-4222-8222-222222222222','11111111-1111-4111-8111-111111111111')[i];assert other not in text
        assert '不确认当前责任或办理权限' in text and '只读打开' in text
        if kind=='receipt':assert ('Case已取消' in text and '新办理暂停' in text) if i==0 else '状态待核对' in text
        rows.append(dict(id=expected,text_sha256=hashlib.sha256(text.encode()).hexdigest()))
    REPORT.setdefault('collaboration_record_observations',[]).append(dict(width=page.viewport_size['width'],kind=kind,records=rows,same_named_distinct_keys=True))


def combined_breakpoints(page):
    require_operation_time(5);counts=request_counts();viewport=dict(page.viewport_size);scroll=page.evaluate('()=>({x:scrollX,y:scrollY})')
    try:
        for width in (899,900,1060):
            page.set_viewport_size(dict(width=width,height=1000));collaboration_geometry(page,'breakpoint-'+str(width))
        page.set_viewport_size(dict(width=1060,height=1000))
        row=page.evaluate("""()=>{const box=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}};
            const nav=document.querySelector('.workspace-nav');return {width:innerWidth,body:getComputedStyle(document.body).display,direction:getComputedStyle(nav).flexDirection,
            current:[...document.querySelectorAll('[data-tab][aria-current=page]')].map(e=>e.dataset.tab),documentWidth:document.documentElement.scrollWidth,
            nav:box(nav),session:box(document.querySelector('.session-panel')),buttons:[...nav.querySelectorAll('button')].map(e=>({tab:e.dataset.tab,...box(e)}))};} """)
        assert row['width']==1060 and row['body']=='block' and row['direction']=='row' and row['current']==['collaboration'] and row['documentWidth']==1060,row
        buttons=row['buttons'];assert [r['tab'] for r in buttons]==['service','collaboration','resource'],row
        assert max(r['top'] for r in buttons)-min(r['top'] for r in buttons)<=1,row
        assert all(a['right']<=b['left'] for a,b in zip(buttons,buttons[1:])),row
        assert row['nav']['left']<=buttons[0]['left'] and buttons[-1]['right']<=row['nav']['right'] and row['session']['top']>=row['nav']['bottom'],row
        REPORT['breakpoint_1060']=row
    finally:page.set_viewport_size(viewport);page.evaluate('p=>window.scrollTo(p.x,p.y)',scroll)
    assert counts==request_counts();REPORT['breakpoint_1060']['request_delta']=0


def collaboration_observation(page,width):
    require_operation_time(15)
    page.locator('[data-tab="collaboration"]').click(timeout=15000)
    assert page.locator('#collaboration').is_visible() and page.locator('#service').is_hidden()
    assert page.locator('[aria-current="page"][data-tab]').get_attribute('data-tab')=='collaboration'
    compose_fixture(page,'.collaboration-heading')
    if width==1200:
        read_list_fixture(page,'dispatch','EMPTY',held=True)
        assert '不代表没有其他事项' in page.locator('#dispatch-list-status').inner_text()
        compose_fixture(page,'.collaboration-heading');collaboration_geometry(page,'empty-1200')
        observe(page,'current-collaboration-empty-1200',True);capture(page,'05-collaboration-empty-1200.png')
        read_list_fixture(page,'dispatch','READY');collaboration_records(page,'dispatch')
        compose_fixture(page,'.collaboration-lane:first-child');visible_in_viewport(page,['dispatch-items']);collaboration_geometry(page,'records-1200')
        observe(page,'current-collaboration-records-1200',True);capture(page,'06-collaboration-records-1200.png')
        combined_breakpoints(page)
    else:
        read_list_fixture(page,'receipt','READY',held=True);collaboration_records(page,'receipt');collaboration_geometry(page,'records-390')
        compose_fixture(page,'.collaboration-lane:last-child')
        first=page.locator('#receipt-items > button').nth(0)
        first_rect=first.evaluate("e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height}}")
        assert 0<=first_rect['top']<first_rect['bottom']<=1000,first_rect
        observe(page,'current-collaboration-records-390',True);capture(page,'07-collaboration-records-390.png')
        second=page.locator('#receipt-items > button').nth(1)
        second.evaluate("e=>e.scrollIntoView({block:'start',behavior:'instant'})")
        second_rect=second.evaluate("e=>{const r=e.getBoundingClientRect();return {top:r.top,bottom:r.bottom,height:r.height}}")
        assert 0<=second_rect['top']<second_rect['bottom']<=1000,second_rect
        observe(page,'current-collaboration-second-record-390-no-PNG',True)
        REPORT['narrow_records_scope']=dict(first_card_in_PNG=first_rect,second_card_geometry_font_only=second_rect,
            screenshot='07 is a partial vertical viewport with original warning/first complete card; second record has geometry/font observations only, no second-record pixel claim')
        read_list_fixture(page,'receipt','DENIED',held=True)
        assert page.locator('#receipt-items').inner_text()=='' and page.locator('#dispatch-items').inner_text()==''
        assert page.evaluate('()=>preparationView===null&&dispatchView===null&&receiptView===null')
        assert '权限被拒绝' in page.locator('#receipt-list-status').inner_text()
        page.locator('#receipt-list').focus();page.keyboard.press('Shift+Tab');page.keyboard.press('Tab')
        assert page.locator('#receipt-list').evaluate("e=>document.activeElement===e&&e.matches(':focus-visible')")
        compose_fixture(page,'.collaboration-lane:last-child');visible_in_viewport(page,['receipt-list-status'])
        observe(page,'current-collaboration-denied-390',True);capture(page,'08-collaboration-denied-390.png')
        REPORT['denial_scope']='READY cards -> original refresh clears cards/views before response -> current403 DENIED remains empty. Not independent403-caused private-view clearing or real permission revocation acceptance.'


def run_flow(started):
    global OUT,PRIVATE,START
    os.umask(0o077);START=started;server=None;thread=None
    try:
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='38')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        pages,binding=source_contract();REPORT['source_binding']=binding
        (PRIVATE/'current.html').write_bytes(pages['web.html'])
        REPORT['fixture_scope']='Transparent read-only HTTP response and client UI-state fixtures; not live business or permission acceptance'
        env=dict(os.environ)
        for key,name in [('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')]:
            p=PRIVATE/name;p.mkdir(mode=0o700);env[key]=str(p)
        env=installed_font_environment(env,PRIVATE/'fontconfig',REPORT,extra_text=FIXTURE_SUMMARY+FIXTURE_LABEL+FIXTURE_GOAL)
        signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(90-(time.monotonic()-START))))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
        with owned_browser(env) as browser:
            base.resource.verify_sandbox(browser,REPORT);REPORT['browser_version']=browser.version
            for width in (1200,390):
                stage('CURRENT_ENTRY_'+str(width));context,page=open_page(browser,origin,'/current',width)
                try:
                    mark_fixture(page)
                    page.locator('#token').fill('SYNTHETIC_UI_STATE_FIXTURE')
                    page.keyboard.press('Tab') # Commit the original change handler before request-delta accounting.
                    page.wait_for_load_state('networkidle',timeout=15000)
                    page.evaluate('()=>window.scrollTo(0,0)')
                    entry_observation(page,width)
                    stage('NATIVE_RETURN_'+str(width))
                    for link,target,first in RETURN_LINKS:
                        for method in ('mouse','Enter'):
                            shot=('03-native-existing-390.png' if target=='existing-preparation-entry' else '04-native-formal-390.png') if width==390 and method=='mouse' else None
                            native_return(page,link,target,first,method,shot=shot)
                    if width==390:
                        stage('RETURN_UNKNOWN_AND_INFLIGHT');return_guard_observation(page)
                    stage('COLLABORATION_'+str(width));collaboration_observation(page,width)
                finally:context.close()
            assert all(q.empty() for q in LIST_REPLIES.values())
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
        source=base.require_hosted(os.environ,run_number='38')
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
