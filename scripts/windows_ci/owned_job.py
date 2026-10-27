"""Fresh Windows job: suspend, bind and verify exact creation handles, then run.

Only native_suite/regression coordinators opt in. No PID discovery, alternate
identity, breakaway, privilege adjustment, ACL changes or uncontained fallback.
CPython's _winapi handles CreateProcessW/STARTUPINFOEX and its Unicode environment.
"""
import ctypes
import math
import os
from pathlib import Path
import subprocess
import time


class OwnedJobError(RuntimeError):
    """Fixed failure category; raw WinAPI errors are not public diagnostics."""


# Fixed Win32 widths even when imported by the Linux contract tests.
DWORD = ctypes.c_uint32
BOOL = ctypes.c_int32
HANDLE = ctypes.c_void_p
SIZE_T = ctypes.c_size_t


class BasicLimit(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_int64),
                ('PerJobUserTimeLimit', ctypes.c_int64), ('LimitFlags', DWORD),
                ('MinimumWorkingSetSize', SIZE_T), ('MaximumWorkingSetSize', SIZE_T),
                ('ActiveProcessLimit', DWORD), ('Affinity', SIZE_T),
                ('PriorityClass', DWORD), ('SchedulingClass', DWORD)]


class IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ('ReadOperationCount', 'WriteOperationCount', 'OtherOperationCount',
                 'ReadTransferCount', 'WriteTransferCount', 'OtherTransferCount')]


class ExtendedLimit(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', BasicLimit), ('IoInfo', IoCounters),
                ('ProcessMemoryLimit', SIZE_T), ('JobMemoryLimit', SIZE_T),
                ('PeakProcessMemoryUsed', SIZE_T), ('PeakJobMemoryUsed', SIZE_T)]


class Accounting(ctypes.Structure):
    _fields_ = [(name, ctypes.c_int64) for name in
                ('TotalUserTime', 'TotalKernelTime', 'ThisPeriodTotalUserTime', 'ThisPeriodTotalKernelTime')]
    _fields_ += [(name, DWORD) for name in
                 ('TotalPageFaultCount', 'TotalProcesses', 'ActiveProcesses', 'TotalTerminatedProcesses')]


