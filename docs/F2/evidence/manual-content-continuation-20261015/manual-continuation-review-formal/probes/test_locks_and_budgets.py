"""Actual original commands exercise new continuation locks and 64/128 budgets."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import json
import os
from test_plan_source_conflicts import (
    http_f, link_fixture, receipt_fixture, preparation_fixture, read, edit, changed,
    send as old_send, cold, path, stored, snapshot, complete, adopt, source_preview,
    plan_command, lock, verified, prepare, results,
)
from test_preparation import headers
from test_registered_local_revision import patch_body
from test_final_unknown import SIX_GOALS

HERE = Path(__file__).resolve().parent
SOURCE = 'SYNTHETIC exact line A\nSYNTHETIC exact line B'
MANUAL = 'SYNTHETIC retained original human reminder\n' + SOURCE


def record(value):
    with (HERE / (os.environ['REVIEW_SEAM_WINDOW'] + '-lock-budget-observed.jsonl')).open('a') as stream:
        stream.write(json.dumps(value, sort_keys=True) + '\n')


def keep_body(value):
    return dict(schema=1, action='KEEP_AND_CONTINUE', expected_plan_id=value['plan_id'],
                expected_plan_revision=value['plan_revision'], expected_note_revision=value['note']['revision'],
                expected_ledger_revision=value['opportunity_revision'],
                expected_preview_sha256=value['continuation']['preview_sha256'],
                card_id=value['card_id'], text=None, reason='SYNTHETIC explicit keep with original safety gates')


def keep(f, parent, value, key=None):
    return f[3].post(path(parent) + '/commands', headers=headers(f[2], key=key or uuid4().hex), json=keep_body(value))


def test_downstream_P3_lock_survives_continue_and_refuses_both_adopt_routes(http_f):
    f = http_f
    parent, _, _, _ = complete(f, goals=SIX_GOALS, local=True)
    edit(f, parent, MANUAL)
    assert lock(f, parent, 'P3').status_code == 200
    parent, card = changed(f, parent, mixed=True, text=SOURCE)
    value = read(f, parent, card).json()
    before = stored(f, parent)
    p1 = next(s for s in before['steps'] if s['adapter_id'] == 'P1')
    p3 = next(s for s in before['steps'] if s['adapter_id'] == 'P3')
    assert not p1.get('manual_lock') and p3['manual_lock']
    assert value['continuation']['can_keep_and_continue']
    response = keep(f, parent, value)
    assert response.status_code == 200, response.text
    continued = stored(f, parent)
    assert continued['steps'] == before['steps'] and continued['events'][:-1] == before['events']
    assert next(s for s in continued['steps'] if s['adapter_id'] == 'P3')['manual_lock'] == p3['manual_lock']
    plain = patch_body(f, parent)  # Original observing read precedes snapshots.
    preview = source_preview(f, parent, card).json()
    assert not preview['can_adopt'] and 'AFFECTED_LOCK_REQUIRES_EXPLICIT_UNLOCK' in preview['blocking_reasons']
    untouched = snapshot(f)
    with_card = adopt(f, parent, preview['adoption'])
    without_card = adopt(f, parent, plain)
    assert with_card.status_code == without_card.status_code == 409
    assert snapshot(f) == untouched
    assert next(s for s in stored(f, parent)['steps'] if s['adapter_id'] == 'P3')['manual_lock'] == p3['manual_lock']
    unlocked = plan_command(f, parent, 'P3', 'UNLOCK')
    assert unlocked.status_code == 200, unlocked.text
    preview = source_preview(f, parent, card).json()
    assert preview['can_adopt']
    adopted = adopt(f, parent, preview['adoption'])
    assert adopted.status_code == 201, adopted.text
    final = stored(f, parent)
    assert final['id'] == before['id'] and [s['id'] for s in final['steps']] == [s['id'] for s in before['steps']]
    assert final['owner_amendments'] == continued['owner_amendments']
    record(dict(design='MC12_DOWNSTREAM_LOCK', action='KEEP_AND_CONTINUE',
                P1_locked=False, P3_lock_exact_after_continuation=True,
                both_original_ADOPT_HTTP_statuses=[409, 409], original_UNLOCK_required=True,
                ADOPT_after_UNLOCK_status=201, original_six_goals_and_UUIDs_preserved=True))


def test_new_keep_continuation_actual_business_and_VERIFY_finish_at_revision_64(http_f):
    from test_service_dispatches import offer, command as dispatch_command
    from test_executor_receipts import act as receipt_command
    from test_case_lifecycle import read as lifecycle_read, act as lifecycle_command
    from test_case_resources import post as resource_bind
    f = http_f
    parent, combination, old_dispatch, _ = complete(f, goals=SIX_GOALS, local=True)
    edit(f, parent, MANUAL + '\nSYNTHETIC temporary manual version')
    edit(f, parent, MANUAL)
    assert stored(f, parent)['revision'] == 8
    for _ in range(22):
        assert lock(f, parent, 'P5').status_code == 200
        assert plan_command(f, parent, 'P5', 'UNLOCK').status_code == 200
    assert lock(f, parent, 'P1').status_code == 200
    assert lock(f, parent, 'P3').status_code == 200
    initial = stored(f, parent)
    assert initial['revision'] == 54
    parent, card = changed(f, parent, mixed=True, text=SOURCE)
    value = read(f, parent, card).json()
    response = old_send(f, parent, value, 'KEEP_MANUAL')
    assert response.status_code == 200, response.text
    assert plan_command(f, parent, 'P1', 'UNLOCK').status_code == 200
    assert plan_command(f, parent, 'P3', 'UNLOCK').status_code == 200
    assert stored(f, parent)['revision'] == 57
    value = read(f, parent, card).json()
    assert not value['can_edit'] and value['continuation']['can_keep_and_continue']
    response = keep(f, parent, value)
    assert response.status_code == 200 and stored(f, parent)['revision'] == 58, response.text
    preview = source_preview(f, parent, card)
    assert preview.status_code == 200 and preview.json()['can_adopt'], preview.text
    assert adopt(f, parent, preview.json()['adoption']).status_code == 201
    assert stored(f, parent)['revision'] == 59
    parent = prepare(f, parent, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC actual source review').json()
    parent = prepare(f, parent, 'CONFIRM', reason='SYNTHETIC actual source confirmation').json()
    verified(f, parent, 'P1')
    rebound = resource_bind(f, parent, combination, revision=1)
    assert rebound.status_code == 201, rebound.text
    verified(f, parent, 'P2')
    offered = offer(f, parent, revision=old_dispatch['revision'], recovery_receipt_step_id=old_dispatch['receipt_step_id'])[0]
    assert offered.status_code == 201, offered.text
    dispatch = dispatch_command(f, offered.json(), 'ACCEPT')
    assert dispatch.status_code == 200, dispatch.text
    dispatch = dispatch.json()
    verified(f, parent, 'P3')
    receipt = f[3].get('/api/executor-receipts/' + dispatch['receipt_step_id'], headers=headers(f[2], 'executor-a')).json()
    receipt = receipt_command(f, receipt, 'SUBMIT', text='SYNTHETIC actual renewed receipt at new keep budget').json()
    acknowledged = receipt_command(f, receipt, 'ACKNOWLEDGE')
    assert acknowledged.status_code == 200, acknowledged.text
    verified(f, parent, 'P4')
    revalidated = lifecycle_command(f, parent, lifecycle_read(f, parent).json(), 'REVALIDATE')
    assert revalidated.status_code == 200, revalidated.text
    verified(f, parent, 'P5')
    final = stored(f, parent)
    assert final['revision'] == 64 and final['events'][:54] == initial['events']
    assert final['required_goals'] == SIX_GOALS
    assert final['id'] == initial['id'] and [s['id'] for s in final['steps']] == [s['id'] for s in initial['steps']]
    assert next(iter(final['owner_amendments'].values()))['text'] == MANUAL
    assert [e['action'] for e in final['events'][54:]] == ['KEEP_MANUAL', 'UNLOCK', 'UNLOCK', 'KEEP_AND_CONTINUE', 'ADOPT'] + ['VERIFY'] * 5
    assert results(f, parent).json()['state'] == 'LOCAL_OUTPUTS_VERIFIED'
    assert read(f, parent).json()['state'] == 'RESOLVED'
    record(dict(design='MC35_CAPACITY_LIMIT', subcase='exact_real_64_finish', action='KEEP_AND_CONTINUE',
                original_HTTP_only_revision_54=True, continuation_revision=58, ADOPT_revision=59,
                final_revision=64, original_54_event_prefix_unchanged=True,
                actual_original_business_work_and_5_VERIFY=True, manual_text_exact=True, six_goals=True))


def test_new_keep_continuation_refuses_one_event_short_plan_budget(http_f):
    f = http_f
    parent, _, _, _ = complete(f, goals=SIX_GOALS, local=True)
    edit(f, parent, MANUAL + '\nSYNTHETIC earlier edit')
    edit(f, parent, MANUAL)
    for _ in range(25):
        assert lock(f, parent, 'P5').status_code == 200
        assert plan_command(f, parent, 'P5', 'UNLOCK').status_code == 200
    assert stored(f, parent)['revision'] == 58
    parent, card = changed(f, parent, mixed=True, text=SOURCE)
    value = read(f, parent, card).json()
    assert value['continuation']['coverage_satisfied']
    assert not value['continuation']['can_keep_and_continue']
    assert 'EVENT_CAPACITY_RESERVED_FOR_UNLOCK_ACCEPT_ADOPT_VERIFY' in value['blocking_reasons']
    before = snapshot(f)
    key = uuid4().hex
    response = keep(f, parent, value, key)
    assert response.status_code == 409, response.text
    assert snapshot(f) == before
    recovery = cold(f, parent, key)
    assert recovery.status_code == 200 and recovery.json()['status'] == 'NOT_OBSERVED'
    assert snapshot(f) == before
    record(dict(design='MC35_CAPACITY_LIMIT', subcase='one_event_short_at_58',
                actual_plan_revision=58, exact_source_lines_carried=True,
                new_continuation_status=409, business_plan_ledger_unchanged=True,
                cold_original_key='NOT_OBSERVED', original_event_limit=64))


def test_new_keep_uses_128th_ledger_slot_and_original_ADOPT_needs_no_extra_slot(http_f):
    from test_case_opportunities import get as opportunities, post as opp_post, body as opp_body
    f = http_f
    parent, _, _, _ = complete(f, goals=SIX_GOALS, local=True)
    edit(f, parent, MANUAL)
    parent, card = changed(f, parent, mixed=True, text=SOURCE)
    current = opportunities(f, parent).json()
    while current['revision'] < 127:
        refreshed = opp_post(f, parent, opp_body(current, 'REFRESH'))
        assert refreshed.status_code == 200, refreshed.text
        current = refreshed.json()['current']
    assert current['revision'] == 127
    value = read(f, parent, card).json()
    assert value['continuation']['can_keep_and_continue']
    key = uuid4().hex
    response = keep(f, parent, value, key)
    assert response.status_code == 200, response.text
    with f[1].connect() as connection:
        ledger = connection.execute('SELECT opportunities FROM preparations WHERE id=%s', (parent['preparation_id'],)).fetchone()['opportunities']
    assert ledger['revision'] == len(ledger['events']) == 128
    assert ledger['events'][-1]['outcome'] == 'KEEP_AND_CONTINUE'
    preview = source_preview(f, parent, card)
    assert preview.status_code == 200 and preview.json()['can_adopt'], preview.text
    adopted = adopt(f, parent, preview.json()['adoption'])
    assert adopted.status_code == 201, adopted.text
    with f[1].connect() as connection:
        after = connection.execute('SELECT opportunities FROM preparations WHERE id=%s', (parent['preparation_id'],)).fetchone()['opportunities']
    assert after == ledger
    current_view = read(f, parent, card).json()
    before = snapshot(f)
    # This is explicitly the existing closed request-type bound, not a claim
    # that an out-of-range request reached a business validator.
    out_of_range = keep(f, parent, current_view)
    assert out_of_range.status_code == 422, out_of_range.text
    assert snapshot(f) == before
    recovery = cold(f, parent, key)
    assert recovery.status_code == 200 and recovery.json()['status'] == 'COMMITTED'
    assert snapshot(f) == before
    record(dict(design='MC35_CAPACITY_LIMIT', subcase='actual_last_ledger_slot_128',
                real_original_NO_CHANGE_refreshes=True, continuation_ledger_revision=128,
                original_ADOPT_status=201, ADOPT_does_not_add_opportunity_event=True,
                next_command_128_revision_typed_bound_status=422,
                typed_refusal_is_not_business_validator_claim=True,
                original_key_cold_COMMITTED=True, original_ledger_limit=128))
