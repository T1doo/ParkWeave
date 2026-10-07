"""Real owned-fixture PG/API local report; no external or physical effect."""
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from datetime import timedelta
import hashlib
import json
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from parkweave import executor_receipts as er
from parkweave import isolated_local_execution as local
from parkweave.api import create_app
from parkweave.installed_fixture_receipt import NativeDatabaseCreationEvidence
from parkweave.store import Conflict, Denied, Store
from test_isolated_run_access import (access_fixture, approved, act as access_act,
                                      permission_snapshot, APPROVER)
# Imported explicitly for pytest's dependency resolution; no alternate seed path.
from test_executor_receipts import receipt_fixture, act as receipt_act
from test_preparation import preparation_fixture, headers, command as prep_act
from test_service_dispatches import offer, command as dispatch_act


def receipt_read(f, step_id, user='fixture-a', api=None):
    return (api or f[3]).get('/api/executor-receipts/' + str(step_id), headers=headers(f[2], user))


def accepted(a):
    f, parent, _, _, _ = a
    approved(a)
    response = offer(f, parent)[0]
    assert response.status_code == 201, response.text
    response = dispatch_act(f, response.json(), 'ACCEPT')
    assert response.status_code == 200, response.text
    dispatch = response.json()
    response = receipt_read(f, dispatch['receipt_step_id'], 'executor-a')
    assert response.status_code == 200, response.text
    return dispatch, response.json()


@pytest.fixture
def local_fixture(access_fixture):
    a = access_fixture
    adapter = local.IsolatedLocalExecutor(a[2], enabled_for_isolated_tests=True)
    adapter.attach_store(a[0][0])
    dispatch, row = accepted(a)
    assert permission_snapshot(a[0][1]) == a[4]
    return a, adapter, dispatch, row


def execute(f, row, user='executor-a', key=None, body=None, api=None):
    body = body or dict(expected_revision=row['step']['revision'], reason='SYNTHETIC explicit local report')
    return (api or f[3]).post('/api/executor-receipts/' + str(row['step']['id']) + '/execute-local',
                            headers=headers(f[2], user, key or uuid4().hex), json=body)


def effects(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT row_to_json(t) row FROM ' + table + ' t ORDER BY row_to_json(t)::text').fetchall()
                for table in ('service_receipt_steps', 'service_step_receipts', 'service_receipt_events')}