class WindowsBackend:
    def __init__(self, *, observation_target=None, observation_backend=None):
        if os.name != 'nt':
            raise OwnedJobError('WINDOWS_REQUIRED')
        import _winapi
        import msvcrt
        self.win, self.crt = _winapi, msvcrt
        # Optional borrowed descendant; never substitute our created parent.
        self.observation_target = observation_target
        self.observation_backend = observation_backend
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        declarations = {
            'CreateJobObjectW': ([ctypes.c_void_p, ctypes.c_wchar_p], HANDLE),
            'SetInformationJobObject': ([HANDLE, ctypes.c_int32, ctypes.c_void_p, DWORD], BOOL),
            'AssignProcessToJobObject': ([HANDLE, HANDLE], BOOL),
            'IsProcessInJob': ([HANDLE, HANDLE, ctypes.POINTER(BOOL)], BOOL),
            'GetProcessId': ([HANDLE], DWORD),
            'ResumeThread': ([HANDLE], DWORD),
            'TerminateJobObject': ([HANDLE, ctypes.c_uint32], BOOL),
            'QueryInformationJobObject': ([HANDLE, ctypes.c_int32, ctypes.c_void_p, DWORD, ctypes.POINTER(DWORD)], BOOL),
        }
        for name, (args, result) in declarations.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result

    def create_job(self):
        # NULL security attributes => non-inheritable; NULL name => fresh job.
        job = self.kernel.CreateJobObjectW(None, None)
        if not job:
            raise OwnedJobError('JOB_CREATE_REFUSED')
        limits = ExtendedLimit()
        limits.BasicLimitInformation.LimitFlags = 0x2000  # KILL_ON_JOB_CLOSE only
        try:
            if not self.kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
                raise OwnedJobError('JOB_LIMIT_REFUSED')
        except BaseException as error:
            try:
                self.close(job)
            except BaseException:
                error.cleanup = 'OWNED_TREE_STOP_UNCONFIRMED'
            raise
        return job

    def launch(self, args, cwd, env, stdout, stderr):
        win = self.win
        duplicates = []
        created = None
        primary = None
        with open(os.devnull, 'rb') as stdin:
            try:
                for file in (stdin, stdout, stderr):
                    handle = win.DuplicateHandle(win.GetCurrentProcess(), self.crt.get_osfhandle(file.fileno()),
                                                 win.GetCurrentProcess(), 0, True, win.DUPLICATE_SAME_ACCESS)
                    duplicates.append(handle)
                startup = subprocess.STARTUPINFO()
                startup.dwFlags = win.STARTF_USESTDHANDLES
                startup.hStdInput, startup.hStdOutput, startup.hStdError = duplicates
                startup.lpAttributeList = {'handle_list': duplicates}
                # Exact handles only; job/process/thread handles are not inherited.
                flags = 0x4 | 0x400 | 0x80000  # SUSPENDED | UNICODE_ENVIRONMENT | EXTENDED_STARTUPINFO_PRESENT
                process, thread, pid, _ = win.CreateProcess(
                    args[0], subprocess.list2cmdline(args), None, None, True,
                    flags, env, str(cwd) if cwd is not None else None, startup)
                created = process, thread, pid
            except BaseException as error:
                primary = error
            finally:
                for handle in duplicates:
                    try:
                        self.close(handle)
                    except BaseException as error:
                        if primary is None:
                            primary = OwnedJobError('STDIO_HANDLE_CLOSE_REFUSED')
        if primary is not None:
            if created is not None:
                process, thread, _ = created
                primary.cleanup = 'OWNED_TREE_STOP_UNCONFIRMED'
                try:
                    self.abort_suspended(process)
                    primary.cleanup = 'SUSPENDED_CHILD_STOPPED'
                except BaseException:
                    pass  # Preserve the original refusal, never run or broaden scope.
                finally:
                    for handle in (thread, process):
                        try:
                            self.close(handle)
                        except BaseException:
                            primary.cleanup = 'OWNED_TREE_STOP_UNCONFIRMED'
            raise primary
        return created

    def bind(self, job, process, pid):
        if self.kernel.GetProcessId(process) != pid:
            raise OwnedJobError('CREATION_IDENTITY_REFUSED')
        if not self.kernel.AssignProcessToJobObject(job, process):
            raise OwnedJobError('JOB_BIND_REFUSED')
        inside = BOOL()
        if not self.kernel.IsProcessInJob(process, job, ctypes.byref(inside)) or not inside.value:
            raise OwnedJobError('JOB_MEMBERSHIP_REFUSED')

    def resume(self, thread):
        if self.kernel.ResumeThread(thread) != 1:
            raise OwnedJobError('THREAD_RESUME_REFUSED')

    def wait(self, process, timeout):
        status = self.win.WaitForSingleObject(process, max(0, int(timeout * 1000)))
        if status == self.win.WAIT_TIMEOUT:
            raise subprocess.TimeoutExpired('OWNED_JOB', timeout)
        if status != self.win.WAIT_OBJECT_0:
            raise OwnedJobError('PROCESS_WAIT_REFUSED')
        return self.win.GetExitCodeProcess(process)

    def abort_suspended(self, process):
        # Only the exact handle returned by this invocation, never OpenProcess/PID.
        self.win.TerminateProcess(process, 125)
        self.wait(process, 5)

    def stop_tree(self, job):
        # One deadline includes identity reads, termination and all observations.
        # Nonblocking API calls cannot be forcibly preempted if a backend hangs.
        cleanup_started = time.monotonic()
        deadline = cleanup_started + 5
        observer = None
        self.observation_receipt = None
        target = getattr(self, 'observation_target', None)
        if target is not None:
            if __package__:
                from .job_stop_observation import (
                    HeldDescendant, MAX_HANDLE, ReadOnlyBackend, StopObservationAdapter)
            else:
                from job_stop_observation import (
                    HeldDescendant, MAX_HANDLE, ReadOnlyBackend, StopObservationAdapter)
            def refused(reason):
                self.observation_receipt = {'scope': 'EXACT_PROCESS_ONLY', 'status': 'FAIL',
                                            'reason': reason, 'sample_count': 0, 'samples': []}
            try:
                if (not isinstance(target, HeldDescendant)
                        or type(target.handle) is not int or not 0 < target.handle <= MAX_HANDLE
                        or target.handle == getattr(self, '_owned_parent_handle', None)
                        or target.handle in getattr(self, '_owned_handles', ())
                        or type(target.expected_pid) is not int or target.expected_pid <= 0
                        or target.expected_pid == getattr(self, '_owned_parent_pid', None)
                        or type(target.expected_created) not in (int, float)
                        or not math.isfinite(target.expected_created) or target.expected_created <= 0):
                    raise ValueError()
                reads = getattr(self, 'observation_backend', None)
                if reads is None:reads = ReadOnlyBackend()
                if time.monotonic() >= deadline:
                    refused('DEADLINE')
                else:
                    pid, created, signal = reads.identity(target.handle)
                    if time.monotonic() >= deadline:
                        refused('DEADLINE')
                    elif (type(pid) is not int or pid != target.expected_pid
                            or type(created) not in (int, float) or not math.isfinite(created)
                            or created <= 0
                            or abs(created - target.expected_created) > .00001
                            or type(signal) is not str or signal not in ('LIVE', 'SIGNALED')):
                        refused('IDENTITY_REFUSED')
                    else:
                        observer = StopObservationAdapter(target.handle, job,
                            cleanup_started=cleanup_started, backend=reads,
                            clock=time.monotonic, pause=time.sleep)
                        observer.capture('BEFORE_TERMINATE')
            except Exception:
                refused('IDENTITY_REFUSED')
        try:
            # Refused observation must not prevent the original owned Job kill.
            if not self.kernel.TerminateJobObject(job, 124):
                raise OwnedJobError('JOB_TERMINATE_REFUSED')
            if observer is not None:observer.capture('AFTER_TERMINATE')
            while True:
                if time.monotonic() >= deadline:
                    raise OwnedJobError('JOB_STOP_UNCONFIRMED')
                state, length = Accounting(), DWORD()
                if not self.kernel.QueryInformationJobObject(job, 1, ctypes.byref(state), ctypes.sizeof(state), ctypes.byref(length)):
                    raise OwnedJobError('JOB_QUERY_REFUSED')
                if time.monotonic() >= deadline:
                    raise OwnedJobError('JOB_STOP_UNCONFIRMED')
                if length.value != ctypes.sizeof(state):
                    raise OwnedJobError('JOB_QUERY_REFUSED')
                if state.ActiveProcesses == 0:
                    if observer is not None:
                        observer.capture('ACCOUNTING_ZERO')
                        self.observation_receipt = observer.finish()
                    if (self.observation_receipt is not None
                            and self.observation_receipt['status'] != 'PASS'):
                        raise OwnedJobError('JOB_STOP_UNCONFIRMED')
                    if time.monotonic() >= deadline:
                        raise OwnedJobError('JOB_STOP_UNCONFIRMED')
                    return 'OWNED_TREE_STOPPED'
                if time.monotonic() >= deadline:
                    raise OwnedJobError('JOB_STOP_UNCONFIRMED')
                time.sleep(min(.01, max(0, deadline-time.monotonic())))
        finally:
            if observer is not None and self.observation_receipt is None:
                self.observation_receipt = observer.finish()

    def close(self, handle):
        self.win.CloseHandle(handle)


