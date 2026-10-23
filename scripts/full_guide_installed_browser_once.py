"""One installed synthetic A completion/B independent reuse,39 original DOM POSTs.

Two sequential90s browser supervisors share one270s work clock and one API/PG.
No API preparation writes, automatic VERIFY, second setup or external business.
"""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json,os,re,signal,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from scripts import guide_installed_browser_once as guide
from scripts.visual_owned_launch import atomic_report,supervise

installed=guide.installed;source=guide.source;tail=guide.tail;base=guide.base;ROOT=guide.ROOT
RUN='32';MODULE='scripts.full_guide_installed_browser_once'
SHOTS={'01-A-local-approved.png','02-A-executor-receipt.png','03-A-five-local-verified.png','04-B-independent-reuse.png'}
TEXTS={'A-local-verified-case.txt','B-unfinished-case.txt'}
PUBLIC=SHOTS|TEXTS|{'failure-guide.png','result.json','installation-redacted.log',installed.WHEEL_NAME}
failed=guide.failed


def snapshot(run):
    """Only this Case's named records. B's legitimate new rows are not compared."""
    result=source.snapshot(run);id=run.record['preparation_id']
    with source.owner(run) as c:
        c.execute('SET TRANSACTION READ ONLY')
        result['case']=c.execute('SELECT * FROM cases WHERE id=%s',(run.record['case_id'],)).fetchone()
        for name in ('preparation_evidence','preparation_events','service_dispatches','service_receipt_steps','case_local_lifecycles','case_local_events'):
            result[name]=c.execute('SELECT * FROM '+name+' WHERE preparation_id=%s ORDER BY id',(id,)).fetchall() if name not in ('case_local_lifecycles',) else c.execute('SELECT * FROM '+name+' WHERE preparation_id=%s',(id,)).fetchall()
        for name in ('service_dispatch_offers','service_dispatch_events'):
            result[name]=c.execute('SELECT * FROM '+name+' WHERE dispatch_id IN (SELECT id FROM service_dispatches WHERE preparation_id=%s) ORDER BY id',(id,)).fetchall()
        for name in ('service_step_receipts','service_receipt_events'):
            result[name]=c.execute('SELECT * FROM '+name+' WHERE step_id IN (SELECT id FROM service_receipt_steps WHERE preparation_id=%s) ORDER BY id',(id,)).fetchall()
    return json.loads(json.dumps(result,default=str,sort_keys=True))


class Budget(guide.Budget):
    def __init__(self,run):
        super().__init__(run)
        self.posts=len(run.report.get('DOM_write_requests',[]));self.reads=run.report.get('request_budget',{}).get('main_GET',0)
        self.keys={x['key'] for x in run.report.get('DOM_write_requests',[]) if x['key'] is not None}
    def route(self,route):
        req=route.request;url=urlsplit(req.url);origin=urlsplit(self.run.report['origin'])
        try:
            assert (url.scheme,url.netloc)==(origin.scheme,origin.netloc) and not url.username and not url.password
            assert url.path in ('/','/demo','/favicon.ico') or url.path.startswith('/api/')
            if req.method=='GET':assert self.reads<360;self.reads+=1
            else:
                assert req.method=='POST' and not url.query and not self.readonly and self.queue
                assert self.posts<(30 if self.run.phase=='A' else 39)
                path,action,actor=self.queue[0];body=req.post_data_json
                assert url.path==path and req.headers.get('authorization')=='Bearer '+self.run.tokens[actor]
                assert action is None or body.get('action')==action
                preview=path.endswith('/preview');key=req.headers.get('idempotency-key')
                if preview:assert key is None
                else:
                    assert key and re.fullmatch('[0-9a-f-]{36}',key) and key not in self.keys;self.keys.add(key)
                self.posts+=1;self.queue.pop(0)
                self.run.report.setdefault('DOM_write_requests',[]).append(dict(phase=self.run.phase,path=path,action=action,actor=actor,key=key,preview=preview,body=body))
            route.continue_()
        except BaseException as e:
            self.run.report['violations'].append(dict(method=req.method,path=url.path,error_type=type(e).__name__));route.abort();raise
        finally:
            self.run.report['request_budget']=dict(POST=self.posts,DOM_POST=self.posts,API_PREPARATION_POST=0,main_GET=self.reads,
                readiness_attempts=self.run.ready,GET=self.reads+self.run.ready,ceilings=dict(POST=40,DOM_POST=39,API_PREPARATION_POST=0,main_GET=360,readiness=40,GET=400,business_worker_once=2,browser_supervisor_segments=2))


