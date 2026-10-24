"""Run43/attempt1: original template revision UI; static GET fixtures, no backend."""
import hashlib,json,os,signal,socket,subprocess,sys,tempfile,threading,time,traceback
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit,urlencode
from playwright.sync_api import sync_playwright
from scripts import fictional_park_browser_once as base
from scripts.fictional_park_restart_browser_once import installed_font_environment,verify_rendered_font
from scripts.visual_owned_launch import atomic_report,supervise

ROOT=Path(__file__).resolve().parents[1]
REPORT=dict(scope='REAL_CHROME_TEMPLATE_UPGRADE_PRESENTATION_NO_BACKEND',status='RUNNING',stage='START',
    product_API=False,database=False,real_model_calls=0,business_POSTs=0,requests=[],browser_requests=[],
    checks=[],font_observations=[],page_errors=[],violations=[],unexpected_GET=[],cleanup_errors=[])
OUT=None;PRIVATE=None;PAGE=None;START=0;CHECKPOINT=None
BASELINE_SHA='89cc51e2f161de87e4c5fe7bb44e893181853f96'
PAGE_NAME='template_upgrade_web.html'
PAGE_SHA256='410ab1080d3c714e98d550deb158697999ed3f7b557fb20666630b00d4b18c60'
ISOLATED_ENTRY_SOURCES={'src/parkweave/template_isolated_app.py':'22eaee2712d5a5e83d7c9dbd397272d8d7dfdfe45b84438d2c31b06448bde27a',
    'src/parkweave/template_upgrade.py':'901054f04b370eac2238e0c9e19b6512b7c7bded3de682405c2397a7137e8db9'}
PNG_FILES=('01-upgrade-ready-1200.png','02-upgrade-ready-390.png','03-upgrade-unknown-1200.png','04-upgrade-unknown-390.png')
PUBLIC_FILES=frozenset(PNG_FILES+('failure-visual.png','result.json'))
EXPECTED_CHANGED_PATHS=frozenset(('.github/workflows/fictional-park-browser-once.yml',
    'scripts/workspace_visual_browser_once.py','scripts/fictional_park_font_once.py'))
FIXTURE_SUMMARY='合成界面回放 · 无真实事项、身份或授权'
FIXTURE_LABEL='SYNTHETIC UI_STATE_FIXTURE / READ_ONLY_RESPONSE_FIXTURE；仅静态原页面与合成GET响应，不是工厂、业务服务或权限验收。'

def presentation_contract(reviewed,current,page=PAGE_NAME):
    assert page==PAGE_NAME and hashlib.sha256(reviewed).hexdigest()==PAGE_SHA256,'exact reviewed template upgrade page required'
    assert current==reviewed,'product page must equal the reviewed parent bytes'

def validate_source_listing(parent,changed,dirty):
    assert parent==BASELINE_SHA,'exact reviewed direct parent required'
    assert len(changed)==len(set(changed)) and set(changed)==EXPECTED_CHANGED_PATHS,'unreviewed commit paths'
    assert not dirty,'tracked or untracked workspace changes refused'

def source_contract():
    parent=subprocess.check_output(['git','rev-parse','HEAD^'],cwd=ROOT,text=True).strip()
    changed=subprocess.check_output(['git','diff','--name-only',BASELINE_SHA,'HEAD'],cwd=ROOT,text=True).splitlines()
    validate_source_listing(parent,changed,subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True))
    path='src/parkweave/'+PAGE_NAME;current=(ROOT/path).read_bytes()
    presentation_contract(subprocess.check_output(['git','show',BASELINE_SHA+':'+path],cwd=ROOT),current)
    for path,digest in ISOLATED_ENTRY_SOURCES.items():
        reviewed=subprocess.check_output(['git','show',BASELINE_SHA+':'+path],cwd=ROOT)
        assert (ROOT/path).read_bytes()==reviewed and hashlib.sha256(reviewed).hexdigest()==digest,'isolated entry source changed'
    return {PAGE_NAME:current},dict(reviewed_product_sha=BASELINE_SHA,page=PAGE_NAME,page_sha256=PAGE_SHA256,
        isolated_entry_sources=ISOLATED_ENTRY_SOURCES,exact_changed_paths=sorted(changed),
        isolated_entry_scope='Original /template-upgrade bytes only; factory/checker/engine/API/PG never started',
        product_page_identical_to_reviewed_baseline=True)


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



