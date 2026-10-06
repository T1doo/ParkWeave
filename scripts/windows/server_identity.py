"""Read-only launcher/server binding. Records are private; refusals are constant."""
import ctypes
import math
import os
import time
from contextlib import ExitStack
from pathlib import Path

KERNEL_TIME_TOLERANCE = 0.000010


class IdentityRefused(Exception):
    def __init__(self):
        super().__init__('SERVER_IDENTITY_REFUSED')


def positive_pid(value):
    return type(value) is int and 0 < value <= 0xffffffff


def creation_time(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


class WindowsBackend:
    """Only query/synchronize rights; no termination or privilege API."""
    def __init__(self):
        if os.name != 'nt':
            raise IdentityRefused()
        from ctypes import wintypes
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.FILETIME = wintypes.FILETIME
        declarations = {
            'OpenProcess': ([wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE),
            'GetProcessId': ([wintypes.HANDLE], wintypes.DWORD),
            'GetProcessTimes': ([wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4, wintypes.BOOL),
            'WaitForSingleObject': ([wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD),
            'CloseHandle': ([wintypes.HANDLE], wintypes.BOOL),
        }
        for name, (args, result) in declarations.items():
            function = getattr(self.kernel, name)
            function.argtypes = args
            function.restype = result

    def open(self, pid):
        handle = self.kernel.OpenProcess(0x1000 | 0x100000, False, pid)
        if not handle:
            raise IdentityRefused()
        return handle

    def creation_handle(self, process):
        import psutil
        if not isinstance(process, psutil.Popen):
            return None
        # psutil.Popen forwards attributes absent on Process to its private
        # subprocess.Popen. _proc is the psutil platform object, not Popen.
        handle = process._handle
        if isinstance(handle, bool) or not handle or int(handle) <= 0:
            raise IdentityRefused()
        return int(handle)

    def identity(self, handle):
        pid = self.kernel.GetProcessId(handle)
        times = [self.FILETIME() for _ in range(4)]
        if not pid or not self.kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            raise IdentityRefused()
        ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        # Subtract the epoch before float conversion, preserving sub-microsecond precision.
        created = (ticks - 116444736000000000) / 10000000
        wait = self.kernel.WaitForSingleObject(handle, 0)
        if wait not in (0, 258):
            raise IdentityRefused()
        return pid, created, wait == 258

    def close(self, handle):
        if not self.kernel.CloseHandle(handle):
            raise IdentityRefused()


class PinnedProcess:
    """Hold an exact process object while its PID identity is checked/used."""
    def __init__(self, pid, created, backend=None):
        self.pid, self.created = pid, created
        self.backend = backend
        self.handle = None
        self.alive = None

    def verify(self, *, require_live=True):
        self.alive = None
        if type(require_live) is not bool:
            raise IdentityRefused()
        if self.handle is None:
            raise IdentityRefused()
        pid, created, alive = self.backend.identity(self.handle)
        if not positive_pid(pid) or pid != self.pid or not creation_time(created) or abs(created - self.created) > KERNEL_TIME_TOLERANCE or type(alive) is not bool or (require_live and not alive):
            raise IdentityRefused()
        self.alive = alive
        return self

    def __enter__(self):
        if not positive_pid(self.pid) or not creation_time(self.created):
            raise IdentityRefused()
        if self.backend is None:
            self.backend = WindowsBackend()
        try:
            self.handle = self.backend.open(self.pid)
            return self.verify()
        except BaseException as error:
            if self.handle is not None:
                handle, self.handle = self.handle, None
                try:
                    self.backend.close(handle)
                except Exception:
                    pass
            if isinstance(error, Exception):
                raise IdentityRefused() from None
            raise

    def __exit__(self, kind, value, traceback):
        handle, self.handle = self.handle, None
        if handle is not None:
            try:
                self.backend.close(handle)
            except Exception:
                raise IdentityRefused() from None


def _snapshot(process):
    pid, created = process.pid, process.create_time()
    if not positive_pid(pid) or not creation_time(created):
        raise IdentityRefused()
    return pid, created, process.cwd(), tuple(process.cmdline()), process.ppid()


def bind_server(root, record, health_pid, repo, *, identify,
                process_factory=None, backend=None, clock=time.time):
    """Return a fixed relation and a private server record (or None).

    identify must be the lifecycle's unchanged identify_process, including its
    trusted_command check. Only the reported PID is opened; no enumeration.
    """
    try:
        if not positive_pid(health_pid) or not isinstance(record, dict):
            raise IdentityRefused()
        if not positive_pid(record['pid']) or not creation_time(record['created']) or not isinstance(record['command'], list) or not all(isinstance(arg, str) for arg in record['command']):
            raise IdentityRefused()
        if not identify(root, record, repo):
            raise IdentityRefused()
        before = _snapshot(root)
        if before[0] != record['pid'] or abs(before[1] - record['created']) > KERNEL_TIME_TOLERANCE:
            raise IdentityRefused()
        if before[2] != str(Path(repo).resolve()) or before[3] != tuple(record['command']):
            raise IdentityRefused()
        if backend is None:
            backend = WindowsBackend()
        borrowed = backend.creation_handle(root)
        def verify_borrowed():
            if borrowed is not None:
                pid, created, alive = backend.identity(borrowed)
                if not positive_pid(pid) or pid != before[0] or not creation_time(created) or abs(created-record['created']) > KERNEL_TIME_TOLERANCE or alive is not True:
                    raise IdentityRefused()
        verify_borrowed()
        with ExitStack() as stack:
            root_pin = stack.enter_context(PinnedProcess(before[0], record['created'], backend))
            child_record = None
            if health_pid == before[0]:
                relation = 'ROOT'
                candidate, candidate_before, candidate_pin = root, before, root_pin
            else:
                if process_factory is None:
                    import psutil
                    process_factory = psutil.Process
                candidate = process_factory(health_pid)
                candidate_before = _snapshot(candidate)
                bound_at = clock()
                if not creation_time(bound_at) or candidate_before[0] != health_pid:
                    raise IdentityRefused()
                if candidate_before[4] != before[0] or not before[1] <= candidate_before[1] <= min(bound_at, before[1] + 60):
                    raise IdentityRefused()
                if candidate_before[2:4] != before[2:4]:
                    raise IdentityRefused()
                child_record = {'pid': health_pid, 'created': candidate_before[1],
                                'command': list(record['command']), 'parent_pid': before[0],
                                'parent_created': record['created']}
                if not identify(candidate, child_record, repo):
                    raise IdentityRefused()
                candidate_pin = stack.enter_context(PinnedProcess(health_pid, candidate_before[1], backend))
                relation = 'DIRECT_CHILD'
            if _snapshot(root) != before or _snapshot(candidate) != candidate_before:
                raise IdentityRefused()
            if not identify(root, record, repo) or (child_record is not None and not identify(candidate, child_record, repo)):
                raise IdentityRefused()
            root_pin.verify()
            candidate_pin.verify()
            verify_borrowed()
        return {'relation': relation, 'server': child_record}
    except Exception:
        return {'relation': 'REFUSED', 'server': None}
