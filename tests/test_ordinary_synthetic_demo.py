"""Actual fresh synthetic launcher -> ordinary worker/API -> two new Cases.

No test fixture prepares business rows or assigns a Run. Owner SQL below is
read-only verification, except the explicitly owned negative drift test.
"""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from pathlib import Path
from uuid import uuid4
import errno,json,os,socket,subprocess,sys,time
import httpx
import psycopg
import pytest
from scripts import ordinary_synthetic_demo as demo
from parkweave.store import Store,Denied
from parkweave.process_env import minimal_environment
from test_service_case_steps import GOALS
from test_ordinary_case_goal_record_pack_process import html

ROOT=Path(__file__).resolve().parents[1]


class PrivateTokens(dict):
    def __repr__(self):return '<private synthetic sessions>'


def port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]


def command(*args):return [sys.executable,'-B','-m','scripts.ordinary_synthetic_demo',*args]


def environment():return minimal_environment(os.environ,PYTHONPATH=str(ROOT/'src')+os.pathsep+str(ROOT),PYTHONDONTWRITEBYTECODE='1')


@pytest.fixture
def demo_state(tmp_path):
    result=subprocess.run(command('setup'),cwd=ROOT,env=environment(),capture_output=True,text=True,timeout=45)
    (tmp_path/'setup.stdout').write_text(result.stdout);(tmp_path/'setup.stderr').write_text(result.stderr)
    assert result.returncode==0,result.stderr
    rows=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert len(rows)==2 and rows[0]['setup_state_dir']==rows[1]['state_dir']
    p=Path(rows[-1]['state_dir']);marker=json.loads((p/'state.json').read_text());tokens=PrivateTokens(json.loads((p/'sessions.json').read_text()))
    assert not (p/'data/postmaster.pid').exists()
    return p,marker,tokens


def finish_server(child,p,selected_port,directory,primary,ready):
    """Observe cleanup on success AND failure; never signal an unowned PID."""
    errors=[]
    record=dict(stage='SERVER_FINALLY', primary_error=demo.error_facts(primary) if primary is not None else None,
        child_created=child is not None, child_exit_code=None, checks={}, cleanup_errors=[])
    def failure(error):
        errors.append(error);record['cleanup_errors'].append(demo.error_facts(error))
    if child is not None:
        try:
            if child.poll() is None:child.terminate()
            child.wait(timeout=40)
        except BaseException as error:failure(error)
        try:
            record['child_exit_code']=child.poll()
            record['checks']['CLI_exited']=record['child_exit_code'] is not None
            if not record['checks']['CLI_exited']:raise RuntimeError('owned CLI exit unconfirmed')
            if primary is None and child.returncode!=0:raise RuntimeError('owned CLI exited unsuccessfully')
        except BaseException as error:failure(error)
        for name,path in [('postmaster_marker_absent',p/'data/postmaster.pid'),('stop_unconfirmed_marker_absent',p/'stop-unconfirmed')]:
            try:
                record['checks'][name]=not path.exists()
                if not record['checks'][name]:raise RuntimeError('retained owned stop marker requires inspection')
            except BaseException as error:failure(error)
        try:
            with socket.create_connection(('127.0.0.1',selected_port),timeout=.3):
                record['checks']['loopback_listener']='PRESENT_NOT_ADOPTED'
            failure(RuntimeError('listener remains; no adoption or signalling'))
        except OSError as error:
            if error.errno==errno.ECONNREFUSED:record['checks']['loopback_listener']='CONNECTION_REFUSED'
            else:
                record['checks']['loopback_listener']='UNKNOWN';failure(error)
        except BaseException as error:
            record['checks']['loopback_listener']='UNKNOWN';failure(error)
        try:
            prefix='ORDINARY_SYNTHETIC_DEMO_DIAGNOSTIC '
            lines=(directory/'serve.stderr').read_text().splitlines()
            records=[json.loads(line[len(prefix):]) for line in lines if line.startswith(prefix)]
            record['launcher_diagnostics']=records
            if not records:raise RuntimeError('launcher child cleanup facts missing')
            for item in records:
                roles={row['role']:row for row in item['children']}
                if len(roles)!=len(item['children']):raise RuntimeError('duplicate child role facts')
                for role,status in item['creation'].items():
                    if (status=='created')!=(role in roles):raise RuntimeError('child creation/exit facts disagree')
                if ready is not None:
                    for role in ('postgres','api','worker'):
                        if roles.get(role,{}).get('pid')!=ready[role+'_pid']:raise RuntimeError('ready child identity absent from cleanup facts')
                if item['cleanup_errors']:raise RuntimeError('launcher reported owned cleanup failure')
                for row in item['children']:
                    if type(row['exit_code']) is not int:raise RuntimeError('owned child exit code unconfirmed')
        except BaseException as error:failure(error)
    else:
        record['checks']['CLI_exited']='NOT_CREATED'
    record['cleanup_confirmed']=not errors
    try:(directory/'server-cleanup.json').write_text(json.dumps(record,indent=2)+'\n')
    except BaseException as error:failure(error);record['cleanup_confirmed']=False
    if errors:
        problem=BaseExceptionGroup('ordinary server operation and cleanup evidence failed',([primary] if primary is not None else [])+errors)
        problem.server_observation=record
        raise problem from None
    if primary is not None:primary.server_observation=record


