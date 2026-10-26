"""Unwired suspended initdb creation core; NO resume or password transmission.

Original OWNER/runtime-loading gates remain before native creation. Even after
all process checks this core leaves started=False: PGDATA source checks are
unaccepted natively and client authentication is still absent before resume.
No production factory/build wiring, credentials, SQL or filesystem writes.
Native calls below would require separate authorization; source checks do not
claim Windows loading or initialization. Deadlines are cooperative, not a
claim that synchronous CreateProcessAsUserW is forcibly cancellable.
"""
import ctypes as C
import math
import ntpath
import os
import re
import time
import weakref

from .fixed_directories import FixedDirectoryLease, _exclusive_entry, _exclusive_operation
from .endpoint_plan import _key_held
from .initdb_pipe_candidate import _OwnedInitdbPipe, _pwfile_name_held
from .processes import Command, PinnedExecutable, _ProcessState, ProcessRefused
from .restricted_startup_candidate import _OwnedStartup, _utf16, command_buffer, environment_buffer, _handle
from .restricted_token_candidate import _RestrictedPrimaryCandidate, _dacl_bytes
from .runtime_payload import RuntimePayloadPrerequisite
from .windows_process_handles import WindowsJobProcess
from .pgdata_candidate import _NewDataTarget, _path_held


class ProcessInformation(C.Structure):
    _fields_ = [('process', C.c_void_p), ('thread', C.c_void_p),
                ('pid', C.c_uint32), ('thread_id', C.c_uint32)]


def _need(ok):
    if not ok:
        raise ProcessRefused('RESTRICTED_INITDB_CANDIDATE_REFUSED')


