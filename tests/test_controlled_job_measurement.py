"""Injected cooperative protocol/entry tests; no native subprocess operation."""
import ctypes
import json
import subprocess
import sys
from types import SimpleNamespace
import pytest
from scripts.windows_ci import controlled_job_measurement as measurement
from scripts.windows_ci import owned_job as job


class State:
    def __init__(self,mode,timed):
        self.mode,self.timed=mode,timed;self.now=10.;self.events=[]
        self.main_stopped=False;self.unrelated_stopped=False;self.primary_closed=False
    def pause(self,seconds):self.now+=seconds


class Reads:
    def __init__(self,state,unrelated=False):self.state,self.unrelated=state,unrelated
    def identity(self,handle):
        if self.unrelated:
            assert handle in (701,704);self.state.events.append('unrelated_identity')
            return 703,21.,self.signal(handle)
        assert handle==909;self.state.events.append('target_identity')
        if self.state.mode=='identity_unknown':return 404,float('nan'),'LIVE'
        return 404,20.,self.signal(handle)
    def membership(self,process,handle):
        assert (process,handle)==((704,700) if self.unrelated else (909,101))
        self.state.events.append('unrelated_member' if self.unrelated else 'target_member')
        return self.unrelated or self.state.mode!='non_member'
    def active_processes(self,handle):
        return 0 if (self.state.unrelated_stopped if self.unrelated else self.state.main_stopped) else 2
    def signal(self,process):
        stopped=self.state.unrelated_stopped if self.unrelated else self.state.main_stopped
        if not self.unrelated and self.state.mode=='signal_unknown' and stopped:return 'UNKNOWN'
        if not self.unrelated and self.state.mode=='still_live':return 'LIVE'
        return 'SIGNALED' if stopped else 'LIVE'


class Kernel:
    def __init__(self,state,unrelated=False):self.state,self.unrelated=state,unrelated
    def GetProcessId(self,process):return 703 if self.unrelated else 321
    def AssignProcessToJobObject(self,*args):return 1
    def IsProcessInJob(self,process,handle,ptr):
        ctypes.cast(ptr,ctypes.POINTER(job.BOOL)).contents.value=1;return 1
    def ResumeThread(self,*args):return 1
    def TerminateJobObject(self,handle,code):
        self.state.events.append('stop_unrelated' if self.unrelated else 'stop_main')
        if not self.unrelated and self.state.mode=='terminate_fail':return 0
        if self.unrelated:self.state.unrelated_stopped=True
        else:self.state.main_stopped=True
        return 1
    def QueryInformationJobObject(self,handle,kind,ptr,size,length):
        if not self.unrelated and self.state.mode=='query_fail':raise job.OwnedJobError('JOB_QUERY_REFUSED')
        ctypes.cast(ptr,ctypes.POINTER(job.Accounting)).contents.ActiveProcesses=0
        ctypes.cast(length,ctypes.POINTER(job.DWORD)).contents.value=size
        return 1


class Primary(measurement.MeasurementBackend):
    def __init__(self,state,record,ack,timed):
        self.state=state;self.record,self.ack,self.timed=record,ack,timed
        self.coordinator=505;self.transferred=None;self.kernel=Kernel(state);self.reads=Reads(state)
        self.win=SimpleNamespace(WAIT_TIMEOUT=258,WAIT_OBJECT_0=0,
            WaitForSingleObject=self.native_wait,GetExitCodeProcess=lambda handle:17)
    def native_wait(self,handle,milliseconds):
        if self.timed:
            self.state.now+=milliseconds/1000;return 258
        return 0
    def create_job(self):return 101
    def launch(self,*args):self.state.events.append('created_parent');return 202,303,321
    def read_record(self):
        if self.state.mode=='handshake_timeout':return None
        if self.state.mode=='bad_record':return {'version':1,'handle':202,'pid':404,'ticks':116444736200000000}
        # Mock parent's actual transfer, not a native creation claim.
        self.state.events.append('cooperative_transfer')
        return {'version':1,'handle':909,'pid':404,'ticks':116444736200000000}
    def acknowledge(self):self.state.events.append('ack_verified_target')
    def close(self,handle):
        if handle in (303,202,101):
            self.state.events.append('close_own_'+str(handle));self.state.primary_closed=True
        elif handle==909:
            assert self.state.primary_closed;self.state.events.append('close_borrowed_target')
        elif handle==505:self.state.events.append('close_coordinator_capability')
        else:raise AssertionError('unexpected handle')