@contextmanager
def server(p,directory,selected_port=None,*,local_demo_config=None):
    directory.mkdir();selected_port=selected_port or port()
    with (directory/'serve.stdout').open('w') as out,(directory/'serve.stderr').open('w') as err:
        extra=['--local-demo-config',str(local_demo_config)] if local_demo_config is not None else []
        child=None;primary=None;ready=None
        try:
            child=subprocess.Popen(command('serve','--state-dir',str(p),'--port',str(selected_port),*extra),cwd=ROOT,env=environment(),stdout=out,stderr=err)
            deadline=time.monotonic()+30;ready=None
            while time.monotonic()<deadline:
                assert child.poll() is None,'ordinary demo child exited before readiness; inspect safe launcher diagnostics'
                rows=[json.loads(line) for line in (directory/'serve.stdout').read_text().splitlines() if line.startswith('{')]
                if rows:ready=rows[-1];break
                time.sleep(.05)
            expected_mode='LOCAL_DEMO_CURRENT_PREPARATION' if local_demo_config is not None else 'CURRENT_PREPARATION'
            assert ready and ready['mode']==expected_mode and ready['models']=='DISABLED'
            # Bounded test evidence only: no Authorization header or body text.
            def trace(kind,request,status=None):
                payload=json.loads(request.content) if request.content else {}
                with (directory/'http-metadata.jsonl').open('a') as stream:
                    stream.write(json.dumps(dict(kind=kind,monotonic=time.monotonic(),method=request.method,
                        path=request.url.path,request_key=request.headers.get('Idempotency-Key'),
                        action=payload.get('action'),status=status))+'\n')
            hooks=dict(request=[lambda request:trace('REQUEST',request)],
                response=[lambda response:trace('RESPONSE',response.request,response.status_code)])
            with httpx.Client(base_url=ready['url'],timeout=20,event_hooks=hooks) as api:
                assert api.get('/health').json()['process_id']==ready['api_pid']
                try:yield api,ready
                except httpx.ReadTimeout:
                    # Observe this exact owned database once before normal cleanup.
                    try:
                        with psycopg.connect(demo.lifecycle.dsn(p),connect_timeout=3,
                                options='-c statement_timeout=1000',row_factory=psycopg.rows.dict_row) as c:
                            c.execute('SET TRANSACTION READ ONLY')
                            observed=dict(activity=c.execute("SELECT pid,state,wait_event_type,wait_event,pg_blocking_pids(pid) blockers FROM pg_stat_activity WHERE datname=current_database() ORDER BY pid").fetchall(),
                                locks=c.execute("SELECT pid,locktype,mode,granted,relation::regclass::text relation FROM pg_locks WHERE database=(SELECT oid FROM pg_database WHERE datname=current_database()) ORDER BY pid,locktype,mode").fetchall())
                    except Exception as error:observed=dict(diagnostic_error_type=type(error).__name__)
                    (directory/'http-timeout-observation.json').write_text(json.dumps(observed,default=str,indent=2)+'\n')
                    raise
        except BaseException as error:
            primary=error
            raise
        finally:
            finish_server(child,p,selected_port,directory,primary,ready)


