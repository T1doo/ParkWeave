"""Private inherited-pipe desktop bridge, never a browser or permission issuer.

The EXE owns this exact child. Only the original live workspace callback emits
RUNNING; EOF is a stop request. No password/bearer/DSN enters argv or replies.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import threading
import time

MAX_REQUEST = 32768
_unknown = []


def request(stream):
    raw = stream.readline(MAX_REQUEST+1)
    if not raw.endswith(b'\n') or len(raw)>MAX_REQUEST:raise ValueError('DESKTOP_REQUEST_REFUSED')
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('DESKTOP_DUPLICATE_FIELD')
            result[key]=value
        return result
    value=json.loads(raw,object_pairs_hook=pairs)
    if type(value) is not dict or set(value)!={'action','instance','database_port','api_port','passwords','initialize_profile'}:
        raise ValueError('DESKTOP_REQUEST_SHAPE')
    if value['action'] not in ('status','new','reopen'):raise ValueError('DESKTOP_ACTION')
    if type(value['instance']) is not str or len(value['instance'])>2048:raise ValueError('DESKTOP_INSTANCE')
    if any(type(value[k]) is not int or not 0<=value[k]<=65535 for k in ('database_port','api_port')):
        raise ValueError('DESKTOP_PORT')
    if type(value['passwords']) is not dict:raise ValueError('DESKTOP_ENROLLMENT')
    if type(value['initialize_profile']) is not bool or (value['action']=='status' and value['initialize_profile']):
        raise ValueError('DESKTOP_PROFILE_MODE')
    if value['action']!='new' and (value['passwords'] or value['database_port'] or value['api_port']):
        raise ValueError('DESKTOP_REOPEN_READS_EXISTING_INPUTS')
    return value


class Channel:
    def __init__(self,source,sink):
        self.source,self.sink=source,sink
        self.stop=threading.Event();self.closed=threading.Event()
        self.confirmed=False
    def emit(self,kind,*fields):
        if kind not in ('RUNNING','ALIVE','STOPPED','REFUSED','UNKNOWN'):raise ValueError('DESKTOP_EVENT')
        raw=('PW1\t'+'\t'.join((kind,*map(str,fields)))+'\n').encode('ascii')
        if len(raw)>16384 or any('\n' in str(x) or '\t' in str(x) for x in fields):raise ValueError('DESKTOP_EVENT_BOUNDS')
        self.sink.write(raw);self.sink.flush()
    def monitor(self):
        try:
            # Any input/EOF after the first bounded request means stop. Never
            # interpret another launch, key, token or command in the same child.
            self.confirmed=self.source.read(1)==b'S'
        finally:self.stop.set();self.closed.set()


def run(value,channel,*,entry_module=None,profile_factory=None,observe=None):
    if entry_module is None:
        if __package__:from . import entry as entry_module
        else:
            # Bootstrap these two exact pinned launcher files. Do not change
            # _pth/sys.path or let an unrelated vendor module choose the entry.
            import importlib.util
            for name,file in (('payload','payload.py'),('_parkweave_desktop_entry','entry.py')):
                spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(file))
                if spec is None or spec.loader is None:raise ValueError('DESKTOP_PINNED_BOOTSTRAP_REQUIRED')
                module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
                if file=='entry.py':entry_module=module
    args=['--action',value['action']]
    if value['action']!='status':args+=['--instance',value['instance']]
    if value['action']=='new':args+=['--database-port',str(value['database_port']),'--api-port',str(value['api_port'])]
    def enroll():
        from scripts.windows_portable.native_web_login import NativeLoginEnrollment
        return NativeLoginEnrollment(value['passwords'])
    entered=False
    def use(workspace,invocation):
        nonlocal entered
        entered=True
        workspace.check()
        if channel.stop.is_set():
            if channel.confirmed:return
            raise RuntimeError('DESKTOP_HOST_LOST_STOP_UNKNOWN')
        factory=profile_factory
        if factory is None:
            from scripts.windows_portable.desktop_profile import NativeDesktopProfile
            factory=NativeDesktopProfile
        profile=factory(workspace,invocation,value['action']=='new' or value['initialize_profile'])
        try:
            workspace.check();profile.verify()
            if channel.stop.is_set():
                if channel.confirmed:return
                raise RuntimeError('DESKTOP_HOST_LOST_STOP_UNKNOWN')
            channel.emit('RUNNING',workspace.application.port,profile.path.encode('utf-16-le').hex())
            while not channel.stop.wait(.75):
                workspace.check();profile.verify()
                app=workspace.application
                app.adapter.live_identity(app.api);app.adapter.live_identity(app.worker)
                if observe is not None:observe(workspace)
                channel.emit('ALIVE')
            if not channel.confirmed:raise RuntimeError('DESKTOP_HOST_LOST_STOP_UNKNOWN')
        finally:
            # Host must close/release WebView2 before sending its stop byte.
            # Profile is retained; neither cookies nor localStorage are erased.
            profile.close()
    # Do not forward ordinary CLI output or private exception text to the host.
    # Fixed maximum output prevents accidental unbounded diagnostics in memory.
    class Discard(io.TextIOBase):
        def __init__(self):self.reason='ORIGINAL_ENTRY_GATE_OR_FAILURE'
        def write(self,text):
            for code in ('OWNER_MUTATION_PAUSED','WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED',
                         'NATIVE_RUNTIME_LOADING_NOT_ACCEPTED','SYSTEM_CRT_PREREQUISITE_UNVERIFIED'):
                if code in text:self.reason=code
            return len(text)
    diagnostic=Discard()
    with contextlib.redirect_stdout(diagnostic),contextlib.redirect_stderr(diagnostic):
        code=entry_module.main(args,read=lambda _: (_ for _ in ()).throw(EOFError()),use_workspace=use,enroll=enroll)
    if code==0 and value['action']!='status':channel.emit('STOPPED')
    elif not entered and diagnostic.reason!='ORIGINAL_ENTRY_GATE_OR_FAILURE':channel.emit('REFUSED',diagnostic.reason)
    else:channel.emit('UNKNOWN','ORIGINAL_ENTRY_FAILED_OR_STOP_UNKNOWN')
    return code


def main():
    if os.name!='nt' or not sys.flags.isolated:raise SystemExit(2)
    # Standard streams must be the two anonymous pipes explicitly inherited by
    # the desktop host. No console/file/terminal or unrelated HANDLE fallback.
    import ctypes as C
    import msvcrt
    kernel=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
    kernel.GetFileType.argtypes=[C.c_void_p];kernel.GetFileType.restype=C.c_uint32
    if any(kernel.GetFileType(msvcrt.get_osfhandle(s.fileno()))!=3 for s in (sys.stdin,sys.stdout)):
        raise SystemExit(2)
    channel=Channel(sys.stdin.buffer,sys.stdout.buffer)
    try:
        value=request(channel.source)
        thread=threading.Thread(target=channel.monitor,daemon=True);thread.start()
        return run(value,channel)
    except BaseException:
        try:channel.emit('UNKNOWN','DESKTOP_BRIDGE_FAILED')
        except BaseException:pass
        return 2


if __name__=='__main__':raise SystemExit(main())
