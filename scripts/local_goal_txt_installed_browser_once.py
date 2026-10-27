"""One installed NO_MODEL goal/TXT combination; fresh context, not PG restart."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import json,os,subprocess,tempfile,time
from scripts import local_source_restart_installed_browser_once as source

old=source.old
base=source.base
SHOTS=frozenset(('01-goals-unverified.png','02-goals-verified.png','03-goals-txt.png','04-fresh-original-link.png'))
TEXTS=frozenset(('current-case-record-pack.txt','fresh-case-record-pack.txt'))
PUBLIC_FILES=SHOTS|TEXTS|{'failure-source-restart.png','result.json','installation-redacted.log',old.WHEEL_NAME}
MARKER='核对数据（UTF-8 JSON，原文按JSON转义；不包含读取凭据）：\n'


def digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def truth(value,record,state):
    """Check full API hashes before comparing the intentionally narrower TXT."""
    assert value['preparation_id']==record['preparation_id'] and value['case_id']==record['case_id'] and value['run_id']==record['run_id']
    assert value['plan_id']==record['plan_id'] and value['state']==state
    assert value['current_required_goals']==source.GOALS and [r['goal'] for r in value['results']]==source.GOALS
    assert not value['case_goal_completed'] and value['read_only'] and not value['automatically_verified']
    assert (value['qualification'],value['external_acceptance'],value['offline_fulfillment'])==('NOT_EVALUATED','NOT_SUBMITTED','NO_EVIDENCE')
    expected=['LOCAL_OUTPUT_VERIFIED']*2 if state=='LOCAL_OUTPUTS_VERIFIED' else ['LOCAL_OUTPUT_VERIFIED','NEEDS_RECHECK']
    assert [r['state'] for r in value['results']]==expected
    trace=value['source_trace'];assert trace['trace_sha256']==digest({k:v for k,v in trace.items() if k!='trace_sha256'})
    assert trace['candidate']['producer']['mode']=='NO_MODEL' and trace['candidate']['producer']['real_model_calls']==0
    assert [s['adapter_id'] for s in trace['steps']]==['P1','P2','P3','P4']
    for row in value['results']:
        assert row['result_sha256']==digest({k:v for k,v in row.items() if k!='result_sha256'})
        assert row['adoption_trace_sha256']==trace['trace_sha256']


def unpack(text,value):
    prefix,raw=text.split(MARKER);pack=json.loads(raw)
    assert '核对数据 SHA256：'+digest(pack)+'\n' in prefix
    # Literal V1 export contract, independently constructed from the full API
    # object. Equality includes every exported key; no cropped original hash is
    # recomputed. This scenario has only the P1/P2 result/output contracts.
    def pick(item,fields):return {key:deepcopy(item[key]) for key in fields}
    expected=pick(value,('actor_id','preparation_id','case_id','run_id','preparation_revision','request_revision','current_request','original_request','plan_id','plan_revision','state','read_only','automatically_verified','case_goal_completed','qualification','external_acceptance','offline_fulfillment','current_required_goals','adopted_goals','binding_issues'))
    expected.update(scope='SYNTHETIC_CASE_RECORD_PACK_V1',source_scope=value['scope'],
        snapshot_limits='ALLOWED_READ_PROJECTION_ONLY; NOT_ALL_SOURCE_ATOMICITY; NOT_A_SIGNATURE; EXPORTED_COPY_CANNOT_BE_REVOKED')
    expected['results']=[pick(row,('goal','title','adapter_id','step_id','state','next_action','adoption_trace_sha256','result_sha256','issues','actual_output','historical_verification')) for row in value['results']]
    original=value['source_trace']
    trace=pick(original,('scope','preparation_id','case_id','run_id','plan_id','plan_revision','origin','historical_adoption_only','trace_sha256','required_goals','steps'))
    trace['adoption']=pick(original['adoption'],('event_id','event_revision','fingerprint','preparation_revision','request_revision','source_sha256','catalog_sha256','registry_sha256'))
    trace['candidate']=pick(original['candidate'],('candidate_id','candidate_sha256','verification_sha256','validator_version','accepted_at'))
    trace['selected_service_refs']=[]
    for ref in original['service_selection']['selection']['selections']:
        releases=[r for r in original['service_capabilities'] if r['release_id']==ref['release_id'] and r['revision']==ref['revision'] and r['release_sha256']==ref['release_sha256']]
        instances=[i for i in original['park_instances'] if i['instance_id']==ref['instance_id'] and i['config_revision']==ref['config_revision'] and i['config_sha256']==ref['config_sha256']]
        assert len(releases)==len(instances)==1
        trace['selected_service_refs'].append({**pick(ref,('release_id','revision','release_sha256','instance_id','config_revision','config_sha256')),'service_id':releases[0]['service_id'],'park_id':instances[0]['park_id']})
    expected['historical_adoption_source']=trace
    expected['historical_plans']=[pick(plan,('id','revision','goals')) for plan in value['historical_plans']]
    expected['template_availability']=None if value['template_availability'] is None else pick(value['template_availability'],('effective_release_id','effective_release_sha256','current','reasons'))
    assert pack==expected,'TXT differs from the complete literal export whitelist'
    return pack


class Flow(source.Flow):
    def shot(self,name,selector):
        assert name in SHOTS
        target=self.page.locator(selector);target.scroll_into_view_if_needed(timeout=15000)
        geometry=self.page.evaluate('''() => ({width:innerWidth,documentWidth:document.documentElement.scrollWidth,
            navPosition:getComputedStyle(document.querySelector('.workspace-nav')).position})''')
        assert geometry['documentWidth']<=geometry['width'] and geometry['navPosition'] not in ('sticky','fixed')
        path=self.run.public/name;self.page.screenshot(path=str(path),mask=[self.page.locator('#token')],timeout=10000)
        self.run.report['screenshots'].append(dict(file=name,sha256=sha256(path.read_bytes()).hexdigest(),geometry=geometry))


def export(flow,label,state,filename=None):
    run=flow.run;run.report['stage']=label;before=source.snapshot(run);posts=run.budget.posts;offset=len(run.report['responses'])
    flow.click('#service-plan-prepare');flow.page.wait_for_function('()=>servicePlanView?.plan_id',timeout=30000)
    plan=flow.page.evaluate('(keys)=>Object.fromEntries(keys.map(k=>[k,servicePlanView[k]]))',list(source.PLAN_FIELDS))
    expected=['VERIFIED','VERIFIED','PENDING','BLOCKED'] if state=='LOCAL_OUTPUTS_VERIFIED' else ['VERIFIED','NEEDS_RECHECK','BLOCKED','BLOCKED']
    assert [s['state'] for s in plan['steps']]==expected;source.tail_pending(before['preparation']['service_case_plan'])
    flow.click('#goal-results-read');flow.page.wait_for_function('()=>goalResultView!==null&&!document.querySelector("#goal-results-read").disabled',timeout=30000)
    value=flow.page.evaluate('goalResultView');truth(value,run.record,state)
    path='/api/preparations/'+run.record['preparation_id']+'/goal-results'
    assert source.call(run,'/goal-results')==value
    goal_reads=sum(r['path']==path and r['method']=='GET' for r in run.report['responses'])
    flow.click('#case-record-pack-generate');flow.page.wait_for_function('()=>!caseRecordPackBusy&&caseRecordPackView!==null',timeout=30000)
    text=flow.page.locator('#case-record-pack-text').input_value();pack=unpack(text,value)
    with flow.page.expect_download(timeout=30000) as observed:flow.click('#case-record-pack-download')
    download=observed.value
    assert download.failure() is None
    destination=run.public/filename if filename else run.private/'unverified-case-record-pack.txt'
    assert filename is None or filename in TEXTS
    download.save_as(destination)
    assert destination.read_bytes()==text.encode() and len(text.encode())<=128*1024
    assert sum(r['path']==path and r['method']=='GET' for r in run.report['responses'])==goal_reads+4
    assert all(r['method'] in ('GET','HEAD') for r in run.report['responses'][offset:]) and run.budget.posts==posts
    assert source.snapshot(run)==before
    for secret in run.secrets:assert secret not in text and secret[:12] not in text
    run.report.setdefault('exports',[]).append(dict(stage=label,goal_results=value,plan_UI=plan,pack=pack,pack_sha256=digest(pack),
        text_sha256=sha256(text.encode()).hexdigest(),bytes=len(text.encode()),file=filename,GET_only=True,named_business_projection_equal=True))
    return text,value


def current(run,browser):
    flow=Flow(run,browser);primary=None;path='/api/preparations/'+run.record['preparation_id']
    try:
        run.report['stage']='SOURCE_CHANGE_REQUIRED_INITIAL_STATE';flow.open();flow.existing();flow.click('#opp-read')
        flow.page.wait_for_function('()=>oppView?.cards.length===1&&!oppBusy',timeout=30000)
        flow.click('#service-plan-prepare');flow.page.wait_for_function('()=>servicePlanView?.plan_id',timeout=30000)
        flow.page.locator('#service-plan-reason').fill('SYNTHETIC 明确采纳实际来源差异，不核验未开始尾步')
        flow.click('[data-opp-plan-preview="'+run.card['id']+'"]')
        flow.page.wait_for_function('()=>opportunityPlanView?.can_adopt===true&&!opportunityPlanBusy',timeout=30000)
        flow.page.locator('#opp-plan-confirm').check()
        adopted=flow.post('#opp-plan-adopt',path+'/service-case-plan',status=201)
        run.report['source_ADOPT_UI']=dict(command_receipt=adopted['command_receipt'],revision=adopted['revision'])
        pending,_=export(flow,'CURRENT_UNVERIFIED_GOALS_TXT','UNVERIFIED')
        flow.shot('01-goals-unverified.png','#goal-results-status');flow.font('UNVERIFIED_GOALS_VISIBLE')
        assert 'NEEDS_RECHECK' in pending
        source.new_holds(run);flow.click('[data-tab="resource"]');flow.page.locator('#delivery-case').fill(run.record['preparation_id'])
        flow.click('#resource-catalog');flow.page.wait_for_function('()=>bundleActor!==null',timeout=30000)
        flow.click('#resource-mine');flow.page.wait_for_function('()=>bundleActor!==null&&!bundleBusy',timeout=30000)
        for hold in run.record['new_holds']:flow.page.locator('[data-combination-hold="'+hold['hold_id']+'"]').check()
        flow.page.locator('#delivery-reapproval').check();quote=flow.post('#delivery-preview',path+'/resource-delivery/preview')
        assert quote['expected_link_revision']==1 and quote['context']['source_reapproval']['source_adoption_event_id']==adopted['command_receipt']['id']
        proposal=flow.post('#plan-approval-propose',path+'/plan-approval/proposals',status=201);item=proposal['items'][-1]
        assert item['purpose']=='CASE_RESOURCE_REAPPROVAL'
        approval=flow.post('#plan-approval-approve',path+'/plan-approval/commands','APPROVE');assert approval['items'][-1]['state']=='APPROVED'
        run.new_delivery=flow.post('#delivery-confirm',path+'/resource-delivery',status=201)
        assert run.new_delivery['link']['revision']==2 and run.new_delivery['receipt']['plan_approval']['id']==item['id']
        source.step(run,'P2');flow.click('[data-tab="service"]');flow.existing()
        text,value=export(flow,'CURRENT_VERIFIED_GOALS_TXT','LOCAL_OUTPUTS_VERIFIED','current-case-record-pack.txt')
        flow.shot('02-goals-verified.png','#goal-results-status');flow.font('VERIFIED_GOALS_VISIBLE')
        flow.shot('03-goals-txt.png','#case-record-pack-output')
        run.hot_text=text;run.hot_results=value;run.sealed=source.snapshot(run)
        assert len(run.sealed['links'])==2 and all(h['state']=='CONFIRMED' for h in run.sealed['holds'])
        assert run.sealed['preparation']['service_case_plan']['steps'][0]==run.report['initial_business_snapshot']['preparation']['service_case_plan']['steps'][0]
        run.report['receipts_before_fresh_context']=[run.old_delivery['receipt'],run.new_delivery['receipt']]
    except BaseException as error:primary=error;raise
    finally:flow.close(primary)


def fresh(run,browser):
    old.require_work(run,60);flow=Flow(run,browser,cold=True);primary=None;posts=run.budget.posts
    path='/api/preparations/'+run.record['preparation_id'];offset=len(run.report['responses'])
    try:
        run.report['stage']='FRESH_CONTEXT_ORIGINAL_KEY_READ';flow.open();flow.existing()
        flow.click('#case-resource-load');flow.page.wait_for_function('()=>caseResourceView?.link_revision===2',timeout=30000)
        for original in (run.old_delivery,run.new_delivery):
            key=original['delivery_binding']['request_key'];flow.page.locator('#case-resource-recovery-kind').select_option('LINK')
            flow.page.locator('#case-resource-recovery-key').fill(key);flow.page.locator('#case-resource-recovery-fingerprint').fill('')
            with flow.page.expect_response(lambda r:r.request.method=='GET' and r.url.endswith(path+'/resource-link/recovery/'+key),timeout=30000) as observed:flow.click('#case-resource-recovery-read')
            response=observed.value;assert response.status==200;value=response.json()
            assert value['status']=='COMMITTED' and value['record']['id']==original['link']['id'] and value['fingerprint']==original['delivery_binding']['fingerprint']
            target=flow.page.locator('#case-resource-recovery-result');flow.expect(target).to_be_visible()
            for literal in ('COMMITTED',original['link']['id'],original['delivery_binding']['fingerprint']):flow.expect(target).to_contain_text(literal)
            receipt=source.call(run,'/resource-delivery/recovery/'+key);assert receipt['receipt']==original['receipt']
            run.report.setdefault('fresh_original_reads',[]).append(dict(key=key,LINK_response=value,DOM_text=target.inner_text(),receipt=receipt['receipt']))
        flow.shot('04-fresh-original-link.png','#case-resource-recovery-result');flow.font('FRESH_LINK_VISIBLE')
        text,value=export(flow,'FRESH_CONTEXT_GOALS_TXT','LOCAL_OUTPUTS_VERIFIED','fresh-case-record-pack.txt')
        assert text==run.hot_text and value==run.hot_results and source.snapshot(run)==run.sealed
        assert run.budget.posts==posts and all(r['method'] in ('GET','HEAD') for r in run.report['responses'][offset:])
        run.report['fresh_context']=dict(new_context=True,empty_localStorage_at_login=True,original_LINK_keys=2,full_receipts_equal=True,
            TXT_bytes_equal=True,full_goal_results_equal=True,business_POSTs=0,PG_restart=False,API_restart=False,setup_repeated=False)
    except BaseException as error:primary=error;raise
    finally:flow.close(primary)


def collect(run,complete=True):
    source.collect(run,complete=False)
    if not complete:return
    observations=run.report['process_installation_attestations']
    assert set(observations)=={'setup-attestation','api-attestation','worker-0-attestation'}
    for role,items in observations.items():
        assert len(items)==2 and items[0]['pid']==items[1]['pid']
        assert items[0]['stage'].startswith('BEFORE_') and items[1]['stage'].startswith('AFTER_')
        assert all(x['wheel_sha256']==run.report['installation']['wheel_sha256'] and x['verified_package_files']==191 and x['isolated'] and not x['PYTHONPATH'] for x in items)
    assert 'web.html' in observations['api-attestation'][-1]['actual_opened_package_resources']
    assert 'local-resource-approval-schema.sql' in observations['setup-attestation'][-1]['actual_opened_package_resources']
    assert len(run.report['service_generations'])==1 and run.report['installed_worker_exits']==[0]


def main():
    os.umask(0o077);started=time.monotonic()
    report=dict(status='NOT_RUN',stage='HOST_GATE',scope='INSTALLED_NO_MODEL_CURRENT_GOALS_TXT_FRESH_CONTEXT',responses=[],screenshots=[],violations=[],page_errors=[],real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False,PG_restart=False)
    run=SimpleNamespace(started=started,report=report,secrets=[],public=None);run.budget=old.Budget(report)
    try:
        report['source_sha']=base.require_hosted(os.environ,run_number='18')
        run.private=Path(tempfile.mkdtemp(prefix='parkweave-installed-goal-txt-'))
        run.public=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';run.public.mkdir(mode=0o700,exist_ok=False)
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
                with source.server(run,'first'):
                    source.prepare_first(run);current(run,browser);fresh(run,browser)
                collect(run)
        assert not report['violations'] and not report['page_errors'];old.require_work(run)
        assert run.budget.posts==30 and run.budget.phase_posts==dict(API_PREPARATION=25,BROWSER=5)
        report.update(work_completion_seconds=round(time.monotonic()-started,3),status='PASS',stage='INSTALLED_GOALS_TXT_FRESH_CONTEXT_COMPLETE')
    except BaseException as error:report.update(status='FAIL',error_type=type(error).__name__,error=str(error))
    finally:
        if hasattr(run,'harness'):
            try:collect(run,complete=False)
            except BaseException as error:base.finalization_failure(report,error)
        if run.public is not None:
            try:source.publish_logs(run)
            except BaseException as error:base.finalization_failure(report,error)
    return base.finish_report(report,run.secrets,run.public,started=started,allowed_names=PUBLIC_FILES)


if __name__=='__main__':raise SystemExit(main())
