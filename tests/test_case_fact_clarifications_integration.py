"""Actual product integration gold; core module tests are owned separately.

These tests intentionally require the integrated API and real UUID PostgreSQL
fixture. Until integration and its scheduled test window arrive, they are a
reviewable test specification, not evidence of a completed product slice.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from parkweave import controlled_plans as cp
from test_preparation import preparation_fixture, headers, command as prep_command, read as prep_read
from test_executor_receipts import receipt_fixture, act as receipt_command
from test_case_resources import link_fixture, post as resource_link
from test_service_dispatches import offer, command as dispatch_command, REVIEWER
from test_service_case_steps import (setup, GOALS, adopt, accepted, verified,
    read as plan_read, command as plan_command)
from test_case_lifecycle import read as local_read, act as local_command
from test_dispatch_recovery import receipt_read

PROFILE = 'LOCAL_SERVICE_PREPARATION_FACTS_V1'
PURPOSE = 'SERVICE_PREPARATION'
FIELDS = ('region', 'employees', 'service_need')


def authority(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text').fetchall()
                for table in ('principals', 'capability_grants', 'field_grants', 'action_grants',
                              'preparation_grants', 'synthetic_resource_grants', 'run_assignments')}


def business(f):
    """Fact observations/refusals must not copy or mutate downstream records."""
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text').fetchall()
                for table in ('preparation_evidence', 'case_resource_links', 'resource_case_claims',
                              'synthetic_resource_holds', 'synthetic_resource_combinations',
                              'service_dispatches', 'service_dispatch_offers', 'service_dispatch_events',
                              'service_receipt_steps', 'service_step_receipts', 'service_receipt_events',
                              'case_local_lifecycles', 'case_local_events', 'dispatch_notice_outbox',
                              'dispatch_notices', 'cases')}


def preparation_records(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text').fetchall()
                for table in ('preparations', 'preparation_events', 'preparation_evidence')}


def assertions(f):
    with f[1].connect() as c:
        return c.execute('SELECT * FROM fact_assertions ORDER BY id').fetchall()


def fact_body(field, value, source, *, expired=False):
    now = datetime.now(timezone.utc)
    return dict(schema_version='parkweave-domain/1.0-draft', field=field, value=value,
        unit='people' if field == 'employees' else 'text',
        source_ref=dict(id=source, kind='SYNTHETIC', revision='1'),
        source_excerpt='PRIVATE_FACT_EXCERPT_' + source, purpose=PURPOSE,
        validity=dict(valid_from=(now - timedelta(days=1)).isoformat(),
                      valid_until=(now + timedelta(days=-0.5 if expired else 3)).isoformat(), timezone='UTC'))


def post_fact(f, field, value, source, user='fixture-a', **options):
    response = f[3].post('/api/facts', headers=headers(f[2], user, uuid4().hex),
                         json=fact_body(field, value, source, **options))
    assert response.status_code == 201, response.text
    return response.json()['fact_id']


def seed_facts_through_original_api(f):
    selected = {}
    for field, value in zip(FIELDS, ('PRIVATE_REGION_SELECTED', 17, 'PRIVATE_SERVICE_NEED_SELECTED')):
        selected[field] = post_fact(f, field, value, 'selected-' + field)
    # A competing valid assertion must remain visible and unresolved globally.
    post_fact(f, 'region', 'PRIVATE_CONFLICTING_REGION', 'competing-region')
    return selected


def fact_read(f, parent, user='fixture-a'):
    return f[3].get('/api/preparations/' + parent['preparation_id'] + '/fact-clarifications',
                    headers=headers(f[2], user))


def declare(f, parent, key=None, user='fixture-a', **extra):
    body = dict(expected_preparation_revision=parent['revision'], expected_clarification_revision=0,
                profile=PROFILE, purpose=PURPOSE, reason='Owner explicitly declares this Case fact purpose', **extra)
    return f[3].post('/api/preparations/' + parent['preparation_id'] + '/fact-clarifications/declare',
                     headers=headers(f[2], user, key or uuid4().hex), json=body)


def confirm_body(f, parent, selected):
    """Bind explicit owner choices to the current real assertion IDs and hashes."""
    response = fact_read(f, parent)
    assert response.status_code == 200, response.text
    view = response.json()
    response = f[3].get('/api/facts', params=[('fields', field) for field in FIELDS], headers=headers(f[2]))
    assert response.status_code == 200, response.text
    assertions = {item['id']: item for item in response.json()['facts']}
    return dict(expected_preparation_revision=view['preparation_revision'],
        expected_clarification_revision=view['revision'], expected_source_sha256=view['source_sha256'],
        choices=[dict(field=field, assertion_id=selected[field],
                      expected_assertion_revision=assertions[selected[field]]['revision'],
                      expected_assertion_fingerprint=assertions[selected[field]]['fingerprint']) for field in FIELDS],
        reason='Owner selects current actual sources only for this Case purpose')


def confirm(f, parent, body, key=None, user='fixture-a'):
    return f[3].post('/api/preparations/' + parent['preparation_id'] + '/fact-clarifications/confirm',
                     headers=headers(f[2], user, key or uuid4().hex), json=body)


def current_parent(f, parent):
    response = prep_read(f, parent)
    assert response.status_code == 200, response.text
    row = response.json()['preparation']
    return dict(preparation_id=str(row['id']), revision=row['revision'], run_id=str(row['run_id']),
                case_id=str(row['case_id']), state=row['state'])


def human_review_and_confirm(f, parent):
    response = prep_command(f, parent, 'REVIEW', REVIEWER, reason='Real specialist checks current Case materials and purpose')
    assert response.status_code == 200, response.text
    response = prep_command(f, response.json(), 'CONFIRM', reason='Owner confirms this actual reviewed preparation version')
    assert response.status_code == 200, response.text
    return response.json()


def assert_resource_p1_uses_current_fact_descriptor(f, parent):
    response = f[3].get('/api/preparations/' + parent['preparation_id'] + '/resource-plan-binding',
                         headers=headers(f[2]))
    assert response.status_code == 200, response.text
    with f[0].connect() as c:
        current = c.execute('SELECT * FROM preparations WHERE id=%s', (parent['preparation_id'],)).fetchone()
        _, source_snapshots = cp._sources(f[0], c, current)
    checkpoint = response.json()['checkpoints']['P1']
    assert checkpoint['current_snapshot'] == source_snapshots['P1']
    assert checkpoint['current_source_sha256'] == cp._hash(source_snapshots['P1'])
    return response.json()


def declared_and_selected(f):
    parent = setup(f, GOALS[4])
    selected = seed_facts_through_original_api(f)
    response = declare(f, parent)
    assert response.status_code == 200, response.text
    parent = current_parent(f, parent)
    body = confirm_body(f, parent, selected)
    response = confirm(f, parent, body)
    assert response.status_code == 200, response.text
    return current_parent(f, parent), selected, response.json()


def complete_and_close(f, parent):
    assert adopt(f, parent).status_code == 201
    combination, dispatch = accepted(f, parent)
    verified(f, parent, 'P3')
    receipt = receipt_read(f, dispatch['receipt_step_id'])
    receipt = receipt_command(f, receipt, 'SUBMIT', text='Actual executor record for this selected fact purpose').json()
    ack_key = uuid4().hex
    ack_body = dict(action='ACKNOWLEDGE', expected_revision=receipt['step']['revision'],
                    reason='SYNTHETIC owner decision', receipt_sha256=receipt['current_receipt']['source_sha256'])
    response = receipt_command(f, receipt, 'ACKNOWLEDGE', key=ack_key)
    assert response.status_code == 200, response.text
    receipt = response.json()
    verified(f, parent, 'P4')
    response = local_command(f, parent, local_read(f, parent).json(), 'REVALIDATE')
    assert response.status_code == 200, response.text
    response = local_command(f, parent, local_read(f, parent).json(), 'CLOSE_LOCAL_RECORD')
    assert response.status_code == 200, response.text
    verified(f, parent, 'P5')
    return combination, dispatch, receipt, response.json(), (ack_key, ack_body)


def test_declared_profile_blocks_original_human_review_until_actual_fact_choices(link_fixture):
    f = link_fixture
    parent = setup(f, GOALS[4])
    selected = seed_facts_through_original_api(f)
    permissions = authority(f)
    old_revision = parent['revision']
    response = declare(f, parent)
    assert response.status_code == 200, response.text
    parent = current_parent(f, parent)
    assert parent['revision'] == old_revision + 1 and parent['state'] == 'IN_PREPARATION'
    assert prep_read(f, parent).json()['preparation']['review_sha256'] is None
    before = business(f)
    assert prep_command(f, parent, 'REVIEW', REVIEWER, reason='Cannot skip owner fact purpose choices').status_code == 409
    assert prep_command(f, parent, 'CONFIRM', reason='Cannot inherit old review').status_code == 409
    assert business(f) == before
    body = confirm_body(f, parent, selected)
    response = confirm(f, parent, body)
    assert response.status_code == 200, response.text
    parent = current_parent(f, parent)
    assert parent['revision'] == old_revision + 2 and parent['state'] == 'IN_PREPARATION'
    assert prep_read(f, parent).json()['preparation']['review_sha256'] is None
    parent = human_review_and_confirm(f, parent)
    assert parent['state'] == 'LOCAL_CONFIRMED' and authority(f) == permissions
    view = fact_read(f, parent).json()
    assert view['state'] == 'CURRENT' and view['satisfied']
    assert view['revision'] == 2 and [entry['action'] for entry in view['history']] == ['DECLARE_FACT_PURPOSE', 'CONFIRM_FACT_PURPOSE']
    assert all(question['state'] == 'USER_SELECTED_FOR_CASE' for question in view['necessary_questions'])
    projection = assert_resource_p1_uses_current_fact_descriptor(f, parent)
    assert projection['checkpoints']['P1']['current_snapshot']['fact_clarification']['satisfied']


def test_original_fact_append_invalidates_actual_gates_then_requires_complete_explicit_recovery(link_fixture):
    f = link_fixture
    parent, selected, _ = declared_and_selected(f)
    parent = human_review_and_confirm(f, parent)
    combination, old_dispatch, old_receipt, old_local, old_ack = complete_and_close(f, parent)
    permissions = authority(f)
    history = deepcopy(business(f))
    old_plan = plan_read(f, parent).json()
    old_step_ids = [step['id'] for step in old_plan['steps']]
    old_parent_revision = parent['revision']
    post_fact(f, 'region', 'PRIVATE_NEW_COMPETING_REGION', 'new-competition-after-close')
    before = business(f)
    old_fact_version = fact_read(f, parent).json()
    assert old_fact_version['state'] == 'STALE' and not old_fact_version['satisfied']
    old_fact_history = deepcopy(old_fact_version['history'])
    projection = assert_resource_p1_uses_current_fact_descriptor(f, parent)
    assert 'CURRENT_FACT_PURPOSE_CONFIRMATION_REQUIRED' in projection['checkpoints']['P1']['issues']
    assert prep_command(f, parent, 'CONFIRM', reason='An old decision cannot silently authorize current facts').status_code == 409
    assert receipt_command(f, old_receipt, 'SUBMIT').status_code == 409
    assert offer(f, parent, revision=old_dispatch['revision'], recovery_receipt_step_id=old_receipt['step']['id'])[0].status_code == 409
    assert plan_command(f, parent, 'P1').status_code == 409
    assert plan_command(f, parent, 'P5').status_code == 409
    assert local_command(f, parent, local_read(f, parent).json(), 'CLOSE_LOCAL_RECORD').status_code == 409
    assert business(f) == before
    body = confirm_body(f, parent, selected)
    response = confirm(f, parent, body)
    assert response.status_code == 200, response.text
    parent = current_parent(f, parent)
    assert parent['revision'] == old_parent_revision + 1 and parent['state'] == 'IN_PREPARATION'
    assert prep_read(f, parent).json()['preparation']['review_sha256'] is None
    assert fact_read(f, parent).json()['history'][:-1] == old_fact_history
    assert prep_command(f, parent, 'CONFIRM', reason='A new fact selection still needs specialist review').status_code == 409
    parent = human_review_and_confirm(f, parent)
    verified(f, parent, 'P1')
    assert plan_command(f, parent, 'P2').status_code == 409
    response = resource_link(f, parent, combination, revision=1)
    assert response.status_code == 201, response.text
    verified(f, parent, 'P2')
    response = offer(f, parent, revision=old_dispatch['revision'], recovery_receipt_step_id=old_receipt['step']['id'])[0]
    assert response.status_code == 201, response.text
    response = dispatch_command(f, response.json(), 'ACCEPT')
    assert response.status_code == 200, response.text
    dispatch = response.json()
    receipt = receipt_read(f, dispatch['receipt_step_id'])
    assert receipt['step']['id'] != old_receipt['step']['id'] and receipt['current_receipt'] is None
    assert receipt['step']['preparation_revision'] > old_receipt['step']['preparation_revision']
    assert receipt_command(f, old_receipt, 'REOPEN').status_code == 409
    before_replay = business(f)
    response = f[3].post('/api/executor-receipts/' + old_receipt['step']['id'] + '/commands',
                         headers=headers(f[2], key=old_ack[0]), json=old_ack[1])
    assert response.status_code == 200, response.text
    assert response.json()['event'] == old_receipt['event']
    assert response.json()['replay_mode'] == 'HISTORICAL_COMMITTED_EVENT'
    assert not response.json()['is_current_step'] and business(f) == before_replay
    verified(f, parent, 'P3')
    assert plan_command(f, parent, 'P4').status_code == 409
    receipt = receipt_command(f, receipt, 'SUBMIT', text='Actual new receipt against the reconfirmed fact purpose').json()
    assert receipt['current_receipt']['version'] == 1
    receipt = receipt_command(f, receipt, 'ACKNOWLEDGE').json()
    verified(f, parent, 'P4')
    local = local_read(f, parent).json()
    assert local['cycle'] == old_local['cycle'] and local['local_record_state'] != 'READY'
    assert local_command(f, parent, local, 'REVALIDATE').status_code == 409
    response = local_command(f, parent, local, 'REOPEN')
    assert response.status_code == 200, response.text
    assert response.json()['cycle'] == old_local['cycle'] + 1
    response = local_command(f, parent, local_read(f, parent).json(), 'REVALIDATE')
    assert response.status_code == 200, response.text
    response = local_command(f, parent, local_read(f, parent).json(), 'CLOSE_LOCAL_RECORD')
    assert response.status_code == 200, response.text
    final = verified(f, parent, 'P5')
    assert [step['id'] for step in final['steps']] == old_step_ids
    assert not final['case_goal_completed'] and not final['new_grants']
    after = business(f)
    for table in ('preparation_evidence', 'service_dispatch_offers', 'service_step_receipts', 'service_receipt_events', 'case_local_events'):
        assert all(row in after[table] for row in history[table])
    assert authority(f) == permissions
    with f[1].connect() as c:
        assert c.execute('SELECT state FROM cases WHERE id=%s', (parent['case_id'],)).fetchone()['state'] == 'WAITING_CONFIRMATION'


def test_owner_private_fact_choices_do_not_leak_through_original_shared_projections(link_fixture):
    f = link_fixture
    parent, selected, _ = declared_and_selected(f)
    parent = human_review_and_confirm(f, parent)
    before, permissions, facts = preparation_records(f), authority(f), assertions(f)
    owner = fact_read(f, parent)
    assert owner.status_code == 200, owner.text
    assert 'PRIVATE_REGION_SELECTED' in owner.text and 'PRIVATE_FACT_EXCERPT_' in owner.text
    for user in ('fixture-a', REVIEWER):
        response = prep_read(f, parent, user)
        assert response.status_code == 200, response.text
        assert 'fact_clarifications' not in response.json()['preparation']
        encoded = response.text
        assert all(value not in encoded for value in selected.values())
        assert 'PRIVATE_REGION_SELECTED' not in encoded and 'PRIVATE_FACT_EXCERPT_' not in encoded
    for user in (REVIEWER, 'executor-a', 'fixture-b', 'fixture-c'):
        response = fact_read(f, parent, user)
        assert response.status_code == 403, response.text
        assert 'PRIVATE_' not in response.text and all(value not in response.text for value in selected.values())
    assert preparation_records(f) == before and authority(f) == permissions and assertions(f) == facts


def test_old_confirm_key_restores_history_without_reactivating_changed_fact_source(link_fixture):
    f = link_fixture
    parent = setup(f, GOALS[4])
    selected = seed_facts_through_original_api(f)
    assert declare(f, parent).status_code == 200
    parent = current_parent(f, parent)
    body, key = confirm_body(f, parent, selected), uuid4().hex
    first = confirm(f, parent, body, key)
    assert first.status_code == 200, first.text
    parent = human_review_and_confirm(f, current_parent(f, parent))
    post_fact(f, 'service_need', 'PRIVATE_NEW_SERVICE_NEED', 'changed-after-confirmed-key')
    before, downstream, permissions = preparation_records(f), business(f), authority(f)
    replay = confirm(f, parent, body, key)
    assert replay.status_code == 200, replay.text
    assert replay.json()['recovery'] == 'HISTORICAL_COMMITTED_EVENT'
    assert not replay.json()['current_decision_restored']
    assert fact_read(f, parent).json()['state'] == 'STALE'
    # The true original prep event is immutable; the current decision is still stale.
    assert preparation_records(f) == before and business(f) == downstream and authority(f) == permissions
    assert prep_command(f, parent, 'REVIEW', REVIEWER, reason='Historical replay cannot restore active choice').status_code == 409
    changed = deepcopy(body)
    changed['reason'] = 'Same key with changed body is forbidden'
    assert confirm(f, parent, changed, key).status_code == 409
    assert preparation_records(f) == before and business(f) == downstream


@pytest.mark.parametrize('revocation', ['field_read', 'field_write', 'prepare', 'execute'])
def test_current_authority_precedes_old_fact_confirmation_key_replay(link_fixture, revocation):
    f = link_fixture
    parent = setup(f, GOALS[0])
    selected = seed_facts_through_original_api(f)
    assert declare(f, parent).status_code == 200
    parent = current_parent(f, parent)
    body, key = confirm_body(f, parent, selected), uuid4().hex
    first = confirm(f, parent, body, key)
    assert first.status_code == 200, first.text
    # Revocation is isolated fixture administration, never an application grant.
    with f[1].connect() as c:
        if revocation.startswith('field_'):
            c.execute("UPDATE field_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' "
                      "AND field_name='region' AND purpose=%s AND capability=%s",
                      (PURPOSE, 'READ' if revocation == 'field_read' else 'WRITE'))
        elif revocation == 'prepare':
            c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        else:
            c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before, downstream, permissions = preparation_records(f), business(f), authority(f)
    assert confirm(f, parent, body, key).status_code == 403
    assert preparation_records(f) == before and business(f) == downstream and authority(f) == permissions


@pytest.mark.parametrize('mutation', ['source_append', 'source_hash', 'preparation_revision', 'assertion_revision', 'foreign_assertion'])
def test_original_api_fact_choice_cas_refusal_has_no_preparation_or_business_write(link_fixture, mutation):
    f = link_fixture
    parent = setup(f, GOALS[0])
    selected = seed_facts_through_original_api(f)
    assert declare(f, parent).status_code == 200
    parent = current_parent(f, parent)
    body = confirm_body(f, parent, selected)
    if mutation == 'source_append':
        post_fact(f, 'region', 'PRIVATE_APPEND_AFTER_PREVIEW', 'stale-preview')
    elif mutation == 'source_hash':
        body['expected_source_sha256'] = '0' * 64
    elif mutation == 'preparation_revision':
        body['expected_preparation_revision'] -= 1
    elif mutation == 'assertion_revision':
        body['choices'][0]['expected_assertion_revision'] += 1
    else:
        body['choices'][0]['assertion_id'] = post_fact(f, 'region', 'PRIVATE_FOREIGN_REGION', 'foreign-source', user='fixture-b')
    before, downstream, permissions, facts = preparation_records(f), business(f), authority(f), assertions(f)
    response = confirm(f, parent, body)
    assert response.status_code == 409, response.text
    assert preparation_records(f) == before and business(f) == downstream
    assert authority(f) == permissions and assertions(f) == facts


def test_two_real_confirmation_requests_cannot_both_commit_the_same_revision(link_fixture):
    f = link_fixture
    parent = setup(f, GOALS[0])
    selected = seed_facts_through_original_api(f)
    assert declare(f, parent).status_code == 200
    parent = current_parent(f, parent)
    body = confirm_body(f, parent, selected)
    old_revision, downstream, permissions, facts = parent['revision'], business(f), authority(f), assertions(f)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda key: confirm(f, parent, body, key), [uuid4().hex, uuid4().hex]))
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert current_parent(f, parent)['revision'] == old_revision + 1
    with f[1].connect() as c:
        events = c.execute("SELECT * FROM preparation_events WHERE preparation_id=%s AND action='CONFIRM_FACT_PURPOSE'",
                           (parent['preparation_id'],)).fetchall()
    assert len(events) == 1
    assert business(f) == downstream and authority(f) == permissions and assertions(f) == facts


def test_undeclared_legacy_preparation_keeps_original_manual_lifecycle(link_fixture):
    f = link_fixture
    parent = setup(f, GOALS[4])
    seed_facts_through_original_api(f)
    permissions, facts = authority(f), assertions(f)
    _, _, receipt, closed, _ = complete_and_close(f, parent)
    assert receipt['step']['state'] == 'LOCAL_ACKNOWLEDGED'
    assert closed['local_record_state'] == 'LOCAL_RECORD_CLOSED'
    assert not closed['case_goal_completed']
    assert authority(f) == permissions and assertions(f) == facts
    with f[1].connect() as c:
        actions = c.execute('SELECT action FROM preparation_events WHERE preparation_id=%s', (parent['preparation_id'],)).fetchall()
    assert not any(row['action'] in ('DECLARE_FACT_PURPOSE', 'CONFIRM_FACT_PURPOSE') for row in actions)


def test_null_ledger_cannot_downgrade_a_native_declared_preparation_to_legacy(link_fixture):
    f = link_fixture
    parent, _, _ = declared_and_selected(f)
    parent = human_review_and_confirm(f, parent)
    assert adopt(f, parent).status_code == 201
    combination, dispatch = accepted(f, parent)
    # Deliberate isolated administrator corruption of the ledger, not a business
    # state transition. Its real native declaration event remains in PostgreSQL.
    with f[1].connect() as c:
        assert c.execute("SELECT 1 FROM preparation_events WHERE preparation_id=%s AND action='DECLARE_FACT_PURPOSE'",
                         (parent['preparation_id'],)).fetchone()
        c.execute('UPDATE preparations SET fact_clarifications=NULL WHERE id=%s', (parent['preparation_id'],))
    before, downstream, permissions, facts = preparation_records(f), business(f), authority(f), assertions(f)
    assert fact_read(f, parent).status_code == 409
    projection = assert_resource_p1_uses_current_fact_descriptor(f, parent)
    descriptor = projection['checkpoints']['P1']['current_snapshot']['fact_clarification']
    assert descriptor['enabled'] and descriptor['state'] == 'STALE' and not descriptor['satisfied']
    assert prep_command(f, parent, 'REVIEW', REVIEWER, reason='NULL must not remove the declared dependency').status_code == 409
    assert prep_command(f, parent, 'CONFIRM', reason='NULL must not inherit original review').status_code == 409
    assert plan_command(f, parent, 'P1').status_code == 409
    assert resource_link(f, parent, combination, revision=1).status_code == 409
    assert offer(f, parent, revision=dispatch['revision'], recovery_receipt_step_id=dispatch['receipt_step_id'])[0].status_code == 409
    old_receipt = receipt_read(f, dispatch['receipt_step_id'])
    assert receipt_command(f, old_receipt, 'SUBMIT').status_code == 409
    after = preparation_records(f)
    # The existing Case-step gate may persist a failed-source observation. Only
    # a verified step's invalidated flag may change from absent/false to true;
    # this must not write a command event, prep revision, source proof or receipt.
    normalized = deepcopy(after)
    for original, observed in zip(before['preparations'], normalized['preparations']):
        old_plan, new_plan = original['service_case_plan'], observed['service_case_plan']
        assert old_plan['id'] == new_plan['id']
        for old_step, new_step in zip(old_plan['steps'], new_plan['steps']):
            if old_step.get('invalidated') != new_step.get('invalidated'):
                assert old_step.get('verified_sha256') and new_step.get('invalidated') is True
                if 'invalidated' in old_step:
                    new_step['invalidated'] = old_step['invalidated']
                else:
                    new_step.pop('invalidated')
    assert normalized == before and business(f) == downstream
    assert authority(f) == permissions and assertions(f) == facts


@pytest.mark.parametrize('changed_grant', ['field_read', 'field_write', 'capability_read', 'capability_execute'])
def test_restored_grant_revision_cannot_reactivate_the_old_fact_decision(link_fixture, changed_grant):
    f = link_fixture
    parent = setup(f, GOALS[0])
    selected = seed_facts_through_original_api(f)
    assert declare(f, parent).status_code == 200
    parent = current_parent(f, parent)
    body, key = confirm_body(f, parent, selected), uuid4().hex
    response = confirm(f, parent, body, key)
    assert response.status_code == 200, response.text
    parent = human_review_and_confirm(f, current_parent(f, parent))
    original = fact_read(f, parent).json()
    old_permissions = authority(f)
    if changed_grant.startswith('field_'):
        capability = 'READ' if changed_grant == 'field_read' else 'WRITE'
        f[1].revoke_field('fixture-a', 'region', capability)
        table, where, params = 'field_grants', 'field_name=%s AND purpose=%s AND capability=%s', ('region', PURPOSE, capability)
    else:
        capability = 'READ' if changed_grant == 'capability_read' else 'EXECUTE'
        f[1].revoke_capability('fixture-a', capability)
        table, where, params = 'capability_grants', 'capability=%s', (capability,)
    assert confirm(f, parent, body, key).status_code == 403
    # Restore only the existing isolated prerequisite row, with a new revision.
    # No new authority or grant row is created by either administrator or API.
    with f[1].connect() as c:
        f[1].lock_principal(c, 'fixture-a', exclusive=True)
        c.execute('UPDATE ' + table + ' SET active=true,revision=revision+1 WHERE principal_id=%s AND ' + where,
                  ('fixture-a', *params))
    before, downstream, permissions, facts = preparation_records(f), business(f), authority(f), assertions(f)
    assert all(len(permissions[name]) == len(old_permissions[name]) for name in permissions)
    current = fact_read(f, parent)
    assert current.status_code == 200, current.text
    assert current.json()['state'] == 'STALE' and not current.json()['satisfied']
    assert current.json()['source_sha256'] != original['source_sha256']
    assert current.json()['history'] == original['history']
    replay = confirm(f, parent, body, key)
    assert replay.status_code == 200, replay.text
    assert replay.json()['recovery'] == 'HISTORICAL_COMMITTED_EVENT'
    assert not replay.json()['current_decision_restored']
    assert prep_command(f, parent, 'REVIEW', REVIEWER, reason='Restored rights require a fresh explicit selection').status_code == 409
    assert preparation_records(f) == before and business(f) == downstream
    assert authority(f) == permissions and assertions(f) == facts
