"""Case-bound slot corrections through real preparation APIs and isolated UUID PG."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from uuid import UUID, uuid4

import pytest

from parkweave import preparation as prep
from test_preparation import preparation_fixture, create, add, command, read, headers
from test_plan_preview import digest

SLOTS = ('need_summary', 'material_outline')


def checked(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def fresh(f, user='fixture-a', label='PROJECT_A'):
    p, _, _ = create(f, user=user, goal='SYNTHETIC independently entered ' + label)
    assert checked(read(f, p, user))['current_materials'] == []
    for slot in SLOTS:
        p = checked(add(f, p, slot, text='SYNTHETIC ' + label + ' original ' + slot, user=user))
    return p


def request(f, p, slots=SLOTS, user='prep-specialist-fixture-a', key=None, reason='SYNTHETIC explicit slot correction'):
    return command(f, p, 'REQUEST_CHANGES', user, key=key, reason=reason, correction_slots=list(slots))


def materials(row):
    return {item['slot']: item for item in row['current_materials']}


def authority(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text').fetchall()
                for table in ('capability_grants', 'preparation_grants', 'run_assignments')}


@pytest.mark.parametrize('action', ['REVIEW', 'CONFIRM', 'REOPEN', 'ADD_EVIDENCE'])
def test_correction_slots_only_allowed_on_request_changes(preparation_fixture, action):
    f = preparation_fixture
    p = fresh(f)
    data = dict(action=action, expected_revision=p['revision'], correction_slots=['need_summary'])
    if action == 'ADD_EVIDENCE':
        data.update(slot='need_summary', text='SYNTHETIC new source', source_kind='USER_STATEMENT', source_label='SYNTHETIC')
    else:
        data['reason'] = 'SYNTHETIC wrong command shape'
    before = digest(f)
    r = f[3].post('/api/preparations/' + p['preparation_id'] + '/commands',
                  headers=headers(f[2], key=uuid4().hex), json=data)
    assert r.status_code == 422, r.text
    assert digest(f) == before


@pytest.mark.parametrize('slots', [[], ['need_summary', 'need_summary'], ['not_a_material'], ['need_summary', 'material_outline', 'need_summary']])
def test_requested_slots_are_bounded_distinct_registered_materials(preparation_fixture, slots):
    f = preparation_fixture
    p = fresh(f)
    before = digest(f)
    assert request(f, p, slots).status_code == 422
    assert digest(f) == before


def test_legacy_generic_request_changes_preserves_existing_review_contract(preparation_fixture):
    f = preparation_fixture
    p = fresh(f)
    p = checked(command(f, p, 'REQUEST_CHANGES', 'prep-specialist-fixture-a', reason='SYNTHETIC legacy generic request'))
    p = checked(command(f, p, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC legacy current review'))
    p = checked(command(f, p, 'CONFIRM', reason='SYNTHETIC legacy confirmation'))
    assert p['state'] == 'LOCAL_CONFIRMED'
    view = checked(read(f, p))
    assert all(m['version'] == 1 for m in view['current_materials'])
    assert p['qualification'] == 'NOT_EVALUATED' and p['offline_fulfillment'] == 'NO_EVIDENCE'


@pytest.mark.parametrize('user', ['fixture-a', 'fixture-b', 'prep-specialist-fixture-b'])
def test_only_current_case_assigned_specialist_can_request_slot_correction(preparation_fixture, user):
    f = preparation_fixture
    p = fresh(f)
    before = digest(f)
    assert request(f, p, ['need_summary'], user=user).status_code == 403
    assert digest(f) == before


@pytest.mark.parametrize('cap', ['READ', 'REVIEW_ASSIGNED', 'inactive'])
def test_current_specialist_revocation_blocks_lost_reply_replay_and_review(preparation_fixture, cap):
    f = preparation_fixture
    p = fresh(f)
    key = uuid4().hex
    requested = checked(request(f, p, ['need_summary'], key=key))
    with f[1].connect() as c:
        if cap == 'inactive':
            c.execute("UPDATE principals SET active=false WHERE id='prep-specialist-fixture-a'")
        else:
            table = 'preparation_grants' if cap == 'REVIEW_ASSIGNED' else 'capability_grants'
            c.execute('UPDATE ' + table + " SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability=%s", (cap,))
    before = digest(f)
    assert request(f, p, ['need_summary'], key=key).status_code == 403
    assert command(f, requested, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC revoked review').status_code == 403
    assert digest(f) == before


@pytest.mark.parametrize('cap', ['PREPARE', 'EXECUTE'])
def test_current_owner_revocation_blocks_real_correction_submission(preparation_fixture, cap):
    f = preparation_fixture
    p = fresh(f)
    p = checked(request(f, p, ['need_summary']))
    with f[1].connect() as c:
        table = 'preparation_grants' if cap == 'PREPARE' else 'capability_grants'
        c.execute('UPDATE ' + table + " SET active=false WHERE principal_id='fixture-a' AND capability=%s", (cap,))
    before = digest(f)
    assert add(f, p, 'need_summary', text='SYNTHETIC blocked actual correction').status_code == 403
    assert digest(f) == before


def test_slot_request_same_key_lost_reply_and_changed_body_conflict(preparation_fixture):
    f = preparation_fixture
    p = fresh(f)
    key = uuid4().hex
    result = checked(request(f, p, ['need_summary'], key=key))
    before = digest(f)
    assert checked(request(f, p, ['need_summary'], key=key)) == result
    assert request(f, p, ['material_outline'], key=key).status_code == 409
    assert request(f, p, ['need_summary'], key=key, reason='SYNTHETIC changed reason').status_code == 409
    other = fresh(f, label='PROJECT_B')
    other_before = digest(f)
    assert request(f, other, ['need_summary'], key=key).status_code == 409
    assert digest(f) == other_before
    # Earlier reply is unchanged even after unrelated project creation.
    assert checked(request(f, p, ['need_summary'], key=key)) == result


def test_correction_event_failure_rolls_back_metadata_revision_and_evidence(preparation_fixture, monkeypatch):
    f = preparation_fixture
    p = fresh(f)
    before = digest(f)
    def failed_event(*args, **kwargs):
        raise RuntimeError('SYNTHETIC_CORRECTION_EVENT_FAILURE')
    monkeypatch.setattr(prep, 'event', failed_event)
    with pytest.raises(RuntimeError, match='SYNTHETIC_CORRECTION_EVENT_FAILURE'):
        request(f, p, ['need_summary'])
    assert digest(f) == before


def corrections(f, p, user='fixture-a'):
    return f[3].get('/api/preparations/' + p['preparation_id'] + '/material-corrections', headers=headers(f[2], user))


def targets(row):
    return {item['slot']: item for item in row['active_targets']}


def test_two_fresh_enterprises_correct_real_sources_without_copying_cases_or_grants(preparation_fixture):
    f = preparation_fixture
    original_authority = authority(f)
    flows = []
    for user, label in [('fixture-a', 'ENTERPRISE_A_NEW_CASE'), ('fixture-b', 'ENTERPRISE_B_NEW_CASE')]:
        specialist = 'prep-specialist-' + user
        p = fresh(f, user, label)
        before = materials(checked(read(f, p, user)))
        p = checked(request(f, p, user=specialist, reason='SYNTHETIC ' + label + ' specific corrections'))
        requested = checked(corrections(f, p, user))
        ids = {slot: item['id'] for slot, item in targets(requested).items()}
        assert requested['correction_state'] == 'CHANGES_REQUESTED'
        assert set(ids) == set(SLOTS) and len(set(ids.values())) == 2
        for slot, item in targets(requested).items():
            UUID(item['id']); UUID(item['request_id'])
            assert item['base_version'] == 1 and item['base_sha256'] == before[slot]['source_sha256']
            assert item['base_source']['evidence_id'] == before[slot]['id']
            assert item['base_source']['actor_id'] == user and item['requested_by'] == specialist
            assert item['status'] == 'REQUESTED'
        denied_before = digest(f)
        assert command(f, p, 'REVIEW', specialist, reason='SYNTHETIC unchanged old material').status_code == 409
        assert command(f, p, 'CONFIRM', user, reason='SYNTHETIC bypass correction').status_code == 409
        assert digest(f) == denied_before
        p = checked(add(f, p, SLOTS[0], text='SYNTHETIC ' + label + ' corrected summary', user=user))
        partial = checked(corrections(f, p, user))
        assert partial['correction_state'] == 'CHANGES_REQUESTED' and not partial['can_review']
        assert targets(partial)[SLOTS[0]]['status'] == 'SUBMITTED_FOR_REVIEW'
        assert targets(partial)[SLOTS[1]]['status'] == 'REQUESTED'
        assert command(f, p, 'REVIEW', specialist, reason='SYNTHETIC only one updated slot').status_code == 409
        p = checked(add(f, p, SLOTS[1], text='SYNTHETIC ' + label + ' corrected material outline', user=user))
        submitted = checked(corrections(f, p, specialist))
        assert submitted['correction_state'] == 'SUBMITTED_FOR_REVIEW' and submitted['can_review']
        assert {slot: item['id'] for slot, item in targets(submitted).items()} == ids
        assert all(item['current_version'] == 2 and item['status'] == 'SUBMITTED_FOR_REVIEW' for item in submitted['active_targets'])
        p = checked(command(f, p, 'REVIEW', specialist, reason='SYNTHETIC ' + label + ' review new current sources'))
        resolved = checked(corrections(f, p, user))
        assert resolved['correction_state'] == 'RESOLVED'
        assert len(resolved['items']) == 2
        assert all(item['status'] == 'RESOLVED' and item['resolution']['reviewer_id'] == specialist and item['current_review_valid'] for item in resolved['items'])
        p = checked(command(f, p, 'CONFIRM', user, reason='SYNTHETIC ' + label + ' owner confirms'))
        final = checked(read(f, p, user))
        assert final['preparation']['state'] == 'LOCAL_CONFIRMED'
        assert [m['version'] for m in final['material_history']] == [1, 2, 1, 2]
        assert all(label in m['text'] and m['source_sha256'] == sha256(m['text'].encode()).hexdigest() for m in final['material_history'])
        assert final['qualification'] == 'NOT_EVALUATED' and final['offline_fulfillment'] == 'NO_EVIDENCE'
        flows.append((p, final, resolved))
    assert flows[0][0]['case_id'] != flows[1][0]['case_id'] and flows[0][0]['run_id'] != flows[1][0]['run_id']
    assert not {m['id'] for m in flows[0][1]['current_materials']} & {m['id'] for m in flows[1][1]['current_materials']}
    assert not {t['id'] for t in flows[0][2]['items']} & {t['id'] for t in flows[1][2]['items']}
    assert authority(f) == original_authority
    before = digest(f)
    assert corrections(f, flows[0][0], 'fixture-b').status_code == 403
    assert corrections(f, flows[1][0], 'prep-specialist-fixture-a').status_code == 403
    assert digest(f) == before


def test_two_projects_same_owner_keep_independent_corrections_and_current_sources(preparation_fixture):
    f = preparation_fixture
    first = fresh(f, label='OWNER_PROJECT_FIRST')
    second = fresh(f, label='OWNER_PROJECT_SECOND')
    second_before = checked(read(f, second))
    first = checked(request(f, first, ['need_summary']))
    first = checked(add(f, first, 'need_summary', text='SYNTHETIC OWNER_PROJECT_FIRST real correction'))
    assert checked(corrections(f, first))['correction_state'] == 'SUBMITTED_FOR_REVIEW'
    assert checked(corrections(f, second))['correction_state'] == 'NOT_REQUESTED'
    assert checked(read(f, second)) == second_before
    second = checked(request(f, second, ['material_outline']))
    a, b = checked(corrections(f, first)), checked(corrections(f, second))
    assert a['case_id'] != b['case_id']
    assert set(targets(a)) == {'need_summary'} and set(targets(b)) == {'material_outline'}
    assert not {item['id'] for item in a['items']} & {item['id'] for item in b['items']}
    assert command(f, second, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC other project correction insufficient').status_code == 409


def test_rerequest_same_slot_supersedes_it_without_losing_other_active_slot(preparation_fixture):
    f = preparation_fixture
    p = fresh(f)
    p = checked(request(f, p))
    original = checked(corrections(f, p))
    original_targets = targets(original)
    p = checked(add(f, p, 'need_summary', text='SYNTHETIC first correction submission'))
    p = checked(request(f, p, ['need_summary'], reason='SYNTHETIC reviewer requires another summary revision'))
    current = checked(corrections(f, p))
    assert len(current['history']) == 2 and len(current['items']) == 3
    assert targets(current)['material_outline']['id'] == original_targets['material_outline']['id']
    assert targets(current)['material_outline']['status'] == 'REQUESTED'
    replacement = targets(current)['need_summary']
    assert replacement['id'] != original_targets['need_summary']['id'] and replacement['base_version'] == 2
    old = next(item for item in current['items'] if item['id'] == original_targets['need_summary']['id'])
    assert old['status'] == 'SUPERSEDED' and old['superseded_by'] == replacement['id']
    assert old['base_source'] == original_targets['need_summary']['base_source']
    assert old['reason'] == original_targets['need_summary']['reason']
    assert command(f, p, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC replacement still unchanged').status_code == 409
    p = checked(add(f, p, 'material_outline', text='SYNTHETIC outline first actual correction'))
    assert command(f, p, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC summary still needs third version').status_code == 409
    p = checked(add(f, p, 'need_summary', text='SYNTHETIC summary third version'))
    p = checked(command(f, p, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC both latest corrections reviewed'))
    resolved = checked(corrections(f, p))
    assert len([item for item in resolved['items'] if item['status'] == 'RESOLVED']) == 2
    assert next(item for item in resolved['items'] if item['id'] == old['id'])['status'] == 'SUPERSEDED'


def test_concurrent_submission_versions_and_same_key_request_commit_once(preparation_fixture):
    f = preparation_fixture
    p = fresh(f)
    key = uuid4().hex
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda _: request(f, p, ['need_summary'], key=key), range(2)))
    assert [r.status_code for r in replies] == [200, 200]
    assert replies[0].json() == replies[1].json()
    p = replies[0].json()
    assert len(checked(corrections(f, p))['items']) == 1
    with ThreadPoolExecutor(2) as pool:
        replies = list(pool.map(lambda n: add(f, p, 'need_summary', text='SYNTHETIC concurrent actual version ' + str(n)), range(2)))
    assert sorted(r.status_code for r in replies) == [200, 409]
    current = checked(read(f, p))
    assert materials(current)['need_summary']['version'] == 2
    assert len([m for m in current['material_history'] if m['slot'] == 'need_summary']) == 2
    correction = targets(checked(corrections(f, p)))['need_summary']
    assert correction['status'] == 'SUBMITTED_FOR_REVIEW'
    assert len(correction['submissions']) == 1


def test_real_submission_event_failure_rolls_back_evidence_and_correction_status(preparation_fixture, monkeypatch):
    f = preparation_fixture
    p = fresh(f)
    p = checked(request(f, p, ['need_summary']))
    before = digest(f)
    def failed_event(*args, **kwargs):
        raise RuntimeError('SYNTHETIC_SUBMISSION_EVENT_FAILURE')
    monkeypatch.setattr(prep, 'event', failed_event)
    with pytest.raises(RuntimeError, match='SYNTHETIC_SUBMISSION_EVENT_FAILURE'):
        add(f, p, 'need_summary', text='SYNTHETIC actual correction must roll back')
    assert digest(f) == before


def test_legacy_request_fingerprint_and_lost_reply_survive_additive_migration(preparation_fixture):
    import json
    f = preparation_fixture
    p = fresh(f)
    key = uuid4().hex
    reason = 'SYNTHETIC legacy request before correction selection'
    result = checked(command(f, p, 'REQUEST_CHANGES', 'prep-specialist-fixture-a', key=key, reason=reason))
    old_body = dict(preparation_id=p['preparation_id'], action='REQUEST_CHANGES', expected_revision=p['revision'],
                    slot=None, text=None, source_kind=None, source_label=None, reason=reason)
    expected = sha256(json.dumps(old_body, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    with f[1].connect() as c:
        stored = c.execute('SELECT fingerprint,payload FROM preparation_events WHERE actor_id=%s AND request_key=%s', ('prep-specialist-fixture-a', key)).fetchone()
        assert stored['fingerprint'] == expected and stored['payload'] == result
    before = digest(f)
    f[1].migrate()
    f[1].migrate()
    assert checked(command(f, p, 'REQUEST_CHANGES', 'prep-specialist-fixture-a', key=key, reason=reason)) == result
    assert digest(f) == before


@pytest.mark.parametrize('tamper', ['fabricated_version', 'wrong_actor', 'changed_text'])
def test_review_requires_actual_owner_add_evidence_source_and_hash(preparation_fixture, tamper):
    f = preparation_fixture
    p = fresh(f)
    p = checked(request(f, p, ['need_summary']))
    if tamper != 'fabricated_version':
        p = checked(add(f, p, 'need_summary', text='SYNTHETIC real owner correction before tamper'))
    with f[1].connect() as c:
        evidence = c.execute("SELECT id FROM preparation_evidence WHERE preparation_id=%s AND slot='need_summary' ORDER BY version DESC LIMIT 1", (p['preparation_id'],)).fetchone()
        if tamper == 'fabricated_version':
            c.execute('UPDATE preparation_evidence SET version=version+1 WHERE id=%s', (evidence['id'],))
        elif tamper == 'wrong_actor':
            c.execute("UPDATE preparation_evidence SET actor_id='prep-specialist-fixture-a' WHERE id=%s", (evidence['id'],))
        else:
            c.execute("UPDATE preparation_evidence SET text='SYNTHETIC changed without original hash' WHERE id=%s", (evidence['id'],))
    before = digest(f)
    assert command(f, p, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC tampered source cannot resolve').status_code == 409
    view = checked(corrections(f, p))
    assert targets(view)['need_summary']['status'] == 'REQUESTED'
    assert targets(view)['need_summary']['resolution'] is None
    assert digest(f) == before


def test_new_material_preserves_old_resolution_but_cannot_claim_current_review(preparation_fixture):
    f = preparation_fixture
    p = fresh(f)
    p = checked(request(f, p, ['need_summary']))
    p = checked(add(f, p, 'need_summary', text='SYNTHETIC actual correction version two'))
    p = checked(command(f, p, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC review corrected current sources'))
    original = checked(corrections(f, p))
    target = original['items'][0]
    assert target['status'] == 'RESOLVED' and target['current_review_valid']
    p = checked(command(f, p, 'CONFIRM', reason='SYNTHETIC confirm corrected current sources'))
    p = checked(add(f, p, 'need_summary', text='SYNTHETIC new actual version three after resolution'))
    current = checked(corrections(f, p))
    stale = current['items'][0]
    assert stale['id'] == target['id'] and stale['status'] == 'STALE_RESOLUTION'
    assert stale['resolution'] == target['resolution'] and stale['resolved_source'] == target['resolved_source']
    assert not stale['current_review_valid'] and not current['current_review_valid']
    assert stale['current_version'] == 3
    assert stale['source_status'] == 'HISTORICAL_SOURCE_CHANGED'
    assert current['correction_state'] == 'STALE_RESOLUTION'
    assert command(f, p, 'CONFIRM', reason='SYNTHETIC old resolved history cannot approve new source').status_code == 409


@pytest.mark.parametrize('change', ['reopen', 'other_material'])
def test_unchanged_target_source_with_changed_review_preserves_resolution_and_reports_review_staleness(preparation_fixture, change):
    f = preparation_fixture
    p = fresh(f)
    p = checked(request(f, p, ['need_summary']))
    p = checked(add(f, p, 'need_summary', text='SYNTHETIC actual corrected target version two'))
    p = checked(command(f, p, 'REVIEW', 'prep-specialist-fixture-a', reason='SYNTHETIC review actual corrected target'))
    p = checked(command(f, p, 'CONFIRM', reason='SYNTHETIC confirmation of reviewed target'))
    original = checked(corrections(f, p))
    target = original['items'][0]
    evidence_before = materials(checked(read(f, p)))['need_summary']
    if change == 'reopen':
        p = checked(command(f, p, 'REOPEN', reason='SYNTHETIC explicit current review reopening'))
    else:
        p = checked(add(f, p, 'material_outline', text='SYNTHETIC independent outline revision invalidates package review'))
    current = checked(corrections(f, p))
    stale = current['items'][0]
    assert materials(checked(read(f, p)))['need_summary'] == evidence_before
    assert stale['id'] == target['id'] and stale['resolved_source'] == target['resolved_source']
    assert stale['resolution'] == target['resolution']
    assert stale['status'] == 'STALE_RESOLUTION' and stale['source_status'] == 'HISTORICAL_REVIEW_CHANGED'
    assert current['correction_state'] == 'STALE_RESOLUTION'
    assert not stale['current_review_valid'] and not current['current_review_valid']
    before = digest(f)
    assert command(f, p, 'CONFIRM', reason='SYNTHETIC historical resolution cannot bypass changed review').status_code == 409
    assert digest(f) == before


@pytest.mark.parametrize('submitted', [False, True])
def test_forged_reviewed_state_and_current_hash_cannot_confirm_unresolved_correction(preparation_fixture, submitted):
    f = preparation_fixture
    p = fresh(f)
    p = checked(request(f, p, ['need_summary']))
    if submitted:
        p = checked(add(f, p, 'need_summary', text='SYNTHETIC actual submitted source remains unresolved'))
    actual = checked(read(f, p))
    original = checked(corrections(f, p))
    assert original['items'][0]['resolution'] is None
    with f[1].connect() as c:
        c.execute("UPDATE preparations SET state='REVIEWED',review_sha256=%s WHERE id=%s", (actual['snapshot_sha256'], p['preparation_id']))
    before = digest(f)
    r = command(f, p, 'CONFIRM', reason='SYNTHETIC fabricated state and hash must not resolve correction')
    assert r.status_code == 409, r.text
    assert digest(f) == before
    current = checked(corrections(f, p))
    assert current['items'][0]['resolution'] is None
    assert current['items'][0]['status'] == ('SUBMITTED_FOR_REVIEW' if submitted else 'REQUESTED')
