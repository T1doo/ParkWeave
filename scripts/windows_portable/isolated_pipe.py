"""Frozen pipe operation in an exactly owned helper; no timeout threads.

One caller deadline includes creation and exit/reap. Windows Job candidate is
not native accepted. No secrets, shell, arbitrary helper source or PID lookup.
"""
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import threading
import time

from . import processes as p

# Only this frozen source can run in the helper. Input is a borrowed pipe, output
# is a new private result pipe. A blocked ReadFile/WriteFile dies with the helper.
HELPER = '''import os,sys,json
op,nonce=sys.argv[1:]
if os.name=='nt':
 import msvcrt
 msvcrt.setmode(0,os.O_BINARY);msvcrt.setmode(1,os.O_BINARY)
try:
 if op=='read':
  raw=b''
  while b'\\n' not in raw and len(raw)<=4096:
   x=os.read(0,1)
   if not x:raise EOFError()
   raw+=x
  if len(raw)>4096 or not raw.endswith(b'\\n'):raise ValueError()
  out=raw
 else:
  raw=(json.dumps({'schema':'parkweave-worker-go/1','challenge':nonce,'command':'GO'},separators=(',',':'))+'\\n').encode()
  if os.name=='nt':
   import ctypes as C
   k=C.WinDLL('kernel32.dll',use_last_error=True)
   k.GetStdHandle.argtypes=[C.c_int32];k.GetStdHandle.restype=C.c_void_p
   k.WriteFile.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32),C.c_void_p];k.WriteFile.restype=C.c_int32
   n=C.c_uint32()
   if not k.WriteFile(k.GetStdHandle(-10),raw,len(raw),C.byref(n),None) or n.value!=len(raw):raise OSError()
  elif os.write(0,raw)!=len(raw):raise OSError()
  out=(json.dumps({'operation':op,'challenge':nonce,'written':True},separators=(',',':'))+'\\n').encode()
except BaseException as e:
 os.write(1,json.dumps({'helper_error':type(e).__name__[:64],'errno':getattr(e,'errno',None)}).encode());os._exit(121)
if len(out)>4096:os._exit(122)
if os.write(1,out)!=len(out):os._exit(123)
'''


class PipeFailure(p.ProcessRefused):
    def __init__(self,phase,operation,cleanup_confirmed=False):
        self.phase,self.outcome,self.cleanup_confirmed=phase,'UNKNOWN',cleanup_confirmed
        self.go_may_have_been_sent=operation=='go'
        super().__init__('PIPE_OPERATION_UNKNOWN:'+phase)


class _LinuxHelper(p.LinuxSingleProcess):
    def preflight(self,command):
        # Same single-thread/fd-exec containment requirements, a separate frozen
        # protocol profile. The original sleep/true launcher is not broadened.
        import signal
        if (os.name!='posix' or threading.active_count()!=1 or len(os.listdir('/proc/self/task'))!=1
                or threading.current_thread() is not threading.main_thread()
                or signal.getsignal(signal.SIGCHLD)!=signal.SIG_DFL
                or not hasattr(os,'pidfd_open') or not hasattr(signal,'pidfd_send_signal')
                or os.execve not in os.supports_fd):raise p.ProcessRefused('HELPER_PIDFD_PROFILE_REQUIRED')
        raw=Path(sys.executable).resolve().read_bytes()
        if (command.size!=len(raw) or command.sha256!=hashlib.sha256(raw).hexdigest()
                or command.arguments[:4]!=('-I','-B','-c',HELPER)
                or command.arguments[4] not in ('read','go')):raise p.ProcessRefused('FROZEN_HELPER_REQUIRED')

    def _exec(self,group,env):
        os.dup2(group.resources['pipe_borrowed'],0)
        os.dup2(group.resources['pipe_result_w'],1)
        super()._exec(group,env)


def _decode(raw):
    from parkweave.runtime_readiness import parse
    return parse(raw.rstrip(b'\n'))


