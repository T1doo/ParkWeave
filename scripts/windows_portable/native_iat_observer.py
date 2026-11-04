"""Actual original-process namespace/IAT reads, separate from image source trust.

No guessed PEB layout, PID discovery, LoadLibrary in the target or remote write.
Policy remains unset. Memory exports prove where an import resolves; they do
not prove the mapped image's file identity (a separate required observation).
"""
import ctypes as C
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import PureWindowsPath
import re
import struct
import sys
import time
import weakref

from . import native_trial_authority as a
from .api_set_map import parse_v6,resolve_metadata
from .crt_pe import Image

P=C.c_void_p;D=C.c_uint32;B=C.c_int32;S=C.c_size_t


@dataclass(frozen=True)
class NamespaceLayout:
    nt_version: tuple
    peb_api_set_offset: int
    namespace_version: int


_REVIEWED_LAYOUT=None
# Source-reviewed TRIAL parser selection, NOT an observed runner/Windows11
# fact or a Microsoft stable-ABI guarantee. phnt 53fbbdc5... ntpebteb.h,
# SHA256 9869d45323706a6bf7cb3ed168b4ca6560aef194f1c6a4d37aaad74a356ad248.
# AMD64 offsetof is also locked by native_mapped_abi.c. No UBR is pinned:
# exact live version/architecture/schema/IAT are still read every observation.
_TRIAL_SERVER_2025_LAYOUT=NamespaceLayout((10,0,26100,3),0x68,6)
_peers=weakref.WeakKeyDictionary()


class UnsupportedNamespaceObservation(RuntimeError):
    """Known unmodelled loader form; no observation, no invented policy."""


class BasicInformation(C.Structure):
    _fields_=[('reserved',P),('peb',P),('reserved2',P*2),('pid',S),('reserved3',P)]


class ModuleInformation(C.Structure):
    _fields_=[('base',P),('size',D),('entry',P)]


class MemoryInformation(C.Structure):
    _fields_=[('base',P),('allocation',P),('allocation_protect',D),('partition',C.c_uint16),
        ('region_size',S),('state',D),('protect',D),('kind',D)]


def _bind(lib,name,result,args):
    fn=getattr(lib,name);fn.restype=result;fn.argtypes=args;return fn


def layout(lease=None):
    value=_REVIEWED_LAYOUT
    trial=value is None
    if trial:
        if a.bound_state(lease) is None:return None
        value=_TRIAL_SERVER_2025_LAYOUT
        if os.name!='nt' or C.sizeof(P)!=8:return None
        actual=sys.getwindowsversion()
        if value.nt_version!=(actual.major,actual.minor,actual.build,actual.product_type):return None
    a.need(type(value) is NamespaceLayout and type(value.peb_api_set_offset) is int
        and 0<value.peb_api_set_offset<=512 and value.peb_api_set_offset%8==0
        and value.namespace_version==6 and os.name=='nt' and C.sizeof(P)==8)
    version=sys.getwindowsversion()
    a.need(value.nt_version==(version.major,version.minor,version.build,version.product_type))
    return value


