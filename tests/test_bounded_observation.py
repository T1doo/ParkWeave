"""Bounded typed telemetry distinguishes failure hypotheses without raw content."""
import json,threading
from types import SimpleNamespace
import pytest
from test_lifecycle_diagnostics import lifecycle,diagnostic,module,POISON


def prepare_start(tmp_path,monkeypatch,case):
    import psutil,urllib.request,urllib.error
    monkeypatch.setattr(lifecycle,'RUNTIME',tmp_path);monkeypatch.setattr(lifecycle,'STATE',tmp_path/'state.json')
    monkeypatch.setattr(lifecycle,'load_config',lambda:{'python':'SYNTHETIC-python','port':8765})
    for name in ('check_python','port_available','protect_private_root'):monkeypatch.setattr(lifecycle,name,lambda *args:None)
    monkeypatch.setattr(lifecycle,'check_dsn_scope',lambda *args,**kw:None)
    monkeypatch.setattr(lifecycle,'needed_environment',lambda name:'SYNTHETIC')
    monkeypatch.setattr(lifecycle,'time',SimpleNamespace(sleep=lambda _:None))
    children=[]
    class Child:
        def __init__(self,*args,**kwargs):self.pid=901+len(children);self.stopped=False;children.append(self)
        def create_time(self):return 1.0
        def poll(self):
            if self.stopped:return 0
            if case=='API_EXITED' and self is children[0]:return 7
            if case=='WORKER_EXITED' and self is children[1]:return 7
            return None
    monkeypatch.setattr(psutil,'Popen',Child)
    def cleanup(record,*args):children[record['pid']-901].stopped=True;return 'STOPPED'
    monkeypatch.setattr(lifecycle,'stop_record',cleanup)
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return json.dumps({'execution_mode':'FAULT_INJECTION' if case=='MODE_MISMATCH' else 'LOCAL','model':'LIVE' if case=='MODEL_MISMATCH' else 'MODEL_MOCK','process_id':9999 if case=='PID_MISMATCH' else 901,'secret':POISON}).encode()
    class Opener:
        def open(self,url,timeout):
            assert url=='http://127.0.0.1:8765/health' and timeout==1
            errors={'REFUSED':urllib.error.URLError(ConnectionRefusedError(POISON)),'TIMEOUT':urllib.error.URLError(TimeoutError(POISON)),'HTTP':urllib.error.HTTPError(POISON,503,POISON,None,None),'OTHER':urllib.error.URLError(OSError(POISON))}
            if case in errors:raise errors[case]
            return Response()
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())


@pytest.mark.parametrize('case,key,last',[('REFUSED','refused','CONNECTION_REFUSED'),('TIMEOUT','timeouts','TRANSPORT_TIMEOUT'),('HTTP','http_errors','HTTP_NON_SUCCESS'),('OTHER','other_errors','TRANSPORT_OTHER')])
def test_start_transport_failure_categories_and_alive_refusal_counts(tmp_path,monkeypatch,case,key,last):
    prepare_start(tmp_path,monkeypatch,case)
    with pytest.raises(lifecycle.BoundaryError) as error:lifecycle.start()
    row=diagnostic.parse(diagnostic.command('start',error.value),'start');obs=row['start_observation']
    assert row['boundary_reason']=='READINESS_TIMEOUT' and obs['last']==last and obs[key]==obs['attempts']==50
    assert obs['responses']==0 and not diagnostic.START_MATCHES&set(obs)
    assert obs['api']==obs['worker']=='RUNNING' and obs['alive_refused']==(50 if case=='REFUSED' else 0)
    assert obs['cleanup_attempted']==obs['stopped']==2 and obs['after_api']==obs['after_worker']=='EXIT_ZERO'
    assert POISON not in json.dumps(row)


@pytest.mark.parametrize('case,api,worker',[('API_EXITED','EXIT_NONZERO','RUNNING'),('WORKER_EXITED','RUNNING','EXIT_NONZERO')])
def test_start_child_exit_is_distinct_before_any_health_request(tmp_path,monkeypatch,case,api,worker):
    prepare_start(tmp_path,monkeypatch,case)
    with pytest.raises(lifecycle.BoundaryError) as error:lifecycle.start()
    row=diagnostic.parse(diagnostic.command('start',error.value),'start');obs=row['start_observation']
    assert row['boundary_reason']=='SERVICE_EXITED' and obs['last']=='CHILD_EXITED' and obs['attempts']==0
    assert (obs['api'],obs['worker'])==(api,worker)


@pytest.mark.parametrize('case,flags',[('MODE_MISMATCH',(False,True,True)),('MODEL_MISMATCH',(True,False,True)),('PID_MISMATCH',(True,True,False))])
def test_start_valid_health_response_preserves_three_separate_match_flags(tmp_path,monkeypatch,case,flags):
    prepare_start(tmp_path,monkeypatch,case)
    with pytest.raises(lifecycle.BoundaryError) as error:lifecycle.start()
    obs=diagnostic.parse(diagnostic.command('start',error.value),'start')['start_observation']
    assert obs['responses']==obs['mismatches']==obs['attempts']==50 and obs['last']=='HEALTH_MISMATCH'
    assert tuple(obs[k] for k in ('mode_matches','model_matches','process_matches'))==flags
    assert POISON not in json.dumps(obs)


