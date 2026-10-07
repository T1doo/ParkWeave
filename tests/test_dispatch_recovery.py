"""Receipt generation recovery through original product APIs in isolated PG."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest

from parkweave import service_dispatches as sd, executor_receipts as er
from parkweave.store import Conflict
from test_preparation import preparation_fixture, headers, command as prep_command, add
from test_executor_receipts import receipt_fixture, ready, act as receipt_action
from test_case_resources import link_fixture, group, post as resource_link
from test_service_dispatches import offer, command as dispatch_action, read as dispatch_read, REVIEWER


def receipt_read(f, step_id, user='fixture-a'):
    response = f[3].get('/api/executor-receipts/' + step_id, headers=headers(f[2], user))
    assert response.status_code == 200, response.text
    return response.json()


def changed_materials(f, parent):
    result = prep_command(f, parent, 'REOPEN', reason='Explicit changed material source')
    assert result.status_code == 200, result.text
    parent = result.json()
    result = add(f, parent, 'need_summary', 'New source version after previously accepted dispatch')
    assert result.status_code == 200, result.text
    parent = result.json()
    result = prep_command(f, parent, 'REVIEW', REVIEWER, reason='Reviewer checks actual new source version')
    assert result.status_code == 200, result.text
    result = prep_command(f, result.json(), 'CONFIRM', reason='Owner confirms new material snapshot')
    assert result.status_code == 200, result.text
    return result.json()


def accepted(f):
    response, parent, _ = offer(f)
    assert response.status_code == 201, response.text
    result = dispatch_action(f, response.json(), 'ACCEPT')
    assert result.status_code == 200, result.text
    dispatch = result.json()
    return parent, dispatch, receipt_read(f, dispatch['receipt_step_id'])


def records(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text').fetchall()
                for table in ('service_dispatches', 'service_dispatch_offers', 'service_dispatch_events',
                              'service_receipt_steps', 'service_step_receipts', 'service_receipt_events',
                              'dispatch_notice_outbox', 'dispatch_notices')}


def authority(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text').fetchall()
                for table in ('principals', 'capability_grants', 'preparation_grants', 'run_assignments',
                              'synthetic_resource_grants')}


def test_pre_recovery_accepted_material_change_dead_end(receipt_fixture):
    """Baseline gold: old accepted receipt remains unusable after fresh materials."""
    f = receipt_fixture
    parent, dispatch, old = accepted(f)
    current = changed_materials(f, parent)
    before = records(f)
    response = receipt_action(f, old, 'SUBMIT')
    assert response.status_code == 409, response.text
    response = offer(f, current, revision=dispatch['revision'])[0]
    assert response.status_code == 409, response.text
    assert records(f) == before
    assert receipt_read(f, old['step']['id'])['dependency'] == 'DEPENDENCY_CHANGED'


def recovery_offer(f, parent, dispatch, old, **extra):
    return offer(f, parent, revision=dispatch['revision'],
                 recovery_receipt_step_id=old['step']['id'], **extra)[0]


def stale_accepted(f):
    parent, dispatch, old = accepted(f)
    old = receipt_action(f, old, 'SUBMIT', text='Immutable original generation receipt').json()
    old = receipt_action(f, old, 'ACKNOWLEDGE').json()
    parent = changed_materials(f, parent)
    return parent, dispatch, old


def recovered(f):
    parent, dispatch, old = stale_accepted(f)
    response = recovery_offer(f, parent, dispatch, old)
    assert response.status_code == 201, response.text
    offered = response.json()
    response = dispatch_action(f, offered, 'ACCEPT')
    assert response.status_code == 200, response.text
    current = response.json()
    return parent, dispatch, old, offered, current, receipt_read(f, current['receipt_step_id'])


def test_explicit_same_executor_reoffer_accept_creates_fresh_generation_preserving_history(receipt_fixture):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f)
    original = records(f)
    grants = authority(f)
    response = recovery_offer(f, parent, dispatch, old)
    assert response.status_code == 201, response.text
    offered = response.json()
    assert offered['current_offer']['state'] == 'OFFERED'
    assert offered['current_offer']['executor_id'] == old['step']['executor_id']
    assert offered['receipt_step_id'] is None and offered['current_receipt_step_id'] is None
    old_read = receipt_read(f, old['step']['id'])
    assert not old_read['is_current_step'] and old_read['record_mode'] == 'HISTORICAL_GENERATION'
    response = dispatch_action(f, offered, 'ACCEPT')
    assert response.status_code == 200, response.text
    current = response.json()
    assert current['receipt_step_id'] != old['step']['id']
    fresh = receipt_read(f, current['receipt_step_id'])
    assert fresh['is_current_step'] and fresh['current_receipt'] is None
    assert fresh['step']['preparation_revision'] == parent['revision']
    assert fresh['step']['preparation_sha256'] == parent['snapshot_sha256']
    assert fresh['step']['state'] == 'AWAITING_RECEIPT'
    assert fresh['receipt_history'] == []
    for table in ('service_receipt_steps', 'service_step_receipts', 'service_receipt_events', 'service_dispatch_offers'):
        after = records(f)[table]
        assert all(row in after for row in original[table])
    assert current['offers'][0] == dispatch['current_offer']
    # No old acknowledgement can substitute for actual new submission.
    premature = f[3].post('/api/executor-receipts/' + fresh['step']['id'] + '/commands',
        headers=headers(f[2], key=uuid4().hex), json=dict(action='ACKNOWLEDGE',
            expected_revision=fresh['step']['revision'], reason='Old generation cannot acknowledge new work',
            receipt_sha256=old['current_receipt']['source_sha256']))
    assert premature.status_code == 409
    fresh = receipt_action(f, fresh, 'SUBMIT', text='Actual new generation executor work log').json()
    fresh = receipt_action(f, fresh, 'ACKNOWLEDGE').json()
    assert fresh['step']['state'] == 'LOCAL_ACKNOWLEDGED'
    assert authority(f) == grants and not fresh['case_goal_completed']
    with f[1].connect() as c:
        events = c.execute('SELECT id,action FROM service_dispatch_events ORDER BY revision').fetchall()
        for event in events:
            recipients = {r['recipient_id'] for r in c.execute('SELECT recipient_id FROM dispatch_notice_outbox WHERE event_id=%s', (event['id'],)).fetchall()}
            assert recipients == {'fixture-a', 'executor-a' if event['action'] in ('OFFER', 'REOFFER') else REVIEWER}


@pytest.mark.parametrize('action', ['SUBMIT', 'ACKNOWLEDGE', 'REQUEST_CHANGES', 'REOPEN'])
def test_old_generation_is_read_only_after_new_offer_and_accept(receipt_fixture, action):
    f = receipt_fixture
    parent, _, old, _, _, _ = recovered(f)
    before = records(f)
    assert receipt_action(f, old, action).status_code == 409
    assert records(f) == before
    current = receipt_read(f, old['step']['id'])
    assert not current['is_current_step'] and current['step'] == old['step']
    assert current['receipt_history'] == old['receipt_history']


def test_unknown_committed_old_submit_reply_only_restores_historical_event(receipt_fixture):
    f = receipt_fixture
    parent, dispatch, initial = accepted(f)
    key = 'lost-original-receipt-reply'
    old = receipt_action(f, initial, 'SUBMIT', key=key).json()
    parent = changed_materials(f, parent)
    response = recovery_offer(f, parent, dispatch, old)
    assert response.status_code == 201, response.text
    new = dispatch_action(f, response.json(), 'ACCEPT').json()
    before = records(f)
    replay = receipt_action(f, initial, 'SUBMIT', key=key)
    assert replay.status_code == 200, replay.text
    replay = replay.json()
    assert replay['event'] == old['event']
    assert replay['replay_mode'] == 'HISTORICAL_COMMITTED_EVENT' and not replay['is_current_step']
    assert records(f) == before
    assert receipt_read(f, new['receipt_step_id'])['current_receipt'] is None
    assert receipt_action(f, initial, 'SUBMIT', key=key, text='changed original key body').status_code == 409


@pytest.mark.parametrize('mutation', ['missing_predecessor', 'wrong_predecessor', 'stale_dispatch', 'stale_preparation', 'different_executor', 'fresh_parent'])
def test_recovery_requires_exact_stale_accepted_generation_and_cas(receipt_fixture, mutation):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f) if mutation != 'fresh_parent' else accepted(f)
    before = records(f)
    if mutation == 'missing_predecessor': response = offer(f, parent, revision=dispatch['revision'])[0]
    elif mutation == 'wrong_predecessor':
        response = offer(f, parent, revision=dispatch['revision'], recovery_receipt_step_id=str(uuid4()))[0]
    elif mutation == 'stale_dispatch': response = recovery_offer(f, parent, {**dispatch, 'revision': 0}, old)
    elif mutation == 'stale_preparation': response = recovery_offer(f, {**parent, 'revision': 1}, dispatch, old)
    elif mutation == 'different_executor': response = recovery_offer(f, parent, dispatch, old, executor='unassigned')
    else: response = recovery_offer(f, parent, dispatch, old)
    assert response.status_code == (403 if mutation == 'different_executor' else 409), response.text
    assert records(f) == before


@pytest.mark.parametrize('user', ['fixture-a', 'fixture-b', 'fixture-c', 'executor-a', 'executor-b', 'unassigned', 'prep-specialist-fixture-b'])
def test_recovery_offer_role_and_tenant_scope_do_not_expand_authority(receipt_fixture, user):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f)
    before = records(f)
    grants = authority(f)
    assert recovery_offer(f, parent, dispatch, old, user=user).status_code == 403
    assert records(f) == before and authority(f) == grants


@pytest.mark.parametrize('change', ['reviewer_read', 'reviewer_grant', 'owner_execute', 'owner_prepare', 'executor_read', 'executor_assignment'])
def test_recovery_rechecks_current_grants_before_write_and_old_key_replay(receipt_fixture, change):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f)
    key = 'committed-recovery-offer'
    response = recovery_offer(f, parent, dispatch, old, key=key)
    assert response.status_code == 201, response.text
    offered = response.json()
    with f[1].connect() as c:
        if change.endswith('_read') or change == 'owner_execute':
            who = REVIEWER if change.startswith('reviewer') else 'fixture-a' if change.startswith('owner') else 'executor-a'
            c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',
                      (who, 'EXECUTE' if change == 'owner_execute' else 'READ'))
        elif change in ('reviewer_grant', 'owner_prepare'):
            c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',
                      (REVIEWER if change.startswith('reviewer') else 'fixture-a',))
        else: c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
    before = records(f)
    grants = authority(f)
    assert dispatch_action(f, offered, 'ACCEPT').status_code == 403
    assert recovery_offer(f, parent, dispatch, old, key=key).status_code == 403
    assert records(f) == before and authority(f) == grants


@pytest.mark.parametrize('same_key', [False, True])
def test_concurrent_recovery_offer_and_accept_create_single_generation(receipt_fixture, same_key):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f)
    body = sd.Offer(expected_preparation_revision=parent['revision'], expected_dispatch_revision=dispatch['revision'],
        executor_id='executor-a', reason='Explicit concurrent recovery', recovery_receipt_step_id=old['step']['id'])
    def send_offer(index):
        try: return sd.offer(f[0], f[2][REVIEWER], UUID(parent['preparation_id']), 'shared-offer' if same_key else f'offer-{index}', body)
        except Conflict: return 'CONFLICT'
    with ThreadPoolExecutor(2) as pool: responses = list(pool.map(send_offer, range(2)))
    assert responses.count('CONFLICT') == (0 if same_key else 1)
    current = next(r for r in responses if isinstance(r, dict))
    body = sd.Command(action='ACCEPT', expected_revision=current['revision'], reason='Actual concurrent acceptance')
    def send_accept(index):
        try: return sd.command(f[0], f[2]['executor-a'], UUID(str(current['dispatch_id'])), 'shared-accept' if same_key else f'accept-{index}', body)
        except Conflict: return 'CONFLICT'
    with ThreadPoolExecutor(2) as pool: responses = list(pool.map(send_accept, range(2)))
    assert responses.count('CONFLICT') == (0 if same_key else 1)
    after = records(f)
    assert len(after['service_dispatch_offers']) == len(after['service_receipt_steps']) == 2
    assert len(after['service_step_receipts']) == 1


def test_even_legal_other_executor_cannot_replace_original_material_responsibility(receipt_fixture):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f)
    # Explicit isolated prerequisite, not an effect of a product recovery action.
    f[1].assign_status('unassigned', UUID(parent['run_id']), active=True)
    before = records(f)
    grants = authority(f)
    assert recovery_offer(f, parent, dispatch, old, executor='unassigned').status_code == 409
    assert records(f) == before and authority(f) == grants


@pytest.mark.parametrize('when', ['reoffer', 'accept'])
@pytest.mark.parametrize('table', ['service_dispatch_events', 'dispatch_notice_outbox'])
def test_event_or_notice_failure_rolls_back_complete_generation_transaction(receipt_fixture, when, table):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f)
    if when == 'accept':
        response = recovery_offer(f, parent, dispatch, old)
        assert response.status_code == 201, response.text
        offered = response.json()
    before = records(f)
    grants = authority(f)
    with f[1].connect() as c:
        c.execute("CREATE FUNCTION fixture_recovery_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'isolated recovery rollback fault'; END $$")
        c.execute('CREATE TRIGGER fixture_recovery_fault BEFORE INSERT ON ' + table + ' FOR EACH ROW EXECUTE FUNCTION fixture_recovery_fault()')
    with pytest.raises(psycopg.errors.RaiseException):
        if when == 'reoffer': recovery_offer(f, parent, dispatch, old)
        else: dispatch_action(f, offered, 'ACCEPT')
    assert records(f) == before and authority(f) == grants
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n'] == 1


def test_actual_five_step_source_change_blocking_and_explicit_generation_recovery(link_fixture):
    from test_service_case_steps import (setup, GOALS, adopt, accepted as plan_accepted,
        verified, read as plan_read, command as plan_command)
    from test_case_lifecycle import read as lifecycle_read, act as lifecycle_action
    f = link_fixture
    parent = setup(f, GOALS[4])
    assert adopt(f, parent).status_code == 201
    combination, dispatch = plan_accepted(f, parent)
    verified(f, parent, 'P3')
    old = receipt_read(f, dispatch['receipt_step_id'])
    old = receipt_action(f, old, 'SUBMIT', text='Previously completed original material work').json()
    old = receipt_action(f, old, 'ACKNOWLEDGE').json()
    verified(f, parent, 'P4')
    local = lifecycle_action(f, parent, lifecycle_read(f, parent).json(), 'REVALIDATE')
    assert local.status_code == 200, local.text
    original_plan = verified(f, parent, 'P5')
    assert original_plan['state'] == 'VERIFIED'
    ids = [s['id'] for s in original_plan['steps']]
    history = records(f)
    grants = authority(f)
    parent = changed_materials(f, parent)
    assert receipt_action(f, old, 'SUBMIT').status_code == 409
    assert recovery_offer(f, parent, dispatch, old).status_code == 409
    assert plan_command(f, parent, 'P3').status_code == 409
    assert plan_command(f, parent, 'P4').status_code == 409
    assert plan_command(f, parent, 'P5').status_code == 409
    assert records(f) == history
    verified(f, parent, 'P1')
    # Rechecking the plan cannot fabricate the newly required resource binding.
    assert plan_command(f, parent, 'P2').status_code == 409
    response = resource_link(f, parent, combination, revision=1)
    assert response.status_code == 201, response.text
    verified(f, parent, 'P2')
    assert plan_command(f, parent, 'P3').status_code == 409
    response = recovery_offer(f, parent, dispatch, old)
    assert response.status_code == 201, response.text
    response = dispatch_action(f, response.json(), 'ACCEPT')
    assert response.status_code == 200, response.text
    current = response.json()
    new = receipt_read(f, current['receipt_step_id'])
    assert new['step']['id'] != old['step']['id']
    assert receipt_action(f, new, 'SUBMIT').status_code == 409
    verified(f, parent, 'P3')
    assert plan_command(f, parent, 'P4').status_code == 409
    assert plan_command(f, parent, 'P5').status_code == 409
    new = receipt_action(f, new, 'SUBMIT', text='Actual executor work against freshly confirmed materials').json()
    assert plan_command(f, parent, 'P4').status_code == 409
    new = receipt_action(f, new, 'ACKNOWLEDGE').json()
    verified(f, parent, 'P4')
    assert plan_command(f, parent, 'P5').status_code == 409
    local = lifecycle_action(f, parent, lifecycle_read(f, parent).json(), 'REVALIDATE')
    assert local.status_code == 200, local.text
    current_plan = verified(f, parent, 'P5')
    assert current_plan['state'] == 'VERIFIED'
    assert [s['id'] for s in current_plan['steps']] == ids
    assert not current_plan['case_goal_completed'] and not current_plan['new_grants']
    assert new['qualification'] == 'NOT_EVALUATED' and new['offline_fulfillment'] == 'NO_EVIDENCE'
    assert authority(f) == grants
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM cases WHERE id=%s', (parent['case_id'],)).fetchone()['state'] != 'FULFILLED'
        assert c.execute('SELECT count(*) n FROM runs').fetchone()['n'] == 1
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n'] == 2


def test_lost_committed_recovery_accept_reply_replays_without_reviving_old_generation(receipt_fixture, monkeypatch):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f)
    response = recovery_offer(f, parent, dispatch, old)
    assert response.status_code == 201, response.text
    offered = response.json()
    original_post = f[3].post
    committed = []
    def lose_committed_response(*args, **kwargs):
        response = original_post(*args, **kwargs)
        assert response.status_code == 200, response.text
        committed.append(response.json())
        raise RuntimeError('Injected response loss after actual API transaction committed')
    monkeypatch.setattr(f[3], 'post', lose_committed_response)
    key = 'lost-recovery-accept-response'
    with pytest.raises(RuntimeError): dispatch_action(f, offered, 'ACCEPT', key=key)
    monkeypatch.setattr(f[3], 'post', original_post)
    before = records(f)
    response = dispatch_action(f, offered, 'ACCEPT', key=key)
    assert response.status_code == 200
    assert response.json()['event'] == committed[0]['event']
    assert records(f) == before
    second = receipt_read(f, committed[0]['receipt_step_id'])
    parent = changed_materials(f, parent)
    response = recovery_offer(f, parent, committed[0], second)
    assert response.status_code == 201, response.text
    latest = dispatch_action(f, response.json(), 'ACCEPT').json()
    before = records(f)
    replay = dispatch_action(f, offered, 'ACCEPT', key=key)
    assert replay.status_code == 200, replay.text
    assert replay.json()['event'] == committed[0]['event']
    assert replay.json()['receipt_step_id'] == latest['receipt_step_id']
    assert replay.json()['receipt_step_id'] != committed[0]['receipt_step_id']
    assert records(f) == before
    assert dispatch_action(f, offered, 'ACCEPT', key=key, reason='Changed lost-reply body').status_code == 409
    with f[1].connect() as c:
        assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n'] == 3


@pytest.mark.parametrize('when', ['accept', 'submit'])
@pytest.mark.parametrize('change', ['text', 'source_sha256'])
def test_actual_current_material_text_or_hash_drift_blocks_recovery_execution(receipt_fixture, when, change):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f)
    response = recovery_offer(f, parent, dispatch, old)
    assert response.status_code == 201, response.text
    offered = response.json()
    if when == 'submit':
        response = dispatch_action(f, offered, 'ACCEPT')
        assert response.status_code == 200, response.text
        step = receipt_read(f, response.json()['receipt_step_id'])
    # Independent source writer exposes drift without changing the saved
    # preparation revision or accepted hash. No product Grant is changed.
    with f[1].connect() as c:
        value = 'Unreviewed actual material content drift' if change == 'text' else '0' * 64
        c.execute('UPDATE preparation_evidence SET ' + change + '=%s WHERE id=(SELECT id FROM preparation_evidence '
                  "WHERE preparation_id=%s AND slot='need_summary' ORDER BY version DESC LIMIT 1)",
                  (value, parent['preparation_id']))
    before = records(f)
    grants = authority(f)
    response = dispatch_action(f, offered, 'ACCEPT') if when == 'accept' else receipt_action(f, step, 'SUBMIT')
    assert response.status_code == 409, response.text
    assert records(f) == before and authority(f) == grants


def test_corrupt_previous_accept_event_cannot_authorize_new_generation(receipt_fixture):
    f = receipt_fixture
    parent, dispatch, old = stale_accepted(f)
    with f[1].connect() as c:
        c.execute("UPDATE service_dispatch_events SET payload=jsonb_set(payload,'{receipt_step_id}',to_jsonb(%s::text)) "
                  "WHERE dispatch_id=%s AND action='ACCEPT'", (str(uuid4()), dispatch['dispatch_id']))
    before = records(f)
    grants = authority(f)
    assert recovery_offer(f, parent, dispatch, old).status_code == 409
    assert records(f) == before and authority(f) == grants


def test_corrupt_current_offer_pointer_never_falls_back_to_any_historical_step(receipt_fixture):
    f = receipt_fixture
    parent, _, old, _, current, new = recovered(f)
    with f[1].connect() as c:
        c.execute('UPDATE service_dispatch_offers SET receipt_step_id=%s WHERE id=%s',
                  (old['step']['id'], current['current_offer']['id']))
    before = records(f)
    grants = authority(f)
    for row in (old, new):
        observed = receipt_read(f, row['step']['id'])
        assert not observed['is_current_step']
        assert receipt_action(f, row, 'SUBMIT').status_code == 409
    assert receipt_action(f, old, 'ACKNOWLEDGE').status_code == 409
    assert records(f) == before and authority(f) == grants


@pytest.mark.parametrize('state', ['OFFERED', 'DECLINED', 'WITHDRAWN', 'ACCEPTED'])
def test_executor_coordination_requires_actual_current_accepted_generation(link_fixture, state):
    from test_service_case_steps import (setup, adopt, accepted as plan_accepted,
        verified, command as plan_command)
    f = link_fixture
    parent = setup(f)
    assert adopt(f, parent).status_code == 201
    combination, original = plan_accepted(f, parent)
    old = receipt_read(f, original['receipt_step_id'])
    parent = changed_materials(f, parent)
    verified(f, parent, 'P1')
    assert resource_link(f, parent, combination, revision=1).status_code == 201
    verified(f, parent, 'P2')
    response = recovery_offer(f, parent, original, old)
    assert response.status_code == 201, response.text
    current = response.json()
    if state != 'OFFERED':
        action = 'DECLINE' if state == 'DECLINED' else 'WITHDRAW' if state == 'WITHDRAWN' else 'ACCEPT'
        response = dispatch_action(f, current, action)
        assert response.status_code == 200, response.text
        current = response.json()
    before = records(f)
    grants = authority(f)
    response = plan_command(f, parent, 'P3', 'BEGIN', user='executor-a')
    assert response.status_code == (200 if state == 'ACCEPTED' else 409), response.text
    assert records(f) == before and authority(f) == grants


def test_selected_receipt_generation_with_wrong_case_binding_cannot_supply_current_proof(receipt_fixture):
    f = receipt_fixture
    parent, _, old, _, current, new = recovered(f)
    other = ready(f)  # A real isolated second Case, never a copied source Case.
    with f[1].connect() as c:
        c.execute('UPDATE service_receipt_steps SET case_id=%s WHERE id=%s',
                  (other['case_id'], new['step']['id']))
    before = records(f)
    grants = authority(f)
    with f[1].connect() as c:
        source = c.execute('SELECT * FROM preparations WHERE id=%s', (parent['preparation_id'],)).fetchone()
        assert er.current_step(c, source) is None
    observed = receipt_read(f, new['step']['id'])
    assert not observed['is_current_step']
    assert receipt_action(f, new, 'SUBMIT').status_code == 409
    assert not receipt_read(f, old['step']['id'])['is_current_step']
    assert records(f) == before and authority(f) == grants
