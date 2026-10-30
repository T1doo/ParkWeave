"""SHA256 catalog verification of an ORIGINAL debug-event member HANDLE.

Reads the existing OS catalog database only. No Add/RemoveCatalog, certificate
store install, network retrieval, signer/root expansion or native work at import.
HCATINFO is not a CTL_CONTEXT. A held catalog byte copy supplies pcCatalogContext,
so the WinTrust member decision cannot substitute another catalog path's bytes.
"""
import ctypes as C
from hashlib import sha256
import re
import time
import uuid

from parkweave.windows_files import component,DIRECTORY,REPARSE,UNSAFE_ATTRIBUTES
from .native_system_crt import TrustData,CRTRefused,os_security,bind
from .windows_process_handles import native_file_path
from pathlib import PureWindowsPath

P=C.c_void_p;D=C.c_uint32;B=C.c_int32
_retained=[]


class CatalogInfo(C.Structure):
    _fields_=[('size',D),('path',C.c_uint16*260)]


class CatalogTrust(C.Structure):
    _fields_=[('size',D),('version',D),('catalog_path',C.c_wchar_p),('tag',C.c_wchar_p),
        ('member_path',C.c_wchar_p),('member',P),('hash',P),('hash_size',D),('ctl',P),('admin',P)]


def need(ok):
    if not ok:raise CRTRefused()


def catalog_path(info):
    need(info.size==C.sizeof(CatalogInfo))
    units=list(info.path);need(0 in units)
    end=units.index(0);need(0<end<260)
    return bytes(info.path)[:end*2].decode('utf-16-le',errors='strict')