def call(api,tokens,path,body=None,actor='enterprise',expected=200):
    headers={'Authorization':'Bearer '+tokens[actor]}
    if body is None:r=api.get(path,headers=headers)
    else:
        headers['Idempotency-Key']=uuid4().hex;r=api.post(path,headers=headers,json=body)
    assert r.status_code==expected,r.text
    return r.json()


def prepare_case(api,tokens,label,scope=None):
    scope=scope or demo.SCOPES['primary']
    run=call(api,tokens,'/api/runs',dict(goal='SYNTHETIC '+label+' wholly new request'),expected=202)['run_id']
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        row=call(api,tokens,'/api/runs/'+run)
        if row['state']=='SUCCEEDED':break
        assert row['state'] in ('QUEUED','RUNNING'),row
        time.sleep(.05)
    else:pytest.fail('ordinary worker did not finish new local Case')
    p=call(api,tokens,'/api/preparations',dict(run_id=run,service_id='synthetic-material-preparation',service_version=1,reviewer_id=scope['ids']['specialist']),expected=201)
    base='/api/preparations/'+p['preparation_id']
    p=call(api,tokens,base+'/request-intent',dict(expected_preparation_revision=p['revision'],request_text='SYNTHETIC new '+label+' request and explicit five goals',required_goals=GOALS))
    request_revision=p['request_intent']['revision']
    for slot in ('need_summary','material_outline'):
        p=call(api,tokens,base+'/commands',dict(action='ADD_EVIDENCE',expected_revision=p['revision'],slot=slot,text='SYNTHETIC '+label+' '+slot+' independently entered',source_kind='USER_STATEMENT',source_label='SYNTHETIC explicit '+label))
    for actor,action in (('specialist','REVIEW'),('enterprise','CONFIRM')):
        p=call(api,tokens,base+'/commands',dict(action=action,expected_revision=p['revision'],reason='SYNTHETIC user '+action),actor=actor)
    return p,request_revision


def adopt_case(api,tokens,p,request_revision):
    base='/api/preparations/'+p['preparation_id']
    planning=call(api,tokens,base+'/planning-preview')['current']
    assert planning['required_goals']==GOALS
    plan=call(api,tokens,base+'/service-case-plan',dict(expected_preparation_revision=p['revision'],expected_request_revision=request_revision,expected_source_sha256=planning['source_sha256'],expected_plan_revision=0,required_goals=GOALS,reason='SYNTHETIC explicit user ADOPT'),expected=201)
    assert len(plan['steps'])==5
    return p


def new_case(api,tokens,label,scope=None):
    p,request_revision=prepare_case(api,tokens,label,scope)
    return adopt_case(api,tokens,p,request_revision)


def verify(api,tokens,p,adapter):
    base='/api/preparations/'+p['preparation_id']+'/service-case-plan';row=call(api,tokens,base)
    step=next(s for s in row['steps'] if s['adapter_id']==adapter)
    row=call(api,tokens,base+'/commands',dict(action='VERIFY',step_id=step['id'],expected_revision=row['revision'],expected_source_sha256=step['source_sha256'],reason='SYNTHETIC explicit '+adapter))
    assert next(s for s in row['steps'] if s['adapter_id']==adapter)['state']=='VERIFIED'


