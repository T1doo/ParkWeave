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


@pytest.mark.parametrize('invalid',[0,-1,True,1<<64,1<<128])
def test_readonly_job_candidate_refuses_invalid_handles_before_any_read(invalid):
    from scripts.windows_ci.job_stop_observation import observe
    class NoRead:
        def __getattr__(self,name):raise AssertionError('invalid handle reached backend')
    for process,job in ((invalid,1),(1,invalid)):
        row=observe(process,job,cleanup_started=10,clock=lambda:10,backend=NoRead())
        assert row=={'status':'UNKNOWN','reason':'INVALID_INPUT','sample_count':0,'samples':[]}


@pytest.mark.parametrize('primary',[0,17,'timeout'])
@pytest.mark.parametrize('mode',['signal_later','live','unknown','non_member'])
def test_eng073_unwired_adapter_exact_gold_and_close_order(tmp_path,primary,mode):
    """Only injected handles and reads; no Windows/process/termination operation."""
    from scripts.windows_ci.job_stop_observation import StopObservationAdapter
    class Candidate:
        def __init__(self):
            self.events=[];self.now=10.;self.row=None;self.reads=0
        def clock(self):return self.now
        def pause(self,seconds):self.now+=seconds
        def create_job(self):return 101
        def launch(self,*args):return 202,303,404
        def bind(self,*args):self.events.append('bind_before_resume')
        def resume(self,*args):self.events.append('resume')
        def wait(self,*args):
            if primary=='timeout':raise subprocess.TimeoutExpired('OWNED_JOB',1)
            return primary
        def membership(self,*args):
            self.events.append('readonly_member');return mode!='non_member'
        def active_processes(self,*args):
            self.events.append('readonly_accounting');return 2 if self.reads==0 else 0
        def signal(self,*args):
            self.events.append('readonly_signal');self.reads+=1
            if mode=='unknown':return 'UNKNOWN'
            return 'SIGNALED' if mode=='signal_later' and self.reads>=4 else 'LIVE'
        def stop_tree(self,job):
            observer=StopObservationAdapter(202,job,cleanup_started=self.now,
                    backend=self,clock=self.clock,pause=self.pause)
            observer.capture('BEFORE_TERMINATE')
            self.events.append('existing_termination_mock')
            observer.capture('AFTER_TERMINATE')
            observer.capture('ACCOUNTING_ZERO')
            self.row=observer.finish();self.events.append('exact_gold_before_close')
            # Test-only coordinator projection; exact PASS never becomes tree PASS.
            if self.row['status']!='PASS':raise JOB.OwnedJobError('JOB_STOP_UNCONFIRMED')
            return 'OWNED_TREE_STOP_UNCONFIRMED'
        def close(self,handle):self.events.append('close_'+str(handle))
    backend=Candidate()
    if primary=='timeout':
        with pytest.raises(subprocess.TimeoutExpired) as failed:injected(tmp_path,backend)
        assert failed.value.cleanup=='OWNED_TREE_STOP_UNCONFIRMED'
    elif primary==0 and mode!='signal_later':
        with pytest.raises(JOB.OwnedJobError) as failed:injected(tmp_path,backend)
        assert failed.value.cleanup=='OWNED_TREE_STOP_UNCONFIRMED'
    else:
        result=injected(tmp_path,backend)
        assert result.returncode==primary and result.cleanup=='OWNED_TREE_STOP_UNCONFIRMED'
    assert backend.row['scope']=='EXACT_PROCESS_ONLY'
    assert backend.row['status']==('PASS' if mode=='signal_later' else 'FAIL')
    assert backend.events[-4:]==['exact_gold_before_close','close_303','close_202','close_101']
    assert backend.now<15 and backend.row['sample_count']<=8
    if mode=='signal_later':
        assert backend.row['samples'][2]['signal']=='LIVE'
        assert backend.row['samples'][-1]['signal']=='SIGNALED'


