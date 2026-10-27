"""Fresh second-park inputs; original owned-PG business commands, no auto send."""
from copy import deepcopy
from uuid import uuid4

import pytest

from parkweave.service_instance_consumer import ColdInput, ParkInstanceConsumer
from parkweave.template_consumer import ConsumerRepository
from parkweave.store import Conflict, Denied
from test_preparation import preparation_fixture, headers
from test_service_capability_catalog_actual import capability_catalog, register, material_instance
from service_release_acceptance_support import authority_snapshot


def setup(a, tmp_path):
    release = register(a)['release']
    instance = material_instance(release, 'park-b')
    a['catalog'].bind_instance('park-b', uuid4().hex, instance)
    facade = ParkInstanceConsumer(a['catalog'], ConsumerRepository(tmp_path / 'cold.consumer.candidate.sqlite3'), enabled_for_isolated_tests=True)
    data = ColdInput(instance_id=instance['instance_id'], expected_config_revision=instance['config_revision'], expected_config_sha256=instance['config_sha256'], expected_release_id=release['release_id'], expected_release_sha256=release['release_sha256'], goal='SYNTHETIC second park independently supplied material request', required_goals=['LOCAL_MATERIAL_PREPARATION'], fields={mapping['input_field']:dict(slot=slot, text='SYNTHETIC B new '+slot, source_kind='USER_STATEMENT', source_label='SYNTHETIC second park new source') for slot, mapping in instance['fields'].items()}, reason='SYNTHETIC explicit cold-input confirmation')
    return facade, data


def stage(view, name):
    return next(stage for stage in view['stages'] if stage['name'] == name)


def test_fresh_second_park_original_case_materials_no_auto_adopt(capability_catalog, tmp_path):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    store, owner, tokens, api = a['f']
    before = authority_snapshot(owner)
    key = uuid4().hex
    view = facade.prepare(tokens['fixture-c'], key, data)
    assert len(view['stages']) == 1 and view['automatic_execution'] is False
    assert facade.prepare(tokens['fixture-c'], key, data) == view
    command = stage(view, 'CREATE_RUN')
    reply = api.post('/api/runs', headers=headers(tokens, 'fixture-c', command['request_key']), json=command['body'])
    assert reply.status_code == 202, reply.text
    store.finish(store.claim('SYNTHETIC second park cold-input worker'))
    view = facade.prepare_stage(tokens['fixture-c'], key, 'CREATE_PREPARATION')
    command = stage(view, 'CREATE_PREPARATION')
    reply = api.post('/api/preparations', headers=headers(tokens, 'fixture-c', command['request_key']), json=command['body'])
    assert reply.status_code == 201, reply.text
    preparation_id = reply.json()['preparation_id']
    for name in ('SAVE_REQUEST', 'ADD_need_summary', 'ADD_material_outline'):
        view = facade.prepare_stage(tokens['fixture-c'], key, name)
        command = stage(view, name)
        path = '/api/preparations/' + preparation_id + ('/request-intent' if name == 'SAVE_REQUEST' else '/commands')
        reply = api.post(path, headers=headers(tokens, 'fixture-c', command['request_key']), json=command['body'])
        assert reply.status_code in (200, 201), reply.text
    actual = api.get('/api/preparations/' + preparation_id, headers=headers(tokens, 'fixture-c')).json()
    assert {m['text'] for m in actual['current_materials']} == {material.text for material in data.fields.values()}
    with owner.connect() as c:
        parent = c.execute('SELECT * FROM preparations WHERE id=%s', (preparation_id,)).fetchone()
        assert (parent['park_id'], parent['owner_id'], parent['reviewer_id']) == ('park-b', 'fixture-c', 'prep-specialist-fixture-c')
        assert parent['service_case_plan'] is None
    after = authority_snapshot(owner)
    assert after == before
    recovered = facade.read(tokens['fixture-c'], key)
    assert all(item['status'] == 'COMMITTED' and item['automatically_replayed'] is False for item in recovered['product_observations'])
    assert facade.read(tokens['fixture-c'], key)['automatic_adoption'] is False


def test_cold_binding_exact_external_fields_and_same_key_conflict(capability_catalog, tmp_path):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    token = a['f'][2]['fixture-c']
    key = uuid4().hex
    facade.prepare(token, key, data)
    changed = data.model_copy(update={'goal': 'SYNTHETIC changed goal'})
    with pytest.raises(Conflict): facade.prepare(token, key, changed)
    changed = data.model_dump()
    changed['fields']['invented-field'] = changed['fields'].pop(next(iter(changed['fields'])))
    with pytest.raises(Conflict): facade.prepare(token, uuid4().hex, ColdInput.model_validate(changed))
    changed = data.model_copy(update={'expected_config_revision': 2})
    with pytest.raises(Conflict): facade.prepare(token, uuid4().hex, changed)


def test_history_read_retained_after_source_withdrawal_no_new_commands(capability_catalog, tmp_path):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    token = a['f'][2]['fixture-c']
    key = uuid4().hex
    before = facade.prepare(token, key, data)
    a['catalog'].withdraw_instance('park-b', uuid4().hex, data.instance_id, 1, 'SYNTHETIC explicit withdrawal')
    after = facade.read(token, key)
    assert after['current_available'] is False
    assert after['input'] == before['input'] and after['stages'] == before['stages']
    with pytest.raises(Conflict): facade.prepare_stage(token, key, 'CREATE_PREPARATION')


