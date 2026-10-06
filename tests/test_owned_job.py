"""Portable contract injection and separately marked native Windows tree probes."""
import ctypes
import importlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest
import psutil

from test_windows_ci_preparation import module

JOB=importlib.import_module('scripts.windows_ci.owned_job')


class FakeBackend:
    """No OS processes: prove ordering, refusal and primary failure preservation."""
    def __init__(self,fail=None,code=17):
        self.fail=fail;self.code=code;self.events=[];self.descendant_alive=False;self.unrelated_alive=True
    def event(self,name):
        self.events.append(name)
        if name==self.fail:raise JOB.OwnedJobError('SYNTHETIC_REFUSAL')
    def create_job(self):self.event('create');return 'job'
    def launch(self,*args):self.event('launch_suspended');return 'process','thread',123
    def bind(self,job,process,pid):
        assert (job,process,pid)==('job','process',123);self.event('bind_verified')
    def resume(self,thread):self.event('resume');self.descendant_alive=True
    def wait(self,process,timeout):
        self.event('wait')
        if self.code=='timeout':raise subprocess.TimeoutExpired('SYNTHETIC',timeout)
        return self.code
    def abort_suspended(self,process):assert not self.descendant_alive;self.event('abort_exact')
    def stop_tree(self,job):
        assert job=='job';self.event('stop_tree');self.descendant_alive=False;return 'OWNED_TREE_STOPPED'
    def close(self,handle):self.event('close_'+handle)


def injected(tmp_path,backend):
    with (tmp_path/'stdout').open('wb') as out,(tmp_path/'stderr').open('wb') as err:
        return JOB.run([sys.executable,'-c','pass'],timeout=1,stdout=out,stderr=err,_backend=backend)


def test_job_contract_binds_before_resume_and_cleans_descendants_without_masking_exit(tmp_path):
    backend=FakeBackend();result=injected(tmp_path,backend)
    assert result.returncode==17 and result.cleanup=='OWNED_TREE_STOPPED'
    assert backend.events==['create','launch_suspended','bind_verified','resume','wait','stop_tree','close_thread','close_process','close_job']
    assert not backend.descendant_alive and backend.unrelated_alive


@pytest.mark.parametrize('fail',['create','launch_suspended','bind_verified','resume'])
def test_job_setup_refusal_never_runs_uncontained_child_or_retries(tmp_path,fail):
    backend=FakeBackend(fail=fail)
    with pytest.raises(JOB.OwnedJobError) as failure:injected(tmp_path,backend)
    assert 'wait' not in backend.events and not backend.descendant_alive and backend.unrelated_alive
    if fail in ('bind_verified','resume'):
        assert failure.value.cleanup=='SUSPENDED_CHILD_STOPPED'
        assert backend.events[-4:]==['abort_exact','close_thread','close_process','close_job']
    else:assert failure.value.cleanup=='NOT_STARTED'
    assert backend.events.count('launch_suspended')<=1


@pytest.mark.parametrize('cleanup_fail',[False,True])
def test_job_timeout_keeps_primary_failure_and_reports_cleanup_separately(tmp_path,cleanup_fail):
    backend=FakeBackend(code='timeout',fail='stop_tree' if cleanup_fail else None)
    with pytest.raises(subprocess.TimeoutExpired) as failure:injected(tmp_path,backend)
    assert failure.value.timeout==1
    assert failure.value.cleanup==('OWNED_TREE_STOP_UNCONFIRMED' if cleanup_fail else 'OWNED_TREE_STOPPED')
    assert backend.events[-3:]==['close_thread','close_process','close_job'] and backend.unrelated_alive


@pytest.mark.parametrize('code',[0,17])
def test_job_cleanup_failure_never_turns_failure_or_success_into_pass(tmp_path,code):
    backend=FakeBackend(code=code,fail='stop_tree')
    if code==0:
        with pytest.raises(JOB.OwnedJobError) as failure:injected(tmp_path,backend)
        assert failure.value.cleanup=='OWNED_TREE_STOP_UNCONFIRMED'
    else:
        result=injected(tmp_path,backend)
        assert result.returncode==17 and result.cleanup=='OWNED_TREE_STOP_UNCONFIRMED'