def successful(f, row, **kwargs):
    response = execute(f, row, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def current_view(f, row):
    response = receipt_read(f, row['step']['id'])
    assert response.status_code == 200, response.text
    return response.json()


def renew(a):
    access_act(a, 'REQUEST')
    return access_act(a, 'APPROVE')


def test_disabled_constructor_does_not_touch_a_bridge_or_database():
    class Unavailable:
        def __getattribute__(self, name):
            raise AssertionError('disabled constructor must not inspect bridge')
    value = local.IsolatedLocalExecutor(Unavailable())
    assert not value.enabled
    with pytest.raises(Denied):
        value.attach_store(object())


@pytest.mark.parametrize('proof_kind', ['copied', 'absent', 'native'])
def test_unissued_and_native_proof_cannot_enable_local_schema(access_fixture, proof_kind):
    a = access_fixture
    bridge = copy(a[2])
    proof = bridge.proof
    if proof_kind == 'copied':
        bridge.proof = copy(proof)
    elif proof_kind == 'absent':
        bridge.proof = None
    else:
        bridge.proof = NativeDatabaseCreationEvidence(proof.database_oid, proof.database_name,
            proof.cluster.owner, proof.cluster.system_identifier, proof.cluster.data_directory,
            proof.cluster.postmaster_start, uuid4(), uuid4(), 1)
    before = permission_snapshot(a[0][1])
    with pytest.raises(Denied):
        local.IsolatedLocalExecutor(bridge, enabled_for_isolated_tests=True)
    with a[0][1].connect() as c:
        assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='service_step_receipts' AND column_name='adapter_execution'").fetchone()
    assert permission_snapshot(a[0][1]) == before


def test_existing_accepted_step_without_adapter_cannot_execute(access_fixture, monkeypatch):
    f = access_fixture[0]
    _, row = accepted(access_fixture)
    before = effects(f)
    from parkweave import controlled_plans
    def unexpected_gate(*args, **kwargs):
        raise AssertionError('disabled execution must refuse before plan gate')
    monkeypatch.setattr(controlled_plans, 'gate', unexpected_gate)
    assert execute(f, row).status_code == 403
    assert effects(f) == before
    assert permission_snapshot(f[1]) == access_fixture[4]


def test_actual_report_exact_binding_hash_uuid_persistence_rebuild_and_owner_ack(local_fixture):
    a, adapter, dispatch, row = local_fixture
    f, parent, bridge, _, before = a
    result = successful(f, row)
    receipt = result['current_receipt']
    metadata = receipt['adapter_execution']
    report = metadata['report']
    assert result['step']['state'] == 'RECEIPT_RECORDED'
    assert result['local_execution']['current'] and not result['local_execution']['can_execute']
    assert report['adapter_id'] == local.ADAPTER_ID and report['effect'] == local.EFFECT
    assert str(UUID(report['execution_id'])) == report['execution_id']
    assert str(UUID(str(receipt['id']))) == str(receipt['id'])
    assert report['binding']['step_id'] == str(result['step']['id'])
    assert report['binding']['offer_id'] == dispatch['current_offer']['id']
    assert report['binding']['run_id'] == parent['run_id'] and report['binding']['case_id'] == parent['case_id']
    assert report['binding']['executor_id'] == 'executor-a'
    assert receipt['text'] == json.dumps(report, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    assert hashlib.sha256(receipt['text'].encode()).hexdigest() == receipt['source_sha256']
    assert report['external_acceptance'] == 'NOT_SUBMITTED' and report['offline_fulfillment'] == 'NO_EVIDENCE'
    assert not report['case_goal_completed'] and not result['case_goal_completed']
    submits = [event for event in result['history'] if event['action'] == 'SUBMIT']
    assert len(submits) == 1 and submits[0]['payload']['adapter_execution'] == metadata
    assert submits[0]['payload']['receipt_id'] == str(receipt['id'])
    reconstructed = Store(f[0].dsn)
    bridge.attach_store(reconstructed)
    local.IsolatedLocalExecutor(bridge, enabled_for_isolated_tests=True).attach_store(reconstructed)
    with TestClient(create_app(reconstructed)) as api:
        reread = receipt_read(f, row['step']['id'], 'executor-a', api).json()
        assert reread['current_receipt'] == receipt and reread['local_execution']['current']
    ack = receipt_act(f, result, 'ACKNOWLEDGE')
    assert ack.status_code == 200, ack.text
    assert ack.json()['step']['state'] == 'LOCAL_ACKNOWLEDGED' and ack.json()['local_execution']['current']
    assert permission_snapshot(f[1]) == before


@pytest.mark.parametrize('user', ['fixture-a', APPROVER, 'unassigned', 'executor-b', 'executor-c', 'fixture-b'])
def test_wrong_role_unassigned_and_cross_tenant_have_zero_local_effect(local_fixture, user):
    a, _, _, row = local_fixture
    f = a[0]
    before = effects(f)
    assert execute(f, row, user=user).status_code == 403
    assert effects(f) == before and permission_snapshot(f[1]) == a[4]


def test_disabled_local_command_refuses_before_any_database_connection():
    class NoDatabase:
        def connect(self):
            raise AssertionError('disabled execution must not connect')
    data = local.ExecuteLocal(expected_revision=1, reason='SYNTHETIC explicit disabled request')
    with pytest.raises(Denied, match='disabled'):
        er.command(NoDatabase(), 'unused-token', uuid4(), uuid4().hex, data)


def test_same_key_lost_reply_exact_retry_and_body_conflict_one_report(local_fixture):
    a, _, _, row = local_fixture
    f = a[0]
    body = dict(expected_revision=row['step']['revision'], reason='SYNTHETIC original retry body')
    key = uuid4().hex
    first = successful(f, row, key=key, body=body)
    before = effects(f)
    retry = successful(f, row, key=key, body=body)
    assert retry['event'] == first['event'] and retry['current_receipt'] == first['current_receipt']
    assert effects(f) == before
    assert execute(f, row, key=key, body={**body, 'reason': 'SYNTHETIC changed request'}).status_code == 409
    assert len(retry['receipt_history']) == 1


def test_concurrent_exact_key_commits_only_one_version(local_fixture):
    a, _, _, row = local_fixture
    f = a[0]
    key = uuid4().hex
    body = dict(expected_revision=row['step']['revision'], reason='SYNTHETIC concurrent exact request')
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: execute(f, row, key=key, body=body), range(2)))
    assert [response.status_code for response in results] == [200, 200]
    assert results[0].json()['current_receipt'] == results[1].json()['current_receipt']
    final = current_view(f, row)
    assert len(final['receipt_history']) == 1
    assert len([event for event in final['history'] if event['action'] == 'SUBMIT']) == 1


