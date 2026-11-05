"""Existing x64 System32 CRT witness. Read-only; never installs or admits a loader.

System files are a separate, explicit OS trust domain, not OS_DLLS entries.
Offline Authenticode failures (including missing revocation cache) fail closed.
"""
import ctypes as C
from hashlib import sha256
import math
import json
import os
import time
import threading
import weakref

from parkweave.windows_files import root_parts,DIRECTORY,REPARSE,UNSAFE_ATTRIBUTES
from .fixed_directories import FixedDirectoryLease
from .fixed_windows_journal import NativeFixedLeaseAPI
from .native_runtime_staging import NativeRuntimeInstallation
from .crt_pe import CRT_DLLS,compatible
from .authenticode_signature import (SignatureVerification,CRTRefused,SignatureRejected,CRTTrustFailure,ROOT_SHA256,
    TRUST_PHASES,TRUST_ACTIVITIES,TRUST_CLOSE,FileTrust,TrustData,TrustChoice,Signer,ProviderCert,CertContext,bind,need)

HELP='https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist?view=msvc-170'
TRUSTED=frozenset(('S-1-5-18','S-1-5-32-544',
 'S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464'))
WRITE=0x2|0x4|0x10|0x40|0x100|0x10000|0x40000|0x80000|0x1000000|0x40000000|0x10000000
_issued=weakref.WeakKeyDictionary();_unknown=[]
P=C.c_void_p;D=C.c_uint32;B=C.c_int32


def os_security(security,*,ancestor=False):
    need(security.owner in TRUSTED and security.control&4 and security.aces)
    for ace in security.aces:
        need(ace.kind in (0,1) and not ace.flags&~0x1f)
        # INHERIT_ONLY does not grant access to this existing object. Ancestor
        # create-child rights do not authorize changing the held existing path.
        mask=WRITE&~(0x2|0x4) if ancestor else WRITE
        need(ace.kind!=0 or ace.flags&8 or ace.sid in TRUSTED or not ace.mask&mask)