# These constants are visibly synthetic UI fixtures, not issued business proofs.
INSTANCE='11111111-1111-4111-8111-111111111111'
TARGET='22222222-2222-4222-8222-222222222222'
DIGEST='a'*64
CHOICE_KEY='SYNTHETIC_VISUAL_CHOICE_KEY'
APPLY_KEY='SYNTHETIC_VISUAL_APPLY_KEY'
UPGRADE_PATH='/template-upgrade'
CATALOG_URI='/api/template-consumer/catalog'
CHECK_URI='/api/template-upgrade/'+INSTANCE+'/check?'+urlencode({'target_release_id':TARGET,'target_sha256':DIGEST})
CHOICE_URI='/api/template-upgrade/'+INSTANCE+'/requests/'+CHOICE_KEY
APPLY_URI='/api/template-upgrade/'+INSTANCE+'/apply-requests/'+APPLY_KEY
FIXTURE_LIMITS={UPGRADE_PATH:2,CATALOG_URI:2,CHECK_URI:2,CHOICE_URI:2,APPLY_URI:4}
FIXTURE_READS={}
CHECK_REPLY=dict(revision=1,check_sha256=DIGEST,check=dict(classification='NEEDS_RECHECK',
    allowed_choices=['KEEP_CURRENT','REQUEST_RECHECK','ACK_COMPATIBLE'],original_content_version=1,target_content_version=2,
    original_source_revision='SYNTHETIC_OLD',target_source_revision='SYNTHETIC_NEW',changes=['SYNTHETIC_UI_RECHECK_ONLY'],
    original_release_id='SYNTHETIC_OLD_RELEASE',target_release_id=TARGET,target_release_sha256=DIGEST),
    application=dict(eligible=True,choice_revision=1,choice_event_sha256=DIGEST,plan_id='SYNTHETIC_PLAN',plan_revision=3,
        preparation_revision=4,source_sha256=DIGEST,effective_release_id='SYNTHETIC_OLD_RELEASE',blockers=[],
        affected=['P1','P2','P3','P4','P5'],preserved=[],requires_structure_confirmation=True,structure_sha256=DIGEST,
        structure_change=dict(added_goals=['SYNTHETIC_UI_ONLY_新增模板必需目标待本人逐项重核'],added_template_steps=['P5'])))

def fixture_response(uri):
    # Exact URL+query, finite totals, and two precise recovery replies per width.
    if uri=='/favicon.ico':
        count=FIXTURE_READS.get(uri,0)+1;FIXTURE_READS[uri]=count
        if count<=2:return 204,'image/x-icon',b''
    elif uri in FIXTURE_LIMITS:
        count=FIXTURE_READS.get(uri,0)+1;FIXTURE_READS[uri]=count
        if count<=FIXTURE_LIMITS[uri]:
            if uri==UPGRADE_PATH:return 200,'text/html; charset=utf-8',(PRIVATE/'upgrade.html').read_bytes()
            if uri==CATALOG_URI:
                body=dict(templates=[dict(name='SYNTHETIC 长中文模板名称：联合培训资料版本核对与历史保全，不代表真实资格或履约',release_id=TARGET,release_sha256=DIGEST)])
            elif uri==CHECK_URI:body=CHECK_REPLY
            elif uri==APPLY_URI and count%2==0:return 403,'application/json',b'{}'
            else:body=dict(status='NOT_OBSERVED',event=None)
            return 200,'application/json',json.dumps(body,ensure_ascii=False).encode()
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

def open_page(browser,origin,width):
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
    response=page.goto(origin+UPGRADE_PATH,wait_until='load',timeout=15000)
    assert response.status==200 and response.body()==(PRIVATE/'upgrade.html').read_bytes()
    page.wait_for_load_state('networkidle',timeout=15000)  # Settle optional favicon before exact request deltas.
    return context,page

def request_counts():return (len(REPORT['requests']),len(REPORT['browser_requests']),REPORT['business_POSTs'])

