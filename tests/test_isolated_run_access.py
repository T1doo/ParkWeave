"""Owned fresh PG + original SQLite engine; not production permission setup."""
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
from uuid import UUID, uuid4

import psycopg
from psycopg.types.json import Jsonb
import pytest

from parkweave import case_fact_clarifications as facts
from parkweave import run_access_candidate as candidate
from parkweave.isolated_run_access import IsolatedRunAccessBridge, NAMESPACE, ProjectionPending
from parkweave.installed_fixture_receipt import NativeDatabaseCreationEvidence
from parkweave.store import Conflict, Denied, Store
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture, filled, command as prep_command, headers

APPROVER = 'prep-specialist-fixture-a'
PERMISSIONS = ('principals', 'capability_grants', 'field_grants', 'action_grants',
               'preparation_grants', 'synthetic_resource_grants')


def permission_snapshot(owner):
    with owner.connect() as c:
        return {table: c.execute('SELECT row_to_json(t) row FROM ' + table + ' t ORDER BY row_to_json(t)::text').fetchall()
                for table in PERMISSIONS}


@pytest.fixture
def access_fixture(receipt_fixture, tmp_path):
    f = receipt_fixture
    parent = filled(f)
    parent = prep_command(f, parent, 'REVIEW', APPROVER, reason='SYNTHETIC independent material check').json()
    parent = prep_command(f, parent, 'CONFIRM', reason='SYNTHETIC owner confirms').json()
    assert 'run_id' in parent
    before = permission_snapshot(f[1])
    now = [datetime.now(timezone.utc)]
    bridge = IsolatedRunAccessBridge(f[1], f[1]._case_fact_fixture_receipt,
        tmp_path / 'case.run-access.candidate.sqlite3', approver_ids={APPROVER},
        enabled_for_isolated_tests=True, clock=lambda: now[0])
    bridge.attach_store(f[0])
    assert permission_snapshot(f[1]) == before
    yield f, parent, bridge, now, before


def view(a, user='fixture-a'):
    f, parent, bridge, _, _ = a
    return bridge.read(f[2][user], parent['run_id'])


def body(a, action, user=None, **changes):
    user = user or (APPROVER if action in ('APPROVE', 'REJECT') else 'fixture-a')
    state = view(a, user)
    data = dict(action=action, expected_revision=state['revision'],
                expected_run_revision=state['run_revision'],
                expected_authority_sha256=state['authority_sha256'], reason='SYNTHETIC explicit ' + action)
    if action == 'REQUEST':
        now = a[3][0]
        data.update(target_id='executor-a', target_role='service_executor', capability='READ',
                    requested_validity=dict(valid_from=now.isoformat(), valid_until=(now + timedelta(minutes=10)).isoformat(), timezone='UTC'))
    elif action == 'APPROVE':
        data['approved_validity'] = state['request']['requested_validity']
    data.update(changes)
    return candidate.RunCommand.model_validate(data)


def act(a, action, user=None, key=None, data=None, **changes):
    f, parent, bridge, _, _ = a
    user = user or (APPROVER if action in ('APPROVE', 'REJECT') else 'fixture-a')
    return bridge.command(f[2][user], parent['run_id'], key or uuid4().hex,
                          data or body(a, action, user, **changes))


def approved(a):
    act(a, 'REQUEST')
    return act(a, 'APPROVE')


def assignment(a, principal='executor-a'):
    f, parent, _, _, _ = a
    with f[1].connect() as c:
        return c.execute('SELECT * FROM run_assignments WHERE principal_id=%s AND run_id=%s',
                         (principal, parent['run_id'])).fetchone()


def allowed(a, store=None):
    f, parent, _, _, _ = a
    store = store or f[0]
    with store.connect() as c:
        p = store.auth(c, f[2]['executor-a'], lock=True)
        return store.assignment_allowed(c, p, parent['run_id'])


def test_default_disabled_has_no_database_or_journal_effect(tmp_path):
    class NoDatabase:
        def connect(self):
            raise AssertionError('disabled constructor must not connect')
    path = tmp_path / 'disabled.run-access.candidate.sqlite3'
    bridge = IsolatedRunAccessBridge(NoDatabase(), None, path, approver_ids=set())
    assert not bridge.status('unused')['enabled'] and not path.exists()


