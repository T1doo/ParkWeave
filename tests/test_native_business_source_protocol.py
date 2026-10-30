"""Pure source/protocol checks only. Never Windows native execution evidence."""
import copy
import pickle
import time
from unittest.mock import patch

import pytest

from scripts.windows import lifecycle
from scripts.windows_portable import native_acceptance_issuer as issuer
from scripts.windows_portable.native_business_adapter import NativeBusinessTestAdapter, BusinessRestartObservation, inspect_restart
from scripts.windows_portable.native_composition import compose_native_local_preparation
from scripts.windows_portable.endpoint_plan import PlanMode, EndpointRequest
from scripts.windows_portable.controller import CandidateRefused
from scripts.windows_portable.preparation_business_trial import PreparationBusinessTrial


def composition(path, mode):
    return compose_native_local_preparation(base=str(path), mode=mode,
        request=EndpointRequest(55431, 58761) if mode is PlanMode.NEW else None,
        runtime=dict(source_commit='a'*40, manifest_sha256='b'*64),
        initdb_sha256='c'*64, initdb_size=1, postgres_sha256='d'*64, postgres_size=1,
        python_sha256='e'*64, python_size=1, challenge='f'*32)


def test_adapter_real_compositions_refuse_before_reservation_or_native_access(tmp_path):
    first, second = composition(tmp_path, PlanMode.NEW), composition(tmp_path, PlanMode.REOPEN)
    with patch.object(PreparationBusinessTrial, 'begin', side_effect=AssertionError('unexpected trial execution')):
        adapter = NativeBusinessTestAdapter(first, second, str(tmp_path/'trial'))
        with pytest.raises(lifecycle.BoundaryError) as caught:
            adapter.run()
    assert caught.value.parkweave_lifecycle_reason == 'OWNER_MUTATION_PAUSED'
    assert adapter.trial.state == 'NOT_STARTED' and not adapter.started
    assert list(tmp_path.iterdir()) == []


def test_reports_name_lists_and_unissued_observations_cannot_issue_acceptance():
    deadline = time.monotonic()+5
    with pytest.raises(issuer.AcceptanceRefused):
        issuer.issue_accepted(None, ({'complete_native_business_restart': True},), deadline)
    forged = issuer.VerifiedNativeObservation()
    with pytest.raises(issuer.AcceptanceRefused):
        issuer.issue_accepted(None, (forged,), deadline)
    with pytest.raises(issuer.AcceptanceRefused) as caught:
        issuer.issue_accepted(None, (), deadline)
    assert caught.value.reason == 'NATIVE_ACCEPTANCE_EVIDENCE_INCOMPLETE'
    assert 'dpapi_cross_os_identity_isolation' in caught.value.missing
    assert 'complete_native_business_restart' in caught.value.missing
    with pytest.raises(CandidateRefused):
        inspect_restart(BusinessRestartObservation(), None, deadline)
    for value in (forged, issuer.AcceptedInstallationCapability(), BusinessRestartObservation()):
        for clone in (copy.copy, copy.deepcopy, pickle.dumps):
            with pytest.raises(TypeError):
                clone(value)
    status = issuer.issuer_status()
    assert not status['reviewed_platform_policy'] and not status['activation_allowed']
    assert 'api_set_resolution' in status['missing_producers']


def test_expired_original_business_window_refuses_before_native_revalidation(monkeypatch):
    from scripts.windows_portable import native_business_adapter as native
    proof = BusinessRestartObservation()
    invocation, snapshot = object(), object()
    native._issued[proof] = (invocation, snapshot, time.monotonic()-1)
    monkeypatch.setattr(native, '_snapshot', lambda *args: pytest.fail('must refuse BEFORE native access'))
    try:
        with pytest.raises(CandidateRefused):
            inspect_restart(proof, invocation, time.monotonic()+20)
    finally:
        native._issued.pop(proof, None)


def test_wait_run_has_one_absolute_deadline_and_only_read_polls(monkeypatch):
    from scripts.windows_portable import local_preparation as client
    from scripts.windows_portable.test_local_preparation import workspace, RUN
    clock = [100.0]
    class Reads:
        def __init__(self): self.deadlines=[]
        def request(self, application, actor, method, path, body, key, deadline):
            assert (method, path, body, key) == ('GET', '/api/runs/'+RUN, None, None)
            self.deadlines.append(deadline)
            clock[0] += .21
            return dict(run_id=RUN, state='QUEUED')
    transport=Reads()
    monkeypatch.setattr(client.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(client.time, 'sleep', lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    with pytest.raises(CandidateRefused, match='deadline'):
        workspace(transport).enterprise.wait_run(RUN, seconds=.5)
    assert len(transport.deadlines) == 2 and set(transport.deadlines) == {100.5}
