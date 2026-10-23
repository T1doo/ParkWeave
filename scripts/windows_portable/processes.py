"""Private fixed-command process capabilities, not an activated PG bootstrap.

Linux is explicitly EXACT_SINGLE_PROCESS_ELF, not a process-tree sandbox.
Windows uses the original suspended Job backend and exact creation handles.
No PID discovery, external kill, new credentials or permission changes.
"""
from dataclasses import dataclass, field
import hashlib
import math
import os
from pathlib import Path
from types import MappingProxyType
import select
import signal
import stat
import threading
import time

from .payload import safe_name


class ProcessRefused(RuntimeError):
    pass


@dataclass(frozen=True, repr=False)
class Command:
    relative_executable: str
    sha256: str
    size: int
    arguments: tuple[str, ...] = ()
    model: str = 'SINGLE_PROCESS_ELF'

    def __post_init__(self):
        import re
        safe_name(self.relative_executable)
        if (type(self.sha256) is not str or not re.fullmatch('[0-9a-f]{64}', self.sha256) or type(self.size) is not int
                or not 0 < self.size <= 64 * 1024 * 1024 or type(self.arguments) is not tuple
                or len(self.arguments) > 32 or any(type(v) is not str or '\x00' in v or len(v) > 2048 for v in self.arguments)
                or sum(len(v) for v in self.arguments) > 8192
                or self.model not in ('SINGLE_PROCESS_ELF', 'WINDOWS_JOB')):
            raise ProcessRefused('FIXED_PRIVATE_COMMAND_REQUIRED')


class PinnedExecutable:
    def __init__(self, lease, command):
        self.lease, self.command = lease, command
        self.handles, self.file = [], None
        self.directory_links = []
        self.path = str(Path(lease.fs.base) / Path(lease.fs.chain[-1][1]) / command.relative_executable) if os.name == 'posix' else None
        lease._verify()
        if os.name != 'posix':
            from .windows_process_handles import pin_executable
            pin_executable(self)
            return
        fd = lease.fs.root
        try:
            parts = command.relative_executable.split('/')
            for part in parts[:-1]:
                parent = fd
                fd = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=parent)
                self.handles.append(fd)
                self.directory_links.append((parent, part, fd))
                meta = os.fstat(fd)
                if meta.st_uid != os.geteuid() or meta.st_mode & 0o077: raise ProcessRefused('PRIVATE_EXEC_DIRECTORY_REQUIRED')
            self.file = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            self.handles.append(self.file)
            self.parent, self.basename = fd, parts[-1]
            self.original = os.fstat(self.file)
            self.verify()
        except BaseException as primary:
            try: self.close()
            except BaseException as cleanup: raise BaseExceptionGroup('EXEC_PIN_FAILED', [primary, cleanup]) from primary
            raise

    def verify(self):
        self.lease._verify()
        if os.name != 'posix':
            from .windows_process_handles import verify_executable
            return verify_executable(self)
        if self.file is None: raise ProcessRefused('EXEC_HANDLE_CONSUMED')
        for parent, name, held in self.directory_links:
            actual, current = os.fstat(held), os.stat(name, dir_fd=parent, follow_symlinks=False)
            if (not stat.S_ISDIR(actual.st_mode) or actual.st_uid != os.geteuid() or actual.st_mode & 0o077
                    or not stat.S_ISDIR(current.st_mode) or
                    (actual.st_dev, actual.st_ino) != (current.st_dev, current.st_ino)):
                raise ProcessRefused('EXEC_DIRECTORY_IDENTITY_CHANGED')
        info = os.fstat(self.file)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or not info.st_mode & stat.S_IXUSR or info.st_size != self.command.size):
            raise ProcessRefused('PRIVATE_EXECUTABLE_REQUIRED')
        current = os.stat(self.basename, dir_fd=self.parent, follow_symlinks=False)
        signature = lambda row: (row.st_dev, row.st_ino, row.st_mode, row.st_nlink, row.st_size, row.st_uid, row.st_mtime_ns, row.st_ctime_ns)
        if signature(info) != signature(self.original) or signature(current) != signature(info):
            raise ProcessRefused('EXEC_IDENTITY_CHANGED')
        digest = hashlib.sha256(); os.lseek(self.file, 0, os.SEEK_SET)
        first = os.read(self.file, min(info.st_size, 1024 * 1024)); digest.update(first)
        if self.command.model == 'SINGLE_PROCESS_ELF' and first[:4] != b'\x7fELF':
            raise ProcessRefused('SINGLE_PROCESS_ELF_REQUIRED')
        count = len(first)
        while count < info.st_size:
            raw = os.read(self.file, min(1024 * 1024, info.st_size - count))
            if not raw: raise ProcessRefused('EXEC_SHORT_READ')
            count += len(raw); digest.update(raw)
        os.lseek(self.file, 0, os.SEEK_SET)
        if digest.hexdigest() != self.command.sha256 or signature(os.fstat(self.file)) != signature(info):
            raise ProcessRefused('EXEC_HASH_REFUSED')

    def close(self):
        errors, handles = [], list(reversed(self.handles))
        self.handles.clear(); self.file = None
        for handle in handles:
            try:
                if os.name == 'posix': os.close(handle)
                else: self.lease.fs.api.close(handle)
            except BaseException as error: errors.append(error)
        if errors: raise BaseExceptionGroup('EXEC_CLOSE_UNKNOWN', errors)