def run(args, *, timeout, stdout, stderr, cwd=None, env=None, _backend=None):
    """Regular-file output only. Raise original timeout/error with cleanup metadata."""
    args = [str(value) for value in args]
    if not args or not Path(args[0]).is_absolute() or not Path(args[0]).is_file() or timeout <= 0:
        raise ValueError('explicit existing executable and positive deadline required')
    backend = _backend if _backend is not None else WindowsBackend()
    job = process = thread = None
    resumed = False
    primary = None
    code = None
    cleanup_error = None
    cleanup = 'NOT_STARTED'
    try:
        job = backend.create_job()
        process, thread, pid = backend.launch(args, cwd, env, stdout, stderr)
        if isinstance(backend, WindowsBackend):
            backend._owned_parent_handle, backend._owned_parent_pid = process, pid
            backend._owned_handles = (thread, process, job)
        backend.bind(job, process, pid)
        backend.resume(thread)
        resumed = True
        code = backend.wait(process, timeout)
    except BaseException as error:
        primary = error
        if process is None and getattr(error,'cleanup',None) in ('SUSPENDED_CHILD_STOPPED','OWNED_TREE_STOP_UNCONFIRMED'):
            cleanup = error.cleanup
    finally:
        try:
            if process is not None:
                cleanup = 'OWNED_TREE_STOP_UNCONFIRMED'
                if resumed:
                    cleanup = backend.stop_tree(job)
                else:
                    backend.abort_suspended(process)
                    cleanup = 'SUSPENDED_CHILD_STOPPED'
        except BaseException as error:
            cleanup_error = error
            if primary is None and (code is None or code == 0):
                primary = error
        finally:
            for handle in (thread, process, job):
                if handle is not None:
                    try:
                        backend.close(handle)
                    except BaseException as error:
                        cleanup = 'OWNED_TREE_STOP_UNCONFIRMED'
                        cleanup_error = error
                        if primary is None and (code is None or code == 0):
                            primary = error
    if primary is not None:
        primary.cleanup = cleanup
        primary.parkweave_owned_tree_cleanup = cleanup
        if cleanup_error is not None:
            primary.cleanup_error_category = type(cleanup_error).__name__
        if getattr(backend, 'observation_receipt', None) is not None:
            primary.exact_process_observation = backend.observation_receipt
        raise primary
    result = subprocess.CompletedProcess(args, code)
    result.cleanup = cleanup
    if getattr(backend, 'observation_receipt', None) is not None:
        result.exact_process_observation = backend.observation_receipt
    return result
