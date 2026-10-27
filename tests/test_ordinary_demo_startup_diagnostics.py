"""Deterministic failures only: no PostgreSQL/API/browser/font download or CI."""
from contextlib import contextmanager, nullcontext
import errno
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from scripts import ordinary_synthetic_demo as demo
from scripts import material_only_demo as lifecycle
import test_ordinary_synthetic_demo as helper

SECRET='UNIT_PRIVATE_TOKEN_MUST_NOT_APPEAR'


@pytest.fixture
def owned():
    with tempfile.TemporaryDirectory(prefix=demo.PREFIX,dir='/tmp') as directory:
        p=Path(directory)
        (p/'data').mkdir(mode=0o700);(p/'logs').mkdir(mode=0o700)
        yield p


def fail_port(monkeypatch,p):
    monkeypatch.setattr(sys,'argv',['ordinary-demo','serve','--state-dir',str(p)])
    monkeypatch.setattr(demo.signal,'signal',lambda *a:None)
    def failed(*a):raise OSError(errno.EADDRINUSE,SECRET)
    monkeypatch.setattr(demo,'check_port',failed)
    return demo.main()


def read_diagnostic(stderr):
    prefix='ORDINARY_SYNTHETIC_DEMO_DIAGNOSTIC '
    return json.loads(next(line[len(prefix):] for line in stderr.splitlines() if line.startswith(prefix)))


def test_precheck_failure_records_safe_facts_before_owned_state_binding(owned,monkeypatch,capsys):
    assert fail_port(monkeypatch,owned)==1
    captured=capsys.readouterr();record=read_diagnostic(captured.err)
    assert record['stage']=='PORT_PRECHECK' and record['error']==dict(type='OSError',errno=errno.EADDRINUSE)
    assert record['creation']==dict(postgres='not_created',api='not_created',worker='not_created')
    assert record['children']==[] and not captured.out and SECRET not in captured.err
    assert json.loads((owned/'failure.log').read_text())==record
    assert demo._last_owned_state is None


@pytest.mark.parametrize('kind',['symlink','fifo','broad_mode'])
def test_private_failure_log_rejects_unsafe_target_preserves_primary(owned,tmp_path,monkeypatch,capsys,kind):
    path=owned/'failure.log';other=tmp_path/'untouched';other.write_text('ORIGINAL')
    if kind=='symlink':path.symlink_to(other)
    elif kind=='fifo':demo.os.mkfifo(path,mode=0o600)
    else:path.write_text('ORIGINAL');path.chmod(0o644)
    assert fail_port(monkeypatch,owned)==1
    captured=capsys.readouterr();record=read_diagnostic(captured.err)
    assert record['error']['errno']==errno.EADDRINUSE and 'recording_error' in record
    assert SECRET not in captured.err and other.read_text()=='ORIGINAL'
    if kind=='broad_mode':assert path.read_text()=='ORIGINAL'


class Process:
    def __init__(self,pid=123,code=None):self.pid=pid;self.returncode=code;self.terminated=0;self.waited=0
    def poll(self):return self.returncode
    def terminate(self):self.terminated+=1;self.returncode=0
    def wait(self,timeout):self.waited+=1;return self.returncode
    def send_signal(self,signum):self.returncode=0