def test_successful_start_observation_uses_existing_marker_without_claiming_cleanup(tmp_path,monkeypatch,capsys):
    prepare_start(tmp_path,monkeypatch,'SUCCESS');lifecycle.start()
    obs=diagnostic.parse(capsys.readouterr().out,'start')['start_observation']
    assert obs['attempts']==obs['responses']==1 and obs['last']=='HEALTH_MATCH' and obs['cleanup_attempted']==0
    assert obs['after_api']==obs['after_worker']=='UNKNOWN' and obs['created']==2


def test_sampler_inflight_keeps_valid_checkpoint_and_never_exports_query_or_credentials(tmp_path,monkeypatch):
    from scripts.windows_ci import regression_plugin as plugin
    progress=module('regression_progress');path=tmp_path/'server-regression-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.progress.json'
    p=plugin.Progress(SimpleNamespace(getoption=lambda _:path));p.values.update(collected=2,ordinal=1)
    p.maintenance='host=127.0.0.1 dbname=postgres user=SYNTHETIC'
    entered=threading.Event();release=threading.Event()
    class Cursor:
        def fetchone(self):return (3,1,1,2,1,1)
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,query):entered.set();assert release.wait(3);return Cursor()
    def connect(dsn,**kwargs):
        assert 'connect_timeout=2' in dsn and 'statement_timeout=1000' in dsn and 'lock_timeout=500' in dsn
        return Connection()
    p.connect=connect;thread=threading.Thread(target=p.sample);thread.start()
    try:
        assert entered.wait(3);p.mark('pytest_call')
        before=progress.read_snapshot(path);assert before['regression_phase']=='pytest_call' and before['regression_observation']['sample_state']=='NOT_SAMPLED'
    finally:release.set();thread.join(3)
    assert not thread.is_alive()
    obs=progress.read_snapshot(path)['regression_observation']
    assert obs['sample_attempts']==1 and obs['sample_state']=='AVAILABLE' and obs['client_connections']==3 and obs['lock_waiters']==2 and obs['blocked']==1
    assert 'SYNTHETIC' not in path.read_text() and 'SELECT' not in path.read_text()
    p.sample_budget=20;p.sample();assert p.values['sample_attempts']==1


def test_regression_completed_phase_totals_and_fixture_costs_are_separate(monkeypatch,tmp_path):
    from scripts.windows_ci import regression_plugin as plugin
    progress=module('regression_progress');clock=[100.0]
    path=tmp_path/'server-regression-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb.progress.json'
    p=plugin.Progress(SimpleNamespace(getoption=lambda _:path),clock=lambda:clock[0]);p.values.update(collected=2,ordinal=1)
    p.mark('pytest_setup');p.fixture_stage('CREATE_DB');clock[0]+=2;p.fixture_stage('MIGRATE');clock[0]+=3;p.fixture_stage('SEED');clock[0]+=1;p.fixture_stage('GRANTS');clock[0]+=1;p.fixture_stage('CLIENT')
    for when,duration in [('setup',7),('call',4),('teardown',2)]:
        p.report(SimpleNamespace(when=when,duration=duration))
    p.fixture_stage('DROP_DB');clock[0]+=2;p.fixture_stage('DONE')
    obs=progress.read_snapshot(path)['regression_observation']
    assert (obs['setup_ms'],obs['call_ms'],obs['teardown_ms'],obs['completed'],obs['collected'])==(7000,4000,2000,1,2)
    assert (obs['create_ms'],obs['migrate_ms'],obs['seed_ms'],obs['grants_ms'],obs['drop_ms'])==(2000,3000,1000,1000,2000)
    assert obs['fixture_stage']=='DONE' and obs['fixture_ms']==0


def test_safe_observation_projection_covers_positive_results_and_rejects_extra_fields(tmp_path,monkeypatch,capsys):
    prepare_start(tmp_path,monkeypatch,'SUCCESS');lifecycle.start();obs=diagnostic.parse(capsys.readouterr().out,'start')['start_observation']
    publisher=module('publish_summary');public=publisher.base('SUMMARY_AVAILABLE');public.update(report_state='COMPLETED',active_phase='UNKNOWN',cases=[{'case':'Start_native','status':'PASS','exit_code':0,'start_observation':obs}])
    commands,ok=publisher.annotation_commands(public);assert ok and len(commands)==2 and 'HEALTH_MATCH' in commands[1] and all(publisher.annotation_size(c)<=2048 for c in commands)
    for bad in [dict(obs,refused=True),dict(obs,secret=POISON),dict(obs,created=3),dict(obs,process_matches=POISON)]:
        with pytest.raises(ValueError):diagnostic.start_observation(bad)


def test_regression_observation_rejects_inconsistent_or_untyped_evidence(tmp_path):
    progress=module('regression_progress')
    obs={**{k:0 for k in progress.TIMINGS},'completed':1,'collected':2,'ordinal':1,'fixture_stage':'DONE','sample_attempts':0,'sample_state':'NOT_SAMPLED'}
    assert progress.observation(obs)==obs
    for bad in [dict(obs,completed=2),dict(obs,ordinal=3),dict(obs,setup_ms=True),dict(obs,sample_attempts=21),dict(obs,sample_state='AVAILABLE'),dict(obs,blocked=0),dict(obs,secret=POISON)]:
        with pytest.raises(ValueError):progress.observation(bad)
    path=tmp_path/'server-regression-cccccccccccccccccccccccccccccccc.progress.json'
    progress.write(path,'report_write',telemetry=obs)
    row=json.loads(path.read_text());row['telemetry']['secret']=POISON;path.write_text(json.dumps(row))
    assert 'regression_observation' not in progress.read_snapshot(path)
