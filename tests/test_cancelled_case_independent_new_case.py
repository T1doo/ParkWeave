"""Compose existing ordinary commands after cancellation; no clone/migration API."""
from copy import deepcopy
from uuid import UUID, uuid4
import pytest
from fastapi.testclient import TestClient
from parkweave.api import create_app
from parkweave.service_instance_consumer import ParkInstanceConsumer
from parkweave.template_consumer import ConsumerRepository
from parkweave.service_plan_approval import IsolatedPlanApproval
from test_preparation import preparation_fixture, headers, command as material
from test_executor_receipts import receipt_fixture, act as receipt_command
from test_service_capability_catalog_actual import capability_catalog, capability_resource_catalog
from cancel33_fixture_support import cancel33_case
from test_schema33_before_receipt_cancellation import cancel_body
from test_case_cancellation_before_receipt import post as cancel_case, recover as recover_cancel
from test_plan_replacement_reapproval import generate
from test_new_enterprise_local_chain import ALL_GOALS
from test_service_case_steps import verified
from test_service_plan_approval import enable, approved
from test_case_resource_delivery import quoted, submit
from test_resource_bundles import cancel as release_bundle, states
from test_service_dispatches import offer, command as dispatch_command
from test_case_lifecycle import read as local_read, act as local_command
from service_release_acceptance_support import case_history


def ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()


def cancelled_old(x):
    f, p = x['f'], x['p']
    key = uuid4().hex
    ok(cancel_case(f, p, cancel_body(x), key))
    saved = case_history(f[1], p['preparation_id'])
    assert saved['cases'][0]['state'] == 'CANCELLED'
    assert states(f, x['holds']) == ['CONFIRMED'] * len(x['holds'])
    return key, saved


def assert_old_preserved(x, original, *, released=False):
    f, p = x['f'], x['p']
    current = case_history(f[1], p['preparation_id'])
    expected = deepcopy(original)
    if released:
        for row in expected['synthetic_resource_holds']:
            row['state'] = 'RELEASED'
    assert current == expected
    assert current['cases'][0]['state'] == 'CANCELLED'
    assert not current['service_step_receipts']
    assert all(row['state'] == 'ACCEPTED' for row in current['service_dispatch_offers'])


def fresh_cold_case(f, facade):
    api = f[3]
    directory = ok(api.get('/api/service-instance-configurations', headers=headers(f[2])))
    instance = next(i for i in directory['instances'] if i['service_id'] == 'synthetic-material-preparation')
    body = dict(instance_id=instance['instance_id'], expected_config_revision=instance['config_revision'],
        expected_config_sha256=instance['config_sha256'], expected_release_id=instance['release_id'],
        expected_release_sha256=instance['release_sha256'], goal='SYNTHETIC NEW_AFTER_CANCEL entirely fresh request',
        required_goals=ALL_GOALS, fields={instance['fields'][slot]: dict(slot=slot,
            text='SYNTHETIC NEW_AFTER_CANCEL independent ' + slot, source_kind='USER_STATEMENT',
            source_label='SYNTHETIC fresh independently submitted source') for slot in ('need_summary', 'material_outline')},
        reason='SYNTHETIC explicit independent new input after old cancellation')
    key = uuid4().hex
    view = ok(api.post('/api/service-instance-cold-inputs', headers=headers(f[2], key=key), json=body), 201)
    assert not view['automatic_adoption'] and not view['automatic_execution']
    assert api.post('/api/service-instance-cold-inputs', headers=headers(f[2], key=key),
        json={**body, 'goal': 'SYNTHETIC changed original key parameters'}).status_code == 409
    assert api.get('/api/service-instance-cold-inputs/recovery', headers=headers(f[2], 'fixture-b', key)).status_code == 403
    prep_id = None
    for name in ('CREATE_RUN', 'CREATE_PREPARATION', 'SAVE_REQUEST', 'ADD_need_summary', 'ADD_material_outline'):
        if name != 'CREATE_RUN':
            view = ok(api.post('/api/service-instance-cold-inputs/prepare-stage', params={'stage': name},
                headers=headers(f[2], key=key)))
        stage = next(s for s in view['stages'] if s['name'] == name)
        path = '/api/runs' if name == 'CREATE_RUN' else '/api/preparations' if name == 'CREATE_PREPARATION' else '/api/preparations/' + prep_id + ('/request-intent' if name == 'SAVE_REQUEST' else '/commands')
        response = api.post(path, headers=headers(f[2], key=stage['request_key']), json=stage['body'])
        assert response.status_code in (200, 201, 202), response.text
        if name == 'CREATE_RUN':
            # Original local worker, independent from any model/provider.
            work = f[0].claim('SYNTHETIC independent post-cancellation new Case fixture worker')
            assert work and str(work['id']) == response.json()['run_id']
            f[0].finish(work)
        if name == 'CREATE_PREPARATION':
            prep_id = response.json()['preparation_id']
        # Discard the response and recover the actual original key, without POST replay.
        view = ok(api.get('/api/service-instance-cold-inputs/recovery', headers=headers(f[2], key=key)))
        observed = next(o for o in view['product_observations'] if o['name'] == name)
        assert observed['status'] == 'COMMITTED' and not observed['automatically_replayed']
    p = ok(api.get('/api/preparations/' + prep_id, headers=headers(f[2])))['preparation']
    actual = ok(api.get('/api/preparations/' + prep_id, headers=headers(f[2])))
    assert {m['text'] for m in actual['current_materials']} == {m['text'] for m in body['fields'].values()}
    with f[1].connect() as c:
        assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s', (prep_id,)).fetchone()['service_case_plan'] is None
    return {**p, 'preparation_id': prep_id}