def complete(api,tokens,p,label,scope=None,p1_verified=False):
    scope=scope or demo.SCOPES['primary']
    base='/api/preparations/'+p['preparation_id']
    if not p1_verified:verify(api,tokens,p,'P1')
    now=datetime.now(timezone.utc);holds=[]
    for resource in (row['id'] for row in scope['resources']):
        holds.append(call(api,tokens,'/api/synthetic-resources/'+str(resource)+'/holds',dict(starts_at=(now+timedelta(hours=1)).isoformat(),ends_at=(now+timedelta(hours=2)).isoformat(),quantity=1,expected_revision=1,ttl_seconds=120,purpose='SYNTHETIC '+label),expected=201)['hold'])
    group=call(api,tokens,'/api/resource-combinations',dict(members=[dict(hold_id=h['id'],expected_revision=h['resource_revision']) for h in holds]),expected=201)['combination']
    call(api,tokens,base+'/resource-link',dict(combination_id=group['id'],expected_preparation_revision=p['revision'],expected_link_revision=0,reason='SYNTHETIC original combination association'),expected=201)
    verify(api,tokens,p,'P2')
    d=call(api,tokens,base+'/dispatch',dict(expected_preparation_revision=p['revision'],expected_dispatch_revision=0,executor_id=scope['ids']['executor'],reason='SYNTHETIC explicit reviewer OFFER'),actor='specialist',expected=201)
    d=call(api,tokens,'/api/service-dispatches/'+d['dispatch_id']+'/commands',dict(action='ACCEPT',expected_revision=d['revision'],reason='SYNTHETIC executor accepts own step'),actor='executor')
    verify(api,tokens,p,'P3')
    receipt='/api/executor-receipts/'+d['receipt_step_id'];r=call(api,tokens,receipt,actor='executor')
    r=call(api,tokens,receipt+'/commands',dict(action='SUBMIT',expected_revision=r['step']['revision'],text='SYNTHETIC '+label+' actual manual demo receipt',source_kind='SYNTHETIC',source_label='SYNTHETIC user receipt '+label),actor='executor')
    call(api,tokens,receipt+'/commands',dict(action='ACKNOWLEDGE',expected_revision=r['step']['revision'],reason='SYNTHETIC owner verifies',receipt_sha256=r['current_receipt']['source_sha256']))
    verify(api,tokens,p,'P4')
    for action in ('REVALIDATE','CLOSE_LOCAL_RECORD'):
        row=call(api,tokens,base+'/local-case')
        call(api,tokens,base+'/local-case/commands',dict(action=action,expected_revision=row['revision'],expected_cycle=row['cycle'],expected_snapshot_sha256=row['current_snapshot_sha256'],reason='SYNTHETIC explicit '+action))
    verify(api,tokens,p,'P5');results=call(api,tokens,base+'/goal-results')
    assert results['state']=='LOCAL_OUTPUTS_VERIFIED' and len(results['results'])==5 and not results['case_goal_completed']
    assert all(x['historical_verification']['current'] for x in results['results'])
    return d,results