class Unrelated(job.WindowsBackend):
    def __init__(self,state):self.state=state;self.kernel=Kernel(state,True);self.reads=Reads(state,True)
    def create_job(self):return 700
    def launch(self,*args):self.state.events.append('created_unrelated');return 701,702,703
    def duplicate_readonly(self,process):assert process==701;return 704
    def close(self,handle):self.state.events.append('close_unrelated_'+str(handle))


class Factory:
    def __init__(self,state):self.state=state
    def backend(self):return Unrelated(self.state)
    def main(self,*args):return Primary(self.state,*args)


@pytest.mark.parametrize('timed',[False,True])
@pytest.mark.parametrize('mode',['good','still_live','signal_unknown','identity_unknown','non_member','bad_record','handshake_timeout','terminate_fail','query_fail'])
def test_controlled_entry_protocol_actual_production_cleanup(tmp_path,monkeypatch,timed,mode):
    state=State(mode,timed)
    monkeypatch.setattr(measurement.time,'monotonic',lambda:state.now)
    monkeypatch.setattr(measurement.time,'sleep',state.pause)
    row=measurement.execute_case(timed,executable=sys.executable,directory=tmp_path,
                                  environment={},factory=Factory(state))
    assert row['status']==('PASS' if mode=='good' else 'FAIL')
    if mode in ('good','still_live','signal_unknown','terminate_fail','query_fail'):
        assert row['primary']==('TIMEOUT' if timed else 'EXIT17')
        assert row['observation']['scope']=='EXACT_PROCESS_ONLY'
        assert row['observation']['status']==('PASS' if mode=='good' else 'FAIL')
    assert row['unrelated']=='LIVE' and row['unrelated_cleanup']=='OWNED_TREE_STOPPED'
    assert row['transfer_closed'] is (mode not in ('bad_record','handshake_timeout'))
    assert state.events.index('stop_main')<state.events.index('stop_unrelated')
    assert state.events.index('unrelated_identity')<state.events.index('stop_unrelated')
    if 'close_borrowed_target' in state.events:
        assert state.events.index('close_own_101')<state.events.index('close_borrowed_target')
    text=json.dumps(row)
    assert str(tmp_path) not in text and '909' not in text and '505' not in text
    if mode=='good':assert state.events.index('target_member')<state.events.index('ack_verified_target')


def test_explicit_entry_does_not_default_run_native(capsys):
    assert measurement.main([])==2
    assert json.loads(capsys.readouterr().out)['status']=='NOT_RUN'


def test_project_observation_rejects_or_drops_private_fields():
    value={'scope':'EXACT_PROCESS_ONLY','status':'PASS','reason':'EXACT_PROCESS_SIGNALED',
           'sample_count':3,'samples':[{'stage':stage,'membership':'MEMBER',
            'accounting':'NONZERO' if index==0 else 'ZERO',
            'signal':'LIVE' if index==0 else 'SIGNALED','pid':123,'path':'private'}
            for index,stage in enumerate(('BEFORE_TERMINATE','AFTER_TERMINATE','ACCOUNTING_ZERO'))],
           'handle':909}
    result=measurement.project_observation(value)
    assert result is not None and 'private' not in json.dumps(result) and 'pid' not in json.dumps(result)
    value['samples'][0]['signal']='private'
    assert measurement.project_observation(value) is None


def test_atomic_ack_existing_bytes_are_not_overwritten(tmp_path):
    path=tmp_path/'ack'
    measurement.publish_exclusive(path,b'ACK')
    assert path.read_bytes()==b'ACK' and not path.with_suffix('.tmp').exists()
    with pytest.raises(FileExistsError):measurement.publish_exclusive(path,b'OTHER')
    assert path.read_bytes()==b'ACK' and not path.with_suffix('.tmp').exists()


