"""One bounded installed guide intake, truthful unfinished TXT and fresh reopening.

Nine original DOM POSTs; no API preparation writes, VERIFY, service restart or
second setup. The existing90s dedicated browser supervisor remains unchanged.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json, os, re, signal, subprocess, sys, tempfile, time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

from scripts import local_approval_installed_browser_once as installed
from scripts import local_source_restart_installed_browser_once as source
from scripts import local_tail_installed_browser_once as tail
from scripts.local_goal_txt_installed_browser_once import unpack
from scripts.fictional_park_restart_browser_once import installed_font_environment, verify_rendered_font
from scripts.visual_owned_launch import atomic_report, supervise

base = installed.base
ROOT = base.ROOT
RUN = '31'
SHOTS = {'01-guide-ready.png','02-reviewed-new-input.png','03-current-unfinished-txt.png','04-reopened-unfinished-txt.png'}
TEXTS = {'current-unfinished-case.txt','reopened-unfinished-case.txt'}
PUBLIC = SHOTS | TEXTS | {'failure-guide.png','result.json','installation-redacted.log',installed.WHEEL_NAME}


def failed(report, error):
    detail=dict(error_type=type(error).__name__,error=str(error),stage=report.get('stage'))
    if 'error_type' in report:report.setdefault('later_errors',[]).append(detail)
    else:report.update(detail)
    report['status']='FAIL'


class Budget:
    """Exact new window; old8-DOM drivers and their contracts are untouched."""
    def __init__(self, run):
        self.run = run; self.reads = 0; self.posts = 0; self.queue = []; self.keys = set(); self.readonly = False
    def authorize(self, *commands):
        assert not self.readonly and not self.queue
        self.queue = list(commands)  # (path, action, actor)
    def route(self, route):
        req = route.request; url = urlsplit(req.url); origin = urlsplit(self.run.report['origin'])
        try:
            assert (url.scheme,url.netloc) == (origin.scheme,origin.netloc) and not url.username and not url.password
            assert url.path in ('/','/demo','/favicon.ico') or url.path.startswith('/api/')
            if req.method == 'GET':
                assert self.reads < 360; self.reads += 1
            else:
                assert req.method == 'POST' and not url.query and not self.readonly and self.posts < 9 and self.queue
                path, action, actor = self.queue[0]
                assert url.path == path and req.headers.get('authorization') == 'Bearer '+self.run.tokens[actor]
                body = req.post_data_json
                assert action is None or body.get('action') == action
                assert body.get('action') != 'VERIFY'
                key = req.headers.get('idempotency-key')
                assert key and re.fullmatch('[0-9a-f-]{36}',key) and key not in self.keys
                self.keys.add(key); self.queue.pop(0); self.posts += 1
                self.run.report.setdefault('DOM_write_requests',[]).append(dict(path=path,action=action,actor=actor,key=key,body=body))
            route.continue_()
        except BaseException as error:
            self.run.report['violations'].append(dict(method=req.method,path=url.path,error_type=type(error).__name__))
            route.abort(); raise
        finally:
            self.run.report['request_budget'] = dict(POST=self.posts,DOM_POST=self.posts,API_PREPARATION_POST=0,
                main_GET=self.reads,readiness_attempts=self.run.ready,GET=self.reads+self.run.ready,
                ceilings=dict(POST=40,DOM_POST=9,API_PREPARATION_POST=0,main_GET=360,readiness=40,GET=400,worker_once=2))


class Walk:
    def __init__(self, run, browser, width):
        from playwright.sync_api import expect
        self.run=run; self.expect=expect; self.w=None; self.actor=None
        self.context=browser.new_context(viewport=dict(width=width,height=1000),locale='zh-CN',service_workers='block',accept_downloads=True)
        self.context.route('**/*',run.budget.route)
        self.context.on('response',self.observed)
        self.context.on('page',lambda p:p.on('pageerror',lambda e:run.report['page_errors'].append(str(e))))
        self.guide=self.context.new_page(); self.guide.set_default_timeout(15000)
    def observed(self, response):
        req=response.request; path=urlsplit(response.url).path
        row=dict(stage=self.run.report['stage'],method=req.method,path=path,status=response.status)
        if req.method=='GET' and path in ('/','/demo'):
            name='park_demo_web.html' if path=='/demo' else 'web.html'
            assert response.status==200 and sha256(response.body()).hexdigest()==self.run.report['installation']['package_files']['parkweave/'+name]
            assert "frame-ancestors 'none'" in response.headers['content-security-policy']
            row['installed_body_sha256']=sha256(response.body()).hexdigest()
        if req.method=='POST':
            row.update(key=req.headers.get('idempotency-key'),body_sha256=sha256((req.post_data or '').encode()).hexdigest())
            if response.ok:
                row['response']=response.json()
        self.run.report['responses'].append(row)
    def click(self, page, selector):
        installed.require_work(self.run,30)
        control=page.locator(selector); control.scroll_into_view_if_needed(timeout=15000)
        self.expect(control).to_be_visible(); self.expect(control).to_be_enabled(); control.click()
    def ready(self):
        self.w.wait_for_function('()=>preparationReadReady()&&!prepCommandPending',timeout=30000)
    def idle(self):
        self.w.wait_for_function('()=>!servicePlanPending&&!activeEntryWriteFlow&&entryWriteRequests.size===0',timeout=30000)
    def open(self):
        r=self.guide.goto(self.run.report['origin']+'/demo',wait_until='load',timeout=15000)
        assert r.status==200 and sha256(r.body()).hexdigest()==self.run.report['installation']['package_files']['parkweave/park_demo_web.html']
        assert "frame-ancestors 'none'" in r.headers['content-security-policy'] and self.guide.locator('iframe').count()==0
        assert self.guide.evaluate('localStorage.length')==0
        self.guide.locator('#sessions').set_input_files(self.run.state/'sessions.json')
        self.expect(self.guide.locator('#workspace-open')).to_be_enabled()
        with self.guide.expect_popup(timeout=15000) as opened:self.click(self.guide,'#workspace-open')
        self.w=opened.value; self.w.set_default_timeout(15000); self.w.wait_for_load_state('load',timeout=15000)
        assert self.w.url==self.run.report['origin']+'/'
        # Fetching actual DOM source via the response event also proves it came
        # from the installed API; the complete package attestation is separate.
        assert self.w.evaluate('localStorage.length')==0 and self.w.locator('#token').input_value()==''
        self.role('enterprise')
    def role(self, actor):
        self.click(self.guide,'[data-role="'+actor+'"]'); self.actor=actor
        assert self.w.locator('#token').input_value()==self.run.tokens[actor]
        self.expect(self.guide.locator('#status')).to_contain_text('已切换')
    def existing(self):
        self.click(self.w,'[data-tab="collaboration"]'); self.click(self.w,'#prep-list')
        button=self.w.locator('#prep-items>button'); self.expect(button).to_have_count(1)
        self.expect(button).to_contain_text(self.run.record['goal']); self.click(self.w,'#prep-items>button'); self.ready()
        p=self.w.evaluate('preparationView.preparation')
        assert all(p[key]==self.run.record[target] for key,target in (('id','preparation_id'),('case_id','case_id'),('run_id','run_id')))
    def post(self, selector, path, *, action=None, status=200):
        self.run.budget.authorize((path,action,self.actor))
        with self.w.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path==path,timeout=30000) as seen:
            self.click(self.w,selector)
        r=seen.value; assert r.status==status and not self.run.budget.queue
        self.idle(); return r.json()
    def shot(self, name, selector, page=None):
        assert name in SHOTS; page=page or self.w
        page.locator(selector).scroll_into_view_if_needed(timeout=15000)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        path=self.run.public/name
        page.screenshot(path=str(path),mask=[page.locator('#token')] if page is self.w else [page.locator('#sessions')],timeout=10000)
        self.run.report['screenshots'].append(dict(file=name,sha256=sha256(path.read_bytes()).hexdigest(),viewport=page.viewport_size))
    def font(self, stage):
        selected=self.run.report['installed_CJK_font']; selected['visible_node_font_usage']=[]; selected['rendering_observed']=False
        verify_rendered_font(self.w,self.run.report)
        self.run.report.setdefault('font_observations',[]).append(dict(stage=stage,complete=selected['rendering_observed'],nodes=deepcopy(selected['visible_node_font_usage'])))
    def export(self, filename):
        posts=self.run.budget.posts; self.click(self.w,'#service-plan-prepare')
        self.w.wait_for_function('()=>servicePlanView?.plan_id&&!servicePlanPending',timeout=30000)
        plan=self.w.evaluate('(fields)=>Object.fromEntries(fields.map(k=>[k,servicePlanView[k]]))',list(source.PLAN_FIELDS))
        assert plan['plan_id']==self.run.record['plan_id']
        assert [s['state'] for s in plan['steps']]==['PENDING','BLOCKED','BLOCKED','BLOCKED','BLOCKED']
        assert not any(e['action']=='VERIFY' for e in plan['events'])
        self.click(self.w,'#goal-results-read'); self.w.wait_for_function('()=>goalResultView!==null',timeout=30000)
        value=self.w.evaluate('goalResultView')
        tail.truth(value,self.run.record,['AWAITING_OWNER_VERIFICATION']+['WAITING_DEPENDENCY']*4)
        self.click(self.w,'#case-record-pack-generate'); self.w.wait_for_function('()=>caseRecordPackView!==null&&!caseRecordPackBusy',timeout=30000)
        text=self.w.locator('#case-record-pack-text').input_value(); pack=unpack(text,value)
        with self.w.expect_download(timeout=30000) as download:self.click(self.w,'#case-record-pack-download')
        assert download.value.failure() is None; download.value.save_as(self.run.public/filename)
        assert (self.run.public/filename).read_bytes()==text.encode() and len(text.encode())<=128*1024 and self.run.budget.posts==posts
        for secret in self.run.tokens.values():assert secret not in text and secret[:12] not in text
        self.run.report.setdefault('exports',[]).append(dict(file=filename,goal_results=value,plan=plan,pack=pack,sha256=sha256(text.encode()).hexdigest(),bytes=len(text.encode()),business_POSTs=0))
        return text, value, plan
    def close(self, primary=None):
        errors=[]
        closed=dict(stage=self.run.report['stage'],guide=False,popup=False,context=False)
        if primary is not None:
            try:
                page=self.w if self.w is not None and not self.w.is_closed() else self.guide
                page.screenshot(path=str(self.run.public/'failure-guide.png'),mask=[page.locator('#token')] if page is self.w else [page.locator('#sessions')],timeout=5000)
            except BaseException as error:self.run.report['failure_screenshot_error']=type(error).__name__
        try:
            if not self.guide.is_closed():self.guide.close()
            closed['guide']=self.guide.is_closed()
        except BaseException as error:errors.append(error)
        try:
            if self.w is not None and not self.w.is_closed():
                assert self.w.locator('#token').input_value()=='','guide pagehide must clear its associated identity'
        except BaseException as error:errors.append(error)
        try:
            if self.w is not None and not self.w.is_closed():self.w.close()
            closed['popup']=self.w is None or self.w.is_closed()
        except BaseException as error:errors.append(error)
        try:self.context.close();closed['context']=True
        except BaseException as error:errors.append(error)
        self.run.report.setdefault('context_closes',[]).append(closed)
        if not all(closed[k] for k in ('guide','popup','context')) and not errors:errors.append(RuntimeError('Client context close unconfirmed'))
        if errors:
            self.run.report.setdefault('context_cleanup_errors',[]).extend(type(e).__name__ for e in errors)
            raise BaseExceptionGroup('Guide body and context cleanup failures',([primary] if primary else [])+errors) from None


def intake(run, browser):
    walk=Walk(run,browser,1200); primary=None
    try:
        run.report['stage']='INSTALLED_GUIDE_NEW_INPUT'; walk.open(); walk.shot('01-guide-ready.png','#workspace-panel',walk.guide)
        w=walk.w; walk.click(w,'[data-tab="service"]'); walk.click(w,'#prep-catalog')
        w.locator('#prep-reviewer').select_option('ordinary-demo-specialist'); walk.click(walk.guide,'#fill-goal')
        goal=w.locator('#prep-goal').input_value(); assert 'SYNTHETIC' in goal
        run.budget.authorize(('/api/runs',None,'enterprise'),('/api/preparations',None,'enterprise'))
        with w.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path=='/api/runs',timeout=30000) as created:
            walk.click(w,'#prep-create button')
        assert created.value.status==202
        installed.worker_once(run,0)  # Before waiting for the original intake/polling handler.
        walk.ready(); assert not run.budget.queue
        p=w.evaluate('preparationView.preparation'); run.record=dict(preparation_id=p['id'],case_id=p['case_id'],run_id=p['run_id'],goal=goal)
        path='/api/preparations/'+p['id']; walk.click(w,'#plan-prepare'); walk.click(walk.guide,'#fill-request')
        walk.post('#request-save',path+'/request-intent'); walk.click(w,'#plan-materials'); walk.ready()
        for control in ('#fill-need','#fill-outline'):
            walk.click(walk.guide,control); walk.post('#prep-evidence button',path+'/commands',action='ADD_EVIDENCE'); walk.ready()
        walk.role('specialist'); walk.existing(); w.locator('#prep-reason').fill('SYNTHETIC 周禾在原页面明确核对本次新资料')
        walk.post('#prep-review',path+'/commands',action='REVIEW'); walk.ready(); walk.shot('02-reviewed-new-input.png','#prep-materials')
        walk.role('enterprise'); walk.existing(); w.locator('#prep-reason').fill('SYNTHETIC 林岚在原页面明确确认本次新资料')
        walk.post('#prep-confirm',path+'/commands',action='CONFIRM'); walk.ready()
        walk.click(w,'#service-plan-prepare'); w.wait_for_function('()=>servicePlanView!==null',timeout=30000)
        walk.click(w,'#service-selection-read'); w.wait_for_function('()=>serviceSelectionCatalog!==null&&!serviceSelectionBusy',timeout=30000)
        selected=walk.post('#service-selection-generate',path+'/service-selections',status=201)
        assert selected['producer']['mode']=='NO_MODEL' and selected['producer']['real_model_calls']==0
        w.locator('#service-selection-confirm').check(); w.locator('#service-plan-reason').fill('SYNTHETIC 林岚明确采纳本次原NO_MODEL候选，不核验未办步骤')
        plan=walk.post('#service-plan-adopt',path+'/service-case-plan',status=201); run.record['plan_id']=plan['plan_id']
        assert plan['candidate_consumption']['candidate_id']==selected['candidate_id']
        run.report.update(record=run.record,candidate=selected,initial_plan=plan)
        original=walk.export('current-unfinished-case.txt'); walk.shot('03-current-unfinished-txt.png','#goal-results-status'); walk.font('CURRENT_UNFINISHED')
        assert run.budget.posts==9 and len(run.report['installed_worker_exits'])==1
        return original
    except BaseException as error:primary=error; failed(run.report,error); raise
    finally:walk.close(primary)


def browser_worker(config, started):
    run=SimpleNamespace(**config); run.started=config['started']
    for key in ('private','public','harness','state','python'):setattr(run,key,Path(getattr(run,key)))
    run.tokens={k:v for k,v in json.loads((run.state/'sessions.json').read_text()).items() if k in ('enterprise','specialist','executor')}
    run.budget=Budget(run); report=run.report; primary=None
    def alarm(*_):raise TimeoutError('85s browser operation clock reached cleanup reserve')
    signal.signal(signal.SIGALRM,alarm); signal.alarm(max(1,int(85-(time.monotonic()-started))))
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            report['stage']='CHROME_LAUNCH'
            try:browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=config['chrome_env'],timeout=15000)
            except BaseException as error:
                failed(report,error);atomic_report(Path(config['browser_result']),report);raise
            try:
                report['chrome_version']=browser.version; base.resource.verify_sandbox(browser,report)
                original=intake(run,browser)
                before=tail.snapshot(run); posts=run.budget.posts; run.budget.readonly=True
                report['stage']='FRESH_CONTEXT_ORIGINAL_IDENTITY_READS'; walk=Walk(run,browser,390); error=None
                try:
                    walk.open(); walk.existing(); current=walk.export('reopened-unfinished-case.txt')
                    assert current==original and run.budget.posts==posts and tail.snapshot(run)==before
                    walk.shot('04-reopened-unfinished-txt.png','#goal-results-status'); walk.font('REOPENED_UNFINISHED')
                    report['reopening']=dict(new_context=True,empty_initial_storage=True,read_only=True,business_POSTs=0,
                        exact_goal_results_and_plan_and_TXT=True,named_projection_before=before,named_projection_after=tail.snapshot(run),PG_restart=False,setup_repeated=False)
                except BaseException as e:error=e;failed(report,e);raise
                finally:walk.close(error)
            except BaseException as error:failed(report,error); raise
            finally:
                try:browser.close(); report['browser_close']='CLOSED'
                except BaseException as error:
                    report['browser_cleanup_error']=type(error).__name__;failed(report,error);raise
        assert not report['violations'] and not report['page_errors'] and run.budget.posts==9
        report.update(status='PASS',stage='COMPLETE')
    except BaseException as error:
        primary=error; failed(report,error); raise
    finally:
        signal.alarm(0); report['browser_operation_seconds']=time.monotonic()-started
        report['browser_worker_final']=True; atomic_report(Path(config['browser_result']),report)


def supervise_browser(config_path):
    config=json.loads(Path(config_path).read_text()); directory=Path(config['private'])/'browser-supervision'; directory.mkdir(mode=0o700)
    started=time.monotonic()
    result=supervise([sys.executable,'-B','-m','scripts.guide_installed_browser_once','--browser-worker',str(config_path)],
        env=dict(os.environ),cwd=ROOT,directory=directory,started=started)
    atomic_report(directory/'owned.json',result)
    return 0 if result['status']=='CLEANUP_CONFIRMED' and result['operation_status']=='PASS' else 1


def main():
    os.umask(0o077); started=time.monotonic()
    report=dict(scope='INSTALLED_GUIDE_NEW_DOM_INPUT_UNFINISHED_TXT_FRESH_REOPEN',status='NOT_RUN',stage='HOST_GATE',
        responses=[],screenshots=[],violations=[],page_errors=[],real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False,PG_restart=False)
    run=SimpleNamespace(started=started,report=report,secrets=[],public=None)
    try:
        report['source_sha']=base.require_hosted(os.environ,run_number=RUN)
        run.private=Path(tempfile.mkdtemp(prefix='parkweave-installed-guide-'))
        run.public=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';run.public.mkdir(mode=0o700)
        installed.installation(run,installed.current_wheel(run))
        env=dict(os.environ)
        for key,name in (('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')):
            directory=run.private/name; directory.mkdir(mode=0o700);env[key]=str(directory)
        env=installed_font_environment(env,run.private/'fontconfig',report)
        # The service is owned by this process. A separate dedicated supervisor
        # has no preexisting children and owns only its90s browser/worker tree.
        run.budget=SimpleNamespace(internal_reads=0)
        with installed.server(run):
            with source.owner(run) as c:
                c.execute('SET TRANSACTION READ ONLY')
                report['empty_business_tables']={t:c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('runs','cases','preparations','service_dispatches','service_receipt_steps','run_assignments')}
                assert not any(report['empty_business_tables'].values())
            installed.require_work(run,120)
            cfg=dict(started=started,report=report,ready=run.budget.internal_reads,chrome_env=env,
                browser_result=str(run.private/'browser-result.json'),**{k:str(getattr(run,k)) for k in ('private','public','harness','state','python')})
            path=run.private/'browser-config.json';path.write_text(json.dumps(cfg))
            with (run.private/'browser-supervisor.log').open('w') as log:
                child=subprocess.run([sys.executable,'-B','-m','scripts.guide_installed_browser_once','--browser-supervisor',str(path)],cwd=ROOT,env=dict(os.environ),stdout=log,stderr=log,timeout=100)
            if (run.private/'browser-result.json').exists():report.update(json.loads((run.private/'browser-result.json').read_text()))
            owned=json.loads((run.private/'browser-supervision/owned.json').read_text());report['owned_browser']=owned
            assert child.returncode==0 and owned['operation_status']=='PASS' and owned['bound_processes_exited'] and not owned['errors'] and not owned['signals']
            assert report.get('browser_worker_final') and report['status']=='PASS'
        installed.collect_installation(run,complete=False)
        attest=report['process_installation_attestations'];assert set(attest)=={'setup-attestation','api-attestation','worker-0-attestation'}
        assert all(len(v)==2 and all(r['wheel_sha256']==report['installation']['wheel_sha256'] for r in v) for v in attest.values())
        opened=attest['api-attestation'][-1]['actual_opened_package_resources'];assert {'web.html','park_demo_web.html'}<=set(opened)
        report['work_completion_seconds']=time.monotonic()-started;assert report['work_completion_seconds']<=270
        report['stage']='COMPLETE';report['status']='PASS'
    except BaseException as error:failed(report,error)
    finally:
        if hasattr(run,'harness'):
            try:installed.collect_installation(run,complete=False)
            except BaseException as error:base.finalization_failure(report,error)
        if run.public is not None:
            try:
                installed.publish_logs(run)
                extra=[]
                for path in (run.private/'browser-supervisor.log',run.private/'browser-supervision/worker-output.log'):
                    if path.exists():
                        data=path.read_bytes();assert len(data)<=256*1024
                        for secret in run.secrets:data=data.replace(secret.encode(),b'[REDACTED_SYNTHETIC_SESSION]').replace(secret[:12].encode(),b'[REDACTED_SYNTHETIC_SESSION]')
                        extra.extend([('CAPTURED_COMPONENT '+path.name+'\n').encode(),data,b'\n'])
                with (run.public/'installation-redacted.log').open('ab') as log:log.write(b''.join(extra))
            except BaseException as error:base.finalization_failure(report,error)
    return base.finish_report(report,run.secrets,run.public,started=started,allowed_names=PUBLIC)


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--browser-supervisor':raise SystemExit(supervise_browser(sys.argv[2]))
    if len(sys.argv)==3 and sys.argv[1]=='--browser-worker':
        hand=json.loads(sys.stdin.buffer.readline(4096))
        assert hand['parent_pid']==os.getppid() and hand['worker_pid']==os.getpid() and 0<=time.monotonic()-hand['started']<85
        browser_worker(json.loads(Path(sys.argv[2]).read_text()),hand['started'])
    else:raise SystemExit(main())