def _operation(owner,group,op,nonce,deadline):
    from parkweave.runtime_readiness import challenge,parse,require_pipe
    if (op not in ('read','go') or type(deadline) not in (int,float) or not math.isfinite(deadline)
            or not 0<deadline-time.monotonic()<=5):raise p.ProcessRefused('PIPE_ABSOLUTE_CLOCK_REQUIRED')
    challenge(nonce)
    fd=group.resources['worker_ready_r' if op=='read' else 'worker_go_w'];require_pipe(fd)
    # Cleanup has part of the SAME deadline, never an extra stop_seconds clock.
    work_deadline=deadline-.5
    if time.monotonic()>=work_deadline:raise PipeFailure('NO_CLEANUP_RESERVE',op,True)
    command=p.Command(group.command.relative_executable,group.command.sha256,group.command.size,
                      ('-I','-B','-c',HELPER,op,nonce),group.command.model,'PIPE_PROBE_V1')
    if os.name=='posix':backend=_LinuxHelper()
    else:
        from .windows_process_handles import WindowsJobProcess
        if type(owner.backend) is not WindowsJobProcess:raise p.ProcessRefused('NATIVE_JOB_HELPER_REQUIRED')
        backend=WindowsJobProcess()
    backend.preflight(command)
    pin=p.PinnedExecutable(owner.lease,command)
    state=p._ProcessState(command,pin)
    # Retain even partial creation before any process can use the borrowed pipe.
    active=group.resources.setdefault('active_pipe_helpers',[]);active.append((backend,state))
    primary=None;code=None;confirmed=False;raw=b''
    try:
        state.resources['pipe_borrowed']=fd
        state.resources['pipe_result_r'],state.resources['pipe_result_w']=os.pipe()
        from parkweave.process_env import minimal_environment
        env=minimal_environment(os.environ)
        env['PATH']=str(Path(pin.path).parent)
        for key in ('TEMP','TMP','TMPDIR'):env[key]=str(Path(pin.path).parents[len(command.relative_executable.split('/'))-1])
        def register(exact):
            if exact is not state:raise p.ProcessRefused('HELPER_REGISTRATION_REFUSED')
            state.registration='ACKNOWLEDGED'
        backend.create(state,register,env,work_deadline)
        state.creating=False
        # Only the child keeps a result writer; consume-before-close, no retry.
        writer=state.resources.pop('pipe_result_w')
        try:os.close(writer)
        except BaseException:
            state.resources['result_writer_close_unknown']=True
            raise
        code=backend.observe(state,work_deadline)
        if code is None:raise PipeFailure('DEADLINE',op)
        if code!=0:raise PipeFailure('HELPER_EXIT',op)
    except BaseException as error:primary=error
    finally:
        state.creating=False
        try:
            confirmed=backend.stop(state,deadline)
            if not confirmed:raise PipeFailure('CLEANUP_EXIT_UNKNOWN',op)
            # All helper writers are gone; the parent write handle must also
            # have been positively closed before reading (otherwise no EOF).
            if 'pipe_result_w' in state.resources:
                writer=state.resources.pop('pipe_result_w')
                try:os.close(writer)
                except BaseException:
                    state.resources['result_writer_close_unknown']=True
                    raise
            if state.resources.get('stdio_close_unknown') or state.resources.get('result_writer_close_unknown'):raise PipeFailure('WRITER_CLOSE_UNKNOWN',op)
            # <=4096 bytes and EOF: frozen helper has no child, all writers
            # are gone. No PeekNamedPipe or active-producer read in the root.
            reader=state.resources.get('pipe_result_r')
            if reader is not None:
                raw=os.read(reader,4097)
                if len(raw)>4096 or os.read(reader,1):raise PipeFailure('RESULT_LIMIT',op)
            backend.close_observed(state);pin.close()
            reader=state.resources.pop('pipe_result_r',None)
            if reader is not None:os.close(reader)
            active.remove((backend,state))
        except BaseException as cleanup:
            owner.unknown=True
            failure=PipeFailure('CLEANUP_UNKNOWN',op)
            failure.owned_helper=state
            failures=([primary] if primary else [])+[cleanup,failure]
            try:owner.lease.mark_unknown('RUNNING')
            except BaseException as journal_error:failures.append(journal_error)
            raise BaseExceptionGroup('PIPE_AND_CLEANUP_UNKNOWN',failures) from primary
    if primary is not None:
        if isinstance(primary,PipeFailure):
            primary.cleanup_confirmed=confirmed
            if primary.phase=='HELPER_EXIT':
                try:value=json.loads(raw) if raw else {}
                except (ValueError,UnicodeError):value={}
                if (type(value) is dict and set(value)=={'helper_error','errno'}
                        and type(value['helper_error']) is str and len(value['helper_error'])<=64
                        and (value['errno'] is None or type(value['errno']) is int)):
                    primary.helper_diagnostic=value
        raise primary
    if time.monotonic()>=deadline:raise PipeFailure('LATE_RESULT',op,True)
    if op=='go':
        if _decode(raw)!={'operation':op,'challenge':nonce,'written':True}:
            raise PipeFailure('GO_UNKNOWN',op,True)
        return None
    return _decode(raw)


def operation(owner,group,op,nonce,deadline):
    try:
        result=_operation(owner,group,op,nonce,deadline)
        if time.monotonic()>=deadline:raise PipeFailure('LATE_RESULT',op,True)
        return result
    except PipeFailure:raise
    except BaseException as primary:
        # Covers parser, OS, registration and cleanup failures after a possible
        # GO. Preserve the cause, never report NOT_SENT or replay the command.
        failure=PipeFailure('GO_UNKNOWN' if op=='go' else 'READ_UNKNOWN',op,
                            not bool(group.resources.get('active_pipe_helpers')))
        raise failure from primary