def test_windows_structures_have_fixed_width_and_expected_pointer_alignment():
    assert ctypes.sizeof(JOB.DWORD)==4 and ctypes.sizeof(JOB.BOOL)==4
    if ctypes.sizeof(ctypes.c_void_p)==8:
        assert ctypes.sizeof(JOB.BasicLimit)==64 and ctypes.sizeof(JOB.ExtendedLimit)==144
    assert ctypes.sizeof(JOB.Accounting)==48


def low_level_backend(monkeypatch,fail_close=None,create_refused=False):
    calls=[]
    class Win:
        STARTF_USESTDHANDLES=0x100;DUPLICATE_SAME_ACCESS=2;WAIT_OBJECT_0=0;WAIT_TIMEOUT=258
        def GetCurrentProcess(self):return 99
        def DuplicateHandle(self,*args):
            handle=100+sum(name=='duplicate' for name,*_ in calls)
            assert args[4] is True;calls.append(('duplicate',handle));return handle
        def CreateProcess(self,*args):
            calls.append(('create_suspended',))
            assert args[0]==sys.executable and args[4] is True and args[5]==0x80404
            startup=args[8]
            assert startup.lpAttributeList=={'handle_list':[100,101,102]}
            assert (startup.hStdInput,startup.hStdOutput,startup.hStdError)==(100,101,102)
            if create_refused:raise OSError('SYNTHETIC_CREATE_REFUSED')
            return 201,202,203,204
        def CloseHandle(self,handle):
            calls.append(('close',handle))
            if handle==fail_close:raise OSError('SYNTHETIC_CLOSE_REFUSED')
        def TerminateProcess(self,handle,code):assert handle==201;calls.append(('abort',handle))
        def WaitForSingleObject(self,handle,ms):assert (handle,ms)==(201,5000);return 0
        def GetExitCodeProcess(self,handle):return 125
    backend=JOB.WindowsBackend.__new__(JOB.WindowsBackend)
    backend.win=Win();backend.crt=SimpleNamespace(get_osfhandle=lambda fd:fd)
    monkeypatch.setattr(JOB.subprocess,'STARTUPINFO',SimpleNamespace,raising=False)
    return backend,calls


@pytest.mark.parametrize('failed_handle',[100,101,102])
def test_launch_stdio_close_failure_after_creation_aborts_exact_child_and_closes_all(tmp_path,monkeypatch,failed_handle):
    backend,calls=low_level_backend(monkeypatch,fail_close=failed_handle)
    with (tmp_path/'out').open('wb') as out,(tmp_path/'err').open('wb') as err:
        with pytest.raises(JOB.OwnedJobError) as failure:backend.launch([sys.executable,'-c','pass'],None,{},out,err)
    assert failure.value.cleanup=='SUSPENDED_CHILD_STOPPED'
    assert [event[1] for event in calls if event[0]=='close']==[100,101,102,202,201]
    assert ('abort',201) in calls


def test_launch_create_refusal_closes_all_acquired_stdio_handles(tmp_path,monkeypatch):
    backend,calls=low_level_backend(monkeypatch,create_refused=True)
    with (tmp_path/'out').open('wb') as out,(tmp_path/'err').open('wb') as err:
        with pytest.raises(OSError):backend.launch([sys.executable,'-c','pass'],None,{},out,err)
    assert calls[-3:]==[('close',100),('close',101),('close',102)] and not any(x[0]=='abort' for x in calls)


@pytest.mark.parametrize('close_refused',[False,True])
def test_job_limit_refusal_closes_new_unnamed_job_and_keeps_cleanup_failure(monkeypatch,close_refused):
    backend,calls=low_level_backend(monkeypatch,fail_close=77 if close_refused else None)
    def create(attributes,name):assert attributes is None and name is None;return 77
    def limits(job,kind,pointer,length):
        assert job==77 and kind==9 and length==ctypes.sizeof(JOB.ExtendedLimit)
        assert ctypes.cast(pointer,ctypes.POINTER(JOB.ExtendedLimit)).contents.BasicLimitInformation.LimitFlags==0x2000
        return 0
    backend.kernel=SimpleNamespace(CreateJobObjectW=create,SetInformationJobObject=limits)
    with pytest.raises(JOB.OwnedJobError) as failure:backend.create_job()
    assert calls==[('close',77)]
    assert getattr(failure.value,'cleanup',None)==('OWNED_TREE_STOP_UNCONFIRMED' if close_refused else None)