@pytest.mark.parametrize('cleanup_fails',[False,True])
def test_worker_spawn_failure_retains_primary_and_owned_exit_facts(owned,monkeypatch,cleanup_fails):
    marker=dict(schema=demo.SCHEMA,source={},ids=demo.IDS,scopes=demo.SCOPES,
        sessions_sha256=demo.sha256(b'unit').hexdigest(),system_identifier='unit',database_oid=1,authority={})
    (owned/'state.json').write_text(json.dumps(marker));(owned/'sessions.json').write_bytes(b'unit')
    @contextmanager
    def locked(value):yield owned
    @contextmanager
    def postgres(p,*,observation):
        row=dict(role='postgres',pid=100,exit_code=None);observation['children'].append(row)
        observation['creation']['postgres']='created'
        try:yield SimpleNamespace(pid=100)
        finally:row['exit_code']=0
    class Connection:
        def execute(self,sql):self.sql=sql;return self
        def fetchone(self):
            if 'system_identifier' in self.sql:return dict(system_identifier='unit')
            if 'pg_database' in self.sql:return dict(oid=1)
            return dict(v=32)
    monkeypatch.setattr(demo,'locked',locked);monkeypatch.setattr(demo,'check_port',lambda p:None)
    monkeypatch.setattr(demo,'source_binding',lambda:{});monkeypatch.setattr(demo,'authority',lambda c:{})
    monkeypatch.setattr(lifecycle,'postgres',postgres)
    monkeypatch.setattr(demo.psycopg,'connect',lambda *a,**k:nullcontext(Connection()))
    api=Process(101);calls=[]
    primary=OSError(errno.EIO,SECRET)
    def spawn(args,**kwargs):
        calls.append(args)
        if 'parkweave.worker' in args:raise primary
        return api
    def stop(children):
        assert children==[api]
        if cleanup_fails:raise OSError(errno.EPERM,SECRET)
        api.returncode=0
    monkeypatch.setattr(demo.subprocess,'Popen',spawn);monkeypatch.setattr(demo,'stop_children',stop)
    observation={}
    with pytest.raises(BaseException) as caught:demo.serve(owned,8765,observation=observation)
    assert len(calls)==2 and observation['stage']=='WORKER_SPAWN'
    assert observation['children'][0]['exit_code']==0
    if cleanup_fails:
        assert isinstance(caught.value,BaseExceptionGroup) and caught.value.exceptions[0] is primary
        assert (owned/'stop-unconfirmed').exists() and observation['cleanup_errors'][0]['errno']==errno.EPERM
    else:assert caught.value is primary and observation['children'][1]['exit_code']==0
    assert SECRET not in json.dumps(demo.diagnostic_record(observation,caught.value))


def test_postgres_cleanup_failure_keeps_original_and_exit_observation(owned,monkeypatch):
    child=Process();primary=RuntimeError(SECRET)
    def fail_signal(signal):raise OSError(errno.EPERM,SECRET)
    child.send_signal=fail_signal
    monkeypatch.setattr(lifecycle.subprocess,'Popen',lambda *a,**k:child)
    monkeypatch.setattr(lifecycle,'pg_bin',lambda n:n)
    monkeypatch.setattr(lifecycle.psycopg,'connect',lambda *a,**k:nullcontext())
    obs=dict(children=[],creation=dict(postgres='not_created'),cleanup_errors=[])
    with pytest.raises(BaseExceptionGroup) as caught:
        with lifecycle.postgres(owned,observation=obs):raise primary
    assert caught.value.exceptions[0] is primary
    assert caught.value.exceptions[1].errno==errno.EPERM
    assert obs['creation']['postgres']=='created' and obs['children'][0]['exit_code'] is None
    assert obs['cleanup_errors'][0]['errno']==errno.EPERM
    assert SECRET not in json.dumps(demo.error_facts(caught.value))


def launcher_record(*,exit_code=0):
    return dict(stage='POSTGRES_START',error=dict(type='OSError',errno=errno.EIO),
        creation=dict(postgres='created',api='not_created',worker='not_created'),
        children=[dict(role='postgres',pid=101,exit_code=exit_code)],cleanup_errors=[])


def helper_setup(owned,tmp_path,monkeypatch,*,body=False,kind=None):
    directory=tmp_path/'server';process=Process(code=None if body else 1)
    def spawn(*args,**kwargs):
        record=launcher_record(exit_code=None if kind=='unknown_child_exit' else 0)
        if body:
            record['creation']=dict(postgres='created',api='created',worker='created')
            record['children']=[dict(role=role,pid=pid,exit_code=0) for role,pid in [('postgres',101),('api',123),('worker',124)]]
        (directory/'serve.stderr').write_text('ORDINARY_SYNTHETIC_DEMO_DIAGNOSTIC '+json.dumps(record)+'\n')
        if body:(directory/'serve.stdout').write_text(json.dumps(dict(mode='CURRENT_PREPARATION',models='DISABLED',api_pid=123,worker_pid=124,postgres_pid=101,url='http://127.0.0.1:8765'))+'\n')
        return process
    def refused(*args,**kwargs):
        if kind=='listener':return nullcontext()
        if kind=='timeout':raise TimeoutError(errno.ETIMEDOUT,SECRET)
        raise ConnectionRefusedError(errno.ECONNREFUSED,SECRET)
    monkeypatch.setattr(helper.subprocess,'Popen',spawn);monkeypatch.setattr(helper.socket,'create_connection',refused)
    if kind=='marker':(owned/'data/postmaster.pid').write_text('UNIT_MARKER_NOT_REAL_PID')
    if kind=='wait_timeout':process.wait=Mock(side_effect=subprocess.TimeoutExpired('UNIT_COMMAND',40))
    api=SimpleNamespace(get=lambda path:SimpleNamespace(json=lambda:dict(process_id=123)))
    monkeypatch.setattr(helper.httpx,'Client',lambda **kwargs:nullcontext(api))
    return directory,process


