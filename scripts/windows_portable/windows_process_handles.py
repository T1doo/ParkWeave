"""Windows Job process adapter; native execution NOT_RUN, no entry wiring.

Uses the established owned_job creation/binding protocol, retaining creation
handles even if stdio cleanup or pre-Job validation fails. No OpenProcess,
privilege adjustment, inherited Job handle, breakaway or uncontained fallback.
"""
import ctypes as C
import hashlib
import os
from pathlib import Path
import subprocess
import time

from .processes import ProcessRefused


def pin_executable(pin):
    from parkweave.windows_files import private_acl
    api, root = pin.lease.fs.api, pin.lease.fs.root
    pin.directory_bindings = []
    try:
        parts = pin.command.relative_executable.split('/')
        for part in parts[:-1]:
            root = api.open_relative(root, part, False); pin.handles.append(root)
            info = api.info(root)
            if (not info.attributes & 0x10 or info.attributes & (0x400 | 0x40 | 0x1000 | 0x40000 | 0x400000)
                    or info.volume != pin.lease.fs.volume): raise ProcessRefused('PRIVATE_EXEC_DIRECTORY_REQUIRED')
            private_acl(api.security(root), api.user_sid())
            pin.directory_bindings.append((root, info, api.descriptor(root)))
        pin.file = api.open_relative(root, parts[-1], True); pin.handles.append(pin.file)
        pin.original, pin.descriptor = api.info(pin.file), api.descriptor(pin.file)
        pin.path = api.final_path(pin.file)
        pin.root_path = api.final_path(pin.lease.fs.root)
        pin.native_path = native_file_path(api, pin.file)
        verify_executable(pin)
    except BaseException as primary:
        try: pin.close()
        except BaseException as cleanup: raise BaseExceptionGroup('NATIVE_EXEC_PIN_FAILED', [primary, cleanup]) from primary
        raise


def native_file_path(api, handle):
    buffer = C.create_unicode_buffer(4096)
    length = api.getpath(handle, buffer, len(buffer), 2)  # VOLUME_NAME_NT.
    if not 0 < length < len(buffer): raise ProcessRefused('NATIVE_IMAGE_PATH_REFUSED')
    return buffer.value


def verify_executable(pin):
    from parkweave.windows_files import private_acl
    api = pin.lease.fs.api; info = api.info(pin.file)
    for handle, before, descriptor in pin.directory_bindings:
        if api.info(handle) != before or api.descriptor(handle) != descriptor:
            raise ProcessRefused('NATIVE_EXEC_DIRECTORY_CHANGED')
        private_acl(api.security(handle), api.user_sid())
    if (info != pin.original or api.descriptor(pin.file) != pin.descriptor
            or info.attributes & (0x10 | 0x400 | 0x40 | 0x1000 | 0x40000 | 0x400000)
            or info.links != 1 or info.volume != pin.lease.fs.volume or info.size != pin.command.size
            or api.final_path(pin.file) != pin.path or native_file_path(api, pin.file) != pin.native_path):
        raise ProcessRefused('NATIVE_EXEC_BINDING_REFUSED')
    private_acl(api.security(pin.file), api.user_sid())
    # Explicitly rewind the held handle for GO-time revalidation.
    from ctypes import wintypes
    rewind = api.readonly.k.SetFilePointerEx
    rewind.argtypes, rewind.restype = [C.c_void_p, C.c_int64, C.c_void_p, wintypes.DWORD], C.c_int32
    api.need(rewind(pin.file, 0, None, 0))
    digest, size, first = hashlib.sha256(), 0, b''
    while size < info.size:
        raw = api.read(pin.file, min(1024 * 1024, info.size - size))
        if not raw: raise ProcessRefused('NATIVE_EXEC_SHORT_READ')
        if not size: first = raw
        size += len(raw); digest.update(raw)
    if (getattr(pin, '_image_required', True) and first[:2] != b'MZ' or
            digest.hexdigest() != pin.command.sha256 or api.info(pin.file) != info):
        raise ProcessRefused('NATIVE_EXEC_HASH_REFUSED')
    # Loader/DLL closure remains a separate unaccepted product prerequisite.