class OriginalMemory:
    def __init__(self,witness,process,check,deadline,policy):
        from .native_acceptance_issuer import _deadline
        _deadline(deadline);witness._binding()
        self.witness,self.process,self.check,self.policy=witness,process,check,policy
        self.deadline=a.budget(witness.lease,deadline);self.pages={};self.used=0
        k=witness.api.readonly.k
        self.read_process=_bind(k,'ReadProcessMemory',B,[P,P,P,S,C.POINTER(S)])
        self.query_memory=_bind(k,'VirtualQueryEx',S,[P,P,C.POINTER(MemoryInformation),S])
        self.module_information=_bind(k,'K32GetModuleInformation',B,[P,P,C.POINTER(ModuleInformation),D])
        self.mapped_name=_bind(k,'K32GetMappedFileNameW',D,[P,P,C.c_wchar_p,D])
        self.process_id=_bind(k,'GetProcessId',D,[P])
        self.nt=C.WinDLL('ntdll.dll',use_last_error=True,winmode=0x800)
        self.basic=_bind(self.nt,'NtQueryInformationProcess',C.c_int32,[P,D,P,D,C.POINTER(D)])

    def gate(self):
        a.budget(self.witness.lease,self.deadline)
        a.need(time.monotonic()<self.deadline)

    def read(self,address,size):
        self.gate();a.need(type(address) is int and type(size) is int
            and 0<address<0x800000000000 and 0<size<=4*1024*1024 and address+size<0x800000000000)
        self.used+=size;a.need(self.used<=32*1024*1024)
        data=C.create_string_buffer(size);read=S()
        a.need(self.read_process(self.process,address,data,size,C.byref(read)) and read.value==size)
        return data.raw

    def image_read(self,base,size,offset,length):
        a.need(type(offset) is int and type(length) is int and 0<=offset<=size
            and 0<length<=size-offset)
        result=[];current=offset
        while current<offset+length:
            page=current//4096*4096;key=(base,page)
            if key not in self.pages:
                info=MemoryInformation();address=base+page
                self.gate();a.need(self.query_memory(self.process,address,C.byref(info),C.sizeof(info))==C.sizeof(info)
                    and info.allocation==base and info.kind==0x1000000 and info.state==0x1000
                    and not info.protect&(0x1|0x100))
                self.pages[key]=self.read(address,min(4096,size-page))
            data=self.pages[key];start=current-page;n=min(offset+length-current,len(data)-start)
            a.need(n>0);result.append(data[start:start+n]);current+=n
        return b''.join(result)

    def namespace(self):
        self.check();self.gate();basic=BasicInformation();length=D()
        a.need(self.basic(self.process,0,C.byref(basic),C.sizeof(basic),C.byref(length))==0
            and length.value==C.sizeof(basic) and basic.peb
            and basic.pid==self.process_id(self.process))
        pointer=basic.peb+self.policy.peb_api_set_offset
        address=struct.unpack('<Q',self.read(pointer,8))[0]
        header=self.read(address,28);version,size=struct.unpack_from('<II',header)
        a.need(version==self.policy.namespace_version and 28<=size<=4*1024*1024)
        raw=self.read(address,size);mapping=parse_v6(raw)
        a.need(mapping['namespace_size']==size and raw[:28]==header and self.read(pointer,8)==struct.pack('<Q',address))
        self.check();return pointer,address,raw,mapping

    def modules(self):
        self.gate();self.witness._architecture(self.process);result=[]
        modules=(P*4096)();used=D()
        a.need(self.witness.modules(self.process,modules,C.sizeof(modules),C.byref(used),3)
            and 0<used.value<=C.sizeof(modules) and used.value%C.sizeof(P)==0)
        for base in modules[:used.value//C.sizeof(P)]:
            info=ModuleInformation()
            a.need(self.module_information(self.process,base,C.byref(info),C.sizeof(info))
                and info.base==base and 4096<=info.size<=128*1024*1024)
            name=C.create_unicode_buffer(4096);length=self.mapped_name(self.process,base,name,len(name))
            a.need(0<length<len(name) and name.value.startswith('\\Device\\')
                and all(base!=row[0] for row in result))
            result.append((base,info.size,name.value.casefold()))
        return tuple(sorted(result))

    def recheck(self):
        for (base,page),raw in self.pages.items():a.need(self.read(base+page,len(raw))==raw)
        self.check()


class RemoteImage:
    """Export reader over actual MEM_IMAGE pages, not a re-opened file."""
    def __init__(self,memory,base,size):
        self.memory,self.base,self.image_size=memory,base,size
        a.need(self.read(0,2)==b'MZ');pe=self.u(0x3c,'I')
        a.need(0<pe<65536 and self.read(pe,4)==b'PE\0\0' and self.u(pe+4,'H')==0x8664)
        count=self.u(pe+6,'H');optional=self.u(pe+20,'H');self.opt=pe+24
        a.need(0<count<=96 and optional>=240 and self.u(self.opt,'H')==0x20b
            and self.u(self.opt+56,'I')==size and self.u(self.opt+108,'I')>=14)
        self.memory_sections=[]
        for i in range(count):
            where=self.opt+optional+40*i
            length=max(self.u(where+8,'I'),self.u(where+16,'I'));address=self.u(where+12,'I')
            a.need(address+length<=size);self.memory_sections.append((address,length))

    def read(self,offset,length):return self.memory.image_read(self.base,self.image_size,offset,length)
    def u(self,offset,fmt):return struct.unpack('<'+fmt,self.read(offset,struct.calcsize('<'+fmt)))[0]
    def directory(self,index):return self.u(self.opt+112+index*8,'I'),self.u(self.opt+116+index*8,'I')
    def offset(self,rva,length=1):
        a.need(type(rva) is int and length>0 and sum(v<=rva and rva+length<=v+n for v,n in self.memory_sections)==1)
        return rva
    def text(self,rva):
        self.offset(rva);data=self.read(rva,min(1025,self.image_size-rva));end=data.find(b'\0')
        a.need(0<end<=1024 and all(32<=c<127 for c in data[:end]));self.offset(rva,end+1)
        return data[:end].decode('ascii')
    memory_target=Image.memory_target
    export_targets=Image.export_targets


def _observe(witness,process,check,deadline,images):
    policy=layout(witness.lease);a.need(policy is not None)
    from .native_loader_images import inspect
    images=inspect(images,witness.lease,witness,deadline)
    memory=OriginalMemory(witness,process,check,deadline,policy)
    check();first=memory.modules();pointer,address,raw,mapping=memory.namespace()
    by_name={};by_native={}
    for base,size,path in first:
        name=PureWindowsPath(path).name.lower()
        a.need(name not in by_name);by_name[name]=(base,size,path);by_native[path.casefold()]=(base,size,path)
    remote={};exports={};results=[];unresolved=[]
    def resolve(dll,symbol,importer,seen=()):
        memory.gate();a.need(len(seen)<32 and (dll,symbol,importer) not in seen)
        seen=(*seen,(dll,symbol,importer))
        if dll.startswith(('api-','ext-')):
            selected=resolve_metadata(mapping,dll,importer)
            if selected['status']!='STATIC_MAPPED_NOT_NATIVE_VERIFIED' or not selected['host']:
                raise UnsupportedNamespaceObservation('API_SET_FORM_NOT_COLLECTED')
            dll=selected['host']
        a.need(dll in by_name);base,size,path=by_name[dll]
        if base not in remote:remote[base]=RemoteImage(memory,base,size)
        if base not in exports:exports[base]=remote[base].export_targets()
        a.need(symbol in exports[base]);rva,forwarder=exports[base][symbol]
        if forwarder is None:return base+rva,(dll,symbol,rva)
        module,separator,next_symbol=forwarder.partition('.')
        a.need(separator and re.fullmatch('[A-Za-z0-9_-]+',module) and next_symbol)
        return resolve(module.lower()+'.dll',next_symbol,dll,seen)
    for name,(native_path,image) in images.items():
        original=by_native.get(native_path.casefold())
        if original is None:continue
        base,size,path=original;a.need(image.image_size==size)
        basename=PureWindowsPath(path).name.lower()
        for dll,symbol,slot,delayed,initial in image.import_slots():
            value=struct.unpack('<Q',memory.image_read(base,size,slot,8))[0]
            if delayed and base<=value<base+size:
                unresolved.append((name,dll,symbol,slot));continue
            actual,terminal=resolve(dll,symbol,basename)
            a.need(value==actual);results.append((name,dll,symbol,slot,terminal))
    a.need(results)
    if unresolved:raise UnsupportedNamespaceObservation('UNRESOLVED_DELAY_IMPORT_NOT_COLLECTED')
    a.need(memory.modules()==first and memory.read(pointer,8)==struct.pack('<Q',address)
        and memory.read(address,len(raw))==raw)
    memory.recheck();witness._binding()
    actual=sys.getwindowsversion()
    return ((actual.major,actual.minor,actual.build,actual.product_type),tuple(first),sha256(raw).hexdigest(),tuple(results))


def capture_peer(lease,witness,peer,deadline,images):
    if layout(lease) is None:return
    from .native_database_endpoint import _BackendWitness
    a.need(a.bound_state(lease) is not None and type(peer) is _BackendWitness
        and peer.endpoint.crt_witness is witness and witness.lease is lease)
    witness.require_group_binding(peer.endpoint.adapter,peer.endpoint.token)
    peer._verify_identity()
    _peers.pop(lease,None)
    try:evidence=_observe(witness,peer.handle,peer._verify_identity,deadline,images)
    except UnsupportedNamespaceObservation:return
    _peers[lease]=(peer,peer.endpoint,peer.birth,evidence)


def capture_groups(lease,witness,groups,deadline,images):
    if layout(lease) is None or lease not in _peers:return
    from .windows_process_handles import WindowsJobProcess
    a.need(lease in _peers and len(groups)==3 and a.bound_state(lease) is not None)
    a.need(len({id(token) for _,token,_ in groups})==3 and sorted(
        (adapter._group(token).command.relative_executable,adapter._group(token).command.stdio_contract)
        for adapter,token,_ in groups)==[('runtime/postgresql/bin/postgres.exe','NONE'),
            ('runtime/python/python.exe','NONE'),('runtime/python/python.exe','WORKER_READINESS_V1')])
    peer,endpoint,birth,peer_evidence=_peers[lease]
    a.need(endpoint.crt_witness is witness and endpoint.adapter._group(endpoint.token).resources['job']==endpoint.job
        and any(adapter is endpoint.adapter and token is endpoint.token for adapter,token,_ in groups))
    observations=[]
    for adapter,token,identity in groups:
        group=witness.require_group_binding(adapter,token)
        a.need(type(adapter.backend) is WindowsJobProcess and group.operation_lock.acquire(blocking=False))
        try:
            def check():
                a.need(adapter._group(token) is group and adapter._live_identity(group)==identity)
                inside=B();a.need(witness.inside(group.resources['process'],group.resources['job'],C.byref(inside)) and inside.value)
                group.executable.verify()
            check()
            try:evidence=_observe(witness,group.resources['process'],check,deadline,images)
            except UnsupportedNamespaceObservation:return
            observations.append((adapter,token,identity,evidence))
        finally:group.operation_lock.release()
    from .native_trial_facts import _seal
    return _seal(lease,('api_set_resolution',),witness,(policy_signature(lease),peer,endpoint,birth,peer_evidence,tuple(observations)))


def policy_signature(lease):
    value=layout(lease);a.need(value is not None);return (value.nt_version,value.peb_api_set_offset,value.namespace_version)
