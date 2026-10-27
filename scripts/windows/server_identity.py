"""Read-only launcher/server binding. Records are private; refusals are constant."""
import ctypes
import math
import os
import sys
import time
from contextlib import ExitStack
from pathlib import Path

KERNEL_TIME_TOLERANCE = 0.000010
REFUSAL_STAGES = frozenset({'ROOT_POLICY','ROOT_SNAPSHOT','BORROWED','ROOT_PIN','CHILD_SNAPSHOT','CHILD_POLICY','CHILD_PIN','RECHECK','CLOSE','UNKNOWN'})
REFUSAL_REASONS = frozenset({'POLICY_REFUSED','RECORD_MISMATCH','UNAVAILABLE','OPEN_FAILED','PID_MISMATCH','CTIME_MISMATCH','NOT_LIVE','READ_FAILED','PARENT_MISMATCH','CREATION_WINDOW_REFUSED','IDENTITY_CHANGED','CLOSE_FAILED','CHECK_FAILED','ORPHAN_REFUSED','AMBIGUOUS','TRUSTED_COMMAND_REFUSED','CWD_MISMATCH','COMMAND_MISMATCH','ARGV0_MISMATCH','COMMAND_TAIL_MISMATCH'})


def validate_identity_refusal(value):
    if not isinstance(value,dict) or set(value)!={'stage','reason'} or not isinstance(value['stage'],str) or value['stage'] not in REFUSAL_STAGES or not isinstance(value['reason'],str) or value['reason'] not in REFUSAL_REASONS:
        raise ValueError('invalid identity refusal')
    return dict(value)


def refusal(stage, reason='CHECK_FAILED'):
    return {'stage':stage if isinstance(stage,str) and stage in REFUSAL_STAGES else 'UNKNOWN',
            'reason':reason if isinstance(reason,str) and reason in REFUSAL_REASONS else 'CHECK_FAILED'}


class IdentityRefused(Exception):
    def __init__(self, reason='CHECK_FAILED'):
        super().__init__('SERVER_IDENTITY_REFUSED')
        self.reason = reason if isinstance(reason,str) and reason in REFUSAL_REASONS else 'CHECK_FAILED'


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
            raise IdentityRefused('OPEN_FAILED')
        return handle

    def creation_handle(self, process):
        import psutil
        if not isinstance(process, psutil.Popen):
            return None
        # psutil.Popen forwards attributes absent on Process to its private
        # subprocess.Popen. _proc is the psutil platform object, not Popen.
        handle = process._handle
        if isinstance(handle, bool) or not handle or int(handle) <= 0:
            raise IdentityRefused('UNAVAILABLE')
        return int(handle)

    def identity(self, handle):
        pid = self.kernel.GetProcessId(handle)
        times = [self.FILETIME() for _ in range(4)]
        if not pid or not self.kernel.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            raise IdentityRefused('READ_FAILED')
        ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
        # Subtract the epoch before float conversion, preserving sub-microsecond precision.
        created = (ticks - 116444736000000000) / 10000000
        wait = self.kernel.WaitForSingleObject(handle, 0)
        if wait not in (0, 258):
            raise IdentityRefused('READ_FAILED')
        return pid, created, wait == 258

    def close(self, handle):
        if not self.kernel.CloseHandle(handle):
            raise IdentityRefused('CLOSE_FAILED')


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
        try:pid, created, alive = self.backend.identity(self.handle)
        except Exception:raise IdentityRefused('READ_FAILED') from None
        if not positive_pid(pid) or pid != self.pid:raise IdentityRefused('PID_MISMATCH')
        if not creation_time(created) or abs(created - self.created) > KERNEL_TIME_TOLERANCE:raise IdentityRefused('CTIME_MISMATCH')
        if type(alive) is not bool:raise IdentityRefused('READ_FAILED')
        if require_live and not alive:raise IdentityRefused('NOT_LIVE')
        self.alive = alive
        return self

    def __enter__(self):
        if not positive_pid(self.pid) or not creation_time(self.created):
            raise IdentityRefused()
        if self.backend is None:
            self.backend = WindowsBackend()
        try:
            try:self.handle = self.backend.open(self.pid)
            except Exception:raise IdentityRefused('OPEN_FAILED') from None
            return self.verify()
        except BaseException as error:
            if self.handle is not None:
                handle, self.handle = self.handle, None
                try:
                    self.backend.close(handle)
                except Exception:
                    pass
            if isinstance(error, Exception):
                raise IdentityRefused(error.reason if isinstance(error,IdentityRefused) else 'CHECK_FAILED') from None
            raise

    def __exit__(self, kind, value, traceback):
        handle, self.handle = self.handle, None
        if handle is not None:
            try:
                self.backend.close(handle)
            except Exception:
                # An existing refusal remains the primary branch. A close error
                # on an otherwise successful body still forbids acceptance.
                if kind is None:raise IdentityRefused('CLOSE_FAILED') from None


