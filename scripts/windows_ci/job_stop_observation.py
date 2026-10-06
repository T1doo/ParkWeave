"""Unwired ENG072 candidate: observe caller-verified held handles only.

The caller must keep its exact process and inner Job handles open throughout,
and supply the original cleanup start from the same monotonic clock. This is
one process observation, never proof that an arbitrary whole tree has stopped.
No process discovery, opening, closing or termination is performed here.
"""
import ctypes
import math
import os
import time

from .owned_job import Accounting, BOOL, DWORD, HANDLE

MAX_SAMPLES = 8
INTERVAL = .05
CLEANUP_SECONDS = 5
MAX_HANDLE = (1 << (8 * ctypes.sizeof(HANDLE))) - 1


class ReadOnlyBackend:
    def __init__(self):
        if os.name != 'nt':
            raise RuntimeError('WINDOWS_REQUIRED')
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        declarations = {
            'IsProcessInJob': ([HANDLE, HANDLE, ctypes.POINTER(BOOL)], BOOL),
            'QueryInformationJobObject': ([HANDLE, ctypes.c_int32, ctypes.c_void_p,
                                           DWORD, ctypes.POINTER(DWORD)], BOOL),
            'WaitForSingleObject': ([HANDLE, DWORD], DWORD),
        }
        for name, (args, result) in declarations.items():
            function = getattr(self.kernel, name)
            function.argtypes, function.restype = args, result

    def membership(self, process, job):
        value = BOOL()
        if not self.kernel.IsProcessInJob(process, job, ctypes.byref(value)):
            raise RuntimeError('READ_REFUSED')
        if value.value not in (0, 1):
            raise RuntimeError('READ_REFUSED')
        return bool(value.value)

    def active_processes(self, job):
        value, length = Accounting(), DWORD()
        if not self.kernel.QueryInformationJobObject(
                job, 1, ctypes.byref(value), ctypes.sizeof(value), ctypes.byref(length)):
            raise RuntimeError('READ_REFUSED')
        if length.value != ctypes.sizeof(value):
            raise RuntimeError('READ_REFUSED')
        return int(value.ActiveProcesses)

    def signal(self, process):
        value = self.kernel.WaitForSingleObject(process, 0)
        if value == 0:
            return 'SIGNALED'
        if value == 258:
            return 'LIVE'
        return 'UNKNOWN'


def observe(process, job, *, cleanup_started, backend, clock=time.monotonic,
            pause=time.sleep):
    """At most eight snapshots, strictly inside the caller's original 5 seconds.

    Membership/accounting/signal are successive reads, not an atomic snapshot.
    A non-member or unknown read cannot establish owned-process completion.
    Each read is gated separately by the existing deadline. Queries must be
    nonblocking; Python cannot preempt a backend call that itself hangs.
    """
    samples = []

    def result(status, reason):
        return {'status': status, 'reason': reason,
                'sample_count': len(samples), 'samples': samples}

    if (type(process) is not int or not 0 < process <= MAX_HANDLE or type(job) is not int or not 0 < job <= MAX_HANDLE
            or type(cleanup_started) not in (int, float)
            or not math.isfinite(cleanup_started)):
        return result('UNKNOWN', 'INVALID_INPUT')
    deadline = cleanup_started + CLEANUP_SECONDS

    def budget():
        now = clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < cleanup_started:
            raise ValueError()
        return deadline - now

    try:
        for index in range(MAX_SAMPLES):
            if budget() <= 0:
                return result('UNKNOWN', 'DEADLINE')
            member = backend.membership(process, job)
            if type(member) is not bool:
                return result('UNKNOWN', 'READ_UNKNOWN')
            if budget() <= 0:
                return result('UNKNOWN', 'DEADLINE')
            active = backend.active_processes(job)
            if type(active) is not int or active < 0:
                return result('UNKNOWN', 'READ_UNKNOWN')
            if budget() <= 0:
                return result('UNKNOWN', 'DEADLINE')
            signal = backend.signal(process)
            if signal not in ('LIVE', 'SIGNALED', 'UNKNOWN') or type(signal) is not str:
                return result('UNKNOWN', 'READ_UNKNOWN')
            if budget() <= 0:
                return result('UNKNOWN', 'DEADLINE')
            samples.append({'membership': 'MEMBER' if member else 'NON_MEMBER',
                            'accounting': 'ZERO' if active == 0 else 'NONZERO',
                            'signal': signal})
            if not member:
                return result('UNKNOWN', 'NON_MEMBER')
            if signal == 'UNKNOWN':
                return result('UNKNOWN', 'READ_UNKNOWN')
            if signal == 'SIGNALED':
                return result('EXACT_PROCESS_SIGNALED', 'OBSERVED')
            if index + 1 < MAX_SAMPLES:
                remaining = budget()
                if remaining <= 0:
                    return result('UNKNOWN', 'DEADLINE')
                pause(min(INTERVAL, remaining))
        return result('UNKNOWN', 'SAMPLE_LIMIT')
    except Exception:
        return result('UNKNOWN', 'READ_UNKNOWN')
