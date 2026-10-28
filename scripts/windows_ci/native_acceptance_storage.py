"""Owned native test objects only; no product lease or acceptance is issued.

Construction WOULD create one protected directory and bounded fixed-name files.
The reviewed harness window must precede construction. No native import work,
path deletion, existing-object adoption, ACL repair or security setter here.
"""
import ctypes as C
from dataclasses import dataclass,field
import os
import re
import time

from parkweave.windows_files import root_parts,private_acl,DIRECTORY,REPARSE,UNSAFE_ATTRIBUTES
from parkweave.windows_handles import (PTR,UnicodeString,ObjectAttributes,IOStatus,FileInfo,
    nt_status,completed_nt_handle,require_nt_create_ready,retain_pending_nt_create)
from scripts.windows_portable.fixed_windows_journal import NativeFixedLeaseAPI
from scripts.windows_portable.native_secret_store_candidate import private_file_descriptor
from scripts.windows_portable.restricted_token_candidate import _parse,_dacl_bytes
from scripts.windows_portable.pgdata_candidate import _sid_text,directory_batch
from scripts.windows_portable import fixed_journal as journal

_unknown=[]
NAMES=frozenset(('lock.bin','journal.bin','torn.bin','identities.dpapi'))


def need(ok):
    if not ok:raise RuntimeError('NATIVE_ACCEPTANCE_STORAGE_REFUSED')


@dataclass(repr=False,eq=False)
class Node:
    handle:int
    name:str
    parent:int
    directory:bool
    created:bool=False
    identity:tuple|None=None
    descriptor:tuple|None=None
    path:str|None=None
    size:int=0
    closed:bool=False
    close_attempted:bool=False
    delete_attempted:bool=False
    origin:object=field(default=None,repr=False)