def test_fresh_setup_two_new_cases_original_worker_full_chain_and_physical_restart(demo_state,tmp_path):
    p,marker,tokens=demo_state
    original_marker=(p/'state.json').read_bytes();starts=[]
    with server(p,tmp_path/'first-start') as (api,ready):
        starts.append(ready)
        with Store(demo.lifecycle.dsn(p)).connect() as c:
            c.execute('SET TRANSACTION READ ONLY');assert all(c.execute('SELECT count(*) n FROM '+t).fetchone()['n']==0 for t in ('runs','cases','preparations','run_assignments'))
        with Store(demo.lifecycle.dsn(p,application=True)).connect() as c:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):c.execute("UPDATE capability_grants SET active=false")
        first=new_case(api,tokens,'A设备维护');d,a=complete(api,tokens,first,'A')
        f=(None,None,{'fixture-a':tokens['enterprise'],'executor-a':tokens['executor']},api)
        pack=html(f,tmp_path/'first-html',first,a['plan_id'],'LOCAL_OUTPUTS_VERIFIED',goal_count=5)
        assert all(c['method']=='GET' for c in pack['calls'])
    assert (p/'state.json').read_bytes()==original_marker
    with server(p,tmp_path/'cold-start') as (api,ready):
        starts.append(ready);assert ready['postgres_pid']!=starts[0]['postgres_pid'] and ready['api_pid']!=starts[0]['api_pid']
        assert call(api,tokens,'/api/preparations/'+first['preparation_id']+'/goal-results')==a
        cold=html((None,None,{'fixture-a':tokens['enterprise'],'executor-a':tokens['executor']},api),tmp_path/'cold-html',first,a['plan_id'],'LOCAL_OUTPUTS_VERIFIED',goal_count=5)
        assert (tmp_path/'first-html/download.txt').read_bytes()==(tmp_path/'cold-html/download.txt').read_bytes()
        historical=call(api,tokens,'/api/service-dispatches/'+d['dispatch_id'])
        assert historical['assignment_valid_until']==d['assignment_valid_until']
        second=new_case(api,tokens,'B员工培训');other,b=complete(api,tokens,second,'B')
        assert all(first[k]!=second[k] for k in ('run_id','case_id','preparation_id')) and a['plan_id']!=b['plan_id'] and d['dispatch_id']!=other['dispatch_id']
        assert call(api,tokens,'/api/preparations/'+first['preparation_id']+'/goal-results')==a
        assert 'B员工培训' not in json.dumps(call(api,tokens,'/api/preparations/'+first['preparation_id']),ensure_ascii=False)
        with Store(demo.lifecycle.dsn(p)).connect() as c:
            c.execute('SET TRANSACTION READ ONLY');assert demo.authority(c)==marker['authority']
            assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
            assert c.execute('SELECT count(*) n FROM case_local_events').fetchone()['n']==4
            assert c.execute('SELECT count(*) n FROM cases').fetchone()['n']==2
    assert (p/'state.json').read_bytes()==original_marker
    (tmp_path/'ordinary-demo-chain.json').write_text(json.dumps(dict(starts=starts,cases=[dict(preparation=first,dispatch=d['dispatch_id'],plan=a['plan_id']),dict(preparation=second,dispatch=other['dispatch_id'],plan=b['plan_id'])],worker_processes=2,fixture_finish_calls=0,physical_postgres_restart=True,authority_unchanged=True,run_assignments=0,nodevm_checks=[pack['checks'],cold['checks']],browser=False),default=str,indent=2)+'\n')


def test_occupied_port_does_not_adopt_or_stop_listener(tmp_path):
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0));listener.listen();selected=listener.getsockname()[1]
        result=subprocess.run(command('serve','--state-dir','/tmp/not-a-demo','--port',str(selected)),cwd=ROOT,env=environment(),capture_output=True,text=True,timeout=10)
        assert result.returncode==1 and not result.stdout and 'OSError' in result.stderr
        with socket.create_connection(('127.0.0.1',selected),timeout=.3):pass
    (tmp_path/'occupied-port-result.json').write_text(json.dumps(dict(exit_code=result.returncode,listener_preserved=True,no_setup=True))+'\n')


def test_initialization_requires_live_original_creation_receipt():
    with pytest.raises(Denied):demo.initialize(Store('must-not-connect'),{})


