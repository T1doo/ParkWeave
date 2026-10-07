"""Material reuse creates independent, unverified evidence in isolated real PG."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4
import secrets

import psycopg
import pytest
from psycopg.types.json import Jsonb
from parkweave.store import digest

from test_preparation import preparation_fixture, create, add, command, read, headers


def confirmed_source(f, user='fixture-a'):
    row, _, _ = create(f, user=user, goal='Synthetic source Case with independently supplied materials')
    for slot, text in (('need_summary', 'Source request belongs only to its original Case'),
                       ('material_outline', 'Synthetic reusable documentary material outline')):
        response = command(f, row, 'ADD_EVIDENCE', user=user, slot=slot, text=text,
            source_kind='DOCUMENT_EXCERPT', source_label='Explicit source document ' + slot)
        assert response.status_code == 200, response.text
        row = response.json()
    response = command(f, row, 'REVIEW', user='prep-specialist-' + user, reason='Original source human material review')
    assert response.status_code == 200, response.text
    response = command(f, response.json(), 'CONFIRM', user=user, reason='Original source owner confirmation')
    assert response.status_code == 200, response.text
    return response.json()


def target(f, user='fixture-a'):
    return create(f, user=user, goal='Fresh Case with its own explicit current request')[0]


def business(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text').fetchall()
                for table in ('preparations', 'preparation_evidence', 'preparation_events', 'runs', 'cases',
                              'service_receipt_steps', 'service_dispatches', 'controlled_plans', 'controlled_plan_events')}


def authority(f):
    with f[1].connect() as c:
        return {table: c.execute('SELECT * FROM ' + table + ' ORDER BY to_jsonb(' + table + ')::text').fetchall()
                for table in ('principals', 'field_grants', 'capability_grants', 'action_grants',
                              'preparation_grants', 'run_assignments', 'synthetic_resource_grants')}


def test_original_add_evidence_does_not_accept_source_reuse_authority(preparation_fixture):
    """Baseline real command rejects an unregistered source-copy contract atomically."""
    f = preparation_fixture
    source = confirmed_source(f)
    fresh = target(f)
    outline = next(item for item in read(f, source).json()['current_materials'] if item['slot'] == 'material_outline')
    before = business(f)
    permissions = authority(f)
    response = command(f, fresh, 'ADD_EVIDENCE', slot='material_outline', text=outline['text'],
        source_kind=outline['source_kind'], source_label=outline['source_label'],
        source_preparation_id=source['preparation_id'], source_evidence_id=outline['id'],
        expected_source_sha256=outline['source_sha256'])
    assert response.status_code == 422, response.text
    assert business(f) == before and authority(f) == permissions
    assert read(f, fresh).json()['current_materials'] == []


def reuse_body(f, source, fresh):
    view = read(f, source).json()
    material = next(item for item in view['current_materials'] if item['slot'] == 'material_outline')
    return dict(expected_target_revision=fresh['revision'], source_preparation_id=source['preparation_id'],
        expected_source_preparation_revision=view['preparation']['revision'], source_evidence_id=material['id'],
        expected_source_evidence_version=material['version'], expected_source_evidence_sha256=material['source_sha256'],
        expected_source_snapshot_sha256=view['snapshot_sha256'], purpose='SAME_SERVICE_MATERIAL_OUTLINE',
        reason='Explicit reuse of own same-service documentary material into a new Case')


def reuse(f, fresh, body, key=None, user='fixture-a'):
    return f[3].post('/api/preparations/' + fresh['preparation_id'] + '/material-reuse',
                     headers=headers(f[2], user, key or uuid4().hex), json=body)


def source_change(f, source):
    response = command(f, source, 'REOPEN', reason='Source Case receives independently updated material')
    assert response.status_code == 200, response.text
    response = add(f, response.json(), 'material_outline', 'New documentary outline belongs only to source Case')
    assert response.status_code == 200, response.text
    return response.json()


def test_reuse_is_new_unverified_evidence_and_target_needs_own_request_and_human_review(preparation_fixture):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    original_source = deepcopy(read(f, source).json())
    permissions = authority(f)
    body = reuse_body(f, source, fresh)
    response = reuse(f, fresh, body)
    assert response.status_code == 201, response.text
    copied = response.json()
    assert copied['action'] == 'ADD_EVIDENCE' and copied['state'] == 'IN_PREPARATION'
    provenance = copied['material_reuse']
    assert provenance['requires_independent_review'] and provenance['purpose'] == body['purpose']
    view = read(f, copied).json()
    assert view['preparation']['review_sha256'] is None
    assert view['preparation']['goal'] == 'Fresh Case with its own explicit current request'
    assert len(view['current_materials']) == 1
    evidence = view['current_materials'][0]
    assert evidence['slot'] == 'material_outline' and evidence['version'] == 1
    assert evidence['id'] != body['source_evidence_id']
    assert evidence['authenticity'] == 'UNVERIFIED'
    assert evidence['source_sha256'] == body['expected_source_evidence_sha256']
    assert provenance['target_evidence_id'] == evidence['id']
    assert provenance['source_evidence_id'] == body['source_evidence_id']
    assert command(f, copied, 'REVIEW', user='prep-specialist-fixture-a', reason='Missing new request').status_code == 409
    assert command(f, copied, 'CONFIRM', reason='Cannot inherit source review').status_code == 409
    response = add(f, copied, 'need_summary', 'A new request independently supplied for this Case')
    assert response.status_code == 200, response.text
    response = command(f, response.json(), 'REVIEW', user='prep-specialist-fixture-a', reason='Actual target human material review')
    assert response.status_code == 200, response.text
    response = command(f, response.json(), 'CONFIRM', reason='Actual target owner confirms this snapshot')
    assert response.status_code == 200, response.text
    assert response.json()['state'] == 'LOCAL_CONFIRMED'
    assert response.json()['qualification'] == 'NOT_EVALUATED'
    assert read(f, source).json() == original_source
    assert authority(f) == permissions
    with f[1].connect() as c:
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 24
        assert c.execute('SELECT count(*) n FROM runs').fetchone()['n'] == 2


@pytest.mark.parametrize('user', ['fixture-b', 'fixture-c', 'prep-specialist-fixture-a'])
def test_other_owner_tenant_and_reviewer_cannot_copy_or_read_target_candidates(preparation_fixture, user):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    before, permissions = business(f), authority(f)
    assert reuse(f, fresh, body, user=user).status_code == 403
    response = f[3].get('/api/preparations/' + fresh['preparation_id'] + '/material-reuse', headers=headers(f[2], user))
    assert response.status_code == 403
    assert business(f) == before and authority(f) == permissions


@pytest.mark.parametrize('source_owner', ['fixture-b', 'reuse-peer-owner'])
def test_source_owned_by_another_enterprise_is_not_a_copy_candidate(preparation_fixture, source_owner):
    f = preparation_fixture
    if source_owner == 'reuse-peer-owner':
        # Explicit prerequisites only in this already-created UUID fixture DB.
        reviewer = 'prep-specialist-' + source_owner
        for actor in (source_owner, reviewer): f[2][actor] = secrets.token_urlsafe(32)
        with f[1].connect() as c:
            for actor, role in ((source_owner, 'enterprise_operator'), (reviewer, 'park_specialist')):
                c.execute("INSERT INTO principals VALUES(%s,%s,'park-a','org-a',%s,true)", (actor, digest(f[2][actor]), role))
            for actor, capability in ((source_owner, 'READ'), (source_owner, 'EXECUTE'), (reviewer, 'READ')):
                c.execute("INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,'park-a','org-a')", (actor, capability))
            c.execute("INSERT INTO action_grants(principal_id,action,park_id,org_id) VALUES(%s,'case.create','park-a','org-a')", (source_owner,))
            f[1].seed_field_grants(c, source_owner, 'park-a', 'org-a')
            for actor, capability in ((source_owner, 'PREPARE'), (reviewer, 'REVIEW_ASSIGNED')):
                c.execute("INSERT INTO preparation_grants(principal_id,park_id,org_id,capability) VALUES(%s,'park-a','org-a',%s)", (actor, capability))
    source, fresh = confirmed_source(f, source_owner), target(f)
    source_view = read(f, source, source_owner).json()
    material = next(x for x in source_view['current_materials'] if x['slot'] == 'material_outline')
    body = dict(expected_target_revision=fresh['revision'], source_preparation_id=source['preparation_id'],
        expected_source_preparation_revision=source['revision'], source_evidence_id=material['id'],
        expected_source_evidence_version=material['version'], expected_source_evidence_sha256=material['source_sha256'],
        expected_source_snapshot_sha256=source_view['snapshot_sha256'], purpose='SAME_SERVICE_MATERIAL_OUTLINE', reason='Forbidden foreign source')
    before, permissions = business(f), authority(f)
    assert reuse(f, fresh, body).status_code == 403
    response = f[3].get('/api/preparations/' + fresh['preparation_id'] + '/material-reuse', headers=headers(f[2]))
    assert response.status_code == 200
    assert source['preparation_id'] not in response.text and material['text'] not in response.text
    assert business(f) == before and authority(f) == permissions


def test_source_request_summary_cannot_be_copied_as_documentary_outline(preparation_fixture):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    item = next(x for x in read(f, source).json()['current_materials'] if x['slot'] == 'need_summary')
    body.update(source_evidence_id=item['id'], expected_source_evidence_version=item['version'],
                expected_source_evidence_sha256=item['source_sha256'])
    before = business(f)
    assert reuse(f, fresh, body).status_code == 409
    assert business(f) == before


@pytest.mark.parametrize('field', ['expected_target_revision', 'expected_source_preparation_revision',
    'expected_source_evidence_version', 'expected_source_evidence_sha256', 'expected_source_snapshot_sha256'])
def test_exact_revisions_and_actual_material_hashes_are_required(preparation_fixture, field):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    body[field] = '0' * 64 if field.endswith('sha256') else body[field] + 1
    before = business(f)
    assert reuse(f, fresh, body).status_code == 409
    assert business(f) == before


@pytest.mark.parametrize('mutation', [{'purpose': 'CASE_ACCEPTANCE'}, {'slot': 'need_summary'}])
def test_purpose_and_slot_cannot_expand_the_reuse_contract(preparation_fixture, mutation):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = {**reuse_body(f, source, fresh), **mutation}
    before = business(f)
    assert reuse(f, fresh, body).status_code == 422
    assert business(f) == before


@pytest.mark.parametrize('change', ['reopened', 'actual_text', 'different_service_version'])
def test_source_must_be_fresh_confirmed_and_same_service_version(preparation_fixture, change):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    if change == 'reopened':
        assert command(f, source, 'REOPEN', reason='Source is no longer confirmed').status_code == 200
    else:
        with f[1].connect() as c:
            if change == 'actual_text': c.execute('UPDATE preparation_evidence SET text=%s WHERE id=%s', ('Unreviewed source content drift', body['source_evidence_id']))
            else:
                c.execute("INSERT INTO preparation_catalog VALUES('park-a','synthetic-material-preparation',2,%s,%s,'SYNTHETIC','NOT_EVALUATED')",
                          ('Explicit isolated second service version', Jsonb({'kind': 'SYNTHETIC', 'id': 'ENG100-second-service-version',
                            'revision': '2', 'statement': 'A distinct test service version with explicit prerequisites.'})))
                c.execute('UPDATE preparations SET service_version=2 WHERE id=%s', (source['preparation_id'],))
        if change == 'different_service_version':
            # Establish a genuinely current version-2 review so a mismatch
            # cannot be rejected merely because its review hash became stale.
            source = command(f, source, 'REOPEN', reason='Explicit isolated service-version review').json()
            source = command(f, source, 'REVIEW', user='prep-specialist-fixture-a', reason='Human review of version-2 source').json()
            source = command(f, source, 'CONFIRM', reason='Confirm version-2 source materials').json()
            body = reuse_body(f, source, fresh)
    before = business(f)
    assert reuse(f, fresh, body).status_code == 409
    assert business(f) == before


def test_target_with_existing_material_is_not_silently_overwritten(preparation_fixture):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    response = add(f, fresh, 'need_summary', 'Existing target request supplied before attempting copy')
    assert response.status_code == 200
    fresh = response.json()
    body['expected_target_revision'] = fresh['revision']
    before = business(f)
    assert reuse(f, fresh, body).status_code == 409
    assert business(f) == before


@pytest.mark.parametrize('capability', ['READ', 'EXECUTE', 'PREPARE', 'case.create'])
def test_current_authority_precedes_lost_reply_key_replay(preparation_fixture, capability):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    assert reuse(f, fresh, body, key='committed-copy').status_code == 201
    with f[1].connect() as c:
        table = 'preparation_grants' if capability == 'PREPARE' else 'action_grants' if capability == 'case.create' else 'capability_grants'
        field = 'action' if capability == 'case.create' else 'capability'
        c.execute('UPDATE ' + table + ' SET active=false WHERE principal_id=%s AND ' + field + '=%s', ('fixture-a', capability))
    before, permissions = business(f), authority(f)
    assert reuse(f, fresh, body, key='committed-copy').status_code == 403
    assert business(f) == before and authority(f) == permissions


def test_source_change_after_copy_preserves_frozen_target_and_history_only_replay(preparation_fixture):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    response = reuse(f, fresh, body, key='frozen-copy')
    assert response.status_code == 201, response.text
    copied = response.json()
    frozen = deepcopy(read(f, copied).json())
    path = '/api/preparations/' + copied['preparation_id'] + '/material-reuse'
    history = f[3].get(path, headers=headers(f[2])).json()['history']
    assert history[0]['source_status'] == 'CURRENT_SOURCE_SNAPSHOT'
    assert history[0]['material_reuse'] == copied['material_reuse']
    source_change(f, source)
    before = business(f)
    response = reuse(f, fresh, body, key='frozen-copy')
    assert response.status_code == 201 and response.json() == copied
    assert read(f, copied).json() == frozen
    history = f[3].get(path, headers=headers(f[2])).json()['history']
    assert history[0]['source_status'] == 'HISTORICAL_SOURCE_CHANGED'
    assert history[0]['material_reuse'] == copied['material_reuse']
    assert business(f) == before
    assert reuse(f, fresh, body, key='new-key-stale-source').status_code == 409
    assert business(f) == before
    # The copied target can receive its own request and its own independent review.
    copied = add(f, copied, 'need_summary', 'New target request unaffected by changed source Case').json()
    copied = command(f, copied, 'REVIEW', user='prep-specialist-fixture-a', reason='Review frozen copied target materials').json()
    copied = command(f, copied, 'CONFIRM', reason='Confirm independent target snapshot').json()
    assert copied['state'] == 'LOCAL_CONFIRMED'


def test_lost_committed_copy_reply_uses_exact_key_and_body_without_extra_evidence(preparation_fixture, monkeypatch):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    original = f[3].post
    committed = []
    def lost_reply(*args, **kwargs):
        response = original(*args, **kwargs)
        assert response.status_code == 201, response.text
        committed.append(response.json())
        raise RuntimeError('Injected response loss after real copy transaction committed')
    monkeypatch.setattr(f[3], 'post', lost_reply)
    with pytest.raises(RuntimeError): reuse(f, fresh, body, key='lost-copy')
    monkeypatch.setattr(f[3], 'post', original)
    before = business(f)
    response = reuse(f, fresh, body, key='lost-copy')
    assert response.status_code == 201 and response.json() == committed[0]
    assert business(f) == before
    assert reuse(f, fresh, {**body, 'reason': 'Changed original copy request'}, key='lost-copy').status_code == 409
    assert business(f) == before


@pytest.mark.parametrize('same_key', [False, True])
def test_concurrent_copy_has_one_evidence_and_one_event_or_exact_replays(preparation_fixture, same_key):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    def send(index): return reuse(f, fresh, body, key='same-copy-key' if same_key else 'copy-' + str(index))
    with ThreadPoolExecutor(2) as pool: results = list(pool.map(send, range(2)))
    assert sorted(r.status_code for r in results) == ([201, 201] if same_key else [201, 409])
    if same_key: assert results[0].json() == results[1].json()
    view = read(f, fresh).json()
    assert len(view['current_materials']) == 1 and view['current_materials'][0]['version'] == 1
    assert len([e for e in view['history'] if e['action'] == 'ADD_EVIDENCE']) == 1


def test_actual_source_update_and_copy_serialize_without_torn_material_snapshot(preparation_fixture):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    permissions = authority(f)
    def update_source(): return command(f, source, 'REOPEN', reason='Actual source writer racing copy')
    with ThreadPoolExecutor(2) as pool:
        change = pool.submit(update_source)
        copy = pool.submit(reuse, f, fresh, body, 'source-race-copy')
        changed, copied = change.result(), copy.result()
    assert changed.status_code == 200
    assert copied.status_code in (201, 409), copied.text
    view = read(f, fresh).json()
    if copied.status_code == 201:
        assert len(view['current_materials']) == 1
        assert view['current_materials'][0]['source_sha256'] == body['expected_source_evidence_sha256']
        assert copied.json()['material_reuse']['source_evidence_id'] == body['source_evidence_id']
    else:
        assert view['current_materials'] == []
        assert not any(e['action'] == 'ADD_EVIDENCE' for e in view['history'])
    assert authority(f) == permissions


@pytest.mark.parametrize('boundary', ['event', 'invalidation'])
def test_copy_failure_rolls_back_evidence_revision_event_and_provenance(preparation_fixture, monkeypatch, boundary):
    from parkweave import controlled_plans
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    before, permissions = business(f), authority(f)
    if boundary == 'event':
        with f[1].connect() as c:
            c.execute("CREATE FUNCTION fixture_copy_fault() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'isolated copy rollback fault'; END $$")
            c.execute('CREATE TRIGGER fixture_copy_fault BEFORE INSERT ON preparation_events FOR EACH ROW EXECUTE FUNCTION fixture_copy_fault()')
        error = psycopg.errors.RaiseException
    else:
        def fail_invalidation(*args, **kwargs): raise RuntimeError('Injected required checkpoint invalidation failure')
        monkeypatch.setattr(controlled_plans, 'invalidate', fail_invalidation)
        error = RuntimeError
    with pytest.raises(error): reuse(f, fresh, body)
    assert business(f) == before and authority(f) == permissions


def test_get_candidate_metadata_preview_and_history_are_read_only(preparation_fixture):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    before, permissions = business(f), authority(f)
    with f[1].connect() as c: audit = c.execute('SELECT * FROM authorization_audit ORDER BY id').fetchall()
    path = '/api/preparations/' + fresh['preparation_id'] + '/material-reuse'
    response = f[3].get(path, headers=headers(f[2]))
    assert response.status_code == 200, response.text
    assert response.json()['can_reuse'] and len(response.json()['items']) == 1
    assert response.json()['items'][0]['source_goal'] == 'Synthetic source Case with independently supplied materials'
    assert 'Synthetic reusable documentary material outline' not in response.text
    response = f[3].get(path, params={'source_evidence_id': body['source_evidence_id']}, headers=headers(f[2]))
    assert response.status_code == 200, response.text
    assert response.json()['source_preview']['text'] == 'Synthetic reusable documentary material outline'
    assert business(f) == before and authority(f) == permissions
    with f[1].connect() as c: assert c.execute('SELECT * FROM authorization_audit ORDER BY id').fetchall() == audit


def test_source_scope_loss_redacts_history_and_blocks_old_key_without_rewriting_copied_evidence(preparation_fixture):
    f = preparation_fixture
    source, fresh = confirmed_source(f), target(f)
    body = reuse_body(f, source, fresh)
    response = reuse(f, fresh, body, key='source-scope-loss')
    assert response.status_code == 201, response.text
    copied = response.json()
    frozen = deepcopy(read(f, copied).json())
    with f[1].connect() as c:
        c.execute('UPDATE preparations SET owner_id=%s WHERE id=%s', ('fixture-b', source['preparation_id']))
    before = business(f)
    response = f[3].get('/api/preparations/' + fresh['preparation_id'] + '/material-reuse', headers=headers(f[2]))
    assert response.status_code == 200, response.text
    history = response.json()['history'][0]
    assert history['source_status'] == 'SOURCE_UNAVAILABLE'
    assert history['material_reuse']['target_evidence_id'] == copied['material_reuse']['target_evidence_id']
    assert not any(key.startswith('source_') for key in history['material_reuse'])
    assert source['preparation_id'] not in response.text
    assert body['source_evidence_id'] not in response.text
    assert reuse(f, fresh, body, key='source-scope-loss').status_code == 403
    assert read(f, copied).json() == frozen
    assert business(f) == before