@pytest.mark.parametrize('invalid', ['copy', 'manual', 'subtype', 'native', 'absent'])
def test_unissued_proof_refused_before_schema_and_journal(receipt_fixture, tmp_path, invalid):
    owner = receipt_fixture[1]
    proof = owner._case_fact_fixture_receipt
    if invalid == 'copy':
        proof = copy(proof)
    elif invalid == 'manual':
        proof = facts.FixtureDatabaseEvidence(proof.cluster, proof.database_name, proof.database_oid, uuid4())
    elif invalid == 'subtype':
        class Subtype(facts.FixtureDatabaseEvidence):
            pass
        proof = Subtype(proof.cluster, proof.database_name, proof.database_oid, proof.nonce)
    elif invalid == 'native':
        proof = NativeDatabaseCreationEvidence(proof.database_oid, proof.database_name,
            proof.cluster.owner, proof.cluster.system_identifier, proof.cluster.data_directory,
            proof.cluster.postmaster_start, uuid4(), uuid4(), 1)
    else:
        proof = None
    path = tmp_path / 'denied.run-access.candidate.sqlite3'
    with pytest.raises(Denied, match='issued fresh owned temporary fixture proof'):
        IsolatedRunAccessBridge(owner, proof, path, approver_ids={APPROVER}, enabled_for_isolated_tests=True)
    assert not path.exists()
    with owner.connect() as c:
        assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='run_assignments' AND column_name='managed_access'").fetchone()


def test_existing_reviewer_is_not_implicitly_access_approver(receipt_fixture, tmp_path):
    f = receipt_fixture
    with pytest.raises(Denied, match='explicit bounded isolated access contract'):
        IsolatedRunAccessBridge(f[1], f[1]._case_fact_fixture_receipt,
            tmp_path / 'missing.run-access.candidate.sqlite3', approver_ids=set(), enabled_for_isolated_tests=True)
    with pytest.raises(Denied, match='explicit existing synthetic access approver'):
        IsolatedRunAccessBridge(f[1], f[1]._case_fact_fixture_receipt,
            tmp_path / 'owner.run-access.candidate.sqlite3', approver_ids={'fixture-a'}, enabled_for_isolated_tests=True)


def test_request_independent_approval_actual_assignment_and_revoke(access_fixture):
    a = access_fixture
    f, parent, bridge, _, before = a
    assert assignment(a) is None
    initial = view(a)
    assert initial['case_id'] == parent['case_id'] and initial['can_request'] and not initial['actual_run_access']
    requested = act(a, 'REQUEST')
    assert requested['state'] == 'REQUESTED' and assignment(a) is None
    approved_view = act(a, 'APPROVE')
    assert approved_view['state'] == 'APPROVED' and approved_view['actual_run_access']
    assert approved_view['projection_state'] == 'APPLIED' and allowed(a)
    assert assignment(a)['managed_access']['namespace'] == NAMESPACE
    assert permission_snapshot(f[1]) == before
    revoked = act(a, 'REVOKE')
    assert revoked['state'] == 'REVOKED' and not revoked['actual_run_access'] and not allowed(a)
    assert assignment(a)['active'] is False
    assert [event['action'] for event in revoked['history']] == ['REQUEST', 'APPROVE', 'REVOKE']
    assert permission_snapshot(f[1]) == before


@pytest.mark.parametrize('user', ['fixture-b', 'fixture-c', 'executor-b', 'executor-c', 'prep-specialist-fixture-b'])
def test_cross_tenant_access_decisions_refused(access_fixture, user):
    f, parent, bridge, _, _ = access_fixture
    with pytest.raises(Denied):
        bridge.read(f[2][user], parent['run_id'])
    with pytest.raises(Denied):
        bridge.command(f[2][user], parent['run_id'], uuid4().hex, body(access_fixture, 'REQUEST'))
    assert assignment(access_fixture) is None


@pytest.mark.parametrize('user,action', [('fixture-a', 'APPROVE'), ('executor-a', 'APPROVE'), ('executor-a', 'REQUEST')])
def test_no_self_approval_or_beneficiary_request(access_fixture, user, action):
    a = access_fixture
    act(a, 'REQUEST')
    data = body(a, action, APPROVER if action == 'APPROVE' else 'fixture-a')
    with pytest.raises(Denied):
        act(a, action, user=user, data=data)
    assert assignment(a) is None


def test_managed_without_provider_denied_and_legacy_unchanged(access_fixture):
    a = access_fixture
    approved(a)
    assert not allowed(a, Store(a[0][0].dsn))
    f, parent, _, _, _ = a
    f[1].assign_status('unassigned', UUID(parent['run_id']))
    with Store(f[0].dsn).connect() as c:
        p = f[0].auth(c, f[2]['unassigned'], lock=True)
        assert Store(f[0].dsn).assignment_allowed(c, p, parent['run_id'])
    with pytest.raises(Denied, match='managed assignment'):
        f[1].assign_status('executor-a', UUID(parent['run_id']), active=False)