class NativeSystemCRT(SignatureVerification):
    native_acceptance=False

    def __init__(self,lease,installation,runtime,deadline):
        self.handles=[];self.unknown=[];self.failed=self.closed=False;self.rows={};self.directories=[]
        self.lock=threading.Lock()
        try:self._initialize(lease,installation,runtime,deadline)
        except BaseException:
            self.failed=True
            raise CRTRefused() from None

    def _initialize(self,lease,installation,runtime,deadline):
        need(os.name=='nt' and C.sizeof(P)==8 and type(lease) is FixedDirectoryLease
             and type(lease.fs.api) is NativeFixedLeaseAPI and type(installation) is NativeRuntimeInstallation)
        self.lease,self.installation,self.runtime=lease,installation,dict(runtime)
        self.api=lease.fs.api;self.deadline=deadline
        self._time();requirements=installation.system_crt_requirements(lease,runtime,self.deadline)
        self.requirements=requirements
        k=self.api.readonly.k
        self.system=bind(k,'GetSystemDirectoryW',D,[C.c_wchar_p,D])
        self.arch=bind(k,'IsWow64Process2',B,[P,C.POINTER(C.c_uint16),C.POINTER(C.c_uint16)])
        self.inside=bind(k,'IsProcessInJob',B,[P,P,C.POINTER(B)])
        self.modules=bind(k,'K32EnumProcessModulesEx',B,[P,P,D,C.POINTER(D),D])
        self.module_path=bind(k,'K32GetModuleFileNameExW',D,[P,P,C.c_wchar_p,D])
        self.seek=bind(k,'SetFilePointerEx',B,[P,C.c_int64,P,D])
        self._architecture(self.api.process())
        text=C.create_unicode_buffer(4096);n=self.system(text,len(text));need(0<n<len(text))
        drive,parts=root_parts(text.value);need(parts[-1].casefold()=='system32')
        self.path=text.value.rstrip('\\');parent=self._hold(self.api.open_drive(drive))
        need(self.api.drive_type(self.api.final_path(parent))==3)
        self._directory(parent)
        for component in parts:
            parent=self._hold(self.api.open_relative(parent,component,False));self._directory(parent)
        self.directory=parent;self.directory_id=self._identity(parent,True)
        self.trust=C.WinDLL('wintrust.dll',use_last_error=True,winmode=0x800)
        self.crypto=C.WinDLL('crypt32.dll',use_last_error=True,winmode=0x800)
        self.wvt=bind(self.trust,'WinVerifyTrust',C.c_int32,[P,P,C.POINTER(TrustData)])
        self.provider=bind(self.trust,'WTHelperProvDataFromStateData',P,[P])
        self.signer=bind(self.trust,'WTHelperGetProvSignerFromChain',C.POINTER(Signer),[P,D,B,D])
        self.cert=bind(self.trust,'WTHelperGetProvCertFromChain',C.POINTER(ProviderCert),[C.POINTER(Signer),D])
        self.cert_name=bind(self.crypto,'CertGetNameStringW',D,[C.POINTER(CertContext),D,D,P,C.c_wchar_p,D])
        for name in sorted(CRT_DLLS):
            handle=self._hold(self.api.open_relative(parent,name,True))
            before=self._identity(handle,False);raw=self._read(handle,before[0].size)
            version=compatible(raw,requirements['symbols'][name])
            certificates=self._signature(handle,self.path+'\\'+name,image_name=name)
            need(self._identity(handle,False)==before)
            self.rows[name]=(handle,before,sha256(raw).hexdigest(),version,certificates)
        self._verify_files()
        _issued[self]=(lease,installation,self.api,tuple(sorted(runtime.items())),self.path,self.directory,self.directory_id,
                       tuple(sorted(self.rows.items())),tuple(self.handles),tuple(self.directories),self.lock,self._requirements_bytes())

    def __reduce__(self):raise TypeError('SYSTEM_CRT_WITNESS_NOT_TRANSFERABLE')
    def __copy__(self):raise TypeError('SYSTEM_CRT_WITNESS_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo):raise TypeError('SYSTEM_CRT_WITNESS_NOT_TRANSFERABLE')

    def _time(self):
        now=time.monotonic()
        need(not self.failed and not self.closed and type(self.deadline) in (int,float)
             and math.isfinite(self.deadline) and now<self.deadline<=now+30)
        from .native_trial_authority import budget
        self.deadline=budget(self.lease,self.deadline)

    def _hold(self,h):self.handles.append(h);return h

    def _architecture(self,process):
        machine,native=C.c_uint16(),C.c_uint16()
        need(self.arch(process,C.byref(machine),C.byref(native)) and machine.value==0 and native.value==0x8664)

    def _identity(self,h,directory,*,ancestor=False):
        self._time();info=self.api.info(h)
        need(not info.attributes&(REPARSE|UNSAFE_ATTRIBUTES) and bool(info.attributes&DIRECTORY)==directory
             and info.identity>0 and (directory or info.links>=1 and 0<info.size<=128*1024*1024))
        self._time();os_security(self.api.security(h),ancestor=ancestor)
        self._time();descriptor=self.api.descriptor(h)
        self._time();path=self.api.final_path(h);self._time()
        return info,descriptor,path

    def _directory(self,h):
        value=self._identity(h,True,ancestor=True);self._time();need(self.api.filesystem(h)=='NTFS');self._time()
        self.directories.append((h,value))

    def _read(self,h,size):
        self._time();self.api.need(self.seek(h,0,None,0));chunks=[];remaining=size
        while remaining:
            self._time();raw=self.api.read(h,min(1024*1024,remaining));need(0<len(raw)<=remaining)
            chunks.append(raw);remaining-=len(raw)
        self._time();need(self.api.read(h,1)==b'');self._time();return b''.join(chunks)

    def _signature_root(self):return ROOT_SHA256

    def _signature_budget(self,delegation,deadline):
        if delegation is None:
            need(deadline is None);self._time();return None
        from .native_mapped_sources import signature_budget
        return signature_budget(delegation,self,deadline)

    def _signature_cleanup_budget(self,delegation):
        if delegation is None:
            from .native_trial_authority import budget
            return budget(self.lease,cleanup=True)
        from .native_mapped_sources import signature_budget
        return signature_budget(delegation,self,cleanup=True)

    def _retain_trust_unknown(self):
        if self not in _unknown:_unknown.append(self)

    def _verify_files(self):
        self._time();need(self._identity(self.directory,True)==self.directory_id)
        for h,before in self.directories:need(self._identity(h,True,ancestor=True)==before)
        for name,(h,before,digest,version,certificates) in self.rows.items():
            need(self._identity(h,False)==before and
                 before[2].casefold()==(self.directory_id[2].rstrip('\\')+'\\'+name).casefold())
            need(sha256(self._read(h,before[0].size)).hexdigest()==digest)

    def _binding(self):
        binding=_issued.get(self);need(binding is not None)
        need(not self.failed and not self.closed and not self.unknown and binding==(
            self.lease,self.installation,self.api,tuple(sorted(self.runtime.items())),self.path,self.directory,self.directory_id,
            tuple(sorted(self.rows.items())),tuple(self.handles),tuple(self.directories),self.lock,self._requirements_bytes()))
        self.installation._issued_binding(self.lease,self.runtime)
        self.lease._verify()

    def _requirements_bytes(self):
        return json.dumps(self.requirements,sort_keys=True,separators=(',',':')).encode('ascii')

    def _scope(self,lease):
        binding=_issued.get(self)
        need(binding is not None and binding[0] is lease and self.lease is lease)

    def require_group_binding(self,adapter,token):
        from .processes import PrivateProcessAdapter
        need(type(adapter) is PrivateProcessAdapter)
        self._scope(adapter.lease)  # Before any native observation of either installation.
        group=adapter._group(token)
        need(group.executable.lease is self.lease)
        command=group.command
        rows=[row for row in self.installation.files if row[0]==command.relative_executable]
        need(len(rows)==1 and command.size==rows[0][1] and command.sha256==rows[0][2])
        self._binding()
        return group

    def _loaded(self,process):
        self._time();self._architecture(process)
        modules=(P*4096)();count=D()
        self._time()
        need(self.modules(process,modules,C.sizeof(modules),C.byref(count),3)
             and 0<count.value<=C.sizeof(modules) and count.value%C.sizeof(P)==0)
        result={};observed=[]
        for module in modules[:count.value//C.sizeof(P)]:
            self._time();text=C.create_unicode_buffer(4096);n=self.module_path(process,module,text,len(text));self._time()
            need(0<n<len(text));path=text.value
            need(module and all(module!=prior[0] for prior in observed));observed.append((module,path.casefold()))
            name=path.rsplit('\\',1)[-1].lower()
            if name in CRT_DLLS:
                need(name not in result and path.casefold()==(self.path+'\\'+name).casefold())
                result[name]=path.casefold()
        self._time();return dict(crt=result,modules=tuple(sorted(observed)))

    def _observe(self,process,check,required,deadline,*,wait_for_modules=False):
        self._binding();need(self.lock.acquire(blocking=False))
        try:return self._observe_locked(process,check,required,deadline,wait_for_modules=wait_for_modules)
        finally:self.lock.release()

    def _observe_locked(self,process,check,required,deadline,*,wait_for_modules=False):
        self._binding();now=time.monotonic()
        need(type(deadline) in (int,float) and math.isfinite(deadline) and now<deadline<=now+30)
        self.deadline=deadline
        try:
            check();self._verify_files();first=self._loaded(process)
            required=set(required)
            if wait_for_modules:
                while True:
                    self._time()
                    time.sleep(min(0.02,max(0,self.deadline-time.monotonic())))
                    self._time();check()
                    second=self._loaded(process)
                    if second==first and required.issubset(first['crt']):break
                    # Startup may add modules, but an observed mapping must
                    # not disappear or change its address/path binding.
                    need(set(first['modules']).issubset(second['modules']))
                    first=second
            else:
                need(required.issubset(first['crt']));check()
                need(self._loaded(process)==first)
            self._verify_files();check();self._binding()
        except BaseException:
            self.failed=True;raise CRTRefused() from None
        return dict(scope='ORIGINAL_PROCESS_SYSTEM_CRT_SNAPSHOT',native_acceptance=False,
                    minimum_toolset_compatibility='NOT_ESTABLISHED',activation_allowed=False,
                    files={name:dict(sha256=row[2],version=row[3],signer_chain_sha256=row[4])
                           for name,row in self.rows.items()})

    def observe_group(self,adapter,token,deadline,*,wait_for_modules=False):
        from .processes import PrivateProcessAdapter
        from .windows_process_handles import WindowsJobProcess
        need(type(adapter) is PrivateProcessAdapter and isinstance(adapter.backend,WindowsJobProcess))
        group=self.require_group_binding(adapter,token);need(group.operation_lock.acquire(blocking=False))
        try:
            r=group.resources;identity=adapter._live_identity(group)
            process,job=r['process'],r['job'];image=group.executable.native_path
            need(group.command.relative_executable in self.requirements['processes'])
            required=self.requirements['processes'][group.command.relative_executable]
            def check():
                need(adapter._group(token) is group and r['process']==process and r['job']==job and r['bound'] is True
                     and adapter._live_identity(group)==identity)
                inside=B();need(self.inside(process,job,C.byref(inside)) and inside.value==1)
                text=C.create_unicode_buffer(4096);n=D(len(text))
                need(adapter.backend.image(process,1,text,C.byref(n)) and 0<n.value<len(text)
                     and text.value.casefold()==image.casefold());group.executable.verify()
            return self._observe(process,check,required,deadline,wait_for_modules=wait_for_modules)
        finally:group.operation_lock.release()

    def observe_peer(self,peer,deadline):
        from .native_database_endpoint import _BackendWitness
        need(type(peer) is _BackendWitness and peer.endpoint.crt_witness is self)
        self.require_group_binding(peer.endpoint.adapter,peer.endpoint.token)
        return self._observe(peer.handle,peer._verify_identity,
            self.requirements['processes']['runtime/postgresql/bin/postgres.exe'],deadline)

    def close(self):
        readonly=getattr(getattr(self,'api',None),'readonly',None)
        if self.unknown or getattr(readonly,'_query_unknown',False) or getattr(readonly,'_nt_create_pending',False):
            if self not in _unknown:_unknown.append(self)
            raise CRTRefused()  # Unknown native state may still borrow these original handles.
        need(self.lock.acquire(blocking=False))
        try:self._close_owned()
        finally:self.lock.release()

    def _close_owned(self):
        errors=[]
        while self.handles:
            h=self.handles.pop()
            try:self.api.close(h)
            except BaseException as error:self.unknown.append(('CLOSE_UNKNOWN',h));errors.append(error)
        self.closed=True
        if self.unknown:
            if self not in _unknown:_unknown.append(self)
            raise CRTRefused()