def test_failure_after_report_insert_rolls_back_receipt_and_event(local_fixture, monkeypatch):
    a, _, _, row = local_fixture
    f = a[0]
    original = er._event
    def fail_after_event(c, p, step, key, fp, action, **extra):
        value = original(c, p, step, key, fp, action, **extra)
        if action == 'SUBMIT' and extra.get('adapter_execution'):
            raise Conflict('SYNTHETIC injected post-report persistence failure')
        return value
    before = effects(f)
    monkeypatch.setattr(er, '_event', fail_after_event)
    assert execute(f, row).status_code == 409
    assert effects(f) == before
    monkeypatch.setattr(er, '_event', original)
    assert len(successful(f, row)['receipt_history']) == 1


@pytest.mark.parametrize('change', ['revoke', 'expire'])
def test_revoked_or_expired_lease_blocks_new_execution_and_old_reply_replay(local_fixture, change):
    a, _, _, row = local_fixture
    f = a[0]
    key = uuid4().hex
    body = dict(expected_revision=row['step']['revision'], reason='SYNTHETIC original lease')
    result = successful(f, row, key=key, body=body)
    if change == 'revoke':
        access_act(a, 'REVOKE')
    else:
        a[3][0] += timedelta(minutes=11)
    before = effects(f)
    assert execute(f, row, key=key, body=body).status_code in (403, 409)
    assert receipt_act(f, result, 'ACKNOWLEDGE').status_code in (403, 409)
    assert effects(f) == before
    assert not current_view(f, row)['local_execution']['current']


@pytest.mark.parametrize('change', ['revoke', 'expire'])
def test_new_lease_does_not_revive_old_report_explicit_fresh_execution_required(local_fixture, change):
    a, _, _, row = local_fixture
    f = a[0]
    key = uuid4().hex
    body = dict(expected_revision=row['step']['revision'], reason='SYNTHETIC old lease report')
    old = successful(f, row, key=key, body=body)
    if change == 'revoke':
        access_act(a, 'REVOKE')
    else:
        a[3][0] += timedelta(minutes=11)
    latest = renew(a)
    restored = current_view(f, row)
    assert restored['current_receipt'] == old['current_receipt']
    assert not restored['local_execution']['current'] and not restored['local_execution']['can_execute']
    executor_view = receipt_read(f, row['step']['id'], 'executor-a').json()
    assert not executor_view['local_execution']['current'] and executor_view['local_execution']['can_execute']
    assert executor_view['current_receipt'] == old['current_receipt']
    assert execute(f, row, key=key, body=body).status_code in (403, 409)
    assert receipt_act(f, restored, 'ACKNOWLEDGE').status_code in (403, 409)
    fresh = successful(f, executor_view)
    assert fresh['current_receipt']['version'] == 2
    assert fresh['current_receipt']['id'] != old['current_receipt']['id']
    assert fresh['current_receipt']['adapter_execution']['report']['execution_id'] != old['current_receipt']['adapter_execution']['report']['execution_id']
    assert fresh['current_receipt']['adapter_execution']['report']['binding']['managed_access'] != old['current_receipt']['adapter_execution']['report']['binding']['managed_access']
    assert latest['actual_run_access'] and receipt_act(f, fresh, 'ACKNOWLEDGE').status_code == 200
    assert len(current_view(f, row)['receipt_history']) == 2 and permission_snapshot(f[1]) == a[4]


@pytest.mark.parametrize('action', ['REQUEST_CHANGES', 'REOPEN'])
def test_owner_correction_keeps_historical_report_and_requires_fresh_output(local_fixture, action):
    a, _, _, row = local_fixture
    f = a[0]
    first = successful(f, row)
    changed = receipt_act(f, first, action)
    assert changed.status_code == 200, changed.text
    changed = changed.json()
    assert not changed['local_execution']['current'] and not changed['local_execution']['can_execute']
    assert changed['current_receipt'] == first['current_receipt']
    executor_view = receipt_read(f, row['step']['id'], 'executor-a').json()
    assert not executor_view['local_execution']['current'] and executor_view['local_execution']['can_execute']
    assert executor_view['current_receipt'] == first['current_receipt']
    assert receipt_act(f, changed, 'ACKNOWLEDGE').status_code == 409
    fresh = successful(f, executor_view)
    assert fresh['current_receipt']['version'] == 2 and fresh['local_execution']['current']
    assert receipt_act(f, fresh, 'ACKNOWLEDGE').status_code == 200


