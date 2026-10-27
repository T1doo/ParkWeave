"""Actual cleanup/control flow with injected WinAPI bytes; no native evidence."""
import ctypes
import subprocess
import sys

import pytest

from scripts.windows_ci import owned_job as job


class Kernel:
    def __init__(self, replies):
        self.replies = iter(replies)
        self.queries = 0
        self.terminations = 0

    def TerminateJobObject(self, handle, code):
        assert (handle, code) == (101, 124)
        self.terminations += 1
        return 1

    def QueryInformationJobObject(self, handle, kind, pointer, size, length):
        assert (handle, kind, size) == (101, 1, 48)
        assert length is not None
        output = ctypes.cast(length, ctypes.POINTER(job.DWORD)).contents
        assert output.value == 0  # fresh output for each query
        ok, actual_length, active = next(self.replies)
        self.queries += 1
        if actual_length is not None:
            output.value = actual_length
        if active is not None:
            ctypes.cast(pointer, ctypes.POINTER(job.Accounting)).contents.ActiveProcesses = active
        return ok


def backend(replies):
    result = job.WindowsBackend.__new__(job.WindowsBackend)
    result.kernel = Kernel(replies)
    return result


@pytest.mark.parametrize('length', [None, 0, 4, 40, 44, 47, 49, 2**32 - 1])
def test_success_flag_with_incomplete_or_oversized_output_never_means_stopped(length):
    candidate = backend([(1, length, None)])
    with pytest.raises(job.OwnedJobError, match='^JOB_QUERY_REFUSED$'):
        candidate.stop_tree(101)
    assert candidate.kernel.terminations == candidate.kernel.queries == 1
    assert candidate.observation_receipt is None


def test_complete_nonzero_reply_waits_for_fresh_complete_zero(monkeypatch):
    now = [10.]
    monkeypatch.setattr(job.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(job.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    candidate = backend([(1, 48, 1), (1, 48, 0)])
    assert candidate.stop_tree(101) == 'OWNED_TREE_STOPPED'
    assert candidate.kernel.queries == 2 and candidate.kernel.terminations == 1
    assert now[0] == 10.01


def test_second_query_cannot_inherit_previous_returned_length(monkeypatch):
    monkeypatch.setattr(job.time, 'sleep', lambda seconds: None)
    candidate = backend([(1, 48, 1), (1, None, 0)])
    with pytest.raises(job.OwnedJobError, match='^JOB_QUERY_REFUSED$'):
        candidate.stop_tree(101)
    assert candidate.kernel.queries == 2 and candidate.kernel.terminations == 1


def test_failed_api_with_complete_zero_payload_remains_query_failure():
    candidate = backend([(0, 48, 0)])
    with pytest.raises(job.OwnedJobError, match='^JOB_QUERY_REFUSED$'):
        candidate.stop_tree(101)
    assert candidate.kernel.queries == candidate.kernel.terminations == 1


@pytest.mark.parametrize('primary', [0, 17, 'timeout'])
def test_incomplete_cleanup_preserves_primary_and_closes_original_handles(tmp_path, primary):
    candidate = backend([(1, None, None)])
    closed = []
    candidate.create_job = lambda: 101
    candidate.launch = lambda *args: (202, 303, 404)
    candidate.bind = lambda *args: None
    candidate.resume = lambda *args: None
    candidate.close = closed.append

    def wait(*args):
        if primary == 'timeout':
            raise subprocess.TimeoutExpired('OWNED_JOB', 1)
        return primary

    candidate.wait = wait
    with (tmp_path / 'out').open('wb') as out, (tmp_path / 'err').open('wb') as err:
        def run():
            return job.run([sys.executable, '-c', 'pass'], timeout=1,
                           stdout=out, stderr=err, _backend=candidate)
        if primary == 17:
            value = run()
            assert value.returncode == 17
        else:
            with pytest.raises(subprocess.TimeoutExpired if primary == 'timeout' else job.OwnedJobError) as caught:
                run()
            value = caught.value
            assert value.cleanup_error_category == 'OwnedJobError'
            if primary == 0:
                assert value.args == ('JOB_QUERY_REFUSED',)
    assert value.cleanup == 'OWNED_TREE_STOP_UNCONFIRMED'
    assert closed == [303, 202, 101]
    assert candidate.kernel.queries == candidate.kernel.terminations == 1