def test_legacy_assignment_cannot_be_taken_over(access_fixture):
    a = access_fixture
    f, parent, _, _, _ = a
    f[1].assign_status('executor-a', UUID(parent['run_id']))
    old = assignment(a)
    act(a, 'REQUEST')
    with pytest.raises(Conflict, match='legacy assignment protected'):
        act(a, 'APPROVE')
    assert assignment(a) == old and view(a)['state'] == 'REQUESTED'


def test_failed_pg_approval_projection_stays_closed_and_same_key_recovers(access_fixture, monkeypatch):
    a = access_fixture
    act(a, 'REQUEST')
    data, key = body(a, 'APPROVE'), uuid4().hex
    bridge = a[2]
    real = bridge._project
    monkeypatch.setattr(bridge, '_project', lambda *args: (_ for _ in ()).throw(Conflict('SYNTHETIC projection failed')))
    with pytest.raises(ProjectionPending) as pending:
        act(a, 'APPROVE', key=key, data=data)
    assert pending.value.decision_committed and pending.value.projection_pending
    assert view(a)['state'] == 'APPROVED' and view(a)['projection_state'] == 'PENDING'
    assert assignment(a) is None and not allowed(a)
    monkeypatch.setattr(bridge, '_project', real)
    recovered = act(a, 'APPROVE', key=key, data=data)
    assert recovered['actual_run_access'] and len(recovered['history']) == 2


def test_api_partial_projection_409_preserves_retry_and_audit(access_fixture, monkeypatch):
    a = access_fixture
    act(a, 'REQUEST')
    f, parent, bridge, _, _ = a
    data, key = body(a, 'APPROVE'), uuid4().hex
    original = bridge._project
    monkeypatch.setattr(bridge, '_project', lambda *args: (_ for _ in ()).throw(psycopg.errors.LockNotAvailable('SYNTHETIC busy')))
    path = '/api/runs/' + parent['run_id'] + '/access/commands'
    first = f[3].post(path, headers=headers(f[2], APPROVER, key), json=data.model_dump(mode='json'))
    assert first.status_code == 409 and first.json()['decision_committed'] and first.json()['projection_pending']
    assert assignment(a) is None and len(view(a)['history']) == 2 and not allowed(a)
    monkeypatch.setattr(bridge, '_project', original)
    replay = f[3].post(path, headers=headers(f[2], APPROVER, key), json=data.model_dump(mode='json'))
    assert replay.status_code == 200 and replay.json()['actual_run_access']
    assert len(replay.json()['history']) == 2


def test_failed_pg_revoke_projection_still_revokes_access(access_fixture, monkeypatch):
    a = access_fixture
    approved(a)
    data, key = body(a, 'REVOKE'), uuid4().hex
    bridge = a[2]
    real = bridge._project
    monkeypatch.setattr(bridge, '_project', lambda *args: (_ for _ in ()).throw(Conflict('SYNTHETIC projection failed')))
    with pytest.raises(Conflict):
        act(a, 'REVOKE', key=key, data=data)
    assert assignment(a)['active'] is True and not allowed(a)
    assert view(a)['state'] == 'REVOKED'
    monkeypatch.setattr(bridge, '_project', real)
    assert act(a, 'REVOKE', key=key, data=data)['state'] == 'REVOKED'
    assert assignment(a)['active'] is False


@pytest.mark.parametrize('field,value', [('namespace', 'FOREIGN'), ('lease_id', 'other'), ('authority_sha256', '0' * 64)])
def test_changed_managed_row_not_touched_by_revoke(access_fixture, field, value):
    a = access_fixture
    approved(a)
    original = assignment(a)
    metadata = dict(original['managed_access'], **{field: value})
    with a[0][1].connect() as c:
        c.execute('UPDATE run_assignments SET managed_access=%s WHERE principal_id=%s AND run_id=%s',
                  (Jsonb(metadata), 'executor-a', a[1]['run_id']))
    changed = assignment(a)
    assert not allowed(a)
    with pytest.raises(ProjectionPending):
        act(a, 'REVOKE')
    assert assignment(a) == changed


def test_old_approve_cannot_restore_after_revoke_or_new_lease(access_fixture):
    a = access_fixture
    act(a, 'REQUEST')
    data, key = body(a, 'APPROVE'), uuid4().hex
    first = act(a, 'APPROVE', data=data, key=key)
    act(a, 'REVOKE')
    with pytest.raises(Conflict):
        act(a, 'APPROVE', data=data, key=key)
    act(a, 'REQUEST')
    latest = act(a, 'APPROVE')
    assert latest['lease_id'] != first['lease_id'] and allowed(a)
    stable = assignment(a)
    with pytest.raises(Conflict):
        act(a, 'APPROVE', data=data, key=key)
    assert assignment(a) == stable