@dataclass(eq=False, repr=False)
class _ProcessState:
    command: Command
    executable: PinnedExecutable
    resources: dict = field(default_factory=dict, repr=False)
    creating: bool = True
    exec_error_pipe_closed: bool = False
    target_image_observed: bool = False
    started: bool = False
    registration: str = 'NOT_CALLED'
    attempted_stop: bool = False
    stopped: bool = False
    errors: list = field(default_factory=list, repr=False)
    returncode: int | None = None

class OwnedGroup:
    """Opaque invocation token; no raw process, executable or mutable state."""
    __slots__ = ()

    def __reduce__(self): raise TypeError('process capabilities cannot be serialized')


def _proc_identity(pid):
    with open(f'/proc/{pid}/stat', 'r', encoding='ascii') as stream:
        raw = stream.read(4096)
    fields = raw[raw.rfind(')') + 2:].split()
    return (int(fields[1]), int(fields[3]), int(fields[19]))  # ppid/session/birth ticks


class LinuxSingleProcess:
    scope = 'EXACT_SINGLE_PROCESS_ELF_NOT_TREE'

    def _exec(self, group, env):
        os.execve(group.executable.file, [group.executable.path, *group.command.arguments], env)

    def preflight(self, command):
        if (os.name != 'posix' or not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal')
                or not hasattr(os, 'P_PIDFD') or os.execve not in os.supports_fd
                or threading.active_count() != 1 or threading.current_thread() is not threading.main_thread()
                or len(os.listdir('/proc/self/task')) != 1
                or signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL
                or command.model != 'SINGLE_PROCESS_ELF'):
            raise ProcessRefused('SINGLE_THREAD_PIDFD_FDEXEC_PROFILE_REQUIRED')
        # This reference environment is authorized for harmless probes, not a
        # generic Linux/PG tree launcher. Match the existing OS sleep/true bytes,
        # execute only their private copies, and accept no shell/script args.
        names = {'runtime/probe/sleep': 'sleep', 'runtime/probe/true': 'true'}
        program = names.get(command.relative_executable)
        if program is None: raise ProcessRefused('LINUX_HARMLESS_PROBE_PROFILE_REQUIRED')
        if program == 'true' and command.arguments:
            raise ProcessRefused('LINUX_HARMLESS_PROBE_PROFILE_REQUIRED')
        if program == 'sleep':
            try: duration = float(command.arguments[0]) if len(command.arguments) == 1 else 0
            except ValueError: duration = 0
            if not math.isfinite(duration) or not 0 < duration <= 5:
                raise ProcessRefused('LINUX_BOUNDED_SLEEP_REQUIRED')
        reference = Path('/usr/bin') / program
        raw = reference.read_bytes()
        if len(raw) != command.size or hashlib.sha256(raw).hexdigest() != command.sha256:
            raise ProcessRefused('LINUX_EXISTING_PROBE_BYTES_REQUIRED')
        test = os.pidfd_open(os.getpid(), 0); os.close(test)

    def create(self, group, register, env, deadline):
        if time.monotonic() >= deadline: raise ProcessRefused('STARTUP_DEADLINE')
        r = group.resources
        ready_r, ready_w = os.pipe2(os.O_CLOEXEC)
        r.update(ready_r=ready_r, ready_w=ready_w)
        go_r, go_w = os.pipe2(os.O_CLOEXEC)
        r.update(go_r=go_r, go_w=go_w)
        exec_r, exec_w = os.pipe2(os.O_CLOEXEC)
        r.update(exec_r=exec_r, exec_w=exec_w)
        pid = os.fork()
        if pid == 0:
            try:
                for fd in (ready_r, go_w, exec_r): os.close(fd)
                signal.signal(signal.SIGTERM, signal.SIG_DFL)
                os.setsid()
                os.write(ready_w, b'R'); os.close(ready_w)
                if os.read(go_r, 1) != b'G': os._exit(126)
                os.close(go_r)
                os.fchdir(group.executable.lease.fs.root)
                with open(os.devnull, 'r+b', buffering=0) as null:
                    for fd in (0, 1, 2): os.dup2(null.fileno(), fd)
                self._exec(group, env)
            except BaseException as error:
                # Fixed category/errno only, never exception text/argv/env.
                try: os.write(exec_w, str(getattr(error, 'errno', 0) or 0).encode('ascii')[:12])
                finally: os._exit(127)
        r['pid'] = pid
        for key in ('ready_w', 'go_r', 'exec_w'): os.close(r.pop(key))
        # Pin the exact returned, unreaped child before any executable GO.
        r['pidfd'] = os.pidfd_open(pid, 0)
        if not select.select([ready_r], [], [], max(0, deadline - time.monotonic()))[0] or os.read(ready_r, 1) != b'R':
            raise ProcessRefused('CHILD_GATE_NOT_READY')
        before = _proc_identity(pid)
        if before[:2] != (os.getpid(), pid): raise ProcessRefused('CHILD_BIRTH_REFUSED')
        r['birth'] = before
        register(group)
        if time.monotonic() >= deadline: raise ProcessRefused('STARTUP_DEADLINE')
        group.executable.verify()  # Register cannot replace a pinned executable silently.
        if _proc_identity(pid) != before: raise ProcessRefused('CHILD_BIRTH_CHANGED')
        if time.monotonic() >= deadline: raise ProcessRefused('STARTUP_DEADLINE')
        os.write(go_w, b'G'); os.close(r.pop('go_w'))
        # CLOEXEC EOF is success; an error payload is explicitly not success.
        if not select.select([exec_r], [], [], max(0, deadline - time.monotonic()))[0]:
            raise ProcessRefused('EXEC_RESULT_UNKNOWN')
        error = os.read(exec_r, 13)
        if error:
            r['exec_errno'] = int(error) if error.isdigit() else None
            raise ProcessRefused('EXEC_FAILED')
        group.exec_error_pipe_closed = True
        # EOF only means no exec error payload was received. A signal before
        # exec closes the same pipe. Independently observe the pinned target,
        # never infer it from a quick exit (including status zero).
        code = self.observe(group, time.monotonic())
        if code is not None and code != 0:
            raise ProcessRefused('TARGET_EXITED_BEFORE_IMAGE_OBSERVATION')
        if code is None:
            try:
                image = os.stat(f'/proc/{pid}/exe')
                pinned = os.fstat(group.executable.file)
                group.target_image_observed = ((image.st_dev, image.st_ino) == (pinned.st_dev, pinned.st_ino)
                    and _proc_identity(pid) == before)
            except (FileNotFoundError, ProcessLookupError):
                pass  # Target vanished; no historical success is manufactured.
        group.started = group.target_image_observed
        for key in ('ready_r', 'exec_r'): os.close(r.pop(key))

    def observe(self, group, deadline):
        r = group.resources
        if r.get('reaped'): return group.returncode
        if 'pidfd' not in r:
            # No signal authority: EOF the gate and only wait for this exact
            # unreaped child returned by our fork. Never send by numeric PID.
            if 'pid' not in r: return 0
            while time.monotonic() < deadline:
                result = os.waitid(os.P_PID, r['pid'], os.WEXITED | os.WNOHANG | os.WNOWAIT)
                if result is not None:
                    return result.si_status if result.si_code == os.CLD_EXITED else -result.si_status
                time.sleep(min(.01, max(0, deadline - time.monotonic())))
            return None
        if not select.select([r['pidfd']], [], [], max(0, deadline - time.monotonic()))[0]: return None
        result = os.waitid(os.P_PIDFD, r['pidfd'], os.WEXITED | os.WNOHANG | os.WNOWAIT)
        if result is None: return None
        return result.si_status if result.si_code == os.CLD_EXITED else -result.si_status

    def stop(self, group, deadline):
        r = group.resources
        if 'go_w' in r: os.close(r.pop('go_w'))  # Abort pre-GO without executing the target.
        if 'pid' not in r: return True
        code = self.observe(group, time.monotonic())
        if code is None and 'pidfd' in r:
            try: signal.pidfd_send_signal(r['pidfd'], signal.SIGTERM, None, 0)
            except ProcessLookupError: code = self.observe(group, deadline)
            else: code = self.observe(group, min(deadline, time.monotonic() + .2))
            if code is None and time.monotonic() < deadline:
                try: signal.pidfd_send_signal(r['pidfd'], signal.SIGKILL, None, 0)
                except ProcessLookupError: pass  # Read same retained handle; never change target.
                code = self.observe(group, deadline)
        elif code is None:
            code = self.observe(group, deadline)
        if code is None: return False  # Keep last observation capability.
        group.returncode = code
        if 'pidfd' in r:
            reaped = os.waitid(os.P_PIDFD, r['pidfd'], os.WEXITED | os.WNOHANG)
        else:
            reaped = os.waitid(os.P_PID, r['pid'], os.WEXITED | os.WNOHANG)
        if reaped is None: return False
        r['reaped'] = True
        return True

    def close_observed(self, group):
        r = group.resources; errors = []
        for key in ('go_w', 'go_r', 'ready_r', 'ready_w', 'exec_r', 'exec_w', 'pidfd'):
            fd = r.pop(key, None)  # Consume BEFORE close; never retry unknown fd.
            if fd is not None:
                try: os.close(fd)
                except BaseException as error: errors.append(error)
        if errors: raise BaseExceptionGroup('OWNED_PROCESS_CLOSE_UNKNOWN', errors)