def test_tree_cleanup_safe_projection_keeps_timeout_and_rejects_untrusted_metadata():
    diagnostic=module('diagnostics');publisher=module('publish_summary');suite=module('native_suite')
    failure=subprocess.TimeoutExpired('SYNTHETIC_PRIVATE',600)
    failure.parkweave_owned_tree_cleanup='OWNED_TREE_STOP_UNCONFIRMED'
    row=diagnostic.exception_row('full_engineering_regression',failure,'regression_run')
    binding={'synthetic':'binding'};record=suite.summary([row])
    record.update(diagnostic_schema=1,diagnostic_binding=binding,report_state='COMPLETED',active_phase='UNKNOWN')
    public=publisher.project(record,binding);commands,ok=publisher.annotation_commands(public)
    assert ok and public['cases'][0]['category']=='TimeoutExpired'
    assert 'OWNED_TREE_STOP_UNCONFIRMED' in repr(commands) and 'SYNTHETIC_PRIVATE' not in repr(commands)
    record['cases'][0]['owned_tree_cleanup']='SYNTHETIC /secret/path'
    with pytest.raises(ValueError):publisher.project(record,binding)
    assert diagnostic.exception_row('full_engineering_regression',RuntimeError('private'),'regression_run')['status']=='FAIL'


@pytest.mark.parametrize('timeout',[False,True])
def test_native_command_routes_only_suite_into_job_and_preserves_fixed_timeout(tmp_path,monkeypatch,timeout):
    native=module('native_command');calls=[]
    monkeypatch.setattr(native,'os',SimpleNamespace(name='nt',environ={}))
    def run(args,**kwargs):
        calls.append(kwargs)
        assert kwargs['timeout']==900 and kwargs['stdout'].fileno()!=kwargs['stderr'].fileno()
        if timeout:
            failure=subprocess.TimeoutExpired('SYNTHETIC_PRIVATE',900);failure.cleanup='OWNED_TREE_STOP_UNCONFIRMED';raise failure
        return SimpleNamespace(returncode=17,cleanup='OWNED_TREE_STOPPED')
    monkeypatch.setattr(native,'run_owned_job',run)
    result=native.execute(sys.executable,['-c','pass'],'native_suite',900,tmp_path)
    assert len(calls)==1 and result['exit_code']==(124 if timeout else 17) and result['timed_out']==timeout
    assert result['cleanup']==('OWNED_TREE_STOP_UNCONFIRMED' if timeout else 'OWNED_TREE_STOPPED')
    # Other commands preserve their prior direct-child route.
    result=native.execute(sys.executable,['-c','raise SystemExit(7)'],'pg_status',5,tmp_path)
    assert result['exit_code']==7 and len(calls)==1


def test_native_regression_uses_job_regular_files_existing_environment_and_600_seconds(tmp_path,monkeypatch):
    suite=module('native_suite');env={'SYNTHETIC':'isolated'};calls=[]
    monkeypatch.setattr(suite,'os',SimpleNamespace(name='nt'))
    def run(args,**kwargs):calls.append((args,kwargs));return SimpleNamespace(returncode=17,cleanup='OWNED_TREE_STOPPED')
    monkeypatch.setattr(suite,'run_owned_job',run)
    result=suite.run_regression(sys.executable,tmp_path/'report.json',tmp_path/'progress.json',env)
    assert result.returncode==17 and len(calls)==1
    args,kwargs=calls[0]
    assert args[1]=='scripts/run_acceptance.py' and kwargs['timeout']==600 and kwargs['env'] is env
    assert 'capture_output' not in kwargs and kwargs['stdout'].closed and kwargs['stderr'].closed
    assert len(list(tmp_path.glob('*.stdout')))==1 and len(list(tmp_path.glob('*.stderr')))==1


