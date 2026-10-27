"""Future running-initdb client verification only: NO_RESUME / NO_SECRET.

No GetNamedPipeInfo access expansion, PID reopen, arbitrary Job-child trust,
impersonation, Disconnect, password or WriteFile. Pending connect cancellation
is not completion: original pipe/event/OVERLAPPED remain strongly registered
until actual completion; otherwise cleanup stays UNKNOWN, never a false PASS.
"""
import ctypes as C
import math
import time
import weakref

from .fixed_directories import FixedDirectoryLease,_exclusive_entry,_exclusive_operation
from .endpoint_plan import _key_held
from .initdb_pipe_candidate import _OwnedInitdbPipe,_pwfile_name_held,PipeFailure
from .restricted_initdb_candidate import _RestrictedInitdbBackend
from .processes import _ProcessState,ProcessRefused


class _Offset(C.Structure):
    _fields_=[('low',C.c_uint32),('high',C.c_uint32)]
class _Position(C.Union):
    _fields_=[('offset',_Offset),('pointer',C.c_void_p)]
class Overlapped(C.Structure):
    _fields_=[('internal',C.c_size_t),('internal_high',C.c_size_t),
              ('position',_Position),('event',C.c_void_p)]


def need(ok):
    if not ok:raise ProcessRefused('ORIGINAL_INITDB_CLIENT_REFUSED')


def _limit(deadline):
    need(type(deadline) in (int,float) and math.isfinite(deadline))
    left=deadline-time.monotonic();need(0<left<=5)
    return left