class PrivateProcessAdapter:
    """Trusted internal consumer of an immutable command catalogue and lease.

    Commands are frozen at construction; launch takes an identifier only, not
    arbitrary executable/argv/env. No CLI/HTTP hook or PG readiness adapter is
    provided here. Windows Job containment remains native NOT_RUN.
    """
    def __init__(self, lease, commands, *, startup_seconds=2, stop_seconds=3, _backend=None):
        if (not commands or len(commands) > 8 or any(type(k) is not str or not k.isascii() or
                not k.isidentifier() or len(k) > 40 or type(v) is not Command for k,v in commands.items())
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 5
                       for v in (startup_seconds, stop_seconds))):
            raise ProcessRefused('BOUNDED_FIXED_CATALOGUE_REQUIRED')
        self.lease, self.commands = lease, MappingProxyType(dict(commands))
        self.startup_seconds, self.stop_seconds = startup_seconds, stop_seconds
        if _backend is None:
            if os.name == 'posix': _backend = LinuxSingleProcess()
            elif os.name == 'nt':
                from .windows_process_handles import WindowsJobProcess
                _backend = WindowsJobProcess()
            else: raise ProcessRefused('SUPPORTED_NATIVE_PROCESS_BACKEND_REQUIRED')
        self.backend, self._issued, self.unknown = _backend, {}, False

    def _group(self, group):
        entry = self._issued.get(id(group))
        if type(group) is not OwnedGroup or entry is None or entry[0] is not group:
            raise ProcessRefused('THIS_INVOCATION_CAPABILITY_REQUIRED')
        return entry[1]

    def launch(self, name, register):
        if self.unknown or len(self._issued) >= 8 or type(name) is not str or name not in self.commands or not callable(register):
            raise ProcessRefused('PROCESS_LAUNCH_REFUSED')
        phase = self.lease.status()
        if phase not in ('CLUSTER', 'APPLICATION') and not (phase == 'NEW' and isinstance(self.backend, LinuxSingleProcess)):
            raise ProcessRefused('ACTIVE_LEASE_LAUNCH_PHASE_REQUIRED')
        command = self.commands[name]
        self.backend.preflight(command)
        executable = PinnedExecutable(self.lease, command)
        group, token = _ProcessState(command, executable), OwnedGroup()
        self._issued[id(token)] = (token, group)
        registered = False
        def register_once(capability):
            nonlocal registered
            if registered or capability is not group: raise ProcessRefused('CREATION_REGISTRATION_REFUSED')
            registered = True; group.registration = 'CALLED'; register(token)
            group.registration = 'ACKNOWLEDGED'
        # No inherited secrets/provider/proxy/loader/PYTHONPATH. Temporary output
        # and cwd are explicitly inside this held private directory.
        try:
            from parkweave.process_env import minimal_environment
            env = minimal_environment(os.environ)
            env['PATH'] = str(Path(executable.path).parent)
            for key in ('TEMP', 'TMP', 'TMPDIR'): env[key] = str(Path(executable.path).parents[len(command.relative_executable.split('/')) - 1])
            self.backend.create(group, register_once, env, time.monotonic() + self.startup_seconds)
            if not registered: raise ProcessRefused('CREATION_NOT_REGISTERED')
            group.creating = False
            return token
        except BaseException as primary:
            group.creating = False
            group.errors.append(('START', primary))
            try:
                if not self.stop_owned(token): group.errors.append(('START_CLEANUP', ProcessRefused('EXIT_UNKNOWN')))
            except BaseException as cleanup: group.errors.append(('START_CLEANUP', cleanup))
            raise ProcessStartFailure(primary, token) from primary

    def observe(self, group, seconds=0):
        group = self._group(group)
        if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 0 <= seconds <= 5:
            raise ProcessRefused('BOUNDED_OBSERVATION_REQUIRED')
        if group.stopped: return group.returncode
        return self.backend.observe(group, time.monotonic() + seconds)

    def describe(self, group):
        group = self._group(group)
        from .controller import exception_chain
        return dict(scope=self.backend.scope, registration=group.registration,
                    exec_error_pipe='ERROR_RECEIVED' if 'exec_errno' in group.resources else 'NO_ERROR_RECEIVED' if group.exec_error_pipe_closed else 'UNKNOWN',
                    target_image='OBSERVED' if group.target_image_observed else 'NOT_OBSERVED',
                    resume_acknowledged=group.started if self.backend.scope.startswith('EXACT_CREATED_WINDOWS') else False,
                    business_readiness='NOT_CHECKED', stopped_confirmed=group.stopped,
                    outcome='UNKNOWN' if self.unknown else 'FAILED' if group.errors else 'OBSERVED',
                    returncode=group.returncode,
                    errors=[dict(phase=phase, types=[type(e).__name__[:64] for e in exception_chain(error)[:16]])
                            for phase,error in group.errors[:16]])

    def stop_owned(self, group):
        group = self._group(group)
        if group.creating: raise ProcessRefused('CREATION_IN_PROGRESS')
        if group.attempted_stop: return group.stopped
        group.attempted_stop = True
        try:
            confirmed = self.backend.stop(group, time.monotonic() + self.stop_seconds)
            if confirmed:
                self.backend.close_observed(group)
                group.executable.close()
                group.stopped = True
                return True
            group.errors.append(('EXIT', ProcessRefused('OWNED_EXIT_UNKNOWN')))
        except BaseException as error: group.errors.append(('STOP', error))
        self.unknown = True
        # Preserve last process observation capability on unknown exit. The
        # controller also sees False and must not mark the installation stopped.
        try: self.lease.mark_unknown('RUNNING')
        except BaseException as error: group.errors.append(('JOURNAL_UNKNOWN', error))
        return False


class ProcessStartFailure(ProcessRefused):
    def __init__(self, primary, group):
        self.primary, self.group = primary, group
        super().__init__('PRIVATE_PROCESS_START_FAILED')