@pytest.mark.parametrize('elapsed',[5,6])
def test_eng073_adapter_does_not_refresh_expired_cleanup_budget(elapsed):
    from scripts.windows_ci.job_stop_observation import StopObservationAdapter
    class NoRead:
        def __getattr__(self,name):raise AssertionError('expired budget reached backend')
    observer=StopObservationAdapter(1,2,cleanup_started=10,backend=NoRead(),clock=lambda:10+elapsed)
    for stage in observer.STAGES:observer.capture(stage)
    row=observer.finish()
    assert row['status']=='FAIL' and row['reason']=='DEADLINE' and row['sample_count']==0


def test_eng073_adapter_rejects_missing_before_termination_hook():
    from scripts.windows_ci.job_stop_observation import StopObservationAdapter
    observer=StopObservationAdapter(1,2,cleanup_started=10,backend=object(),clock=lambda:10)
    observer.capture('AFTER_TERMINATE')
    assert observer.finish()['reason']=='STAGE_REFUSED'


def test_eng073_accounting_zero_hook_requires_actual_zero():
    from scripts.windows_ci.job_stop_observation import StopObservationAdapter
    class Backend:
        def membership(self,*args):return True
        def active_processes(self,*args):return 1
        def signal(self,*args):return 'SIGNALED'
    observer=StopObservationAdapter(1,2,cleanup_started=10,backend=Backend(),clock=lambda:10)
    for stage in observer.STAGES:observer.capture(stage)
    assert observer.finish()['reason']=='STAGE_REFUSED'


def test_eng073_finish_rechecks_original_deadline_after_signal():
    from scripts.windows_ci.job_stop_observation import StopObservationAdapter
    class Backend:
        def membership(self,*args):return True
        def active_processes(self,*args):return 0
        def signal(self,*args):return 'SIGNALED'
    now=[10.]
    observer=StopObservationAdapter(1,2,cleanup_started=10,backend=Backend(),clock=lambda:now[0])
    for stage in observer.STAGES:observer.capture(stage)
    now[0]=15.
    row=observer.finish()
    assert row['status']=='FAIL' and row['reason']=='DEADLINE'


@pytest.mark.parametrize('primary',[0,17,'timeout'])
@pytest.mark.parametrize('mode',['signal_later','live','unknown','non_member','wrong_identity','parent_target','parent_identity','thread_target','job_target'])
def test_eng074_real_stop_tree_optin_exact_handle_and_primary(tmp_path,monkeypatch,primary,mode):
    """Actual production stop_tree + run; only kernel/read calls are injected."""
    from scripts.windows_ci.job_stop_observation import HeldDescendant
    now=[10.];events=[];signals=[0]
    monkeypatch.setattr(JOB.time,'monotonic',lambda:now[0])
    monkeypatch.setattr(JOB.time,'sleep',lambda seconds:now.__setitem__(0,now[0]+seconds))
    class Kernel:
        def TerminateJobObject(self,handle,code):
            assert (handle,code)==(101,124);events.append('terminate_original_job');return 1
        def QueryInformationJobObject(self,handle,kind,ptr,size,length):
            assert (handle,kind,size)==(101,1,48)
            ctypes.cast(ptr,ctypes.POINTER(JOB.Accounting)).contents.ActiveProcesses=0
            events.append('original_query_zero');return 1
    class Reads:
        def identity(self,handle):
            assert handle==909;events.append('same_handle_identity')
            return (405 if mode=='wrong_identity' else 404),20.,'LIVE'
        def membership(self,process,job):
            assert (process,job)==(909,101);events.append('same_handle_membership')
            return mode!='non_member'
        def active_processes(self,job):events.append('readonly_accounting');return 0
        def signal(self,process):
            assert process==909;signals[0]+=1;events.append('same_handle_signal')
            if mode=='unknown':return 'UNKNOWN'
            return 'SIGNALED' if mode=='signal_later' and signals[0]>=4 else 'LIVE'
    class Actual(JOB.WindowsBackend):
        def __init__(self):
            self.kernel=Kernel();self.observation_backend=Reads()
            target_handle={'parent_target':202,'thread_target':303,'job_target':101}.get(mode,909)
            self.observation_target=HeldDescendant(target_handle,
                                                  321 if mode=='parent_identity' else 404,20.)
        def create_job(self):return 101
        def launch(self,*args):return 202,303,321
        def bind(self,*args):events.append('bind')
        def resume(self,*args):events.append('resume')
        def wait(self,*args):
            if primary=='timeout':raise subprocess.TimeoutExpired('OWNED_JOB',1)
            return primary
        def close(self,handle):
            assert self.observation_receipt is not None
            assert handle!=909 # Borrowed descendant is never closed by production.
            events.append('close_'+str(handle))
    backend=Actual();success=mode=='signal_later'
    if primary=='timeout':
        with pytest.raises(subprocess.TimeoutExpired) as failed:injected(tmp_path,backend)
        item=failed.value
    elif primary==0 and not success:
        with pytest.raises(JOB.OwnedJobError) as failed:injected(tmp_path,backend)
        item=failed.value
    else:
        item=injected(tmp_path,backend);assert item.returncode==primary
    assert item.cleanup==('OWNED_TREE_STOPPED' if success else 'OWNED_TREE_STOP_UNCONFIRMED')
    assert item.exact_process_observation['scope']=='EXACT_PROCESS_ONLY'
    assert item.exact_process_observation['status']==('PASS' if success else 'FAIL')
    assert events[-3:]==['close_303','close_202','close_101']
    assert events.count('terminate_original_job')==1 and now[0]<15.
    if mode in ('parent_target','parent_identity','thread_target','job_target'):
        assert 'same_handle_identity' not in events
    if success:
        row=item.exact_process_observation
        assert row['samples'][2]['signal']=='LIVE' and row['samples'][-1]['signal']=='SIGNALED'


