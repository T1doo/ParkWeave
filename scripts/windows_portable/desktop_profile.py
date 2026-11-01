"""Stable current-user WebView2 data under the original running instance.

New-only protected directory creation, reopen-only original directory reads.
No ACL setters, profile repair/deletion, shared browser profile or secrets file.
This does not admit WebView2 loading or establish Windows durability.
"""
import ctypes as C
from hashlib import sha256
import os
import time

from parkweave.windows_files import private_acl,DIRECTORY,REPARSE,UNSAFE_ATTRIBUTES
from parkweave.windows_handles import (PTR,UnicodeString,ObjectAttributes,IOStatus,
    completed_nt_handle,require_nt_create_ready,retain_pending_nt_create,query_call,require_query_ready)
from .fixed_secret_store import _under_lease
from .fixed_directories import FixedDirectoryLease
from .fixed_windows_journal import FixedWindowsFilesystem,NativeFixedLeaseAPI
from .native_secret_store_candidate import _NativeSecretFiles
from .pgdata_candidate import root_descriptor,check_descriptor,check_security,descriptor_digest
from .processes import PrivateProcessAdapter

_unknown=[]


def need(value):
    if not value:raise RuntimeError('DESKTOP_PROFILE_REFUSED')


class NativeDesktopProfile:
    def __init__(self,workspace,invocation,fresh):
        self.workspace=workspace;self.handles=[];self.close_attempted=False
        self.failed=False;self.api=self.probe=None
        try:
            workspace.check();adapter=workspace.application.adapter
            from .local_preparation import LocalPreparationInvocation
            need(os.name=='nt' and type(fresh) is bool and type(adapter) is PrivateProcessAdapter)
            need(type(invocation) is LocalPreparationInvocation and invocation.processes.application is workspace.application)
            self.lease=adapter.lease
            need(type(self.lease) is FixedDirectoryLease and type(self.lease.fs) is FixedWindowsFilesystem
                 and type(self.lease.fs.api) is NativeFixedLeaseAPI)
            self.api=self.lease.fs.api
            from .native_instance_security import NativeFixedStoreSecurity
            from .native_preparation_sessions import NativePreparationSessionProvider,PreparationFile
            self.security=invocation.security.security;self.provider=invocation.security.provider
            need(type(self.security) is NativeFixedStoreSecurity and type(self.provider) is NativePreparationSessionProvider
                 and self.provider.security is self.security and self.security.lease is self.lease)
            _under_lease(self.lease,lambda:self._open(fresh))
            # Exact original directory identities survive process/host restart.
            # First desktop use of an existing installation requires a separate
            # explicit CREATE, never OPEN-failed fallback or adoption.
            binding=dict(schema='parkweave-desktop-profile/1',leaf=self.leaf,
                sid_sha256=sha256(self.probe.sid_bytes).hexdigest(),
                parent_id=list(self.parent_fact[0]),profile_id=list(self.profile_fact[0]),
                parent_sd_sha256=descriptor_digest(self.parent_fact[1]),
                profile_sd_sha256=descriptor_digest(self.profile_fact[1]))
            stored=self.security._run(self.lease,lambda deadline:self.provider._file(
                self.security.store,PreparationFile.DESKTOP_PROFILE,binding if fresh else None))
            need(stored==binding)
            self.verify()
        except BaseException:
            self.failed=True
            _unknown.append(self)  # retain partial native outputs/lease/API before surfacing
            raise

    def _inspect(self,handle,path,*,profile):
        info=self.api.info(handle)
        need(info.attributes&DIRECTORY and not info.attributes&(REPARSE|UNSAFE_ATTRIBUTES)
             and info.volume==self.lease.fs.root_id[0] and info.identity>0
             and self.api.final_path(handle)==path)
        sd=self.api.descriptor(handle)
        if profile:
            check_security(self.api.security(handle),self.probe.user,root=True,directory=True)
            check_descriptor(sd,self.probe.sid_bytes,root=True,directory=True)
        else:private_acl(self.api.security(handle),self.probe.user)
        return (info.volume,info.identity),sd

    def _open(self,fresh):
        self.lease._verify();need(self.lease.record['phase']=='RUNNING')
        self.probe=object.__new__(_NativeSecretFiles)
        _NativeSecretFiles.__init__(self.probe,self.lease,time.monotonic()+10)
        self.root_path=self.api.final_path(self.lease.fs.root)
        parent=self.api.open_relative(self.lease.fs.root,'files',False);self.handles.append(parent)
        self.parent=parent
        self.parent_fact=self._inspect(parent,self.root_path+'\\files',profile=False)
        self.leaf='desktop-webview2-'+sha256(self.probe.sid_bytes).hexdigest()[:24]
        self.native_path=self.root_path+'\\files\\'+self.leaf
        require_nt_create_ready(self.api.readonly)
        raw=self.leaf.encode('utf-16-le');buffer=C.create_string_buffer(raw+b'\0\0')
        name=UnicodeString(len(raw),len(raw)+2,C.cast(buffer,PTR))
        sd=C.create_string_buffer(root_descriptor(self.probe.sid_bytes)) if fresh else None
        attrs=ObjectAttributes(C.sizeof(ObjectAttributes),parent,C.pointer(name),0x40,
            C.cast(sd,PTR) if sd is not None else None,None)
        handle,io=PTR(),IOStatus()
        from .native_protected_objects import submit_create
        status=submit_create(self.api,handle,io,attrs,(name,buffer,sd),access=0x120081,
            attributes=0x10,share=3,disposition=2 if fresh else 1,options=0x20|0x200000|1)
        if status==0 and io.Status not in (None,0):
            retain_pending_nt_create(self.api.readonly,handle,io,attrs,name,buffer,sd);need(False)
        if not completed_nt_handle(status,handle.value):
            if status>=0 or handle.value not in (None,0):
                retain_pending_nt_create(self.api.readonly,handle,io,attrs,name,buffer,sd)
            need(False)
        self.handles.append(handle.value);self.profile=handle.value
        need(status==0 and io.Information==(2 if fresh else 1))
        self.profile_fact=self._inspect(self.profile,self.native_path,profile=True)
        # WebView2 receives a conventional absolute DOS path. Authority remains
        # the retained original HANDLE and volume/file identity, not this text.
        count,text=self._dos_path()
        need(4<count<4096 and text.startswith('\\\\?\\')
             and len(text)>6 and text[5:7]==':\\')
        self.path=text[4:]
        self.dos_path=text
        self._verify()

    def _dos_path(self):
        buffer=C.create_unicode_buffer(4096)
        count=query_call(self.api.readonly,'DESKTOP_PROFILE_DOS_PATH',self.api.getpath,
            (self.profile,buffer,len(buffer),0),(self,buffer))
        return count,buffer.value

    def _verify(self):
        need(not self.failed and not self.close_attempted)
        self.lease._verify();need(self.lease.record['phase']=='RUNNING')
        self.probe.deadline=time.monotonic()+5;self.probe._gate()
        need(self.api.final_path(self.lease.fs.root)==self.root_path
             and self._inspect(self.parent,self.root_path+'\\files',profile=False)==self.parent_fact
             and self._inspect(self.profile,self.native_path,profile=True)==self.profile_fact)
        count,text=self._dos_path();need(0<count<4096 and text==self.dos_path)

    def verify(self):
        try:
            self.workspace.check()  # Public lease status only outside its gate.
            return _under_lease(self.lease,self._verify)
        except BaseException:
            self.failed=True;_unknown.append(self);raise

    def close(self):
        need(not self.close_attempted);self.close_attempted=True
        try:
            require_nt_create_ready(self.api.readonly);require_query_ready(self.api.readonly)
        except BaseException:
            self.failed=True;self.lease.poisoned=True;_unknown.append(self);raise
        errors=[]
        for handle in reversed(self.handles):
            try:self.api.close(handle)
            except BaseException as error:errors.append(error)
        if errors:
            self.failed=True;self.lease.poisoned=True;_unknown.append(self)
            raise BaseExceptionGroup('DESKTOP_PROFILE_CLOSE_UNKNOWN',errors)
        self.handles.clear()
