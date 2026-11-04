"""Owned initdb bootstrap composition; original native admission gates remain.

No import-time native calls. Password bytes are sent once to the authenticated
original initdb pipe client, never placed in a pathname, argv or environment.
Unobserved asynchronous writes retain their buffer/event/pipe until completion.
This implementation is not Windows execution or native acceptance evidence.
"""
import ctypes as C
import time
import weakref

from .controller import CandidateRefused
from .fixed_secret_store import _under_lease
from .initdb_client_candidate import (Overlapped, _Connection, verify_running_client,
                                     consume_observation_held)
from .initdb_pipe_candidate import _OwnedInitdbPipe
from .restricted_initdb_candidate import _freeze, _RestrictedInitdbBackend
from .restricted_token_candidate import _RestrictedPrimaryCandidate, TokenProfile
from .runtime_payload import RuntimePayloadPrerequisite
from .processes import PrivateProcessAdapter

class InitdbTransmission:
    __slots__=('__weakref__',)
    def __reduce__(self):raise TypeError('initdb transmission cannot be transferred')
    def __copy__(self):raise TypeError('initdb transmission cannot be copied')
    def __deepcopy__(self,memo):raise TypeError('initdb transmission cannot be copied')

_transmitted=weakref.WeakKeyDictionary()


def need(ok):
    if not ok:raise CandidateRefused('PROTECTED_INITDB_BOOTSTRAP_REFUSED')


_active_writes = {}  # Strong roots; cancellation alone never frees an OVERLAPPED.


class _PipeWrite:
    def __init__(self,server,password):
        need(type(password) is str and 12<=len(password)<=128
             and all(33<=ord(c)<=126 for c in password))
        self.server,self.kernel,self.pipe=server,server._kernel,server._handle
        self.buffer=bytearray(password.encode('ascii')+b'\n')
        self.native_buffer=(C.c_ubyte*len(self.buffer)).from_buffer(self.buffer)
        self.ov=Overlapped();self.event=None
        self.submitted=self.returned=self.complete=self.success=False
        self.cancel_attempted=self.close_attempted=self.closed=False
        declarations={
            'CreateEventW':([C.c_void_p,C.c_int32,C.c_int32,C.c_wchar_p],C.c_void_p),
            'WriteFile':([C.c_void_p,C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32),C.POINTER(Overlapped)],C.c_int32),
            'GetOverlappedResult':([C.c_void_p,C.POINTER(Overlapped),C.POINTER(C.c_uint32),C.c_int32],C.c_int32),
            'CancelIoEx':([C.c_void_p,C.POINTER(Overlapped)],C.c_int32),
            'WaitForSingleObject':([C.c_void_p,C.c_uint32],C.c_uint32),
            'CloseHandle':([C.c_void_p],C.c_int32),
        }
        for name,(arguments,result) in declarations.items():
            function=getattr(self.kernel,name);function.argtypes,function.restype=arguments,result

    def _result(self):
        count=C.c_uint32()
        ok=self.kernel.GetOverlappedResult(self.pipe,C.byref(self.ov),C.byref(count),False)
        error=None if ok else C.get_last_error()
        if ok or error==995:
            self.complete=True;self.success=bool(ok) and count.value==len(self.buffer)
        return self.complete

    def send(self,deadline):
        need(not self.submitted and self.server._pending_write is None and not self.server._closed)
        # Register even allocation failures so private bytes can be erased.
        _active_writes[id(self)]=self;self.server._pending_write=self
        self.event=self.kernel.CreateEventW(None,True,False,None)
        need(self.event not in (None,0,C.c_void_p(-1).value))
        self.ov.event=self.event
        need(time.monotonic()<deadline)
        self.submitted=True  # Unknown call outcome must retain all original IO memory.
        count=C.c_uint32()
        ok=self.kernel.WriteFile(self.pipe,self.native_buffer,len(self.buffer),C.byref(count),C.byref(self.ov))
        self.returned=True
        error=None if ok else C.get_last_error()
        if ok:
            self.complete=True;self.success=count.value==len(self.buffer)
        elif error==997:
            self.kernel.WaitForSingleObject(self.event,max(0,int((deadline-time.monotonic())*1000)))
            self._result()
        else:self.complete=True  # Documented immediate failure, no pending IO.
        need(self.complete and self.success and time.monotonic()<deadline)

    def cancel_and_observe(self,deadline):
        if not self.submitted:self.complete=True
        if self.submitted and not self.complete and not self.cancel_attempted:
            self.cancel_attempted=True
            self.kernel.CancelIoEx(self.pipe,C.byref(self.ov))
        if not self.complete and self.returned:
            self.kernel.WaitForSingleObject(self.event,max(0,int(min(5,deadline-time.monotonic())*1000)))
            self._result()
        return self.complete

    def finish(self):
        need(self.complete)
        # Erase only after the kernel has stopped referencing this allocation.
        self.buffer[:]=b'\0'*len(self.buffer)
        if self.event not in (None,0,C.c_void_p(-1).value) and not self.close_attempted:
            self.close_attempted=True
            need(self.kernel.CloseHandle(self.event));self.closed=True
        need(self.event in (None,0,C.c_void_p(-1).value) or self.closed)
        _active_writes.pop(id(self),None)
        if self.server._pending_write is self:self.server._pending_write=None


