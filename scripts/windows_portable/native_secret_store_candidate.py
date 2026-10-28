"""Unwired native three-file source chain; no import-time native calls.

This is not FakeSecretAPI/IsolatedUserProtection. Every native capability is
registered from a successful original handle. Real execution needs separate
native acceptance; the public factory, controller and packaging stay closed.
File flush is not directory durability or an atomic three-file transaction.
"""
import ctypes as C
from dataclasses import dataclass
import hashlib
import math
import os
import struct
import time
import weakref
from threading import get_ident

from parkweave.windows_files import private_acl, DIRECTORY, REPARSE, UNSAFE_ATTRIBUTES
from parkweave.windows_handles import (PTR, UnicodeString, ObjectAttributes, IOStatus, FileInfo,
    nt_status,completed_nt_handle,require_nt_create_ready,retain_pending_nt_create)
from . import credential_envelope as e, endpoint_plan as ep, fixed_secret_store as s
from .dpapi_native_candidate import _NativeDPAPI
from .fixed_directories import FixedDirectoryLease
from .fixed_windows_journal import FixedWindowsFilesystem, NativeFixedLeaseAPI
from .pgdata_candidate import _sid_text, FILE_ALL
from .restricted_token_candidate import _parse


def need(ok):
    if not ok: raise s.StoreRefused('NATIVE_SECRET_SOURCE_REFUSED')


def private_file_descriptor(sid):
    from .default_dacl_candidate import _sid_buffer
    _sid_buffer(sid)
    ace=struct.pack('<BBHI',0,0,8+len(sid),FILE_ALL)+sid
    acl=struct.pack('<BBHHH',2,0,8+len(ace),1,0)+ace
    return struct.pack('<BBHIIII',1,0,0x9004,20,0,0,20+len(sid))+sid+acl


class _NativeCapability:
    __slots__=('__weakref__',)
    def __reduce__(self): raise TypeError('NATIVE_SECRET_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('NATIVE_SECRET_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo): raise TypeError('NATIVE_SECRET_NOT_TRANSFERABLE')


@dataclass
class _Owned:
    handle: int
    parent: object
    leaf: str
    directory: bool
    created: bool
    creation_descriptor: tuple = None
    close_attempted: bool = False
    write_attempted: bool = False
    flush_attempted: bool = False
    closed: bool = False


