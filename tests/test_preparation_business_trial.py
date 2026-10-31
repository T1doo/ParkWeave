"""Actual Linux PG/API/ordinary worker for the native adapter's business code.

The HTTP bridge here has no Windows endpoint capability. These are business
integration results, never Windows ownership/loading/acceptance evidence.
"""
from contextlib import contextmanager
import json
import subprocess
import sys
import time

import pytest

from test_preparation import preparation_fixture
from ordinary_case_step_support import ordinary_api, environment, ROOT
from scripts.linux_fixture_server import stop_children
from scripts.windows_portable.controller import CandidateRefused
from scripts.windows_portable.local_preparation import PreparationWorkspace, PreparationCommandUnknown
from scripts.windows_portable.local_preparation_identity import PreparationIdentities
from scripts.windows_portable.preparation_business_trial import PreparationBusinessTrial


class ActualHTTP:
    def __init__(self, api, *, interrupt=False):
        self.api, self.interrupt = api, interrupt
        self.writes = []
        self.deadlines = []

    def request(self, application, actor, method, path, body, key, deadline):
        headers = {'Authorization': 'Bearer ' + actor.bearer}
        self.deadlines.append(deadline)
        if key is not None:
            headers['Idempotency-Key'] = key
            self.writes.append((path, key))
        response = self.api.request(method, path, headers=headers, json=body,
            timeout=max(.001, deadline-time.monotonic()))
        assert response.status_code in (200, 201, 202), 'real business API refused'
        if self.interrupt and method == 'POST' and path == '/api/preparations':
            raise ConnectionError('controlled loss AFTER actual SQL commit')
        return response.json()


@contextmanager
def ordinary_worker(f, path):
    path.mkdir()
    with (path/'worker.log').open('w') as log:
        child = subprocess.Popen([sys.executable, '-B', '-m', 'parkweave.worker'], cwd=ROOT,
            env=environment(f), stdout=log, stderr=subprocess.STDOUT)
        try:
            yield child
            assert child.poll() is None
        finally:
            stop_children([child])
            assert child.poll() is not None


def test_real_adapter_scenario_slot_corrections_unicode_two_roles_and_cold_http_readback(preparation_fixture, tmp_path):
    f = preparation_fixture
    identities = PreparationIdentities.from_mapping(f[2])  # Actual seeded synthetic principals.
    trial = PreparationBusinessTrial(seconds=120)
    trial.reserve()  # Controller startup is reserved before the business clock.
    with ordinary_worker(f, tmp_path/'first-worker'):
        with ordinary_api(f, tmp_path/'first-api') as api:
            transport = ActualHTTP(api)
            first = PreparationWorkspace(object(), identities, transport, lambda: None)
            deadline=trial.start_business(time.monotonic()+600)
            first.limit_deadline(deadline)
            trial.create(first)
            assert trial.state == 'FIRST_CONFIRMED'
            assert len(transport.writes) == len(set(transport.writes)) == 11
            assert max(transport.deadlines) <= deadline
            first.close()
    # API/worker are actually stopped above. The fixture PG stays running:
    # this result deliberately cannot prove a Windows PostgreSQL restart.
    with ordinary_worker(f, tmp_path/'second-worker'):
        with ordinary_api(f, tmp_path/'second-api') as api:
            second_transport = ActualHTTP(api)
            second = PreparationWorkspace(object(), identities, second_transport, lambda: None, deadline=deadline)
            assert trial.reopened(second).view == trial.checkpoint.view
            assert not second_transport.writes
            second.close()
    (tmp_path/'business-result.json').write_text(json.dumps(dict(
        scope='REAL_LINUX_PG_HTTP_WORKER_BUSINESS_ONLY', history_revision=10,
        writes=11, partial_correction_preserved=True, unicode_material=True,
        actual_api_worker_restart=True, exact_readback=True,
        windows_native_acceptance=False, postgres_restart=False)))


def test_actual_commit_response_loss_consumes_trial_and_never_reissues(preparation_fixture, tmp_path):
    f = preparation_fixture
    trial = PreparationBusinessTrial(seconds=90)
    deadline = trial.begin()
    with ordinary_worker(f, tmp_path/'worker'):
        with ordinary_api(f, tmp_path/'api') as api:
            transport = ActualHTTP(api, interrupt=True)
            workspace = PreparationWorkspace(object(), PreparationIdentities.from_mapping(f[2]),
                transport, lambda: None, deadline=deadline)
            with pytest.raises(PreparationCommandUnknown) as caught:
                trial.create(workspace)
            assert caught.value.action == 'CREATE' and trial.state == 'UNKNOWN'
            assert len(transport.writes) == 2
            with pytest.raises(CandidateRefused):
                trial.create(workspace)
            with pytest.raises(CandidateRefused):
                trial.begin()
            with f[1].connect() as c:
                assert c.execute('SELECT count(*) AS n FROM preparations').fetchone()['n'] == 1
                assert c.execute('SELECT count(*) AS n FROM preparation_events').fetchone()['n'] == 1
            assert len(transport.writes) == 2
            workspace.close()