def test_startup_exit1_still_executes_and_confirms_cleanup_checks(owned,tmp_path,monkeypatch):
    directory,child=helper_setup(owned,tmp_path,monkeypatch)
    with pytest.raises(AssertionError) as caught:
        with helper.server(owned,directory,selected_port=8765):pytest.fail('must not yield')
    record=caught.value.server_observation
    assert record['cleanup_confirmed'] and record['child_exit_code']==1 and record['checks']['CLI_exited']
    assert child.waited==1 and child.terminated==0
    assert record==json.loads((directory/'server-cleanup.json').read_text())


@pytest.mark.parametrize('kind',['listener','timeout','marker','wait_timeout','unknown_child_exit'])
def test_startup_primary_and_cleanup_failures_both_retained(owned,tmp_path,monkeypatch,kind):
    directory,child=helper_setup(owned,tmp_path,monkeypatch,kind=kind)
    with pytest.raises(BaseExceptionGroup) as caught:
        with helper.server(owned,directory,selected_port=8765):pytest.fail('must not yield')
    record=caught.value.server_observation
    assert isinstance(caught.value.exceptions[0],AssertionError) and len(caught.value.exceptions)>=2
    assert not record['cleanup_confirmed'] and record['cleanup_errors']
    if kind=='timeout':assert record['checks']['loopback_listener']=='UNKNOWN'
    assert SECRET not in (directory/'server-cleanup.json').read_text()
    assert child.terminated==0


def test_body_failure_also_executes_cleanup_without_masking_original(owned,tmp_path,monkeypatch):
    directory,child=helper_setup(owned,tmp_path,monkeypatch,body=True);primary=RuntimeError(SECRET)
    with pytest.raises(RuntimeError) as caught:
        with helper.server(owned,directory,selected_port=8765):raise primary
    assert caught.value is primary and child.terminated==1 and child.waited==1
    assert caught.value.server_observation['cleanup_confirmed']
    assert SECRET not in (directory/'server-cleanup.json').read_text()


def test_failed_stderr_sink_does_not_replace_primary_or_private_record(owned,monkeypatch):
    class FailedOutput:
        def write(self,*a):raise OSError(errno.EIO,SECRET)
        def flush(self):raise OSError(errno.EIO,SECRET)
    monkeypatch.setattr(sys,'stderr',FailedOutput())
    assert fail_port(monkeypatch,owned)==1
    record=json.loads((owned/'failure.log').read_text())
    assert record['stage']=='PORT_PRECHECK' and record['error']['errno']==errno.EADDRINUSE
    assert SECRET not in (owned/'failure.log').read_text()


def test_cli_spawn_failure_reports_not_created_without_signalling(owned,tmp_path,monkeypatch):
    primary=OSError(errno.EAGAIN,SECRET);directory=tmp_path/'server'
    def spawn(*a,**k):raise primary
    monkeypatch.setattr(helper.subprocess,'Popen',spawn)
    with pytest.raises(OSError) as caught:
        with helper.server(owned,directory,selected_port=8765):pytest.fail('must not yield')
    assert caught.value is primary and not caught.value.server_observation['child_created']
    assert caught.value.server_observation['checks']['CLI_exited']=='NOT_CREATED'
    assert SECRET not in (directory/'server-cleanup.json').read_text()


@pytest.mark.parametrize('remaining',[0,1])
def test_private_failure_log_counts_new_record_before_append(owned,monkeypatch,capsys,remaining):
    original=b'X'*(1048576-remaining);path=owned/'failure.log';path.write_bytes(original);path.chmod(0o600)
    assert fail_port(monkeypatch,owned)==1
    record=read_diagnostic(capsys.readouterr().err)
    assert record['error']['errno']==errno.EADDRINUSE and 'recording_error' in record
    assert path.read_bytes()==original


def test_normal_serve_interrupt_keeps_exit_semantics_if_stderr_fails(owned,monkeypatch):
    class FailedOutput:
        def write(self,*a):raise OSError(errno.EIO,SECRET)
        def flush(self):raise OSError(errno.EIO,SECRET)
    def interrupted(*a,**kw):raise KeyboardInterrupt()
    monkeypatch.setattr(sys,'argv',['ordinary-demo','serve','--state-dir',str(owned)])
    monkeypatch.setattr(demo.signal,'signal',lambda *a:None)
    monkeypatch.setattr(demo,'serve',interrupted);monkeypatch.setattr(sys,'stderr',FailedOutput())
    assert demo.main()==0 and not (owned/'failure.log').exists()