def redirector_authority(command, repo, runtime=None):
    """Resolve one venv target from the managed runtime, never from a candidate.

    CPython's Windows redirector uses pyvenv.cfg home/python.exe and preserves
    the command tail. Cross-check that target against the running venv.
    """
    runtime = sys if runtime is None else runtime
    try:
        venv = Path(repo).resolve() / '.venv-windows'
        managed = venv / 'Scripts' / 'python.exe'
        def absolute_file(value):
            path = Path(value)
            if not path.is_absolute() or not path.is_file():raise ValueError()
            return path.resolve()
        if not isinstance(command,list) or not command or command[0] != str(managed):raise ValueError()
        if absolute_file(runtime.executable) != managed or Path(runtime.prefix).resolve() != venv:raise ValueError()
        base_prefix = Path(runtime.base_prefix)
        if not base_prefix.is_absolute() or base_prefix.resolve() == venv:raise ValueError()
        base = absolute_file(runtime._base_executable)
        if base == managed or base.name.lower() != 'python.exe' or base.parent != base_prefix.resolve():raise ValueError()
        with (venv / 'pyvenv.cfg').open('rb') as stream:data = stream.read(8193)
        if len(data)>8192:raise ValueError()
        fields = {}
        for line in data.decode('utf-8').splitlines():
            key, equal, value = line.partition('=')
            key = key.strip().lower()
            if equal and key in ('home','executable'):
                if key in fields:raise ValueError()
                fields[key] = value.strip()
        home = Path(fields['home'])
        if not home.is_absolute() or home.resolve() != base_prefix.resolve():raise ValueError()
        target = home / 'python.exe'
        if absolute_file(target) != base:raise ValueError()
        if 'executable' in fields and absolute_file(fields['executable']) != base:raise ValueError()
        return {'managed':str(managed),'base':str(target),'command':[str(target),*command[1:]]}
    except Exception:raise IdentityRefused('TRUSTED_COMMAND_REFUSED') from None


def _snapshot(process, *, image=False):
    pid, created = process.pid, process.create_time()
    if not positive_pid(pid) or not creation_time(created):
        raise IdentityRefused()
    result = pid, created, process.cwd(), tuple(process.cmdline()), process.ppid()
    if image:
        executable=Path(process.exe())
        if not executable.is_absolute():raise IdentityRefused('ARGV0_MISMATCH')
        return (*result,str(executable.resolve()))
    return result


