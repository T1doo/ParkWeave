"""Interruption probes reuse the original pinned, registered process adapter."""
import base64
import ctypes as C
import os
import time
import weakref
import zlib

from . import native_trial_authority as a
from .native_protected_objects import require_original_creation
from .processes import Command,PrivateProcessAdapter
from .windows_process_handles import WindowsJobProcess,consume_stopped_group

_issued=weakref.WeakKeyDictionary()
_retained=[]
STAGES=('BEFORE_WRITE','PARTIAL_WRITE','BEFORE_FLUSH','AFTER_FLUSH')


class NativeInterruptionBackend(WindowsJobProcess):
    def __init__(self,probe,node,stage,command):
        a.need(a.bound_state(probe.lease) is not None and stage in STAGES)
        before=require_original_creation(probe.api,node)
        super().__init__()
        self.lease,self.probe,self.node,self.stage,self.command=probe.lease,probe,node,stage,command
        _issued[self]=(probe.lease,probe,node,stage,command,before)

    def preflight(self,command):
        a.budget(self.lease)
        a.need(self in _issued and command is self.command and command.stdio_contract=='FIXED_SLOT_INTERRUPT_V1'
            and command.arguments[:4]==('-I','-B','-m','scripts.windows_ci.native_slot_interrupt_child')
            and command.arguments[4]==self.stage)
        a.need(require_original_creation(self.probe.api,self.node)==_issued[self][-1])


def prepare_stdio(backend,group,null_fd):
    a.need(type(backend) is NativeInterruptionBackend and backend in _issued
           and group.command is backend.command and group.executable.lease is backend.lease)
    backend.preflight(group.command)
    r,original=group.resources,backend.original;win=original.win
    duplicate=win.DuplicateHandle(win.GetCurrentProcess(),backend.node,win.GetCurrentProcess(),0,False,win.DUPLICATE_SAME_ACCESS)
    r['interrupt_duplicate']=duplicate  # Before CRT ownership transfer.
    try:
        fd=original.crt.open_osfhandle(duplicate,os.O_WRONLY|os.O_BINARY)
        a.need(fd>=0)
    except BaseException:
        r.setdefault('stdio_close_unknown',[]).append(('INTERRUPT_CRT_TRANSFER',duplicate));raise
    r['interrupt_file_fd']=fd;r.pop('interrupt_duplicate')
    r['interrupt_ready_r'],r['interrupt_ready_w']=os.pipe()
    return [null_fd,fd,r['interrupt_ready_w']]


class NativeInterruptionJob:
    def __init__(self,probe,security,node,stage,raw):
        self.probe,self.security,self.node,self.stage=probe,security,node,stage
        self.lease=probe.lease;self.token=None;self.adapter=None
        a.need(a.bound_state(self.lease) is not None and len(raw)==8192 and stage in STAGES)
        security.runtime_installation._issued_binding(self.lease,security.runtime)
        _,size,digest=next(row for row in security.runtime_installation.files if row[0]=='runtime/python/python.exe')
        # Frozen command data are bounded non-secret journal bytes, NOT a path
        # or credential. Authority is only the inherited original stdout file.
        command=Command('runtime/python/python.exe',digest,size,('-I','-B','-m','scripts.windows_ci.native_slot_interrupt_child',stage,
            base64.b64encode(zlib.compress(raw)).decode('ascii')),'WINDOWS_JOB','FIXED_SLOT_INTERRUPT_V1')
        backend=NativeInterruptionBackend(probe,node,stage,command)
        self.adapter=PrivateProcessAdapter(self.lease,{'slot_probe':command},startup_seconds=5,_backend=backend)

    def run(self):
        import msvcrt
        self.token=self.adapter.launch('slot_probe',lambda token:a.register_auxiliary(self.security.processes,self.adapter,token))
        group=self.adapter._group(self.token)
        identity=self.adapter.live_identity(self.token)
        peek=self.adapter.backend.kernel.PeekNamedPipe
        peek.argtypes,peek.restype=[C.c_void_p,C.c_void_p,C.c_uint32,C.c_void_p,C.POINTER(C.c_uint32),C.c_void_p],C.c_int32
        deadline=a.budget(self.lease,time.monotonic()+5)
        frame=bytearray();expected=('PW_SLOT_INTERRUPTION/1 '+self.stage+' '+str(identity[0])+'\n').encode('ascii')
        while time.monotonic()<deadline:
            a.budget(self.lease,deadline)
            a.need(self.adapter.live_identity(self.token)==identity)
            available=C.c_uint32()
            a.need(peek(msvcrt.get_osfhandle(group.resources['interrupt_ready_r']),None,0,None,C.byref(available),None))
            if available.value:
                a.need(available.value<=128)
                frame.extend(os.read(group.resources['interrupt_ready_r'],available.value))
                if b'\n' in frame:break
            time.sleep(.005)
        a.need(bytes(frame)==expected and time.monotonic()<deadline)
        a.need(self.security.processes.stop_owned(self.token) is True)
        consume_stopped_group(self.adapter,self.token,identity)
        return self.stage,identity,self.probe.api.info(self.node).size

    def cleanup_partial(self):
        token=self.token
        # launch may have registered the original token before returning it.
        if token is None and self.adapter is not None:
            values=tuple(self.adapter._issued.values())
            if len(values)==1:token=values[0][0]
        if token is None:return True
        if id(token) in self.security.processes._owned:return self.security.processes.stop_owned(token)
        return self.adapter.stop_owned(token)
