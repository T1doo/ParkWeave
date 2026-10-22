"""One bounded installed NO_MODEL A/B adoption and fresh-role readback window."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import json,os,tempfile,time
from urllib.parse import urlsplit
from scripts import local_tail_installed_browser_once as tail
source=tail.source;old=tail.old;base=tail.base
NAMES=frozenset(('01-new-input-confirmed.png','02-owner-distinct-plans.png','03-specialist-distinct-materials.png','04-executor-own-record.png','05-executor-denied-cleared.png'))
PUBLIC_FILES=NAMES|{'failure-source-restart.png','result.json','installation-redacted.log',old.WHEEL_NAME}
B_INPUT=dict(goal='SYNTHETIC 再次办理B 单独材料核对',request='SYNTHETIC B本次只整理培训目录，不沿用A安装包事项',need_summary='SYNTHETIC B员工培训需求 17人',material_outline='SYNTHETIC B独立培训大纲 第17版',goals=['LOCAL_MATERIAL_PREPARATION'])


def second(run):
    run.report['stage']='SECOND_NEW_INPUT_API_NO_OLD_MATERIAL_COPY'
    value=old.api_call(run,'/api/runs',dict(goal=B_INPUT['goal']),expected=202);old.worker_once(run,1)
    assert old.api_call(run,'/api/runs/'+value['run_id'])['state']=='SUCCEEDED'
    p=old.api_call(run,'/api/preparations',dict(run_id=value['run_id'],service_id='synthetic-material-preparation',service_version=1,reviewer_id='ordinary-demo-specialist'),expected=201)
    path='/api/preparations/'+p['preparation_id']
    p=old.api_call(run,path+'/request-intent',dict(expected_preparation_revision=p['revision'],request_text=B_INPUT['request'],required_goals=B_INPUT['goals']))
    for slot in ('need_summary','material_outline'):
        p=old.api_call(run,path+'/commands',dict(action='ADD_EVIDENCE',expected_revision=p['revision'],slot=slot,text=B_INPUT[slot],source_kind='USER_STATEMENT',source_label='SYNTHETIC B新输入非复用'))
    p=old.api_call(run,path+'/commands',dict(action='REVIEW',expected_revision=p['revision'],reason='SYNTHETIC 原专员明确审核B新资料'),actor='specialist')
    assert p['state']=='REVIEWED'
    return dict(preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=p['run_id'])


class Flow(tail.Flow):
    def route(self,route):
        if getattr(self,'reads_only',False) and route.request.method not in ('GET','HEAD'):
            self.run.report['violations'].append(dict(stage='FRESH_ROLE_READ',method=route.request.method,path=urlsplit(route.request.url).path));route.abort();raise AssertionError('fresh role read attempted POST')
        return super().route(route)
    def shot(self,name,selector):
        assert name in NAMES;self.page.locator(selector).scroll_into_view_if_needed(timeout=15000)
        geometry=self.page.evaluate('()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,navPosition:getComputedStyle(document.querySelector(".workspace-nav")).position})')
        assert geometry['width']==geometry['documentWidth'] and geometry['navPosition'] not in ('fixed','sticky')
        p=self.run.public/name;self.page.screenshot(path=str(p),mask=[self.page.locator('#token')],timeout=10000)
        self.run.report['screenshots'].append(dict(file=name,sha256=sha256(p.read_bytes()).hexdigest(),geometry=geometry))


def adopt_second(run,browser):
    flow=Flow(run,browser);primary=None
    try:
        flow.open();flow.existing();flow.expect(flow.page.locator('#prep-confirm')).to_be_enabled()
        flow.page.locator('#prep-reason').fill('SYNTHETIC 本人明确确认B的新资料')
        # Genuine original DOM action, counted as BROWSER, not reclassified API.
        path='/api/preparations/'+run.record['preparation_id']+'/commands';run.budget.authorize(path,'CONFIRM')
        with flow.page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path==path,timeout=30000) as observed:flow.click('#prep-confirm')
        response=observed.value;assert response.status==200 and run.budget.expected is None;flow.idle();p=response.json()
        key=response.request.headers['idempotency-key']
        with source.owner(run) as c:
            c.execute('SET TRANSACTION READ ONLY');rows=c.execute('SELECT * FROM preparation_events WHERE preparation_id=%s AND request_key=%s',(run.record['preparation_id'],key)).fetchall()
        assert len(rows)==1 and rows[0]['payload']==p and rows[0]['action']=='CONFIRM' and rows[0]['actor_id']=='ordinary-demo-enterprise'
        run.report['second_confirmation_original_key']=json.loads(json.dumps(dict(path=path,key=key,request=response.request.post_data_json,SQL_event=rows[0]),default=str))
        assert p['state']=='LOCAL_CONFIRMED'
        flow.shot('01-new-input-confirmed.png','#prep-materials')
        capabilities=source.call(run,'/service-capabilities')
        selected=source.call(run,'/service-selections',dict(expected_preparation_revision=p['revision'],expected_source_sha256=capabilities['source_sha256'],expected_capability_catalog_sha256=capabilities['capability_catalog_sha256']),expected=201)
        assert selected['producer']['mode']=='NO_MODEL' and selected['producer']['real_model_calls']==0
        plan=source.call(run,'/service-case-plan',dict(expected_preparation_revision=p['revision'],expected_request_revision=capabilities['request_revision'],expected_plan_revision=0,expected_source_sha256=capabilities['source_sha256'],required_goals=B_INPUT['goals'],reason='SYNTHETIC 本人明确采纳B独立NO_MODEL候选',candidate_id=selected['candidate_id'],expected_candidate_sha256=selected['candidate_sha256'],expected_verification_sha256=selected['verification_sha256']),expected=201)
        run.record['plan_id']=plan['plan_id'];run.report['second_candidate']=selected;run.report['second_initial_plan']=plan
        assert all(s['state']=='PENDING' for s in plan['steps'])
    except BaseException as error:primary=error;raise
    finally:flow.close(primary)


def accept_first(run,browser):
    flow=Flow(run,browser);primary=None
    try:
        flow.open();flow.role('specialist');flow.existing();flow.click('#dispatch-prepare')
        flow.expect(flow.page.locator('#dispatch-executor option')).to_have_count(1)
        flow.page.locator('#dispatch-executor').select_option('ordinary-demo-executor');flow.page.locator('#dispatch-offer-reason').fill('SYNTHETIC A原专员明确分派')
        path='/api/preparations/'+run.record['preparation_id']+'/dispatch'
        offered=flow.post('#dispatch-offer-button',path,status=201)
        flow.role('executor');flow.dispatch(offered['dispatch_id']);flow.page.locator('#dispatch-decision-reason').fill('SYNTHETIC A原执行者本人接责')
        accepted=flow.post('#dispatch-accept','/api/service-dispatches/'+offered['dispatch_id']+'/commands','ACCEPT')
        run.report['first_accepted_dispatch']=accepted
    except BaseException as error:primary=error;raise
    finally:flow.close(primary)


def assert_distinct(first,second):
    for key in ('preparation_id','case_id','run_id','plan_id'):assert first[key]!=second[key]


def reads(run,browser):
    original_record=run.record
    first,second=run.report['records'];assert_distinct(first,second)
    def both_snapshots():
        values={}
        for record in (first,second):
            run.record=record;values[record['preparation_id']]=tail.snapshot(run)
        run.record=original_record;return values
    sealed=both_snapshots();posts=run.budget.posts;start=len(run.report['responses'])
    run.report['fresh_roles']=[]
    for role in ('enterprise','specialist','executor'):
        run.report['stage']='FRESH_'+role.upper()+'_READ_ONLY';flow=Flow(run,browser);primary=None;flow.reads_only=True
        try:
            flow.open();flow.role(role)
            entry=dict(role=role,new_context=True,empty_localStorage=True,preparations=[],plans=[]);run.report['fresh_roles'].append(entry)
            if role!='executor':
                for record in (first,second):
                    run.record=record;flow.click('[data-tab="service"]');flow.existing();view=flow.page.evaluate('JSON.parse(JSON.stringify(preparationView))')
                    assert view['preparation']['id']==record['preparation_id'] and view['preparation']['case_id']==record['case_id'] and view['preparation']['run_id']==record['run_id']
                    entry['preparations'].append(view)
                    if record is second:
                        rendered=flow.page.locator('#prep-materials').inner_text()
                        assert B_INPUT['need_summary'] in rendered and B_INPUT['material_outline'] in rendered
                    else:assert B_INPUT['need_summary'] not in json.dumps(view,ensure_ascii=False)
                    if role=='enterprise':
                        flow.click('#service-plan-prepare');flow.page.wait_for_function('(id)=>servicePlanView?.plan_id===id',arg=record['plan_id'],timeout=30000)
                        plan=flow.page.evaluate('JSON.parse(JSON.stringify(servicePlanView))');entry['plans'].append(plan)
                        assert plan['candidate_consumption']['candidate_id']==(run.report['second_candidate']['candidate_id'] if record is second else run.report['API_initial_candidate_proofs'][0]['candidate_id'])
                        assert plan['required_goals']==(B_INPUT['goals'] if record is second else old.GOALS)
                        assert not plan['case_goal_completed']
                        assert [s['state'] for s in plan['steps']]==(['PENDING'] if record is second else ['VERIFIED','VERIFIED','PENDING','BLOCKED','BLOCKED'])
                flow.shot('02-owner-distinct-plans.png' if role=='enterprise' else '03-specialist-distinct-materials.png','#service-plan-summary' if role=='enterprise' else '#prep-materials')
            else:
                run.record=first;accepted=run.report['first_accepted_dispatch'];flow.dispatch(accepted['dispatch_id']);entry['dispatch']=flow.page.evaluate('JSON.parse(JSON.stringify(dispatchView))')
                flow.click('#dispatch-receipt');flow.page.wait_for_function('(id)=>receiptView?.step.id===id',arg=accepted['receipt_step_id'],timeout=30000)
                entry['receipt']=flow.page.evaluate('JSON.parse(JSON.stringify(receiptView))')
                assert entry['receipt']['step']['case_id']==first['case_id'] and entry['receipt']['current_receipt'] is None
                text=json.dumps([entry['dispatch'],entry['receipt']],ensure_ascii=False)
                assert all(v not in text for v in (B_INPUT['need_summary'],B_INPUT['material_outline'],B_INPUT['request']))
                flow.shot('04-executor-own-record.png','#receipt-summary')
                run.record=second;path='/api/preparations/'+second['preparation_id']
                denied=old.api_call(run,path+'/dispatch',actor='executor',expected=403);entry['B_dispatch_API_403']=denied
                flow.click('[data-tab="service"]');flow.page.locator('#existing-preparation-id').fill(second['preparation_id'])
                with flow.page.expect_response(lambda r:urlsplit(r.url).path==path+'/entry' and r.request.method=='GET',timeout=30000) as observed:flow.click('#existing-preparation-read')
                assert observed.value.status==403
                flow.page.wait_for_function('()=>preparationView===null&&servicePlanView===null&&dispatchView===null&&receiptView===null',timeout=30000)
                entry['B_entry_UI_403_after_navigation_cleared']=True;flow.shot('05-executor-denied-cleared.png','#existing-preparation-status')
            flow.font('FRESH_'+role.upper()+'_VISIBLE')
        except BaseException as error:primary=error;raise
        finally:flow.close(primary)
    run.record=original_record
    assert both_snapshots()==sealed and run.budget.posts==posts
    assert all(r['method'] in ('GET','HEAD') for r in run.report['responses'][start:])
    run.report['fresh_role_readback']=dict(roles=3,new_contexts=3,business_POSTs=0,named_projection_equal=True,PG_restart=False)
    run.report['final_named_business_snapshot']=sealed


def main():
    os.umask(0o077);started=time.monotonic();report=dict(status='NOT_RUN',stage='HOST_GATE',scope='INSTALLED_NO_MODEL_DISTINCT_INPUT_ADOPTIONS_FRESH_ROLE_READS',responses=[],screenshots=[],violations=[],page_errors=[],real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False,PG_restart=False)
    run=SimpleNamespace(started=started,report=report,secrets=[],public=None);run.budget=old.Budget(report)
    try:
        report['source_sha']=base.require_hosted(os.environ,run_number='22')
        run.private=Path(tempfile.mkdtemp(prefix='parkweave-installed-again-'));run.public=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';run.public.mkdir(mode=0o700,exist_ok=False)
        old.installation(run,old.current_wheel(run))
        from scripts.fictional_park_restart_browser_once import installed_font_environment
        env=dict(os.environ)
        for key,name in (('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')):
            p=run.private/name;p.mkdir(mode=0o700);env[key]=str(p)
        env=installed_font_environment(env,run.private/'fontconfig',report)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            with pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=env) as browser:
                report['real_browser']=True;report['chrome_version']=browser.version;base.resource.verify_sandbox(browser,report)
                with source.server(run,'first'):
                    # Existing A P1/P2 are setup prerequisites only; no new P1/P2
                    # acceptance claim, tail verification or TXT export here.
                    tail.prepare(run);first=deepcopy(run.record);accept_first(run,browser)
                    before_second=tail.snapshot(run)
                    run.record=second(run);adopt_second(run,browser);report['records']=[first,deepcopy(run.record)]
                    run.record=first;after_second=tail.snapshot(run)
                    assert {k:v for k,v in before_second.items() if k!='tail_tables'}=={k:v for k,v in after_second.items() if k!='tail_tables'}
                    for name,rows in before_second['tail_tables'].items():
                        actual=after_second['tail_tables'][name]
                        assert rows==([r for r in actual if r['id']==first['case_id']] if name=='cases' else actual)
                    report['first_before_second']=before_second;report['first_after_second']=after_second
                    run.record=report['records'][1]
                    reads(run,browser)
                old.collect_installation(run)
                for items in report['process_installation_attestations'].values():
                    assert all(x['verified_package_files']==191 and x['isolated'] and not x['PYTHONPATH'] for x in items)
        assert run.budget.posts==29 and run.budget.phase_posts==dict(API_PREPARATION=26,BROWSER=3)
        assert not report['violations'] and not report['page_errors'];old.require_work(run)
        report.update(status='PASS',stage='TWO_ADOPTED_INPUTS_THREE_FRESH_ROLES_COMPLETE',work_completion_seconds=round(time.monotonic()-started,3))
    except BaseException as error:report.update(status='FAIL',error_type=type(error).__name__,error=str(error))
    finally:
        if hasattr(run,'harness'):
            try:old.collect_installation(run,complete=False)
            except BaseException as error:base.finalization_failure(report,error)
        if run.public is not None:
            try:source.publish_logs(run)
            except BaseException as error:base.finalization_failure(report,error)
    return base.finish_report(report,run.secrets,run.public,started=started,allowed_names=PUBLIC_FILES)

if __name__=='__main__':raise SystemExit(main())
