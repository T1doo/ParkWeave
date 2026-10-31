"""Pure source/protocol checks only. Never Windows native execution evidence."""
import copy
from pathlib import Path
import pickle
import shutil
import subprocess
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


def test_actual_git_crlf_checkout_keeps_role_bytes_and_original_integrity_gate(tmp_path,monkeypatch):
    if shutil.which('git') is None:pytest.skip('Git checkout required; no alternative source adoption')
    from parkweave import store
    from scripts.windows_portable.controller import NativeDatabaseOperations
    root=Path(__file__).resolve().parents[1]
    repo=tmp_path/'checkout';repo.mkdir()
    subprocess.run(['git','init','-q',str(repo)],check=True,capture_output=True)
    def git(*args,input=None):
        return subprocess.check_output(['git','-C',str(repo),*args],input=input)
    original=(root/'src/parkweave/roles.sql').read_bytes()
    for name,raw in (('.gitattributes',(root/'.gitattributes').read_bytes()),
                     ('src/parkweave/roles.sql',original)):
        blob=git('hash-object','-w','--stdin',input=raw).decode().strip()
        git('update-index','--add','--cacheinfo','100644',blob,name)
    # Explicit CRLF reproduces the Windows-native EOL policy without running
    # Windows, changing system Git config, or calling native security APIs.
    git('-c','core.autocrlf=false','-c','core.eol=crlf','checkout-index','--all')
    roles=repo/'src/parkweave/roles.sql'
    assert roles.read_bytes()==original,'checkout changed the raw role source bytes'
    monkeypatch.setattr(store,'__file__',str(roles.with_name('store.py')))
    assert NativeDatabaseOperations().prepare_new()==original
    # The fix is checkout policy, never canonicalizing or accepting modified SQL.
    roles.write_bytes(original+b'-- SYNTHETIC corruption must remain refused\n')
    with pytest.raises(CandidateRefused):NativeDatabaseOperations().prepare_new()


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
    assert 'api_set_resolution' in status['implemented_producers']
    assert 'original_job_and_backend_loaded_sources' in status['implemented_producers']
    assert status['native_acceptance']=='NOT_ACCEPTED' and not status['usable_product']


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