class CatalogMemberVerifier:
    def __init__(self,trace,member,path):
        from .native_mapped_sources import NativeMappedSources
        need(type(trace) is NativeMappedSources)
        trace._guard(work=True)
        record=trace.pending
        need(record is not None and record.get('file') is not None
            and any(row is record['file'] for row in trace.files) and record['file']['handle']==member
            and record['file']['owned'] and not record['file']['attempted'])
        native=native_file_path(trace.api,member).casefold()
        name=PureWindowsPath(native).name
        need(native.rpartition('\\')[0]==trace.system_path
            and path.casefold()==(trace.crt.path.rstrip('\\')+'\\'+name).casefold())
        self.trace,self.crt,self.api,self.member,self.path=trace,trace.crt,trace.api,member,path
        self.resources=[];self.nodes=[];self.unknown=False;self.closed=False;self.wvt_closed=False
        self.inflight=None
        self.deadline=min(trace.state.deadline,time.monotonic()+10)
        self.buffers=[];_retained.append(self)
        trust=self.crt.trust;crypto=self.crt.crypto
        self.acquire=bind(trust,'CryptCATAdminAcquireContext2',B,[C.POINTER(P),P,C.c_wchar_p,P,D])
        self.calculate=bind(trust,'CryptCATAdminCalcHashFromFileHandle2',B,[P,P,C.POINTER(D),P,D])
        self.enumerate=bind(trust,'CryptCATAdminEnumCatalogFromHash',P,[P,P,D,D,C.POINTER(P)])
        self.info=bind(trust,'CryptCATCatalogInfoFromContext',B,[P,C.POINTER(CatalogInfo),D])
        self.release_catalog=bind(trust,'CryptCATAdminReleaseCatalogContext',B,[P,P,D])
        self.release_admin=bind(trust,'CryptCATAdminReleaseContext',B,[P,D])
        self.create_ctl=bind(crypto,'CertCreateCTLContext',P,[D,P,D])
        self.free_ctl=bind(crypto,'CertFreeCTLContext',B,[P])

    def guard(self):
        self.trace._guard(work=True);need(not self.closed and not self.unknown and time.monotonic()<self.deadline)

    def call(self,function,*args):
        self.inflight=(function,args)  # Keep all original output storage on an uncertain call.
        try:result=function(*args)
        except BaseException:
            self.unknown=True;raise
        self.inflight=None
        return result

    def inspect(self,handle,directory):
        self.guard();info=self.api.info(handle)
        need(bool(info.attributes&DIRECTORY)==directory and not info.attributes&(REPARSE|UNSAFE_ATTRIBUTES)
            and info.identity>0 and (directory or 0<info.size<=16*1024*1024))
        os_security(self.api.security(handle),ancestor=directory)
        return info,self.api.descriptor(handle),self.api.final_path(handle),self.trace.identifier(handle)

    def pin_catalog(self,path):
        prefix=self.crt.path.rstrip('\\')+'\\'
        need(path[:len(prefix)].casefold()==prefix.casefold())
        parts=path[len(prefix):].split('\\')
        need(len(parts)==3 and parts[0].casefold()=='catroot'
            and parts[1].casefold()=='{f750e6c3-38ee-11d1-85e5-00c04fc295ee}'
            and parts[2].lower().endswith('.cat'))
        parent=self.crt.directory
        for index,name in enumerate(parts):
            self.guard();component(name)
            directory=index<2
            handle=self.api.open_relative(parent,name,not directory)
            row=dict(kind='FILE',handle=handle,owned=True,attempted=False,closed=False);self.nodes.append(row)
            row['before']=self.inspect(handle,directory);row['directory']=directory
            parent=handle
        before=self.nodes[-1]['before'];size=before[0].size
        need(self.trace.seek(parent,0,None,0));chunks=[];remaining=size
        while remaining:
            self.guard();part=self.api.read(parent,min(1024*1024,remaining))
            need(0<len(part)<=remaining);chunks.append(part);remaining-=len(part)
        need(self.api.read(parent,1)==b'');raw=b''.join(chunks)
        for row in self.nodes:need(self.inspect(row['handle'],row['directory'])==row['before'])
        return raw,sha256(raw).hexdigest(),before[3]

    def verify(self):
        self.guard()
        # Fixed SHA256, no SHA1/default-algorithm fallback or resize/retry.
        subsystem=C.create_string_buffer(uuid.UUID('f750e6c3-38ee-11d1-85e5-00c04fc295ee').bytes_le)
        admin=P();admin_row=dict(kind='ADMIN',output=admin,owned=False,attempted=False,closed=False)
        self.resources.append(admin_row);self.buffers.append(subsystem)
        ok=self.call(self.acquire,C.byref(admin),subsystem,'SHA256',None,0)
        admin_row['owned']=bool(ok and admin.value not in (None,0,P(-1).value))
        if not ok and admin.value:self.unknown=True
        need(ok and admin_row['owned'])
        digest=(C.c_ubyte*32)();size=D(32);self.buffers.extend((digest,size))
        need(self.trace.seek(self.member,0,None,0))
        self.guard();need(self.call(self.calculate,admin.value,self.member,C.byref(size),digest,0) and size.value==32)
        # Explicitly one candidate, not a previous-context iteration. The one
        # returned HCATINFO remains ours and is released once after WVT CLOSE.
        catalog_row=dict(kind='CATALOG',handle=None,owned=False,attempted=False,closed=False)
        self.resources.append(catalog_row)
        self.guard();catalog=self.call(self.enumerate,admin.value,digest,32,0,None)
        catalog_row['handle']=catalog;catalog_row['owned']=catalog not in (None,0,P(-1).value);need(catalog_row['owned'])
        info=CatalogInfo();info.size=C.sizeof(info);self.buffers.append(info)
        self.guard();need(self.call(self.info,catalog,C.byref(info),0));path=catalog_path(info)
        raw,full_hash,identity=self.pin_catalog(path)
        encoded=C.create_string_buffer(raw);self.buffers.append(encoded)
        ctl_row=dict(kind='CTL',handle=None,owned=False,attempted=False,closed=False);self.resources.append(ctl_row)
        self.guard();ctl=self.call(self.create_ctl,0x10001,encoded,len(raw))
        ctl_row['handle']=ctl;ctl_row['owned']=ctl not in (None,0,P(-1).value);need(ctl_row['owned'])
        catalog_data=CatalogTrust(C.sizeof(CatalogTrust),0,path,bytes(digest).hex().upper(),self.path,
            self.member,C.cast(digest,P),32,ctl,admin.value)
        data=TrustData();data.size=C.sizeof(data);data.ui=2;data.revocation=1;data.choice=2
        data.catalog=C.cast(C.pointer(catalog_data),P);data.action=1;data.flags=0x80|0x1000|0x2000
        self.buffers.extend((catalog_data,data))
        self.guard()
        try:roots=self.crt._verify_trust(data,(self,))
        finally:
            # _verify_trust marks any WVT-close uncertainty before raising.
            self.wvt_closed=not bool(self.crt.unknown)
        self.guard()
        for row in self.nodes:need(self.inspect(row['handle'],row['directory'])==row['before'])
        return ('SHA256_CATALOG_MEMBER',bytes(digest).hex(),full_hash,identity,roots)

    def close(self):
        need(not self.closed and not self.unknown and not self.crt.unknown
            and not getattr(self.api.readonly,'_nt_create_pending',False)
            and not getattr(self.api.readonly,'_query_unknown',False))
        end=min(self.trace.state.cleanup_end,time.monotonic()+5)
        for row in list(reversed(self.resources))+list(reversed(self.nodes)):
            self.trace._guard();need(time.monotonic()<end)
            if not row['owned']:continue
            need(not row['attempted']);row['attempted']=True
            try:
                handle=row['output'].value if 'output' in row else row['handle']
                if row['kind']=='CTL':need(self.call(self.free_ctl,handle))
                elif row['kind']=='CATALOG':need(self.call(self.release_catalog,self.resources[0]['output'].value,handle,0))
                elif row['kind']=='ADMIN':need(self.call(self.release_admin,handle,0))
                else:self.api.close(handle)
                row['closed']=True
            except BaseException:
                self.unknown=True;raise
        self.closed=True
        # All native borrowers are known released. Keep small original close
        # records, not a copy of the same multi-MiB catalog for every DLL.
        self.buffers.clear()
        if self in _retained:_retained.remove(self)


def verify_member(trace,member,path):
    verifier=object.__new__(CatalogMemberVerifier)
    if not hasattr(trace,'catalog_verifiers'):trace.catalog_verifiers=[]
    trace.catalog_verifiers.append(verifier)
    primary=cleanup=None;result=None
    try:
        CatalogMemberVerifier.__init__(verifier,trace,member,path)
        result=verifier.verify()
    except BaseException as error:primary=error
    finally:
        try:verifier.close()
        except BaseException as error:cleanup=error
    if cleanup is not None:
        trace.failed=True
        from .native_trial_authority import fail_resource
        fail_resource(trace.lease)
    if primary is not None or cleanup is not None:raise CRTRefused() from None
    return result
