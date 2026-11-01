"""Actual POSIX IO bridge for the shared production storage algorithm ONLY.

Never calls the Windows constructor, manufactures Windows identities/ACLs,
changes a journal to READY, or issues a native runtime/acceptance capability.
"""
import ctypes as C
from hashlib import sha256
import os,stat,time
from pathlib import Path
from types import SimpleNamespace

from parkweave.windows_files import Info
from scripts.windows_portable import native_runtime_staging as runtime
from scripts.windows_portable import endpoint_plan
from scripts.windows_portable.fixed_secret_store import _under_lease


class PosixStorage(runtime.NativeRuntimeInstallation):
    def __init__(self,lease,source,files,*,seconds=60):
        self.lease=lease;self.api=SimpleNamespace(readonly=SimpleNamespace())
        self.key=_under_lease(lease,lambda:endpoint_plan._key_held(lease))
        self.deadline=time.monotonic()+seconds;self.failed=self.closed=False
        self.handles=[];self.cleanup_errors=[];self.rows={};self.identities=set();self.source_nodes={}
        self._completion_pending=True;self._copy_complete=False;self._created_directory_rows={}
        self.root_path=self.path(lease.fs.root);self.root_sd=self.descriptor(lease.fs.root)
        self.probe=SimpleNamespace(unknown=False)
        paths=set()
        for path in files:
            for i in range(1,len(path.split('/'))):paths.add('/'.join(path.split('/')[:i]))
        self.directories=tuple(sorted(paths,key=lambda p:(p.count('/'),p)))
        self.files=tuple((name,len(data),sha256(data).hexdigest()) for name,data in sorted(files.items()))
        self.api.need=lambda ok:runtime.need(ok)
        self.api.info=self.info;self.api.read=self.read;self.api.close=self.close_fd
        self.api.writefile=self.write;self.api.flushfile=self.flush;self.seek=self.seek_fd
        self.events=[];self.source=source
        self.inject=None

    @staticmethod
    def path(fd):return os.readlink('/proc/self/fd/'+str(fd)).replace('/','\\')
    @staticmethod
    def descriptor(fd):
        s=os.fstat(fd);return s.st_uid,stat.S_IMODE(s.st_mode)
    @staticmethod
    def info(fd):
        s=os.fstat(fd)
        return Info(0x10 if stat.S_ISDIR(s.st_mode) else 0x80,s.st_size,s.st_nlink,s.st_dev,s.st_ino)
    def event(self,kind,fd=None):
        self.events.append((kind,fd))
        if self.inject:self.inject(self,kind,fd)
    def read(self,fd,n):self.event('read',fd);return os.read(fd,n)
    def write(self,fd,buffer,n,count,overlapped):
        self.event('write',fd)
        C.cast(count,C.POINTER(C.c_uint32)).contents.value=os.write(fd,C.string_at(buffer,n));return 1
    def flush(self,fd):self.event('flush',fd);os.fsync(fd);return 1
    def seek_fd(self,fd,offset,result,origin):os.lseek(fd,offset,origin);return 1
    def close_fd(self,fd):self.event('close',fd);os.close(fd)
    def _gate(self):self._time();self.lease._verify()
    def _source(self,root):
        self._gate();fd=self._hold(os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW))
        self.source_volume=os.fstat(fd).st_dev;return fd
    def _open(self,parent,name):
        self._gate();return self._hold(os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=parent))
    def _create(self,parent,leaf,directory):
        self._gate();self.event('create',parent)
        if directory:
            os.mkdir(leaf,0o700,dir_fd=parent)
            fd=os.open(leaf,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        else:fd=os.open(leaf,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
        return self._hold(fd)
    def _inspect(self,fd,directory,*,private=True,volume=None):
        self._time();self.event('inspect',fd);s=os.fstat(fd)
        runtime.need(stat.S_ISDIR(s.st_mode)==directory and (directory or stat.S_ISREG(s.st_mode)))
        runtime.need(volume is None or s.st_dev==volume)
        runtime.need(not private or s.st_uid==os.geteuid() and not stat.S_IMODE(s.st_mode)&0o077)
        return self.info(fd),self.descriptor(fd),self.path(fd)
    def _entries(self,fd):
        self._gate();rows=[]
        for name in os.listdir(fd):
            s=os.stat(name,dir_fd=fd,follow_symlinks=False)
            runtime.need(stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode))
            rows.append((name,0x10 if stat.S_ISDIR(s.st_mode) else 0x80,s.st_ino))
        return tuple(rows)

    def dispose_posix_test_only(self):
        # Test failure injection can deliberately make the production cleanup
        # refuse. POSIX calls are synchronous and this test owns all FDs. This
        # teardown NEVER establishes native safe-close or Windows completion.
        for fd in tuple(self.handles):
            try:os.close(fd)
            except OSError:pass
        self.handles.clear()