@pytest.mark.parametrize('change', ['preparation', 'offer'])
def test_changed_parent_or_current_offer_blocks_execution_without_effect(local_fixture, change):
    a, _, dispatch, row = local_fixture
    f, parent = a[:2]
    if change == 'preparation':
        assert prep_act(f, parent, 'REOPEN', reason='SYNTHETIC changed preparation').status_code == 200
    else:
        with f[1].connect() as c:
            # Preserve the original CHECK: only an ACCEPTED offer may bind a step.
            c.execute("UPDATE service_dispatch_offers SET state='WITHDRAWN',receipt_step_id=NULL WHERE id=%s",
                      (UUID(dispatch['current_offer']['id']),))
    before = effects(f)
    assert execute(f, row).status_code in (403, 409)
    assert effects(f) == before


def test_manual_source_label_cannot_prove_local_adapter_output(local_fixture):
    a, _, _, row = local_fixture
    f = a[0]
    manual = receipt_act(f, row, 'SUBMIT', text='SYNTHETIC claimed adapter report', source_label=local.ADAPTER_ID)
    assert manual.status_code == 200, manual.text
    value = manual.json()
    assert value['current_receipt'].get('adapter_execution') is None
    assert not value['local_execution']['current'] and value['local_execution']['record'] is None
    assert receipt_act(f, value, 'ACKNOWLEDGE').status_code == 200  # Legacy manual contract remains manual.


def test_provider_absent_metadata_is_readable_history_but_cannot_ack(local_fixture):
    a, _, _, row = local_fixture
    f = a[0]
    result = successful(f, row)
    reconstructed = Store(f[0].dsn)
    a[2].attach_store(reconstructed)
    with TestClient(create_app(reconstructed)) as api:
        historical = receipt_read(f, row['step']['id'], api=api)
        assert historical.status_code == 200, historical.text
        assert not historical.json()['local_execution']['enabled']
        assert not historical.json()['local_execution']['current']
        body = dict(action='ACKNOWLEDGE', expected_revision=result['step']['revision'],
                    receipt_sha256=result['current_receipt']['source_sha256'], reason='SYNTHETIC no provider')
        before = effects(f)
        response = api.post('/api/executor-receipts/' + str(row['step']['id']) + '/commands',
                            headers=headers(f[2], key=uuid4().hex), json=body)
        assert response.status_code == 409 and effects(f) == before


def test_stale_adapter_output_blocks_original_lifecycle_receipt_recheck(local_fixture):
    a, _, _, row = local_fixture
    f, parent = a[:2]
    done = successful(f, row)
    ack = receipt_act(f, done, 'ACKNOWLEDGE')
    assert ack.status_code == 200, ack.text
    path = '/api/preparations/' + parent['preparation_id'] + '/local-case'
    before = f[3].get(path, headers=headers(f[2])).json()
    assert before['checks']['RECEIPT_RECHECK'] == []
    access_act(a, 'REVOKE')
    renew(a)
    stale = f[3].get(path, headers=headers(f[2])).json()
    assert stale['checks']['RECEIPT_RECHECK']
    assert not stale['case_goal_completed'] and stale['offline_fulfillment'] == 'NO_EVIDENCE'


def test_adapter_step_cannot_downgrade_to_manual_text_after_reopen(local_fixture):
    a, _, _, row = local_fixture
    f = a[0]
    first = successful(f, row)
    changed = receipt_act(f, first, 'REOPEN')
    assert changed.status_code == 200, changed.text
    changed = changed.json()
    assert changed['local_execution']['requires_adapter']
    before = effects(f)
    manual = receipt_act(f, changed, 'SUBMIT', text='SYNTHETIC manual downgrade', source_label=local.ADAPTER_ID)
    assert manual.status_code == 409 and effects(f) == before
    assert not current_view(f, row)['local_execution']['current']
    fresh = successful(f, changed)
    assert fresh['current_receipt']['adapter_execution']['report']['execution_id'] != first['current_receipt']['adapter_execution']['report']['execution_id']
    assert receipt_act(f, fresh, 'ACKNOWLEDGE').status_code == 200


def test_local_execution_reserves_final_revision_for_enterprise_ack(local_fixture):
    a, _, _, row = local_fixture
    f = a[0]
    with f[1].connect() as c:
        c.execute('UPDATE service_receipt_steps SET revision=63 WHERE id=%s',
                  (UUID(str(row['step']['id'])),))
    executor_view = receipt_read(f, row['step']['id'], 'executor-a')
    assert executor_view.status_code == 200, executor_view.text
    executor_view = executor_view.json()
    assert executor_view['step']['revision'] == 63
    assert not executor_view['local_execution']['can_execute']
    before = effects(f)
    assert execute(f, executor_view).status_code == 422
    assert execute(f, executor_view, body=dict(expected_revision=62,
                    reason='SYNTHETIC reserve acknowledgement capacity')).status_code == 409
    assert effects(f) == before and permission_snapshot(f[1]) == a[4]
