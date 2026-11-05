"""Original thread suspend-count refusal semantics with finite diagnostics."""
import json
from types import SimpleNamespace
import pytest
from scripts.windows_ci import owned_job as jobs
from scripts.windows_ci.native_failure_diagnostics import detail


@pytest.mark.parametrize('previous', [0, 2, 0xffffffff])
def test_resume_never_accepts_wrong_suspend_count_or_retries(previous, monkeypatch):
    calls=[]
    backend=object.__new__(jobs.WindowsBackend)
    backend.kernel=SimpleNamespace(ResumeThread=lambda thread: calls.append(thread) or previous)
    monkeypatch.setattr(jobs.ctypes, 'get_last_error', lambda: 6, raising=False)
    with pytest.raises(jobs.OwnedThreadResumeError) as caught:
        backend.resume(123)
    assert calls == [123]
    report=detail(caught.value,'OwnedJobError')
    assert report['thread_resume']==dict(previous_count=previous,winerror=6 if previous==0xffffffff else None)
    assert '123' not in json.dumps(report)


def test_exactly_one_suspend_count_preserves_success():
    backend=object.__new__(jobs.WindowsBackend)
    backend.kernel=SimpleNamespace(ResumeThread=lambda thread: 1)
    assert backend.resume(123) is None


@pytest.mark.parametrize('value', [True, 'PRIVATE_TEXT', -1, 2**32])
def test_invalid_numeric_diagnostic_fields_never_leak(value):
    error=jobs.OwnedThreadResumeError(value,None)
    report=detail(error,'OwnedJobError')
    assert report['thread_resume']==dict(details='UNAVAILABLE')
    assert 'PRIVATE_TEXT' not in json.dumps(report)


@pytest.mark.parametrize('observation', [dict(wait=0,exit_code=0xc000000d), dict(wait=258,exit_code=None)])
def test_owned_process_observation_is_finite_numeric_data(observation):
    error=jobs.OwnedThreadResumeError(0xffffffff,6)
    error.process_observation=observation
    assert detail(error,'OwnedJobError')['owned_process_at_resume']==observation


@pytest.mark.parametrize('observation', [dict(wait=True,exit_code=1), dict(wait=0,exit_code='PRIVATE_TEXT'), dict(wait=0,exit_code=1,path='PRIVATE_TEXT')])
def test_untrusted_process_metadata_is_not_exported(observation):
    error=jobs.OwnedThreadResumeError(0xffffffff,6)
    error.process_observation=observation
    result=detail(error,'OwnedJobError')
    assert 'owned_process_at_resume' not in result
    assert 'PRIVATE_TEXT' not in json.dumps(result)