class _NativeSecretFiles:
    """Fixed names and private original-HANDLE registry, no arbitrary Path API."""
    def __init__(self,lease,deadline,*,layout=None):
        need(os.name=='nt' and C.sizeof(PTR)==8 and type(lease) is FixedDirectoryLease
             and type(lease.fs) is FixedWindowsFilesystem and type(lease.fs.api) is NativeFixedLeaseAPI)
        need(type(deadline) in (int,float) and math.isfinite(deadline))
        self.lease,self.api,self.deadline=lease,lease.fs.api,deadline
        self.key=ep._key_held(lease)
        self.layout=layout
        need(self.key[-1]==1 or layout is None)
        self.caps={}; self.temporary=[]; self.failed=False; self.unknown=[]
        self.thread=self.api.k.GetCurrentThread
        self.thread.argtypes,self.thread.restype=[],PTR
        self.open_thread=self.api.a.OpenThreadToken
        self.open_thread.argtypes,self.open_thread.restype=[PTR,C.c_uint32,C.c_int32,C.POINTER(PTR)],C.c_int32
        self.sid_bytes=self.current_sid_bytes()
        self.user=_sid_text(self.sid_bytes)
        need(self.api.user_sid()==self.user)

    def _time(self): need(time.monotonic()<self.deadline)

    def _close_temporary(self,entry):
        need(not entry['attempted']);entry['attempted']=True
        try:self.api.close(entry['handle']);entry['closed']=True
        except BaseException:
            self.unknown.append(('TOKEN_CLOSE_UNKNOWN',entry['handle']));self.failed=True
            raise

    def current_sid_bytes(self):
        self._time()
        token=PTR()
        ok=self.open_thread(self.thread(),8,True,C.byref(token))
        error=C.get_last_error() if not ok else None
        if ok:
            need(token.value not in (None,PTR(-1).value))
            entry=dict(handle=token.value,attempted=False,closed=False);self.temporary.append(entry)
            primary=s.StoreRefused('THREAD_IMPERSONATION_REFUSED')
            try:self._close_temporary(entry)
            except BaseException as cleanup:raise BaseExceptionGroup('THREAD_TOKEN_CLOSE_UNKNOWN',[primary,cleanup])
            raise primary
        need(error==1008)  # ERROR_NO_TOKEN, never RevertToSelf or OpenAsSelf fallback.
        token=PTR();used=C.c_uint32();buffer=C.create_string_buffer(4096)
        self.api.need(self.api.opentoken(self.api.process(),8,C.byref(token)))
        need(token.value not in (None,PTR(-1).value))
        entry=dict(handle=token.value,attempted=False,closed=False);self.temporary.append(entry)
        primary=cleanup=None;value=None
        try:
            self.api.need(self.api.tokeninfo(token,1,buffer,len(buffer),C.byref(used)))
            value=_parse(buffer,used.value,1)
        except BaseException as error:primary=error
        finally:
            try:self._close_temporary(entry)
            except BaseException as error:cleanup=error
        if primary is not None or cleanup is not None:
            raise BaseExceptionGroup('NATIVE_USER_QUERY_UNKNOWN',[x for x in (primary,cleanup) if x is not None])
        return value

    def _gate(self):
        need(not self.failed and type(self.lease) is FixedDirectoryLease and
             type(self.lease.fs) is FixedWindowsFilesystem and self.api is self.lease.fs.api)
        self._time();need(ep._key_held(self.lease)==self.key and self.current_sid_bytes()==self.sid_bytes)

    def binds(self,lease):
        need(lease is self.lease);self._gate()
        if self.key[-1]==1:
            from .native_layout_candidate import _leaf_held
            _leaf_held(lease,self.layout,'secrets')
        return True

    def owns(self,cap,lease,parent):
        # Cleanup must remain possible after poisoning/identity or time failure.
        row=self.caps.get(cap) if type(cap) is _NativeCapability else None
        return (lease is self.lease and row is not None and not row.close_attempted and row.parent is parent)

    def _row(self,cap):
        need(type(cap) is _NativeCapability and cap in self.caps)
        row=self.caps[cap];need(not row.close_attempted);return row

    def _open(self,parent,leaf,*,directory,create):
        self._gate()
        require_nt_create_ready(self.api.readonly)
        if directory:
            need(leaf=='secrets' and parent==self.lease.fs.root and self._parent_cap is None and not create)
        else:
            from .native_preparation_sessions import PreparationFile
            need(leaf in (*s.NAMES.values(), *(kind.value for kind in PreparationFile)) and self._parent_cap in self.caps and
                 self._row(self._parent_cap).handle==parent and self._row(self._parent_cap).directory)
        text=leaf.encode('utf-16-le');buffer=C.create_string_buffer(text+b'\0\0')
        name=UnicodeString(len(text),len(text)+2,C.cast(buffer,PTR))
        raw=private_file_descriptor(self.sid_bytes) if create else None
        descriptor=C.create_string_buffer(raw) if raw is not None else None
        attributes=ObjectAttributes(C.sizeof(ObjectAttributes),parent,C.pointer(name),0x40,
                                   C.cast(descriptor,PTR) if descriptor is not None else None,None)
        handle,io=PTR(),IOStatus()
        access=0x120081|(0x40000000 if create else 0)
        status=self.api.ntcreate(C.byref(handle),access,C.byref(attributes),C.byref(io),None,
            0x10 if directory else 0x80,0 if create else 1,2 if create else 1,
            0x20|0x200000|(1 if directory else 0x40),None,0)
        status=nt_status(status)
        if status==0x103:
            retain_pending_nt_create(self.api.readonly,handle,io,attributes,name,buffer,descriptor)
            need(False)
        need(completed_nt_handle(status,handle.value))
        cap=_NativeCapability();self.caps[cap]=_Owned(handle.value,self._parent_cap,leaf,directory,create)
        try:
            need(status==0)
            need(io.Information==(2 if create else 1))  # CREATED / OPENED.
            self.inspect(cap)
            self.caps[cap].creation_descriptor=self.api.descriptor(handle.value)
            return cap
        except BaseException as primary:
            self.failed=True
            try:self.close(cap)
            except BaseException as cleanup:raise BaseExceptionGroup('NATIVE_SECRET_OPEN_CLOSE_UNKNOWN',[primary,cleanup])
            raise

    def open_secrets(self,lease):
        need(lease is self.lease and not any(not r.close_attempted for r in self.caps.values()))
        self.binds(lease)  # NEW must consume the exact layout capability; REOPEN never creates it.
        self._parent_cap=None
        return self._open(lease.fs.root,'secrets',directory=True,create=False)

    def open_file(self,directory,purpose,*,create):
        need(type(purpose) is e.Purpose and type(create) is bool)
        parent=self._row(directory);need(parent.directory and parent.parent is None)
        self._parent_cap=directory
        return self._open(parent.handle,s.NAMES[purpose],directory=False,create=create)

    def open_preparation_file(self,directory,kind,*,create):
        from .native_preparation_sessions import PreparationFile
        need(type(kind) is PreparationFile and type(create) is bool)
        parent=self._row(directory);need(parent.directory and parent.parent is None)
        self._parent_cap=directory
        return self._open(parent.handle,kind.value,directory=False,create=create)

    def inspect(self,cap):
        self._gate();row=self._row(cap);info=self.api.info(row.handle)
        need(not info.attributes&(REPARSE|UNSAFE_ATTRIBUTES) and bool(info.attributes&DIRECTORY)==row.directory
             and info.volume==self.key[1][0] and info.identity>0 and
             (row.directory or info.links==1) and 0<=info.size<=e.MAX_CIPHERTEXT)
        descriptor=self.api.descriptor(row.handle)
        private_acl(self.api.security(row.handle),self.user)
        need(descriptor[0]==self.user)
        if row.directory and self.key[-1]==1:
            from .native_layout_candidate import _leaf_held
            _,_,identity,sd=_leaf_held(self.lease,self.layout,'secrets')
            need((info.volume,info.identity)==identity and descriptor==sd)
        if not row.directory:
            raw=private_file_descriptor(self.sid_bytes)[20+len(self.sid_bytes):]
            need(descriptor[2]==raw and descriptor[1]&~1 in (0x1004,0x9004))
        parent_id=self.key[1] if row.parent is None else self.inspect(row.parent).identity
        parent_handle=self.lease.fs.root if row.parent is None else self._row(row.parent).handle
        need(self.api.final_path(row.handle)==self.api.final_path(parent_handle).rstrip('\\')+'\\'+row.leaf)
        detail=FileInfo();self.api.need(self.api.getinfo(row.handle,C.byref(detail)))
        revision=(detail.Creation.High<<96)|(detail.Creation.Low<<64)|(detail.Write.High<<32)|detail.Write.Low
        return s.ObjectInfo((info.volume,info.identity),parent_id,row.leaf,row.directory,
                            descriptor[0],descriptor[1],descriptor[2],True,False,info.links,info.size,revision)

    def creation_descriptor(self,cap):
        self._gate();row=self._row(cap);need(row.created and row.creation_descriptor is not None)
        return row.creation_descriptor

    def _seek(self,row):
        seek=self.api.k.SetFilePointerEx
        seek.argtypes,seek.restype=[PTR,C.c_int64,PTR,C.c_uint32],C.c_int32
        self.api.need(seek(row.handle,0,None,0))

    def read(self,cap,limit):
        self._gate();row=self._row(cap)
        need(not row.directory and type(limit) is int and 0<limit<=e.MAX_CIPHERTEXT+1)
        self._seek(row);return self.api.read(row.handle,limit)

    def write(self,cap,raw):
        self._gate();row=self._row(cap)
        need(row.created and not row.directory and not row.write_attempted and type(raw) is bytes
             and 0<len(raw)<=e.MAX_CIPHERTEXT)
        row.write_attempted=True  # One attempt, including short/unknown outcome.
        self._seek(row);buffer=C.create_string_buffer(raw);count=C.c_uint32()
        self.api.need(self.api.writefile(row.handle,buffer,len(raw),C.byref(count),None))
        need(count.value<=len(raw));return count.value

    def flush(self,cap):
        self._gate();row=self._row(cap)
        need(row.created and row.write_attempted and not row.flush_attempted)
        row.flush_attempted=True;self.api.flush(row.handle);return True

    def close(self,cap):
        row=self._row(cap);row.close_attempted=True  # No lease/SID check before cleanup.
        try:self.api.close(row.handle);row.closed=True
        except BaseException:
            self.failed=True;self.unknown.append(('FILE_CLOSE_UNKNOWN',row.handle));raise
        return True


