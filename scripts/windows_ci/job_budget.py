"""An explicit job test cutoff, mapped once to a monotonic local deadline."""
import math
import os
import time


def system_uptime_ms():
    if os.name=='nt':
        import ctypes
        function=ctypes.WinDLL('kernel32',use_last_error=True).GetTickCount64
        function.argtypes=[];function.restype=ctypes.c_ulonglong
        return function()
    # Portable synthetic scheduling only; native Windows uses shared kernel tick.
    return int(time.monotonic()*1000)


class JobBudget:
    def __init__(self, deadline, *, uptime_deadline=None, wall=time.time, clock=time.monotonic, uptime=system_uptime_ms):
        if type(deadline) not in (int, float) or not math.isfinite(deadline):
            raise ValueError('finite absolute job cutoff required')
        remaining = deadline - wall()
        if remaining>1290:raise ValueError('wall cutoff exceeds 1290-second test envelope')
        if uptime_deadline is not None:
            if type(uptime_deadline) is not int or not 0<=uptime_deadline<2**63:raise ValueError('integer uptime cutoff required')
            uptime_remaining=(uptime_deadline-uptime())/1000
            if uptime_remaining>1290:raise ValueError('uptime cutoff exceeds 1290-second test envelope')
            remaining=min(remaining,uptime_remaining)
        if remaining > 1290:
            raise ValueError('job test cutoff exceeds 1290-second test envelope')
        self.clock = clock
        self.end = clock() + max(0, remaining)

    def remaining(self):
        return max(0, self.end - self.clock())

    def limit(self, maximum, reserve=0):
        return min(maximum, max(0, self.remaining() - reserve))