class Walk(guide.Walk):
    def post(self,selector,path,*,action=None,status=200):
        self.run.report['current_control']=dict(phase=self.run.phase,selector=selector,path=path,action=action,actor=self.actor)
        self.run.report['stage']='PHASE_'+self.run.phase+'_DOM_'+(action or path.rsplit('/',1)[-1])
        return super().post(selector,path,action=action,status=status)
    def existing(self):
        self.click(self.w,'[data-tab="collaboration"]');self.click(self.w,'#prep-list')
        button=self.w.locator('#prep-items>button').filter(has_text=self.run.record['goal']);self.expect(button).to_have_count(1)
        button.scroll_into_view_if_needed(timeout=15000);button.click();self.ready()
        p=self.w.evaluate('preparationView.preparation')
        assert all(p[k]==self.run.record[v] for k,v in (('id','preparation_id'),('case_id','case_id'),('run_id','run_id')))
    def idle(self):
        self.w.wait_for_function('()=>!servicePlanPending&&!planApprovalBusy&&!deliveryBusy&&!bundleBusy&&!dispatchAcceptBusy&&!receiptSubmitBusy&&!localCaseRecoveryBusy&&!activeEntryWriteFlow&&entryWriteRequests.size===0&&!originalStoredWritePending()',timeout=30000)
    def shot(self,name,selector,page=None):
        assert name in SHOTS;page=page or self.w;page.locator(selector).scroll_into_view_if_needed(timeout=15000)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        path=self.run.public/name;page.screenshot(path=str(path),mask=[page.locator('#token')] if page is self.w else [page.locator('#sessions')],timeout=10000)
        self.run.report['screenshots'].append(dict(file=name,sha256=sha256(path.read_bytes()).hexdigest(),viewport=page.viewport_size))
    def verify(self,adapter):
        assert self.actor=='enterprise';self.existing();self.click(self.w,'#service-plan-prepare')
        self.w.wait_for_function('(id)=>servicePlanView?.plan_id===id&&!servicePlanPending',arg=self.run.record['plan_id'],timeout=30000)
        self.w.locator('#service-plan-reason').fill('SYNTHETIC 林岚在原入口明确核验本事项'+adapter)
        value=self.post('[data-service-adapter="'+adapter+'"] [data-service-action="VERIFY"]','/api/preparations/'+self.run.record['preparation_id']+'/service-case-plan/commands',action='VERIFY')
        assert next(x for x in value['steps'] if x['adapter_id']==adapter)['state']=='VERIFIED'
        self.run.report.setdefault('explicit_verifications',[]).append(dict(adapter=adapter,receipt=value['command_receipt']))
    def export(self,filename,verified=False,*,private=False):
        posts=self.run.budget.posts;self.click(self.w,'#service-plan-prepare');self.w.wait_for_function('()=>servicePlanView?.plan_id&&!servicePlanPending',timeout=30000)
        plan=self.w.evaluate('(fields)=>Object.fromEntries(fields.map(k=>[k,servicePlanView[k]]))',list(source.PLAN_FIELDS))
        assert plan['plan_id']==self.run.record['plan_id']
        assert [s['state'] for s in plan['steps']]==(['VERIFIED']*5 if verified else ['PENDING']+['BLOCKED']*4)
        self.click(self.w,'#goal-results-read');self.w.wait_for_function('()=>goalResultView!==null',timeout=30000);value=self.w.evaluate('goalResultView')
        tail.truth(value,self.run.record,['LOCAL_OUTPUT_VERIFIED']*5 if verified else ['AWAITING_OWNER_VERIFICATION']+['WAITING_DEPENDENCY']*4)
        self.click(self.w,'#case-record-pack-generate');self.w.wait_for_function('()=>caseRecordPackView!==null&&!caseRecordPackBusy',timeout=30000)
        text=self.w.locator('#case-record-pack-text').input_value();pack=guide.unpack(text,value)
        with self.w.expect_download(timeout=30000) as download:self.click(self.w,'#case-record-pack-download')
        assert download.value.failure() is None
        target=(self.run.private/'A-after-B-case.txt') if private else self.run.public/filename
        download.value.save_as(target);assert target.read_bytes()==text.encode() and len(text.encode())<=128*1024 and self.run.budget.posts==posts
        for secret in self.run.tokens.values():assert secret not in text and secret[:12] not in text
        self.run.report.setdefault('exports',[]).append(dict(phase=self.run.phase,file=None if private else filename,case=self.run.record['case_id'],goal_results=value,plan=plan,pack=pack,sha256=sha256(text.encode()).hexdigest(),bytes=len(text.encode()),business_POSTs=0))
        return text,value,plan
    def intake(self,reuse=False):
        w=self.w;run=self.run;self.click(w,'[data-tab="service"]');self.click(w,'#prep-catalog')
        self.guide.locator('#scenario').select_option('again' if reuse else 'first');w.locator('#prep-reviewer').select_option('ordinary-demo-specialist');self.click(self.guide,'#fill-goal')
        goal=w.locator('#prep-goal').input_value();run.budget.authorize(('/api/runs',None,'enterprise'),('/api/preparations',None,'enterprise'))
        with w.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path=='/api/runs',timeout=30000) as created:self.click(w,'#prep-create button')
        assert created.value.status==202;installed.worker_once(run,0 if run.phase=='A' else 1);self.ready();assert not run.budget.queue
        p=w.evaluate('preparationView.preparation');run.record=dict(preparation_id=p['id'],case_id=p['case_id'],run_id=p['run_id'],goal=goal);path='/api/preparations/'+p['id']
        self.click(w,'#plan-prepare');self.click(self.guide,'#fill-request');self.post('#request-save',path+'/request-intent');self.click(w,'#plan-materials');self.ready()
        if reuse:
            assert w.evaluate('preparationView.current_materials.length')==0
            self.click(w,'#material-reuse-read');w.wait_for_function('()=>materialReuseView?.items.length===1',timeout=30000)
            item=w.evaluate('materialReuseView.items[0]');assert item['source_preparation_id']==run.report['records']['A']['preparation_id']
            w.locator('#material-reuse-source').select_option(item['source_evidence_id']);self.click(w,'#material-reuse-preview');w.wait_for_function('()=>materialReuseView?.source_preview',timeout=30000)
            w.locator('#material-reuse-purpose').check();w.locator('#material-reuse-reason').fill('SYNTHETIC 林岚明确同用途复制原生目录，本次新诉求独立审核')
            copied=self.post('#material-reuse-confirm',path+'/material-reuse',status=201);self.ready()
            proof=copied['material_reuse'];material=w.evaluate('preparationView.current_materials.find(x=>x.slot==="material_outline")')
            assert copied['preparation_id']==run.record['preparation_id'] and copied['state']=='IN_PREPARATION'
            assert proof['source_preparation_id']==item['source_preparation_id'] and proof['source_evidence_id']==item['source_evidence_id']
            assert proof['target_evidence_id']==material['id'] and material['id']!=item['source_evidence_id'] and proof['requires_independent_review'] is True
            assert material['version']==1 and sha256(material['text'].encode()).hexdigest()==material['source_sha256']==item['source_evidence_sha256']==proof['target_sha256']
            run.report['reuse']=dict(source=item,original_response=copied,actual_new_material=material)
        for button in (('#fill-need',) if reuse else ('#fill-need','#fill-outline')):
            self.click(self.guide,button);self.post('#prep-evidence button',path+'/commands',action='ADD_EVIDENCE');self.ready()
        self.role('specialist');self.existing();w.locator('#prep-reason').fill('SYNTHETIC 周禾独立核对本次新资料')
        reviewed=self.post('#prep-review',path+'/commands',action='REVIEW');self.ready()
        self.role('enterprise');self.existing();w.locator('#prep-reason').fill('SYNTHETIC 林岚独立确认本次新资料')
        confirmed=self.post('#prep-confirm',path+'/commands',action='CONFIRM');self.ready()
        events=[]
        with source.owner(run) as c:
            c.execute('SET TRANSACTION READ ONLY')
            for action,actor,response in (('REVIEW','ordinary-demo-specialist',reviewed),('CONFIRM','ordinary-demo-enterprise',confirmed)):
                request=next(x for x in run.report['DOM_write_requests'] if x['phase']==run.phase and x['action']==action)
                rows=c.execute('SELECT id,actor_id,request_key,action,payload FROM preparation_events WHERE preparation_id=%s AND request_key=%s',(run.record['preparation_id'],request['key'])).fetchall()
                assert len(rows)==1 and rows[0]['actor_id']==actor and rows[0]['action']==action and rows[0]['payload']==response
                assert response['preparation_id']==run.record['preparation_id'] and response['case_id']==run.record['case_id'] and response['run_id']==run.record['run_id']
                events.append(rows[0])
        run.report.setdefault('independent_material_decisions',{})[run.phase]=json.loads(json.dumps(events,default=str))
        self.click(w,'#service-plan-prepare');w.wait_for_function('()=>servicePlanView!==null',timeout=30000)
        self.click(w,'#service-selection-read');w.wait_for_function('()=>serviceSelectionCatalog!==null&&!serviceSelectionBusy',timeout=30000)
        selected=self.post('#service-selection-generate',path+'/service-selections',status=201)
        assert selected['producer']['mode']=='NO_MODEL' and selected['producer']['real_model_calls']==0
        w.locator('#service-selection-confirm').check();w.locator('#service-plan-reason').fill('SYNTHETIC 林岚明确采纳本次新候选，不继承其他Case核验')
        plan=self.post('#service-plan-adopt',path+'/service-case-plan',status=201);run.record['plan_id']=plan['plan_id']
        assert plan['candidate_consumption']['candidate_id']==selected['candidate_id'] and not any(e['action']=='VERIFY' for e in plan['events'])
        run.report.setdefault('records',{})[run.phase]=deepcopy(run.record)
        run.report.setdefault('candidates',{})[run.phase]=dict(candidate_id=selected['candidate_id'],candidate_sha256=selected['candidate_sha256'],plan_id=plan['plan_id'])
    def resources(self):
        w=self.w;self.click(w,'[data-tab="resource"]');self.click(w,'#resource-catalog');w.wait_for_function('()=>bundleActor!==null',timeout=30000)
        ids=w.locator('#resource-select option').evaluate_all('rows=>rows.map(r=>r.value)');assert len(ids)==2
        now=datetime.now(timezone.utc);holds=[]
        for n,rid in enumerate((ids[0],ids[1],ids[0])):
            start=now+timedelta(hours=1 if n<2 else 4);end=start+timedelta(hours=1)
            w.locator('#resource-select').select_option(rid);w.locator('#resource-start').fill(start.strftime('%Y-%m-%dT%H:%M'));w.locator('#resource-end').fill(end.strftime('%Y-%m-%dT%H:%M'))
            w.locator('#resource-quantity').fill('1');w.locator('#resource-ttl').fill('300');w.locator('#resource-purpose').fill('SYNTHETIC 原页面本地演示占位'+str(n))
            q=self.post('#resource-preview','/api/synthetic-resources/'+rid+'/preview');assert q['available'] is True
            held=self.post('#resource-hold','/api/synthetic-resources/'+rid+'/holds',status=201);holds.append(held['hold']['id'])
        self.click(w,'#resource-mine');w.wait_for_function('()=>!bundleBusy',timeout=30000)
        for id in holds:w.locator('[data-combination-hold="'+id+'"]').check()
        w.locator('#delivery-case').fill(self.run.record['preparation_id']);path='/api/preparations/'+self.run.record['preparation_id']
        quote=self.post('#delivery-preview',path+'/resource-delivery/preview');assert quote['context']['plan_id']==self.run.record['plan_id']
        proposed=self.post('#plan-approval-propose',path+'/plan-approval/proposals',status=201);item=proposed['items'][-1];assert item['state']=='PROPOSED'
        approved=self.post('#plan-approval-approve',path+'/plan-approval/commands',action='APPROVE');assert approved['items'][-1]['id']==item['id'] and approved['items'][-1]['state']=='APPROVED'
        self.shot('01-A-local-approved.png','#plan-approval-panel')
        delivered=self.post('#delivery-confirm',path+'/resource-delivery',status=201)
        assert delivered['receipt']['plan_approval']['scope']=='LOCAL_CASE_RESOURCE_APPROVAL_V1' and delivered['receipt']['plan_approval']['id']==item['id'] and delivered['link']['revision']==1
        self.run.report['local_delivery']=dict(approval_id=item['id'],holds=holds,receipt=delivered['receipt'])
    def dispatch(self,id):
        self.click(self.w,'[data-tab="collaboration"]');self.click(self.w,'#dispatch-list')
        item=self.w.locator('#dispatch-items>button').filter(has_text=id);self.expect(item).to_have_count(1);item.click()
        self.w.wait_for_function('(id)=>dispatchView?.dispatch_id===id',arg=id,timeout=30000)
    def complete(self):
        self.verify('P1');self.resources();self.verify('P2');path='/api/preparations/'+self.run.record['preparation_id'];w=self.w
        self.role('specialist');self.existing();self.click(w,'#dispatch-prepare')
        self.expect(w.locator('#dispatch-executor option')).to_have_count(1);w.locator('#dispatch-executor').select_option('ordinary-demo-executor');w.locator('#dispatch-offer-reason').fill('SYNTHETIC 周禾明确分派本事项')
        offered=self.post('#dispatch-offer-button',path+'/dispatch',status=201)
        self.role('executor');self.dispatch(offered['dispatch_id']);w.locator('#dispatch-decision-reason').fill('SYNTHETIC 许辰本人明确接责')
        accepted=self.post('#dispatch-accept','/api/service-dispatches/'+offered['dispatch_id']+'/commands',action='ACCEPT');self.run.report['accepted_dispatch']=accepted
        self.role('enterprise');self.verify('P3');self.role('executor');self.dispatch(offered['dispatch_id']);self.click(w,'#dispatch-receipt')
        w.locator('#receipt-text').fill('SYNTHETIC 许辰为虚构云杉企业整理本次巡检办理记录；无外部履约。');w.locator('#receipt-source').fill('SYNTHETIC 青禾园本地原办理记录')
        receipt_path='/api/executor-receipts/'+accepted['receipt_step_id']+'/commands';self.post('#receipt-submit-button',receipt_path,action='SUBMIT')
        self.shot('02-A-executor-receipt.png','#receipt-current')
        self.role('enterprise');self.click(w,'[data-tab="collaboration"]');self.click(w,'#receipt-list')
        item=w.locator('#receipt-items>button').filter(has_text=accepted['receipt_step_id']);self.expect(item).to_have_count(1);item.click()
        w.wait_for_function('(id)=>receiptView?.step.id===id',arg=accepted['receipt_step_id'],timeout=30000);w.locator('#receipt-reason').fill('SYNTHETIC 林岚本人明确核对原回执全文')
        self.post('#receipt-ack',receipt_path,action='ACKNOWLEDGE');self.verify('P4');self.existing();self.click(w,'#local-case-prepare')
        w.wait_for_function('()=>localCaseView?.can_revalidate===true',timeout=30000)
        w.locator('#local-case-reason').fill('SYNTHETIC 林岚本人明确重新校验本轮本地记录');self.post('#local-case-validate',path+'/local-case/commands',action='REVALIDATE')
        w.locator('#local-case-reason').fill('SYNTHETIC 林岚明确关闭本地记录，不证明真实履约');self.post('#local-case-close',path+'/local-case/commands',action='CLOSE_LOCAL_RECORD');self.verify('P5')