def test_cross_park_nonowner_and_default_disabled(capability_catalog, tmp_path):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    key = uuid4().hex
    facade.prepare(a['f'][2]['fixture-c'], key, data)
    for user in ('fixture-a', 'prep-specialist-fixture-c'):
        with pytest.raises(Denied): facade.read(a['f'][2][user], key)
    with pytest.raises(Denied): ParkInstanceConsumer(a['catalog'], facade.repository)
    with pytest.raises(Denied): ParkInstanceConsumer(a['catalog'], a['consumer'].repository, enabled_for_isolated_tests=True)


def test_original_run_reply_recovered_after_journal_restart_without_resend(capability_catalog, tmp_path):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    store, owner, tokens, api = a['f']
    key = uuid4().hex
    view = facade.prepare(tokens['fixture-c'], key, data)
    command = stage(view, 'CREATE_RUN')
    # Commit the original request and deliberately discard its response.
    response = api.post('/api/runs', headers=headers(tokens, 'fixture-c', command['request_key']), json=command['body'])
    assert response.status_code == 202
    del response
    with owner.connect() as c:
        count = c.execute('SELECT count(*) n FROM runs').fetchone()['n']
    restarted = ParkInstanceConsumer(a['catalog'], ConsumerRepository(facade.repository.path), enabled_for_isolated_tests=True)
    recovered = restarted.read(tokens['fixture-c'], key)
    assert recovered['product_observations'][0]['status'] == 'COMMITTED'
    assert recovered['product_observations'][0]['result']['run_state'] == 'QUEUED'
    assert recovered['product_observations'][0]['automatically_replayed'] is False
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM runs').fetchone()['n'] == count
    with pytest.raises(Conflict): restarted.prepare_stage(tokens['fixture-c'], key, 'CREATE_PREPARATION')


def test_current_prepare_revocation_blocks_replay_but_owner_read_retained(capability_catalog, tmp_path):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    token = a['f'][2]['fixture-c']
    key = uuid4().hex
    view = facade.prepare(token, key, data)
    with a['f'][1].connect() as c:
        a['f'][1].lock_principal(c, 'fixture-c', exclusive=True)
        c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-c' AND capability='PREPARE'")
    with pytest.raises(Denied): facade.prepare(token, key, data)
    after = facade.read(token, key)
    assert after['input'] == view['input'] and after['current_available'] is False
    assert after['product_observations'][0]['status'] == 'NOT_OBSERVED'


@pytest.mark.parametrize('flag', [1, 'true', [], {}])
def test_non_boolean_fixture_switch_refused(capability_catalog, tmp_path, flag):
    a = capability_catalog
    repository = ConsumerRepository(tmp_path / 'strict.consumer.candidate.sqlite3')
    with pytest.raises(Denied):
        ParkInstanceConsumer(a['catalog'], repository, enabled_for_isolated_tests=flag)


def test_ducktyped_catalog_refused(capability_catalog, tmp_path):
    a = capability_catalog
    class DuckCatalog:
        consumer = a['consumer']
    repository = ConsumerRepository(tmp_path / 'strict.consumer.candidate.sqlite3')
    with pytest.raises(Denied):
        ParkInstanceConsumer(DuckCatalog(), repository, enabled_for_isolated_tests=True)


def test_cancelled_original_new_case_retains_cold_read_blocks_stage_preparation(capability_catalog, tmp_path):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    store, owner, tokens, api = a['f']
    token = tokens['fixture-c']
    key = uuid4().hex
    command = stage(facade.prepare(token, key, data), 'CREATE_RUN')
    response = api.post('/api/runs', headers=headers(tokens, 'fixture-c', command['request_key']), json=command['body'])
    assert response.status_code == 202
    store.finish(store.claim('SYNTHETIC fresh cancellation fixture'))
    command = stage(facade.prepare_stage(token, key, 'CREATE_PREPARATION'), 'CREATE_PREPARATION')
    response = api.post('/api/preparations', headers=headers(tokens, 'fixture-c', command['request_key']), json=command['body'])
    assert response.status_code == 201
    preparation_id = response.json()['preparation_id']
    path = '/api/preparations/' + preparation_id + '/case-cancellation'
    source = api.get(path, headers=headers(tokens, 'fixture-c')).json()
    cancellation = dict(case_id=source['case_id'], expected_preparation_revision=source['preparation_revision'], expected_lifecycle_revision=source['lifecycle_revision'], expected_source_sha256=source['source_sha256'], confirm_cancel=True, reason='SYNTHETIC second park withdraws fresh request')
    response = api.post(path, headers=headers(tokens, 'fixture-c', uuid4().hex), json=cancellation)
    assert response.status_code == 200, response.text
    with pytest.raises(Conflict): facade.prepare_stage(token, key, 'SAVE_REQUEST')
    recovered = facade.read(token, key)
    assert len(recovered['stages']) == 2
    assert all(item['status'] == 'COMMITTED' for item in recovered['product_observations'])
