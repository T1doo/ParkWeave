"""NEW-only fixed private directories; source candidate, no accepted factory.

Directory ownership is not a policy for future dynamic temp/log/files children.
No adoption, mkdir-if-exists, ACL repair, credential or process operation.
"""
import ctypes as C
from dataclasses import dataclass
import math
import os
import time
import weakref

from parkweave.windows_handles import PTR,UnicodeString,ObjectAttributes,IOStatus
from parkweave.windows_files import private_acl,DIRECTORY,REPARSE,UNSAFE_ATTRIBUTES
from .fixed_directories import FixedDirectoryLease,_exclusive_entry,_exclusive_operation
from .fixed_windows_journal import FixedWindowsFilesystem,NativeFixedLeaseAPI
from .endpoint_plan import _key_held
from .native_secret_store_candidate import _NativeSecretFiles,private_file_descriptor

NAMES=('data','secrets','files','logs','tmp')


class LayoutRefused(RuntimeError):pass


def need(ok):
    if not ok:raise LayoutRefused('NATIVE_PRIVATE_LAYOUT_REFUSED')


@dataclass(frozen=True,repr=False)
class _Binding:
    key:tuple
    root_sd:tuple
    root_path:str
    rows:tuple


_issued=weakref.WeakKeyDictionary()
_by_lease=weakref.WeakKeyDictionary()


@_exclusive_entry
def _create(lease,layout):
    return _create_held(lease,layout)


@_exclusive_operation
def _create_held(lease,layout):
    need(type(layout) is _NativeLayout and layout.lease is lease and lease not in _by_lease)
    _by_lease[lease]=layout
    try:
        key=_key_held(lease)
        need(key[-1]==1 and lease.record['phase']=='NEW' and lease.record['initialized'] is False)
        layout._create(key)
    except BaseException:
        layout._fail();raise


@_exclusive_operation
def _leaf_held(lease,layout,name):
    need(type(layout) is _NativeLayout and layout.lease is lease and name in NAMES
         and _by_lease.get(lease) is layout)
    try:
        binding=layout._verify()
        return next(row for row in binding.rows if row[0]==name)  # handle, ID, SD are private data.
    except BaseException:
        layout._fail();raise


@_exclusive_entry
def _close(lease,layout):
    need(type(layout) is _NativeLayout and layout.lease is lease)
    layout._close_owned()


class _NativeLayout:
    native_acceptance=False
    launch_ready=False

    def __init__(self,lease,deadline):
        need(os.name=='nt' and type(lease) is FixedDirectoryLease and
             type(lease.fs) is FixedWindowsFilesystem and type(lease.fs.api) is NativeFixedLeaseAPI)
        need(type(deadline) in (int,float) and math.isfinite(deadline))
        self.lease,self.api,self.deadline=lease,lease.fs.api,deadline
        self.handles=[];self.cleanup_errors=[];self.failed=self.closed=False
        self.probe=None;self.outcome='NOT_CREATED'

    def __reduce__(self):raise TypeError('LAYOUT_NOT_TRANSFERABLE')
    def __copy__(self):raise TypeError('LAYOUT_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo):raise TypeError('LAYOUT_NOT_TRANSFERABLE')

    def create(self):_create(self.lease,self)
    def close(self):_close(self.lease,self)

    def _time(self):need(time.monotonic()<self.deadline)

    def _root(self,key,descriptor,path):
        self._time();self.lease._verify();self.probe._gate()
        need(_key_held(self.lease)==key and self.api is self.lease.fs.api and
             self.api.descriptor(self.lease.fs.root)==descriptor and
             self.api.final_path(self.lease.fs.root)==path)

    def _inspect(self,handle,name,path):
        info=self.api.info(handle)
        need(info.attributes&DIRECTORY and not info.attributes&(REPARSE|UNSAFE_ATTRIBUTES)
             and info.volume==self.lease.fs.root_id[0] and info.identity>0 and
             self.api.final_path(handle)==path+'\\'+name)
        private_acl(self.api.security(handle),self.probe.user)
        sd=self.api.descriptor(handle)
        expected=private_file_descriptor(self.probe.sid_bytes)[20+len(self.probe.sid_bytes):]
        need(sd[0]==self.probe.user and sd[1]&~1 in (0x1004,0x9004) and sd[2]==expected)
        return (info.volume,info.identity),sd

    def _create(self,key):
        self.probe=object.__new__(_NativeSecretFiles)  # Retain partial constructor ownership.
        _NativeSecretFiles.__init__(self.probe,self.lease,self.deadline)  # Identity only, no file opens.
        descriptor=self.api.descriptor(self.lease.fs.root)
        path=self.api.final_path(self.lease.fs.root)
        rows=[];identities={tuple(self.lease.fs.root_id),tuple(self.lease.fs.lock_id),tuple(self.lease.fs.journal_id)}
        for leaf in NAMES:
            self._root(key,descriptor,path)
            raw=leaf.encode('utf-16-le');buffer=C.create_string_buffer(raw+b'\0\0')
            name=UnicodeString(len(raw),len(raw)+2,C.cast(buffer,PTR))
            sd=C.create_string_buffer(private_file_descriptor(self.probe.sid_bytes))
            attrs=ObjectAttributes(C.sizeof(ObjectAttributes),self.lease.fs.root,C.pointer(name),0x40,C.cast(sd,PTR),None)
            handle,io=PTR(),IOStatus()
            status=self.api.ntcreate(C.byref(handle),0x120081,C.byref(attrs),C.byref(io),None,
                0x10,3,2,0x20|0x200000|1,None,0)  # FILE_CREATE only, no existing fallback.
            need(status==0 and handle.value not in (None,PTR(-1).value))
            self.handles.append(handle.value)
            need(io.Information==2)
            identity,security=self._inspect(handle.value,leaf,path)
            need(identity not in identities);identities.add(identity)
            rows.append((leaf,handle.value,identity,security))
            self._root(key,descriptor,path)
        _issued[self]=_Binding(key,descriptor,path,tuple(rows))
        self._verify();self.outcome='NEW_LAYOUT_OBSERVED_NOT_NATIVE_ACCEPTANCE'

    def _verify(self):
        need(not self.failed and not self.closed and _by_lease.get(self.lease) is self)
        binding=_issued.get(self);need(binding is not None)
        self._root(binding.key,binding.root_sd,binding.root_path)
        need(tuple(row[0] for row in binding.rows)==NAMES and tuple(self.handles)==tuple(row[1] for row in binding.rows))
        for name,handle,identity,sd in binding.rows:
            need(self._inspect(handle,name,binding.root_path)==(identity,sd))
        self._root(binding.key,binding.root_sd,binding.root_path)
        return binding

    def _close_owned(self):
        errors=[]
        while self.handles:
            handle=self.handles.pop()
            try:self.api.close(handle)
            except BaseException as error:
                self.cleanup_errors.append(('DIRECTORY_CLOSE_UNKNOWN',handle));errors.append(error)
        self.closed=True
        if errors:
            self.failed=True;self.lease.poisoned=True;self.outcome='UNKNOWN'
            raise BaseExceptionGroup('NATIVE_LAYOUT_CLOSE_UNKNOWN',errors)

    def _fail(self):
        self.failed=True;self.lease.poisoned=True;self.outcome='UNKNOWN'
        try:self._close_owned()
        except BaseException:pass


def native_private_layout():raise LayoutRefused('NATIVE_PRIVATE_LAYOUT_NOT_ACCEPTED')