def phase_flow(run,browser):
    walk=Walk(run,browser,1200 if run.phase=='A' else 390);error=None
    try:
        run.report['stage']='PHASE_'+run.phase+'_ORIGINAL_GUIDE';walk.open();walk.intake(reuse=run.phase=='B')
        if run.phase=='A':
            walk.complete();original=walk.export('A-local-verified-case.txt',True);walk.shot('03-A-five-local-verified.png','#goal-results-status');walk.font('A_FIVE_VERIFIED')
            assert run.budget.posts==30;run.report['A_sealed_snapshot']=snapshot(run)
            run.report['A_export_signature']=dict(sha256=sha256(original[0].encode()).hexdigest(),goal_results=original[1],plan=original[2])
        else:
            a=run.report['records']['A'];b=run.report['records']['B']
            assert all(a[k]!=b[k] for k in ('preparation_id','case_id','run_id','plan_id','goal'))
            assert run.report['candidates']['A']['candidate_id']!=run.report['candidates']['B']['candidate_id']
            walk.export('B-unfinished-case.txt');walk.shot('04-B-independent-reuse.png','#goal-results-status');walk.font('B_UNFINISHED')
            assert run.budget.posts==39;run.budget.readonly=True;run.record=deepcopy(a);run.report['stage']='A_AFTER_B_READ_ONLY'
            walk.existing();original=walk.export('A-local-verified-case.txt',True,private=True);signature=run.report['A_export_signature']
            assert original[1]==signature['goal_results'] and original[2]==signature['plan'] and sha256(original[0].encode()).hexdigest()==signature['sha256']
            after=snapshot(run);assert after==run.report['A_sealed_snapshot']
            run.report['A_after_B']=dict(named_projection_after=after,goal_plan_TXT_equal=True,business_POSTs=0,
                excluded_B_rows='B Case,Run,preparation,evidence/events,candidate,plan are legitimate distinct new records;not wholeDB comparison')
    except BaseException as e:error=e;failed(run.report,e);raise
    finally:walk.close(error)


