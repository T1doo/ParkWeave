from copy import deepcopy
from datetime import datetime, timezone
from test_structure_review_runtime import (upgrade_case, link_fixture, receipt_fixture,
    preparation_fixture, record_private_fixture_sessions, full_six, SIX,
    publication, structure_admit, structure_apply, original)


def test_structure_actual_saved_event_expiry_before_real_pg_commit_rolls_back(upgrade_case, monkeypatch):
    from parkweave import service_case_steps
    u = upgrade_case
    row, _, _ = full_six(u)
    target = publication(u, SIX[:4]+[SIX[-1]])
    _, data = structure_admit(u, row, target)
    before = deepcopy(original.stored(u, row))
    save = service_case_steps._save
    clock = u['engine'].clock
    observed = []

    def save_and_expire(c, parent, plan):
        save(c, parent, plan)
        if plan['events'][-1]['request_key'] == 'structure-expiry-after-real-save':
            actual = c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',
                (row['preparation_id'],)).fetchone()['service_case_plan']
            observed.append(actual['events'][-1]['request_key'])
            u['engine'].clock = lambda: datetime(2100, 1, 1, tzinfo=timezone.utc)

    monkeypatch.setattr(service_case_steps, '_save', save_and_expire)
    response = structure_apply(u, row, data, 'structure-expiry-after-real-save')
    u['engine'].clock = clock
    assert observed == ['structure-expiry-after-real-save']
    assert response.status_code in (403, 409), response.text
    assert original.stored(u, row) == before