class ClientObservation:
    __slots__=('__weakref__',)
    def __reduce__(self):raise TypeError('CLIENT_OBSERVATION_NOT_TRANSFERABLE')
    def __copy__(self):raise TypeError('CLIENT_OBSERVATION_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo):raise TypeError('CLIENT_OBSERVATION_NOT_TRANSFERABLE')


_observed=weakref.WeakKeyDictionary()
_active={}  # Strong roots for all submitted original OV/event/pipe records.


class _Connection:
    def __init__(self,backend,group):
        self.backend,self.group,self.server=backend,group,backend.server
        self.pipe=self.server._handle
        self.kernel=self.server._kernel
        self.ov=Overlapped();self.event=None
        self.submitted=self.complete=self.connected=self.cancel_attempted=self.event_close_attempted=False
        self.connect_returned=self.event_closed=False
        self.errors=[]
        declarations={
            'CreateEventW':([C.c_void_p,C.c_int32,C.c_int32,C.c_wchar_p],C.c_void_p),
            'ConnectNamedPipe':([C.c_void_p,C.POINTER(Overlapped)],C.c_int32),
            'CancelIoEx':([C.c_void_p,C.POINTER(Overlapped)],C.c_int32),
            'GetOverlappedResult':([C.c_void_p,C.POINTER(Overlapped),C.POINTER(C.c_uint32),C.c_int32],C.c_int32),
            'WaitForSingleObject':([C.c_void_p,C.c_uint32],C.c_uint32),
            'GetNamedPipeClientProcessId':([C.c_void_p,C.POINTER(C.c_uint32)],C.c_int32),
        }
        for name,(args,result) in declarations.items():
            fn=getattr(self.kernel,name);fn.argtypes,fn.restype=args,result

    def _result(self):
        transferred=C.c_uint32()
        ok=self.kernel.GetOverlappedResult(self.pipe,C.byref(self.ov),C.byref(transferred),False)
        error=C.get_last_error() if not ok else None
        # Connect's byte count is undefined. Never inspect it as evidence.
        if ok or error==995:
            self.complete=True;self.connected=bool(ok)
        elif error!=996:
            self.errors.append(('COMPLETION_UNKNOWN',error))
        return self.complete

    def connect(self,work_deadline):
        event=self.kernel.CreateEventW(None,True,False,None)
        need(event not in (None,0,C.c_void_p(-1).value))
        self.event=event;self.ov.event=event
        _active[id(self)]=self
        self.server._pending_connection=self  # Before submission or any later exception.
        self.submitted=True
        ok=self.kernel.ConnectNamedPipe(self.pipe,C.byref(self.ov))
        self.connect_returned=True
        error=C.get_last_error() if not ok else None
        if ok or error==535:  # ERROR_PIPE_CONNECTED is a real early connection.
            self.complete=True;self.connected=True
        elif error==997:
            self.kernel.WaitForSingleObject(self.event,max(0,int((work_deadline-time.monotonic())*1000)))
            self._result()
        else:
            self.complete=True  # Documented immediate failure, not pending IO.
            self.errors.append(('CONNECT_FAILED',error))
        need(self.complete and self.connected and time.monotonic()<work_deadline)

    def cancel_and_observe(self,deadline):
        if not self.submitted:
            self.complete=True  # No Connect call has been attempted.
            return True
        if self.submitted and not self.complete and not self.cancel_attempted:
            self.cancel_attempted=True
            ok=self.kernel.CancelIoEx(self.pipe,C.byref(self.ov))
            error=C.get_last_error() if not ok else None
            if not ok and error!=1168:self.errors.append(('CANCEL_UNKNOWN',error))
        if not self.complete and self.connect_returned:
            remaining=max(0,deadline-time.monotonic())
            self.kernel.WaitForSingleObject(self.event,int(min(remaining,5)*1000))
            self._result()
        # False leaves the original OV/event/pipe rooted and unclosed.
        return self.complete

    def finish(self):
        need(self.complete)
        if self.event is not None and not self.event_close_attempted:
            self.event_close_attempted=True
            try:
                if not self.kernel.CloseHandle(self.event):need(False)
            except BaseException as error:
                self.errors.append(('EVENT_CLOSE_UNKNOWN',type(error).__name__))
                self.server.cleanup_errors.append(('CLIENT_EVENT_CLOSE_UNKNOWN',type(error).__name__,self.event))
                raise
            self.event_closed=True
        need(self.event is None or self.event_closed)
        _active.pop(id(self),None)
        if self.server._pending_connection is self:self.server._pending_connection=None

    def identity(self,deadline):
        backend,group=self.backend,self.group
        r=group.resources
        need(type(backend) is _RestrictedInitdbBackend and type(group) is _ProcessState
             and self.server._claimed_group is group and group.started and not group.creating
             and not group.stopped and not group.attempted_stop and r.get('bound') is True
             and r.get('process') is not None and r.get('job') is not None)
        backend._fresh(group,deadline)
        need(self.server._handle==self.pipe and backend.birth(r['process'])==r['birth'])
        need(self.kernel.WaitForSingleObject(r['process'],0)==258)  # WAIT_TIMEOUT: original handle alive.
        pid=backend.original.kernel.GetProcessId(r['process'])
        need(pid==r['pid']==r['birth'][0] and pid>0)
        inside=C.c_int32()
        need(backend.original.kernel.IsProcessInJob(r['process'],r['job'],C.byref(inside)) and inside.value)
        backend._child_token(group)
        client=C.c_uint32()
        need(self.kernel.GetNamedPipeClientProcessId(self.pipe,C.byref(client)))
        need(client.value==pid)  # Equality is anchored to original HANDLE+birth, never OpenProcess.
        image=C.create_unicode_buffer(4096);length=C.c_uint32(len(image))
        need(backend.image(r['process'],1,image,C.byref(length)) and 0<length.value<len(image))
        need(image.value.casefold()==group.executable.native_path.casefold())
        group.executable.verify()
        need(backend.birth(r['process'])==r['birth'] and self.kernel.WaitForSingleObject(r['process'],0)==258)
        return r['birth'],pid


@_exclusive_entry
def verify_running_client(lease,backend,group,deadline):
    _limit(deadline)
    need(type(lease) is FixedDirectoryLease and type(backend) is _RestrictedInitdbBackend
         and backend.lease is lease and type(group) is _ProcessState and group.started and not group.creating)
    # No-Resume normal candidate refuses here before any connect/event/native IO.
    need(group.operation_lock.acquire(blocking=False))
    owner_locked=server_locked=False;op=None
    try:
        owner_locked=backend.owner._lock.acquire(timeout=max(0,deadline-time.monotonic()))
        need(owner_locked)
        server_locked=backend.server._lock.acquire(timeout=max(0,deadline-time.monotonic()))
        need(server_locked)
        server=backend.server
        need(type(server) is _OwnedInitdbPipe and not server._client_attempted and server._pending_connection is None)
        key=_key_held(lease);_pwfile_name_held(lease,server,backend.owner)
        need(deadline-time.monotonic()>.5)
        server._client_attempted=True
        op=_Connection(backend,group)
        op.connect(deadline-.5)
        first=op.identity(deadline)
        _pwfile_name_held(lease,server,backend.owner)
        need(op.identity(deadline)==first and _key_held(lease)==key and time.monotonic()<deadline)
        op.finish()
        need(op.identity(deadline)==first and _key_held(lease)==key and time.monotonic()<deadline)
        observation=ClientObservation()
        _observed[observation]=(backend,group,key,first,deadline)
        return observation  # No secret transmission or resumed-process receipt.
    except BaseException:
        lease.poisoned=True;backend.server.failed=True
        if op is not None:
            try:
                if op.cancel_and_observe(deadline):op.finish()
            except BaseException as error:op.errors.append(('CLEANUP_UNKNOWN',type(error).__name__))
        raise
    finally:
        if server_locked:backend.server._lock.release()
        if owner_locked:backend.owner._lock.release()
        group.operation_lock.release()


@_exclusive_operation
def consume_observation_held(lease,observation):
    need(type(observation) is ClientObservation)
    record=_observed.get(observation)
    need(record is not None and record[0].lease is lease)
    _observed.pop(observation)
    backend,group,key,identity,deadline=record
    group_locked=owner_locked=server_locked=False
    try:
        group_locked=group.operation_lock.acquire(blocking=False);need(group_locked)
        owner_locked=backend.owner._lock.acquire(timeout=max(0,deadline-time.monotonic()));need(owner_locked)
        server_locked=backend.server._lock.acquire(timeout=max(0,deadline-time.monotonic()));need(server_locked)
        need(time.monotonic()<deadline and _key_held(lease)==key)
        # The original pending record is complete; recheck the same pipe/process.
        op=_Connection(backend,group)
        need(op.identity(deadline)==identity)
        return backend,group  # Still NO_SECRET; no function sends a password.
    except BaseException:
        lease.poisoned=True;backend.server.failed=True;raise
    finally:
        if server_locked:backend.server._lock.release()
        if owner_locked:backend.owner._lock.release()
        if group_locked:group.operation_lock.release()


def retire_pending(server,deadline):
    """Explicit cleanup-only observation, never an automatic retry/connect."""
    _limit(deadline)
    need(type(server) is _OwnedInitdbPipe)
    need(server._lock.acquire(timeout=_limit(deadline)))
    try:
        op=server._pending_connection
        need(op is not None and _active.get(id(op)) is op and op.server is server and op.pipe==server._handle)
        need(op.cancel_and_observe(deadline));op.finish()
    finally:server._lock.release()


def native_initdb_client():raise ProcessRefused('NATIVE_INITDB_CLIENT_NOT_ACCEPTED')