def _arguments(data_directory, pipe_name):
    _need(type(data_directory) is str and ntpath.isabs(data_directory) and bool(ntpath.splitdrive(data_directory)[0])
          and 0 < len(data_directory) <= 2048 and not any(ord(c)<32 for c in data_directory))
    _need(type(pipe_name) is str and re.fullmatch(re.escape('\\\\.\\pipe\\ParkWeave-') +
          r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}-[0-9a-f]{32}', pipe_name) is not None)
    # Shape only, never pipe authority. Only the exact registered server below
    # can supply the actual value, never a caller-provided pathname.
    return ('-D', data_directory, '-U', 'postgres', '--pwfile', pipe_name,
            '--auth-local=scram-sha-256', '--auth-host=scram-sha-256',
            '--encoding=UTF8', '--locale=C')


class _FrozenInitdb:
    def __reduce__(self): raise TypeError('INITDB_COMMAND_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('INITDB_COMMAND_NOT_TRANSFERABLE')
    def __deepcopy__(self, memo): raise TypeError('INITDB_COMMAND_NOT_TRANSFERABLE')


_frozen_by_lease = weakref.WeakKeyDictionary()


@_exclusive_entry
def _freeze(lease, owner, server, specification, *, data_target):
    _need(type(lease) is FixedDirectoryLease and lease not in _frozen_by_lease)
    _need(type(owner) is _RestrictedPrimaryCandidate and type(server) is _OwnedInitdbPipe)
    _need(type(data_target) is _NewDataTarget)
    _need(type(specification) is Command and specification.model == 'WINDOWS_JOB'
          and specification.relative_executable == 'runtime/postgresql/bin/initdb.exe'
          and specification.arguments == specification.environment == ()
          and specification.stdio_contract == 'NONE')
    with owner._lock, server._lock:
        key = _key_held(lease)
        name = _pwfile_name_held(lease, server, owner)
        command = Command(specification.relative_executable, specification.sha256, specification.size,
                          _arguments(_path_held(lease, data_target), name), 'WINDOWS_JOB')
        lease._verify()
        _need(_key_held(lease) == key)
        frozen = object.__new__(_FrozenInitdb)
        frozen.lease, frozen.owner, frozen.server = lease, owner, server
        frozen.key, frozen.command = key, command
        frozen.data_target = data_target
        _frozen_by_lease[lease] = frozen
        return frozen


def native_restricted_initdb():
    raise ProcessRefused('NATIVE_RESTRICTED_INITDB_NOT_ACCEPTED')


@_exclusive_operation
def _create_held(lease, backend, group, register, environment, deadline):
    _need(type(lease) is FixedDirectoryLease and backend.lease is lease)
    with backend.owner._lock, backend.server._lock:
        return backend._native_create(group, register, environment, deadline)


class _RestrictedInitdbBackend(WindowsJobProcess):
    native_acceptance = False
    launch_ready = False
    scope = 'SUSPENDED_INITDB_CORE_PGDATA_CANDIDATE_NO_CLIENT_ACCEPTANCE'

    def __init__(self, frozen, payload, deadline):
        _need(type(frozen) is _FrozenInitdb and _frozen_by_lease.get(frozen.lease) is frozen)
        _need(type(payload) is RuntimePayloadPrerequisite and payload.lease is frozen.lease)
        _need(type(deadline) in (int, float) and math.isfinite(deadline))
        super().__init__()  # original native loaders, no process creation
        self.frozen, self.lease, self.owner, self.server = frozen, frozen.lease, frozen.owner, frozen.server
        self.payload, self.deadline = payload, deadline
        self._preflight_command = None
        self._adv = C.WinDLL('advapi32.dll', use_last_error=True, winmode=0x800)
        self._create_as_user = self._adv.CreateProcessAsUserW
        self._create_as_user.argtypes = [C.c_void_p]*5 + [C.c_int32, C.c_uint32] + [C.c_void_p]*3 + [C.POINTER(ProcessInformation)]
        self._create_as_user.restype = C.c_int32
        for name in ('GetThreadId', 'GetProcessIdOfThread'):
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = [C.c_void_p], C.c_uint32

    def _time(self, deadline):
        _need(time.monotonic() < min(deadline, self.deadline))

    def _native_result(self, group, ok, name):
        if not ok:
            group.resources.setdefault('restricted_native_errors', []).append((name, C.get_last_error()))
            _need(False)

    def preflight(self, command):
        _need(command is self.frozen.command and self._preflight_command is None)
        self._time(self.deadline)
        # Public lease.status in payload checks must run outside private gate.
        from scripts.windows.lifecycle import require_setup_readiness
        require_setup_readiness()
        self.payload.require_for_cluster(self.lease, self.deadline)
        self._preflight_command = command

    def create(self, group, register, env, deadline):
        _need(type(deadline) in (int, float) and math.isfinite(deadline))
        _create_held(self.lease, self, group, register, env, min(deadline, self.deadline))

    def _fresh(self, group, deadline):
        self._time(deadline)
        _need(type(group) is _ProcessState and type(group.executable) is PinnedExecutable
              and group.command is self.frozen.command and self._preflight_command is group.command
              and group.executable.command is group.command and group.executable.lease is self.lease)
        _need(_frozen_by_lease.get(self.lease) is self.frozen and _key_held(self.lease) == self.frozen.key)
        name = _pwfile_name_held(self.lease, self.server, self.owner)
        _need(group.command.arguments == _arguments(_path_held(self.lease, self.frozen.data_target), name))
        group.executable.verify()
        _need(_handle(self.owner._derived))  # NULL must never select caller token

    def _child_token(self, group):
        r, token = group.resources, C.c_void_p()
        entry, primary, cleanup = None, None, None
        try:
            ok = self.owner._adv.OpenProcessToken(r['process'], 8, C.byref(token))
            if ok and _handle(token.value):
                entry = dict(handle=token.value, close_attempted=False)
                r.setdefault('child_query_tokens', []).append(entry)
            self._native_result(group, ok, 'OpenProcessToken_child')
            if not _handle(token.value):
                r.setdefault('stdio_close_unknown', []).append(('INVALID_CHILD_TOKEN_RESULT', token))
                _need(False)
            _need(self.owner._query(token) == self.owner._restricted_snapshot)
            buffer, used = C.create_string_buffer(65536), C.c_uint32()
            self._native_result(group, self.owner._adv.GetTokenInformation(
                token, 6, buffer, C.sizeof(buffer), C.byref(used)), 'GetTokenInformation_child_DACL')
            _need(_dacl_bytes(buffer, used.value) == self.owner._prepared_dacl)
        except BaseException as error:
            primary = error
        finally:
            if entry is not None:
                entry['close_attempted'] = True
                try:
                    self.original.close(entry['handle'])
                    entry['closed'] = True
                except BaseException as error:
                    cleanup = error
                    r.setdefault('stdio_close_unknown', []).append(('CHILD_QUERY_TOKEN', entry))
        if primary is not None or cleanup is not None:
            raise BaseExceptionGroup('RESTRICTED_CHILD_TOKEN_UNKNOWN',
                                     [x for x in (primary, cleanup) if x is not None])

    def _native_create(self, group, register, environment, deadline):
        self._fresh(group, deadline)
        _need(self.server._claimed_group is None)
        self.server._claimed_group = group  # consume before first native attempt
        r, backend = group.resources, self.original
        from scripts.windows_ci.owned_job import ExtendedLimit
        job = backend.kernel.CreateJobObjectW(None, None)
        self._native_result(group, job, 'CreateJobObjectW')
        _need(_handle(job))
        r['job'] = job
        register(group)  # may reenter owner.close/pipe.close; freshcheck below
        _need(group.registration == 'ACKNOWLEDGED')
        limits = ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x2000
        self._native_result(group, backend.kernel.SetInformationJobObject(
            r['job'], 9, C.byref(limits), C.sizeof(limits)), 'SetInformationJobObject')
        startup, primary, cleanup = None, None, []
        try:
            startup = _OwnedStartup()
            r['restricted_startup'] = startup  # retain partial prepare failures
            with open(os.devnull, 'r+b', buffering=0) as null:
                handle = backend.crt.get_osfhandle(null.fileno())
                startup.prepare((handle, handle, handle))
                command = command_buffer(group.executable.path, group.command.arguments)
                application = _utf16(group.executable.path + '\0')
                cwd = _utf16(group.executable.root_path + '\0')
                environment_buffer(environment)  # ordinary OS-only contract first
                self._fresh(group, deadline)  # after external registration callback
                _need(self.server._claimed_group is group and startup.prepared)
                # This sole dedicated source path follows actual native token
                # and pipe checks. Ordinary environment_buffer rejects this key.
                values = {**environment, 'PG_RESTRICT_EXEC': '1'}
                env = _utf16('\0'.join(k+'='+v for k,v in sorted(values.items(), key=lambda x:x[0].lower()))+'\0\0')
                info = ProcessInformation()
                ok = self._create_as_user(self.owner._derived, application, command, None, None,
                                          True, 0x4|0x400|0x80000, env, cwd, C.byref(startup.info), C.byref(info))
                if ok:
                    if _handle(info.process): r['process'] = info.process
                    if _handle(info.thread) and info.thread != info.process: r['thread'] = info.thread
                    r.update(pid=info.pid, restricted_thread_id=info.thread_id, bound=False)
                    if not ('process' in r and 'thread' in r and info.pid and info.thread_id):
                        r.setdefault('stdio_close_unknown', []).append(('INVALID_SUCCESS_PROCESS_INFORMATION', info))
                self._native_result(group, ok, 'CreateProcessAsUserW')
                _need('process' in r and 'thread' in r and info.pid and info.thread_id)
            r['birth'] = self.birth(r['process'])
            _need(r['birth'][0] == r['pid'])
            thread_id = self.kernel.GetThreadId(r['thread'])
            self._native_result(group, thread_id, 'GetThreadId')
            _need(thread_id == r['restricted_thread_id'])
            thread_pid = self.kernel.GetProcessIdOfThread(r['thread'])
            self._native_result(group, thread_pid, 'GetProcessIdOfThread')
            _need(thread_pid == r['pid'])
            image, length = C.create_unicode_buffer(4096), C.c_uint32(4096)
            self._native_result(group, self.image(r['process'], 1, image, C.byref(length)), 'QueryFullProcessImageNameW')
            _need(0 < length.value < 4096)
            _need(image.value.casefold() == group.executable.native_path.casefold())
            group.executable.verify()
            self._child_token(group)
            backend.bind(r['job'], r['process'], r['pid'])
            r['bound'] = True
            _need(self.birth(r['process']) == r['birth'])
            self._child_token(group)
            self._fresh(group, deadline)
            _need(not group.started)
            group.target_image_observed = True
            r['restricted_stage'] = 'VERIFIED_SUSPENDED_NO_DATA_TARGET_OR_CLIENT_ACCEPTANCE'
        except BaseException as error:
            primary = error
        finally:
            if startup is not None:
                try: startup.close()
                except BaseException as error: cleanup.append(error)
                if startup.cleanup_errors:
                    r.setdefault('stdio_close_unknown', []).append(('RESTRICTED_STARTUP', startup))
        if primary is not None or cleanup:
            raise BaseExceptionGroup('RESTRICTED_CREATE_OR_CLEANUP_UNKNOWN',
                                     ([primary] if primary is not None else []) + cleanup)

    def close_observed(self, group):
        errors = []
        try: super().close_observed(group)
        except BaseException as error: errors.append(error)
        if self.server._claimed_group is group:
            try: self.server.close()
            except BaseException as error:
                group.resources.setdefault('stdio_close_unknown', []).append(('BOOTSTRAP_PIPE', self.server))
                errors.append(error)
            if self.server.cleanup_errors:
                group.resources.setdefault('stdio_close_unknown', []).append(('BOOTSTRAP_PIPE_RELEASE_UNKNOWN', self.server))
                errors.append(ProcessRefused('OWNED_BOOTSTRAP_PIPE_RELEASE_UNKNOWN'))
        if errors: raise BaseExceptionGroup('RESTRICTED_PROCESS_CLOSE_UNKNOWN', errors)