def recorded_child_alive(data,*,backend=None,process_factory=psutil.Process):
    # Retained Windows PIDs can still be is_running after kernel termination.
    # Observe the exact handle; unknown/open/read/close failures remain failures.
    def valid_time(value):return type(value) in (int,float) and math.isfinite(value) and value>0
    if type(data['pid']) is not int or data['pid']<=0 or not valid_time(data['created']):
        raise AssertionError('recorded identity unavailable')
    try:owned=process_factory(data['pid'])
    except psutil.NoSuchProcess:return False
    observed=owned.create_time()
    if not valid_time(observed):raise AssertionError('observed creation time unavailable')
    if observed!=data['created']:return False
    if backend is None and os.name!='nt':
        return owned.is_running() and owned.status()!=psutil.STATUS_ZOMBIE
    if backend is None:
        from scripts.windows.server_identity import WindowsBackend
        backend=WindowsBackend()
    handle=backend.open(data['pid'])
    try:
        pid,created,alive=backend.identity(handle)
        if type(pid) is not int or pid<=0 or not valid_time(created):
            raise AssertionError('kernel identity unavailable')
        if pid!=data['pid'] or abs(created-data['created'])>0.00001:
            raise AssertionError('recorded process identity changed during observation')
        if type(alive) is not bool:raise AssertionError('kernel liveness unavailable')
        return alive
    finally:backend.close(handle)


@pytest.mark.parametrize('alive',[False,True])
def test_recorded_child_liveness_uses_exact_kernel_handle_not_retained_pid(alive):
    events=[]
    class Backend:
        def open(self,pid):assert pid==123;events.append('open');return 'exact'
        def identity(self,h):assert h=='exact';events.append('read');return 123,10.0,alive
        def close(self,h):assert h=='exact';events.append('close')
    process=SimpleNamespace(create_time=lambda:10.0,is_running=lambda:True)
    assert recorded_child_alive({'pid':123,'created':10.0},backend=Backend(),process_factory=lambda pid:process) is alive
    assert events==['open','read','close']


@pytest.mark.parametrize('fault',['open','read','close','pid','created','unknown'])
def test_recorded_child_liveness_unknown_never_passes_as_stopped(fault):
    events=[]
    class Backend:
        def open(self,pid):
            events.append('open')
            if fault=='open':raise OSError('refused')
            return 'exact'
        def identity(self,h):
            events.append('read')
            if fault=='read':raise OSError('refused')
            return (124 if fault=='pid' else 123,11.0 if fault=='created' else 10.0,None if fault=='unknown' else False)
        def close(self,h):
            events.append('close')
            if fault=='close':raise OSError('refused')
    with pytest.raises((OSError,AssertionError)):
        recorded_child_alive({'pid':123,'created':10.0},backend=Backend(),process_factory=lambda pid:SimpleNamespace(create_time=lambda:10.0))
    assert ('close' in events)==(fault!='open')


@pytest.mark.skipif(os.name!='nt',reason='native Windows JobObject required; Linux/mock is not coverage')
@pytest.mark.parametrize('timeout',[False,True])
def test_native_job_stops_owned_descendant_and_preserves_unrelated_and_primary(tmp_path,timeout):
    record=tmp_path/'owned-child.json'
    child='import time;time.sleep(30)'
    parent='import subprocess,sys,json,pathlib,psutil,time; p=subprocess.Popen([sys.executable,"-c",'+repr(child)+']); pathlib.Path('+repr(str(record))+').write_text(json.dumps({"pid":p.pid,"created":psutil.Process(p.pid).create_time()})); '+('time.sleep(30)' if timeout else 'raise SystemExit(17)')
    unrelated=subprocess.Popen([sys.executable,'-c',child])
    try:
        with (tmp_path/'out').open('wb') as out,(tmp_path/'err').open('wb') as err:
            if timeout:
                with pytest.raises(subprocess.TimeoutExpired) as failure:
                    JOB.run([sys.executable,'-c',parent],timeout=2,stdout=out,stderr=err)
                assert failure.value.cleanup=='OWNED_TREE_STOPPED'
            else:
                result=JOB.run([sys.executable,'-c',parent],timeout=5,stdout=out,stderr=err)
                assert result.returncode==17
                assert result.cleanup=='OWNED_TREE_STOPPED'
        data=json.loads(record.read_text())
        assert unrelated.poll() is None
        # No killing by recorded PID: the kernel job already owns termination.
        assert not recorded_child_alive(data)
    finally:
        unrelated.terminate();unrelated.wait(timeout=5)