class FileTime(C.Structure):
    _fields_ = [('low', C.c_uint32), ('high', C.c_uint32)]


class WindowsJobProcess:
    scope = 'EXACT_CREATED_WINDOWS_JOB_TREE_NOT_NATIVE_ACCEPTED'

    def __init__(self):
        if os.name != 'nt': raise ProcessRefused('NATIVE_WINDOWS_REQUIRED')
        from scripts.windows_ci.owned_job import WindowsBackend
        self.original = WindowsBackend()
        self.kernel = C.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
        self.times = self.kernel.GetProcessTimes
        self.times.argtypes, self.times.restype = [C.c_void_p] + [C.POINTER(FileTime)] * 4, C.c_int32
        self.image = self.kernel.QueryFullProcessImageNameW
        self.image.argtypes, self.image.restype = [C.c_void_p, C.c_uint32, C.c_wchar_p, C.POINTER(C.c_uint32)], C.c_int32

    def preflight(self, command):
        if command.model != 'WINDOWS_JOB': raise ProcessRefused('WINDOWS_JOB_PROFILE_REQUIRED')
        if command.stdio_contract=='PIPE_PROBE_V1':
            from .isolated_pipe import HELPER
            from parkweave.runtime_readiness import challenge
            if len(command.arguments)!=6 or command.arguments[:4]!=('-I','-B','-c',HELPER) or command.arguments[4] not in ('read','go'):
                raise ProcessRefused('FROZEN_HELPER_REQUIRED')
            challenge(command.arguments[5])

    def birth(self, process):
        created, exited, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
        if not self.times(process, C.byref(created), C.byref(exited), C.byref(kernel), C.byref(user)):
            raise ProcessRefused('CREATION_TIME_REFUSED')
        pid = self.original.kernel.GetProcessId(process)
        ticks = (created.high << 32) | created.low
        if not pid or not ticks: raise ProcessRefused('CREATION_IDENTITY_REFUSED')
        return pid, ticks

    def create(self, group, register, env, deadline):
        r, backend = group.resources, self.original
        from scripts.windows_ci.owned_job import ExtendedLimit
        job = backend.kernel.CreateJobObjectW(None, None)  # Non-inheritable, unnamed.
        if not job: raise ProcessRefused('JOB_CREATE_REFUSED')
        r['job'] = job  # Register BEFORE fallible configuration/cleanup, not on return.
        register(group)
        limits = ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE only.
        if not backend.kernel.SetInformationJobObject(job, 9, C.byref(limits), C.sizeof(limits)):
            raise ProcessRefused('JOB_LIMIT_REFUSED')
        if time.monotonic() >= deadline: raise ProcessRefused('NATIVE_START_DEADLINE')
        duplicates, primary, cleanup = [], None, []
        with open(os.devnull, 'r+b', buffering=0) as null:
            try:
                win = backend.win
                fds = [null.fileno()] * 3
                if getattr(group.command,'stdio_contract','NONE') == 'WORKER_READINESS_V1':
                    r['worker_go_r'],r['worker_go_w'] = os.pipe()
                    r['worker_ready_r'],r['worker_ready_w'] = os.pipe()
                    fds = [r['worker_go_r'],r['worker_ready_w'],null.fileno()]
                if getattr(group.command,'stdio_contract','NONE')=='PIPE_PROBE_V1':
                    fds=[r['pipe_borrowed'],r['pipe_result_w'],null.fileno()]
                for fd in fds:
                    duplicates.append(win.DuplicateHandle(win.GetCurrentProcess(), backend.crt.get_osfhandle(fd),
                        win.GetCurrentProcess(), 0, True, win.DUPLICATE_SAME_ACCESS))
                startup = subprocess.STARTUPINFO(); startup.dwFlags = win.STARTF_USESTDHANDLES
                startup.hStdInput, startup.hStdOutput, startup.hStdError = duplicates
                startup.lpAttributeList = {'handle_list': duplicates}
                args = [group.executable.path, *group.command.arguments]
                process, thread, pid, _ = win.CreateProcess(args[0], subprocess.list2cmdline(args), None, None, True,
                    0x4 | 0x400 | 0x80000, env, group.executable.root_path, startup)
                # Store exact returned handles before any fallible validation or
                # cleanup. Failure before Job assignment still owns this child.
                r.update(process=process, thread=thread, pid=pid, bound=False)
                for key in ('worker_go_r','worker_ready_w'):
                    fd=r.pop(key,None)
                    if fd is not None:
                        try:os.close(fd)
                        except BaseException:
                            r.setdefault('stdio_close_unknown',[]).append(('CRT',fd))
                            raise
            except BaseException as error: primary = error
            finally:
                while duplicates:
                    handle = duplicates.pop()
                    try: backend.close(handle)
                    except BaseException as error:
                        r.setdefault('stdio_close_unknown',[]).append(handle)  # Retain, never retry an unknown CloseHandle.
                        cleanup.append(error)
        if primary is not None or cleanup:
            raise BaseExceptionGroup('NATIVE_CREATE_OR_STDIO_FAILED', ([primary] if primary is not None else []) + cleanup)
        if time.monotonic() >= deadline: raise ProcessRefused('NATIVE_START_DEADLINE')
        r['birth'] = self.birth(r['process'])
        if r['birth'][0] != r['pid']: raise ProcessRefused('CREATION_IDENTITY_REFUSED')
        image, size = C.create_unicode_buffer(4096), C.c_uint32(4096)
        if not self.image(r['process'], 1, image, C.byref(size)) or not 0 < size.value < 4096:
            raise ProcessRefused('CREATION_IMAGE_REFUSED')
        if image.value.casefold() != group.executable.native_path.casefold():
            raise ProcessRefused('CREATION_IMAGE_REFUSED')
        group.executable.verify()
        backend.bind(r['job'], r['process'], r['pid']); r['bound'] = True
        if self.birth(r['process']) != r['birth']: raise ProcessRefused('CREATION_IDENTITY_CHANGED')
        if time.monotonic() >= deadline: raise ProcessRefused('NATIVE_START_DEADLINE')
        backend.resume(r['thread']); group.started = True

    def observe(self, group, deadline):
        r = group.resources
        if 'process' not in r: return group.returncode
        if 'birth' in r and self.birth(r['process']) != r['birth']:
            raise ProcessRefused('CREATION_IDENTITY_CHANGED')
        try: return self.original.wait(r['process'], max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired: return None

    def stop(self, group, deadline):
        from scripts.windows_ci.owned_job import Accounting, DWORD
        r, backend = group.resources, self.original
        if 'process' in r and not r.get('bound'):
            # Original abort_suspended operations, but one shared stop deadline.
            # Job accounting zero alone says NOTHING about an unassigned child.
            backend.win.TerminateProcess(r['process'], 125)
            group.returncode = backend.wait(r['process'], max(0, deadline - time.monotonic()))
            r['unbound_stopped'] = True
        if 'job' not in r: return 'process' not in r
        if time.monotonic() >= deadline: return False
        if not backend.kernel.TerminateJobObject(r['job'], 124):
            raise ProcessRefused('JOB_TERMINATE_REFUSED')
        while time.monotonic() < deadline:
            state, length = Accounting(), DWORD()
            if not backend.kernel.QueryInformationJobObject(r['job'], 1, C.byref(state), C.sizeof(state), C.byref(length)):
                raise ProcessRefused('JOB_QUERY_REFUSED')
            if length.value != C.sizeof(state): raise ProcessRefused('JOB_QUERY_REFUSED')
            if state.ActiveProcesses == 0:
                if 'process' in r:
                    code = self.observe(group, deadline)
                    if code is None: return False
                    group.returncode = code
                return time.monotonic() <= deadline
            time.sleep(min(.01, max(0, deadline - time.monotonic())))
        return False

    def close_observed(self, group):
        errors = []
        for name in ('worker_go_r','worker_go_w','worker_ready_r','worker_ready_w'):
            fd=group.resources.pop(name,None)
            if fd is not None:
                try: os.close(fd)
                except BaseException as error: errors.append(error)
        for name in ('thread', 'process', 'job'):
            handle = group.resources.pop(name, None)
            if handle is not None:
                try: self.original.close(handle)
                except BaseException as error: errors.append(error)
        if errors: raise BaseExceptionGroup('NATIVE_PROCESS_CLOSE_UNKNOWN', errors)
