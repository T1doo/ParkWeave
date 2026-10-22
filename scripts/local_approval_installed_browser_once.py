"""Exact bounded hosted installed-wheel LOCAL approval browser candidate."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json,os,re,shutil,socket,subprocess,sys,tempfile,time
from pathlib import Path
from urllib.parse import urlsplit
import httpx,psycopg
from psycopg.rows import dict_row
from psycopg.conninfo import make_conninfo
from scripts import fictional_park_browser_once as base
from scripts import installed_wheel_support as installed

PRIVATE=base.ROOT/'.runtime/installed-approval-browser-once'
WHEEL_NAME='parkweave-0.1.0-py3-none-any.whl'
NAMES=frozenset(('01-local-proposed.png','02-local-approved.png','03-local-committed-pending.png',
    '04-local-consumed-recovered.png','05-local-revoked.png','06-local-read-denied.png','07-guide-narrow.png'))
PUBLIC_FILES=NAMES|{'result.json','installation-redacted.log',WHEEL_NAME}
GOALS=['LOCAL_MATERIAL_PREPARATION','LOCAL_CASE_RESOURCE_ASSOCIATION','LOCAL_INTERNAL_ACCEPTANCE',
    'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT','LOCAL_CASE_RECORD_RECHECK']


def require_work(run,reserve=0):
    assert time.monotonic()+reserve<=run.started+270,'270s work reservation exhausted;cleanup/publication retained'


class Budget:
    """One cumulative ledger shared by API preparation, browser and negative checks."""
    def __init__(self,report):
        self.report=report;self.reads=0;self.internal_reads=0;self.posts=0;self.phase_posts={};self.expected=None;self.keys={}
    def count(self,method,path,phase):
        assert path.startswith('/') and '?' not in path
        if method in ('GET','HEAD'):
            assert self.reads<360,'main GET/HEAD360 plus readiness40 exhausted';self.reads+=1
        else:
            assert method=='POST' and self.posts<40,'cumulative POST40 exhausted';self.posts+=1
            self.phase_posts[phase]=self.phase_posts.get(phase,0)+1
            limit={'API_PREPARATION':26,'BROWSER':8,'NEGATIVE_AND_REPEAT':3,'INSTALLED_API_PREFLIGHT':8}[phase]
            assert self.phase_posts[phase]<=limit,'phase POST ceiling exhausted'
        self.report['request_budget']=dict(GET_HEAD=self.reads+self.internal_reads,main_GET_HEAD=self.reads,readiness_attempts=self.internal_reads,POST=self.posts,phase_POST=self.phase_posts.copy(),
            ceilings=dict(GET_HEAD=400,main_GET_HEAD=360,readiness_attempts=40,POST=40,API_PREPARATION_POST=26,BROWSER_POST=8,NEGATIVE_REPEAT_POST=3),
            worker_once_ceiling=2,owner_negative_SQL_ceiling=1)
    def authorize(self,path,action=None):
        assert self.expected is None;self.expected=(path,action)
    def route(self,route):
        request=route.request;url=urlsplit(request.url);origin=urlsplit(self.report['origin'])
        try:
            assert (url.scheme,url.netloc)==(origin.scheme,origin.netloc) and not url.username and not url.password
            assert not url.query and (url.path in ('/','/demo','/favicon.ico') or url.path.startswith('/api/'))
            if request.method=='POST':
                assert self.expected is not None and url.path==self.expected[0]
                if self.expected[1] is not None:assert request.post_data_json['action']==self.expected[1]
                key=request.headers.get('idempotency-key')
                if url.path.endswith('/resource-delivery/preview'):
                    assert key is None,'preview must not masquerade as keyed business write'
                else:
                    assert isinstance(key,str) and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',key)
                    assert key not in self.keys,'UI reused an original key across actions or Cases'
                    self.keys[key]=dict(path=url.path,action=self.expected[1])
                    self.report.setdefault('browser_original_keys',[]).append(dict(key=key,**self.keys[key]))
                self.expected=None
            elif request.method=='GET' and '/recovery/' in url.path:
                prefix,key=url.path.rsplit('/recovery/',1);assert key in self.keys
                original=self.keys[key]['path']
                assert original==prefix or original in (prefix+'/proposals',prefix+'/commands'),'recovery belongs to another original action/Case'
            self.count(request.method,url.path,'BROWSER')
            if request.method=='POST' and url.path.endswith('/resource-delivery'):
                self.report['original_delivery_request']=dict(path=url.path,key=request.headers['idempotency-key'],body=request.post_data_json)
            if (self.report.get('interrupt_recovery') and request.method=='GET' and '/resource-delivery/recovery/' in url.path):
                self.report['interrupt_recovery']=False
                response=route.fetch();assert response.status==200
                self.report['interrupted_original_recovery']=dict(path=url.path,status=200,receipt_sha256=sha256(response.body()).hexdigest(),
                    scope='One actual GET response deliberately interrupted before UI;no POST retry')
                route.abort('failed');return
            route.continue_()
        except BaseException as error:
            self.report['violations'].append(dict(method=request.method,path=url.path,error_type=type(error).__name__))
            route.abort();raise


def minimal_env():return dict(PATH='/usr/local/bin:/usr/bin:/bin',LANG='C.UTF-8',PYTHONDONTWRITEBYTECODE='1')


@contextmanager
def server(run):
    run.report['stage']='INSTALLED_API_POSTGRES_START'
    env=minimal_env();p=run.private/'serve.stdout';err=run.private/'serve.stderr';child=None
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    primary=None
    with p.open('w') as out,err.open('w') as stderr:
        try:
            child=subprocess.Popen([str(run.python),'-I','-B',str(run.harness/'entry.py'),'serve',str(run.state),str(port)],cwd=run.harness,env=env,stdout=out,stderr=stderr)
            deadline=min(run.started+270,time.monotonic()+30)
            while time.monotonic()<deadline:
                assert child.poll() is None,'installed server exited;private logs retained'
                rows=p.read_text().splitlines()
                if rows:
                    value=json.loads(rows[-1]);assert value['api_pid']!=child.pid
                    run.report.update(origin=value['url'],owned_services=value)
                    assert 1<=value['readiness_attempts']<=40;run.budget.internal_reads=value['readiness_attempts'];break
                time.sleep(.1)
            else:raise TimeoutError('installed service readiness30s exhausted')
            with httpx.Client(base_url=run.report['origin'],timeout=15) as api:
                run.api=api;yield
        except BaseException as error:
            primary=error
            raise
        finally:
            if child is not None:
                try:
                    if child.poll() is None:child.terminate()
                    child.wait(timeout=40)
                    run.report['server_wrapper_exit']=child.returncode
                    observation=json.loads((run.harness/'owned-processes.json').read_text())
                    run.report['owned_cleanup']=observation
                    assert observation['postgres_marker_absent'] and not observation['cleanup_errors'] and all(x['exit_code'] is not None for x in observation['children'])
                    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',port))==111
                    run.report['owned_API_listener_refused_after_stop']=True
                    assert child.returncode==0 and 'primary_error' not in observation,'owned service failed;cleanup confirmation is not runtime success'
                    assert all(x['exit_code']==0 for x in observation['children']),'owned child abnormal exit;stopped is not runtime success'
                except BaseException as cleanup:
                    run.report['server_cleanup_error']=dict(error_type=type(cleanup).__name__,error=str(cleanup))
                    if primary is not None:raise BaseExceptionGroup('Installed server primary and cleanup failures',[primary,cleanup]) from None
                    raise


def api_call(run,path,body=None,*,actor='enterprise',expected=200,key=None,phase='API_PREPARATION'):
    require_work(run,30);method='GET' if body is None else 'POST';run.budget.count(method,path,phase)
    headers={'Authorization':'Bearer '+run.tokens[actor]}
    if body is not None:headers['Idempotency-Key']=key or __import__('uuid').uuid4().hex
    response=run.api.request(method,path,headers=headers,json=body)
    run.report['responses'].append(dict(stage=run.report['stage'],transport='API',method=method,path=path,status=response.status_code))
    assert response.status_code==expected,(method,path,response.status_code)
    return response.json()


def worker_once(run,index):
    require_work(run,35)
    env=json.loads((run.harness/'application-env.json').read_text());assert 'PYTHONPATH' not in env
    with (run.private/f'worker-{index}.log').open('w') as log:
        result=subprocess.run([str(run.python),'-I','-B',str(run.harness/'entry.py'),'worker',f'worker-{index}'],cwd=run.harness,env=env,stdout=log,stderr=log,timeout=30)
    assert result.returncode==0,'installed worker failed;private output retained'
    run.report.setdefault('installed_worker_exits',[]).append(result.returncode)
    assert len(run.report['installed_worker_exits'])<=2


def prepare(run,index,*,goals=GOALS):
    run.report['stage']='API_PREPARATION_'+str(index)
    label=f'SYNTHETIC 安装包本地批准事项{index}'
    created=api_call(run,'/api/runs',dict(goal=label),expected=202);worker_once(run,index)
    row=api_call(run,'/api/runs/'+created['run_id']);assert row['state']=='SUCCEEDED'
    p=api_call(run,'/api/preparations',dict(run_id=created['run_id'],service_id='synthetic-material-preparation',service_version=1,reviewer_id='ordinary-demo-specialist'),expected=201)
    path='/api/preparations/'+p['preparation_id']
    p=api_call(run,path+'/request-intent',dict(expected_preparation_revision=p['revision'],request_text=label+' 独立新诉求；全部虚构',required_goals=goals))
    for slot in ('need_summary','material_outline'):
        p=api_call(run,path+'/commands',dict(action='ADD_EVIDENCE',expected_revision=p['revision'],slot=slot,text=label+' '+slot,source_kind='USER_STATEMENT',source_label='SYNTHETIC 安装包初态'))
    for actor,action in (('specialist','REVIEW'),('enterprise','CONFIRM')):
        p=api_call(run,path+'/commands',dict(action=action,expected_revision=p['revision'],reason='SYNTHETIC 原身份明确'+action),actor=actor)
    capabilities=api_call(run,path+'/service-capabilities')
    selected=api_call(run,path+'/service-selections',dict(expected_preparation_revision=p['revision'],expected_source_sha256=capabilities['source_sha256'],expected_capability_catalog_sha256=capabilities['capability_catalog_sha256']),expected=201)
    assert selected['producer']['mode']=='NO_MODEL' and selected['producer']['real_model_calls']==0
    assert selected['validator_version']=='LOCAL_SYNTHETIC_DEMO_V2' and selected['producer']['schema_version']=='local-synthetic-demo-producer/2'
    plan=api_call(run,path+'/service-case-plan',dict(expected_preparation_revision=p['revision'],expected_request_revision=capabilities['request_revision'],expected_plan_revision=0,expected_source_sha256=capabilities['source_sha256'],required_goals=goals,reason='SYNTHETIC 原NO_MODEL方案明确ADOPT',candidate_id=selected['candidate_id'],expected_candidate_sha256=selected['candidate_sha256'],expected_verification_sha256=selected['verification_sha256']),expected=201)
    seal=plan['candidate_consumption']['difference_observation']
    assert seal is not None and seal['scope']=='LOCAL_DIFFERENCE_OBSERVATION_BASELINE'
    assert seal['candidate_id']==selected['candidate_id'] and seal['plan_id']==plan['plan_id']
    assert [(s['adapter_id'],s['step_id']) for s in seal['steps']]==[(s['adapter_id'],s['id']) for s in plan['steps']]
    run.report.setdefault('API_initial_candidate_proofs',[]).append(dict(candidate_id=selected['candidate_id'],validator=selected['validator_version'],producer=selected['producer']['schema_version'],plan_id=plan['plan_id'],baseline_sha256=seal['baseline_sha256'],initial_ADOPT_API_not_DOM=True))
    step=next(s for s in plan['steps'] if s['adapter_id']=='P1')
    plan=api_call(run,path+'/service-case-plan/commands',dict(action='VERIFY',step_id=step['id'],expected_revision=plan['revision'],expected_source_sha256=step['source_sha256'],reason='SYNTHETIC 原P1明确核验'))
    assert next(s for s in plan['steps'] if s['adapter_id']=='P1')['state']=='VERIFIED'
    catalog=api_call(run,'/api/synthetic-resources')['items'];assert len(catalog)==2
    resources=[r['id'] for r in catalog];now=datetime.now(timezone.utc);holds=[]
    for i in range(3):
        start=now+timedelta(hours=1+index*12+i*3)
        hold=api_call(run,'/api/synthetic-resources/'+resources[i%2]+'/holds',dict(starts_at=start.isoformat(),ends_at=(start+timedelta(hours=1)).isoformat(),quantity=1,expected_revision=1,ttl_seconds=300,purpose=label+' 时段'+str(i)),expected=201)['hold']
        holds.append(dict(hold_id=hold['id'],expected_revision=hold['resource_revision']))
    return dict(preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=p['run_id'],plan_id=plan['plan_id'],holds=holds)


def business_snapshot(run):
    dsn=make_conninfo(host=str(run.state/'socket'),port=5432,user='postgres',dbname='parkweave',connect_timeout=2)
    with psycopg.connect(dsn,row_factory=dict_row) as c:
        c.execute('SET TRANSACTION READ ONLY')
        ledgers=c.execute('SELECT id,case_id,run_id,local_resource_approvals,local_resource_approval_head FROM preparations ORDER BY id').fetchall()
        holds=c.execute('SELECT h.id,h.state,m.combination_id FROM synthetic_resource_holds h LEFT JOIN synthetic_resource_combination_members m ON m.hold_id=h.id ORDER BY h.id').fetchall()
        counts={name:c.execute('SELECT count(*) n FROM '+name).fetchone()['n'] for name in ('synthetic_resource_combinations','synthetic_resource_combination_members','synthetic_resource_combination_receipts','resource_case_claims','case_resource_links')}
    raw=json.dumps(dict(ledgers=ledgers,holds=holds,counts=counts),sort_keys=True,default=str)
    return dict(sha256=sha256(raw.encode()).hexdigest(),counts=counts,
        local_states={str(r['id']):[e['action'] for e in (r['local_resource_approvals'] or {}).get('events',[])] for r in ledgers},
        holds=[dict(id=str(h['id']),state=h['state'],combination_id=str(h['combination_id']) if h['combination_id'] else None) for h in holds])


def current_wheel(run):
    from importlib.metadata import version
    require_work(run,120)
    run.report['stage']='OFFLINE_BUILD_CURRENT_CHECKOUT'
    assert version('setuptools')=='80.9.0','original pinned build tool required'
    wheel=installed.build(run.private/'current-package')
    assert wheel.name==WHEEL_NAME
    metadata=dict(package_source_sha=run.report['source_sha'],file=wheel.name,bytes=wheel.stat().st_size,
        sha256=sha256(wheel.read_bytes()).hexdigest(),build='setuptools80.9.0/no-index/no-deps/no-build-isolation',
        dependency_downloads_during_wheel_build_and_install=0)
    wheel.with_name('package-source.json').write_text(json.dumps(metadata,indent=2)+'\n')
    run.report['current_checkout_build']=metadata
    return wheel


def installation(run,wheel):
    run.report['stage']='OFFLINE_INSTALLED_WHEEL'
    run.python,run.harness,manifest=installed.install(wheel,run.private/'application')
    run.report['installation']=manifest
    require_work(run,90)
    setup_owned(run)
    run.state=Path(json.loads((run.private/'setup.stdout').read_text().splitlines()[-1])['state_dir'])
    sessions=json.loads((run.state/'sessions.json').read_text());run.tokens={name:sessions[name] for name in ('enterprise','specialist','executor')}
    run.secrets.extend(sessions.values())
    (run.public/wheel.name).write_bytes(wheel.read_bytes())


def setup_owned(run):
    """TERM only our exact setup process; allow its PG context to stop normally."""
    primary=None;child=None
    with (run.private/'setup.stdout').open('w') as out,(run.private/'setup.stderr').open('w') as err:
        try:
            child=subprocess.Popen([str(run.python),'-I','-B',str(run.harness/'entry.py'),'setup'],cwd=run.harness,env=minimal_env(),stdout=out,stderr=err)
            run.report['setup_pid']=child.pid
            try:child.wait(timeout=45)
            except subprocess.TimeoutExpired as error:
                primary=error
                child.terminate()
                try:child.wait(timeout=20)
                except subprocess.TimeoutExpired as cleanup:
                    run.report['setup_stop_status']='STOP_UNCONFIRMED'
                    raise BaseExceptionGroup('Installed setup timeout and stop unconfirmed',[primary,cleanup]) from None
            observation=json.loads((run.harness/'setup-owned-processes.json').read_text())
            run.report['setup_owned_cleanup']=observation
            if observation.get('state_dir'):run.state=Path(observation['state_dir'])
            assert observation['postgres_marker_absent'] and not observation['cleanup_errors'] and all(x['exit_code'] is not None for x in observation['children']),'owned setup PG stop not confirmed'
            run.report['setup_stop_status']='CONFIRMED'
            if primary is not None:raise primary
            assert child.returncode==0 and 'primary_error' not in observation,'installed setup failed;private originals retained'
        except BaseException as error:
            if primary is not None and error is not primary and not isinstance(error,BaseExceptionGroup):
                raise BaseExceptionGroup('Installed setup primary and cleanup errors',[primary,error]) from None
            raise


def collect_installation(run,*,complete=True):
    run.report['process_installation_attestations']={p.stem:json.loads(p.read_text()) for p in sorted(run.harness.glob('*-attestation.json'))}
    if not complete:return
    assert set(run.report['process_installation_attestations'])=={'setup-attestation','api-attestation','worker-0-attestation','worker-1-attestation'}
    assert 'local-resource-approval-schema.sql' in run.report['process_installation_attestations']['setup-attestation'][-1]['actual_opened_package_resources']
    assert 'web.html' in run.report['process_installation_attestations']['api-attestation'][-1]['actual_opened_package_resources']
    for role,items in run.report['process_installation_attestations'].items():
        assert len(items)==2 and items[0]['pid']==items[-1]['pid']
        assert all(x['wheel_sha256']==run.report['installation']['wheel_sha256'] for x in items)


def preflight(wheel,private):
    """Local installed API proof only; never labelled browser acceptance."""
    from types import SimpleNamespace
    private.mkdir(mode=0o700);public=private/'public';public.mkdir()
    report=dict(status='NOT_RUN',stage='INSTALL',responses=[],violations=[],scope='INSTALLED_API_ONLY_NOT_BROWSER')
    run=SimpleNamespace(started=time.monotonic(),private=private,public=public,report=report,secrets=[])
    run.budget=Budget(report)
    try:
        installation(run,wheel)
        with server(run):
            run.budget.count('GET','/','INSTALLED_API_PREFLIGHT');response=run.api.get('/')
            assert response.status_code==200 and sha256(response.content).hexdigest()==run.report['installation']['package_files']['parkweave/web.html']
            records=[prepare(run,i) for i in range(2)];report['records']=records
            report['stage']='INSTALLED_API_APPROVAL_PREFLIGHT'
            p=records[0];path='/api/preparations/'+p['preparation_id']
            q=api_call(run,path+'/resource-delivery/preview',dict(members=p['holds']),phase='INSTALLED_API_PREFLIGHT')
            data=dict(members=p['holds'],expected_preparation_revision=q['expected_preparation_revision'],expected_plan_revision=q['expected_plan_revision'],expected_source_sha256=q['source_sha256'],valid_until=q['valid_until'],reason='SYNTHETIC 安装态API预检')
            x=api_call(run,path+'/plan-approval/proposals',dict(expected_revision=0,delivery=data),expected=201,phase='INSTALLED_API_PREFLIGHT');item=x['items'][0]
            x=api_call(run,path+'/plan-approval/commands',dict(action='APPROVE',approval_id=item['id'],expected_revision=x['revision'],expected_binding_sha256=item['binding_sha256'],reason='SYNTHETIC 原owner明确批准'),phase='INSTALLED_API_PREFLIGHT')
            result=api_call(run,path+'/resource-delivery',{**data,'approval_id':item['id']},expected=201,phase='INSTALLED_API_PREFLIGHT')
            assert result['receipt']['plan_approval']['id']==item['id'] and result['independent_check']['status']=='CURRENT'
            report['business_snapshot']=business_snapshot(run)
        collect_installation(run);report['status']='PASS_API_ONLY_NOT_BROWSER'
    except BaseException as error:report.update(status='FAIL',error_type=type(error).__name__,error=str(error));raise
    finally:
        if hasattr(run,'harness'):
            try:collect_installation(run,complete=False)
            except BaseException as error:base.finalization_failure(report,error)
        (private/'preflight-result.json').write_text(base.resource.redact(report,run.secrets)+'\n')
    return report


def close_guide(run,guide,primary):
    try:guide.close()
    except BaseException as cleanup:
        run.report['guide_close_error']=dict(error_type=type(cleanup).__name__,error=str(cleanup))
        if primary is not None:
            raise BaseExceptionGroup('Guide body and owned close failures',[primary,cleanup]) from None
        raise


def browser_walk(run,browser):
    from playwright.sync_api import expect
    from scripts.fictional_park_restart_browser_once import verify_rendered_font
    report=run.report;records=report['records'];context=browser.new_context(viewport=dict(width=1200,height=1000),service_workers='block')
    context.add_init_script("""window.__installedApprovalClicks=[];document.addEventListener('click',e=>{const t=e.target.closest?.('button,input,a');if(!t||!e.isTrusted)return;const r=t.getBoundingClientRect();if(window.__installedApprovalClicks.length>=50)throw Error('click evidence50 exhausted');window.__installedApprovalClicks.push({id:t.id,tag:t.tagName,trusted:e.isTrusted,x:r.x,y:r.y,width:r.width,height:r.height});},true);""")
    context.route('**/*',run.budget.route)
    context.on('response',lambda response:report['responses'].append(dict(stage=report['stage'],transport='BROWSER',method=response.request.method,path=urlsplit(response.url).path,status=response.status)))
    page=context.new_page();page.set_default_timeout(15000);page.on('pageerror',lambda error:report['page_errors'].append(str(error)))
    click_offset=0;report['DOM_clicks']=[];guide_written=False
    def harvest():
        nonlocal click_offset
        items=page.evaluate('window.__installedApprovalClicks||[]');report['DOM_clicks'].extend(items[click_offset:]);click_offset=len(items)
        assert len(report['DOM_clicks'])<=50 and all(x['trusted'] for x in report['DOM_clicks'])
    def click(selector):
        require_work(run,30);button=page.locator(selector);button.scroll_into_view_if_needed(timeout=15000)
        expect(button).to_be_visible();expect(button).to_be_enabled();button.click()
    def idle():
        page.wait_for_load_state('networkidle',timeout=30000)
        page.wait_for_function('()=>!planApprovalBusy&&!deliveryBusy&&!bundleBusy&&!activeEntryWriteFlow&&entryWriteRequests.size===0',timeout=30000)
    def post(selector,path,action=None,status=200):
        run.budget.authorize(path,action)
        with page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path==path,timeout=30000) as result:click(selector)
        assert result.value.status==status and run.budget.expected is None
        idle();value=result.value.json()
        if not path.endswith('/resource-delivery/preview'):
            key=next(reversed(run.budget.keys));assert run.budget.keys[key]==dict(path=path,action=action)
            if '/plan-approval/' in path:
                assert value['event']['request_key']==key and value['event']['action']==(action or 'PROPOSE')
            else:assert value['receipt']['delivery_binding']['request_key']==key
            report.setdefault('browser_POST_key_proofs',[]).append(dict(path=path,action=action or ('PROPOSE' if '/plan-approval/' in path else 'DELIVERY'),original_key=key,response_matches=True))
        return value
    def shot(name,selector):
        assert name in NAMES;page.locator(selector).scroll_into_view_if_needed(timeout=15000)
        path=run.public/name;page.screenshot(path=str(path),mask=[page.locator('#token')],timeout=10000)
        report['screenshots'].append(dict(file=name,sha256=sha256(path.read_bytes()).hexdigest()))
    def open_page(parent,select_holds=True):
        nonlocal click_offset
        harvest() if page.url!='about:blank' else None
        response=page.goto(report['origin'],wait_until='load');click_offset=0
        assert response.status==200 and sha256(response.body()).hexdigest()==report['installation']['package_files']['parkweave/web.html']
        assert "frame-ancestors 'none'" in response.headers['content-security-policy']
        page.locator('#token').fill(run.tokens['enterprise']);click('[data-tab="resource"]')
        page.locator('#delivery-case').fill(parent['preparation_id'])
        if select_holds:
            click('#resource-catalog');page.wait_for_function('()=>bundleActor!==null',timeout=30000)
            click('#resource-mine');page.wait_for_function('()=>bundleActor!==null&&!bundleBusy',timeout=30000)
            for hold in parent['holds']:page.locator('[data-combination-hold="'+hold['hold_id']+'"]').check()
            assert page.evaluate('combinationSelection.size')==3
    def font_observation(label,target=None):
        entry=dict(stage=label,nodes=[],scope='Visible text-node parents in this named viewport; CDP participating font union, not complete UI glyph/pixel acceptance',complete=False);report.setdefault('font_observations',[]).append(entry)
        selected=report['installed_CJK_font'];selected['visible_node_font_usage']=[];selected['rendering_observed']=False
        try:verify_rendered_font(page if target is None else target,report)
        finally:
            entry['nodes']=deepcopy(selected.get('visible_node_font_usage',[]));entry['complete']=selected.get('rendering_observed') is True
    def geometry(label,target=None):
        target=page if target is None else target
        value=target.evaluate('''() => ({width:innerWidth,height:innerHeight,documentWidth:document.documentElement.scrollWidth,
          controls:[...document.querySelectorAll('button,input,select')].filter(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return s.visibility==='visible'&&s.display!=='none'&&r.width&&r.height&&r.bottom>0&&r.top<innerHeight;}).map(e=>{const r=e.getBoundingClientRect();return {id:e.id,disabled:e.disabled,x:r.x,y:r.y,width:r.width,height:r.height};})})''')
        assert value['documentWidth']<=value['width'],'current styled page horizontally overflows viewport'
        assert all(c['x']>=-1 and c['x']+c['width']<=value['width']+1 for c in value['controls']),'visible control lies outside viewport'
        report.setdefault('viewport_geometry',[]).append(dict(stage=label,**value))
    def enter(parent):
        open_page(parent);base_path='/api/preparations/'+parent['preparation_id']
        quote=post('#delivery-preview',base_path+'/resource-delivery/preview')
        assert quote['synthetic_plan_approval_required'] is True and quote['context']['case_id']==parent['case_id']
        proposal=post('#plan-approval-propose',base_path+'/plan-approval/proposals',status=201)
        assert proposal['scope']=='LOCAL_CASE_RESOURCE_APPROVAL_V1' and proposal['items'][-1]['state']=='PROPOSED'
        assert proposal['case_id']==parent['case_id'] and proposal['run_id']==parent['run_id']
        return base_path,proposal
    try:
        report['stage']='FIRST_LOCAL_PROPOSAL_DOM'
        first_path,proposed=enter(records[0]);first_item=proposed['items'][-1]
        geometry('PROPOSED_DESKTOP');shot('01-local-proposed.png','#plan-approval-result');font_observation('ACTUAL_LOCAL_PROPOSAL_VIEW')
        report['stage']='FIRST_LOCAL_APPROVE_DOM'
        approved=post('#plan-approval-approve',first_path+'/plan-approval/commands','APPROVE')
        assert approved['items'][-1]['state']=='APPROVED';expect(page.locator('#delivery-confirm')).to_be_enabled()
        shot('02-local-approved.png','#plan-approval-result')
        report['stage']='FIRST_LOCAL_DELIVERY_DOM_WITH_INTERRUPTED_GET'
        report['interrupt_recovery']=True
        delivered=post('#delivery-confirm',first_path+'/resource-delivery',status=201)
        assert delivered['receipt']['plan_approval']['id']==first_item['id']
        page.wait_for_function('()=>!deliveryBusy&&deliveryHandles()?.length===1',timeout=30000)
        assert report.get('interrupted_original_recovery') and report['interrupt_recovery'] is False
        committed=business_snapshot(run);assert committed['counts']==dict(synthetic_resource_combinations=1,synthetic_resource_combination_members=3,synthetic_resource_combination_receipts=1,resource_case_claims=1,case_resource_links=1)
        shot('03-local-committed-pending.png','#delivery-error')
        report['stage']='FIRST_LOCAL_ORIGINAL_RECEIPT_RECOVERY_DOM'
        open_page(records[0],select_holds=False)
        key=report['original_delivery_request']['key'];recovery_path=first_path+'/resource-delivery/recovery/'+key
        with page.expect_response(lambda r:urlsplit(r.url).path==recovery_path and r.request.method=='GET') as recovered:click('#delivery-recover')
        assert recovered.value.status==200 and recovered.value.json()['receipt']==delivered['receipt'];idle()
        page.wait_for_function('()=>deliveryHandles()?.length===0',timeout=30000)
        click('#plan-approval-read');page.wait_for_function('()=>planApprovalSelected?.state==="CONSUMED"',timeout=30000)
        assert page.evaluate('planApprovalSelected.id')==first_item['id']
        page.set_viewport_size(dict(width=390,height=1000));geometry('CONSUMED_NARROW')
        shot('04-local-consumed-recovered.png','#plan-approval-result');font_observation('ACTUAL_CONSUMED_LOCAL_VIEW')
        before_repeat=business_snapshot(run);original=report['original_delivery_request']
        report['stage']='EXACT_ORIGINAL_POST_REPEAT_API_CHECK'
        repeated=api_call(run,original['path'],original['body'],expected=201,key=key,phase='NEGATIVE_AND_REPEAT')
        assert repeated['receipt']==delivered['receipt'] and business_snapshot(run)==before_repeat
        report['original_delivery_receipt']=delivered['receipt'];report['repeat_original_key']=dict(same_receipt=True,no_additional_business_effect=True)
        report['stage']='SECOND_LOCAL_PROPOSE_APPROVE_DOM'
        second_path,second=enter(records[1]);second_item=second['items'][-1]
        second=post('#plan-approval-approve',second_path+'/plan-approval/commands','APPROVE');second_item=second['items'][-1]
        assert second_item['id']!=first_item['id'] and second['case_id']==records[1]['case_id'] and second['run_id']==records[1]['run_id']
        second_data=page.evaluate('JSON.parse(JSON.stringify(planApprovalSelected.delivery))')
        before_cross=business_snapshot(run);report['stage']='CROSS_CASE_APPROVAL_REJECTION_API'
        api_call(run,second_path+'/resource-delivery',{**second_data,'approval_id':first_item['id']},expected=409,phase='NEGATIVE_AND_REPEAT')
        assert business_snapshot(run)==before_cross
        report['stage']='SECOND_LOCAL_REVOKE_DOM'
        revoked=post('#plan-approval-revoke',second_path+'/plan-approval/commands','REVOKE')
        assert revoked['items'][-1]['state']=='REVOKED';expect(page.locator('#delivery-confirm')).to_be_disabled()
        before_revoked=business_snapshot(run)
        api_call(run,second_path+'/resource-delivery',{**second_data,'approval_id':second_item['id']},expected=409,phase='NEGATIVE_AND_REPEAT')
        assert business_snapshot(run)==before_revoked
        geometry('REVOKED_NARROW');shot('05-local-revoked.png','#plan-approval-result')
        report['negative_checks']=dict(cross_case_approval_http=409,revoked_delivery_http=409,no_additional_business_effect=True)
        report['stage']='CURRENT_OWNER_READ_REVOKED_FIXTURE'
        require_work(run,35)
        dsn=make_conninfo(host=str(run.state/'socket'),port=5432,user='postgres',dbname='parkweave',connect_timeout=2)
        with psycopg.connect(dsn) as c:
            changed=c.execute("UPDATE capability_grants SET active=false WHERE principal_id='ordinary-demo-enterprise' AND capability='READ' AND active RETURNING principal_id").fetchall();assert len(changed)==1
        report['owner_negative_SQL']=dict(existing_synthetic_READ_grant_revocations=1,restorations=0)
        token=page.locator('#token').input_value()
        with page.expect_response(lambda r:urlsplit(r.url).path in ('/api/resource-bundles','/api/plan-approval/status') and r.request.method=='GET' and r.status==403) as denied:click('#plan-approval-read')
        assert denied.value.status==403;idle()
        report['READ403_actual_path']=urlsplit(denied.value.url).path
        page.wait_for_function('()=>planApprovalView===null&&planApprovalSelected===null&&deliveryQuote===null',timeout=30000)
        assert page.locator('#token').input_value()==token
        for selector in ('#plan-approval-result','#delivery-result','#resource-hold-items','#resource-catalog-view','#resource-current','#combination-items'):
            expect(page.locator(selector)).to_be_empty()
        geometry('DENIED_NARROW');shot('06-local-read-denied.png','#page-feedback')
        report['READ403_cleared_private_views']=True
        report['final_business_snapshot']=business_snapshot(run)
        assert report['final_business_snapshot']==before_revoked
        assert report['final_business_snapshot']['local_states'][records[0]['preparation_id']]==['PROPOSE','APPROVE','CONSUME']
        assert report['final_business_snapshot']['local_states'][records[1]['preparation_id']]==['PROPOSE','APPROVE','REVOKE']
        require_work(run,45)
        report['stage']='INSTALLED_GUIDE_NARROW_READ_ONLY'
        guide=context.new_page();guide.set_viewport_size(dict(width=390,height=1000));guide.set_default_timeout(15000)
        guide.on('pageerror',lambda error:report['page_errors'].append(str(error)));guide_primary=None
        try:
            response=guide.goto(report['origin']+'/demo',wait_until='load')
            assert response.status==200 and sha256(response.body()).hexdigest()==report['installation']['package_files']['parkweave/park_demo_web.html']
            assert "frame-ancestors 'none'" in response.headers['content-security-policy']
            expect(guide.locator('#workspace-open')).to_be_disabled()
            assert guide.locator('#sessions').input_value()=='' and guide.evaluate('sessions===null&&workspaceWindow===null')
            geometry('GUIDE_NARROW_READ_ONLY',guide);font_observation('ACTUAL_GUIDE_NARROW_VIEWPORT',guide)
            path=run.public/'07-guide-narrow.png';guide_written=True;guide.screenshot(path=str(path),timeout=10000)
            report['screenshots'].append(dict(file=path.name,sha256=sha256(path.read_bytes()).hexdigest()))
            report['guide_visual_scope']='390px initial fictional guide, no session file, no workspace opened, no business write'
        except BaseException as error:
            guide_primary=error;report['guide_primary_error']=dict(error_type=type(error).__name__,error=str(error));raise
        finally:close_guide(run,guide,guide_primary)
        assert not report['violations'] and not report['page_errors'];harvest();require_work(run)
        report['work_completion_seconds']=round(time.monotonic()-run.started,3)
        report['stage']='INSTALLED_WHEEL_LOCAL_APPROVAL_BROWSER_COMPLETE'
    except BaseException:
        if guide_written:
            try:
                (run.public/'07-guide-narrow.png').unlink(missing_ok=True)
                report['screenshots']=[x for x in report['screenshots'] if x['file']!='07-guide-narrow.png']
                report['guide_screenshot_withdrawn_for_failure_budget']=True
            except BaseException as cleanup:report['guide_screenshot_withdrawal_error']=type(cleanup).__name__
        try:
            path=run.public/'failure-installed-approval.png';page.screenshot(path=str(path),mask=[page.locator('#token')],timeout=10000)
        except BaseException as error:report['failure_screenshot_error']=type(error).__name__
        raise
    finally:context.close()


def publish_logs(run):
    parts=[];metadata=[];total=0
    paths=[run.private/'current-package/build.log',run.private/'application/install.log',run.private/'setup.stdout',run.private/'setup.stderr',run.private/'serve.stdout',run.private/'serve.stderr']
    paths.extend(sorted(run.private.glob('worker-*.log')))
    if hasattr(run,'state'):paths.append(run.state/'logs/installed-api.log')
    for path in paths:
        if not path.is_file():continue
        raw=path.read_bytes();total+=len(raw);assert total<=2*1024*1024
        clean=raw
        for secret in run.secrets:
            for value in (secret.encode(),secret[:12].encode()):clean=clean.replace(value,b'[REDACTED_SYNTHETIC_SESSION]')
        parts.extend([('CAPTURED_COMPONENT '+path.name+'\n').encode(),clean,b'\n'])
        metadata.append(dict(file=path.name,original_sha256=sha256(raw).hexdigest(),original_bytes=len(raw),public_sha256=sha256(clean).hexdigest()))
    (run.public/'installation-redacted.log').write_bytes(b''.join(parts))
    run.report['captured_component_logs']=dict(scope='Complete captured component outputs concatenated with labels;not a single original job stream',components=metadata)


def main():
    from types import SimpleNamespace
    os.umask(0o077);started=time.monotonic()
    report=dict(status='NOT_RUN',stage='HOST_GATE',scope='INSTALLED_WHEEL_LOCAL_APPROVAL_REAL_BROWSER',responses=[],screenshots=[],violations=[],page_errors=[],real_model_calls=0,formal_source=False,formal_AT35=False,Windows=False)
    run=SimpleNamespace(started=started,report=report,secrets=[],public=None)
    run.budget=Budget(report)
    try:
        report['source_sha']=base.require_hosted(os.environ,run_number='13')
        run.private=Path(tempfile.mkdtemp(prefix='parkweave-installed-browser-'))
        run.public=Path(os.environ['RUNNER_TEMP'])/'parkweave-fictional-browser-candidate';run.public.mkdir(mode=0o700,exist_ok=False)
        installation(run,current_wheel(run))
        from scripts.fictional_park_restart_browser_once import installed_font_environment
        report['stage']='INSTALLED_CJK_PREFLIGHT'
        env=dict(os.environ)
        for key,name in (('XDG_CONFIG_HOME','chrome-config'),('XDG_CACHE_HOME','chrome-cache')):
            path=run.private/name;path.mkdir(mode=0o700);env[key]=str(path)
        env=installed_font_environment(env,run.private/'fontconfig',report)
        from playwright.sync_api import sync_playwright
        with server(run):
            report['records']=[prepare(run,i) for i in range(2)]
            with sync_playwright() as pw:
                with pw.chromium.launch(channel='chrome',headless=True,chromium_sandbox=True,args=['--enable-automation'],env=env) as browser:
                    report['real_browser']=True;report['chrome_version']=browser.version;base.resource.verify_sandbox(browser,report)
                    browser_walk(run,browser)
        collect_installation(run);report['status']='PASS'
    except BaseException as error:report.update(status='FAIL',error_type=type(error).__name__,error=str(error))
    finally:
        if hasattr(run,'harness'):
            try:collect_installation(run,complete=False)
            except BaseException as error:base.finalization_failure(report,error)
        if run.public is not None:
            try:publish_logs(run)
            except BaseException as error:base.finalization_failure(report,error)
    return base.finish_report(report,run.secrets,run.public,started=started,allowed_names=PUBLIC_FILES)


if __name__=='__main__':raise SystemExit(main())
