"""Owned debug-event image-file observations; no native work at import.

The source-bound trial alone can delegate read/observe work to one dedicated
thread. It never takes lease/group locks, changes privileges/DACLs, discovers
PIDs, writes target memory or detaches to continue a failed trial. Attach is a
real per-process debug operation, not side-effect-free sampling.
"""
import ctypes as C
from dataclasses import dataclass
from hashlib import sha256
import os
from pathlib import PureWindowsPath
import queue
import struct
import threading
import time
import weakref
from types import MappingProxyType

from . import native_trial_authority as a
from .native_system_crt import os_security
from .windows_process_handles import WindowsJobProcess,native_file_path

P=C.c_void_p;D=C.c_uint32;B=C.c_int32;S=C.c_size_t
OPERATION='OWN_JOB_IMAGE_DEBUG_OBSERVATIONS'
_sessions=weakref.WeakKeyDictionary();_retained=[];_delegations=weakref.WeakKeyDictionary()
_members=weakref.WeakKeyDictionary()
need=a.need


class ExceptionRecord(C.Structure):
    _fields_=[('code',D),('flags',D),('record',P),('address',P),('count',D),('information',S*15)]
class ExceptionInfo(C.Structure):_fields_=[('record',ExceptionRecord),('first_chance',D)]
class ProcessInfo(C.Structure):
    _fields_=[('file',P),('process',P),('thread',P),('base',P),('debug_offset',D),('debug_size',D),
        ('tls',P),('start',P),('name',P),('unicode',C.c_uint16)]
class LoadInfo(C.Structure):
    _fields_=[('file',P),('base',P),('debug_offset',D),('debug_size',D),('name',P),('unicode',C.c_uint16)]
class ThreadInfo(C.Structure):_fields_=[('thread',P),('tls',P),('start',P)]
class EventData(C.Union):
    _fields_=[('exception',ExceptionInfo),('process',ProcessInfo),('load',LoadInfo),('thread',ThreadInfo),('base',P),('exit_code',D)]
class DebugEvent(C.Structure):_fields_=[('code',D),('pid',D),('tid',D),('data',EventData)]
class FileIdentifier(C.Structure):_fields_=[('volume',C.c_uint64),('identity',C.c_ubyte*16)]
class JobMembers(C.Structure):_fields_=[('assigned',D),('count',D),('pids',S*128)]


class OriginalJobMember:
    __slots__=('__weakref__',)
    def __reduce__(self):raise TypeError('original Job member cannot be transferred')


class PumpDelegation:
    __slots__=('__weakref__',)
    def __reduce__(self):raise TypeError('debug delegation cannot be serialized')
    def __copy__(self):raise TypeError('debug delegation cannot be copied')
    def __deepcopy__(self,memo):raise TypeError('debug delegation cannot be copied')


def bind(lib,name,result,args):
    fn=getattr(lib,name);fn.restype=result;fn.argtypes=args;return fn


@dataclass(eq=False,repr=False)
class Watch:
    process: int
    pid: int
    birth: tuple
    job: int
    backend: object
    origin: object
    done: object
    ready: object
    attached: bool=False
    refused: bool=False
    exited: bool=False
    initial_event: bool=False
    initial_breakpoint: bool=False
    epoch: int=0
    pending_images: int=0
    modules: object=None
    breakin_threads: object=None


