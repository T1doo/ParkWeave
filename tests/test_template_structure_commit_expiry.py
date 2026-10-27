"""Real guarded PG commit must reject a target that expires after its event UPDATE."""
from datetime import datetime, timezone
import pytest

from test_template_upgrade import upgrade_case, publication
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from test_template_structure_independent import (complete_declared, admit, apply,
    private_fixture_sessions, OLD_GOALS, NEW_GOALS, denied_effects_preserved)
from test_template_migration_independent import all_pg_rows, admit as old_admit, apply as old_apply


@pytest.mark.parametrize('kind', ['structure', 'source', 'description'])
def test_apply_target_expiry_at_actual_guarded_pg_commit_rolls_back_every_effect(upgrade_case, monkeypatch, kind):
    from parkweave.store import _AccessConnection
    u = upgrade_case
    row, _, _ = complete_declared(u)
    target = publication(u, NEW_GOALS if kind == 'structure' else OLD_GOALS,
        source='2' if kind == 'source' else '1', name='SYNTHETIC expiry at actual PG commit')
    _, data = (admit if kind == 'structure' else old_admit)(u, row, target)
    assert len(data) == (13 if kind == 'structure' else 11)
    before = all_pg_rows(u)
    clock = u['engine'].clock
    native_commit = _AccessConnection.commit
    observed = []
    key = 'actual-template-commit-expiry-'+kind

    def expire_at_commit(c):
        if not observed and c.info.user == 'parkweave_app':
            actual = c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',
                (row['preparation_id'],)).fetchone()['service_case_plan']
            if actual['events'][-1]['request_key'] == key:
                # The real original UPDATE is visible in this same transaction;
                # no simulated write or earlier-only preflight can satisfy this.
                observed.append(actual['events'][-1]['request_key'])
                u['engine'].clock = lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)
        return native_commit(c)

    monkeypatch.setattr(_AccessConnection, 'commit', expire_at_commit)
    try:
        response = (apply if kind == 'structure' else old_apply)(u, row, data, key)
    finally:
        u['engine'].clock = clock
    assert observed == [key]
    assert response.status_code in (403, 409), response.text
    denied_effects_preserved(before, all_pg_rows(u), 'fixture-a', int(response.status_code == 403))