class _CurrentUserProtection:
    def __init__(self,files):
        need(type(files) is _NativeSecretFiles)
        self.files,self.native,self.failed=files,_NativeDPAPI(),False

    def _call(self,method,raw,entropy):
        need(not self.failed and type(self.native) is _NativeDPAPI and not self.native.failed)
        try:
            self.files._gate()
            result=getattr(self.native,method)(raw,entropy)
            self.files._gate()
            return result
        except BaseException:
            self.failed=True;raise

    def protect(self,raw,entropy):return self._call('protect',raw,entropy)
    def unprotect(self,raw,entropy):return self._call('unprotect',raw,entropy)


class _NativeOperation(s._Operation):
    def check_binding(self):
        need(type(self.store) is _NativeFixedSecretStore)
        self.store._native_check()
        super().check_binding()

    def _admit_cap(self,cap):
        need(type(cap) is _NativeCapability and cap in self.store.api.caps)


@dataclass(frozen=True,repr=False)
class _ReadForReopen:
    state: s.PrivateState


class _Ticket:
    __slots__=('__weakref__',)
    def __reduce__(self):raise TypeError('NATIVE_RECOVERY_NOT_TRANSFERABLE')
    def __copy__(self):raise TypeError('NATIVE_RECOVERY_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo):raise TypeError('NATIVE_RECOVERY_NOT_TRANSFERABLE')


class RecoveredInstance:
    __slots__=('__weakref__',)
    def __reduce__(self):raise TypeError('NATIVE_RECOVERY_NOT_TRANSFERABLE')
    def __copy__(self):raise TypeError('NATIVE_RECOVERY_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo):raise TypeError('NATIVE_RECOVERY_NOT_TRANSFERABLE')


_tickets=weakref.WeakKeyDictionary()
_recoveries=weakref.WeakKeyDictionary()


def _consume_ticket(lease,ticket,stage):
    need(type(ticket) is _Ticket and type(lease) is FixedDirectoryLease and
         lease._operation_owner==get_ident() and lease._operation_depth>0)
    fact=_tickets.get(ticket)
    need(fact is not None)
    store,snapshot,state,digest,request,expected=fact
    need(type(store) is _NativeFixedSecretStore and store.lease is lease and
         store._finalizing is ticket and not store.failed and expected==stage)
    _tickets.pop(ticket)  # Consume before all fallible final observations.
    store._native_check()
    need(lease.snapshot==snapshot and s._Operation._value_digest((state.database,state.sessions,state.config))==digest)
    return store,state,request


class _NativeFixedSecretStore(s.IsolatedFixedSecretStore):
    """Reuses the checked algorithm, never the fake constructor or proof domain."""
    fixture_only=False
    native_acceptance=False
    launch_ready=False

    def __init__(self,lease,runtime,deadline,*,layout=None):
        self.api=object.__new__(_NativeSecretFiles)
        _NativeSecretFiles.__init__(self.api,lease,deadline,layout=layout)
        self.api.binds(lease)
        self.lease=lease;key=self.api.key
        self.binding=e.InstanceBinding(key[0],self.api.user,key[1],key[2],key[3]);self.binding.record()
        e.exact(runtime,('source_commit','manifest_sha256'))
        e.digest(runtime['source_commit'],40);e.digest(runtime['manifest_sha256'])
        self.runtime=e.canonical(runtime)
        self.protection=_CurrentUserProtection(self.api)
        self._config_format=e.ConfigFormat.PGDATA_SCHEMA4
        self.failed=False;self._unknown_caps=[];self._endpoint_finalizing=None
        self._finalizing=None;self._reopen_attempted=False

    def _native_check(self):
        need(type(self) is _NativeFixedSecretStore and not self.failed and
             type(self.api) is _NativeSecretFiles and self.api.lease is self.lease and
             type(self.protection) is _CurrentUserProtection and self.protection.files is self.api and
             not self.protection.failed and type(self.protection.native) is _NativeDPAPI and
             not self.protection.native.failed and
             self.config_format is e.ConfigFormat.PGDATA_SCHEMA4)
        self.api._gate()

    def _new_operation(self):
        return _NativeOperation(self)

    def read_for_reopen(self):
        def read(ctx):
            need(not self._reopen_attempted);self._reopen_attempted=True
            need(ep._key_held(self.lease)[-1]>=2)
            return _ReadForReopen(self._read_state(ctx))
        return self._operate({'READY_STOPPED':True},read)

    def _finalize_closed(self,context,result):
        if type(result) is not _ReadForReopen:
            need(type(result) not in (s._EndpointRecovery,s._AuthenticationRecovery))
            return result
        need(type(context) is _NativeOperation and context.store is self)
        request=context.consume_read_state(result.state)  # One real three-file read/close set.
        state=result.state
        need(e.canonical(state.config['runtime'])==self.runtime)
        ticket=_Ticket();snapshot=self.lease.snapshot
        digest=s._Operation._value_digest((state.database,state.sessions,state.config))
        self._finalizing=ticket;target=None
        try:
            _tickets[ticket]=(self,snapshot,state,digest,request,'PGDATA')
            from .pgdata_candidate import _recover_held
            target=_recover_held(self.lease,ticket,self.api.deadline)
            self._native_check();target._verify()
            _tickets[ticket]=(self,snapshot,state,digest,request,'ENDPOINT')
            plan=ep._register_held(self.lease,None,ep.PlanMode.REOPEN,native_recovery=ticket)
            self._native_check();target._verify()
            need(self.lease.snapshot==snapshot)
            recovered=RecoveredInstance()
            _recoveries[recovered]=(self,snapshot,state,plan,target,digest)
            return recovered
        except BaseException:
            if target is not None:target._fail()
            raise
        finally:
            self._finalizing=None;_tickets.pop(ticket,None)

    def _consume_recovered_held(self,recovered):
        need(self.lease._operation_owner==get_ident() and self.lease._operation_depth>0
             and type(recovered) is RecoveredInstance)
        fact=_recoveries.get(recovered)
        need(fact is not None and fact[0] is self)
        _recoveries.pop(recovered)  # Own result consumed before any fallible native check.
        _,snapshot,state,plan,target,digest=fact
        try:
            self._native_check()
            need(self.lease.snapshot==snapshot and
                 digest==s._Operation._value_digest((state.database,state.sessions,state.config)))
            target._verify();ep._record_held(self.lease,plan,mode=ep.PlanMode.REOPEN)
            return state,plan,target  # Not socket ownership or DB/actor authority.
        except BaseException as primary:
            self.failed=True;self.lease.poisoned=True
            previous=len(target.cleanup_errors);target._fail()
            cleanup=[s.StoreRefused('PGDATA_CLOSE_UNKNOWN') for _ in target.cleanup_errors[previous:]]
            raise s.StoreFailure(primary,cleanup,None) from None


def native_secret_store():
    raise s.StoreRefused('NATIVE_SECRET_STORE_NOT_ACCEPTED')
