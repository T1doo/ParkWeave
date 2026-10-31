"""Concrete LocalService DPAPI peer; source-only until its exact trial approval.

No account/profile creation, password, privilege adjustment or primary-token
setter. A dedicated owned thread alone impersonates the documented built-in
service logon. CurrentUser DPAPI may create service-profile key material; runner
disposal owns that cleanup. Native calls are cooperative, not forcibly cancelled.
"""
import ctypes as C
from hashlib import sha256
import os
import threading
import time

from . import native_trial_authority as a
from .restricted_token_candidate import _parse,_dacl_bytes

P=C.c_void_p;D=C.c_uint32;B=C.c_int32
_retained=[]
OPERATION='TEMP_LOCAL_SERVICE_DPAPI_PEER'


def bind(lib,name,result,args):
    f=getattr(lib,name);f.restype=result;f.argtypes=args;return f


class LocalServiceDPAPIPeer:
    def __init__(self,lease,cipher,entropy,deadline):
        value=a.bound_state(lease)
        a.need(value is not None and OPERATION in value.window.operations and os.name=='nt'
            and type(cipher) is bytes and type(entropy) is bytes and len(entropy)==32)
        from .native_acceptance_issuer import _deadline
        _deadline(deadline)
        self.deadline=a.budget(lease,deadline);self.lease=lease
        self.cipher,self.entropy=cipher,entropy
        self.failed=False;self.complete=False;self.started=False;self.handles=[];self.thread=None
        self.thread_handle=None;self.worker_error=None;self.observation=None
        self.impersonation_attempted=False;self.reverted=False
        _retained.append(self)  # Before construction or thread ownership can fail.
        self.k=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
        self.adv=C.WinDLL('advapi32.dll',use_last_error=True,winmode=0x800)
        self.close_handle=bind(self.k,'CloseHandle',B,[P])
        self.current_process=bind(self.k,'GetCurrentProcess',P,[])
        self.current_thread=bind(self.k,'GetCurrentThread',P,[])
        self.thread_id=bind(self.k,'GetThreadId',D,[P])
        self.wait=bind(self.k,'WaitForSingleObject',D,[P,D])
        self.duplicate=bind(self.k,'DuplicateHandle',B,[P,P,P,C.POINTER(P),D,B,D])
        self.open_primary=bind(self.adv,'OpenProcessToken',B,[P,D,C.POINTER(P)])
        self.open_thread=bind(self.adv,'OpenThreadToken',B,[P,D,B,C.POINTER(P)])
        self.query=bind(self.adv,'GetTokenInformation',B,[P,D,P,D,C.POINTER(D)])
        self.logon=bind(self.adv,'LogonUserW',B,[C.c_wchar_p,C.c_wchar_p,C.c_wchar_p,D,D,C.POINTER(P)])
        self.impersonate=bind(self.adv,'ImpersonateLoggedOnUser',B,[P])
        self.revert=bind(self.adv,'RevertToSelf',B,[])

    def _time(self):
        a.need(not self.failed and time.monotonic()<self.deadline)

    def _output(self,call,*args):
        output=P();row=dict(output=output,owned=False,attempted=False,closed=False)
        self.handles.append(row)  # Original output storage before its call.
        ok=call(*args,C.byref(output));row['owned']=bool(ok and output.value)
        a.need(ok and row['owned']);return output.value

    def _snapshot(self,token):
        result=[]
        for kind in (1,2,3,4,6,8):
            self._time();raw=C.create_string_buffer(65536);used=D()
            a.need(self.query(token,kind,raw,len(raw),C.byref(used)))
            value=_dacl_bytes(raw,used.value) if kind==6 else _parse(raw,used.value,kind)
            if type(value) is dict:value=tuple(sorted(value.items()))
            result.append((kind,value))
        return tuple(result)

    def _duplicate_thread(self):
        output=P();row=dict(output=output,owned=False,attempted=False,closed=False)
        self.handles.append(row)
        process=self.current_process()
        ok=self.duplicate(process,self.current_thread(),process,C.byref(output),0,False,2)
        row['owned']=bool(ok and output.value)
        a.need(ok and row['owned']);return output.value

    def _no_thread_token(self):
        output=P();row=dict(output=output,owned=False,attempted=False,closed=False)
        self.handles.append(row)
        ok=self.open_thread(self.current_thread(),8,True,C.byref(output))
        error=C.get_last_error()
        row['owned']=bool(ok and output.value)
        a.need(not ok and not output.value and error==1008)

    def _close_owned(self):
        for row in reversed(self.handles):
            if not row['owned'] or row['closed']:continue
            self._time();a.need(not row['attempted']);row['attempted']=True
            a.need(self.close_handle(row['output'].value));row['closed']=True

    def _effective(self,identity):
        # Query the CURRENT effective token again, never a previously opened
        # token object that would survive reversion/replacement of the thread.
        self._time();token=self._output(self.open_thread,self.current_thread(),8,True)
        observed=self._snapshot(token)
        a.need(dict(observed)[1]==dict(identity)[1] and dict(observed)[8]==2)
        return observed

    def _worker(self):
        # Only this frozen method can be the thread entry, never a callback.
        try:
            self._time();self._no_thread_token()
            self.thread_handle=self._duplicate_thread()
            a.need(self.thread_id(self.thread_handle)==threading.get_native_id())
            service=self._output(self.logon,'LocalService','NT AUTHORITY',None,5,0)
            identity=self._snapshot(service)
            from .native_protected_objects import sid_bytes
            a.need(dict(identity)[1]==sid_bytes('S-1-5-19') and dict(identity)[8]==1
                and dict(self.primary_before)[1]!=dict(identity)[1])
            self._time();self.impersonation_attempted=True
            a.need(self.impersonate(service))
            effective=self._effective(identity)
            from .dpapi_native_candidate import _NativeDPAPI,NativeFailure
            self.control_crypto=_NativeDPAPI();self.refusal_crypto=_NativeDPAPI()
            control=b'ParkWeave LocalService DPAPI positive control v1'
            self._effective(identity)
            protected=self.control_crypto.protect(control,self.entropy)
            self._effective(identity);a.need(self.control_crypto.unprotect(protected,self.entropy)==control)
            self._effective(identity)
            try:self.refusal_crypto.unprotect(self.cipher,self.entropy)
            except NativeFailure as error:
                a.need(error.winerror==13 and error.primary_type=='ProtectionRefused'
                    and error.phase=='ALLOCATION' and not error.cleanup_types and not self.refusal_crypto.unknown)
            else:a.need(False)
            self._effective(identity)
            self.observation=(self.thread_id(self.thread_handle),identity,effective,
                sha256(protected).hexdigest(),sha256(self.cipher).hexdigest(),sha256(self.entropy).hexdigest())
        except BaseException as error:self.worker_error=type(error).__name__
        finally:
            if self.impersonation_attempted:
                try:
                    # Always attempt exactly one reversion even if work expired.
                    a.need(self.revert());self.reverted=True;self._no_thread_token()
                except BaseException as error:self.worker_error=type(error).__name__

    def run(self):
        try:
            a.budget(self.lease,self.deadline);self._time();a.need(not self.started);self.started=True
            self._no_thread_token()
            primary=self._output(self.open_primary,self.current_process(),8)
            self.primary_before=self._snapshot(primary)
            self.thread=threading.Thread(target=self._worker,name='ParkWeave-LocalService-DPAPI',daemon=True)
            self.thread.start();self.thread.join(max(0,self.deadline-time.monotonic()))
            self._time();a.need(not self.thread.is_alive() and self.thread_handle and not self.worker_error
                and self.reverted and self.observation is not None
                and self.thread_id(self.thread_handle)==self.thread.native_id)
            left=self.deadline-time.monotonic();a.need(left>0)
            a.need(self.wait(self.thread_handle,int(left*1000))==0)
            self._no_thread_token();a.need(self._snapshot(primary)==self.primary_before)
            a.budget(self.lease,self.deadline)
            self._close_owned();self.complete=True
            self.cipher=self.entropy=None  # No secret data in the emitted record.
            return self.observation
        except BaseException:
            self.failed=True  # Unknown live worker/token/close is retained; never retry.
            a.fail_resource(self.lease)
            raise
