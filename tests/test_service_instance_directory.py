"""Actual owned PG discovery: no Case, business write, journal write, or source lease."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from parkweave.api import create_app
from parkweave import controlled_plans as cp
from parkweave.store import Conflict
from test_preparation import preparation_fixture, headers
from test_service_capability_catalog_actual import capability_catalog
from test_service_instance_consumer import setup
from service_release_acceptance_support import table_snapshot


def client(a, facade):
    return TestClient(create_app(a['f'][0], capability_catalog=a['catalog'], instance_consumer=facade))


def pg_snapshot(owner):
    with owner.connect() as c:
        names = [r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()]
    assert len(names) == 46
    return table_snapshot(owner, names)


def unchanged_business_with_original_denial_audit(owner, before):
    after = pg_snapshot(owner)
    # Keep the original global denial audit; it is not a business/journal write.
    old_audit, new_audit = before.pop('authorization_audit'), after.pop('authorization_audit')
    assert after == before
    assert new_audit[:len(old_audit)] == old_audit or not old_audit
    assert len(new_audit) == len(old_audit) + 1
    assert new_audit[-1]['outcome'] == 'DENIED'


def test_directory_current_exact_own_no_case_no_writes_no_source_lease(capability_catalog, tmp_path, monkeypatch):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    api = client(a, facade)
    owner, tokens = a['f'][1:3]
    before = pg_snapshot(owner)
    journal_before = facade.repository.path.read_bytes()
    source_before = a['consumer'].repository.path.read_bytes()
    @contextmanager
    def forbidden():
        pytest.fail('directory attempted a source publication writer lease')
        yield
    monkeypatch.setattr(a['catalog'], 'source_lease', forbidden)
    response = api.get('/api/service-instance-configurations', headers=headers(tokens, 'fixture-c'))
    assert response.status_code == 200, response.text
    value = response.json()
    assert set(value) == {'scope','actor_ref','park_id','read_only','automatically_replayed','provider_enabled','execution_enabled','new_grants','automatic_adoption','instances','allowed_goals','has_unknown_sources'}
    assert value['scope'] == 'SYNTHETIC_PARK_INSTANCE_COLD_INPUT_DIRECTORY'
    assert value['actor_ref'] == cp._hash(dict(actor_id='fixture-c'))
    assert value['park_id'] == 'park-b' and value['read_only'] is True
    assert all(value[n] is False for n in ('automatically_replayed','provider_enabled','execution_enabled','new_grants','automatic_adoption','has_unknown_sources'))
    assert value['allowed_goals'] == ['LOCAL_MATERIAL_PREPARATION']
    row = value['instances'][0]
    assert set(row) == {'instance_id','config_revision','config_sha256','release_id','release_revision','release_sha256','service_id','title','supported_goals','fields'}
    assert row['instance_id'] == data.instance_id and row['config_sha256'] == data.expected_config_sha256
    assert row['release_revision'] == 1
    assert row['fields'] == {material.slot: field for field, material in data.fields.items()}
    assert pg_snapshot(owner) == before
    assert facade.repository.path.read_bytes() == journal_before
    assert a['consumer'].repository.path.read_bytes() == source_before
    with owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n'] == 0


@pytest.mark.parametrize('kind', ['READ','PREPARE','EXECUTE','case.create'])
def test_directory_current_revocation_refused_no_write(capability_catalog, tmp_path, kind):
    a = capability_catalog
    facade, _ = setup(a, tmp_path)
    owner, tokens = a['f'][1:3]
    with owner.connect() as c:
        owner.lock_principal(c, 'fixture-c', exclusive=True)
        table, column = ('action_grants','action') if kind == 'case.create' else ('preparation_grants','capability') if kind == 'PREPARE' else ('capability_grants','capability')
        c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND '+column+'=%s', ('fixture-c',kind))
    before = pg_snapshot(owner)
    response = client(a, facade).get('/api/service-instance-configurations', headers=headers(tokens, 'fixture-c'))
    assert response.status_code == 403, response.text
    unchanged_business_with_original_denial_audit(owner, before)


def test_directory_defaultclosed_other_owner_and_nonowner(capability_catalog, tmp_path):
    a = capability_catalog
    facade, _ = setup(a, tmp_path)
    tokens = a['f'][2]
    assert a['f'][3].get('/api/service-instance-configurations', headers=headers(tokens,'fixture-c')).status_code == 403
    api = client(a, facade)
    assert api.get('/api/service-instance-configurations', headers=headers(tokens,'prep-specialist-fixture-c')).status_code == 403
    value = api.get('/api/service-instance-configurations', headers=headers(tokens,'fixture-a')).json()
    assert value['instances'] == [] and value['allowed_goals'] == []
    assert 'park-b' not in str(value)


@pytest.mark.parametrize('withdraw', ['instance','release','review'])
def test_directory_withdrawal_and_source_change_hide_current_then_prepare_refuses(capability_catalog, tmp_path, withdraw):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    api, tokens = client(a, facade), a['f'][2]
    assert len(api.get('/api/service-instance-configurations', headers=headers(tokens,'fixture-c')).json()['instances']) == 1
    if withdraw == 'instance':
        a['catalog'].withdraw_instance('park-b',uuid4().hex,data.instance_id,1,'SYNTHETIC withdraw configuration')
    elif withdraw == 'release':
        a['catalog'].withdraw_release('park-a',uuid4().hex,data.expected_release_id,1,'SYNTHETIC withdraw capability')
    else:
        a['now'][0] = a['now'][0].replace(year=2100)
    before = pg_snapshot(a['f'][1])
    view = api.get('/api/service-instance-configurations', headers=headers(tokens,'fixture-c')).json()
    assert view['instances'] == [] and view['allowed_goals'] == []
    assert view['has_unknown_sources'] is (withdraw != 'instance')
    response = api.post('/api/service-instance-cold-inputs',headers=headers(tokens,'fixture-c',uuid4().hex),json=data.model_dump(mode='json'))
    assert response.status_code in (403,409), response.text
    if response.status_code == 403:
        unchanged_business_with_original_denial_audit(a['f'][1], before)
    else:
        assert pg_snapshot(a['f'][1]) == before


def test_recovery_subject_key_and_flags_exact(capability_catalog, tmp_path):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    api, tokens = client(a, facade), a['f'][2]
    key = uuid4().hex
    response = api.post('/api/service-instance-cold-inputs',headers=headers(tokens,'fixture-c',key),json=data.model_dump(mode='json'))
    assert response.status_code == 201, response.text
    view = response.json()
    assert view['scope'] == 'SYNTHETIC_PARK_INSTANCE_COLD_INPUT'
    assert view['actor_ref'] == cp._hash(dict(actor_id='fixture-c'))
    assert view['request_key'] == key and view['park_id'] == 'park-b'
    assert view['read_only'] is True
    assert all(view[n] is False for n in ('automatically_replayed','provider_enabled','execution_enabled'))
    assert api.get('/api/service-instance-cold-inputs/recovery',headers=headers(tokens,'fixture-c',key)).json() == view
    assert api.get('/api/service-instance-cold-inputs/recovery',headers=headers(tokens,'fixture-a',key)).status_code == 403


def test_directory_result_does_not_authorize_delayed_prepare_after_withdrawal(capability_catalog, tmp_path):
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    token = a['f'][2]['fixture-c']
    ready, proceed = Event(), Event()
    def delayed_owner():
        view = facade.configurations(token)
        ready.set()
        assert proceed.wait(5)
        with pytest.raises(Conflict):
            facade.prepare(token,uuid4().hex,data)
        return view
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(delayed_owner)
        assert ready.wait(5)
        a['catalog'].withdraw_instance('park-b',uuid4().hex,data.instance_id,1,'SYNTHETIC concurrent source withdrawal')
        proceed.set()
        assert len(pending.result(timeout=5)['instances']) == 1
    with a['f'][1].connect() as c:
        assert c.execute('SELECT count(*) n FROM runs').fetchone()['n'] == 0
    with facade.repository.connect() as journal:
        assert journal.execute('SELECT count(*) FROM consumer_requests').fetchone()[0] == 0


def test_directory_bound_and_current_mapping_invalidity(capability_catalog, tmp_path):
    from copy import deepcopy
    from parkweave.service_capability_contract import hash_instance
    a = capability_catalog
    facade, data = setup(a, tmp_path)
    token = a['f'][2]['fixture-c']
    # Same exact trusted release, independently named current configurations.
    with a['f'][0].connect() as c:
        from parkweave.service_capability_catalog import row, proof, fold
        _, records = fold(proof(row(c,'park-b')))
        base = records[data.instance_id]['instance']
    for n in range(16):
        instance = deepcopy(base)
        instance['instance_id'] = 'park-b-extra-'+str(n)
        instance['config_sha256'] = hash_instance(instance)
        a['catalog'].bind_instance('park-b',uuid4().hex,instance)
    with pytest.raises(Conflict, match='bounded'):
        facade.configurations(token)
    with a['f'][1].connect() as c:
        a['f'][1].lock_principal(c,'prep-specialist-fixture-c',exclusive=True)
        c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-c' AND capability='REVIEW_ASSIGNED'")
    value = facade.configurations(token)
    assert value['instances'] == [] and value['allowed_goals'] == []
    assert value['has_unknown_sources'] is True