def mark_fixture(page):
    page.evaluate("""([summary,text])=>{const n=document.createElement('details');n.dataset.visualFixture='true';
        n.style.cssText='margin:12px 0;padding:8px 10px;border:1px dashed #b2a16e;border-radius:8px;background:#fff6dc;color:#614b19;font-size:12px;line-height:1.5';
        const s=document.createElement('summary');s.textContent=summary;const p=document.createElement('p');p.textContent=text;n.append(s,p);document.querySelector('main').before(n)}""",[FIXTURE_SUMMARY,FIXTURE_LABEL])
    assert page.locator('[data-visual-fixture]>summary').inner_text()==FIXTURE_SUMMARY

def capture(page,name):
    require_operation_time(15)
    assert name in PNG_FILES and page.locator('[data-visual-fixture]>summary').is_visible()
    # Full-page captures retain all four original regions/warnings; viewport
    # remains unchanged. Actual CDP font observations are viewport-scoped only.
    page.screenshot(path=str(OUT/name),timeout=15000,full_page=True,mask=[page.locator('#token')])

UNKNOWN_FIXTURE=r"""([kind,key])=>{
 const original={kind,url:'/api/template-upgrade/'+$('instance').value+(kind==='choice'?'/choices':'/apply'),key,
   body:{scope:'SYNTHETIC_UI_STATE_ONLY',target_release_id:$('target').value,reason:'合成未知结果界面复放，不是已发生的提交'}};
 pending=original;window.__upgradeVisualPending={original,body:original.body,before:JSON.stringify(original)};
 $(kind==='choice'?'key':'apply-key').value=key;fail(context(),{unknown:true});buttons();
}"""

def pending_state(page):
    return page.evaluate("""()=>({same:pending===window.__upgradeVisualPending.original,
        bodySame:pending?.body===window.__upgradeVisualPending.body,bodyUnchanged:JSON.stringify(pending)===window.__upgradeVisualPending.before,
        busy,choice:pending?.kind,applyDisabled:$('apply').disabled,checkDisabled:$('check').disabled,
        choicesDisabled:[...document.querySelectorAll('[data-choice]')].every(e=>e.disabled)})""")