@pytest.mark.skipif(os.name!='nt',reason='native Windows suspended creation required')
def test_native_job_binding_refusal_stops_exact_suspended_child_before_body(tmp_path):
    marker=tmp_path/'body-ran'
    class Refusing(JOB.WindowsBackend):
        def bind(self,*args):raise JOB.OwnedJobError('SYNTHETIC_BIND_REFUSED')
    with (tmp_path/'out').open('wb') as out,(tmp_path/'err').open('wb') as err:
        with pytest.raises(JOB.OwnedJobError) as failure:
            JOB.run([sys.executable,'-c','import pathlib;pathlib.Path('+repr(str(marker))+').touch()'],timeout=2,stdout=out,stderr=err,_backend=Refusing())
    assert failure.value.cleanup=='SUSPENDED_CHILD_STOPPED' and not marker.exists()


@pytest.mark.skipif(os.name!='nt',reason='native Windows last-job-handle closure required')
def test_native_job_coordinator_abrupt_exit_closes_job_and_stops_tree(tmp_path):
    record=tmp_path/'owned-descendant.json'
    child='import time;time.sleep(30)'
    parent='import subprocess,sys,json,pathlib,psutil,time; p=subprocess.Popen([sys.executable,"-c",'+repr(child)+']); r=pathlib.Path('+repr(str(record))+'); t=r.with_suffix(".tmp"); t.write_text(json.dumps({"pid":p.pid,"created":psutil.Process(p.pid).create_time()})); t.replace(r); time.sleep(30)'
    code='''import os,sys,time,threading,pathlib
from scripts.windows_ci.owned_job import run
record=pathlib.Path('''+repr(str(record))+''')
def abrupt():
 deadline=time.monotonic()+8
 while not record.exists() and time.monotonic()<deadline:time.sleep(.01)
 os._exit(42 if record.exists() else 43)
threading.Thread(target=abrupt,daemon=True).start()
with open('''+repr(str(tmp_path/'out'))+''','wb') as out,open('''+repr(str(tmp_path/'err'))+''','wb') as err:
 run([sys.executable,'-c','''+repr(parent)+'''],timeout=20,stdout=out,stderr=err)
'''
    unrelated=subprocess.Popen([sys.executable,'-c',child]);controller=None
    try:
        controller=subprocess.Popen([sys.executable,'-c',code],cwd=Path(__file__).resolve().parents[1])
        assert controller.wait(timeout=10)==42 and unrelated.poll() is None
        data=json.loads(record.read_text());deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if not recorded_child_alive(data):break
            time.sleep(.01)
        else:pytest.fail('owned descendant exit unconfirmed after coordinator handle closure')
    finally:
        if controller is not None and controller.poll() is None:controller.kill();controller.wait(timeout=5)
        unrelated.terminate();unrelated.wait(timeout=5)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),True,None,0])
@pytest.mark.parametrize('source',['record','process','kernel'])
def test_recorded_child_invalid_creation_time_never_means_stopped(value,source):
    calls=[]
    class Backend:
        def open(self,pid):calls.append('open');return 'exact'
        def identity(self,h):return 123,value if source=='kernel' else 10.0,False
        def close(self,h):calls.append('close')
    record={'pid':123,'created':value if source=='record' else 10.0}
    process=SimpleNamespace(create_time=lambda:value if source=='process' else 10.0)
    with pytest.raises(AssertionError):recorded_child_alive(record,backend=Backend(),process_factory=lambda pid:process)
    assert calls==(['open','close'] if source=='kernel' else [])
