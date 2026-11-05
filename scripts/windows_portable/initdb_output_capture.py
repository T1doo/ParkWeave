"""Trial-only anonymous stderr capture; never serialize raw child output."""
import ctypes as C
import os
import threading


POSTGRES_STARTUP_LABELS = (
    'ADMIN_TOKEN_ERROR', 'LISTEN_ADDRESS_UNAVAILABLE', 'POSTMASTER_LOCK_CONFLICT',
    'DATA_DIRECTORY_ERROR', 'ACCESS_DENIED', 'CONFIGURATION_ERROR',
    'POSTGRES_FATAL', 'POSTGRES_PANIC',
)


def postgres_startup_labels(raw):
    data = raw.lower()
    signatures = (
        (b'user with administrative permissions', b'unprivileged user id'),
        (b'could not bind', b'address already in use', b'could not create any tcp/ip sockets'),
        (b'lock file "postmaster.pid" already exists',),
        (b'data directory', b'pg_control'),
        (b'permission denied', b'access is denied'),
        (b'configuration file', b'unrecognized configuration parameter'),
        (b'fatal:',),
        (b'panic:',),
    )
    return tuple(label for label, phrases in zip(POSTGRES_STARTUP_LABELS, signatures)
                 if any(phrase in data for phrase in phrases))


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


class PostgresOutputCapture(InitdbOutputCapture):
    """Drain the trial server's pipe so diagnostic output cannot block it."""

    def __init__(self):
        super().__init__()
        self.reader = None
        self.result = dict(status='READ_UNAVAILABLE', bytes_read=0, truncated=False, labels=())

    def start(self):
        self.close_write()
        reader = threading.Thread(target=self._drain, name='parkweave-postgres-stderr', daemon=True)
        reader.start()
        self.reader = reader

    def _drain(self):
        first = bytearray()
        truncated = False
        try:
            while chunk := os.read(self.read_fd, 4096):
                remaining = 65536 - len(first)
                first.extend(chunk[:remaining])
                truncated |= len(chunk) > remaining
        except OSError:
            return
        self.result = dict(status='CLASSIFIED' if first else 'EMPTY_OR_CLOSED',
                           bytes_read=len(first), truncated=truncated, labels=postgres_startup_labels(first))

    def snapshot(self):
        if self.reader is not None:
            self.reader.join(0.2)
        return dict(self.result)

    def close(self):
        if getattr(self, 'reader', None) is not None:
            self.reader.join(0.2)
            if self.reader.is_alive():
                raise RuntimeError('CAPTURE_DRAIN_UNKNOWN')
        super().close()