def _resume(lease,backend,group,deadline):
    def held():
        need(type(backend) is _RestrictedInitdbBackend and not group.creating and not group.started
             and group.registration=='ACKNOWLEDGED' and group.resources.get('bound') is True
             and not group.resources.get('bootstrap_resume_attempted'))
        need(group.operation_lock.acquire(blocking=False))
        try:
            with backend.owner._lock,backend.server._lock:
                backend._fresh(group,deadline);backend._child_token(group)
                r=group.resources
                need(r.get('restricted_stage')=='VERIFIED_SUSPENDED_NO_DATA_TARGET_OR_CLIENT_ACCEPTANCE'
                     and backend.kernel.WaitForSingleObject(r['process'],0)==258
                     and backend.birth(r['process'])==r['birth'])
                resume=backend.kernel.ResumeThread
                resume.argtypes,resume.restype=[C.c_void_p],C.c_uint32
                r['bootstrap_resume_attempted']=True
                need(resume(r['thread'])==1)
                group.started=True;r['restricted_stage']='RESUMED_AWAITING_ORIGINAL_PIPE_CLIENT'
        finally:group.operation_lock.release()
    return _under_lease(lease,held)


def _transmit(lease,observation,password,deadline):
    def held():
        backend,group=consume_observation_held(lease,observation)
        need(group.operation_lock.acquire(blocking=False))
        writer=None
        try:
            with backend.owner._lock,backend.server._lock:
                op=_Connection(backend,group);op.identity(deadline)
                writer=_PipeWrite(backend.server,password)
                try:
                    writer.send(deadline-.25)
                    writer.finish()
                    from .native_trial_authority import bound_state,budget
                    if bound_state(lease) is not None:
                        budget(lease,deadline)
                        proof=InitdbTransmission()
                        _transmitted[proof]=(lease,backend,group,backend.server,
                            group.resources['birth'],backend.server._handle,group.command.sha256)
                        return proof
                    # initdb reads one newline-terminated password, then closes
                    # its reader. Keep the server alive until the original Job
                    # exits; write completion alone is not client consumption.
                except BaseException:
                    lease.poisoned=True;backend.server.failed=True
                    if writer.cancel_and_observe(deadline):writer.finish()
                    raise
        finally:group.operation_lock.release()
    return _under_lease(lease,held)


def initialize(security,lease,inputs,specification,register,deadline):
    from .native_trial_authority import require_owner,inherit,budget
    from .native_instance_security import NativeFixedStoreSecurity
    require_owner(security)  # Default refusal; explicit original trial resource only.
    deadline=budget(security,deadline)
    need(type(security) is NativeFixedStoreSecurity and security.lease is lease
         and security.inputs is inputs and callable(register))
    security.processes.cluster.prerequisites.require_system_crt(lease,deadline)
    payload=RuntimePayloadPrerequisite(lease,**security.runtime,native_installation=security.runtime_installation)
    payload.require_for_cluster(lease,deadline)  # Original closed native loading gate.
    owner=security._hold(object.__new__(_RestrictedPrimaryCandidate))
    inherit(security,owner)
    _RestrictedPrimaryCandidate.__init__(owner,TokenProfile.CREATE_CANDIDATE)
    owner.derive();owner.prepare_default_dacl();owner.prepare_owner()
    server=security._hold(object.__new__(_OwnedInitdbPipe))
    _OwnedInitdbPipe.__init__(server,lease,owner);server.create()
    frozen=_freeze(lease,owner,server,specification,data_target=security.target)
    backend=_RestrictedInitdbBackend(frozen,payload,deadline)
    inherit(security,backend)
    adapter=PrivateProcessAdapter(lease,{'initdb':frozen.command},_backend=backend)
    token=adapter.launch('initdb',lambda token:register(adapter,token))
    group=adapter._group(token)
    _resume(lease,backend,group,deadline)
    security.system_crt.observe_group(adapter,token,deadline)
    exchange_deadline=min(deadline-3,time.monotonic()+4)
    observation=verify_running_client(lease,backend,group,exchange_deadline)
    transmission=_transmit(lease,observation,security._secrets['postgres'],exchange_deadline)
    while True:
        left=deadline-time.monotonic()-3;need(left>0)
        code=adapter.observe(token,min(left,1))
        if code is not None:break
    need(type(code) is int and code==0)
    need(adapter.stop_owned(token) is True)
    from .native_trial_facts import completed_initdb
    completed_initdb(lease,adapter,token,transmission)
    return adapter,token
