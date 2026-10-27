"""Explicit ENG077 native cooperative parent/leaf measurement; never a CI default.

The parent creates the leaf and transfers only a query/synchronize handle to
its coordinator through a separately inherited PROCESS_DUP_HANDLE capability.
No PID discovery/OpenProcess, owner operation or privilege adjustment occurs.
Private bounded records are not public receipts. Linux injection is not native.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import stat
import sys
import tempfile
import time

if __package__:
    from .owned_job import WindowsBackend, OwnedJobError, run
    from .job_stop_observation import HeldDescendant, ReadOnlyBackend, MAX_HANDLE
else:
    from owned_job import WindowsBackend, OwnedJobError, run
    from job_stop_observation import HeldDescendant, ReadOnlyBackend, MAX_HANDLE

QUERY_SYNC = 0x101000
PROCESS_DUP_HANDLE = 0x40
PARENT = r'''
import ctypes,json,os,pathlib,subprocess,sys,time,_winapi
record,ack=map(pathlib.Path,sys.argv[1:3]);coordinator=int(sys.argv[3]);timed=sys.argv[4]=='TIMEOUT'
p=t=None;accepted=False
try:
 startup=subprocess.STARTUPINFO()
 p,t,pid,_=_winapi.CreateProcess(sys.executable,subprocess.list2cmdline([sys.executable,'-c','import time;time.sleep(30)']),None,None,False,0x404,None,None,startup)
 class FT(ctypes.Structure):_fields_=[('low',ctypes.c_uint32),('high',ctypes.c_uint32)]
 k=ctypes.WinDLL('kernel32',use_last_error=True);k.GetProcessTimes.argtypes=[ctypes.c_void_p]+[ctypes.POINTER(FT)]*4;k.GetProcessTimes.restype=ctypes.c_int32
 k.ResumeThread.argtypes=[ctypes.c_void_p];k.ResumeThread.restype=ctypes.c_uint32
 ts=[FT() for _ in range(4)]
 if not k.GetProcessTimes(p,*(ctypes.byref(x) for x in ts)):raise RuntimeError()
 held=_winapi.DuplicateHandle(_winapi.GetCurrentProcess(),p,coordinator,0x101000,False,0)
 payload=json.dumps({'version':1,'handle':held,'pid':pid,'ticks':(ts[0].high<<32)|ts[0].low},separators=(',',':')).encode('ascii')
 if len(payload)>1024:raise RuntimeError()
 temporary=record.with_suffix('.tmp')
 with temporary.open('xb') as f:f.write(payload)
 os.link(temporary,record);temporary.unlink()
 deadline=time.monotonic()+5
 while not ack.exists():
  if time.monotonic()>=deadline:raise RuntimeError()
  time.sleep(.01)
 if ack.read_bytes()!=b'ACK':raise RuntimeError()
 if k.ResumeThread(t)!=1:raise RuntimeError()
 accepted=True
 if timed:time.sleep(30)
 else:raise SystemExit(17)
finally:
 cleanup_failed=False
 if p is not None and not accepted:
  try:
   _winapi.TerminateProcess(p,125)
   if _winapi.WaitForSingleObject(p,5000)!=_winapi.WAIT_OBJECT_0:cleanup_failed=True
  except Exception:cleanup_failed=True
 for h in (t,p,coordinator):
  if h is not None:
   try:_winapi.CloseHandle(h)
   except Exception:cleanup_failed=True
 if cleanup_failed:raise SystemExit(125)
'''


def publish_exclusive(path, data):
    """Completed private bytes appear atomically; existing destination is refused."""
    temporary=path.with_suffix('.tmp')
    with temporary.open('xb') as stream:stream.write(data)
    try:os.link(temporary,path)
    finally:temporary.unlink()


def pin_creation(backend, reads, process, pid):
    actual, created, signal = reads.identity(process)
    if (type(actual) is not int or actual <= 0 or type(pid) is not int or actual != pid or type(created) not in (int,float)
            or not math.isfinite(created) or created <= 0 or signal != 'LIVE'):
        raise OwnedJobError('CREATION_IDENTITY_REFUSED')
    held = backend.duplicate_readonly(process)
    try:
        other, timestamp, signal = reads.identity(held)
        if (type(other) is not int or other != actual or type(timestamp) not in (int,float)
                or not math.isfinite(timestamp) or timestamp<=0
                or abs(timestamp-created) > .00001 or signal != 'LIVE'):
            raise OwnedJobError('CREATION_IDENTITY_REFUSED')
        return HeldDescendant(held, actual, created)
    except BaseException:
        backend.close(held)
        raise


class MeasurementBackend(WindowsBackend):
    def __init__(self, record, ack, timed):
        super().__init__()
        self.record, self.ack, self.timed = record, ack, timed
        self.reads = ReadOnlyBackend()
        self.transferred = None
        self.coordinator = self.win.DuplicateHandle(self.win.GetCurrentProcess(),
            self.win.GetCurrentProcess(),self.win.GetCurrentProcess(),PROCESS_DUP_HANDLE,False,0)

    def duplicate_readonly(self, process):
        return self.win.DuplicateHandle(self.win.GetCurrentProcess(),process,
            self.win.GetCurrentProcess(),QUERY_SYNC,False,0)

    def launch(self, args, cwd, env, stdout, stderr):
        # This dedicated launcher alone adds its coordinator transfer capability.
        duplicates=[];created=None;error=None
        with open(os.devnull,'rb') as stdin:
            try:
                for stream in (stdin,stdout,stderr):
                    duplicates.append(self.win.DuplicateHandle(self.win.GetCurrentProcess(),
                        self.crt.get_osfhandle(stream.fileno()),self.win.GetCurrentProcess(),0,True,
                        self.win.DUPLICATE_SAME_ACCESS))
                remote=self.win.DuplicateHandle(self.win.GetCurrentProcess(),self.coordinator,
                    self.win.GetCurrentProcess(),0,True,self.win.DUPLICATE_SAME_ACCESS)
                duplicates.append(remote)
                startup=subprocess.STARTUPINFO();startup.dwFlags=self.win.STARTF_USESTDHANDLES
                startup.hStdInput,startup.hStdOutput,startup.hStdError=duplicates[:3]
                startup.lpAttributeList={'handle_list':duplicates}
                command=[args[0],'-c',PARENT,str(self.record),str(self.ack),str(remote),
                         'TIMEOUT' if self.timed else 'EXIT17']
                p,t,pid,_=self.win.CreateProcess(args[0],subprocess.list2cmdline(command),None,None,
                    True,0x80404,env,str(cwd),startup)
                created=p,t,pid
            except BaseException as exc:error=exc
            finally:
                for handle in duplicates:
                    try:self.close(handle)
                    except BaseException as exc:
                        if error is None:error=exc
        if error is not None:
            if created is not None:
                try:self.abort_suspended(created[0])
                finally:
                    for handle in created[:2]:self.close(handle)
            raise error
        return created

    def abort_suspended(self, process):
        self.win.TerminateProcess(process,125)
        WindowsBackend.wait(self,process,5)

    def read_record(self):
        try:
            with self.record.open('rb') as stream:data=stream.read(1025)
        except FileNotFoundError:return None
        if len(data)>1024:raise OwnedJobError('CREATION_IDENTITY_REFUSED')
        return json.loads(data)

    def adopt(self, data):
        if (type(data) is not dict or set(data)!={'version','handle','pid','ticks'}
                or type(data['version']) is not int or data['version']!=1
                or type(data['handle']) is not int or not 0<data['handle']<=MAX_HANDLE
                or data['handle'] in self._owned_handles or data['handle']==self.coordinator
                or type(data['pid']) is not int or not 0<data['pid']<2**32
                or data['pid']==self._owned_parent_pid
                or type(data['ticks']) is not int or not 116444736000000000<data['ticks']<2**64):
            raise OwnedJobError('CREATION_IDENTITY_REFUSED')
        # The protocol's handle was installed by this parent into this process.
        self.transferred=data['handle']
        created=(data['ticks']-116444736000000000)/10000000
        pid,actual,signal=self.reads.identity(self.transferred)
        if (type(pid) is not int or pid!=data['pid'] or type(actual) not in (int,float)
                or not math.isfinite(actual) or actual<=0
                or abs(actual-created)>.00001 or signal!='LIVE'
                or self.reads.membership(self.transferred,self._owned_handles[2]) is not True):
            raise OwnedJobError('CREATION_IDENTITY_REFUSED')
        self.observation_target=HeldDescendant(self.transferred,pid,created)
        self.observation_backend=self.reads

    def acknowledge(self):
        publish_exclusive(self.ack,b'ACK')

    def wait(self, process, timeout):
        deadline=time.monotonic()+timeout
        while self.transferred is None:
            if time.monotonic()>=deadline:raise subprocess.TimeoutExpired('CONTROLLED_JOB',timeout)
            data=self.read_record()
            if data is not None:
                self.adopt(data)
                if time.monotonic()>=deadline:raise subprocess.TimeoutExpired('CONTROLLED_JOB',timeout)
                self.acknowledge()
                break
            time.sleep(min(.01,max(0,deadline-time.monotonic())))
        remaining=deadline-time.monotonic()
        if remaining<=0:raise subprocess.TimeoutExpired('CONTROLLED_JOB',timeout)
        return super().wait(process,remaining)

    def release_transfer(self):
        # Called only after production run has stopped and closed its own handles.
        failures=self.transferred is None
        for handle in (self.transferred,self.coordinator):
            if handle is not None:
                try:self.close(handle)
                except Exception:failures=True
        self.transferred=self.coordinator=None
        return not failures


class NativeFactory:
    def backend(self):
        backend=WindowsBackend()
        backend.reads=ReadOnlyBackend()
        backend.duplicate_readonly=lambda process:backend.win.DuplicateHandle(
            backend.win.GetCurrentProcess(),process,backend.win.GetCurrentProcess(),QUERY_SYNC,False,0)
        return backend

    def main(self, record, ack, timed):return MeasurementBackend(record,ack,timed)


def project_observation(value):
    if type(value) is not dict:return None
    allowed_stages={'BEFORE_TERMINATE','AFTER_TERMINATE','ACCOUNTING_ZERO','AFTER_ACCOUNTING_ZERO'}
    allowed_reasons={'EXACT_PROCESS_SIGNALED','INVALID_INPUT','DEADLINE','IDENTITY_REFUSED',
                     'READ_UNKNOWN','NON_MEMBER','STAGE_REFUSED','SAMPLE_LIMIT'}
    samples=value.get('samples')
    if (value.get('scope')!='EXACT_PROCESS_ONLY' or value.get('status') not in ('PASS','FAIL')
            or value.get('reason') not in allowed_reasons or type(samples) is not list or len(samples)>8
            or type(value.get('sample_count')) is not int or value['sample_count']!=len(samples)):
        return None
    projected=[]
    for item in samples:
        if (type(item) is not dict or item.get('stage') not in allowed_stages
                or item.get('membership') not in ('MEMBER','NON_MEMBER')
                or item.get('accounting') not in ('ZERO','NONZERO')
                or item.get('signal') not in ('LIVE','SIGNALED','UNKNOWN')):return None
        projected.append({k:item[k] for k in ('stage','membership','accounting','signal')})
    if value['status']=='PASS':
        # A measurement PASS requires a live target before termination and a
        # complete ordered timeline, not merely a trusted status field.
        if (value['reason']!='EXACT_PROCESS_SIGNALED' or len(projected)<3
                or [item['stage'] for item in projected[:3]]!=[
                    'BEFORE_TERMINATE','AFTER_TERMINATE','ACCOUNTING_ZERO']
                or any(item['stage']!='AFTER_ACCOUNTING_ZERO' for item in projected[3:])
                or any(item['membership']!='MEMBER' for item in projected)
                or projected[0]['signal']!='LIVE'
                or projected[-1]['accounting']!='ZERO'
                or projected[-1]['signal']!='SIGNALED'):
            return None
    return {'scope':'EXACT_PROCESS_ONLY','status':value['status'],'reason':value['reason'],
            'sample_count':len(projected),'samples':projected}


def execute_case(timed, *, executable, directory, environment, factory):
    row={'case':'PARENT_TIMEOUT' if timed else 'PARENT_EXIT17','status':'FAIL',
         'primary':'UNKNOWN','cleanup':'UNKNOWN','unrelated':'UNKNOWN',
         'unrelated_cleanup':'UNKNOWN','transfer_closed':False,'observation':None}
    unrelated=main=None;job=process=thread=held=None;bound=False
    try:
        with (directory/'out').open('xb') as out,(directory/'err').open('xb') as err:
            unrelated=factory.backend();job=unrelated.create_job()
            process,thread,pid=unrelated.launch([executable,'-c','import time;time.sleep(30)'],
                                               directory,environment,out,err)
            unrelated.bind(job,process,pid);bound=True;unrelated.resume(thread)
            held=pin_creation(unrelated,unrelated.reads,process,pid)
            main=factory.main(directory/'record',directory/'ack',timed)
            try:
                result=run([executable],timeout=2 if timed else 5,stdout=out,stderr=err,
                           cwd=directory,env=environment,_backend=main)
                row['primary']='EXIT17' if result.returncode==17 else 'OTHER_EXIT'
                row['cleanup']=result.cleanup
                row['observation']=project_observation(getattr(result,'exact_process_observation',None))
            except subprocess.TimeoutExpired as error:
                row['primary']='TIMEOUT';row['cleanup']=getattr(error,'cleanup','UNKNOWN')
                row['observation']=project_observation(getattr(error,'exact_process_observation',None))
            except Exception as error:
                row['primary']='ERROR';row['cleanup']=getattr(error,'cleanup','UNKNOWN')
                row['observation']=project_observation(getattr(error,'exact_process_observation',None))
            pid,created,signal=unrelated.reads.identity(held.handle)
            if pid==held.expected_pid and abs(created-held.expected_created)<=.00001 and signal=='LIVE':
                row['unrelated']='LIVE'
            if (row['primary']==('TIMEOUT' if timed else 'EXIT17') and row['cleanup']=='OWNED_TREE_STOPPED'
                    and row['unrelated']=='LIVE' and row['observation'] is not None
                    and row['observation']['status']=='PASS'):row['status']='PASS'
    except Exception:pass
    finally:
        if main is not None:
            try:row['transfer_closed']=main.release_transfer()
            except Exception:row['transfer_closed']=False
        if not row['transfer_closed']:row['status']='FAIL'
        if unrelated is not None:
            try:
                # Unrelated leaf is stopped only after the LIVE gold opportunity.
                if process is not None and not bound:
                    unrelated.abort_suspended(process)
                    row['unrelated_cleanup']='SUSPENDED_CHILD_STOPPED'
                elif process is not None:
                    if held is not None:
                        unrelated.observation_target=held;unrelated.observation_backend=unrelated.reads
                    row['unrelated_cleanup']=unrelated.stop_tree(job)
                    if unrelated.reads.signal(held.handle if held is not None else process)!='SIGNALED':
                        row['unrelated_cleanup']='OWNED_TREE_STOP_UNCONFIRMED'
            except Exception:row['unrelated_cleanup']='OWNED_TREE_STOP_UNCONFIRMED'
            for handle in (held.handle if held is not None else None,thread,process,job):
                if handle is not None:
                    try:unrelated.close(handle)
                    except Exception:row['unrelated_cleanup']='OWNED_TREE_STOP_UNCONFIRMED'
        if row['unrelated_cleanup']!='OWNED_TREE_STOPPED':row['status']='FAIL'
        if row['cleanup'] not in ('OWNED_TREE_STOPPED','OWNED_TREE_STOP_UNCONFIRMED','SUSPENDED_CHILD_STOPPED','NOT_STARTED'):
            row['cleanup']='UNKNOWN'
    if row['unrelated_cleanup'] not in ('OWNED_TREE_STOPPED','OWNED_TREE_STOP_UNCONFIRMED','SUSPENDED_CHILD_STOPPED','NOT_STARTED','UNKNOWN'):
        row['unrelated_cleanup']='UNKNOWN';row['status']='FAIL'
    if type(row['transfer_closed']) is not bool:
        row['transfer_closed']=False;row['status']='FAIL'
    return row


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError('ARGUMENTS_REFUSED')


def main(argv=None):
    parser=SafeParser(add_help=False,allow_abbrev=False)
    parser.add_argument('--run-controlled',action='store_true')
    parser.add_argument('--private-root',type=Path)
    try:args=parser.parse_args(argv)
    except Exception:
        print(json.dumps({'scope':'CONTROLLED_NATIVE_JOB_MEASUREMENT','status':'ARGUMENTS_REFUSED'}));return 2
    if not args.run_controlled:
        print(json.dumps({'scope':'CONTROLLED_NATIVE_JOB_MEASUREMENT','status':'NOT_RUN'}));return 2
    if sys.platform!='win32' or sys.version_info[:2]!=(3,12) or __import__('struct').calcsize('P')!=8:
        print(json.dumps({'scope':'CONTROLLED_NATIVE_JOB_MEASUREMENT','status':'NATIVE_PLATFORM_REQUIRED'}));return 2
    runtime=args.private_root if args.private_root is not None else Path.cwd()/'.runtime'
    runner=os.environ.get('RUNNER_TEMP')
    try:
        root_valid=(runtime is not None and runtime.is_absolute() and runtime.is_dir()
            and not runtime.is_symlink() and not runtime.is_junction()
            and not (getattr(runtime.stat(), 'st_file_attributes', 0)
                     & stat.FILE_ATTRIBUTE_REPARSE_POINT)
            and (args.private_root is None or (runner is not None
                 and runtime.resolve()==Path(runner).resolve())))
    except Exception:root_valid=False
    if not root_valid:
        print(json.dumps({'scope':'CONTROLLED_NATIVE_JOB_MEASUREMENT','status':'PRIVATE_ROOT_REFUSED'}));return 2
    try:
        executable_path=Path(sys._base_executable)
        if not executable_path.is_absolute() or not executable_path.is_file():raise ValueError()
        executable=str(executable_path.resolve())
    except Exception:
        print(json.dumps({'scope':'CONTROLLED_NATIVE_JOB_MEASUREMENT','status':'RUNTIME_REFUSED'}));return 2
    environment={k:v for k,v in os.environ.items() if k in {
        'PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ'}}
    results=[]
    try:
        for timed in (False,True):
            with tempfile.TemporaryDirectory(prefix='controlled-job-',dir=runtime) as root:
                results.append(execute_case(timed,executable=executable,directory=Path(root),
                                            environment=environment,factory=NativeFactory()))
    except Exception:
        print(json.dumps({'scope':'CONTROLLED_NATIVE_JOB_MEASUREMENT','status':'PRIVATE_SETUP_REFUSED'}));return 1
    print(json.dumps({'scope':'CONTROLLED_NATIVE_JOB_MEASUREMENT','proof':'TWO_CONTROLLED_PARENT_CHILD_CASES_EXACT_PROCESS_ONLY_NOT_WHOLE_TREE','results':results},separators=(',',':')))
    return 0 if all(row['status']=='PASS' for row in results) else 1


if __name__=='__main__':raise SystemExit(main())