def test_ttl_expiry_blocks_read_and_cached_approval_replay(access_fixture):
    a = access_fixture
    act(a, 'REQUEST')
    data, key = body(a, 'APPROVE'), uuid4().hex
    act(a, 'APPROVE', data=data, key=key)
    a[3][0] += timedelta(minutes=11)
    assert not allowed(a) and not view(a)['actual_run_access']
    with pytest.raises((Denied, Conflict)):
        act(a, 'APPROVE', data=data, key=key)


def test_guarded_commit_rolls_back_when_lease_expires(access_fixture):
    a = access_fixture
    approved(a)
    f, parent, _, now, _ = a
    event_id = uuid4()
    with pytest.raises(Denied, match='managed access expired or changed'):
        with f[0].connect() as c:
            p = f[0].auth(c, f[2]['executor-a'], lock=True)
            f[0].scoped_run(c, p, UUID(parent['run_id']))
            c.execute("INSERT INTO authorization_audit(id,principal_id,category,outcome) VALUES(%s,%s,'SYNTHETIC_COMMIT_TEST','ALLOWED')", (event_id, p['id']))
            now[0] += timedelta(minutes=11)
    with f[1].connect() as c:
        assert not c.execute('SELECT 1 FROM authorization_audit WHERE id=%s', (event_id,)).fetchone()


def test_managed_autocommit_cannot_skip_final_transaction_guard(access_fixture):
    a = access_fixture
    approved(a)
    with a[0][0].connect() as c:
        c.autocommit = True
        p = a[0][0].auth(c, a[0][2]['executor-a'])
        assert not a[0][0].assignment_allowed(c, p, a[1]['run_id'])


def test_short_lease_expiry_can_revoke_and_request_again_within_fixed_session(access_fixture):
    a = access_fixture
    a[2].max_access_seconds = 60  # Before this Run's first contract is created.
    deadline = a[2].authority_validity.valid_until
    now = a[3][0]
    short = dict(valid_from=now.isoformat(), valid_until=(now + timedelta(seconds=60)).isoformat(), timezone='UTC')
    act(a, 'REQUEST', requested_validity=short)
    first = act(a, 'APPROVE')
    a[3][0] += timedelta(seconds=70)
    assert not allowed(a)
    act(a, 'REVOKE')
    later = a[3][0]
    act(a, 'REQUEST', requested_validity=dict(valid_from=later.isoformat(), valid_until=(later + timedelta(seconds=60)).isoformat(), timezone='UTC'))
    second = act(a, 'APPROVE')
    assert second['lease_id'] != first['lease_id'] and allowed(a)
    assert view(a)['authority_valid_until'] == deadline
    a[3][0] += timedelta(hours=8)
    assert not a[2].status(a[0][2][APPROVER])['can_approve'] and not allowed(a)


def test_current_read_revision_drift_and_restore_never_revives_old_approval(access_fixture):
    a = access_fixture
    approved(a)
    a[0][1].revoke_capability('executor-a', 'READ')
    assert not allowed(a)
    with a[0][1].connect() as c:
        c.execute("UPDATE capability_grants SET active=true WHERE principal_id='executor-a' AND capability='READ'")
    assert not allowed(a) and not view(a)['actual_run_access']


def test_run_revision_drift_and_sqlite_unavailable_fail_closed(access_fixture, monkeypatch):
    a = access_fixture
    approved(a)
    with a[0][1].connect() as c:
        c.execute('UPDATE runs SET revision=revision+1 WHERE id=%s', (a[1]['run_id'],))
    assert not allowed(a)
    view(a)  # Observed contract replacement never re-enables the old lease.
    assert not allowed(a)
    monkeypatch.setattr(a[2].repository, 'connect', lambda *args, **kwargs: (_ for _ in ()).throw(candidate.Conflict('busy')))
    assert not allowed(a)


def test_audit_immutable_and_same_key_approval_concurrency(access_fixture):
    a = access_fixture
    act(a, 'REQUEST')
    data, key = body(a, 'APPROVE'), uuid4().hex
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: act(a, 'APPROVE', key=key, data=data), range(2)))
    assert all(result['actual_run_access'] for result in results)
    assert len(view(a)['history']) == 2
    with sqlite3.connect(a[2].repository.path) as c:
        with pytest.raises(sqlite3.IntegrityError, match='immutable candidate audit'):
            c.execute('UPDATE access_events SET payload=payload')
        with pytest.raises(sqlite3.IntegrityError, match='immutable candidate audit'):
            c.execute('DELETE FROM access_events')