def bind_server(root, record, health_pid, repo, *, identify,
                process_factory=None, backend=None, clock=time.time, identify_reason=None,
                command_authority=None):
    """Return a fixed relation and a private server record (or None).

    identify (or identify_reason) must retain the lifecycle's exact ordered
    trusted command/time/cwd/argv predicates. Only the reported PID is opened.
    """
    def check_policy(process, private_record):
        if identify_reason is None:
            if not identify(process,private_record,repo):raise IdentityRefused('POLICY_REFUSED')
        else:
            reason=identify_reason(process,private_record,repo)
            if reason is not None:raise IdentityRefused(reason)
    current_stage='ROOT_POLICY'
    try:
        if not positive_pid(health_pid) or not isinstance(record, dict):
            raise IdentityRefused('POLICY_REFUSED')
        if not positive_pid(record['pid']) or not creation_time(record['created']) or not isinstance(record['command'], list) or not all(isinstance(arg, str) for arg in record['command']):
            raise IdentityRefused('RECORD_MISMATCH')
        check_policy(root,record)
        authority = command_authority(record['command'],repo) if command_authority is not None else None
        def snapshot(process):return _snapshot(process,image=authority is not None)
        def check_child(process, private_record):
            if authority is None:return check_policy(process,private_record)
            try:
                if not abs(process.create_time()-private_record['created']) < .01:raise IdentityRefused('CTIME_MISMATCH')
                if process.cwd()!=str(Path(repo).resolve()):raise IdentityRefused('CWD_MISMATCH')
                if process.cmdline()!=authority['command']:raise IdentityRefused('COMMAND_MISMATCH')
                image=Path(process.exe())
                if not image.is_absolute() or str(image.resolve())!=str(Path(authority['base']).resolve()):raise IdentityRefused('ARGV0_MISMATCH')
            except IdentityRefused:raise
            except Exception:raise IdentityRefused('READ_FAILED') from None
        current_stage='ROOT_SNAPSHOT'
        before = snapshot(root)
        if before[0] != record['pid'] or abs(before[1] - record['created']) > KERNEL_TIME_TOLERANCE:
            raise IdentityRefused('RECORD_MISMATCH')
        if before[2] != str(Path(repo).resolve()) or before[3] != tuple(record['command']):
            raise IdentityRefused('RECORD_MISMATCH')
        if authority is not None and before[5]!=authority['managed']:raise IdentityRefused('ARGV0_MISMATCH')
        current_stage='ROOT_PIN'
        if backend is None:
            backend = WindowsBackend()
        current_stage='BORROWED'
        try:borrowed = backend.creation_handle(root)
        except Exception:raise IdentityRefused('UNAVAILABLE') from None
        def verify_borrowed():
            if borrowed is not None:
                try:pid, created, alive = backend.identity(borrowed)
                except Exception:raise IdentityRefused('READ_FAILED') from None
                if not positive_pid(pid) or pid != before[0]:raise IdentityRefused('PID_MISMATCH')
                if not creation_time(created) or abs(created-record['created']) > KERNEL_TIME_TOLERANCE:raise IdentityRefused('CTIME_MISMATCH')
                if type(alive) is not bool:raise IdentityRefused('READ_FAILED')
                if alive is not True:raise IdentityRefused('NOT_LIVE')
        verify_borrowed()
        with ExitStack() as stack:
            current_stage='ROOT_PIN'
            root_pin = stack.enter_context(PinnedProcess(before[0], record['created'], backend))
            child_record = None
            if health_pid == before[0]:
                relation = 'ROOT'
                candidate, candidate_before, candidate_pin = root, before, root_pin
            else:
                current_stage='CHILD_SNAPSHOT'
                if process_factory is None:
                    import psutil
                    process_factory = psutil.Process
                candidate = process_factory(health_pid)
                candidate_before = snapshot(candidate)
                bound_at = clock()
                if not creation_time(bound_at) or candidate_before[0] != health_pid:
                    raise IdentityRefused('RECORD_MISMATCH')
                if candidate_before[4] != before[0]:raise IdentityRefused('PARENT_MISMATCH')
                if not before[1] <= candidate_before[1] <= min(bound_at, before[1] + 60):raise IdentityRefused('CREATION_WINDOW_REFUSED')
                current_stage='CHILD_POLICY'
                if candidate_before[2] != before[2]:raise IdentityRefused('CWD_MISMATCH')
                expected = tuple(authority['command']) if authority is not None else before[3]
                if candidate_before[3] != expected:
                    if not candidate_before[3]:raise IdentityRefused('COMMAND_MISMATCH')
                    if candidate_before[3][0] != expected[0]:raise IdentityRefused('ARGV0_MISMATCH')
                    raise IdentityRefused('COMMAND_TAIL_MISMATCH')
                child_record = {'pid': health_pid, 'created': candidate_before[1],
                                'command': list(expected), 'parent_pid': before[0],
                                'parent_created': record['created']}
                if authority is not None:child_record['launcher_command']=list(record['command']);child_record['base_executable']=authority['base']
                check_child(candidate,child_record)
                current_stage='CHILD_PIN'
                candidate_pin = stack.enter_context(PinnedProcess(health_pid, candidate_before[1], backend))
                relation = 'DIRECT_CHILD'
            current_stage='RECHECK'
            if snapshot(root) != before or snapshot(candidate) != candidate_before:
                raise IdentityRefused('IDENTITY_CHANGED')
            check_policy(root,record)
            if authority is not None and command_authority(record['command'],repo)!=authority:raise IdentityRefused('IDENTITY_CHANGED')
            if child_record is not None:check_child(candidate,child_record)
            current_stage='ROOT_PIN'
            root_pin.verify()
            current_stage='ROOT_PIN' if child_record is None else 'CHILD_PIN'
            candidate_pin.verify()
            current_stage='BORROWED'
            verify_borrowed()
            current_stage='CLOSE'
        return {'relation': relation, 'server': child_record}
    except Exception as error:
        reason=error.reason if isinstance(error,IdentityRefused) else 'CHECK_FAILED'
        return {'relation': 'REFUSED', 'server': None,'identity_refusal':refusal(current_stage,reason)}