def browser_worker(config,started):
    run=SimpleNamespace(**config)
    for k in ('private','public','harness','state','python'):setattr(run,k,Path(getattr(run,k)))
    run.tokens={k:v for k,v in json.loads((run.state/'sessions.json').read_text()).items() if k in ('enterprise','specialist','executor')};run.budget=Budget(run);report=run.report
    def alarm(*_):raise TimeoutError('85s segment operation reached cleanup reserve')
    signal.signal(signal.SIGALRM,alarm);signal.alarm(max(1,int(85-(time.monotonic()-started))))
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            report['stage']='PHASE_'+run.phase+'_CHROME_LAUNCH'
            try:browser=pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=config['chrome_env'],timeout=15000)
            except BaseException as e:failed(report,e);atomic_report(Path(config['browser_result']),report);raise
            try:report['chrome_version']=browser.version;base.resource.verify_sandbox(browser,report);phase_flow(run,browser)
            except BaseException as e:failed(report,e);raise
            finally:
                try:browser.close();report.setdefault('browser_closes',{})[run.phase]='CLOSED'
                except BaseException as e:report.setdefault('browser_cleanup_errors',[]).append(type(e).__name__);failed(report,e);raise
        assert run.budget.posts==(30 if run.phase=='A' else 39) and not report['violations'] and not report['page_errors']
        commands=report['DOM_write_requests'];previews=[x for x in commands if x['preview']];keys=[x['key'] for x in commands if not x['preview']]
        assert len(previews)==4 and all(x['key'] is None and x['phase']=='A' for x in previews)
        assert len(keys)==len(set(keys))==(26 if run.phase=='A' else 35)
        assert sum(x['phase']=='A' for x in commands)==30 and sum(x['phase']=='B' for x in commands)==(0 if run.phase=='A' else 9)
        report.update(status='PASS',stage='PHASE_'+run.phase+'_COMPLETE')
    except BaseException as e:failed(report,e);raise
    finally:
        signal.alarm(0);report.setdefault('browser_segment_seconds',{})[run.phase]=time.monotonic()-started
        report['browser_worker_final']=run.phase;atomic_report(Path(config['browser_result']),report)


