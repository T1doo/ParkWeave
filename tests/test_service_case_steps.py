"""Registered Case steps exercised against isolated UUID PostgreSQL and real APIs."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import UUID, uuid4

import pytest

from parkweave import bounded_planning as bp
from test_preparation import preparation_fixture, headers, command as preparation_act
from test_executor_receipts import receipt_fixture, ready, act as receipt_act
from test_case_resources import link_fixture, group, post as resource_link
from test_service_dispatches import offer, command as dispatch_act, REVIEWER
from test_request_intents import save
from test_plan_preview import digest
from test_case_lifecycle import read as lifecycle_read, act as lifecycle_act

GOALS = [
    'LOCAL_MATERIAL_PREPARATION',
    'LOCAL_CASE_RESOURCE_ASSOCIATION',
    'LOCAL_INTERNAL_ACCEPTANCE',
    'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT',
    'LOCAL_CASE_RECORD_RECHECK',
]


def read(f, p, user='fixture-a'):
    return f[3].get('/api/preparations/' + p['preparation_id'] + '/service-case-plan', headers=headers(f[2], user))


def setup(f, goal=GOALS[3]):
    p = ready(f)
    r = save(f, p, goals=[goal], text='SYNTHETIC PRIVATE_CASE_STEP_REQUEST')
    assert r.status_code == 200, r.text
    p = {**p, 'revision': r.json()['revision']}
    p = preparation_act(f, p, 'REVIEW', REVIEWER, reason='SYNTHETIC current goal review').json()
    p = preparation_act(f, p, 'CONFIRM', reason='SYNTHETIC explicit current goal confirmation').json()
    return p


def adopt_body(f, p, **extra):
    preview = f[3].get('/api/preparations/' + p['preparation_id'] + '/planning-preview', headers=headers(f[2])).json()['current']
    with f[1].connect() as c:
        intent = c.execute('SELECT request_intent FROM preparations WHERE id=%s', (p['preparation_id'],)).fetchone()['request_intent']
    return dict(expected_preparation_revision=p['revision'], expected_request_revision=intent['revision'] if intent else 0,
                expected_source_sha256=preview['source_sha256'], expected_plan_revision=0,
                required_goals=preview['required_goals'], reason='SYNTHETIC explicit plan adoption', **extra)


def adopt(f, p, body=None, key=None, user='fixture-a'):
    return f[3].post('/api/preparations/' + p['preparation_id'] + '/service-case-plan',
                     headers=headers(f[2], user, key or uuid4().hex), json=body or adopt_body(f, p))


def step(row, adapter):
    return next(s for s in row['steps'] if s['adapter_id'] == adapter)


def command(f, p, adapter, action='VERIFY', row=None, user='fixture-a', key=None, **extra):
    row = row or read(f, p).json()
    s = step(row, adapter)
    data = dict(action=action, step_id=s['id'], expected_revision=row['revision'],
                expected_source_sha256=s['source_sha256'] if action == 'VERIFY' else None,
                reason='SYNTHETIC explicit ' + action)
    data.update(extra)
    return f[3].post('/api/preparations/' + p['preparation_id'] + '/service-case-plan/commands',
                     headers=headers(f[2], user, key or uuid4().hex), json=data)


def verified(f, p, adapter):
    r = command(f, p, adapter)
    assert r.status_code == 200, r.text
    assert step(r.json(), adapter)['state'] == 'VERIFIED'
    return r.json()


def business(f):
    """Coordination changes must not execute or repair any underlying business record."""
    with f[1].connect() as c:
        return {t: c.execute('SELECT * FROM ' + t + ' ORDER BY to_jsonb(' + t + ')::text').fetchall() for t in
                ('run_assignments', 'capability_grants', 'preparation_grants', 'case_resource_links',
                 'service_dispatches', 'service_dispatch_offers', 'service_receipt_steps',
                 'service_step_receipts', 'case_local_lifecycles')}


def accepted(f, p):
    verified(f, p, 'P1')
    g = group(f)
    r = resource_link(f, p, g)
    assert r.status_code == 201, r.text
    verified(f, p, 'P2')
    r = offer(f, p)[0]
    assert r.status_code == 201, r.text
    r = dispatch_act(f, r.json(), 'ACCEPT')
    assert r.status_code == 200, r.text
    return g, r.json()


@pytest.mark.parametrize('goal,n', list(zip(GOALS, range(1, 6))))
def test_adopt_real_bounded_goal_subgraph_with_stable_case_step_ids(link_fixture, goal, n):
    f = link_fixture
    p = setup(f, goal)
    before = business(f)
    body = adopt_body(f, p)
    key = uuid4().hex
    r = adopt(f, p, body, key)
    assert r.status_code == 201, r.text
    row = r.json()
    assert [s['adapter_id'] for s in row['steps']] == ['P' + str(i) for i in range(1, n + 1)]
    ids = [str(UUID(s['id'])) for s in row['steps']]
    assert len(set(ids)) == n
    assert row['required_goals'] == [goal]
    assert not row['new_grants'] and not row['automatic_execution'] and not row['case_goal_completed']
    assert [s['id'] for s in read(f, p).json()['steps']] == ids
    assert adopt(f, p, body, key).json()['event'] == row['event']
    assert business(f) == before
    with f[1].connect() as c:
        assert not c.execute('SELECT 1 FROM controlled_plans WHERE preparation_id=%s', (p['preparation_id'],)).fetchone()


def test_dependencies_gate_real_business_apis_and_five_verifications(link_fixture):
    f = link_fixture
    p = setup(f, GOALS[4])
    assert adopt(f, p).status_code == 201
    g = group(f)
    before = business(f)
    assert resource_link(f, p, g).status_code == 409
    assert offer(f, p)[0].status_code == 409
    assert command(f, p, 'P2').status_code == 409
    assert business(f) == before
    verified(f, p, 'P1')
    assert resource_link(f, p, g).status_code == 201
    assert offer(f, p)[0].status_code == 409
    verified(f, p, 'P2')
    d = dispatch_act(f, offer(f, p)[0].json(), 'ACCEPT').json()
    s = f[3].get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], 'executor-a')).json()
    assert receipt_act(f, s, 'SUBMIT').status_code == 409
    verified(f, p, 'P3')
    s = receipt_act(f, s, 'SUBMIT').json()
    s = receipt_act(f, s, 'ACKNOWLEDGE').json()
    assert command(f, p, 'P5').status_code == 409
    verified(f, p, 'P4')
    local = lifecycle_read(f, p).json()
    r = lifecycle_act(f, p, local, 'REVALIDATE')
    assert r.status_code == 200, r.text
    row = verified(f, p, 'P5')
    assert row['state'] == 'VERIFIED'
    assert not row['case_goal_completed']


def test_decline_requires_real_reoffer_accept_and_retry_does_not_accept(link_fixture):
    f = link_fixture
    p = setup(f)
    assert adopt(f, p).status_code == 201
    verified(f, p, 'P1')
    assert resource_link(f, p, group(f)).status_code == 201
    verified(f, p, 'P2')
    d = dispatch_act(f, offer(f, p)[0].json(), 'DECLINE').json()
    before = business(f)
    assert command(f, p, 'P3').status_code == 409
    assert command(f, p, 'P3', 'REPORT_FAILURE', user=REVIEWER).status_code == 200
    assert command(f, p, 'P3', 'RETRY', user=REVIEWER).status_code == 200
    assert business(f) == before
    assert command(f, p, 'P3').status_code == 409
    d = offer(f, p, revision=d['revision'])[0].json()
    d = dispatch_act(f, d, 'ACCEPT').json()
    row = verified(f, p, 'P3')
    assert step(row, 'P3')['actual_business_state'] == 'ACCEPTED'


def test_receipt_changes_require_new_actual_submission_and_acknowledgement(link_fixture):
    f = link_fixture
    p = setup(f)
    assert adopt(f, p).status_code == 201
    _, d = accepted(f, p)
    verified(f, p, 'P3')
    s = f[3].get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], 'executor-a')).json()
    s = receipt_act(f, s, 'SUBMIT').json()
    s = receipt_act(f, s, 'REQUEST_CHANGES').json()
    before = business(f)
    assert command(f, p, 'P4').status_code == 409
    assert command(f, p, 'P4', 'REPORT_FAILURE').status_code == 200
    assert command(f, p, 'P4', 'RETRY').status_code == 200
    assert business(f) == before
    s = receipt_act(f, s, 'SUBMIT', text='SYNTHETIC corrected actual receipt').json()
    assert command(f, p, 'P4').status_code == 409
    s = receipt_act(f, s, 'ACKNOWLEDGE').json()
    row = verified(f, p, 'P4')
    assert step(row, 'P4')['actual_business_state'] == 'LOCAL_ACKNOWLEDGED'
    assert len(s['receipt_history']) == 2


@pytest.mark.parametrize('cap', ['READ', 'PREPARE', 'EXECUTE'])
def test_current_owner_revocation_precedes_lost_reply_replay(link_fixture, cap):
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    old = read(f, p).json()
    key = uuid4().hex
    assert command(f, p, 'P1', row=old, key=key).status_code == 200
    with f[1].connect() as c:
        table = 'preparation_grants' if cap == 'PREPARE' else 'capability_grants'
        c.execute('UPDATE ' + table + " SET active=false WHERE principal_id='fixture-a' AND capability=%s", (cap,))
    before = digest(f)
    assert command(f, p, 'P1', row=old, key=key).status_code == 403
    assert digest(f) == before


@pytest.mark.parametrize('user', ['fixture-b', 'fixture-c', 'unassigned', 'executor-b'])
def test_scope_actor_and_foreign_step_denials_leave_plan_unchanged(link_fixture, user):
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    row = read(f, p).json()
    before = digest(f)
    assert read(f, p, user).status_code == 403
    assert command(f, p, 'P1', row=row, user=user).status_code == 403
    assert digest(f) == before
    assert command(f, p, 'P1', row=row, step_id=str(uuid4())).status_code == 409


def test_lost_reply_replay_key_mismatch_stale_cas_and_source(link_fixture):
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    old = read(f, p).json()
    key = uuid4().hex
    done = command(f, p, 'P1', row=old, key=key)
    assert done.status_code == 200, done.text
    after = digest(f)
    assert command(f, p, 'P1', row=old, key=key).json()['event'] == done.json()['event']
    assert digest(f) == after
    assert command(f, p, 'P1', row=old, key=key, reason='SYNTHETIC mismatched key').status_code == 409
    assert command(f, p, 'P1', row=old).status_code == 409
    assert command(f, p, 'P1', expected_source_sha256='0' * 64).status_code == 409


@pytest.mark.parametrize('same_key', [False, True])
def test_concurrent_verify_commits_one_event_or_one_replayed_event(link_fixture, same_key):
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    row = read(f, p).json()
    key = uuid4().hex
    with ThreadPoolExecutor(2) as pool:
        rs = list(pool.map(lambda _: command(f, p, 'P1', row=row, key=key if same_key else uuid4().hex), range(2)))
    assert sorted(r.status_code for r in rs) == ([200, 200] if same_key else [200, 409])
    now = read(f, p).json()
    assert now['revision'] == row['revision'] + 1
    assert len(now['events']) == len(row['events']) + 1


@pytest.mark.parametrize('change', ['request', 'catalog', 'registry'])
def test_stale_adoption_snapshot_rejected_without_plan_or_business_write(link_fixture, monkeypatch, change):
    f = link_fixture
    p = setup(f)
    body = adopt_body(f, p)
    if change == 'request':
        assert save(f, p, goals=[GOALS[0]], text='SYNTHETIC changed request').status_code == 200
    elif change == 'catalog':
        with f[1].connect() as c:
            c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','999'::jsonb)")
    else:
        registry = deepcopy(bp.REGISTRY)
        registry[0]['output'] += ' changed'
        monkeypatch.setattr(bp, 'REGISTRY', registry)
    before = digest(f)
    assert adopt(f, p, body).status_code == 409
    assert digest(f) == before
    assert read(f, p).json()['plan_id'] is None


def test_begin_failure_retry_only_record_coordination_intent(link_fixture):
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    before = business(f)
    original = read(f, p).json()
    ids = [s['id'] for s in original['steps']]
    for action in ('BEGIN', 'REPORT_FAILURE', 'RETRY'):
        r = command(f, p, 'P1', action)
        assert r.status_code == 200, r.text
        assert business(f) == before
        assert [s['id'] for s in r.json()['steps']] == ids
        assert not r.json()['case_goal_completed']
    verified(f, p, 'P1')


def test_current_assignment_required_for_p3_without_creating_access(link_fixture):
    f = link_fixture
    p = setup(f, GOALS[2])
    assert adopt(f, p).status_code == 201
    verified(f, p, 'P1')
    assert resource_link(f, p, group(f)).status_code == 201
    verified(f, p, 'P2')
    with f[1].connect() as c:
        c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
    before = business(f)
    assert command(f, p, 'P3').status_code == 409
    assert offer(f, p)[0].status_code == 403
    assert business(f) == before


@pytest.mark.parametrize('user', [REVIEWER, 'executor-a'])
def test_counterparty_get_is_minimal_and_verify_remains_owner_only(link_fixture, user):
    f = link_fixture
    p = setup(f)
    assert adopt(f, p).status_code == 201
    g, _ = accepted(f, p)
    owner = read(f, p).json()
    before = digest(f)
    r = read(f, p, user)
    assert r.status_code == 200, r.text
    row = r.json()
    assert row['required_goals'] is None and row['binding_issues'] is None
    assert all(s['source_sha256'] is None and s['issues'] is None for s in row['steps'])
    assert 'PRIVATE_CASE_STEP_REQUEST' not in r.text and g['id'] not in r.text
    assert command(f, p, 'P3', row=owner, user=user).status_code == 403
    assert digest(f) == before


def test_stale_request_readoption_archives_immutable_old_ids_and_history(link_fixture):
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    old = verified(f, p, 'P1')
    r = save(f, p, goals=[GOALS[1]], text='SYNTHETIC replacement required goal')
    assert r.status_code == 200, r.text
    p = {**p, 'revision': r.json()['revision']}
    stale = read(f, p).json()
    assert stale['binding_issues']
    before = business(f)
    body = adopt_body(f, p)
    body['expected_plan_revision'] = stale['revision']
    r = adopt(f, p, body)
    assert r.status_code == 201, r.text
    now = r.json()
    assert now['plan_id'] != old['plan_id']
    assert not {s['id'] for s in now['steps']} & {s['id'] for s in old['steps']}
    assert len(now['steps']) == 2
    assert business(f) == before
    archived = next(h for h in now['history'] if h['id'] == old['plan_id'])
    assert [s['id'] for s in archived['steps']] == [s['id'] for s in old['steps']]
    assert archived['events'] == old['events']


def test_coordination_update_failure_rolls_back_plan_and_event(link_fixture, monkeypatch):
    from parkweave import service_case_steps as scs
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    before = digest(f)
    # Fail the production persistence boundary after computing a valid command.
    def failed(*args, **kwargs):
        raise RuntimeError('SYNTHETIC_CASE_STEP_PERSIST_FAILURE')
    monkeypatch.setattr(scs, '_save', failed)
    with pytest.raises(RuntimeError, match='SYNTHETIC_CASE_STEP_PERSIST_FAILURE'):
        command(f, p, 'P1')
    assert digest(f) == before


@pytest.mark.parametrize('change', ['assignment', 'accepted_actor', 'accepted_event_missing', 'receipt_binding'])
def test_p3_verification_requires_current_own_acceptance_and_existing_unique_receipt(link_fixture, change):
    f = link_fixture
    p = setup(f)
    assert adopt(f, p).status_code == 201
    _, d = accepted(f, p)
    with f[1].connect() as c:
        if change == 'assignment':
            c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a'")
        elif change == 'accepted_actor':
            c.execute("UPDATE service_dispatch_events SET actor_id='fixture-a' WHERE action='ACCEPT' AND dispatch_id=%s", (d['dispatch_id'],))
        elif change == 'accepted_event_missing':
            c.execute("UPDATE service_dispatch_events SET action='DECLINE' WHERE action='ACCEPT' AND dispatch_id=%s", (d['dispatch_id'],))
        else:
            c.execute("UPDATE service_receipt_steps SET executor_id='unassigned' WHERE id=%s", (d['receipt_step_id'],))
    before = business(f)
    assert command(f, p, 'P3').status_code == 409
    assert business(f) == before


def test_receipt_source_change_invalidates_checkpoint_preserving_old_verified_evidence(link_fixture):
    f = link_fixture
    p = setup(f)
    assert adopt(f, p).status_code == 201
    _, d = accepted(f, p)
    verified(f, p, 'P3')
    s = f[3].get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], 'executor-a')).json()
    s = receipt_act(f, s, 'SUBMIT').json()
    s = receipt_act(f, s, 'ACKNOWLEDGE').json()
    old = verified(f, p, 'P4')
    key = uuid4().hex
    s = receipt_act(f, s, 'REOPEN').json()
    now = read(f, p).json()
    assert step(now, 'P4')['state'] == 'NEEDS_RECHECK'
    assert now['events'] == old['events']
    assert step(now, 'P4')['verified_sources'] == step(old, 'P4')['verified_sources']
    assert command(f, p, 'P4', row=old, key=key).status_code == 409
    s = receipt_act(f, s, 'SUBMIT', text='SYNTHETIC actual new current evidence').json()
    s = receipt_act(f, s, 'ACKNOWLEDGE').json()
    assert step(read(f, p).json(), 'P4')['state'] == 'NEEDS_RECHECK'
    now = verified(f, p, 'P4')
    assert step(now, 'P4')['verified_sources'] != step(old, 'P4')['verified_sources']
    assert now['events'][:-1] == old['events']


@pytest.mark.parametrize('change', ['submit_actor', 'ack_actor', 'ack_hash'])
def test_p4_verification_rejects_receipt_provenance_changed_under_ack_state(link_fixture, change):
    f = link_fixture
    p = setup(f)
    assert adopt(f, p).status_code == 201
    _, d = accepted(f, p)
    verified(f, p, 'P3')
    s = f[3].get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], 'executor-a')).json()
    s = receipt_act(f, s, 'SUBMIT').json()
    s = receipt_act(f, s, 'ACKNOWLEDGE').json()
    with f[1].connect() as c:
        if change == 'submit_actor':
            c.execute("UPDATE service_receipt_events SET actor_id='fixture-a' WHERE step_id=%s AND action='SUBMIT'", (d['receipt_step_id'],))
        elif change == 'ack_actor':
            c.execute("UPDATE service_receipt_events SET actor_id='executor-a' WHERE step_id=%s AND action='ACKNOWLEDGE'", (d['receipt_step_id'],))
        else:
            c.execute("UPDATE service_receipt_events SET payload=jsonb_set(payload,'{receipt_sha256}',to_jsonb(%s::text)) WHERE step_id=%s AND action='ACKNOWLEDGE'", ('0' * 64, d['receipt_step_id']))
    before = business(f)
    assert command(f, p, 'P4').status_code == 409
    assert business(f) == before


@pytest.mark.parametrize('change', ['catalog', 'registry'])
def test_adopted_binding_change_blocks_checkpoint_and_preserves_immutable_history(link_fixture, monkeypatch, change):
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    old = verified(f, p, 'P1')
    if change == 'catalog':
        with f[1].connect() as c:
            c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','999'::jsonb)")
    else:
        registry = deepcopy(bp.REGISTRY)
        registry[0]['output'] += ' different registered output'
        monkeypatch.setattr(bp, 'REGISTRY', registry)
    now = read(f, p).json()
    assert now['binding_issues'] and now['state'] != 'VERIFIED'
    assert now['binding'] == old['binding'] and now['events'] == old['events']
    assert step(now, 'P1')['verified_sources'] == step(old, 'P1')['verified_sources']
    before = business(f)
    assert command(f, p, 'P1').status_code == 409
    assert business(f) == before


def test_unsupported_goal_and_arbitrary_execution_payload_cannot_adopt(link_fixture):
    f = link_fixture
    p = setup(f, GOALS[0])
    body = adopt_body(f, p)
    before = digest(f)
    assert adopt(f, p, {**body, 'script': 'SYNTHETIC arbitrary script'}).status_code == 422
    assert adopt(f, p, {**body, 'steps': [{'adapter': 'shell.exec'}]}).status_code == 422
    assert adopt(f, p, {**body, 'required_goals': ['REAL_OFFLINE_FULFILLMENT']}).status_code == 409
    assert digest(f) == before


def test_archived_command_lost_reply_replays_old_event_with_current_plan_and_authority(link_fixture):
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    original = read(f, p).json()
    key = uuid4().hex
    done = command(f, p, 'P1', row=original, key=key).json()
    r = save(f, p, goals=[GOALS[1]], text='SYNTHETIC replacement for replay test')
    p = {**p, 'revision': r.json()['revision']}
    stale = read(f, p).json()
    body = adopt_body(f, p)
    body['expected_plan_revision'] = stale['revision']
    current = adopt(f, p, body).json()
    before = digest(f)
    r = command(f, p, 'P1', row=original, key=key)
    assert r.status_code == 200, r.text
    assert r.json()['event'] == done['event']
    assert r.json()['plan_id'] == current['plan_id']
    assert command(f, p, 'P1', row=original).status_code == 409
    assert digest(f) == before
    f[1].revoke_capability('fixture-a', 'EXECUTE')
    before = digest(f)
    assert command(f, p, 'P1', row=original, key=key).status_code == 403
    assert digest(f) == before


def test_adoption_rejects_catalog_change_between_proposal_and_binding(link_fixture, monkeypatch):
    f = link_fixture
    p = setup(f, GOALS[0])
    body = adopt_body(f, p)
    before = business(f)
    proposal = bp._proposal
    def changed_catalog(store, c, principal, parent):
        result = proposal(store, c, principal, parent)
        # An independent catalog owner changes its source after the preview read.
        with f[1].connect() as catalog_owner:
            catalog_owner.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{revision}','999'::jsonb)")
        return result
    monkeypatch.setattr(bp, '_proposal', changed_catalog)
    r = adopt(f, p, body)
    assert r.status_code == 409, r.text
    assert business(f) == before
    with f[1].connect() as c:
        assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s', (p['preparation_id'],)).fetchone()['service_case_plan'] is None


def test_preparation_get_hides_populated_internal_plans_and_specialist_plan_redacts_private_sources(link_fixture):
    f = link_fixture
    p = setup(f, GOALS[0])
    preview = f[3].get('/api/preparations/' + p['preparation_id'] + '/planning-preview', headers=headers(f[2])).json()['current']
    r = f[3].post('/api/preparations/' + p['preparation_id'] + '/planning-preview',
                  headers=headers(f[2], key=uuid4().hex),
                  json={'expected_preparation_revision': p['revision'], 'expected_source_sha256': preview['source_sha256']})
    assert r.status_code == 200, r.text
    assert adopt(f, p).status_code == 201
    owner = command(f, p, 'P1', reason='SYNTHETIC PRIVATE_PLAN_EVENT_ENG096').json()
    assert step(owner, 'P1')['verified_sources'] and owner['binding'] and owner['current_preview']
    with f[1].connect() as c:
        stored = c.execute('SELECT planning_previews,service_case_plan FROM preparations WHERE id=%s', (p['preparation_id'],)).fetchone()
        assert stored['planning_previews'] and stored['service_case_plan']['events']
    before = digest(f)
    for user in ('fixture-a', REVIEWER):
        r = f[3].get('/api/preparations/' + p['preparation_id'], headers=headers(f[2], user))
        assert r.status_code == 200, r.text
        assert 'service_case_plan' not in r.json()['preparation']
        assert 'planning_previews' not in r.json()['preparation']
        assert 'PRIVATE_PLAN_EVENT_ENG096' not in r.text
    r = read(f, p, REVIEWER)
    assert r.status_code == 200, r.text
    specialist = r.json()
    assert specialist['current_preview'] is None and specialist['binding'] is None
    assert specialist['required_goals'] is None and specialist['binding_issues'] is None
    assert specialist['history'] == []
    assert all(s['verified_sources'] is None and s['verified_sha256'] is None and
               s['source_sha256'] is None and s['issues'] is None for s in specialist['steps'])
    assert all(set(e) == {'id', 'revision', 'action', 'step_id'} for e in specialist['events'])
    assert 'PRIVATE_PLAN_EVENT_ENG096' not in r.text and 'PRIVATE_CASE_STEP_REQUEST' not in r.text
    assert read(f, p, 'prep-specialist-fixture-b').status_code == 403
    assert f[3].get('/api/preparations/' + p['preparation_id'], headers=headers(f[2], 'fixture-b')).status_code == 403
    assert digest(f) == before


@pytest.mark.parametrize('change,preview_state', [
    ('request_unsupported', 'PARTIAL'),
    ('request_empty', 'UNKNOWN'),
    ('catalog_missing', 'UNKNOWN'),
])
def test_stale_plan_with_uncovered_current_preview_cannot_readopt_or_archive(link_fixture, change, preview_state):
    f = link_fixture
    p = setup(f, GOALS[0])
    assert adopt(f, p).status_code == 201
    original = verified(f, p, 'P1')
    if change.startswith('request_'):
        goals = [GOALS[0], 'REAL_EXTERNAL_ACCEPTANCE'] if change == 'request_unsupported' else []
        r = save(f, p, goals=goals, text='SYNTHETIC explicit unsupported or empty required goals')
        assert r.status_code == 200, r.text
        p = {**p, 'revision': r.json()['revision']}
    else:
        with f[1].connect() as c:
            c.execute("UPDATE preparation_catalog SET source='{}'::jsonb")
    stale = read(f, p).json()
    assert stale['binding_issues']
    assert stale['current_preview']['state'] == preview_state
    assert stale['can_adopt'] is False
    assert stale['plan_id'] == original['plan_id']
    assert stale['history'] == original['history'] and stale['events'] == original['events']
    body = adopt_body(f, p)
    body['expected_plan_revision'] = stale['revision']
    if change == 'request_empty':
        # A valid-shaped proposal still cannot override the current empty intent.
        body['required_goals'] = [GOALS[0]]
    before = digest(f)
    r = adopt(f, p, body)
    assert r.status_code == 409, r.text
    assert digest(f) == before
    after = read(f, p).json()
    assert after['plan_id'] == original['plan_id']
    assert after['history'] == original['history'] and after['events'] == original['events']


@pytest.mark.parametrize('field', ['receipt_step_id', 'offer_id', 'dispatch_id', 'state', 'actor_id', 'revision', 'executor_id', 'action'])
def test_p3_rejects_accept_payload_that_does_not_match_current_business_binding(link_fixture, field):
    from psycopg.types.json import Jsonb
    f = link_fixture
    p = setup(f)
    assert adopt(f, p).status_code == 201
    _, d = accepted(f, p)
    with f[1].connect() as c:
        event = c.execute("SELECT id,payload FROM service_dispatch_events WHERE dispatch_id=%s AND action='ACCEPT'", (d['dispatch_id'],)).fetchone()
        payload = dict(event['payload'])
        payload[field] = 999 if field == 'revision' else str(uuid4()) if field.endswith('_id') else 'SYNTHETIC_WRONG_BINDING'
        c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s', (Jsonb(payload), event['id']))
    before = business(f)
    r = command(f, p, 'P3')
    assert r.status_code == 409, r.text
    assert business(f) == before
    assert step(read(f, p).json(), 'P3')['state'] != 'VERIFIED'


@pytest.mark.parametrize('action,field', [
    ('SUBMIT', 'step_id'), ('SUBMIT', 'actor_id'), ('SUBMIT', 'action'),
    ('SUBMIT', 'revision'), ('SUBMIT', 'state'),
    ('ACKNOWLEDGE', 'step_id'), ('ACKNOWLEDGE', 'actor_id'), ('ACKNOWLEDGE', 'action'),
    ('ACKNOWLEDGE', 'revision'), ('ACKNOWLEDGE', 'receipt_sha256'), ('ACKNOWLEDGE', 'state'),
    ('ACKNOWLEDGE', 'receipt_id'), ('ACKNOWLEDGE', 'scope'), ('ACKNOWLEDGE', 'table_revision'),
    ('ACKNOWLEDGE', 'actual_version'),
])
def test_p4_rejects_event_payload_or_current_ack_revision_mismatch(link_fixture, action, field):
    from psycopg.types.json import Jsonb
    f = link_fixture
    p = setup(f)
    assert adopt(f, p).status_code == 201
    _, d = accepted(f, p)
    verified(f, p, 'P3')
    s = f[3].get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], 'executor-a')).json()
    s = receipt_act(f, s, 'SUBMIT').json()
    s = receipt_act(f, s, 'ACKNOWLEDGE').json()
    with f[1].connect() as c:
        event = c.execute('SELECT id,payload,revision FROM service_receipt_events WHERE step_id=%s AND action=%s', (d['receipt_step_id'], action)).fetchone()
        payload = dict(event['payload'])
        if field == 'actual_version':
            c.execute('UPDATE service_step_receipts SET version=99 WHERE id=%s', (s['current_receipt']['id'],))
        elif field == 'table_revision':
            payload['revision'] = event['revision'] + 100
            c.execute('UPDATE service_receipt_events SET revision=%s,payload=%s WHERE id=%s', (payload['revision'], Jsonb(payload), event['id']))
        else:
            payload[field] = 999 if field == 'revision' else str(uuid4()) if field.endswith('_id') else '0' * 64 if field == 'receipt_sha256' else 'SYNTHETIC_WRONG_BINDING'
            c.execute('UPDATE service_receipt_events SET payload=%s WHERE id=%s', (Jsonb(payload), event['id']))
    before = business(f)
    r = command(f, p, 'P4')
    assert r.status_code == 409, r.text
    assert business(f) == before
    assert step(read(f, p).json(), 'P4')['state'] != 'VERIFIED'


def test_specialist_service_plan_hides_actual_receipt_state_after_real_ack(link_fixture):
    f = link_fixture
    p = setup(f)
    assert adopt(f, p).status_code == 201
    _, d = accepted(f, p)
    verified(f, p, 'P3')
    s = f[3].get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], 'executor-a')).json()
    s = receipt_act(f, s, 'SUBMIT').json()
    s = receipt_act(f, s, 'ACKNOWLEDGE').json()
    verified(f, p, 'P4')
    before = digest(f)
    r = read(f, p, REVIEWER)
    assert r.status_code == 200, r.text
    assert step(r.json(), 'P4')['actual_business_state'] is None
    assert step(r.json(), 'P4')['verified_sources'] is None
    assert f[3].get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], REVIEWER)).status_code == 403
    assert digest(f) == before