class NativeMappedSources:
    def __init__(self,lease,security):
        from .native_instance_security import NativeFixedStoreSecurity
        state=a.bound_state(lease)
        need(state is not None and OPERATION in state.window.operations
            and type(security) is NativeFixedStoreSecurity and security.lease is lease)
        self.lease,self.security,self.state=lease,security,state
        self.api=lease.fs.api;self.crt=security.system_crt;self.installation=security.runtime_installation
        self.failed=self.closed=False;self.closing=threading.Event();self.lock=threading.Lock();self.io_lock=threading.Lock()
        self.requests=queue.Queue();self.watches={};self.files=[];self.handles=[];self.events=[]
        self.incomplete=set();self.thread_handle=None;self.pending=None;self.last_peer=None
        _retained.append(self)
        self.installation._issued_binding(lease,security.runtime);self.crt._binding()
        self.k=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
        self.attach=bind(self.k,'DebugActiveProcess',B,[D])
        self.wait_event=bind(self.k,'WaitForDebugEventEx',B,[C.POINTER(DebugEvent),D])
        self.continue_event=bind(self.k,'ContinueDebugEvent',B,[D,D,D])
        self.duplicate=bind(self.k,'DuplicateHandle',B,[P,P,P,C.POINTER(P),D,B,D])
        self.current=bind(self.k,'GetCurrentProcess',P,[])
        self.current_thread=bind(self.k,'GetCurrentThread',P,[])
        self.thread_id=bind(self.k,'GetThreadId',D,[P])
        self.thread_process_id=bind(self.k,'GetProcessIdOfThread',D,[P])
        self.wait=bind(self.k,'WaitForSingleObject',D,[P,D])
        self.inside=bind(self.k,'IsProcessInJob',B,[P,P,C.POINTER(B)])
        self.open_process=bind(self.k,'OpenProcess',P,[D,B,D])
        self.query_job=bind(self.k,'QueryInformationJobObject',B,[P,D,P,D,C.POINTER(D)])
        self.query_file=bind(self.k,'GetFileInformationByHandleEx',B,[P,D,P,D])
        self.seek=bind(self.k,'SetFilePointerEx',B,[P,C.c_int64,P,D])
        self.nt=C.WinDLL('ntdll.dll',use_last_error=True,winmode=0x800)
        self.thread_start=bind(self.nt,'NtQueryInformationThread',C.c_int32,[P,D,P,D,C.POINTER(D)])
        self.expected={}
        for name,size,digest in self.installation.files:
            if not name.lower().endswith(('.exe','.dll','.pyd')):continue
            handle,directory,before=self.installation.rows[name];need(not directory)
            path=native_file_path(self.api,handle).casefold()
            self.expected[path]=(name,self.identifier(handle),before,digest)
        self.system_path=native_file_path(self.api,self.crt.directory).rstrip('\\').casefold()
        self.expected=MappingProxyType(self.expected)
        self.delegation=PumpDelegation()
        self.thread=threading.Thread(target=self._pump,name='ParkWeave-owned-image-observer',daemon=True)
        _delegations[self.delegation]=(self,state,os.getpid(),state.key,self.thread,self.expected,self.system_path)
        self.thread.start()

    def identifier(self,handle):
        row=FileIdentifier();need(self.query_file(handle,18,C.byref(row),C.sizeof(row)))
        return row.volume,bytes(row.identity)

    def _guard(self,*,work=False):
        from scripts.windows_ci.native_business_window import current_context
        need(_delegations.get(self.delegation)==(self,self.state,os.getpid(),self.state.key,self.thread,self.expected,self.system_path)
            and threading.current_thread() is self.thread and self.thread.native_id==threading.get_native_id()
            and current_context()==self.state.context and not self.state.closed
            and time.time()<self.state.window.expires_utc
            and time.monotonic()<(self.state.deadline if work else self.state.cleanup_end))
        if work:need(not self.failed and not self.state.failed)

    def _duplicate(self,handle):
        output=P();row=dict(output=output,owned=False,attempted=False,closed=False);self.handles.append(row)
        ok=self.duplicate(self.current(),handle,self.current(),C.byref(output),0,False,2)
        row['owned']=bool(ok and output.value not in (None,0,P(-1).value))
        need(ok and row['owned']);return output.value

    def watch(self,backend,process,job,birth,origin,deadline):
        a.budget(self.lease,deadline);need(not self.failed and not self.closed and not self.closing.is_set())
        self._require_origin(backend,process,job,birth,origin)
        need(type(backend) is WindowsJobProcess and backend.birth(process)==birth and self.wait(process,0)==258)
        inside=B();need(self.inside(process,job,C.byref(inside)) and inside.value)
        with self.lock:prior=self.watches.get(birth[0])
        if prior is not None:
            need(prior.birth==birth and prior.job==job and not prior.exited);return prior
        item=Watch(self._duplicate(process),birth[0],birth,job,backend,origin,
            threading.Event(),threading.Event(),modules={},breakin_threads={})
        self.requests.put(item)
        need(item.done.wait(max(0,deadline-time.monotonic())) and not self.failed)
        a.budget(self.lease,deadline);return item

    def _require_origin(self,backend,process,job,birth,origin):
        from .processes import _ProcessState,PrivateProcessAdapter
        from .native_database_endpoint import _BackendWitness
        if type(origin) is _ProcessState:
            matches=[]
            for token,owner,stopped,attempted in self.security.processes._owned.values():
                adapter=owner if type(owner) is PrivateProcessAdapter else getattr(owner,'_adapters',{}).get(id(token))
                if type(adapter) is PrivateProcessAdapter and adapter._group(token) is origin:
                    need(not stopped and not attempted and adapter.lease is self.lease and adapter.backend is backend)
                    matches.append(adapter)
            need(len(matches)==1 and origin.executable.lease is self.lease
                and origin.registration=='ACKNOWLEDGED' and origin.resources.get('bound') is True
                and origin.resources.get('process')==process and origin.resources.get('job')==job
                and origin.resources.get('birth')==birth)
        elif type(origin) is _BackendWitness:
            endpoint=origin.endpoint
            need(endpoint.adapter.lease is self.lease and endpoint.backend is backend
                and endpoint.crt_witness is self.crt and origin.handle==process
                and endpoint.job==job and origin.birth==birth)
            self.crt.require_group_binding(endpoint.adapter,endpoint.token)
            origin._verify_identity()
        elif type(origin) is OriginalJobMember:
            need(origin in _members)
            source,root,original_process,original_job,original_birth,original_backend=_members[origin]
            need(source is self and process==original_process and job==original_job and birth==original_birth
                and backend is original_backend and root.resources.get('job')==job)
            self._require_origin(backend,root.resources['process'],job,root.resources['birth'],root)
        else:need(False)

    def _identity(self,item,process):
        need(item.backend.birth(process)==item.birth and self.wait(process,0)==258)
        inside=B();need(self.inside(process,item.job,C.byref(inside)) and inside.value)

    def job_pids(self,root,deadline):
        a.budget(self.lease,deadline)
        self._require_origin(self._root_backend(root),root.resources['process'],root.resources['job'],root.resources['birth'],root)
        value=JobMembers();used=D()
        need(self.query_job(root.resources['job'],3,C.byref(value),C.sizeof(value),C.byref(used))
            and 0<value.count==value.assigned<=128)
        pids=tuple(sorted(value.pids[:value.count]));need(len(set(pids))==len(pids) and all(0<p<2**32 for p in pids))
        return pids

    def _root_backend(self,root):
        from .processes import PrivateProcessAdapter
        for token,owner,stopped,attempted in self.security.processes._owned.values():
            adapter=owner if type(owner) is PrivateProcessAdapter else getattr(owner,'_adapters',{}).get(id(token))
            if type(adapter) is PrivateProcessAdapter and adapter._group(token) is root:
                need(not stopped and not attempted and adapter.lease is self.lease);return adapter.backend
        need(False)

    def job_snapshot(self,root,deadline):
        before=self.job_pids(root,deadline);job=root.resources['job'];backend=self._root_backend(root)
        observed=[]
        for pid in before:
            a.budget(self.lease,deadline)
            item=self.watches.get(pid)
            if item is None:
                row=dict(handle=None,owned=False,attempted=False,closed=False);self.handles.append(row)
                process=self.open_process(0x101410,False,pid)
                row['handle']=process;row['owned']=process not in (None,0,P(-1).value)
                need(row['owned']);birth=backend.birth(process)
                inside=B();need(birth[0]==pid and self.inside(process,job,C.byref(inside)) and inside.value
                    and self.wait(process,0)==258 and pid in self.job_pids(root,deadline))
                member=OriginalJobMember();_members[member]=(self,root,process,job,birth,backend)
                item=self.watch(backend,process,job,birth,member,deadline)
            need(item.job==job and not item.exited)
            if not item.attached:return None
            need(item.ready.wait(max(0,deadline-time.monotonic())) and not self.failed)
            snapshot=self.snapshot(item,deadline)
            if snapshot is None:return None
            observed.append(snapshot)
        need(self.job_pids(root,deadline)==before)
        return before,tuple(observed)

    def _hash(self,handle,size):
        need(self.seek(handle,0,None,0));digest=sha256();remaining=size;header=b''
        while remaining:
            self._guard();part=self.api.read(handle,min(1024*1024,remaining))
            need(0<len(part)<=remaining);digest.update(part);remaining-=len(part)
            if len(header)<65536:header+=part[:65536-len(header)]
        need(self.api.read(handle,1)==b'');return digest.hexdigest(),header

    def _file(self,item,row,base):
        left=self.state.deadline-time.monotonic();need(left>0 and self.io_lock.acquire(timeout=left))
        try:return self._file_locked(item,row,base)
        finally:self.io_lock.release()

    def _file_locked(self,item,row,base):
        self._guard(work=True)
        if row is None:self.incomplete.add('NULL_ORIGINAL_IMAGE_FILE');return None
        handle=row['handle'];row.update(base=base,watch=item)
        need(0<base<0x800000000000)
        info=self.api.info(handle);descriptor=self.api.descriptor(handle);identifier=self.identifier(handle)
        path=native_file_path(self.api,handle).casefold()
        need(not info.attributes&(0x10|0x400|0x40|0x1000|0x40000|0x400000) and 64<=info.size<=128*1024*1024)
        digest,header=self._hash(handle,info.size)
        need(header[:2]==b'MZ');pe=struct.unpack_from('<I',header,0x3c)[0]
        need(0<pe<=len(header)-88 and header[pe:pe+4]==b'PE\0\0'
            and struct.unpack_from('<H',header,pe+4)[0]==0x8664)
        image_size=struct.unpack_from('<I',header,pe+24+56)[0]
        expected=self.expected.get(path)
        if expected is not None:
            name,original_id,original,digest_expected=expected
            need(identifier==original_id and (info,descriptor,self.api.final_path(handle))==original
                and digest==digest_expected);trust=('ORIGINAL_PRIVATE_INSTALLATION',name)
        else:
            need(path.rpartition('\\')[0]==self.system_path)
            os_security(self.api.security(handle))
            name=PureWindowsPath(path).name
            # Same strict embedded Microsoft chain as the existing witness.
            # Catalog-only or other roots are NOT silently admitted here.
            chain=self.crt._signature(handle,self.crt.path+'\\'+name)
            trust=('ORIGINAL_SYSTEM32_MICROSOFT_SIGNATURE',chain)
        need(self.api.info(handle)==info and self.api.descriptor(handle)==descriptor and self.identifier(handle)==identifier)
        row.update(info=info,descriptor=descriptor,identifier=identifier,path=path,digest=digest,
            image_size=image_size,trust=trust,verified=True)
        return row

    def _breakin_thread(self,event,item):
        """Identify the OS break-in thread from its original event HANDLE.

        Kernel mapped name + actual memory exports are used ONLY to identify
        debugger control flow, never as an image-file identity observation.
        """
        self._guard(work=True)
        handle=event.data.thread.thread
        need(handle and self.thread_id(handle)==event.tid and self.thread_process_id(handle)==item.pid)
        start=P();used=D()
        need(self.thread_start(handle,9,C.byref(start),C.sizeof(start),C.byref(used))==0
            and used.value==C.sizeof(start) and start.value)
        from .native_iat_observer import RemoteImage,MemoryInformation
        mapped=bind(self.k,'K32GetMappedFileNameW',D,[P,P,C.c_wchar_p,D])
        read=bind(self.k,'ReadProcessMemory',B,[P,P,P,S,C.POINTER(S)])
        query=bind(self.k,'VirtualQueryEx',S,[P,P,C.POINTER(MemoryInformation),S])
        # The original root may still be CREATE_SUSPENDED with no initialized
        # PEB/Ldr module list. Derive the image directly from this actual start
        # address's MEM_IMAGE allocation; never enumerate Ldr at this stage.
        region=MemoryInformation()
        need(query(item.process,start.value,C.byref(region),C.sizeof(region))==C.sizeof(region))
        if region.kind!=0x1000000 or not region.allocation:return
        text=C.create_unicode_buffer(4096);length=mapped(item.process,start.value,text,len(text))
        need(0<length<len(text))
        if text.value.casefold()!=self.system_path+'\\ntdll.dll':return
        base=region.allocation
        def header_read(offset,length):
            self._guard(work=True);buffer=C.create_string_buffer(length);actual=S()
            need(read(item.process,base+offset,buffer,length,C.byref(actual)) and actual.value==length)
            return buffer.raw
        dos=header_read(0,64);need(dos[:2]==b'MZ');pe=struct.unpack_from('<I',dos,0x3c)[0]
        need(0<pe<=65536);header=header_read(pe,88)
        need(header[:4]==b'PE\0\0' and struct.unpack_from('<H',header,4)[0]==0x8664)
        size=struct.unpack_from('<I',header,80)[0];need(4096<=size<=128*1024*1024)
        owner=self
        class Memory:
            def __init__(self):self.pages={}
            def image_read(self,expected_base,expected_size,offset,length):
                owner._guard(work=True)
                need(expected_base==base and expected_size==size and 0<=offset<=size and 0<length<=size-offset)
                parts=[];position=offset
                while position<offset+length:
                    page=position//4096*4096
                    if page not in self.pages:
                        info=MemoryInformation();need(query(item.process,base+page,C.byref(info),C.sizeof(info))==C.sizeof(info)
                            and info.allocation==base and info.kind==0x1000000 and info.state==0x1000
                            and not info.protect&(0x1|0x100))
                        n=min(4096,size-page);buffer=C.create_string_buffer(n);actual=S()
                        need(read(item.process,base+page,buffer,n,C.byref(actual)) and actual.value==n)
                        self.pages[page]=buffer.raw;need(len(self.pages)<=1024)
                    raw=self.pages[page];at=position-page;n=min(offset+length-position,len(raw)-at)
                    need(n>0);parts.append(raw[at:at+n]);position+=n
                return b''.join(parts)
        memory=Memory();image=RemoteImage(memory,base,size);exports=image.export_targets()
        need('DbgUiRemoteBreakin' in exports and 'DbgBreakPoint' in exports)
        remote,forwarder=exports['DbgUiRemoteBreakin'];trap,trap_forwarder=exports['DbgBreakPoint']
        need(forwarder is None and trap_forwarder is None)
        if start.value!=base+remote:return
        # Exact recognized INT3 stubs only; unknown prologues remain unsupported.
        prefix=memory.image_read(base,size,trap,6)
        if prefix.startswith(b'\xcc\xc3'):address=base+trap
        elif prefix==b'\xf3\x0f\x1e\xfa\xcc\xc3':address=base+trap+4
        else:need(False)
        item.breakin_threads[event.tid]=(handle,start.value,address)

    def _is_breakin(self,event,item):
        if not (item.initial_event and event.data.exception.first_chance
            and event.data.exception.record.code==0x80000003 and not item.initial_breakpoint):return False
        record=(item.breakin_threads or {}).get(event.tid)
        if record is None:return False
        handle,expected_start,address=record;start=P();used=D()
        need(self.thread_id(handle)==event.tid and self.thread_process_id(handle)==item.pid
            and self.thread_start(handle,9,C.byref(start),C.sizeof(start),C.byref(used))==0
            and used.value==C.sizeof(start) and start.value==expected_start)
        return event.data.exception.record.address==address

    def _event(self,event):
        record=dict(event=event,attempted=False,continued=False);self.pending=record
        need(len(self.events)<16384);self.events.append(record)
        # Register original event file ownership before ANY identity/deadline
        # validation. Process/thread event handles remain OS-owned and are
        # automatically closed by successful Continue(EXIT_*), never by us.
        file=None
        if event.code in (3,6):
            handle=event.data.process.file if event.code==3 else event.data.load.file
            if handle:
                need(handle!=P(-1).value and len(self.files)<4096)
                file=dict(handle=handle,owned=True,attempted=False,closed=False,verified=False)
                self.files.append(file);record['file']=file
        item=self.watches.get(event.pid);need(item is not None and item.attached and not item.exited)
        image_event=event.code in (3,6,7)
        if image_event:
            with self.lock:item.epoch+=1;item.pending_images+=1
        code=0x10002
        try:
            if event.code==3:
                need(not item.initial_event and event.data.process.process
                    and event.data.process.process!=item.process)
                self._identity(item,event.data.process.process);item.initial_event=True
                image=self._file(item,file,event.data.process.base)
                with self.lock:item.modules[event.data.process.base]=image
            elif event.code==6:
                need(item.initial_event)
                image=self._file(item,file,event.data.load.base)
                with self.lock:item.modules[event.data.load.base]=image
            elif event.code==7:
                with self.lock:need(event.data.base in item.modules);item.modules.pop(event.data.base)
            elif event.code==1:
                if self._is_breakin(event,item):
                    item.initial_breakpoint=True
                else:code=0x80010001
            elif event.code==2:self._breakin_thread(event,item)
            elif event.code==4:
                if item.breakin_threads:item.breakin_threads.pop(event.tid,None)
            elif event.code not in (5,8):need(False)
        except BaseException:
            self.incomplete.add('IMAGE_EVENT_EVIDENCE_INCOMPLETE')
            if event.code==1:code=0x80010001
            if self.crt.unknown:self.failed=True;a.fail_resource(self.lease)
        record['attempted']=True
        need(self.continue_event(event.pid,event.tid,code));record['continued']=True;self.pending=None
        if image_event:
            with self.lock:item.epoch+=1;item.pending_images-=1
        if event.code==1 and item.initial_breakpoint:item.ready.set()
        if event.code==5:
            with self.lock:item.exited=True;item.epoch+=1

    def _pump(self):
        try:
            self.thread_handle=self._duplicate(self.current_thread())
            need(self.thread_id(self.thread_handle)==threading.get_native_id())
            while True:
                self._guard()
                while True:
                    try:item=self.requests.get_nowait()
                    except queue.Empty:break
                    try:
                        self._guard(work=True);self._identity(item,item.process)
                        with self.lock:need(item.pid not in self.watches);self.watches[item.pid]=item
                        ok=self.attach(item.pid)
                        item.attached=bool(ok);item.refused=not ok
                        if not ok:self.incomplete.add('ORIGINAL_DEBUG_ATTACH_REFUSED')
                    finally:item.done.set()
                if self.closing.is_set() and all(w.exited or w.refused for w in self.watches.values()):return
                if not any(w.attached and not w.exited for w in self.watches.values()):
                    # WaitForDebugEvent with no debug connection is invalid.
                    # No native event wait before the first successful attach.
                    self.closing.wait(.01)
                    continue
                event=DebugEvent()
                self.wait_output=event  # Preserve native output storage if Wait raises.
                if self.wait_event(C.byref(event),10):self._event(event)
                else:need(C.get_last_error() in (121,258))
        except BaseException:
            self.failed=True;a.fail_resource(self.lease)
            for item in tuple(self.watches.values()):item.done.set();item.ready.set()
            # Keep the default debugger kill-on-thread-exit policy. Failure
            # cannot detach/continue or report the owned processes stopped.

    def snapshot(self,item,deadline):
        a.budget(self.lease,deadline)
        if self.failed or self.incomplete or not item.attached or not item.initial_event or not item.initial_breakpoint:return None
        left=deadline-time.monotonic();need(left>0 and self.io_lock.acquire(timeout=left))
        try:return self._snapshot_locked(item,deadline)
        finally:self.io_lock.release()

    def _snapshot_locked(self,item,deadline):
        self._identity(item,item.process)
        with self.lock:
            if item.pending_images:return None
            epoch=item.epoch;rows=tuple(sorted(item.modules.items()))
        if not rows or any(row is None or not row['verified'] for _,row in rows):return None
        from .native_iat_observer import ModuleInformation
        enum=bind(self.k,'K32EnumProcessModulesEx',B,[P,P,D,C.POINTER(D),D])
        mapped=bind(self.k,'K32GetMappedFileNameW',D,[P,P,C.c_wchar_p,D])
        module_info=bind(self.k,'K32GetModuleInformation',B,[P,P,C.POINTER(ModuleInformation),D])
        def modules():
            a.budget(self.lease,deadline);values=(P*4096)();used=D()
            need(enum(item.process,values,C.sizeof(values),C.byref(used),3) and 0<used.value<=C.sizeof(values)
                and used.value%C.sizeof(P)==0)
            result=[]
            for base in values[:used.value//C.sizeof(P)]:
                text=C.create_unicode_buffer(4096);length=mapped(item.process,base,text,len(text));info=ModuleInformation()
                need(0<length<len(text) and module_info(item.process,base,C.byref(info),C.sizeof(info)) and info.base==base)
                result.append((base,text.value.casefold(),info.size))
            return tuple(sorted(result))
        observed=modules()
        need(observed==tuple((base,row['path'],row['image_size']) for base,row in rows))
        evidence=[]
        for base,row in rows:
            a.budget(self.lease,deadline)
            need(not row['attempted'] and not row['closed'] and self.api.info(row['handle'])==row['info']
                and self.identifier(row['handle'])==row['identifier'] and self.api.descriptor(row['handle'])==row['descriptor'])
            need(self.seek(row['handle'],0,None,0));digest=sha256();remaining=row['info'].size
            while remaining:
                a.budget(self.lease,deadline);part=self.api.read(row['handle'],min(1024*1024,remaining))
                need(0<len(part)<=remaining);digest.update(part);remaining-=len(part)
            need(digest.hexdigest()==row['digest'] and self.api.info(row['handle'])==row['info'])
            evidence.append((base,row['identifier'],row['descriptor'],row['digest'],row['trust']))
        need(modules()==observed);self._identity(item,item.process)
        with self.lock:need(epoch==item.epoch and not item.exited and not item.pending_images)
        return item.birth,tuple(evidence)

    def close(self):
        a.budget(self.lease,cleanup=True);need(not self.closed)
        self.closing.set();end=a.budget(self.lease,time.monotonic()+5,cleanup=True)
        self.thread.join(max(0,end-time.monotonic()))
        need(not self.thread.is_alive() and self.thread_handle and not self.failed and self.pending is None
            and all(w.exited or w.refused for w in self.watches.values()))
        left=end-time.monotonic();need(left>0 and self.wait(self.thread_handle,int(left*1000))==0)
        for row in list(reversed(self.files))+list(reversed(self.handles)):
            a.budget(self.lease,end,cleanup=True)
            if not row['owned']:continue
            need(not row['attempted']);row['attempted']=True
            handle=row['handle'] if 'handle' in row else row['output'].value
            self.api.close(handle);row['closed']=True
        self.closed=True
        if self in _retained:_retained.remove(self)


def session(lease):
    value=a.bound_state(lease)
    if value is None:return None
    if lease not in _sessions:
        security=next(inv.security.security for inv in value.compositions if inv.security.security.lease is lease)
        candidate=security._hold(object.__new__(NativeMappedSources))
        NativeMappedSources.__init__(candidate,lease,security);_sessions[lease]=candidate
    return _sessions[lease]


def before_resume(backend,group,deadline):
    if type(backend) is not WindowsJobProcess:return
    lease=getattr(group.executable,'lease',None)
    if a.bound_state(lease) is None:return
    need(group.resources.get('bound') is True and not group.started)
    value=session(lease);r=group.resources
    value.watch(backend,r['process'],r['job'],r['birth'],group,deadline)


def actual_peer(lease,peer,deadline):
    if a.bound_state(lease) is None:return
    from .native_database_endpoint import _BackendWitness
    need(type(peer) is _BackendWitness);peer._verify_identity()
    endpoint=peer.endpoint;value=session(lease)
    need(endpoint.adapter.lease is lease and endpoint.crt_witness is value.crt)
    item=value.watch(endpoint.backend,peer.handle,endpoint.job,peer.birth,peer,deadline)
    snapshot=None
    if item.attached:
        need(item.ready.wait(max(0,deadline-time.monotonic())) and not value.failed)
        peer._verify_identity();snapshot=value.snapshot(item,deadline);peer._verify_identity()
    # Capture while this original SQL socket/backend HANDLE is STILL live.
    # Reusing the integer after _database closes its connection is prohibited.
    value.last_peer=(peer,item,snapshot)


def collect(lease,groups,deadline):
    if a.bound_state(lease) is None:return
    value=session(lease);peer=value.last_peer
    if peer is None:return
    original,item,backend_snapshot=peer
    if backend_snapshot is None:return
    need(original.endpoint.adapter.lease is lease and len(groups)==3 and len({id(t) for _,t,_ in groups})==3
        and any(adapter is original.endpoint.adapter and token is original.endpoint.token for adapter,token,_ in groups))
    snapshots=[]
    for adapter,token,identity in groups:
        group=adapter._group(token);watch=value.watches.get(identity[0])
        need(watch is not None and watch.origin is group and watch.birth==identity[1]
            and watch.job==group.resources['job'] and adapter.live_identity(token)==identity)
        snapshot=value.job_snapshot(group,deadline)
        if snapshot is None:return
        snapshots.append(snapshot)
    from .native_trial_facts import _seal
    return _seal(lease,('original_job_and_backend_loaded_sources',),value,(original,tuple(snapshots),backend_snapshot))
