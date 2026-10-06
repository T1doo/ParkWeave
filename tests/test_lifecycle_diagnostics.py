"""Local real boundary probes and fault injection; never native Server acceptance."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import uuid
import pytest
from test_lifecycle import lifecycle
from test_windows_ci_preparation import module,ROOT
import lifecycle_diagnostics as diagnostic

POISON='SYNTHETIC /private/path password=secret %0A::error::injected'


def test_real_missing_python_and_native_version_guard_are_distinct(tmp_path):
    with pytest.raises(FileNotFoundError) as missing:lifecycle.check_python(tmp_path/'missing-python')
    assert diagnostic.failure(missing.value)['boundary_phase']=='python_guard'
    assert diagnostic.failure(missing.value)['category']=='FileNotFoundError'
    if os.name!='nt':
        with pytest.raises(lifecycle.BoundaryError) as wrong:lifecycle.check_python(sys.executable)
        assert diagnostic.failure(wrong.value)['boundary_reason']=='PYTHON_VERSION_REFUSED'
    assert POISON not in diagnostic.command('doctor',missing.value)


def test_real_config_missing_and_utf8_corruption_are_distinct(tmp_path,monkeypatch):
    path=tmp_path/'config.json';monkeypatch.setattr(lifecycle,'CONFIG',path)
    with pytest.raises(lifecycle.BoundaryError) as absent:lifecycle.load_config()
    assert diagnostic.failure(absent.value)['boundary_reason']=='CONFIG_MISSING'
    path.write_bytes(b'\xff')
    with pytest.raises(UnicodeDecodeError) as corrupt:lifecycle.load_config()
    assert diagnostic.failure(corrupt.value)=={'boundary_phase':'configuration','category':'UnicodeDecodeError','boundary_reason':'UNCLASSIFIED'}
    assert str(path) not in diagnostic.command('start',corrupt.value)


def test_real_loopback_refusal_and_occupied_port_are_distinct():
    import psycopg
    with socket.socket() as owned:
        owned.bind(('127.0.0.1',0));port=owned.getsockname()[1]
        with pytest.raises(lifecycle.BoundaryError) as occupied:lifecycle.port_available(port)
        assert diagnostic.failure(occupied.value)['boundary_reason']=='PORT_OCCUPIED'
        with pytest.raises(psycopg.OperationalError) as refused:
            lifecycle.check_dsn_scope(f'host=127.0.0.1 port={port} dbname=parkweave user=parkweave_app',app=True)
        assert diagnostic.failure(refused.value)['boundary_phase']=='database_connect'
        assert diagnostic.failure(refused.value)['category']=='OperationalError'
        assert str(port) not in diagnostic.command('start',refused.value)


def test_real_isolated_local_database_scope_schema_and_role(tmp_path):
    if os.name=='nt':pytest.skip('Linux isolated probe only; preserve configured native parkweave DB')
    import psycopg
    from psycopg.conninfo import make_conninfo
    from parkweave.store import Store
    from pgserver._commands import initdb,pg_ctl
    # Explicit fresh loopback cluster; ordinary pgserver fixtures are socket-only.
    data=tmp_path/'data';data.mkdir(mode=0o700)
    with socket.socket() as reserved:reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
    initdb(['--auth=trust','--encoding=UTF8','--locale=C','-U','postgres'],pgdata=data)
    pg_ctl(['-w','-l',str(tmp_path/'owned-pg.log'),'-o',f'-h 127.0.0.1 -p {port} -k "{data}"','start'],pgdata=data,timeout=10)
    maintenance=make_conninfo(host='127.0.0.1',port=port,dbname='postgres',user='postgres')
    owner=make_conninfo(maintenance,dbname='parkweave')
    app=make_conninfo(owner,user='parkweave_app')
    try:
        with psycopg.connect(maintenance,autocommit=True) as c:
            c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
            c.execute('CREATE DATABASE parkweave')
        store=Store(owner);store.migrate()
        with store.connect() as c:c.execute((ROOT/'src/parkweave/roles.sql').read_text(encoding='utf-8'))
        assert isinstance(lifecycle.check_dsn_scope(app,app=True),str)
        with Store(app).connect() as c:assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']==18
        with pytest.raises(lifecycle.BoundaryError) as privileged:lifecycle.check_dsn_scope(owner,app=True)
        assert diagnostic.failure(privileged.value)['boundary_reason']=='APP_ROLE_REFUSED'
    finally:
        pg_ctl(['-w','stop','-m','fast'],pgdata=data,timeout=10)


@pytest.mark.parametrize('action,phase,exc',[
    ('setup','private_acl',lifecycle.BoundaryError(POISON,'ACL_OWNER_MISMATCH')),
    ('doctor','private_acl',lifecycle.BoundaryError(POISON,'ACL_REFUSED')),
    ('doctor','dependency_freeze',subprocess.CalledProcessError(1,POISON,output=POISON,stderr=POISON)),
    ('doctor','doctor_output',UnicodeEncodeError('ascii',POISON,0,1,POISON)),
    ('start','process_spawn',FileNotFoundError(POISON)),
    ('start','health_readiness',lifecycle.BoundaryError(POISON,'SERVICE_EXITED')),
])
def test_actual_cli_emits_only_fixed_failure_fields(action,phase,exc,monkeypatch,capsys):
    def fail():
        with diagnostic.stage(phase):raise exc
    monkeypatch.setattr(lifecycle,'require_windows',lambda:None)
    monkeypatch.setattr(lifecycle,action,fail)
    monkeypatch.setattr(sys,'argv',['lifecycle',action])
    with pytest.raises(SystemExit) as done:lifecycle.main()
    assert done.value.code==1
    marker=[x for x in capsys.readouterr().out.splitlines() if x.startswith(diagnostic.PREFIX)]
    assert len(marker)==1 and POISON not in marker[0]
    value=diagnostic.parse(marker[0],action)
    assert value['boundary_phase']==phase and value['category']==type(exc).__name__
    assert len((marker[0]+'\n').encode('ascii'))<=diagnostic.MAX_BYTES


@pytest.mark.parametrize('change',[
    {'schema':True},{'action':'start'},{'boundary_phase':POISON},{'category':POISON},{'boundary_reason':POISON},{'extra':POISON},{'cleanup_category':POISON},
])
def test_protocol_rejects_unknown_mismatched_and_private_fields(change):
    row={'schema':1,'action':'doctor','boundary_phase':'database_connect','category':'OperationalError','boundary_reason':'BOUNDARY_REFUSED',**change}
    result=diagnostic.parse(diagnostic.PREFIX+json.dumps(row),'doctor')
    assert result['boundary_reason']=='DIAGNOSTIC_UNAVAILABLE' and POISON not in repr(result)


def test_protocol_rejects_duplicate_oversize_multiple_and_surrogate_markers():
    good=diagnostic.command('doctor',RuntimeError(POISON))
    for stderr in (good+'\n'+good,good.replace('"schema":1','"schema":1,"schema":1'),good+('x'*65537),diagnostic.PREFIX+'\ud800'):
        assert diagnostic.parse(stderr,'doctor')['boundary_reason']=='DIAGNOSTIC_UNAVAILABLE'


@pytest.mark.parametrize('fault',['service_exit','health_shape','record_write'])
def test_start_preserves_primary_diagnostic_if_cleanup_replaces_exception(tmp_path,monkeypatch,fault):
    import psutil
    monkeypatch.setattr(lifecycle,'RUNTIME',tmp_path);monkeypatch.setattr(lifecycle,'STATE',tmp_path/'state.json')
    monkeypatch.setattr(lifecycle,'load_config',lambda:{'python':'SYNTHETIC-python','port':8765})
    for name in ('check_python','port_available','protect_private_root'):monkeypatch.setattr(lifecycle,name,lambda *args:None)
    monkeypatch.setattr(lifecycle,'check_dsn_scope',lambda *args,**kw:None)
    monkeypatch.setattr(lifecycle,'needed_environment',lambda name:'SYNTHETIC')
    class Child:
        pid=901
        def __init__(self,*args,**kwargs):pass
        def create_time(self):return 1.0
        def poll(self):return 1 if fault=='service_exit' else None
    monkeypatch.setattr(psutil,'Popen',Child)
    def cleanup(*args):
        with diagnostic.stage('process_stop'):raise PermissionError(POISON)
    monkeypatch.setattr(lifecycle,'stop_record',cleanup)
    if fault=='health_shape':
        import urllib.request
        class Response:
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'[]'
        class Opener:
            def open(self,*args,**kwargs):return Response()
        monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    if fault=='record_write':monkeypatch.setattr(lifecycle,'write_exclusive',lambda *args:(_ for _ in ()).throw(OSError(POISON)))
    with pytest.raises(PermissionError) as failure:lifecycle.start()
    row=diagnostic.parse(diagnostic.command('start',failure.value),'start')
    phase,category,reason={'service_exit':('health_readiness','BoundaryError','SERVICE_EXITED'),'health_shape':('health_readiness','AttributeError','UNCLASSIFIED'),'record_write':('process_record','OSError','UNCLASSIFIED')}[fault]
    assert row=={'boundary_phase':phase,'category':category,'boundary_reason':reason,'cleanup_category':'PermissionError'}
    assert (tmp_path/'state.json').exists()==(fault!='record_write')  # Original cleanup behavior.


def test_publisher_standalone_without_site_packages_or_pytest(tmp_path):
    from parkweave.process_env import minimal_environment
    result=subprocess.run([sys.executable,'-S',str(ROOT/'scripts/windows_ci/publish_summary.py')],cwd=tmp_path,env=minimal_environment(os.environ),capture_output=True,text=True,timeout=5)
    assert result.returncode==1 and 'SUMMARY_MISSING' in result.stdout and 'ANNOTATIONS_UNAVAILABLE' in result.stdout and result.stderr==''


@pytest.mark.parametrize("setup_failure",[False,True])
def test_suite_uses_setup_doctor_start_stdout_marker_and_preserves_failure(tmp_path,monkeypatch,capsys,setup_failure):
    from types import SimpleNamespace
    suite=module('native_suite');suite.REPO=tmp_path;suite.require_server=lambda:None
    monkeypatch.setattr(suite.sys,'executable',str(tmp_path/'.venv-windows/Scripts/python.exe'))
    monkeypatch.setattr(suite.sys,'argv',['native_suite','--report',str(tmp_path/'summary.json')])
    config={'PARKWEAVE_OWNER_DSN':'host=127.0.0.1 dbname=parkweave user=park_ci_owner','PARKWEAVE_DSN':'host=127.0.0.1 dbname=parkweave user=parkweave_app','PARKWEAVE_TEST_OWNER_DSN':'host=127.0.0.1 dbname=postgres user=park_ci_owner'}
    monkeypatch.setattr(suite.os,'environ',config)
    runtime=tmp_path/'.runtime';runtime.mkdir();(runtime/'synthetic-sessions.json').write_text('{}');(runtime/'windows-config.json').write_text('{}')
    setup_count=0
    def run(command,**kwargs):
        nonlocal setup_count
        for action in ('doctor','start'):
            if any(str(x).endswith(action.title()+'.ps1') for x in command):
                exc=lifecycle.BoundaryError(POISON,'APP_ROLE_REFUSED');exc.parkweave_lifecycle_phase='database_role'
                return SimpleNamespace(returncode=1,stdout=diagnostic.command(action,exc)+'\n',stderr=POISON)
        if any(str(x).endswith('Setup.ps1') for x in command):
            setup_count+=1
            if setup_failure:
                exc=lifecycle.BoundaryError(POISON,'ACL_OWNER_MISMATCH');exc.parkweave_lifecycle_phase='private_acl'
                return SimpleNamespace(returncode=1,stdout=diagnostic.command('setup',exc)+'\n',stderr=POISON)
            return SimpleNamespace(returncode=0 if setup_count==1 else 1,stdout='',stderr='existing configuration protected')
        if 'scripts/run_acceptance.py' in command:Path(command[-1]).write_text(json.dumps({'engineering_total_counts':{'PASS':1,'FAIL':0,'SKIP':0},'whole_AT_EX':'NOT_RUN'}))
        if 'scripts/windows/file_candidate_probe.py' in command:return SimpleNamespace(returncode=1,stdout='NOT_RUN: explicit native Windows11',stderr='')
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(suite.subprocess,'run',run)
    assert suite.main()==1
    rows=json.loads((tmp_path/'summary.json').read_text())['cases']
    if setup_failure:
        row=next(x for x in rows if x['case']=='Setup_native')
        assert row['status']=='FAIL' and row['boundary_phase']=='private_acl' and row['boundary_reason']=='ACL_OWNER_MISMATCH'
        assert next(x for x in rows if x['case']=='lifecycle_API_browser')['reason']=='SETUP_FAILED'
        assert POISON not in capsys.readouterr().out
        return
    for name in ('Doctor_native','Start_native'):
        row=next(x for x in rows if x['case']==name)
        assert row['status']=='FAIL' and row['exit_code']==1 and row['boundary_phase']=='database_role' and row['boundary_reason']=='APP_ROLE_REFUSED'
    assert next(x for x in rows if x['case']=='API_browser_restart')['status']=='NOT_RUN'
    assert POISON not in capsys.readouterr().out


def test_lifecycle_and_regression_fields_survive_safe_annotation_projection():
    publisher=module('publish_summary');binding={'synthetic':'binding'}
    record=module('native_suite').summary([
        {'case':'Doctor_native','status':'FAIL','exit_code':1,'boundary_phase':'database_connect','category':'OperationalError','boundary_reason':'BOUNDARY_REFUSED','private_log':POISON},
        {'case':'Start_native','status':'FAIL','exit_code':1,'boundary_phase':'health_readiness','category':'BoundaryError','boundary_reason':'SERVICE_EXITED','cleanup_category':'PermissionError'},
        {'case':'full_engineering_regression','status':'FAIL','phase':'regression_run','category':'TimeoutExpired','regression_phase':'pytest_setup'},
    ])
    record.update(diagnostic_schema=1,diagnostic_binding=binding,report_state='COMPLETED',active_phase='UNKNOWN')
    public=publisher.project(record,binding);commands,ok=publisher.annotation_commands(public)
    assert ok and len(commands)==4 and POISON not in repr(commands)
    payload=[json.loads(x.split('::',2)[-1]) for x in commands]
    assert payload[1]['boundary_phase']=='database_connect' and payload[2]['cleanup_category']=='PermissionError'
    assert payload[3]['regression_phase']=='pytest_setup' and public['cases'][2]['status']=='FAIL'


def test_regression_progress_atomic_binding_and_corruption_fail_closed(tmp_path,monkeypatch):
    progress=module('regression_progress');path=tmp_path/('server-regression-'+uuid.uuid4().hex+'.progress.json')
    progress.write(path,'pytest_setup');assert progress.read(path)=='pytest_setup'
    data=json.loads(path.read_bytes());assert set(data)=={'schema','execution_id','phase','active_test_id'}
    data['execution_id']=uuid.uuid4().hex;path.write_text(json.dumps(data));assert progress.read(path)=='UNKNOWN'
    for value in (POISON,'x'*513):path.write_text(value);assert progress.read(path)=='UNKNOWN'
    monkeypatch.setattr(progress.os,'replace',lambda *args:(_ for _ in ()).throw(PermissionError(POISON)))
    progress.write(path,'pytest_call')  # Failure is diagnostic only.
    assert not list(tmp_path.glob('.progress-*.tmp'))


def test_real_direct_parent_timeout_does_not_confirm_owned_descendant_cleanup(tmp_path):
    from parkweave.process_env import minimal_environment
    record=tmp_path/'owned-child.json'
    child=[sys.executable,'-c','import time;time.sleep(20)']
    parent='import subprocess,psutil,json,time,pathlib; p=subprocess.Popen('+repr(child)+'); pathlib.Path('+repr(str(record))+').write_text(json.dumps({"pid":p.pid,"created":psutil.Process(p.pid).create_time()})); time.sleep(20)'
    if sys.platform not in ('linux','win32'):pytest.skip('local Linux/Windows probe only')
    # A separate Linux supervisor adopts/reaps only this probe's orphan, avoiding
    # dependence on container PID1. No production process policy is changed.
    code='''import ctypes,json,os,pathlib,psutil,subprocess,sys
if sys.platform=='linux':assert ctypes.CDLL(None).prctl(36,1,0,0,0)==0
record=pathlib.Path('''+repr(str(record))+''')
child='''+repr(child)+'''
try:
 try:
  subprocess.run([sys.executable,'-c','''+repr(parent)+'''],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
 except subprocess.TimeoutExpired:pass
 else:raise AssertionError('parent unexpectedly completed')
 data=json.loads(record.read_text());owned=psutil.Process(data['pid'])
 assert abs(owned.create_time()-data['created'])<.01 and owned.cmdline()==child
 assert owned.is_running()
finally:
 if record.exists():
  data=json.loads(record.read_text());owned=psutil.Process(data['pid'])
  assert abs(owned.create_time()-data['created'])<.01 and owned.cmdline()==child
  owned.terminate();owned.wait(timeout=5)
print('DIRECT_PARENT_TIMEOUT_DESCENDANT_ALIVE_OWNED_CHILD_REAPED')
'''
    result=subprocess.run([sys.executable,'-c',code],env=minimal_environment(os.environ),capture_output=True,text=True,timeout=10)
    assert result.returncode==0 and result.stdout.strip()=='DIRECT_PARENT_TIMEOUT_DESCENDANT_ALIVE_OWNED_CHILD_REAPED'


@pytest.mark.parametrize('phase',['pytest_setup','pytest_call','pytest_teardown'])
def test_real_pytest_stall_checkpoint_identifies_phase_without_test_content(tmp_path,phase):
    progress=module('regression_progress');path=tmp_path/('server-regression-'+uuid.uuid4().hex+'.progress.json')
    code='import time,pytest\n'
    if phase=='pytest_setup':code+='@pytest.fixture\ndef slow():\n time.sleep(20)\ndef test_SYNTHETIC(slow):pass\n'
    elif phase=='pytest_call':code+='def test_SYNTHETIC():time.sleep(20)\n'
    else:code+='@pytest.fixture\ndef slow():\n yield\n time.sleep(20)\ndef test_SYNTHETIC(slow):pass\n'
    test=tmp_path/'test_stall.py';test.write_text(code)
    from parkweave.process_env import minimal_environment
    process=subprocess.Popen([sys.executable,'-m','pytest','-q','-p','scripts.windows_ci.regression_plugin','--parkweave-progress',str(path),str(test)],cwd=ROOT,env=minimal_environment(os.environ),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        import time
        deadline=time.monotonic()+8
        while time.monotonic()<deadline and progress.read(path)!=phase:
            assert process.poll() is None
            time.sleep(.03)
        assert progress.read(path)==phase and process.poll() is None
        assert 'SYNTHETIC' not in path.read_text() and str(test) not in path.read_text()
    finally:
        if process.poll() is None:process.terminate()
        process.wait(timeout=5)


def test_setup_readonly_failure_survives_safe_annotation_projection():
    publisher=module("publish_summary");binding={"synthetic":"binding"}
    record=module("native_suite").summary([{ "case":"Setup_native","status":"FAIL","exit_code":1,"boundary_phase":"private_acl","category":"BoundaryError","boundary_reason":"ACL_OWNER_MISMATCH","private_log":POISON}])
    record.update(diagnostic_schema=1,diagnostic_binding=binding,report_state="COMPLETED",active_phase="UNKNOWN")
    public=publisher.project(record,binding);commands,ok=publisher.annotation_commands(public)
    assert ok and len(commands)==2 and POISON not in repr(commands)
    assert public["cases"][0]["boundary_reason"]=="ACL_OWNER_MISMATCH"


@pytest.mark.parametrize('outcomes',[('FOREIGN_REFUSED','STOPPED'),('STOPPED','FOREIGN_REFUSED'),('STOPPED','ABSENT'),('ABSENT','ABSENT')])
def test_start_cleanup_refusal_preserves_record_and_readiness_failure(tmp_path,monkeypatch,outcomes):
    import psutil,urllib.request
    from types import SimpleNamespace
    monkeypatch.setattr(lifecycle,'RUNTIME',tmp_path);monkeypatch.setattr(lifecycle,'STATE',tmp_path/'state.json')
    monkeypatch.setattr(lifecycle,'load_config',lambda:{'python':'SYNTHETIC-python','port':8765})
    for name in ('check_python','port_available','protect_private_root'):monkeypatch.setattr(lifecycle,name,lambda *args:None)
    monkeypatch.setattr(lifecycle,'check_dsn_scope',lambda *args,**kw:None)
    monkeypatch.setattr(lifecycle,'needed_environment',lambda name:'SYNTHETIC')
    monkeypatch.setattr(lifecycle,'time',SimpleNamespace(sleep=lambda _:None))
    class Child:
        next_pid=901
        def __init__(self,*args,**kwargs):self.pid=Child.next_pid;Child.next_pid+=1
        def create_time(self):return 1.0
        def poll(self):return None
    monkeypatch.setattr(psutil,'Popen',Child)
    class Opener:
        def open(self,*args,**kwargs):raise ConnectionRefusedError('SYNTHETIC')
    monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    attempted=[];written=[];write=lifecycle.write_exclusive
    def save(path,value):write(path,value);written.append(path.read_bytes())
    def cleanup(record,*args):attempted.append(record['pid']);return outcomes[len(attempted)-1]
    monkeypatch.setattr(lifecycle,'write_exclusive',save);monkeypatch.setattr(lifecycle,'stop_record',cleanup)
    with pytest.raises(lifecycle.BoundaryError) as failure:lifecycle.start()
    assert len(attempted)==len(set(attempted))==2
    refused='FOREIGN_REFUSED' in outcomes
    assert lifecycle.STATE.exists()==refused
    if refused:assert lifecycle.STATE.read_bytes()==written[0]
    row=diagnostic.parse(diagnostic.command('start',failure.value),'start')
    assert row['boundary_phase']=='health_readiness' and row['boundary_reason']=='READINESS_TIMEOUT'
    assert row.get('cleanup_category')==('BoundaryError' if refused else None)