def test_ack_becomes_visible_only_after_complete_write(tmp_path,monkeypatch):
    real_link=measurement.os.link;path=tmp_path/'ack'
    def link(source,destination):
        assert not destination.exists() and source.read_bytes()==b'ACK'
        real_link(source,destination)
    monkeypatch.setattr(measurement.os,'link',link)
    measurement.publish_exclusive(path,b'ACK')
    assert path.read_bytes()==b'ACK'
    assert 'os.link(temporary,record)' in measurement.PARENT


def test_private_root_refusal_is_fixed_json(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(measurement.sys,'platform','win32')
    monkeypatch.setattr(measurement.sys,'version_info',(3,12))
    monkeypatch.setenv('RUNNER_TEMP',str(tmp_path/'private-secret'))
    assert measurement.main(['--run-controlled','--private-root',str(tmp_path)])==2
    output=capsys.readouterr()
    assert json.loads(output.out)['status']=='PRIVATE_ROOT_REFUSED' and not output.err
    assert str(tmp_path) not in output.out


def test_private_directory_error_is_fixed_json(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(measurement.sys,'platform','win32')
    monkeypatch.setattr(measurement.sys,'version_info',(3,12))
    monkeypatch.setenv('RUNNER_TEMP',str(tmp_path))
    def refused(*args,**kwargs):raise OSError('private path and credential')
    monkeypatch.setattr(measurement.tempfile,'TemporaryDirectory',refused)
    assert measurement.main(['--run-controlled','--private-root',str(tmp_path)])==1
    output=capsys.readouterr()
    assert json.loads(output.out)['status']=='PRIVATE_SETUP_REFUSED' and not output.err
    assert 'private path' not in output.out


def test_cleanup_output_poison_cannot_be_public(tmp_path,monkeypatch):
    state=State('good',False)
    monkeypatch.setattr(measurement.time,'monotonic',lambda:state.now)
    monkeypatch.setattr(measurement.time,'sleep',state.pause)
    class PoisonUnrelated(Unrelated):
        def stop_tree(self,handle):super().stop_tree(handle);return 'private credential path'
    class PoisonPrimary(Primary):
        def release_transfer(self):super().release_transfer();return 'private credential path'
    class PoisonFactory(Factory):
        def backend(self):return PoisonUnrelated(self.state)
        def main(self,*args):return PoisonPrimary(self.state,*args)
    row=measurement.execute_case(False,executable=sys.executable,directory=tmp_path,
                                 environment={},factory=PoisonFactory(state))
    assert row['status']=='FAIL' and row['transfer_closed'] is False
    assert row['unrelated_cleanup']=='UNKNOWN' and 'credential' not in json.dumps(row)


def test_special_launcher_inherits_only_stdio_and_transfer_capability(tmp_path,monkeypatch):
    duplicated=[];closed=[];created=[]
    class Win:
        DUPLICATE_SAME_ACCESS=2;STARTF_USESTDHANDLES=0x100
        def GetCurrentProcess(self):return -1
        def DuplicateHandle(self,*args):
            assert args[4] is True;duplicated.append(args);return 1000+len(duplicated)
        def CreateProcess(self,*args):created.append(args);return 202,303,321,0
    backend=measurement.MeasurementBackend.__new__(measurement.MeasurementBackend)
    backend.win=Win();backend.crt=SimpleNamespace(get_osfhandle=lambda descriptor:descriptor)
    backend.coordinator=505;backend.record=tmp_path/'record';backend.ack=tmp_path/'ack';backend.timed=False
    backend.close=closed.append
    monkeypatch.setattr(subprocess,'STARTUPINFO',lambda:SimpleNamespace(),raising=False)
    with (tmp_path/'out').open('wb') as out,(tmp_path/'err').open('wb') as err:
        assert backend.launch([sys.executable],tmp_path,{},out,err)==(202,303,321)
    assert len(duplicated)==4 and duplicated[-1][1]==505
    assert created[0][8].lpAttributeList=={'handle_list':[1001,1002,1003,1004]}
    assert created[0][4] is True and created[0][5]==0x80404
    assert closed==[1001,1002,1003,1004]
    compile(measurement.PARENT,'controlled-parent','exec')
    assert 'False,0x404' in measurement.PARENT # Leaf inherits no coordinator or job handles.
    assert '0x101000,False,0' in measurement.PARENT # Remote leaf handle only drops rights.


def test_transfer_close_failure_remains_fail_and_closes_capability():
    backend=measurement.MeasurementBackend.__new__(measurement.MeasurementBackend)
    backend.transferred=909;backend.coordinator=505;closed=[]
    def close(handle):
        closed.append(handle)
        if handle==909:raise OSError('private credential')
    backend.close=close
    assert backend.release_transfer() is False and closed==[909,505]


@pytest.mark.parametrize('resume,wait,expected',[(1,0,17),(0,0,None),(0,258,125)])
def test_actual_parent_source_uses_declared_api_and_exact_cleanup(tmp_path,monkeypatch,resume,wait,expected):
    events=[];record=tmp_path/'record';ack=tmp_path/'ack';ack.write_bytes(b'ACK')
    class Function:
        def __init__(self,fn):self.fn=fn
        def __call__(self,*args):return self.fn(*args)
    def process_times(process,*times):
        assert process==202
        ticks=116444736200000000
        times[0]._obj.low=ticks&0xffffffff;times[0]._obj.high=ticks>>32
        return 1
    def resume_thread(thread):assert thread==303;events.append('resume_exact');return resume
    kernel=SimpleNamespace(GetProcessTimes=Function(process_times),ResumeThread=Function(resume_thread))
    def create(*args):
        assert args[4] is False and args[5]==0x404
        events.append('create_real_child_protocol');return 202,303,404,0
    def duplicate(source,process,coordinator,access,inherit,options):
        assert (process,coordinator,access,inherit,options)==(202,505,0x101000,False,0)
        events.append('duplicate_query_sync');return 909
    def terminate(process,code):assert (process,code)==(202,125);events.append('terminate_creation_handle')
    def wait_for(process,ms):assert (process,ms)==(202,5000);events.append('wait_exact');return wait
    win=SimpleNamespace(CreateProcess=create,DuplicateHandle=duplicate,GetCurrentProcess=lambda:-1,
        CloseHandle=lambda h:events.append('close_'+str(h)),TerminateProcess=terminate,
        WaitForSingleObject=wait_for,WAIT_OBJECT_0=0)
    monkeypatch.setitem(sys.modules,'_winapi',win)
    monkeypatch.setattr(ctypes,'WinDLL',lambda *args,**kwargs:kernel,raising=False)
    monkeypatch.setattr(subprocess,'STARTUPINFO',lambda:SimpleNamespace(),raising=False)
    monkeypatch.setattr(sys,'argv',['controlled-parent',str(record),str(ack),'505','EXIT17'])
    namespace={}
    if expected is None:
        with pytest.raises(RuntimeError):exec(compile(measurement.PARENT,'controlled-parent','exec'),namespace)
    else:
        with pytest.raises(SystemExit) as exited:exec(compile(measurement.PARENT,'controlled-parent','exec'),namespace)
        assert exited.value.code==expected
    assert kernel.ResumeThread.argtypes==[ctypes.c_void_p] and kernel.ResumeThread.restype is ctypes.c_uint32
    assert kernel.GetProcessTimes.argtypes[0] is ctypes.c_void_p
    assert kernel.GetProcessTimes.restype is ctypes.c_int32 and ctypes.sizeof(namespace['FT'])==8
    assert events[-3:]==['close_303','close_202','close_505']
    assert ('terminate_creation_handle' in events)==(resume!=1)
    assert json.loads(record.read_bytes())['handle']==909 and not record.with_suffix('.tmp').exists()


@pytest.mark.parametrize('kind',['junction','reparse'])
def test_private_root_reparse_boundary_fixed_refusal(tmp_path,monkeypatch,capsys,kind):
    monkeypatch.setattr(measurement.sys,'platform','win32')
    monkeypatch.setattr(measurement.sys,'version_info',(3,12))
    monkeypatch.setenv('RUNNER_TEMP',str(tmp_path))
    real_stat=measurement.Path.stat
    monkeypatch.setattr(measurement.Path,'is_junction',lambda self:kind=='junction')
    if kind=='reparse':
        def metadata(path,*args,**kwargs):
            original=real_stat(path,*args,**kwargs)
            if path==tmp_path:
                return SimpleNamespace(st_mode=original.st_mode,
                    st_file_attributes=measurement.stat.FILE_ATTRIBUTE_REPARSE_POINT)
            return original
        monkeypatch.setattr(measurement.Path,'stat',metadata)
    assert measurement.main(['--run-controlled','--private-root',str(tmp_path)])==2
    captured=capsys.readouterr()
    assert json.loads(captured.out)['status']=='PRIVATE_ROOT_REFUSED' and captured.err==''
    assert str(tmp_path) not in captured.out


def test_valid_private_root_enters_both_case_stages(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(measurement.sys,'platform','win32')
    monkeypatch.setattr(measurement.sys,'version_info',(3,12))
    monkeypatch.setenv('RUNNER_TEMP',str(tmp_path))
    monkeypatch.setenv('PRIVATE_TOKEN','must-not-inherit')
    monkeypatch.setenv('HTTPS_PROXY','must-not-inherit')
    monkeypatch.setattr(measurement,'NativeFactory',lambda:None)
    stages=[]
    def case(timed,*,executable,directory,environment,factory):
        assert directory.parent==tmp_path and directory.is_dir()
        assert measurement.Path(executable).is_absolute()
        assert 'PRIVATE_TOKEN' not in environment and 'HTTPS_PROXY' not in environment
        stages.append(timed)
        return {'status':'PASS','case':'PARENT_TIMEOUT' if timed else 'PARENT_EXIT17'}
    monkeypatch.setattr(measurement,'execute_case',case)
    assert measurement.main(['--run-controlled','--private-root',str(tmp_path)])==0
    captured=capsys.readouterr();value=json.loads(captured.out)
    assert stages==[False,True] and len(value['results'])==2 and captured.err==''
    assert str(tmp_path) not in captured.out and 'must-not-inherit' not in captured.out


@pytest.mark.parametrize('argv',[['--PRIVATE_TOKEN=secret'],['--private-root'],['--run-controlle'],['--help','PRIVATE_TOKEN']])
def test_poison_cli_arguments_fixed_safe_refusal(argv,capsys):
    assert measurement.main(argv)==2
    captured=capsys.readouterr()
    assert json.loads(captured.out)=={'scope':'CONTROLLED_NATIVE_JOB_MEASUREMENT','status':'ARGUMENTS_REFUSED'}
    assert captured.err=='' and 'PRIVATE_TOKEN' not in captured.out and 'secret' not in captured.out


@pytest.mark.parametrize('fault',['EMPTY','SINGLE','WRONG_ORDER','ALREADY_SIGNALED','NON_MEMBER','FINAL_LIVE','FALSE_REASON'])
def test_pass_projection_requires_live_before_and_complete_timeline(fault):
    samples=[{'stage':stage,'membership':'MEMBER','accounting':'ZERO',
              'signal':'LIVE' if index==0 else 'SIGNALED'}
             for index,stage in enumerate(('BEFORE_TERMINATE','AFTER_TERMINATE','ACCOUNTING_ZERO'))]
    if fault=='EMPTY':samples=[]
    elif fault=='SINGLE':samples=samples[-1:]
    elif fault=='WRONG_ORDER':samples[0],samples[1]=samples[1],samples[0]
    elif fault=='ALREADY_SIGNALED':samples[0]['signal']='SIGNALED'
    elif fault=='NON_MEMBER':samples[0]['membership']='NON_MEMBER'
    elif fault=='FINAL_LIVE':samples[-1]['signal']='LIVE'
    value={'scope':'EXACT_PROCESS_ONLY','status':'PASS','reason':'READ_UNKNOWN' if fault=='FALSE_REASON' else 'EXACT_PROCESS_SIGNALED','sample_count':len(samples),'samples':samples}
    assert measurement.project_observation(value) is None