def test_cancelled_accepted_case_new_input_independent_approval_capacity_release_and_six_goal_outputs(cancel33_case, capability_resource_catalog, tmp_path):
    x = cancel33_case
    original_f = x['f']
    a = capability_resource_catalog
    assert a['f'] is original_f
    old_key, original = cancelled_old(x)
    facade = ParkInstanceConsumer(a['catalog'], ConsumerRepository(tmp_path / 'independent-new-case.consumer.candidate.sqlite3'), enabled_for_isolated_tests=True)
    with TestClient(create_app(original_f[0], capability_catalog=a['catalog'], instance_consumer=facade)) as api:
        f = original_f[:3] + (api,)
        p = fresh_cold_case(f, facade)
        for key in ('run_id', 'case_id', 'preparation_id'):
            assert p[key] != x['p'][key]
        new_materials = ok(api.get('/api/preparations/' + p['preparation_id'], headers=headers(f[2])))['current_materials']
        assert {m['id'] for m in new_materials}.isdisjoint(str(m['id']) for m in original['preparation_evidence'])
        assert {m['text'] for m in new_materials}.isdisjoint(m['text'] for m in original['preparation_evidence'])
        assert_old_preserved(x, original)
        # Explicit owned-fixture setup for this independently created Run using existing identities.
        # It is neither inherited old assignment nor a product permission grant.
        with f[1].connect() as c:
            assert not c.execute('SELECT 1 FROM run_assignments WHERE run_id=%s', (p['run_id'],)).fetchone()
        f[1].assign_status('executor-a', UUID(p['run_id']), active=True)
        for action, actor in [('REVIEW', 'prep-specialist-fixture-a'), ('CONFIRM', 'fixture-a')]:
            p = ok(material(f, p, action, actor, reason='SYNTHETIC new Case independent ' + action))
        generate({**a, 'f': f}, p)
        verified(f, p, 'P1')
        with f[1].connect() as c:
            old_plan = original['preparations'][0]['service_case_plan']
            new_plan = c.execute('SELECT service_case_plan FROM preparations WHERE id=%s', (p['preparation_id'],)).fetchone()['service_case_plan']
        assert old_plan['id'] != new_plan['id'] and new_plan['required_goals'] == ALL_GOALS
        assert len(new_plan['steps']) == 5
        bridge = IsolatedPlanApproval(f[1], f[1]._case_fact_fixture_receipt, preparation_ids=[x['p']['preparation_id'], p['preparation_id']], enabled_for_isolated_tests=True)
        bridge.attach_store(f[0])
        old_members = dict(members=[dict(hold_id=h['id'], expected_revision=h['resource_revision']) for h in x['holds']])
        assert api.post('/api/preparations/' + p['preparation_id'] + '/resource-delivery/preview', headers=headers(f[2]), json=old_members).status_code == 409
        for h in x['holds']:
            data = dict(starts_at=h['starts_at'], ends_at=h['ends_at'], quantity=2,
                expected_revision=h['resource_revision'], ttl_seconds=300, purpose='SYNTHETIC new capacity demand before independent release')
            refused = api.post('/api/synthetic-resources/' + h['resource_id'] + '/holds', headers=headers(f[2], key=uuid4().hex), json=data)
            assert refused.status_code == 409, refused.text
        assert_old_preserved(x, original)
        group_id = str(original['case_resource_links'][-1]['combination_id'])
        release = ok(release_bundle(f, group_id))
        assert release['combination']['state'] == 'CANCELLED'
        assert_old_preserved(x, original, released=True)
        new_holds = []
        for h in x['holds']:
            with f[1].connect() as c:
                revision = c.execute('SELECT revision FROM synthetic_resources WHERE id=%s', (h['resource_id'],)).fetchone()['revision']
            data = dict(starts_at=h['starts_at'], ends_at=h['ends_at'], quantity=2,
                expected_revision=revision, ttl_seconds=300, purpose='SYNTHETIC independent new reservation after authorized release')
            new_holds.append(ok(api.post('/api/synthetic-resources/' + h['resource_id'] + '/holds', headers=headers(f[2], key=uuid4().hex), json=data), 201)['hold'])
        assert {h['id'] for h in new_holds}.isdisjoint(h['id'] for h in x['holds'])
        data = quoted(f, p, dict(members=[dict(hold_id=h['id'], expected_revision=h['resource_revision']) for h in new_holds]))
        old_approval = original['preparations'][0]['candidate_plan_approvals']['events'][-1]['approval_id']
        assert submit(f, p, {**data, 'approval_id': old_approval}).status_code == 409
        item, _ = approved(f, p, data)
        assert item['id'] != old_approval
        sent = ok(submit(f, p, {**data, 'approval_id': item['id']}), 201)
        assert sent['link']['id'] != str(original['case_resource_links'][-1]['id'])
        assert sent['combination']['id'] != group_id
        verified(f, p, 'P2')
        catalog = ok(api.get('/api/service-dispatches/catalog', params={'preparation_id': p['preparation_id']}, headers=headers(f[2], 'prep-specialist-fixture-a')))
        d = ok(offer(f, p, expected_business_frontier=catalog['business_frontier'])[0], 201)
        d = ok(dispatch_command(f, d, 'ACCEPT', expected_business_frontier=d['business_frontier']))
        assert d['dispatch_id'] != x['accepted']['dispatch_id'] and d['receipt_step_id'] != x['accepted']['receipt_step_id']
        verified(f, p, 'P3')
        row = ok(api.get('/api/executor-receipts/' + d['receipt_step_id'], headers=headers(f[2], 'executor-a')))
        row = ok(receipt_command(f, row, 'SUBMIT', text='SYNTHETIC independent new Case actual manual receipt', expected_business_frontier=row['business_frontier']))
        row = ok(receipt_command(f, row, 'ACKNOWLEDGE', expected_business_frontier=row['business_frontier']))
        verified(f, p, 'P4')
        local = ok(local_read(f, p))
        ok(local_command(f, p, local, 'REVALIDATE', expected_business_frontier=local['business_frontier']))
        local = ok(local_read(f, p))
        ok(local_command(f, p, local, 'CLOSE_LOCAL_RECORD', expected_business_frontier=local['business_frontier']))
        verified(f, p, 'P5')
        results = ok(api.get('/api/preparations/' + p['preparation_id'] + '/goal-results', headers=headers(f[2])))
        assert results['state'] == 'LOCAL_OUTPUTS_VERIFIED' and len(results['results']) == 6
        assert not results['case_goal_completed']
        worklist = ok(api.get('/api/cases/worklist', headers=headers(f[2])))
        old_entry = next(i for i in worklist['items'] if i['case_id'] == x['p']['case_id'])
        new_entry = next(i for i in worklist['items'] if i['case_id'] == p['case_id'])
        assert old_entry['attention'] == 'CANCELLED' and new_entry['attention'] == 'LOCAL_CLOSED'
        assert old_entry['case_id'] != new_entry['case_id']
        assert_old_preserved(x, original, released=True)
        assert ok(recover_cancel(f, x['p'], old_key))['current']['case_state'] == 'CANCELLED'


@pytest.mark.parametrize('denial', ['foreign_owner', 'revoked_hold'])
def test_case_cancellation_does_not_authorize_independent_resource_release(cancel33_case, denial):
    x = cancel33_case
    f = x['f']
    _, original = cancelled_old(x)
    group_id = str(original['case_resource_links'][-1]['combination_id'])
    if denial == 'revoked_hold':
        with f[1].connect() as c:
            c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
    response = release_bundle(f, group_id, user='fixture-b' if denial == 'foreign_owner' else 'fixture-a')
    assert response.status_code == 403, response.text
    assert_old_preserved(x, original)