@pytest.mark.parametrize('slow_operation',['terminate','query'])
@pytest.mark.parametrize('optin',[False,True])
def test_eng074_real_stop_tree_single_budget_includes_native_call_cost(monkeypatch,slow_operation,optin):
    from scripts.windows_ci.job_stop_observation import HeldDescendant
    now=[10.];events=[]
    monkeypatch.setattr(JOB.time,'monotonic',lambda:now[0])
    monkeypatch.setattr(JOB.time,'sleep',lambda seconds:now.__setitem__(0,now[0]+seconds))
    class Kernel:
        def TerminateJobObject(self,*args):
            events.append('terminate')
            if slow_operation=='terminate':now[0]+=5.
            return 1
        def QueryInformationJobObject(self,handle,kind,ptr,size,length):
            events.append('query')
            if slow_operation=='query':now[0]+=5.
            ctypes.cast(ptr,ctypes.POINTER(JOB.Accounting)).contents.ActiveProcesses=0
            return 1
    class Reads:
        def identity(self,*args):return 404,20.,'LIVE'
        def membership(self,*args):return True
        def active_processes(self,*args):return 0
        def signal(self,*args):return 'SIGNALED'
    backend=JOB.WindowsBackend.__new__(JOB.WindowsBackend);backend.kernel=Kernel()
    if optin:
        backend.observation_target=HeldDescendant(909,404,20.)
        backend.observation_backend=Reads()
    with pytest.raises(JOB.OwnedJobError,match='JOB_STOP_UNCONFIRMED'):backend.stop_tree(101)
    assert now[0]==15. and events.count('terminate')==1
    if slow_operation=='terminate':assert 'query' not in events
    if optin:assert backend.observation_receipt['status']=='FAIL'


def test_eng074_default_stop_tree_remains_without_exact_target(monkeypatch):
    monkeypatch.setattr(JOB.time,'monotonic',lambda:10.)
    class Kernel:
        def TerminateJobObject(self,*args):return 1
        def QueryInformationJobObject(self,handle,kind,ptr,size,length):
            ctypes.cast(ptr,ctypes.POINTER(JOB.Accounting)).contents.ActiveProcesses=0
            return 1
    backend=JOB.WindowsBackend.__new__(JOB.WindowsBackend);backend.kernel=Kernel()
    assert backend.stop_tree(101)=='OWNED_TREE_STOPPED'
    assert backend.observation_receipt is None