class OwnedNativeObjects:
    """Real original-HANDLE implementation; never a FixedDirectoryLease."""
    def __init__(self,parent,deadline,window_name):
        self.nodes=[];self.ancestors=[];self.entries={};self.failed=False;self.closed=False
        self.api=None;self.root=None;self.deadline=deadline;self.buffers=[]
        self.ancestor_closes=[]
        self.query_tokens=[]
        need(os.name=='nt' and C.sizeof(PTR)==8)
        need(type(window_name) is str and re.fullmatch('parkweave-native-acceptance-[a-f0-9]{24}',window_name))
        self.api=NativeFixedLeaseAPI();self._time()
        self.api.require_fixed_file_prerequisites(parent)
        self.sid=self._sid();self.user=_sid_text(self.sid);need(self.user==self.api.user_sid())
        k=self.api.readonly.k
        self.seek=k.SetFilePointerEx;self.seek.argtypes=[PTR,C.c_int64,PTR,C.c_uint32];self.seek.restype=C.c_int32
        self.query=k.GetFileInformationByHandleEx
        self.query.argtypes=[PTR,C.c_int32,PTR,C.c_uint32];self.query.restype=C.c_int32
        self.disposition=k.SetFileInformationByHandle
        self.disposition.argtypes=[PTR,C.c_int32,PTR,C.c_uint32];self.disposition.restype=C.c_int32
        drive,parts=root_parts(parent);handle=self.api.open_drive(drive);self.ancestors.append(handle)
        need(self.api.filesystem(handle)=='NTFS' and self.api.drive_type(self.api.final_path(handle))==3)
        for component in parts:
            handle=self.api.open_relative(handle,component,False);self.ancestors.append(handle)
            info=self.api.info(handle);need(info.attributes&DIRECTORY and not info.attributes&(REPARSE|UNSAFE_ATTRIBUTES))
        self.anchor=handle;self.anchor_id=self._id(handle)
        self.anchor_sd=self.api.descriptor(handle);self.anchor_path=self.api.final_path(handle)
        # Deterministic per approved invocation. Retain this empty marker after
        # success, so a second process cannot rerun the window by new RNG.
        self.root=self._open(handle,window_name,directory=True,create=True)
        self.root_id=list(self.root.identity)

    def _time(self):need(not self.closed and time.monotonic()<self.deadline)
    def _id(self,h):
        row=self.api.info(h);return row.volume,row.identity

    def _sid(self):
        # Explicitly refuse thread impersonation; never revert or change tokens.
        k=self.api.readonly.k;a=self.api.readonly.a
        k.GetCurrentThread.argtypes=[];k.GetCurrentThread.restype=PTR
        a.OpenThreadToken.argtypes=[PTR,C.c_uint32,C.c_int32,C.POINTER(PTR)];a.OpenThreadToken.restype=C.c_int32
        token=PTR();row=dict(output=token,owned=False,close_attempted=False,closed=False);self.query_tokens.append(row)
        ok=a.OpenThreadToken(k.GetCurrentThread(),8,True,C.byref(token))
        if ok:
            if token.value in (None,PTR(-1).value):
                self.failed=True
                if self not in _unknown:_unknown.append(self)
                need(False)
            row['owned']=True
            try:need(False)
            finally:self._close_query(row)
        if token.value:
            self.failed=True
            if self not in _unknown:_unknown.append(self)
            need(False)
        need(C.get_last_error()==1008)
        return self.read_primary((1,))[1]

    def _close_query(self,row):
        need(row in self.query_tokens and row['owned'] and not row['close_attempted'])
        row['close_attempted']=True
        try:self.api.close(row['output'].value);row['closed']=True
        except BaseException:
            self.failed=True
            if self not in _unknown:_unknown.append(self)
            raise

    def read_primary(self,kinds):
        self._time();token=PTR()
        row=dict(output=token,owned=False,close_attempted=False,closed=False);self.query_tokens.append(row)
        ok=self.api.opentoken(self.api.process(),8,C.byref(token))
        if not ok and token.value or ok and token.value in (None,PTR(-1).value):
            self.failed=True
            if self not in _unknown:_unknown.append(self)
        self.api.need(ok);need(token.value not in (None,PTR(-1).value));row['owned']=True
        try:
            values={}
            for kind in kinds:
                self._time();used=C.c_uint32();buf=C.create_string_buffer(65536)
                self.api.need(self.api.tokeninfo(token,kind,buf,len(buf),C.byref(used)))
                values[kind]=_dacl_bytes(buf,used.value) if kind==6 else _parse(buf,used.value,kind)
            return values
        finally:self._close_query(row)

    def _anchor(self):
        self._time();need(self._id(self.anchor)==self.anchor_id and self.api.descriptor(self.anchor)==self.anchor_sd
                         and self.api.final_path(self.anchor)==self.anchor_path and self._sid()==self.sid)

    def _open(self,parent,name,*,directory=False,create=False,origin=None,expected_refusal=None):
        self._anchor()
        need(directory or name in NAMES)
        require_nt_create_ready(self.api.readonly)
        text=C.create_string_buffer(name.encode('utf-16-le')+b'\0\0')
        u=UnicodeString(len(name.encode('utf-16-le')),len(name.encode('utf-16-le'))+2,C.cast(text,PTR))
        sd=C.create_string_buffer(private_file_descriptor(self.sid)) if create else None
        attrs=ObjectAttributes(C.sizeof(ObjectAttributes),parent,C.pointer(u),0x40,C.cast(sd,PTR) if sd else None,None)
        h=PTR();io=IOStatus();storage=(h,io,attrs,u,text,sd)
        self.buffers.append(storage)  # Original outputs remain alive before the syscall.
        status=nt_status(self.api.ntcreate(C.byref(h),0x13019f,C.byref(attrs),C.byref(io),None,
            0x10 if directory else 0x80,1,2 if create else 1,
            0x20|0x200000|(1 if directory else 0x40),None,0))
        if status==0x103:
            retain_pending_nt_create(self.api.readonly,h,io,attrs,u,text,sd);self.failed=True;need(False)
        if expected_refusal is not None and status==expected_refusal and not h.value:return None
        owned=completed_nt_handle(status,h.value)
        node=None
        if owned:
            node=Node(h.value,name,parent,directory);self.nodes.append(node)
        try:
            need(status==0 and owned and expected_refusal is None)
            need(io.Information==(2 if create else 1))
            node.created=create;node.origin=node if create else origin
            need(create or origin in self.nodes and origin.created and origin.closed)
            info=self.api.info(h.value)
            need(bool(info.attributes&DIRECTORY)==directory and not info.attributes&(REPARSE|UNSAFE_ATTRIBUTES)
                 and info.identity>0 and info.volume==self.anchor_id[0] and (directory or info.links==1))
            private_acl(self.api.security(h.value),self.user)
            node.identity=(info.volume,info.identity);node.descriptor=self.api.descriptor(h.value)
            node.path=self.api.final_path(h.value);node.size=info.size
            need(node.path==self.api.final_path(parent).rstrip('\\')+'\\'+name)
            need(node.descriptor[0]==self.user and node.descriptor[1]&~1 in (0x1004,0x9004)
                 and node.descriptor[2]==private_file_descriptor(self.sid)[20+len(self.sid):])
            if not create:need(node.identity==origin.identity and node.descriptor==origin.descriptor and node.path==origin.path)
            return node
        except BaseException:self.failed=True;raise

    def file(self,name):
        need(name in NAMES and name not in self.entries);self.verify_root()
        node=self._open(self.root.handle,name,create=True);self.entries[name]=node;return node

    def verify(self,node):
        self._anchor();need(node in self.nodes and not node.close_attempted and node.identity is not None)
        info=self.api.info(node.handle)
        need((info.volume,info.identity)==node.identity and bool(info.attributes&DIRECTORY)==node.directory
             and not info.attributes&(REPARSE|UNSAFE_ATTRIBUTES) and (node.directory or info.links==1 and info.size==node.size))
        need(self.api.descriptor(node.handle)==node.descriptor and self.api.final_path(node.handle)==node.path)
        private_acl(self.api.security(node.handle),self.user)

    def namespace(self):
        self.verify(self.root);result={}
        for index in range(4):
            self._time();raw=C.create_string_buffer(65536)
            if not self.query(self.root.handle,11 if index==0 else 10,raw,len(raw)):
                need(C.get_last_error()==18);return result
            for name,attrs,identity in directory_batch(raw.raw):
                need(name not in result and not attrs&(DIRECTORY|REPARSE|UNSAFE_ATTRIBUTES) and len(result)<len(NAMES))
                result[name]=identity
        need(False)

    def verify_root(self):
        actual=self.namespace();need(actual=={n:r.identity[1] for n,r in self.entries.items() if not r.closed})

    def read(self,node,offset,count):
        self.verify(node);need(0<=offset<=65536 and 0<count<=65536)
        self.api.need(self.seek(node.handle,offset,None,0));raw=self.api.read(node.handle,count)
        self.verify(node);return raw

    def write(self,node,offset,raw):
        self.verify(node);need(type(raw) is bytes and 0<len(raw)<=16384 and 0<=offset and offset+len(raw)<=65536)
        self.api.need(self.seek(node.handle,offset,None,0));buffer=C.create_string_buffer(raw);count=C.c_uint32()
        self.buffers.append((buffer,count))
        try:
            self.api.need(self.api.writefile(node.handle,buffer,len(raw),C.byref(count),None))
            need(count.value==len(raw));node.size=max(node.size,offset+len(raw));self.verify(node)
            return count.value
        except BaseException:self.failed=True;raise

    def flush(self,node):
        self.verify(node)
        try:self.api.flush(node.handle);self.verify(node)
        except BaseException:self.failed=True;raise

    def close_node(self,node):
        need(not node.close_attempted);node.close_attempted=True
        try:self.api.close(node.handle);node.closed=True
        except BaseException:self.failed=True;raise

    def reopen(self,node):
        self.verify(node);self.close_node(node)
        result=self._open(self.root.handle,node.name,origin=node.origin)
        self.entries[node.name]=result;self.verify_root();return result

    def exclusive_refused(self,node):
        self.verify(node)
        # Existing writable+DELETE original HANDLE is not shareable by this
        # competing identical FILE_OPEN. Only this exact known failure passes.
        need(self._open(self.root.handle,node.name,expected_refusal=nt_status(0xc0000043)) is None)

    def cleanup(self):
        if self.closed:return 'ALREADY_CLOSED'
        if self.failed or self.api is not None and getattr(self.api.readonly,'_nt_create_pending',False):
            if self not in _unknown:_unknown.append(self)
            return 'RETAINED_UNKNOWN'
        try:
            if self.root is not None:
                self.verify_root()
                for node in reversed(tuple(self.entries.values())):
                    self.verify(node);need(node.origin in self.nodes and node.origin.created and not node.delete_attempted)
                    node.delete_attempted=True;flag=C.c_ubyte(1)
                    self.api.need(self.disposition(node.handle,4,C.byref(flag),C.sizeof(flag)))
                    self.close_node(node)
                    self.verify_root()
                self.verify_root();self.close_node(self.root)
            # No path-based remove and no re-open/retry on any uncertain close.
            while self.ancestors:
                handle=self.ancestors.pop();self.ancestor_closes.append(handle);self.api.close(handle)
            self.closed=True;return 'OWN_CHILDREN_DELETED_EMPTY_MARKER_RETAINED'
        except BaseException:
            self.failed=True
            if self not in _unknown:_unknown.append(self)
            return 'RETAINED_UNKNOWN'


class NativeSlotIO:
    journal_format=journal.FixedFormat.INSTANCE_V2
    def __init__(self,storage,node,lock):
        self.storage,self.node,self.lock=storage,node,lock
        self.root_id=storage.root_id;self.lock_id=list(lock.identity)
    def verify(self):self.storage.verify_root();self.storage.verify(self.lock);self.storage.verify(self.node)
    def identity(self):return list(self.node.identity)
    def signature(self):
        self.verify();info=FileInfo();self.storage.api.need(self.storage.api.getinfo(self.node.handle,C.byref(info)))
        return (info.Attributes,info.Creation.Low,info.Creation.High,info.Write.Low,info.Write.High,
                info.Volume,info.SizeHigh,info.SizeLow,info.Links,info.IndexHigh,info.IndexLow)
    def length(self):self.verify();return self.storage.api.info(self.node.handle).size
    def read_at(self,offset,count):return self.storage.read(self.node,offset,count)
    def write_at(self,offset,raw):return self.storage.write(self.node,offset,raw)
    def flush_file(self):self.storage.flush(self.node)