def supervisor(config_path):
    config=json.loads(Path(config_path).read_text());directory=Path(config['private'])/('browser-supervision-'+config['phase']);directory.mkdir(mode=0o700)
    result=supervise([sys.executable,'-B','-m',MODULE,'--browser-worker',str(config_path)],env=dict(os.environ),cwd=ROOT,directory=directory,started=time.monotonic())
    atomic_report(directory/'owned.json',result)
    return 0 if result['status']=='CLEANUP_CONFIRMED' and result['operation_status']=='PASS' else 1


def main():
    os.umask(0o077);started=time.monotonic();report=dict(scope='INSTALLED_FULL_NO_MODEL_A_AND_INDEPENDENT_REUSE_B',status='NOT_RUN',stage='HOST_GATE',responses=[],screenshots=[],violations=[],page_errors=[],real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False,PG_restart=False)
    run=SimpleNamespace(started=started,report=report,secrets=[],public=None)
    try:
        report['source_sha']=base.require_hosted(os.environ,run_number=RUN);run.private=Path(tempfile.mkdtemp(prefix='parkweave-installed-full-guide-'))
        run.public=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';run.public.mkdir(mode=0o700)
        installed.installation(run,installed.current_wheel(run));env=dict(os.environ)
        for key,name in (('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')):
            d=run.private/name;d.mkdir(mode=0o700);env[key]=str(d)
        env=guide.installed_font_environment(env,run.private/'fontconfig',report);run.budget=SimpleNamespace(internal_reads=0)
        with installed.server(run):
            with source.owner(run) as c:
                c.execute('SET TRANSACTION READ ONLY');report['empty_business_tables']={t:c.execute('SELECT count(*) n FROM '+t).fetchone()['n'] for t in ('runs','cases','preparations','service_dispatches','service_receipt_steps','run_assignments')};assert not any(report['empty_business_tables'].values())
            for phase,reserve in (('A',235),('B',145)):
                installed.require_work(run,reserve);report.update(status='RUNNING',stage='ADMIT_'+phase)
                report.setdefault('phase_admissions',[]).append(dict(phase=phase,elapsed=time.monotonic()-started,reserved_seconds=reserve,root_limit=270))
                result=run.private/('browser-result-'+phase+'.json');path=run.private/('browser-config-'+phase+'.json')
                cfg=dict(started=started,phase=phase,report=report,ready=run.budget.internal_reads,chrome_env=env,browser_result=str(result),**{k:str(getattr(run,k)) for k in ('private','public','harness','state','python')});path.write_text(json.dumps(cfg))
                with (run.private/('browser-supervisor-'+phase+'.log')).open('w') as log:
                    child=subprocess.run([sys.executable,'-B','-m',MODULE,'--browser-supervisor',str(path)],cwd=ROOT,env=dict(os.environ),stdout=log,stderr=log,timeout=100)
                if result.exists():report.update(json.loads(result.read_text()))
                owned=json.loads((run.private/('browser-supervision-'+phase)/'owned.json').read_text());report.setdefault('owned_browsers',{})[phase]=owned
                assert child.returncode==0 and owned['operation_status']=='PASS' and owned['bound_processes_exited'] and not owned['errors'] and not owned['signals']
                assert report.get('browser_worker_final')==phase and report['status']=='PASS'
        installed.collect_installation(run,complete=False);attest=report['process_installation_attestations']
        assert set(attest)=={'setup-attestation','api-attestation','worker-0-attestation','worker-1-attestation'}
        assert all(len(v)==2 and all(x['wheel_sha256']==report['installation']['wheel_sha256'] and x['isolated'] and not x['PYTHONPATH'] for x in v) for v in attest.values())
        report['work_completion_seconds']=time.monotonic()-started;assert report['work_completion_seconds']<=270
        report.update(status='PASS',stage='COMPLETE')
    except BaseException as e:failed(report,e)
    finally:
        if hasattr(run,'harness'):
            try:installed.collect_installation(run,complete=False)
            except BaseException as e:base.finalization_failure(report,e)
        if run.public is not None:
            try:
                installed.publish_logs(run)
                with (run.public/'installation-redacted.log').open('ab') as log:
                    for phase in ('A','B'):
                        for path in (run.private/('browser-supervisor-'+phase+'.log'),run.private/('browser-supervision-'+phase)/'worker-output.log'):
                            if not path.exists():continue
                            data=path.read_bytes();assert len(data)<=256*1024
                            for secret in run.secrets:data=data.replace(secret.encode(),b'[REDACTED_SYNTHETIC_SESSION]').replace(secret[:12].encode(),b'[REDACTED_SYNTHETIC_SESSION]')
                            log.write(('CAPTURED_COMPONENT '+str(path.relative_to(run.private))+'\n').encode()+data+b'\n')
            except BaseException as e:base.finalization_failure(report,e)
    return base.finish_report(report,run.secrets,run.public,started=started,allowed_names=PUBLIC)


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--browser-supervisor':raise SystemExit(supervisor(sys.argv[2]))
    if len(sys.argv)==3 and sys.argv[1]=='--browser-worker':
        hand=json.loads(sys.stdin.buffer.readline(4096));assert hand['parent_pid']==os.getppid() and hand['worker_pid']==os.getpid() and 0<=time.monotonic()-hand['started']<85
        browser_worker(json.loads(Path(sys.argv[2]).read_text()),hand['started'])
    else:raise SystemExit(main())
