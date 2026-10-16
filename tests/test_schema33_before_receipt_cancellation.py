"""Owned schema33 accepted/manual cancellation; direct modules and real ASGI only."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4
import threading
import psycopg
import pytest

from parkweave import business_frontier as bf, preparation as prep, case_cancellation as cc
from parkweave import case_cancellation_before_receipt as cancellation
from parkweave import executor_receipts as er, service_dispatches as sd
from parkweave.store import Store, Conflict, Denied
from test_preparation import preparation_fixture, headers, command as material
from test_executor_receipts import receipt_fixture, ready, act
from test_service_capability_catalog_actual import capability_catalog, capability_resource_catalog
from test_plan_replacement_reapproval import bind_all, generate
from test_new_enterprise_local_chain import ALL_GOALS
from test_request_intents import save
from test_service_case_steps import verified
from test_resource_bundles import bundle, states
from test_case_resource_delivery import quoted, submit
from test_service_plan_approval import enable, approved
from test_service_dispatches import offer, command as dispatch
from test_case_cancellation import snapshot as original_snapshot, wait_for_pg_lock
from test_case_cancellation_before_receipt import get, body, post, recover


from cancel33_fixture_support import cancel33_case


def snapshot(f):
    result = original_snapshot(f)
    with f[1].connect() as c:
        for table in ('run_assignments', 'synthetic_resource_receipts', 'outbox',
                      'dispatch_notice_outbox', 'dispatch_notices'):
            result[table] = sorted(c.execute('SELECT row_to_json(x) r FROM ' + table + ' x').fetchall(),
                key=lambda row: prep.canonical(row))
    return result


@pytest.fixture
def accepted_schema33(cancel33_case):
    return cancel33_case

def cancel_body(x):
    f, p = x['f'], x['p']
    r = get(f, p)
    assert r.status_code == 200, r.text
    value = r.json()
    assert value['can_cancel'], value
    result = body(f, p)
    result['expected_business_frontier'] = deepcopy(value['business_frontier'])
    return result


def receipt_body(x):
    f, d = x['f'], x['d']
    r = f[3].get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], 'executor-a'))
    assert r.status_code == 200, r.text
    value = r.json()
    return dict(action='SUBMIT', expected_revision=value['step']['revision'],
        text='SYNTHETIC actual first manual receipt', source_kind='SYNTHETIC',
        source_label='SYNTHETIC original executor', expected_business_frontier=value['business_frontier'])


def receipt_post(x, data):
    return x['f'][3].post('/api/executor-receipts/' + x['d']['receipt_step_id'] + '/commands',
        headers=headers(x['f'][2], 'executor-a', uuid4().hex), json=data)


def stable_after_cancel(before, after):
    for table in before:
        if table not in ('cases', 'case_local_lifecycles', 'case_local_events', 'preparations'):
            assert after[table] == before[table], table
    before_parents = {r['r']['id']: deepcopy(r['r']) for r in before['preparations']}
    after_parents = {r['r']['id']: deepcopy(r['r']) for r in after['preparations']}
    assert before_parents.keys() == after_parents.keys()
    changed = [id for id in before_parents if before_parents[id] != after_parents[id]]
    assert len(changed) == 1
    before_parent, after_parent = before_parents[changed[0]], after_parents[changed[0]]
    old_marker = before_parent.pop('candidate_business_frontier')
    new_marker = after_parent.pop('candidate_business_frontier')
    assert before_parent == after_parent
    assert new_marker['epoch'] == old_marker['epoch'] + 2
    assert new_marker['events'][:old_marker['epoch']] == old_marker['events']
    additions = new_marker['events'][old_marker['epoch']:]
    assert [(e['table'], e['operation'], e['revision']) for e in additions] == [
        ('case_local_lifecycles', 'INSERT', old_marker['epoch'] + 1),
        ('case_local_events', 'INSERT', old_marker['epoch'] + 2)]
    assert additions[0]['record_id'] == str(before_parent['id'])
    new_events = {r['r']['id'] for r in after['case_local_events']} - {r['r']['id'] for r in before['case_local_events']}
    assert new_events == {additions[1]['record_id']}
    assert additions[0]['transaction'] == additions[1]['transaction']
    for marker in (old_marker, new_marker):
        marker.pop('epoch')
        marker.pop('events')
    assert old_marker == new_marker


def test_schema33_cancel_keeps_original_six_goals_occupancy_responsibility_and_cold_original_key(accepted_schema33):
    x = accepted_schema33
    f, p = x['f'], x['p']
    data = cancel_body(x)
    key = uuid4().hex
    before = snapshot(f)
    r = post(f, p, data, key)
    assert r.status_code == 200, r.text
    committed = snapshot(f)
    stable_after_cancel(before, committed)
    assert states(f, x['hs']) == ['CONFIRMED'] * len(x['hs'])
    # Simulated lost transport response: reconstruct Store and use only original GET recovery.
    with pytest.raises(Denied, match='issued frontier protocol must remain attached'):
        cancellation.recover(Store(f[0].dsn), f[2]['fixture-a'], UUID(p['preparation_id']), key)
    recovered = cancellation.recover(x['protocol'].attach_store(x['bridge'].attach_store(Store(f[0].dsn))), f[2]['fixture-a'], UUID(p['preparation_id']), key)
    assert recovered['event_id'] == r.json()['event_id']
    assert recovered['current']['case_state'] == 'CANCELLED'
    assert recovered['current']['resource_release_automatic'] is False
    assert recovered['current']['restore_supported'] is False
    assert recovered['current']['case_goal_completed'] is False
    assert post(f, p, data, key).json() == r.json()
    assert post(f, p, {**data, 'reason': 'SYNTHETIC changed parameters'}, key).status_code == 409
    assert recover(f, p, uuid4().hex).json()['status'] == 'NOT_OBSERVED'
    assert post(f, p, data).status_code == 409
    assert snapshot(f) == committed


@pytest.mark.parametrize('user', ['fixture-b', 'fixture-c', 'prep-specialist-fixture-a', 'executor-a', 'unassigned'])
def test_schema33_owner_tenant_role_rechecked_for_all_cancel_routes(accepted_schema33, user):
    x = accepted_schema33
    f, p = x['f'], x['p']
    data = cancel_body(x)
    key = uuid4().hex
    before = snapshot(f)
    assert get(f, p, user).status_code == 403
    assert post(f, p, data, key, user).status_code == 403
    assert recover(f, p, key, user).status_code == 403
    assert snapshot(f) == before


@pytest.mark.parametrize('cap', ['READ', 'PREPARE', 'EXECUTE', 'INACTIVE'])
def test_schema33_revocation_applies_to_original_key_and_read_only_recovery(accepted_schema33, cap):
    x = accepted_schema33
    f, p = x['f'], x['p']
    data, key = cancel_body(x), uuid4().hex
    r = post(f, p, data, key)
    assert r.status_code == 200, r.text
    with f[1].connect() as c:
        f[1].lock_principal(c, 'fixture-a', exclusive=True)
        if cap == 'INACTIVE':
            c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif cap == 'PREPARE':
            c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        else:
            c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s', ('fixture-a', cap))
    before = snapshot(f)
    assert post(f, p, data, key).status_code == 403
    assert recover(f, p, key).status_code == (200 if cap == 'EXECUTE' else 403)
    assert snapshot(f) == before


def test_schema33_event_failure_rolls_back_case_lifecycle_frontier_and_all_resources(accepted_schema33, monkeypatch):
    x = accepted_schema33
    f, p = x['f'], x['p']
    data, before = cancel_body(x), snapshot(f)
    original = cc._commit
    reached = []
    class InjectedCancellationFault(Exception):
        pass
    def fail_after_all_writes(c, *args, **kwargs):
        result = original(c, *args, **kwargs)
        assert c.execute("SELECT state FROM cases WHERE id=%s", (p['case_id'],)).fetchone()['state'] == 'CANCELLED'
        assert c.execute("SELECT count(*) n FROM case_local_events WHERE action='CANCEL_BEFORE_RECEIPT'").fetchone()['n'] == 1
        reached.append(result)
        raise InjectedCancellationFault('SYNTHETIC failure after all cancellation writes before commit')
    monkeypatch.setattr(cc, '_commit', fail_after_all_writes)
    with pytest.raises(InjectedCancellationFault):
        cancellation.cancel(f[0], f[2]['fixture-a'], UUID(p['preparation_id']), uuid4().hex,
            cancellation.Cancel.model_validate(data))
    assert len(reached) == 1
    assert snapshot(f) == before


def test_schema33_cancellation_first_real_parent_lock_serializes_and_refuses_first_submit(accepted_schema33):
    x = accepted_schema33
    f, p = x['f'], x['p']
    verified(f, p, 'P3')
    cancel_request, submit_request = cancel_body(x), receipt_body(x)
    results = []
    def record(kind, response):
        results.append((kind, response.status_code, response.json()))
    with f[1].connect() as blocker:
        blocker.execute('SELECT * FROM cases WHERE id=%s FOR UPDATE', (p['case_id'],))
        cancel_thread = threading.Thread(target=lambda: record('cancel', post(f, p, cancel_request)))
        cancel_thread.start()
        wait_for_pg_lock(f, 'SELECT * FROM cases WHERE id=')
        receipt_thread = threading.Thread(target=lambda: record('submit', receipt_post(x, submit_request)))
        receipt_thread.start()
        wait_for_pg_lock(f, 'FROM preparations WHERE id=')
    cancel_thread.join(6)
    receipt_thread.join(6)
    assert not cancel_thread.is_alive() and not receipt_thread.is_alive()
    assert sorted((kind, status) for kind, status, _ in results) == [('cancel', 200), ('submit', 409)], results
    after = snapshot(f)
    assert not after['service_step_receipts']
    assert len(after['case_local_events']) == 1


def test_schema33_first_submit_wins_real_parent_lock_then_cancel_rechecks_whole_history(accepted_schema33, monkeypatch):
    x = accepted_schema33
    f, p = x['f'], x['p']
    verified(f, p, 'P3')
    cancel_request, submit_request = cancel_body(x), receipt_body(x)
    entered, release = threading.Event(), threading.Event()
    results, once = [], []
    def record(kind, response):
        results.append((kind, response.status_code, response.json()))
    original = prep.case_write_guard
    def pause(c, parent):
        original(c, parent)
        if not once:
            once.append(True)
            entered.set()
            assert release.wait(5)
    monkeypatch.setattr(prep, 'case_write_guard', pause)
    receipt_thread = threading.Thread(target=lambda: record('submit', receipt_post(x, submit_request)))
    receipt_thread.start()
    assert entered.wait(3)
    cancel_thread = threading.Thread(target=lambda: record('cancel', post(f, p, cancel_request)))
    cancel_thread.start()
    try:
        wait_for_pg_lock(f, 'FROM preparations WHERE id=')
    finally:
        release.set()
    receipt_thread.join(6)
    cancel_thread.join(6)
    assert not cancel_thread.is_alive() and not receipt_thread.is_alive()
    assert sorted((kind, status) for kind, status, _ in results) == [('cancel', 409), ('submit', 200)], results
    current = get(f, p).json()
    assert current['case_state'] != 'CANCELLED' and not current['can_cancel']
    assert 'HISTORICAL_RECEIPT_SUBMISSION_NOT_SUPPORTED' in current['blockers']
    assert post(f, p).status_code == 409
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_step_receipts').fetchone()['n'] == 1
        assert c.execute('SELECT count(*) n FROM case_local_events').fetchone()['n'] == 0


def test_schema33_direct_module_writers_refused_after_committed_cancel(accepted_schema33):
    x = accepted_schema33
    f, p, d = x['f'], x['p'], x['d']
    cancel_request, submit_request = cancel_body(x), receipt_body(x)
    r = post(f, p, cancel_request)
    assert r.status_code == 200, r.text
    before = snapshot(f)
    with pytest.raises(Conflict, match='Case cancelled'):
        er.command(x['protocol'].attach_store(x['bridge'].attach_store(Store(f[0].dsn))), f[2]['executor-a'], UUID(d['receipt_step_id']), uuid4().hex,
            er.Command.model_validate(submit_request))
    with pytest.raises(Conflict, match='Case cancelled'):
        sd.command(x['protocol'].attach_store(x['bridge'].attach_store(Store(f[0].dsn))), f[2]['executor-a'], UUID(d['dispatch_id']), uuid4().hex,
            sd.Command(action='ACCEPT', expected_revision=d['revision'], reason='SYNTHETIC late direct writer',
                expected_business_frontier=d['business_frontier']))
    assert snapshot(f) == before


def test_schema33_managed_assignment_remains_ineligible_without_source_mutation(accepted_schema33):
    x = accepted_schema33
    f, p = x['f'], x['p']
    data = cancel_body(x)
    with f[1].connect() as c:
        c.execute("ALTER TABLE run_assignments ADD COLUMN managed_access jsonb")
        c.execute("UPDATE run_assignments SET managed_access='{}'::jsonb WHERE run_id=%s AND principal_id='executor-a'", (p['run_id'],))
    before = snapshot(f)
    view = get(f, p)
    assert view.status_code == 200, view.text
    assert not view.json()['can_cancel']
    assert 'ISOLATED_RUN_ACCESS_NOT_SUPPORTED' in view.json()['blockers']
    assert post(f, p, data).status_code == 409
    assert snapshot(f) == before