def test_retained_source_or_schema_changes_reject_before_postgres(demo_state,monkeypatch):
    p,marker,_=demo_state
    def forbidden(*a,**k):raise AssertionError('must not start postgres')
    monkeypatch.setattr(demo.lifecycle,'postgres',forbidden)
    for change in ({'schema':'other-demo'},{'source':{'sha256':'changed','files':{}}}):
        (p/'state.json').write_text(json.dumps(dict(marker,**change)))
        with pytest.raises(Denied):demo.serve(p,port())
    assert not (p/'data/postmaster.pid').exists()


@pytest.mark.parametrize('change',['business_grant','sql_acl'])
def test_retained_authority_drift_is_not_repaired(demo_state,change):
    p,marker,_=demo_state
    with demo.lifecycle.postgres(p):
        with Store(demo.lifecycle.dsn(p)).connect() as c:
            if change=='business_grant':c.execute("UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability='EXECUTE'",(demo.IDS['enterprise'],))
            else:c.execute('GRANT UPDATE ON capability_grants TO parkweave_app')
    with pytest.raises(Denied):demo.serve(p,port())
    with demo.lifecycle.postgres(p):
        with Store(demo.lifecycle.dsn(p)).connect() as c:
            c.execute('SET TRANSACTION READ ONLY');assert demo.authority(c)!=marker['authority']
            assert not c.execute('SELECT 1 FROM runs').fetchone()
            if change=='business_grant':assert c.execute("SELECT active FROM capability_grants WHERE principal_id=%s AND capability='EXECUTE'",(demo.IDS['enterprise'],)).fetchone()['active'] is False
            else:assert c.execute("SELECT has_table_privilege('parkweave_app','capability_grants','UPDATE') ok").fetchone()['ok'] is True


def test_setup_failure_retains_exactly_one_directory_without_retry(tmp_path,monkeypatch,capsys):
    calls=[]
    def failed(args,**kw):
        calls.append(args);assert args[0].endswith('/initdb')
        raise subprocess.CalledProcessError(99,args)
    monkeypatch.setattr(demo.subprocess,'run',failed);monkeypatch.setattr(demo.signal,'signal',lambda *a:None)
    monkeypatch.setattr(sys,'argv',['ordinary-synthetic-demo','setup'])
    previous=os.umask(0o077)
    try:assert demo.main()==1
    finally:os.umask(previous)
    out=capsys.readouterr();rows=[json.loads(s) for s in out.out.splitlines() if s.startswith('{')]
    assert len(rows)==1 and len(calls)==1
    p=Path(rows[0]['setup_state_dir']);assert p.is_dir() and (p/'failure.log').exists() and not (p/'sessions.json').exists()
    assert 'CalledProcessError' in out.err and 'no automatic retry' in out.err
    (tmp_path/'setup-failure-proof.json').write_text(json.dumps(dict(state_dir=str(p),initdb_attempts=1,state_retained=True,session_issued=False,postgres_started=False))+'\n')


def test_worker_spawn_failure_stops_exact_owned_api_and_postgres(demo_state,tmp_path,monkeypatch):
    p,_,_=demo_state;before=(p/'state.json').read_bytes();original=demo.subprocess.Popen;children=[];worker_attempts=[]
    def spawn(args,**kw):
        if 'parkweave.worker' in args:
            worker_attempts.append(args);raise RuntimeError('SYNTHETIC worker spawn failure')
        child=original(args,**kw);children.append(child);return child
    monkeypatch.setattr(demo.subprocess,'Popen',spawn)
    with pytest.raises(RuntimeError,match='SYNTHETIC worker spawn failure'):demo.serve(p,port())
    assert len(worker_attempts)==1 and len(children)==2 and all(c.poll() is not None for c in children)
    assert (p/'state.json').read_bytes()==before and not (p/'data/postmaster.pid').exists()
    assert (p/'logs/application.log').exists() and not (p/'stop-unconfirmed').exists()
    (tmp_path/'child-failure-proof.json').write_text(json.dumps(dict(stopped_owned_pids=[c.pid for c in children],worker_spawn_attempts=1,marker_unchanged=True,state_retained=True))+'\n')
