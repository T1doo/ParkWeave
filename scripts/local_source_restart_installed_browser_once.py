"""One installed LOCAL source reapproval and true same-state restart; no model."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4
import json,os,socket,subprocess,tempfile,time
import httpx,psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from scripts import local_approval_installed_browser_once as old

base=old.base
GOALS=['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION']
SHOTS=frozenset(('01-source-impact.png','02-source-adopted.png','03-reapproval-approved.png',
 '04-reapproval-consumed.png','05-restarted-history.png','06-restarted-original-link.png'))
PLAN_FIELDS=('actor_ref','role','preparation_id','case_id','run_id','plan_id','revision','required_goals','binding','events','steps')
PUBLIC_FILES=SHOTS|{'failure-source-restart.png','result.json','installation-redacted.log',old.WHEEL_NAME}


def owner(run):
    return psycopg.connect(make_conninfo(host=str(run.state/'socket'),port=5432,user='postgres',dbname='parkweave',connect_timeout=2),row_factory=dict_row)


def snapshot(run):
    """Named business projection, not audit rows or entire database invariance."""
    with owner(run) as c:
        c.execute('SET TRANSACTION READ ONLY')
        p=c.execute('SELECT id,case_id,run_id,revision,service_case_plan,local_resource_approvals,local_resource_approval_head FROM preparations WHERE id=%s',(run.record['preparation_id'],)).fetchone()
        links=c.execute('SELECT * FROM case_resource_links WHERE preparation_id=%s ORDER BY revision',(p['id'],)).fetchall()
        holds=c.execute('SELECT id,state,resource_id,resource_revision,starts_at,ends_at,expires_at FROM synthetic_resource_holds ORDER BY id').fetchall()
        receipts=c.execute('SELECT * FROM synthetic_resource_combination_receipts ORDER BY id').fetchall()
    return json.loads(json.dumps(dict(preparation=p,links=links,holds=holds,receipts=receipts),default=str,sort_keys=True))


def tail_pending(plan):
    assert [s['adapter_id'] for s in plan['steps']]==['P1','P2','P3','P4']
    tail=[s for s in plan['steps'] if s['adapter_id'] in ('P3','P4')]
    assert all(s.get('coordination_state',s.get('state'))=='PENDING' and s['verified_sources'] is None and s['verified_sha256'] is None for s in tail)
    assert not any(e['action']=='VERIFY' and e['step_id'] in {s['id'] for s in tail} for e in plan['events'])


def call(run,suffix='',body=None,**kw):
    return old.api_call(run,'/api/preparations/'+run.record['preparation_id']+suffix,body,**kw)


def step(run,adapter,action='VERIFY'):
    p=call(run,'/service-case-plan');s=next(s for s in p['steps'] if s['adapter_id']==adapter)
    return call(run,'/service-case-plan/commands',dict(action=action,step_id=s['id'],expected_revision=p['revision'],expected_source_sha256=s['source_sha256'],reason='SYNTHETIC 本次明确'+action))


def quote_body(run,holds,revision=None,*,phase='API_PREPARATION'):
    data=dict(members=holds)
    if revision is not None:data['expected_link_revision']=revision
    q=call(run,'/resource-delivery/preview',data,phase=phase)
    body=dict(members=holds,expected_preparation_revision=q['expected_preparation_revision'],expected_plan_revision=q['expected_plan_revision'],expected_source_sha256=q['source_sha256'],valid_until=q['valid_until'],reason='SYNTHETIC 本次明确资源交付')
    if revision is not None:body['expected_link_revision']=revision
    return q,body


def api_approval(run,body,*,phase='API_PREPARATION'):
    view=call(run,'/plan-approval');v=call(run,'/plan-approval/proposals',dict(delivery=body,expected_revision=view['revision']),expected=201,phase=phase)
    # Actual model fields are checked by the original API schema and ledger.
    item=v['items'][-1]
    v=call(run,'/plan-approval/commands',dict(action='APPROVE',approval_id=item['id'],expected_revision=v['revision'],expected_binding_sha256=item['binding_sha256'],reason='SYNTHETIC 本人明确批准'),expected=200,phase=phase)
    return v['items'][-1]


@contextmanager
def server(run,tag):
    """Two generations, one remaining readiness allowance, all failures retained."""
    assert tag in ('first','restarted')
    prior=run.budget.internal_reads;remaining=40-prior;assert remaining>0
    shared=run.harness/'owned-processes.json'
    if shared.exists():
        archived=run.private/'first-owned-processes.json'
        assert tag=='restarted' and archived.exists() and shared.read_bytes()==archived.read_bytes(),'unexpected prior owned observation; not reused or removed'
        shared.unlink()
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    outpath=run.private/(tag+'-serve.stdout');errpath=run.private/(tag+'-serve.stderr');child=None;primary=None
    record=dict(generation=tag,readiness_before=prior,readiness_allowance=remaining)
    run.report.setdefault('service_generations',[]).append(record)
    run.report['stage']=tag.upper()+'_INSTALLED_API_POSTGRES_START'
    with outpath.open('w') as out,errpath.open('w') as err:
        try:
            child=subprocess.Popen([str(run.python),'-I','-B',str(run.harness/'entry.py'),'serve',str(run.state),str(port),str(remaining),tag],cwd=run.harness,env=old.minimal_env(),stdout=out,stderr=err)
            deadline=min(run.started+270,time.monotonic()+30)
            while time.monotonic()<deadline:
                assert child.poll() is None,'installed server exited before readiness; original logs retained'
                lines=outpath.read_text().splitlines()
                if lines:
                    value=json.loads(lines[-1]);attempts=value['readiness_attempts'];assert 1<=attempts<=remaining
                    assert value['api_pid']!=child.pid and value['state_dir']==str(run.state) and value['url']==f'http://127.0.0.1:{port}'
                    run.budget.internal_reads=prior+attempts
                    run.report['origin']=value['url'];record['started']=value;break
                time.sleep(.1)
            else:raise TimeoutError('installed service readiness30s exhausted')
            with httpx.Client(base_url=run.report['origin'],timeout=15) as api:run.api=api;yield
        except BaseException as error:
            primary=error;record['primary_error']=dict(type=type(error).__name__,errno=getattr(error,'errno',None),message=str(error));raise
        finally:
            if child is not None:
                try:
                    if child.poll() is None:child.terminate()
                    child.wait(timeout=40);record['wrapper_exit']=child.returncode
                    path=run.harness/'owned-processes.json'
                    if not path.exists():
                        record['readiness_unconfirmed']=dict(confirmed_before=prior,unconfirmed_allowance=remaining)
                        raise AssertionError('new generation owned cleanup observation absent; no prior observation reused')
                    value=json.loads(path.read_text())
                    assert value['wrapper_pid']==child.pid and value['generation']==tag and value['state_dir']==str(run.state),'owned cleanup belongs to another generation'
                    if 'started' in record:
                        expected={('api',record['started']['api_pid']),('postgres',record['started']['postgres_pid'])}
                        assert {(x['role'],x['pid']) for x in value['children']}==expected,'owned cleanup child identities differ from this generation startup'
                    record['cleanup']=value
                    (run.private/(tag+'-owned-processes.json')).write_bytes(path.read_bytes())
                    attempts=value['readiness_attempts'];assert 0<=attempts<=remaining
                    run.budget.internal_reads=prior+attempts;record['readiness_cumulative']=run.budget.internal_reads
                    assert value['postgres_marker_absent'] and not value['cleanup_errors']
                    assert child.returncode==0 and 'primary_error' not in value and all(x['exit_code']==0 for x in value['children'])
                    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',port))==111
                    record['API_listener_refused_after_stop']=True
                except BaseException as error:
                    record['cleanup_error']=dict(type=type(error).__name__,errno=getattr(error,'errno',None),message=str(error))
                    if primary is not None:raise BaseExceptionGroup('Original installed runtime and cleanup failures',[primary,error]) from None
                    raise


def prepare_first(run):
    run.record=old.prepare(run,0,goals=GOALS);run.report['record']=run.record
    p=call(run,'/service-case-plan');assert p['required_goals']==GOALS;tail_pending(snapshot(run)['preparation']['service_case_plan'])
    step(run,'P1','LOCK');q,body=quote_body(run,run.record['holds']);item=api_approval(run,body)
    result=call(run,'/resource-delivery',{**body,'approval_id':item['id']},expected=201)
    step(run,'P2');run.old_delivery=result;run.old_approval=item
    initial=snapshot(run);tail_pending(initial['preparation']['service_case_plan']);run.report['initial_business_snapshot']=initial
    view=call(run,'/opportunities')
    imported=call(run,'/opportunities/commands',dict(action='IMPORT',expected_revision=view['revision'],expected_source_sha256=view['source_sha256'],reason='SYNTHETIC 人工导入待审来源提示',entry=dict(family_id=str(uuid4()),generation=1,kind='LOCAL_CASE_DATA',catalog_version=1,title='SYNTHETIC 资源来源变更待审',note='SYNTHETIC 仅提示，非批准或事实核验')))
    run.card=imported['current']['cards'][0]
    # One owned fixture source update. No new identity, grants, plan or ledger edit.
    target=old.api_call(run,'/api/synthetic-resources')['items'][0]
    assert target['id'] in {h['resource_id'] for h in initial['holds']}
    with owner(run) as c:
        row=c.execute('SELECT id,revision,capacity FROM synthetic_resources WHERE id=%s AND revision=%s FOR UPDATE',(target['id'],target['revision'])).fetchone()
        assert row is not None
        updated=c.execute('UPDATE synthetic_resources SET capacity=capacity+1,revision=revision+1 WHERE id=%s AND revision=%s RETURNING id,revision,capacity',(row['id'],row['revision'])).fetchone()
        assert updated and updated['capacity']==row['capacity']+1 and updated['revision']==row['revision']+1
    run.report['owned_source_fixture_SQL']=dict(scope='EXACT_EXISTING_SYNTHETIC_RESOURCE_CAS_NOT_PRODUCT_MAINTENANCE_API',statements=1,before={k:str(v) if k=='id' else v for k,v in row.items()},after={k:str(v) if k=='id' else v for k,v in updated.items()},authority_writes=False)
    view=call(run,'/opportunities')
    refreshed=call(run,'/opportunities/commands',dict(action='REFRESH',expected_revision=view['revision'],expected_source_sha256=view['source_sha256'],reason='SYNTHETIC 明确刷新当前来源'))
    run.card=refreshed['current']['cards'][0]


def new_holds(run):
    catalog=old.api_call(run,'/api/synthetic-resources')['items'];assert len(catalog)==2
    holds=[];now=datetime.now(timezone.utc)
    for n in range(3):
        r=catalog[n%2];start=now+timedelta(hours=18+n*3)
        value=old.api_call(run,'/api/synthetic-resources/'+r['id']+'/holds',dict(starts_at=start.isoformat(),ends_at=(start+timedelta(hours=1)).isoformat(),quantity=1,expected_revision=r['revision'],ttl_seconds=300,purpose='SYNTHETIC 来源变更后新占位'+str(n)),expected=201)['hold']
        holds.append(dict(hold_id=value['id'],expected_revision=value['resource_revision']))
    run.record['new_holds']=holds


def collect(run,complete=True):
    observations={p.stem:json.loads(p.read_text()) for p in sorted(run.harness.glob('*-attestation.json'))};run.report['process_installation_attestations']=observations
    if not complete:return
    assert set(observations)=={'setup-attestation','api-attestation','worker-0-attestation'}
    for role,items in observations.items():
        count=4 if role=='api-attestation' else 2;assert len(items)==count
        for n in range(0,count,2):
            assert items[n]['pid']==items[n+1]['pid'] and items[n]['stage'].startswith('BEFORE_') and items[n+1]['stage'].startswith('AFTER_')
        assert all(x['wheel_sha256']==run.report['installation']['wheel_sha256'] and x['verified_package_files']==191 and x['isolated'] and not x['PYTHONPATH'] for x in items)
    apis=observations['api-attestation'];assert apis[0]['pid']!=apis[2]['pid']
    generations=run.report['service_generations'];assert len(generations)==2
    assert generations[0]['started']['postgres_pid']!=generations[1]['started']['postgres_pid']
    assert all('web.html' in apis[n]['actual_opened_package_resources'] for n in (1,3))
    assert 'local-resource-approval-schema.sql' in observations['setup-attestation'][-1]['actual_opened_package_resources']
    assert run.report['installed_worker_exits']==[0]


def publish_logs(run):
    paths=[run.private/'current-package/build.log',run.private/'application/install.log',run.private/'setup.stdout',run.private/'setup.stderr']
    paths+=sorted(run.private.glob('*-serve.*'))+sorted(run.private.glob('worker-*.log'))
    if hasattr(run,'state'):paths.append(run.state/'logs/installed-api.log')
    parts=[];records=[];total=0
    for p in paths:
        if not p.is_file():continue
        raw=p.read_bytes();total+=len(raw);assert total<=2*1024*1024
        clean=raw
        for secret in run.secrets:
            for value in (secret.encode(),secret[:12].encode()):clean=clean.replace(value,b'[REDACTED_SYNTHETIC_SESSION]')
        parts.extend([('CAPTURED_COMPONENT '+p.name+'\n').encode(),clean,b'\n']);records.append(dict(file=p.name,original_sha256=sha256(raw).hexdigest(),original_bytes=len(raw),public_sha256=sha256(clean).hexdigest()))
    (run.public/'installation-redacted.log').write_bytes(b''.join(parts));run.report['captured_component_logs']=records


class Flow:
    def __init__(self,run,browser,*,cold=False):
        from playwright.sync_api import expect
        self.run=run;self.expect=expect;self.cold=cold
        self.context=browser.new_context(viewport=dict(width=390 if cold else 1200,height=1000),locale='zh-CN',service_workers='block')
        self.context.route('**/*',self.route)
        self.context.on('response',lambda r:run.report['responses'].append(dict(stage=run.report['stage'],transport='BROWSER',method=r.request.method,path=urlsplit(r.url).path,status=r.status)))
        self.page=self.context.new_page();self.page.set_default_timeout(15000)
        self.page.on('pageerror',lambda e:run.report['page_errors'].append(str(e)))
        self.page.add_init_script("window.__sourceClicks=[];document.addEventListener('click',e=>{const b=e.target.closest?.('button,input,summary');if(!b||!e.isTrusted)return;const r=b.getBoundingClientRect();if(window.__sourceClicks.length>=50)throw Error('trusted click50 exhausted');window.__sourceClicks.push({id:b.id,tag:b.tagName,x:r.x,y:r.y,width:r.width,height:r.height});},true)")
    def route(self,route):
        if self.cold and route.request.method not in ('GET','HEAD'):
            self.run.report['violations'].append(dict(stage='COLD_READ',method=route.request.method,path=urlsplit(route.request.url).path));route.abort();raise AssertionError('cold recovery attempted business POST')
        url=urlsplit(route.request.url)
        originals={'/api/preparations/'+self.run.record['preparation_id']+'/resource-link/recovery/'+value['delivery_binding']['request_key'] for value in (self.run.old_delivery,self.run.new_delivery)} if self.cold else set()
        if self.cold and route.request.method=='GET' and url.path in originals:
            origin=urlsplit(self.run.report['origin'])
            assert (url.scheme,url.netloc)==(origin.scheme,origin.netloc) and not url.query and not url.username and not url.password
            self.run.budget.count('GET',url.path,'BROWSER');route.continue_();return
        self.run.budget.route(route)
    def click(self,selector):
        old.require_work(self.run,30);b=self.page.locator(selector);b.scroll_into_view_if_needed(timeout=15000)
        self.expect(b).to_be_visible();self.expect(b).to_be_enabled();b.click()
    def idle(self):
        self.page.wait_for_load_state('networkidle',timeout=30000)
        self.page.wait_for_function('()=>!planApprovalBusy&&!deliveryBusy&&!bundleBusy&&!opportunityPlanBusy&&!servicePlanPending&&!activeEntryWriteFlow&&entryWriteRequests.size===0',timeout=30000)
    def post(self,selector,path,action=None,status=200):
        assert not self.cold;self.run.budget.authorize(path,action)
        with self.page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path==path,timeout=30000) as observed:self.click(selector)
        r=observed.value;assert r.status==status and self.run.budget.expected is None
        self.idle();value=r.json()
        if not path.endswith('/preview'):
            key=r.request.headers['idempotency-key']
            proof=value.get('command_receipt') or value.get('event') or value.get('receipt',{}).get('delivery_binding')
            assert proof and proof['request_key']==key
            self.run.report.setdefault('browser_POST_key_proofs',[]).append(dict(path=path,key=key,action=action,response_matches=True))
        return value
    def open(self):
        r=self.page.goto(self.run.report['origin'],wait_until='load')
        assert r.status==200 and sha256(r.body()).hexdigest()==self.run.report['installation']['package_files']['parkweave/web.html']
        assert "frame-ancestors 'none'" in r.headers['content-security-policy']
        assert self.page.evaluate('localStorage.length')==0,'new browser context must start without inherited recovery handles'
        self.page.locator('#token').fill(self.run.tokens['enterprise'])
    def existing(self):
        self.page.locator('#existing-preparation-id').fill(self.run.record['preparation_id']);self.click('#existing-preparation-read')
        self.page.wait_for_function('(id)=>preparationView?.preparation.id===id&&preparationReadReady()',arg=self.run.record['preparation_id'],timeout=30000)
    def shot(self,name,selector):
        assert name in SHOTS;target=self.page.locator(selector);target.scroll_into_view_if_needed(timeout=15000)
        geometry=self.page.evaluate('''() => ({width:innerWidth,documentWidth:document.documentElement.scrollWidth,navPosition:getComputedStyle(document.querySelector('.workspace-nav')).position,
            controls:[...document.querySelectorAll('button,input,summary')].filter(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden'&&r.width&&r.height&&r.bottom>0&&r.top<innerHeight}).map(e=>{const r=e.getBoundingClientRect();return {id:e.id,x:r.x,width:r.width}})})''')
        assert geometry['documentWidth']<=geometry['width'] and geometry['navPosition'] not in ('sticky','fixed')
        assert all(x['x']>=-1 and x['x']+x['width']<=geometry['width']+1 for x in geometry['controls'])
        p=self.run.public/name;self.page.screenshot(path=str(p),mask=[self.page.locator('#token')],timeout=10000)
        self.run.report['screenshots'].append(dict(file=name,sha256=sha256(p.read_bytes()).hexdigest(),geometry=geometry))
    def font(self,stage):
        from scripts.fictional_park_restart_browser_once import verify_rendered_font
        selected=self.run.report['installed_CJK_font'];selected['visible_node_font_usage']=[];selected['rendering_observed']=False
        entry=dict(stage=stage,complete=False,nodes=[],scope='Only actual visible text-node parents, not complete target-codepoint pixel acceptance')
        self.run.report.setdefault('font_observations',[]).append(entry)
        try:verify_rendered_font(self.page,self.run.report)
        finally:entry.update(complete=selected.get('rendering_observed') is True,nodes=deepcopy(selected.get('visible_node_font_usage',[])))
    def close(self,primary=None):
        errors=[]
        if primary is not None:
            p=self.run.public/'failure-source-restart.png'
            try:self.page.screenshot(path=str(p),mask=[self.page.locator('#token')],timeout=10000)
            except BaseException as e:self.run.report['failure_screenshot_error']=dict(type=type(e).__name__,message=str(e))
        try:self.run.report.setdefault('DOM_context_clicks',[]).append(dict(cold=self.cold,clicks=self.page.evaluate('window.__sourceClicks||[]')))
        except BaseException as e:
            errors.append(e);self.run.report.setdefault('context_telemetry_errors',[]).append(dict(type=type(e).__name__,message=str(e)))
        finally:
            try:self.context.close()
            except BaseException as e:
                errors.append(e);self.run.report.setdefault('context_close_errors',[]).append(dict(type=type(e).__name__,message=str(e)))
        if errors:
            if primary is not None:errors.insert(0,primary)
            if len(errors)==1:raise errors[0]
            raise BaseExceptionGroup('Browser body, telemetry and owned close failures',errors) from None


def source_browser(run,browser):
    flow=Flow(run,browser);primary=None;path='/api/preparations/'+run.record['preparation_id']
    try:
        run.report['stage']='SOURCE_CHANGE_UI_PREVIEW';flow.open();flow.existing();flow.click('#opp-read')
        flow.page.wait_for_function('()=>oppView?.cards.length===1&&!oppBusy',timeout=30000)
        # Establish the existing plan first so the actual reason draft survives preview.
        flow.click('#service-plan-prepare');flow.page.wait_for_function('()=>servicePlanView?.plan_id',timeout=30000)
        flow.page.locator('#service-plan-reason').fill('SYNTHETIC 本人核对实际资源来源变化，明确采纳同计划局部修订')
        flow.click('[data-opp-plan-preview="'+run.card['id']+'"]')
        flow.page.wait_for_function('()=>opportunityPlanView?.can_adopt===true&&!opportunityPlanBusy',timeout=30000)
        view=flow.page.evaluate('JSON.parse(JSON.stringify(opportunityPlanView,(k,v)=>k==="uiContext"?undefined:v))')
        assert view['source_impact']['schema']==2 and view['plan_id']==run.record['plan_id'] and not view['blocking_reasons']
        flow.shot('01-source-impact.png','#opp-plan-impact');flow.font('REAL_SOURCE_IMPACT_VIEW')
        flow.page.locator('#opp-plan-confirm').check()
        adopted=flow.post('#opp-plan-adopt',path+'/service-case-plan',status=201)
        assert adopted['plan_id']==run.record['plan_id'];tail_pending(snapshot(run)['preparation']['service_case_plan'])
        run.report['source_ADOPT_UI']=dict(preview=view,command_receipt=adopted['command_receipt'],plan_revision=adopted['revision'])
        flow.shot('02-source-adopted.png','#service-plan-summary')
        new_holds(run);flow.click('[data-tab="resource"]');flow.page.locator('#delivery-case').fill(run.record['preparation_id'])
        flow.click('#resource-catalog');flow.page.wait_for_function('()=>bundleActor!==null',timeout=30000)
        flow.click('#resource-mine');flow.page.wait_for_function('()=>bundleActor!==null&&!bundleBusy',timeout=30000)
        for h in run.record['new_holds']:flow.page.locator('[data-combination-hold="'+h['hold_id']+'"]').check()
        flow.page.locator('#delivery-reapproval').check()
        q=flow.post('#delivery-preview',path+'/resource-delivery/preview')
        assert q['expected_link_revision']==1 and q['context']['source_reapproval']['source_adoption_event_id']==adopted['command_receipt']['id']
        stale=flow.page.evaluate('approvalBaseDeliveryBody(deliveryContext(),deliveryQuote.view)')
        before=snapshot(run);run.report['stage']='STALE_APPROVAL_NEGATIVE_API'
        call(run,'/resource-delivery',{**stale,'approval_id':run.old_approval['id']},expected=409,phase='NEGATIVE_AND_REPEAT')
        assert snapshot(run)==before
        proposed=flow.post('#plan-approval-propose',path+'/plan-approval/proposals',status=201);item=proposed['items'][-1]
        assert item['purpose']=='CASE_RESOURCE_REAPPROVAL'
        approved=flow.post('#plan-approval-approve',path+'/plan-approval/commands','APPROVE')
        assert approved['items'][-1]['state']=='APPROVED';flow.shot('03-reapproval-approved.png','#plan-approval-panel')
        run.report['stage']='NEW_LOCAL_DELIVERY_DOM'
        result=flow.post('#delivery-confirm',path+'/resource-delivery',status=201);run.new_delivery=result
        assert result['link']['revision']==2 and result['receipt']['plan_approval']['id']==item['id']
        step(run,'P2');after=snapshot(run);tail_pending(after['preparation']['service_case_plan'])
        assert after['preparation']['service_case_plan']['id']==run.record['plan_id']
        assert after['preparation']['service_case_plan']['steps'][0]==run.report['initial_business_snapshot']['preparation']['service_case_plan']['steps'][0]
        assert len(after['links'])==2 and all(h['state']=='CONFIRMED' for h in after['holds'])
        original=run.report['original_delivery_request'];run.report['stage']='EXACT_NEW_ORIGINAL_POST_REPEAT_API'
        repeated=old.api_call(run,original['path'],original['body'],key=original['key'],expected=201,phase='NEGATIVE_AND_REPEAT')
        assert repeated['receipt']==result['receipt'] and snapshot(run)==after
        flow.click('[data-tab="service"]');flow.existing();flow.click('#service-plan-prepare');flow.page.wait_for_function('()=>servicePlanView?.plan_id',timeout=30000)
        run.report['sealed_hot_plan_UI']=flow.page.evaluate('(keys)=>Object.fromEntries(keys.map(k=>[k,servicePlanView[k]]))',list(PLAN_FIELDS))
        flow.click('[data-tab="resource"]');flow.page.locator('#delivery-case').fill(run.record['preparation_id'])
        flow.click('#plan-approval-read');flow.page.wait_for_function('()=>planApprovalView?.items.length===2&&planApprovalView.items.every(x=>x.state==="CONSUMED")',timeout=30000)
        flow.page.set_viewport_size(dict(width=390,height=1000));flow.shot('04-reapproval-consumed.png','#plan-approval-panel');flow.font('REAL_REAPPROVAL_CONSUMED_NARROW')
        run.report['before_restart_snapshot']=after
        run.report['receipts_before_restart']=[run.old_delivery['receipt'],result['receipt']]
        run.report['negative_checks']=dict(stale_old_approval_with_fresh_key_http=409,new_original_POST_repeat_same_receipt=True,no_additional_business_effect=True)
    except BaseException as e:primary=e;raise
    finally:flow.close(primary)


def cold_browser(run,browser):
    flow=Flow(run,browser,cold=True);primary=None;posts=run.budget.posts;path='/api/preparations/'+run.record['preparation_id']
    try:
        run.report['stage']='RESTARTED_NEW_CONTEXT_READ_ONLY';flow.open();flow.existing()
        flow.click('#case-resource-load');flow.page.wait_for_function('()=>caseResourceView?.link_revision===2',timeout=30000)
        for original in (run.old_delivery,run.new_delivery):
            key=original['delivery_binding']['request_key']
            flow.page.locator('#case-resource-recovery-kind').select_option('LINK');flow.page.locator('#case-resource-recovery-key').fill(key)
            flow.page.locator('#case-resource-recovery-fingerprint').fill('')
            recovery=path+'/resource-link/recovery/'+key
            with flow.page.expect_response(lambda r:r.request.method=='GET' and r.url.endswith(recovery),timeout=30000) as observed:flow.click('#case-resource-recovery-read')
            assert observed.value.status==200
            value=observed.value.json();assert value['status']=='COMMITTED' and value['record']['id']==original['link']['id'] and value['fingerprint']==original['delivery_binding']['fingerprint']
            target=flow.page.locator('#case-resource-recovery-result')
            flow.expect(target).to_be_visible();flow.expect(target).to_contain_text('COMMITTED')
            flow.expect(target).to_contain_text(original['link']['id']);flow.expect(target).to_contain_text(original['delivery_binding']['fingerprint'])
            DOM_text=target.inner_text()
            self_receipt=call(run,'/resource-delivery/recovery/'+key)
            assert self_receipt['receipt']==original['receipt']
            run.report.setdefault('cold_original_reads',[]).append(dict(key=key,UI_link_id=value['record']['id'],API_delivery_receipt_equal=True,DOM_text=DOM_text,scope='Existing original-key LINK UI plus exact delivery API GET, no synthetic storage handle'))
        flow.shot('06-restarted-original-link.png','#case-resource-recovery-result')
        flow.click('#service-plan-prepare');flow.page.wait_for_function('()=>servicePlanView?.plan_id',timeout=30000)
        restored_plan=flow.page.evaluate('(keys)=>Object.fromEntries(keys.map(k=>[k,servicePlanView[k]]))',list(PLAN_FIELDS))
        assert restored_plan==run.report['sealed_hot_plan_UI'],'cold UI plan projection differs from actual sealed hot UI'
        run.report['restored_cold_plan_UI']=restored_plan
        flow.click('[data-tab="resource"]');flow.page.locator('#delivery-case').fill(run.record['preparation_id'])
        flow.click('#plan-approval-read');flow.page.wait_for_function('()=>planApprovalView?.items.length===2',timeout=30000)
        assert flow.page.evaluate('planApprovalView.items.every(x=>x.state==="CONSUMED")')
        for item in flow.page.locator('#plan-approval-result .approval-audit').all():item.locator('summary').click()
        flow.shot('05-restarted-history.png','#plan-approval-panel');flow.font('RESTARTED_APPROVAL_HISTORY_NARROW')
        assert snapshot(run)==run.report['before_restart_snapshot'] and run.budget.posts==posts
        run.report['cold_recovery']=dict(new_context=True,inherited_localStorage=False,UI_original_LINK_reads=2,API_original_delivery_GETs=2,business_POSTs=0,projection_equal=True,deadline_or_validity_renewed=False,setup_or_seed_repeated=False)
    except BaseException as e:primary=e;raise
    finally:flow.close(primary)


def api_source_continuation(run):
    """Local installed integration preflight only; not a browser substitute."""
    phase='INSTALLED_API_PREFLIGHT'
    view=call(run,'/opportunities/'+run.card['id']+'/plan-revision');run.report['API_source_preview']=view
    assert view['can_adopt'] and view['source_impact']['schema']==2,view['blocking_reasons']
    adopted=call(run,'/service-case-plan',view['adoption'],expected=201,phase=phase)
    tail_pending(snapshot(run)['preparation']['service_case_plan']);new_holds(run)
    q,data=quote_body(run,run.record['new_holds'],1,phase=phase)
    before=snapshot(run)
    call(run,'/resource-delivery',{**data,'approval_id':run.old_approval['id']},expected=409,phase='NEGATIVE_AND_REPEAT');assert snapshot(run)==before
    item=api_approval(run,data,phase=phase);key=uuid4().hex;command={**data,'approval_id':item['id']}
    run.new_delivery=call(run,'/resource-delivery',command,key=key,expected=201,phase=phase)
    assert q['context']['source_reapproval']['source_adoption_event_id']==adopted['command_receipt']['id']
    step(run,'P2');current=snapshot(run);tail_pending(current['preparation']['service_case_plan'])
    assert current['preparation']['service_case_plan']['steps'][0]==run.report['initial_business_snapshot']['preparation']['service_case_plan']['steps'][0]
    repeated=call(run,'/resource-delivery',command,key=key,expected=201,phase='NEGATIVE_AND_REPEAT')
    assert repeated['receipt']==run.new_delivery['receipt'] and snapshot(run)==current
    run.report['before_restart_snapshot']=current
    run.report['receipts_before_restart']=[run.old_delivery['receipt'],run.new_delivery['receipt']]


def cold_gate(run):
    """After first confirmed stop: <=150 leaves120 work +90 final time."""
    old.require_work(run,120)
    assert time.monotonic()<=run.started+150,'cold start requires30s start+90s reads within270s work; no shortened waits'
    assert run.report['service_generations'][-1]['API_listener_refused_after_stop']
    run.report['cold_stage_admission']=dict(elapsed=round(time.monotonic()-run.started,3),start_allowance=30,read_allowance=90,absolute_tail_reserve=90,work_deadline_seconds=270,final_deadline_seconds=360)


def cold_api_check(run):
    before=run.budget.posts
    for result in (run.old_delivery,run.new_delivery):
        value=call(run,'/resource-delivery/recovery/'+result['delivery_binding']['request_key'])
        assert value['receipt']==result['receipt']
    assert snapshot(run)==run.report['before_restart_snapshot'] and run.budget.posts==before


def preflight(directory):
    """Explicit local-only API/restart preflight; never invokes hosted/font/browser."""
    directory=Path(directory);directory.mkdir(mode=0o700,exist_ok=False)
    report=dict(status='NOT_RUN',stage='LOCAL_INSTALLED_PREFLIGHT',scope='LOCAL_API_PREFLIGHT_NOT_BROWSER',responses=[],screenshots=[],violations=[],page_errors=[],real_model_calls=0)
    report['source_sha']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=base.ROOT,text=True).strip()
    run=SimpleNamespace(started=time.monotonic(),report=report,secrets=[],private=directory,public=directory/'public');run.public.mkdir();run.budget=old.Budget(report)
    primary=None
    try:
        old.installation(run,old.current_wheel(run))
        with server(run,'first'):prepare_first(run);api_source_continuation(run)
        cold_gate(run)
        with server(run,'restarted'):cold_api_check(run)
        # No HTML open in API-only preflight, so use explicit role/provenance checks.
        collect(run,complete=False);observations=report['process_installation_attestations']
        assert set(observations)=={'setup-attestation','api-attestation','worker-0-attestation'}
        assert [len(observations[k]) for k in ('setup-attestation','api-attestation','worker-0-attestation')]==[2,4,2]
        assert observations['api-attestation'][0]['pid']!=observations['api-attestation'][2]['pid']
        report['status']='PASS_API_RESTART_PREFLIGHT_NOT_BROWSER'
    except BaseException as e:primary=e;report.update(status='FAIL',error_type=type(e).__name__,error=str(e));raise
    finally:
        report['seconds_through_local_finally']=round(time.monotonic()-run.started,3)
        try:
            if hasattr(run,'harness'):collect(run,complete=False)
            publish_logs(run)
            (directory/'preflight-result.json').write_text(base.resource.redact(report,run.secrets)+'\n')
        except BaseException as e:
            if primary is not None:raise BaseExceptionGroup('Preflight primary and preservation failures',[primary,e]) from None
            raise
    return report


def main():
    os.umask(0o077);started=time.monotonic()
    report=dict(status='NOT_RUN',stage='HOST_GATE',scope='INSTALLED_LOCAL_SOURCE_REAPPROVAL_TRUE_RESTART_BROWSER',responses=[],screenshots=[],violations=[],page_errors=[],real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False)
    run=SimpleNamespace(started=started,report=report,secrets=[],public=None);run.budget=old.Budget(report)
    try:
        report['source_sha']=base.require_hosted(os.environ,run_number='16')
        run.private=Path(tempfile.mkdtemp(prefix='parkweave-installed-source-restart-'))
        run.public=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';run.public.mkdir(mode=0o700,exist_ok=False)
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
                with server(run,'first'):prepare_first(run);source_browser(run,browser)
                cold_gate(run)
                with server(run,'restarted'):
                    cold_browser(run,browser);cold_api_check(run)
                collect(run)
        assert not report['violations'] and not report['page_errors'];old.require_work(run)
        assert run.budget.posts==32 and run.budget.phase_posts==dict(API_PREPARATION=25,BROWSER=5,NEGATIVE_AND_REPEAT=2)
        report['work_completion_seconds']=round(time.monotonic()-started,3);report['status']='PASS';report['stage']='INSTALLED_SOURCE_REAPPROVAL_TRUE_RESTART_COMPLETE'
    except BaseException as e:report.update(status='FAIL',error_type=type(e).__name__,error=str(e))
    finally:
        if hasattr(run,'harness'):
            try:collect(run,complete=False)
            except BaseException as e:base.finalization_failure(report,e)
        if run.public is not None:
            try:publish_logs(run)
            except BaseException as e:base.finalization_failure(report,e)
    return base.finish_report(report,run.secrets,run.public,started=started,allowed_names=PUBLIC_FILES)


if __name__=='__main__':raise SystemExit(main())