def test_actual_same_case_dispatch_accept_receipt_and_revocation(access_fixture):
    a = access_fixture
    f, parent, _, _, before = a
    approved(a)
    prep_path = '/api/preparations/' + parent['preparation_id']
    before_path = f[3].get(prep_path + '/case-path', headers=headers(f[2]))
    assert before_path.status_code == 200, before_path.text
    assert before_path.json()['existing_run_access']['candidate_available']
    before_planning = f[3].get(prep_path + '/planning-preview', headers=headers(f[2]))
    assert before_planning.status_code == 200, before_planning.text
    planning_sha = before_planning.json()['current']['source_sha256']
    for path, user in [('/api/executor-receipts/catalog?preparation_id=' + parent['preparation_id'], 'fixture-a'),
                       ('/api/service-dispatches/catalog?preparation_id=' + parent['preparation_id'], APPROVER)]:
        catalog = f[3].get(path, headers=headers(f[2], user))
        assert catalog.status_code == 200 and catalog.json()['executors'] == [{'id': 'executor-a'}]
    offer = f[3].post('/api/preparations/' + parent['preparation_id'] + '/dispatch', headers=headers(f[2], APPROVER, uuid4().hex),
        json=dict(expected_preparation_revision=parent['revision'],
                  expected_dispatch_revision=0, executor_id='executor-a', reason='SYNTHETIC explicit offer after approval'))
    assert offer.status_code == 201, offer.text
    offered = offer.json()
    accept = f[3].post('/api/service-dispatches/' + offered['dispatch_id'] + '/commands',
        headers=headers(f[2], 'executor-a', uuid4().hex),
        json=dict(action='ACCEPT', expected_revision=offered['revision'], reason='SYNTHETIC own acceptance'))
    assert accept.status_code == 200, accept.text
    receipt_id = accept.json()['receipt_step_id']
    submitted = f[3].post('/api/executor-receipts/' + receipt_id + '/commands',
        headers=headers(f[2], 'executor-a', uuid4().hex),
        json=dict(action='SUBMIT', expected_revision=1, text='SYNTHETIC local work log',
                  source_kind='SYNTHETIC', source_label='SYNTHETIC v1'))
    assert submitted.status_code == 200, submitted.text
    submitted_row = submitted.json()
    acknowledged = f[3].post('/api/executor-receipts/' + receipt_id + '/commands',
        headers=headers(f[2], 'fixture-a', uuid4().hex),
        json=dict(action='ACKNOWLEDGE', expected_revision=submitted_row['step']['revision'],
                  receipt_sha256=submitted_row['current_receipt']['source_sha256'], reason='SYNTHETIC local current receipt check'))
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()['step']['state'] == 'LOCAL_ACKNOWLEDGED' and not acknowledged.json()['case_goal_completed']
    act(a, 'REVOKE')
    assert f[3].get('/api/executor-receipts/' + receipt_id, headers=headers(f[2], 'executor-a')).status_code == 403
    assert f[3].get('/api/executor-receipts', headers=headers(f[2], 'executor-a')).json()['items'] == []
    assert f[3].get('/api/service-dispatches', headers=headers(f[2], 'executor-a')).json()['items'] == []
    assert f[3].get('/api/executor-receipts/' + receipt_id, headers=headers(f[2])).status_code == 200
    assert not f[3].get(prep_path + '/case-path', headers=headers(f[2])).json()['existing_run_access']['candidate_available']
    after_planning = f[3].get(prep_path + '/planning-preview', headers=headers(f[2]))
    assert after_planning.status_code == 200 and after_planning.json()['current']['source_sha256'] != planning_sha
    preview = f[3].post(prep_path + '/controlled-plan/preview', headers=headers(f[2]),
                       json={'required_goals': ['LOCAL_SYNTHETIC_COORDINATION_RECORDS']})
    assert preview.status_code == 200, preview.text
    p3 = next(step for step in preview.json()['steps'] if step['id'] == 'P3')
    assert 'EXISTING_RUN_ASSIGNMENT_REQUIRED' in p3['issues']
    for path, user in [('/api/executor-receipts/catalog?preparation_id=' + parent['preparation_id'], 'fixture-a'),
                       ('/api/service-dispatches/catalog?preparation_id=' + parent['preparation_id'], APPROVER)]:
        assert f[3].get(path, headers=headers(f[2], user)).json()['executors'] == []
    assert permission_snapshot(f[1]) == before
