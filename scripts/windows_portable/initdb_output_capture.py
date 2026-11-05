"""Trial-only anonymous stderr capture; never serialize raw child output."""
import ctypes as C
import os


def labels(raw):
    data=raw.lower();result=[]
    if b'password' in data and (b'open' in data or b'read' in data):result.append('PASSWORD_INPUT_ERROR')
    if b'postgres' in data and (b'not found' in data or b'not find' in data):result.append('POSTGRES_LOOKUP_ERROR')
    if b'postgres.bki' in data:result.append('BKI_FILE_ERROR')
    if b'postgresql.conf.sample' in data:result.append('CONFIG_SAMPLE_ERROR')
    if b'permission denied' in data:result.append('ACCESS_DENIED')
    if b'no such file' in data:result.append('MISSING_FILE')
    if b'could not load' in data or b'could not execute' in data:result.append('LOAD_OR_EXEC_ERROR')
    if b'locale' in data and b'invalid' in data:result.append('LOCALE_ERROR')
    if b'administrator' in data:result.append('ADMIN_TOKEN_ERROR')
    if b'error:' in data:result.append('INITDB_REPORTED_ERROR')
    return tuple(result)


class InitdbOutputCapture:
    def __init__(self):
        if os.name!='nt':raise RuntimeError('WINDOWS_CAPTURE_REQUIRED')
        import msvcrt
        self.read_fd=self.write_fd=None;self.attempted=set();self.errors=[]
        try:
            self.read_fd,self.write_fd=os.pipe()
            self.get_handle=msvcrt.get_osfhandle
            self.kernel=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
            self.peek=self.kernel.PeekNamedPipe
            self.peek.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32,C.c_void_p,C.POINTER(C.c_uint32),C.c_void_p]
            self.peek.restype=C.c_int32
        except BaseException:
            self.close();raise

    @property
    def write_handle(self):return self.get_handle(self.write_fd)

    def _close(self,name):
        fd=getattr(self,name)
        if fd is None:return
        if name in self.attempted:raise RuntimeError('CAPTURE_CLOSE_UNKNOWN_NO_RETRY')
        self.attempted.add(name)
        try:os.close(fd);setattr(self,name,None)
        except BaseException:self.errors.append(name);raise

    def close_write(self):self._close('write_fd')

    def snapshot(self,*,secret_started):
        # Marked BEFORE any password write attempt, including uncertain writes.
        if secret_started is not False:return dict(status='SUPPRESSED_AFTER_SECRET',bytes_read=0,truncated=False,labels=())
        available=C.c_uint32()
        ok=self.peek(self.get_handle(self.read_fd),None,0,None,C.byref(available),None)
        if not ok:
            status='EMPTY_OR_CLOSED' if C.get_last_error()==109 else 'READ_UNAVAILABLE'
            return dict(status=status,bytes_read=0,truncated=False,labels=())
        count=min(65536,available.value)
        raw=os.read(self.read_fd,count) if count else b''  # Single consumer, available bytes only.
        return dict(status='CLASSIFIED',bytes_read=len(raw),truncated=available.value>65536,labels=labels(raw))

    def close(self):
        errors=[]
        for name in ('write_fd','read_fd'):
            try:self._close(name)
            except BaseException as error:errors.append(error)
        if errors:raise BaseExceptionGroup('CAPTURE_CLOSE_UNKNOWN',errors)
