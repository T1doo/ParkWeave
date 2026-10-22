"""One installed NO_MODEL P3/P4/P5 action chain; no external fulfillment."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit,parse_qs
from contextlib import ExitStack
import json,os,tempfile,time
from scripts import local_source_restart_installed_browser_once as source
from scripts.local_goal_txt_installed_browser_once import unpack,digest

old=source.old;base=source.base;GOALS=old.GOALS
SHOTS=frozenset(('01-tail-accepted.png','02-tail-receipt-acknowledged.png','03-p5-not-revalidated.png','04-five-goals-verified.png'))
TEXTS=frozenset(('p5-unverified-case-record-pack.txt','p5-verified-case-record-pack.txt'))
PUBLIC_FILES=SHOTS|TEXTS|{'failure-source-restart.png','result.json','installation-redacted.log',old.WHEEL_NAME}
TABLES=('cases','service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps','service_step_receipts','service_receipt_events','case_local_lifecycles','case_local_events','run_assignments')


def snapshot(run):
    value=source.snapshot(run)
    with source.owner(run) as c:
        c.execute('SET TRANSACTION READ ONLY')
        value['tail_tables']={name:c.execute('SELECT * FROM '+name+' ORDER BY to_jsonb('+name+')::text').fetchall() for name in TABLES}
    return json.loads(json.dumps(value,default=str,sort_keys=True))


def truth(value,record,expected):
    for key in ('preparation_id','case_id','run_id','plan_id'):assert value[key]==record[key]
    assert value['current_required_goals']==GOALS and [r['goal'] for r in value['results']]==GOALS
    assert [r['state'] for r in value['results']]==expected
    assert value['state']==('LOCAL_OUTPUTS_VERIFIED' if expected==['LOCAL_OUTPUT_VERIFIED']*5 else 'UNVERIFIED')
    assert not value['case_goal_completed'] and not value['automatically_verified'] and value['read_only']
    assert (value['qualification'],value['external_acceptance'],value['offline_fulfillment'])==('NOT_EVALUATED','NOT_SUBMITTED','NO_EVIDENCE')
    trace=value['source_trace'];assert trace['trace_sha256']==digest({k:v for k,v in trace.items() if k!='trace_sha256'})
    assert [s['adapter_id'] for s in trace['steps']]==['P1','P2','P3','P4','P5']
    assert trace['candidate']['producer']['mode']=='NO_MODEL' and trace['candidate']['producer']['real_model_calls']==0
    for row in value['results']:
        assert row['result_sha256']==digest({k:v for k,v in row.items() if k!='result_sha256'}) and row['adoption_trace_sha256']==trace['trace_sha256']


def goals(run,label,expected):
    run.report['stage']=label;value=source.call(run,'/goal-results');truth(value,run.record,expected)
    run.report.setdefault('goal_stages',[]).append(dict(stage=label,goal_results=value));return value


def exact_query(query,expected):
    parsed=parse_qs(query,keep_blank_values=True,strict_parsing=True,max_num_fields=6,encoding='utf-8',errors='strict')
    assert parsed=={k:[v] for k,v in expected.items()},'original recovery query differs or has duplicate/unknown fields'


def public_event(table,payload):
    # Existing OrdinaryCaseStepAssignments._dispatch_view hides this one key.
    return {k:v for k,v in payload.items() if k!='case_step_assignment'} if table=='service_dispatch_events' else payload


class Flow(source.Flow):
    def route(self,route):
        request=route.request;url=urlsplit(request.url);origin=urlsplit(self.run.report['origin'])
        if request.method=='GET' and url.path=='/api/service-dispatches/catalog' and url.query=='preparation_id='+self.run.record['preparation_id']:
            assert (url.scheme,url.netloc)==(origin.scheme,origin.netloc) and not url.username and not url.password
            self.run.budget.count('GET',url.path,'BROWSER');route.continue_();return
        pending=getattr(self,'recovery_binding',None)
        if pending and request.method=='POST' and url.path==pending['POST_path']:
            assert request.post_data_json['action']==pending['action'] and request.post_data_json['expected_revision']==int(pending['query']['expected_revision'])
            pending['key']=request.headers['idempotency-key']
        if pending and request.method=='GET' and url.path==pending['path']:
            assert (url.scheme,url.netloc)==(origin.scheme,origin.netloc) and not url.username and not url.password
            exact_query(url.query,pending['query'])
            key=request.headers.get('idempotency-key');assert key==pending['key'] and self.run.budget.keys[key]==dict(path=pending['POST_path'],action=pending['action'])
            assert self.actor=='executor' and request.headers['authorization']=='Bearer '+self.run.tokens['executor']
            self.run.budget.count('GET',url.path,'BROWSER');route.continue_();return
        super().route(route)
    def role(self,name):
        self.actor=name
        field=self.page.locator('#token')
        if field.input_value()!=self.run.tokens[name]:
            field.fill(self.run.tokens[name])
            self.page.wait_for_function('()=>dispatchView===null&&receiptView===null&&servicePlanView===null',timeout=30000)
    def post(self,selector,path,action=None,status=200):
        self.recovery_binding=None
        if action in ('ACCEPT','SUBMIT'):
            value=self.page.evaluate('dispatchView' if action=='ACCEPT' else 'receiptView')
            item=value['current_offer'] if action=='ACCEPT' else value['step']
            query={key:self.run.record[key] for key in ('preparation_id','case_id','run_id')}
            query.update(expected_revision=str(value['revision'] if action=='ACCEPT' else item['revision']),preparation_revision=str(item['preparation_revision']))
            if action=='ACCEPT':query['offer_id']=item['id']
            recovery=('/api/service-dispatches/'+value['dispatch_id']+'/accept-recovery') if action=='ACCEPT' else '/api/executor-receipts/'+item['id']+'/submit-recovery'
            self.recovery_binding=dict(path=recovery,POST_path=path,query=query,action=action,key=None)
        self.run.budget.authorize(path,action)
        with ExitStack() as stack:
            proof=stack.enter_context(self.page.expect_response(lambda r:r.request.method=='GET' and urlsplit(r.url).path==self.recovery_binding['path'],timeout=30000)) if self.recovery_binding else None
            observed=stack.enter_context(self.page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path==path,timeout=30000))
            self.click(selector)
        response=observed.value;assert response.status==status and self.run.budget.expected is None
        self.idle();self.page.wait_for_function('()=>!receiptSubmitBusy&&!dispatchAcceptBusy&&!localCaseRecoveryBusy',timeout=30000)
        value=response.json();key=response.request.headers['idempotency-key']
        table='service_dispatch_events' if path.endswith('/dispatch') or path.startswith('/api/service-dispatches/') else 'service_receipt_events' if path.startswith('/api/executor-receipts/') else 'case_local_events'
        with source.owner(self.run) as c:
            c.execute('SET TRANSACTION READ ONLY')
            rows=c.execute('SELECT id,actor_id,action,fingerprint,payload FROM '+table+' WHERE request_key=%s',(key,)).fetchall()
        assert len(rows)==1 and public_event(table,rows[0]['payload'])==value['event'] and rows[0]['action']==(action or 'OFFER')
        assert rows[0]['actor_id']=={'enterprise':'ordinary-demo-enterprise','specialist':'ordinary-demo-specialist','executor':'ordinary-demo-executor'}[self.actor]
        self.run.report.setdefault('browser_POST_key_proofs',[]).append(dict(path=path,key=key,action=action or 'OFFER',
            request=response.request.post_data_json,stored_event_id=str(rows[0]['id']),actor_id=rows[0]['actor_id'],fingerprint=rows[0]['fingerprint'],stored_payload=rows[0]['payload'],
            response_event_equals_original_key_SQL_public_projection=True,only_dispatch_internal_marker_projected=(table=='service_dispatch_events')))
        if proof:
            recovered=proof.value;assert recovered.status==200;record=recovered.json();binding=self.recovery_binding
            assert record['status']=='COMMITTED' and record['request_key']==key and record['event']['id']==str(rows[0]['id']) and record['event']['action']==action
            assert record['actor_ref']==digest(dict(actor_id=rows[0]['actor_id']))
            for field,expected in binding['query'].items():assert str(record[field])==expected
            assert record['read_only'] and record['historical_only'] and record['automatically_replayed'] is False
            self.run.report.setdefault('original_success_recovery_GETs',[]).append(dict(path=binding['path'],query=binding['query'],request_key=key,response=record,HTTP=200))
        return value
    def dispatch(self,id):
        self.click('[data-tab="collaboration"]');self.click('#dispatch-list')
        items=self.page.locator('#dispatch-items button');self.expect(items).to_have_count(1);items.click()
        self.page.wait_for_function('(id)=>dispatchView?.dispatch_id===id',arg=id,timeout=30000)
        assert self.page.evaluate('dispatchView.preparation_id')==self.run.record['preparation_id']
    def owner_case(self):
        self.role('enterprise');self.click('[data-tab="service"]');self.existing()
    def shot(self,name,selector):
        assert name in SHOTS;self.page.locator(selector).scroll_into_view_if_needed(timeout=15000)
        geometry=self.page.evaluate('''() => ({width:innerWidth,documentWidth:document.documentElement.scrollWidth,navPosition:getComputedStyle(document.querySelector('.workspace-nav')).position})''')
        assert geometry['width']==geometry['documentWidth'] and geometry['navPosition'] not in ('fixed','sticky')
        path=self.run.public/name;self.page.screenshot(path=str(path),mask=[self.page.locator('#token')],timeout=10000)
        self.run.report['screenshots'].append(dict(file=name,sha256=sha256(path.read_bytes()).hexdigest(),geometry=geometry))


def reject(run,label,suffix,body):
    run.report['stage']=label;before=snapshot(run)
    response=source.call(run,suffix,body,expected=409,phase='NEGATIVE_AND_REPEAT');after=snapshot(run)
    assert before==after
    run.report.setdefault('prerequisite_refusals',[]).append(dict(stage=label,path=suffix,request=body,response=response,HTTP=409,named_before=before,named_after=after,named_projection_equal=True))


def local_body(view,action):
    return dict(action=action,expected_revision=view['revision'],expected_cycle=view['cycle'],expected_snapshot_sha256=view['current_snapshot_sha256'],reason='SYNTHETIC 本人明确'+action)


def export(flow,label,filename,expected):
    run=flow.run;run.report['stage']=label;before=snapshot(run);offset=len(run.report['responses']);posts=run.budget.posts
    flow.click('#service-plan-prepare');flow.page.wait_for_function('()=>servicePlanView?.plan_id',timeout=30000)
    flow.click('#goal-results-read');flow.page.wait_for_function('()=>goalResultView!==null&&!document.querySelector("#goal-results-read").disabled',timeout=30000)
    value=flow.page.evaluate('goalResultView');truth(value,run.record,expected)
    assert source.call(run,'/goal-results')==value
    count=sum(v['path'].endswith('/goal-results') and v['method']=='GET' for v in run.report['responses'])
    flow.click('#case-record-pack-generate');flow.page.wait_for_function('()=>!caseRecordPackBusy&&caseRecordPackView!==null',timeout=30000)
    text=flow.page.locator('#case-record-pack-text').input_value();pack=unpack(text,value)
    assert filename in TEXTS
    with flow.page.expect_download(timeout=30000) as observed:flow.click('#case-record-pack-download')
    download=observed.value;assert download.failure() is None;path=run.public/filename;download.save_as(path)
    assert path.read_bytes()==text.encode() and len(path.read_bytes())<=128*1024
    assert sum(v['path'].endswith('/goal-results') and v['method']=='GET' for v in run.report['responses'])==count+4
    assert all(v['method'] in ('GET','HEAD') for v in run.report['responses'][offset:]) and run.budget.posts==posts and snapshot(run)==before
    for secret in run.secrets:assert secret not in text and secret[:12] not in text
    run.report.setdefault('exports',[]).append(dict(stage=label,file=filename,goal_results=value,pack=pack,pack_sha256=digest(pack),TXT_sha256=sha256(path.read_bytes()).hexdigest(),bytes=len(path.read_bytes()),GET_only=True,named_projection_equal=True))
    return value


def prepare(run):
    run.record=old.prepare(run,0,goals=GOALS);run.report['record']=run.record
    _,body=source.quote_body(run,run.record['holds']);item=source.api_approval(run,body)
    run.delivery=source.call(run,'/resource-delivery',{**body,'approval_id':item['id']},expected=201)
    source.step(run,'P2');run.report['initial_business_snapshot']=snapshot(run)


def walk(run,browser):
    flow=Flow(run,browser);primary=None;path='/api/preparations/'+run.record['preparation_id'];v='LOCAL_OUTPUT_VERIFIED'
    try:
        goals(run,'INITIAL_P1_P2_ONLY',[v,v,'WAITING_OUTPUT','WAITING_DEPENDENCY','WAITING_DEPENDENCY'])
        flow.open();flow.role('specialist')
        flow.existing();flow.click('#dispatch-prepare');flow.expect(flow.page.locator('#dispatch-offer')).to_be_visible()
        # The normal owned setup has exactly one eligible existing executor.
        choices=flow.page.locator('#dispatch-executor option');flow.expect(choices).to_have_count(1)
        executor=choices.first.get_attribute('value');assert executor=='ordinary-demo-executor'
        flow.page.locator('#dispatch-executor').select_option(executor);flow.page.locator('#dispatch-offer-reason').fill('SYNTHETIC 原专员明确分派既有执行者')
        run.report['stage']='P3_REVIEWER_OFFER';offered=flow.post('#dispatch-offer-button',path+'/dispatch',status=201)
        flow.role('executor');flow.dispatch(offered['dispatch_id']);flow.page.locator('#dispatch-decision-reason').fill('SYNTHETIC 原执行者本人接责')
        run.report['stage']='P3_EXECUTOR_ACCEPT';accepted=flow.post('#dispatch-accept','/api/service-dispatches/'+offered['dispatch_id']+'/commands','ACCEPT')
        run.report['accepted_dispatch']=accepted;flow.shot('01-tail-accepted.png','#dispatch-summary');flow.font('ACCEPTED_DISPATCH_VISIBLE')
        goals(run,'P3_ACCEPT_NOT_VERIFY',[v,v,'AWAITING_OWNER_VERIFICATION','WAITING_DEPENDENCY','WAITING_DEPENDENCY'])
        run.report['stage']='P3_OWNER_EXPLICIT_VERIFY_API';source.step(run,'P3')
        local=source.call(run,'/local-case');assert not local['can_revalidate'] and local['local_record_state']=='NOT_STARTED'
        reject(run,'P4_MISSING_REFUSES_REVALIDATE','/local-case/commands',local_body(local,'REVALIDATE'))
        run.report['stage']='P4_EXECUTOR_ORIGINAL_MANUAL_SUBMIT';flow.click('#dispatch-receipt');flow.expect(flow.page.locator('#receipt-submit')).to_be_visible()
        receipt_text='SYNTHETIC 许辰为虚构云杉企业整理本次办理记录；仅本地合成记录，不证明外部履约。'
        flow.page.locator('#receipt-text').fill(receipt_text);flow.page.locator('#receipt-source').fill('SYNTHETIC 本地原执行者办理记录 v1')
        receipt_path='/api/executor-receipts/'+accepted['receipt_step_id']+'/commands'
        submitted=flow.post('#receipt-submit-button',receipt_path,'SUBMIT');assert submitted['current_receipt']['text']==receipt_text
        run.report['submitted_receipt']=submitted;goals(run,'P4_SUBMIT_NOT_ACK',[v,v,v,'WAITING_OUTPUT','WAITING_DEPENDENCY'])
        flow.role('enterprise');flow.click('[data-tab="collaboration"]');flow.click('#receipt-list')
        items=flow.page.locator('#receipt-items button');flow.expect(items).to_have_count(1);items.click()
        flow.page.wait_for_function('(id)=>receiptView?.step.id===id',arg=accepted['receipt_step_id'],timeout=30000)
        flow.page.locator('#receipt-reason').fill('SYNTHETIC 企业本人明确核对原执行者全文')
        run.report['stage']='P4_OWNER_ACKNOWLEDGE';ack=flow.post('#receipt-ack',receipt_path,'ACKNOWLEDGE');run.report['acknowledged_receipt']=ack
        flow.shot('02-tail-receipt-acknowledged.png','#receipt-summary');flow.font('ACKNOWLEDGED_RECEIPT_VISIBLE')
        goals(run,'P4_ACK_NOT_VERIFY',[v,v,v,'AWAITING_OWNER_VERIFICATION','WAITING_DEPENDENCY'])
        run.report['stage']='P4_OWNER_EXPLICIT_VERIFY_API';source.step(run,'P4')
        goals(run,'P5_ORIGINAL_REVALIDATE_REQUIRED',[v,v,v,v,'WAITING_OUTPUT'])
        plan=source.call(run,'/service-case-plan');step=next(s for s in plan['steps'] if s['adapter_id']=='P5')
        local=source.call(run,'/local-case');assert local['can_revalidate'] and not local['can_close_local_record'] and local['local_record_state']=='NOT_STARTED'
        reject(run,'P5_VERIFY_WITHOUT_REVALIDATE','/service-case-plan/commands',dict(action='VERIFY',step_id=step['id'],expected_revision=plan['revision'],expected_source_sha256=step['source_sha256'],reason='SYNTHETIC 缺原重新校验必须拒绝'))
        reject(run,'P5_CLOSE_WITHOUT_REVALIDATE','/local-case/commands',local_body(local,'CLOSE_LOCAL_RECORD'))
        flow.owner_case();flow.click('#local-case-prepare');flow.page.wait_for_function('()=>localCaseView?.local_record_state==="NOT_STARTED"',timeout=30000)
        flow.expect(flow.page.locator('#local-case-close')).to_be_disabled();flow.shot('03-p5-not-revalidated.png','#local-case-summary')
        flow.existing();export(flow,'P5_MISSING_TXT','p5-unverified-case-record-pack.txt',[v,v,v,v,'WAITING_OUTPUT'])
        run.report['stage']='P5_OWNER_ORIGINAL_REVALIDATE';flow.click('#local-case-prepare');flow.page.wait_for_function('()=>localCaseView?.can_revalidate===true',timeout=30000)
        flow.page.locator('#local-case-reason').fill('SYNTHETIC 本人核对当前材料、资源、原接单与原回执后明确重新校验')
        ready=flow.post('#local-case-validate',path+'/local-case/commands','REVALIDATE');assert ready['local_record_state']=='READY'
        goals(run,'P5_REVALIDATE_NOT_VERIFY',[v,v,v,v,'AWAITING_OWNER_VERIFICATION'])
        run.report['stage']='P5_OWNER_EXPLICIT_CLOSE_LOCAL_RECORD';flow.page.locator('#local-case-reason').fill('SYNTHETIC 本人明确整理并关闭本地记录，不声明实际履约')
        closed=flow.post('#local-case-close',path+'/local-case/commands','CLOSE_LOCAL_RECORD');assert closed['local_record_state']=='LOCAL_RECORD_CLOSED'
        run.report['closed_local_record']=closed;goals(run,'P5_CLOSE_NOT_VERIFY',[v,v,v,v,'AWAITING_OWNER_VERIFICATION'])
        run.report['stage']='P5_OWNER_EXPLICIT_VERIFY_API';source.step(run,'P5')
        flow.existing();final=export(flow,'FIVE_GOALS_EXPLICITLY_VERIFIED_TXT','p5-verified-case-record-pack.txt',[v]*5)
        flow.page.set_viewport_size(dict(width=390,height=1000));flow.shot('04-five-goals-verified.png','#goal-results-status');flow.font('FIVE_GOAL_STATUS_NARROW')
        outputs={r['adapter_id']:r['actual_output'] for r in final['results']}
        assert outputs['P3']['offer_id']==accepted['current_offer']['id'] and outputs['P4']['receipt_id']==ack['current_receipt']['id']
        assert outputs['P5']['local_record_state']=='LOCAL_RECORD_CLOSED' and outputs['P5']['revalidation_event_id']
        after=snapshot(run);assert not after['tail_tables']['run_assignments']
        assert len(after['tail_tables']['case_local_events'])==2
        assert len(after['links'])==1 and len(after['holds'])==3 and all(h['state']=='CONFIRMED' for h in after['holds'])
        assert source.call(run,'/dispatch')['assignment_valid_until']==accepted['assignment_valid_until']
        run.report['final_named_business_snapshot']=after;run.report['local_close_is_not_external_fulfillment']=True
    except BaseException as error:primary=error;raise
    finally:flow.close(primary)


def main():
    os.umask(0o077);started=time.monotonic()
    report=dict(status='NOT_RUN',stage='HOST_GATE',scope='INSTALLED_NO_MODEL_ORIGINAL_P3_P4_P5_LOCAL_ACTIONS',responses=[],screenshots=[],violations=[],page_errors=[],real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False,PG_restart=False)
    run=SimpleNamespace(started=started,report=report,secrets=[],public=None);run.budget=old.Budget(report)
    try:
        report['source_sha']=base.require_hosted(os.environ,run_number='19')
        run.private=Path(tempfile.mkdtemp(prefix='parkweave-installed-tail-'));run.public=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';run.public.mkdir(mode=0o700,exist_ok=False)
        old.installation(run,old.current_wheel(run))
        from scripts.fictional_park_restart_browser_once import installed_font_environment
        env=dict(os.environ)
        for key,name in (('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')):
            directory=run.private/name;directory.mkdir(mode=0o700);env[key]=str(directory)
        env=installed_font_environment(env,run.private/'fontconfig',report)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            with pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=env) as browser:
                report['real_browser']=True;report['chrome_version']=browser.version;base.resource.verify_sandbox(browser,report)
                with source.server(run,'first'):prepare(run);walk(run,browser)
                from scripts.local_goal_txt_installed_browser_once import collect
                collect(run)
        assert not report['violations'] and not report['page_errors'];old.require_work(run)
        assert run.budget.posts==30 and run.budget.phase_posts==dict(API_PREPARATION=21,BROWSER=6,NEGATIVE_AND_REPEAT=3)
        report.update(status='PASS',stage='INSTALLED_P3_P4_P5_ORIGINAL_ACTIONS_COMPLETE',work_completion_seconds=round(time.monotonic()-started,3))
    except BaseException as error:report.update(status='FAIL',error_type=type(error).__name__,error=str(error))
    finally:
        if hasattr(run,'harness'):
            try:source.collect(run,complete=False)
            except BaseException as error:base.finalization_failure(report,error)
        if run.public is not None:
            try:source.publish_logs(run)
            except BaseException as error:base.finalization_failure(report,error)
    return base.finish_report(report,run.secrets,run.public,started=started,allowed_names=PUBLIC_FILES)


if __name__=='__main__':raise SystemExit(main())