def upgrade_observation(page,width):
    mark_fixture(page)
    assert page.locator('.upgrade-panel').count()==4
    assert page.locator('#check').is_disabled() and page.locator('#apply').is_disabled()
    assert page.locator('[data-choice]:not(:disabled)').count()==0
    assert page.locator('#original-case').is_hidden()
    page.locator('#token').fill('SYNTHETIC_UI_NOT_A_REAL_SESSION')
    page.locator('#instance').fill(INSTANCE)
    page.locator('#catalog').click()
    page.wait_for_function('()=>!busy&&$("target").options.length===1',timeout=15000)
    page.locator('#check').click()
    page.wait_for_function('()=>!busy&&inspection!==null&&$("result").textContent.includes("需人工重验")',timeout=15000)
    assert page.locator('#structure-confirm-label').is_visible() and page.locator('#note-carry-confirm-label').is_hidden()
    before=request_counts();page.locator('#reason').fill('SYNTHETIC：长中文选择说明，仅核对当前事项版本、原目标和历史，不代表正式批准或履约。')
    page.locator('#reason').focus();page.keyboard.press('Tab')
    focus=page.evaluate("""()=>({choice:document.activeElement.dataset.choice,visible:document.activeElement.matches(':focus-visible'),
        outline:getComputedStyle(document.activeElement).outlineStyle,width:getComputedStyle(document.activeElement).outlineWidth})""")
    assert focus['choice']=='KEEP_CURRENT' and focus['visible'] and focus['outline']=='solid' and focus['width']=='3px',focus
    page.locator('#apply-reason').fill('SYNTHETIC：当前版本需要本人再次核对；保持原事项、步骤编号和历史，仍须逐项重核。')
    page.locator('#apply-confirm').check();assert page.locator('#apply').is_disabled()
    page.locator('#structure-confirm').check();assert page.locator('#apply').is_enabled()
    page.locator('#structure-confirm').uncheck();page.locator('#apply-confirm').uncheck()
    assert page.locator('#apply').is_disabled() and request_counts()==before
    REPORT.setdefault('keyboard_and_confirmation',[]).append(dict(width=width,focus=focus,request_delta=0,submit_clicked=False))
    page.evaluate('window.scrollTo(0,0)');observe(page,'upgrade-ready-'+str(width),True)
    capture(page,'01-upgrade-ready-1200.png' if width==1200 else '02-upgrade-ready-390.png')
    for kind,key,control,result_id in [('choice',CHOICE_KEY,'recover','receipt'),('apply',APPLY_KEY,'apply-recover','apply-receipt')]:
        before=request_counts();page.evaluate(UNKNOWN_FIXTURE,[kind,key]);assert request_counts()==before
        page.locator('#'+control).click()
        page.wait_for_function('id=>!busy&&$(id).textContent.includes("NOT_OBSERVED")',arg=result_id,timeout=15000)
        row=pending_state(page)
        assert all(row[k] for k in ('same','bodySame','bodyUnchanged','applyDisabled','checkDisabled','choicesDisabled')) and not row['busy'] and row['choice']==kind,row
        assert request_counts()==(before[0]+1,before[1]+1,0)
        REPORT.setdefault('unknown_readonly_recovery',[]).append(dict(width=width,kind=kind,state=row,GETs=1,POSTs=0,
            scope='Explicit unsubmitted UI pending fixture; not a real lost business response'))
    page.locator('.recovery-panel').scroll_into_view_if_needed(timeout=15000)
    observe(page,'upgrade-unknown-'+str(width),True)
    capture(page,'03-upgrade-unknown-1200.png' if width==1200 else '04-upgrade-unknown-390.png')
    before=request_counts();page.locator('#apply-recover').click()
    page.wait_for_function('()=>!busy&&$("error").textContent==="当前身份或范围无权访问"',timeout=15000)
    cleared=page.evaluate("""()=>({pending:pending===null,inspection:inspection===null,target:$('target').options.length,
        fields:['key','reason','apply-key','apply-reason'].every(id=>$(id).value===''),
        views:['result','receipt','application','apply-receipt'].every(id=>$(id).textContent===''),
        confirmations:['apply-confirm','structure-confirm','note-carry-confirm'].every(id=>!$(id).checked),
        applyDisabled:$('apply').disabled,originalHidden:$('original-case').hidden,originalHref:$('original-case').getAttribute('href')})""")
    assert cleared==dict(pending=True,inspection=True,target=0,fields=True,views=True,confirmations=True,applyDisabled=True,originalHidden=True,originalHref=''),cleared
    assert request_counts()==(before[0]+1,before[1]+1,0)
    REPORT.setdefault('denied_clearing',[]).append(dict(width=width,cleared=cleared,GETs=1,status=403,POSTs=0,
        scope='Static denial response through original renderer; not actual business authorization'))


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
        REPORT['source_sha']=base.require_hosted(os.environ,run_number='43')
        checkpoint()
        PRIVATE=Path(tempfile.mkdtemp(prefix='parkweave-visual-'));OUT=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';OUT.mkdir(mode=0o700,exist_ok=False)
        pages,binding=source_contract();REPORT['source_binding']=binding
        (PRIVATE/'upgrade.html').write_bytes(pages[PAGE_NAME])
        REPORT['fixture_scope']='Transparent original template-upgrade GET projections and explicitly unsubmitted pending UI state; not factory/API/PG, real authority or committed business recovery'
        env=dict(os.environ)
        for key,name in [('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')]:
            p=PRIVATE/name;p.mkdir(mode=0o700);env[key]=str(p)
        env=installed_font_environment(env,PRIVATE/'fontconfig',REPORT,extra_text=FIXTURE_SUMMARY+FIXTURE_LABEL+pages[PAGE_NAME].decode('utf-8')+json.dumps(CHECK_REPLY,ensure_ascii=False))
        signal.signal(signal.SIGALRM,timeout);signal.alarm(max(1,int(90-(time.monotonic()-START))))
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();origin='http://127.0.0.1:'+str(server.server_port)
        with owned_browser(env) as browser:
            base.resource.verify_sandbox(browser,REPORT);REPORT['browser_version']=browser.version
            for width in (1200,390):
                stage('UPGRADE_'+str(width));context,page=open_page(browser,origin,width)
                try:upgrade_observation(page,width)
                finally:context.close()
            assert {uri:FIXTURE_READS.get(uri,0) for uri in FIXTURE_LIMITS}==FIXTURE_LIMITS,'each exact GET fixture quota must be consumed'
            assert FIXTURE_READS.get('/favicon.ico',0)<=2
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
        source=base.require_hosted(os.environ,run_number='43')
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
