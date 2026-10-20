"""Ordinary unaccepted redispatch using owned synthetic PG, never real authority."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from parkweave.api import configured_app
from parkweave import case_step_assignments as cs
from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture, act as receipt_command
from test_ordinary_case_steps import ordinary, consume, inbox, notice, dispatch
from test_case_step_assignments import prepared, ok, REVIEWER
from test_service_dispatches import offer, command as decision
from service_release_acceptance_support import authority_snapshot
from ordinary_case_step_support import ordinary_api, worker_once
from test_ordinary_case_step_process import html


def catalog(f, p):
    return f[3].get('/api/service-dispatches/catalog?preparation_id=' + p['preparation_id'], headers=headers(f[2], REVIEWER))


@pytest.mark.parametrize('terminal', ['DECLINE', 'WITHDRAW'])
def test_explicit_different_executor_reaches_receipt_and_cold_history(ordinary, terminal):
    f, baseline = ordinary
    p = prepared(f)
    first = ok(offer(f, p)[0], 201)
    ended = ok(decision(f, first, terminal))
    before_view = ok(dispatch(f, ended, REVIEWER))
    directory = ok(catalog(f, p))
    assert directory['ready'] and directory['can_offer_again']
    assert directory['executors'] == [{'id': 'unassigned'}]
    assert not directory['can_reassign'] and not directory['can_reoffer']
    key = uuid4().hex
    response, _, body = offer(f, p, revision=ended['revision'], executor='unassigned', key=key)
    renewed = ok(response, 201)
    assert renewed['dispatch_id'] == first['dispatch_id']
    assert renewed['current_offer']['id'] != first['current_offer']['id']
    assert renewed['assignment_valid_until'] == first['assignment_valid_until']
    replay = ok(f[3].post('/api/preparations/' + p['preparation_id'] + '/dispatch', headers=headers(f[2], REVIEWER, key), json=body), 201)
    assert replay['event'] == renewed['event']
    assert len(replay['offers']) == 2
    import os
    if terminal == 'DECLINE' and os.environ.get('REDISPATCH_UI_FIXTURE_OUT'):
        import json
        from pathlib import Path
        # Explicit one-time export of public DTOs from this owned synthetic test.
        # No headers, sessions, DSN, marker internals or permission tables.
        after_view = ok(dispatch(f, renewed, REVIEWER))
        value = dict(scope='OWNED_SYNTHETIC_CLIENT_RESPONSE_SNAPSHOT_ONLY',
            preparation_id=p['preparation_id'], first_deadline=first['assignment_valid_until'],
            list_view=ok(f[3].get('/api/service-dispatches', headers=headers(f[2], REVIEWER))),
            before_view=before_view, before_catalog=directory,
            post_body=body, post_response=renewed, after_view=after_view, after_catalog=ok(catalog(f, p)))
        with Path(os.environ['REDISPATCH_UI_FIXTURE_OUT']).open('x') as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write('\n')
    ok(dispatch(f, first, 'executor-a'), 403)
    ok(decision(f, first, 'ACCEPT'), 403)
    # Drain only after the new generation exists: old valid sources must settle.
    consume(f)
    assert ok(inbox(f))['items'] == []
    new_notice = ok(inbox(f, 'unassigned'))['items'][0]
    assert new_notice['action'] == 'REOFFER' and new_notice['revision'] == renewed['revision']
    assert new_notice['dispatch_id'] == renewed['dispatch_id']
    ok(notice(f, new_notice, 'OPEN', 'unassigned'))
    ok(notice(f, new_notice, 'MARK_READ', 'unassigned'))
    accept_key = uuid4().hex
    accepted = ok(decision(f, renewed, 'ACCEPT', key=accept_key))
    params = dict(preparation_id=p['preparation_id'], case_id=p['case_id'], run_id=p['run_id'],
                  offer_id=renewed['current_offer']['id'], expected_revision=renewed['revision'], preparation_revision=p['revision'])
    path = '/api/service-dispatches/' + renewed['dispatch_id'] + '/accept-recovery'
    recovered = ok(f[3].get(path, headers=headers(f[2], 'unassigned', accept_key), params=params))
    assert recovered['status'] == 'COMMITTED' and recovered['event']['revision'] == accepted['revision']
    receipt = ok(f[3].get('/api/executor-receipts/' + accepted['receipt_step_id'], headers=headers(f[2], 'unassigned')))
    receipt = ok(receipt_command(f, receipt, 'SUBMIT', user='unassigned'))
    receipt = ok(receipt_command(f, receipt, 'ACKNOWLEDGE'))
    assert receipt['step']['state'] == 'LOCAL_ACKNOWLEDGED' and not receipt['case_goal_completed']
    consume(f)
    with f[1].connect() as c:
        assert not c.execute("SELECT 1 FROM dispatch_notice_outbox WHERE state='PENDING'").fetchone()
        old = c.execute('SELECT state,receipt_step_id FROM service_dispatch_offers WHERE id=%s', (first['current_offer']['id'],)).fetchone()
        assert old['state'] == ('DECLINED' if terminal == 'DECLINE' else 'WITHDRAWN') and old['receipt_step_id'] is None
    with TestClient(configured_app()) as cold:
        fresh = (*f[:3], cold)
        history = ok(dispatch(fresh, renewed, 'fixture-a'))
        assert [e['action'] for e in history['history']] == ['OFFER', terminal, 'REOFFER', 'ACCEPT']
        assert history['assignment_valid_until'] == first['assignment_valid_until']
        assert ok(cold.get(path, headers=headers(f[2], 'unassigned', accept_key), params=params)) == recovered
    assert authority_snapshot(f[1]) == baseline
    ok(f[3].get('/api/runs/' + p['run_id'], headers=headers(f[2], 'unassigned')), 403)


def test_old_executor_revocation_does_not_block_explicit_new_responsibility(ordinary):
    f, _ = ordinary
    p = prepared(f)
    first = ok(offer(f, p)[0], 201)
    ended = ok(decision(f, first, 'DECLINE'))
    with f[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
    before = authority_snapshot(f[1])
    new = ok(offer(f, p, revision=ended['revision'], executor='unassigned')[0], 201)
    assert new['assignment_valid_until'] == first['assignment_valid_until']
    ok(dispatch(f, new, 'executor-a'), 403)
    ok(decision(f, new, 'ACCEPT'))
    assert authority_snapshot(f[1]) == before


@pytest.mark.parametrize('phase', ['OFFERED', 'ACCEPTED', 'WITHDRAW_AFTER_ACCEPT', 'SUBMITTED', 'ACKNOWLEDGED'])
def test_active_or_ever_accepted_dispatch_cannot_use_unaccepted_redispatch(ordinary, phase):
    f, _ = ordinary
    p = prepared(f)
    row = ok(offer(f, p)[0], 201)
    if phase != 'OFFERED':
        row = ok(decision(f, row, 'ACCEPT'))
    if phase == 'WITHDRAW_AFTER_ACCEPT':
        row = ok(decision(f, row, 'WITHDRAW'))
    if phase in ('SUBMITTED', 'ACKNOWLEDGED'):
        receipt = ok(f[3].get('/api/executor-receipts/' + row['receipt_step_id'], headers=headers(f[2], 'executor-a')))
        receipt = ok(receipt_command(f, receipt, 'SUBMIT'))
        if phase == 'ACKNOWLEDGED':
            ok(receipt_command(f, receipt, 'ACKNOWLEDGE'))
    with f[1].connect() as c:
        before = c.execute('SELECT count(*) n FROM service_dispatch_events').fetchone()['n']
    directory = ok(catalog(f, p))
    if phase == 'WITHDRAW_AFTER_ACCEPT':
        assert directory['ready'] and directory['can_offer_again']
        ok(offer(f, p, revision=row['revision'], executor='unassigned')[0], 201)
    else:
        assert not directory['ready'] and not directory['can_offer_again']
        ok(offer(f, p, revision=row['revision'], executor='unassigned')[0], 409)
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_dispatch_events').fetchone()['n'] == before + (1 if phase == 'WITHDRAW_AFTER_ACCEPT' else 0)


@pytest.mark.parametrize('target,expected', [('executor-a', 409), ('executor-b', 403), ('executor-c', 403), (REVIEWER, 403)])
def test_redispatch_requires_a_different_existing_same_domain_executor(ordinary, target, expected):
    f, _ = ordinary
    p = prepared(f)
    row = ok(decision(f, ok(offer(f, p)[0], 201), 'DECLINE'))
    before = authority_snapshot(f[1])
    ok(offer(f, p, revision=row['revision'], executor=target)[0], expected)
    assert authority_snapshot(f[1]) == before


@pytest.mark.parametrize('change', ['owner_prepare', 'owner_execute', 'reviewer_grant', 'target_read', 'target_inactive', 'material', 'catalog'])
def test_redispatch_rechecks_current_permissions_and_confirmed_sources(ordinary, change):
    f, _ = ordinary
    p = prepared(f)
    row = ok(decision(f, ok(offer(f, p)[0], 201), 'DECLINE'))
    with f[1].connect() as c:
        if change == 'owner_prepare':
            c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        elif change == 'reviewer_grant':
            c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s', (REVIEWER,))
        elif change == 'owner_execute':
            c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        elif change == 'target_read':
            c.execute("UPDATE capability_grants SET active=false WHERE principal_id='unassigned' AND capability='READ'")
        elif change == 'target_inactive':
            c.execute("UPDATE principals SET active=false WHERE id='unassigned'")
        elif change == 'material':
            c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s', (p['preparation_id'],))
        else:
            c.execute("UPDATE preparation_catalog SET name=name||' changed' WHERE park_id='park-a'")
    before = authority_snapshot(f[1])
    response = offer(f, p, revision=row['revision'], executor='unassigned')[0]
    assert response.status_code in (403, 409), response.text
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n'] == 1
    assert authority_snapshot(f[1]) == before


def test_original_deadline_and_final_check_do_not_renew_on_redispatch(ordinary, monkeypatch):
    f, _ = ordinary
    p = prepared(f)
    first = ok(offer(f, p)[0], 201)
    row = ok(decision(f, first, 'DECLINE'))
    clock = cs._now
    monkeypatch.setattr(cs, '_now', lambda c: clock(c) + timedelta(hours=1))
    assert not ok(catalog(f, p))['ready']
    ok(offer(f, p, revision=row['revision'], executor='unassigned')[0], 409)
    monkeypatch.setattr(cs, '_now', clock)
    # The event is attempted, but the original final deadline check rolls it back.
    original = cs.sd._event
    def expires_after_event(*args, **kwargs):
        result = original(*args, **kwargs)
        monkeypatch.setattr(cs, '_now', lambda c: clock(c) + timedelta(hours=1))
        return result
    monkeypatch.setattr(cs.sd, '_event', expires_after_event)
    ok(offer(f, p, revision=row['revision'], executor='unassigned')[0], 403)
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n'] == 1
        assert c.execute('SELECT revision FROM service_dispatches').fetchone()['revision'] == row['revision']


def test_concurrent_explicit_redispatch_has_one_new_offer(ordinary):
    f, baseline = ordinary
    p = prepared(f)
    first = ok(offer(f, p)[0], 201)
    row = ok(decision(f, first, 'WITHDRAW'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: offer(f, p, revision=row['revision'], executor='unassigned')[0], range(2)))
    assert sorted(r.status_code for r in results) == [201, 409]
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n'] == 2
        assert c.execute('SELECT count(*) n FROM service_dispatch_events').fetchone()['n'] == 3
    assert authority_snapshot(f[1]) == baseline


def test_old_keys_and_old_coordinates_do_not_act_on_a_returning_executor(ordinary):
    f, _ = ordinary
    p = prepared(f)
    offer_key, decline_key = uuid4().hex, uuid4().hex
    first_response, _, first_body = offer(f, p, key=offer_key)
    first = ok(first_response, 201)
    consume(f)
    original_notice = ok(inbox(f))['items'][0]
    ended = ok(decision(f, first, 'DECLINE', key=decline_key))
    second = ok(offer(f, p, revision=ended['revision'], executor='unassigned')[0], 201)
    second = ok(decision(f, second, 'DECLINE'))
    third = ok(offer(f, p, revision=second['revision'], executor='executor-a')[0], 201)
    ok(f[3].post('/api/preparations/' + p['preparation_id'] + '/dispatch', headers=headers(f[2], REVIEWER, offer_key), json=first_body), 409)
    ok(decision(f, first, 'DECLINE', key=decline_key), 409)
    ok(decision(f, first, 'ACCEPT'), 409)
    ok(notice(f, original_notice, 'OPEN'), 403)
    ok(notice(f, original_notice, 'MARK_READ'), 403)
    ok(f[3].get('/api/dispatch-notices/' + original_notice['event_id'], headers=headers(f[2], 'executor-a')), 403)
    consume(f)
    own_notices = ok(inbox(f))['items']
    assert len(own_notices) == 1 and own_notices[0]['revision'] == third['revision']
    with f[1].connect() as c:
        assert c.execute('SELECT revision FROM service_dispatches').fetchone()['revision'] == third['revision']
        assert not c.execute('SELECT 1 FROM service_receipt_steps').fetchone()


@pytest.mark.parametrize('damage', ['terminal_actor', 'terminal_revision_type', 'terminal_reason', 'new_deadline', 'old_catalog', 'old_owner_generation'])
def test_damaged_prefix_or_renewed_deadline_cannot_authorize_new_offer(ordinary, damage):
    f, _ = ordinary
    p = prepared(f)
    first = ok(offer(f, p)[0], 201)
    ended = ok(decision(f, first, 'DECLINE'))
    new = ok(offer(f, p, revision=ended['revision'], executor='unassigned')[0], 201)
    with f[1].connect() as c:
        event = c.execute('SELECT * FROM service_dispatch_events WHERE revision=%s', (3 if damage == 'new_deadline' else 1 if damage.startswith('old_') else 2,)).fetchone()
        payload = event['payload']
        if damage == 'terminal_actor':
            payload['actor_id'] = REVIEWER
        elif damage == 'terminal_revision_type':
            payload['revision'] = 2.0
        elif damage == 'terminal_reason':
            payload['reason'] = 'SYNTHETIC altered terminal reason'
        elif damage == 'new_deadline':
            from datetime import datetime
            deadline = datetime.fromisoformat(first['assignment_valid_until']) + timedelta(microseconds=1)
            payload[cs.MARKER]['valid_until'] = deadline.isoformat()
        elif damage == 'old_catalog':
            payload[cs.MARKER]['binding']['catalog_sha256'] = '0' * 64
        else:
            payload[cs.MARKER]['binding']['generations']['fixture-a']['principal'] = '0'
        c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s', (Jsonb(payload), event['id']))
    ok(dispatch(f, new, 'unassigned'), 403)
    ok(decision(f, new, 'ACCEPT'), 403)
    consume(f)
    with f[1].connect() as c:
        assert c.execute("SELECT 1 FROM dispatch_notice_outbox WHERE state='PENDING'").fetchone()
        assert not c.execute('SELECT 1 FROM service_receipt_steps').fetchone()


def test_original_page_redispatch_retry_new_executor_receipt_and_restart(receipt_fixture, tmp_path):
    initial = receipt_fixture
    baseline = authority_snapshot(initial[1])
    with ordinary_api(initial, tmp_path / 'first-api') as api:
        f = (*initial[:3], api)
        p = prepared(f)
        first = html(f, tmp_path / 'first-offer', 'OFFER', p)
        html(f, tmp_path / 'old-decline', 'DECLINE', p)
    worker_once(initial, tmp_path / 'old-notice-worker')
    with ordinary_api(initial, tmp_path / 'second-api') as api:
        f = (*initial[:3], api)
        new = html(f, tmp_path / 'explicit-redispatch', 'REDISPATCH', p,
                   deadline=first['deadline'], drop_reoffer_response=True)
        assert new['dispatch_id'] == first['dispatch_id'] and new['revision'] == 3
    worker_once(initial, tmp_path / 'new-notice-worker')
    with ordinary_api(initial, tmp_path / 'third-api') as api:
        f = (*initial[:3], api)
        done = html(f, tmp_path / 'new-executor', 'EXECUTE', p,
                    deadline=first['deadline'], executor_id='unassigned')
        ok(dispatch(f, {'dispatch_id': first['dispatch_id']}, 'executor-a'), 403)
    worker_once(initial, tmp_path / 'accepted-notice-worker')
    with ordinary_api(initial, tmp_path / 'cold-api') as api:
        f = (*initial[:3], api)
        cold = html(f, tmp_path / 'cold-read', 'READ', p,
                    deadline=first['deadline'], executor_id='unassigned', step=done['step'])
        assert all(call['method'] == 'GET' for call in cold['calls'])
    assert first['deadline'] == new['deadline'] == done['deadline'] == cold['deadline']
    assert done['state'] == 'LOCAL_ACKNOWLEDGED'
    assert authority_snapshot(initial[1]) == baseline
    with initial[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n'] == 2
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n'] == 1
        assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
    import json
    (tmp_path / 'original-page-chain.json').write_text(json.dumps(dict(
        scope='OWNED_SYNTHETIC_ORDINARY_API_AND_FULL_HTML', first=first, new=new, executed=done, cold=cold,
        real_browser=False, authority_unchanged=True, api_processes=4, worker_processes=3), indent=2) + '\n')


def test_thirty_one_actual_invitations_keep_one_deadline_and_stop_before_version_exhaustion(ordinary):
    f, baseline = ordinary
    p = prepared(f)
    row = ok(offer(f, p)[0], 201)
    deadline = row['assignment_valid_until']
    for index in range(31):
        row = ok(decision(f, row, 'DECLINE'))
        if index < 30:
            target = 'unassigned' if row['current_offer']['executor_id'] == 'executor-a' else 'executor-a'
            row = ok(offer(f, p, revision=row['revision'], executor=target)[0], 201)
            assert row['assignment_valid_until'] == deadline
    assert row['revision'] == 62
    directory = ok(catalog(f, p))
    assert directory['history_limit_reached'] and not directory['ready']
    ok(offer(f, p, revision=row['revision'], executor='unassigned')[0], 409)
    assert authority_snapshot(f[1]) == baseline


def test_original_acceptance_history_still_blocks_when_receipt_pointer_is_cleared(ordinary):
    f, _ = ordinary
    p = prepared(f)
    row = ok(decision(f, ok(offer(f, p)[0], 201), 'ACCEPT'))
    step = row['receipt_step_id']
    row = ok(decision(f, row, 'WITHDRAW'))
    # Owned corruption probe only: never use a cleared pointer as nonacceptance.
    with f[1].connect() as c:
        c.execute('DELETE FROM service_receipt_events WHERE step_id=%s', (step,))
        c.execute('DELETE FROM service_receipt_steps WHERE id=%s', (step,))
    ok(offer(f, p, revision=row['revision'], executor='unassigned')[0], 403)
    with f[1].connect() as c:
        assert c.execute("SELECT count(*) n FROM service_dispatch_events WHERE action='ACCEPT'").fetchone()['n'] == 1
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n'] == 1


def test_damaged_current_terminal_replay_refuses_without_unhandled_key_error(ordinary):
    f, _ = ordinary
    p = prepared(f)
    first = ok(offer(f, p)[0], 201)
    key = uuid4().hex
    ended = ok(decision(f, first, 'WITHDRAW', key=key))
    with f[1].connect() as c:
        c.execute("UPDATE service_dispatch_events SET payload=payload-'offer_id' WHERE action='WITHDRAW'")
    ok(decision(f, first, 'WITHDRAW', key=key), 409)
    with f[1].connect() as c:
        assert c.execute('SELECT revision FROM service_dispatches').fetchone()['revision'] == ended['revision']


def test_accepted_zero_receipt_explicit_withdraw_then_new_executor_completes(ordinary):
    f, baseline = ordinary
    p = prepared(f)
    first = ok(offer(f, p)[0], 201)
    accepted = ok(decision(f, first, 'ACCEPT'))
    old_step = accepted['receipt_step_id']
    ended = ok(decision(f, accepted, 'WITHDRAW'))
    directory = ok(catalog(f, p))
    assert directory['ready'] and directory['can_offer_again']
    assert directory['offer_again_kind'] == 'WITHDRAWN_ZERO_RECEIPT'
    renewed = ok(offer(f, p, revision=ended['revision'], executor='unassigned')[0], 201)
    assert renewed['assignment_valid_until'] == first['assignment_valid_until']
    ok(f[3].get('/api/executor-receipts/' + old_step, headers=headers(f[2], 'executor-a')), 403)
    accepted = ok(decision(f, renewed, 'ACCEPT'))
    assert accepted['receipt_step_id'] != old_step
    receipt = ok(f[3].get('/api/executor-receipts/' + accepted['receipt_step_id'], headers=headers(f[2], 'unassigned')))
    receipt = ok(receipt_command(f, receipt, 'SUBMIT', user='unassigned'))
    receipt = ok(receipt_command(f, receipt, 'ACKNOWLEDGE'))
    assert receipt['step']['state'] == 'LOCAL_ACKNOWLEDGED'
    with f[1].connect() as c:
        old = c.execute('SELECT state,revision,current_receipt_id FROM service_receipt_steps WHERE id=%s', (old_step,)).fetchone()
        assert old == dict(state='AWAITING_RECEIPT', revision=1, current_receipt_id=None)
        assert c.execute('SELECT count(*) n FROM service_receipt_events WHERE step_id=%s', (old_step,)).fetchone()['n'] == 1
    consume(f)
    with f[1].connect() as c:
        assert not c.execute("SELECT 1 FROM dispatch_notice_outbox WHERE state='PENDING'").fetchone()
    with TestClient(configured_app()) as cold:
        history = ok(dispatch((*f[:3], cold), accepted, 'fixture-a'))
        assert [e['action'] for e in history['history']] == ['OFFER', 'ACCEPT', 'WITHDRAW', 'REOFFER', 'ACCEPT']
    assert authority_snapshot(f[1]) == baseline


@pytest.mark.parametrize('change', ['receipt', 'reopened', 'revision', 'extra_event', 'create_missing', 'accept_type', 'terminal_type', 'orphan'])
def test_zero_receipt_handoff_rejects_any_result_or_unknown_history(ordinary, change):
    f, _ = ordinary
    p = prepared(f)
    accepted = ok(decision(f, ok(offer(f, p)[0], 201), 'ACCEPT'))
    step = accepted['receipt_step_id']
    if change in ('receipt', 'reopened'):
        receipt = ok(f[3].get('/api/executor-receipts/' + step, headers=headers(f[2], 'executor-a')))
        receipt = ok(receipt_command(f, receipt, 'SUBMIT'))
        if change == 'reopened':
            ok(receipt_command(f, receipt, 'REOPEN'))
    ended = ok(decision(f, accepted, 'WITHDRAW'))
    with f[1].connect() as c:
        if change == 'revision':
            c.execute('UPDATE service_receipt_steps SET revision=revision+1 WHERE id=%s', (step,))
        elif change == 'extra_event':
            c.execute("UPDATE service_receipt_events SET action='SUBMIT' WHERE step_id=%s", (step,))
        elif change == 'create_missing':
            c.execute('DELETE FROM service_receipt_events WHERE step_id=%s', (step,))
        elif change in ('accept_type', 'terminal_type'):
            action = 'ACCEPT' if change == 'accept_type' else 'WITHDRAW'
            row = c.execute('SELECT * FROM service_dispatch_events WHERE action=%s', (action,)).fetchone()
            payload = row['payload']; payload['revision'] = float(payload['revision'])
            c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s', (Jsonb(payload), row['id']))
        elif change == 'orphan':
            c.execute("INSERT INTO service_receipt_steps SELECT (jsonb_populate_record(NULL::service_receipt_steps,to_jsonb(s)||jsonb_build_object('id',%s::text))).* FROM service_receipt_steps s WHERE id=%s", (str(uuid4()), step))
        before = c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n']
    result = offer(f, p, revision=ended['revision'], executor='unassigned')[0]
    assert result.status_code in (403, 409), result.text
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n'] == before


def test_pending_handoff_can_decline_then_return_without_reviving_old_keys(ordinary):
    f, _ = ordinary
    p = prepared(f)
    first = ok(offer(f, p)[0], 201)
    key = uuid4().hex
    accepted = ok(decision(f, first, 'ACCEPT', key=key))
    old_receipt = ok(f[3].get('/api/executor-receipts/' + accepted['receipt_step_id'], headers=headers(f[2], 'executor-a')))
    ended = ok(decision(f, accepted, 'WITHDRAW'))
    second = ok(offer(f, p, revision=ended['revision'], executor='unassigned')[0], 201)
    second = ok(decision(f, second, 'DECLINE'))
    third = ok(offer(f, p, revision=second['revision'], executor='executor-a')[0], 201)
    ok(decision(f, first, 'ACCEPT', key=key), 409)
    ok(receipt_command(f, old_receipt, 'SUBMIT'), 403)
    fresh = ok(decision(f, third, 'ACCEPT'))
    assert fresh['receipt_step_id'] != accepted['receipt_step_id']
    assert fresh['assignment_valid_until'] == first['assignment_valid_until']


def test_handoff_after_old_executor_revocation_and_final_deadline_rollback(ordinary, monkeypatch):
    f, _ = ordinary
    p = prepared(f)
    accepted = ok(decision(f, ok(offer(f, p)[0], 201), 'ACCEPT'))
    ended = ok(decision(f, accepted, 'WITHDRAW'))
    with f[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
    baseline = authority_snapshot(f[1])
    assert ok(catalog(f, p))['ready']
    clock, event = cs._now, cs.sd._event
    def expire(*args, **kwargs):
        result = event(*args, **kwargs)
        monkeypatch.setattr(cs, '_now', lambda c: clock(c) + timedelta(seconds=301))
        return result
    monkeypatch.setattr(cs.sd, '_event', expire)
    ok(offer(f, p, revision=ended['revision'], executor='unassigned')[0], 403)
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_dispatch_offers').fetchone()['n'] == 1
        assert c.execute('SELECT revision FROM service_dispatches').fetchone()['revision'] == ended['revision']
    monkeypatch.setattr(cs.sd, '_event', event); monkeypatch.setattr(cs, '_now', clock)
    new = ok(offer(f, p, revision=ended['revision'], executor='unassigned')[0], 201)
    ok(decision(f, new, 'ACCEPT'))
    assert authority_snapshot(f[1]) == baseline


def test_withdraw_racing_first_submit_never_loses_a_committed_result(ordinary):
    f, _ = ordinary
    p = prepared(f)
    accepted = ok(decision(f, ok(offer(f, p)[0], 201), 'ACCEPT'))
    receipt = ok(f[3].get('/api/executor-receipts/' + accepted['receipt_step_id'], headers=headers(f[2], 'executor-a')))
    with ThreadPoolExecutor(max_workers=2) as pool:
        writes = [pool.submit(decision, f, accepted, 'WITHDRAW'), pool.submit(receipt_command, f, receipt, 'SUBMIT')]
        withdrawn, submitted = [future.result() for future in writes]
    assert withdrawn.status_code == 200
    assert submitted.status_code in (200, 403)
    ended = withdrawn.json()
    result = offer(f, p, revision=ended['revision'], executor='unassigned')[0]
    assert result.status_code in ((403, 409) if submitted.status_code == 200 else (201,)), result.text
    with f[1].connect() as c:
        count = c.execute('SELECT count(*) n FROM service_step_receipts').fetchone()['n']
        assert count == (1 if submitted.status_code == 200 else 0)


def test_original_page_pending_handoff_restarts_and_keeps_each_explicit_action(receipt_fixture, tmp_path):
    initial = receipt_fixture
    baseline = authority_snapshot(initial[1])
    with ordinary_api(initial, tmp_path / 'first-api') as api:
        f = (*initial[:3], api); p = prepared(f)
        first = html(f, tmp_path / 'first-offer', 'OFFER', p)
        withdrawn = html(f, tmp_path / 'accepted-withdraw', 'WITHDRAW_PENDING', p)
    with ordinary_api(initial, tmp_path / 'second-api') as api:
        f = (*initial[:3], api)
        new = html(f, tmp_path / 'explicit-handoff', 'REDISPATCH', p,
            deadline=first['deadline'], pending_handoff=True, drop_reoffer_response=True)
        assert new['revision'] == 4
        ok(f[3].get('/api/executor-receipts/' + withdrawn['old_step'], headers=headers(f[2], 'executor-a')), 403)
    worker_once(initial, tmp_path / 'notice-worker')
    with ordinary_api(initial, tmp_path / 'third-api') as api:
        f = (*initial[:3], api)
        done = html(f, tmp_path / 'new-executor', 'EXECUTE', p, deadline=first['deadline'], executor_id='unassigned')
        assert done['step'] != withdrawn['old_step'] and done['state'] == 'LOCAL_ACKNOWLEDGED'
    assert authority_snapshot(initial[1]) == baseline
    import json
    (tmp_path / 'pending-handoff-original-page.json').write_text(json.dumps(dict(
        first=first, withdrawn=withdrawn, new=new, done=done, authority_unchanged=True,
        real_browser=False, scope='FULL_SHIPPED_HTML_NODE_VM_REAL_ORDINARY_HTTP_WORKER_PG'), indent=2) + '\n')


@pytest.mark.parametrize('change', ['orphan', 'old_result'])
def test_new_accept_rechecks_zero_history_after_invitation(ordinary, change):
    f, _ = ordinary; p = prepared(f)
    accepted = ok(decision(f, ok(offer(f, p)[0], 201), 'ACCEPT'))
    ended = ok(decision(f, accepted, 'WITHDRAW'))
    renewed = ok(offer(f, p, revision=ended['revision'], executor='unassigned')[0], 201)
    with f[1].connect() as c:
        if change == 'orphan':
            c.execute("INSERT INTO service_receipt_steps SELECT (jsonb_populate_record(NULL::service_receipt_steps,to_jsonb(s)||jsonb_build_object('id',%s::text))).* FROM service_receipt_steps s WHERE id=%s", (str(uuid4()), accepted['receipt_step_id']))
        else:
            c.execute('UPDATE service_receipt_steps SET revision=2 WHERE id=%s', (accepted['receipt_step_id'],))
        count = c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n']
    assert decision(f, renewed, 'ACCEPT').status_code in (403, 409)
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n'] == count


def test_mixed_history_terminal_revision_61_explains_invitation_limit(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    context = object.__new__(cs._OrdinaryCaseStep)
    context.service = SimpleNamespace(local_synthetic_demo=None)
    context.executor_ids = ('executor-a',)
    context.offer_seconds, context.valid_until, context.contract = 300, None, cs.ORDINARY_CONTRACT
    cursor = SimpleNamespace(fetchone=lambda: None)
    connection = SimpleNamespace(execute=lambda *args: cursor)
    context._connection = lambda store: nullcontext(connection)
    context._parent = lambda *args: (dict(role='park_specialist'), dict(id=uuid4(), revision=4))
    context._root = lambda *args: dict(revision=61)
    monkeypatch.setattr(cs.sd, '_own_offer', lambda *args: None)
    monkeypatch.setattr(cs.er, 'material_current', lambda *args: True)
    monkeypatch.setattr(cs.prep, 'case_write_blocked', lambda *args: False)
    result = context.catalog(None, None, uuid4())
    assert not result['ready'] and not result['can_offer_again'] and result['history_limit_reached']
