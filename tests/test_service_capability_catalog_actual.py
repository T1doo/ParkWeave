"""Owned PG governance admission and park mapping; no HTTP publication route."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict

from parkweave.store import Conflict, Denied
from parkweave.template_candidate import Scope, TemplateConfig, TemplateEngine, TemplateRepository, Command
from parkweave.template_consumer import ConsumerConfig, ConsumerRepository, TemplateConsumer
from parkweave.service_capability_catalog import IsolatedServiceCapabilityCatalog
from parkweave.service_capability_contract import hash_instance
from test_preparation import preparation_fixture, create
from test_executor_receipts import receipt_fixture
from test_template_candidate import template_config, definition, VALID
from service_release_acceptance_support import authority_snapshot, case_history, stable_hash


@pytest.fixture
def capability_catalog(preparation_fixture, tmp_path):
    f = preparation_fixture
    config = template_config().model_dump(mode='json')
    for permit in config['permits']:
        permit['scope']['park_id'] = 'park-a'
    now = [datetime(2026, 10, 14, tzinfo=timezone.utc)]
    engine = TemplateEngine(TemplateConfig.model_validate(config),
                            TemplateRepository(tmp_path / 'services.template.candidate.sqlite3'),
                            lambda: now[0])
    scope = Scope(park_id='park-a', template_id='new-enterprise-material-template')
    for action, actor in [('SAVE_DRAFT', 'template-author'), ('SUBMIT', 'template-author'),
                          ('REVIEW', 'template-reviewer'), ('CANDIDATE_PUBLISH', 'template-publisher')]:
        view = engine.read(actor, scope)
        data = dict(action=action, expected_revision=view['revision'],
                    expected_definition_sha256=view['definition_sha256'],
                    reason='SYNTHETIC independently reviewed service fixture ' + action)
        if action == 'SAVE_DRAFT':
            data['draft'] = definition(goals=['LOCAL_MATERIAL_PREPARATION',
                'LOCAL_CASE_RESOURCE_ASSOCIATION', 'LOCAL_INTERNAL_ACCEPTANCE',
                'LOCAL_SYNTHETIC_RECEIPT_ACKNOWLEDGEMENT',
                'LOCAL_SYNTHETIC_COORDINATION_RECORDS', 'LOCAL_CASE_RECORD_RECHECK']).model_dump(mode='json')
        if action == 'CANDIDATE_PUBLISH':
            data['validity'] = VALID
        engine.command(actor, scope, uuid4().hex, Command.model_validate(data))
    published = engine.public_catalog('park-a')['items'][0]
    consumer = TemplateConsumer(f[0], engine,
        ConsumerConfig(enabled_for_isolated_tests=True,
            allowed_database_names=[conninfo_to_dict(f[0].dsn)['dbname']],
            allowed_orgs=[dict(park_id='park-a', org_id='org-a'), dict(park_id='park-b', org_id='org-c')]),
        ConsumerRepository(tmp_path / 'services.consumer.candidate.sqlite3'))
    f[1].migrate_service_capability_fixture()
    catalog = IsolatedServiceCapabilityCatalog(consumer, f[1], enabled_for_isolated_tests=True)
    return dict(f=f, engine=engine, scope=scope, published=published, consumer=consumer,
                catalog=catalog, now=now)


def register(a, service='synthetic-material-preparation', key=None, **extra):
    args = dict(template_scope=a['scope'], template_release_id=a['published']['release_id'],
                expected_template_release_sha256=a['published']['release_sha256'], service_id=service)
    args.update(extra)
    return a['catalog'].register_release('park-a', 'org-a', key or uuid4().hex, **args)


def material_instance(release, park='park-a'):
    owner = 'fixture-c' if park == 'park-b' else 'fixture-a'
    instance = dict(schema_version=1, instance_id=park + '-material-instance', park_id=park,
        release_id=release['release_id'], release_sha256=release['release_sha256'], config_revision=1,
        roles=dict(enterprise_operator=owner, park_specialist='prep-specialist-' + owner), resources={},
        fields={slot:dict(slot=slot, input_field=park + '-fresh-' + slot)
                for slot in ('need_summary', 'material_outline')},
        source=dict(kind='SYNTHETIC', id=park + '-independent-config-source', revision='1', validity=deepcopy(VALID)),
        new_grants=False)
    instance['config_sha256'] = hash_instance(instance)
    return instance


def snapshot(a, parent):
    with a['f'][0].connect() as connection:
        row = connection.execute('SELECT * FROM preparations WHERE id=%s',
                                 (parent['preparation_id'],)).fetchone()
        return a['catalog'].snapshot(connection, row)


def test_original_reviewed_release_registers_and_second_park_binds_own_existing_principals(capability_catalog):
    a = capability_catalog
    f = a['f']
    before = authority_snapshot(f[1])
    p1, _, _ = create(f)
    p2, _, _ = create(f, user='fixture-c', goal='SYNTHETIC independent second park request')
    histories = [case_history(f[1], p['preparation_id']) for p in (p1, p2)]
    event = register(a)
    release = event['release']
    assert release['supported_goals'] == ['LOCAL_MATERIAL_PREPARATION']
    assert release['source_review']['template_release_id'] == a['published']['release_id']
    assert release['source_review']['template_release_sha256'] == a['published']['release_sha256']
    for park in ('park-a', 'park-b'):
        instance = material_instance(release, park)
        assert a['catalog'].bind_instance(park, uuid4().hex, instance)['instance'] == instance
    first, second = snapshot(a, p1), snapshot(a, p2)
    assert first['releases'] == second['releases']
    assert first['instances'][0]['roles']['enterprise_operator'] == 'fixture-a'
    assert second['instances'][0]['roles']['enterprise_operator'] == 'fixture-c'
    assert first['instances'][0]['config_sha256'] != second['instances'][0]['config_sha256']
    assert authority_snapshot(f[1]) == before
    assert [stable_hash(case_history(f[1], p['preparation_id'])) for p in (p1, p2)] == [stable_hash(h) for h in histories]


def test_register_and_bind_same_original_key_replay_changed_body_conflicts(capability_catalog):
    a = capability_catalog
    key = uuid4().hex
    event = register(a, key=key)
    assert register(a, key=key) == event
    with pytest.raises((Conflict, Denied, ValueError)):
        register(a, key=key, service='synthetic-local-record-recheck')
    instance = material_instance(event['release'])
    key = uuid4().hex
    bound = a['catalog'].bind_instance('park-a', key, instance)
    assert a['catalog'].bind_instance('park-a', key, instance) == bound
    different = deepcopy(instance)
    different['fields']['need_summary']['input_field'] = 'explicit-new-field'
    different['config_sha256'] = hash_instance(different)
    with pytest.raises((Conflict, Denied, ValueError)):
        a['catalog'].bind_instance('park-a', key, different)


@pytest.mark.parametrize('change', ['release_hash', 'instance_hash', 'foreign_owner', 'foreign_reviewer',
                                   'inactive_reviewer', 'reviewer_role', 'slot_swap', 'grant', 'old_material'])
def test_resigned_instance_cannot_invent_current_authority_or_copy_business(capability_catalog, change):
    a = capability_catalog
    f = a['f']
    release = register(a)['release']
    value = material_instance(release)
    if change == 'release_hash': value['release_sha256'] = '0' * 64
    elif change == 'foreign_owner': value['roles']['enterprise_operator'] = 'fixture-c'
    elif change == 'foreign_reviewer': value['roles']['park_specialist'] = 'prep-specialist-fixture-b'
    elif change == 'slot_swap': value['fields']['need_summary']['slot'] = 'material_outline'
    elif change == 'grant': value['grant'] = dict(capability='EXECUTE')
    elif change == 'old_material': value['old_material'] = 'SYNTHETIC previous Case private text'
    elif change in ('inactive_reviewer', 'reviewer_role'):
        with f[1].connect() as connection:
            if change == 'inactive_reviewer':
                connection.execute("UPDATE principals SET active=false WHERE id='prep-specialist-fixture-a'")
            else:
                connection.execute("UPDATE principals SET role='enterprise_operator' WHERE id='prep-specialist-fixture-a'")
    value['config_sha256'] = '0' * 64 if change == 'instance_hash' else hash_instance(value)
    before = authority_snapshot(f[1])
    with pytest.raises((Conflict, Denied, ValueError)):
        a['catalog'].bind_instance('park-a', uuid4().hex, value)
    assert authority_snapshot(f[1]) == before


@pytest.mark.parametrize('change', ['hash', 'withdraw', 'expired', 'registry'])
def test_registration_requires_original_current_reviewed_release(capability_catalog, change, monkeypatch):
    a = capability_catalog
    extra = {}
    if change == 'hash': extra['expected_template_release_sha256'] = '0' * 64
    elif change == 'expired': a['now'][0] = datetime(2100, 1, 1, tzinfo=timezone.utc)
    elif change == 'registry':
        from parkweave import bounded_planning as bp
        registry = deepcopy(bp.REGISTRY)
        registry[0]['acceptance'] = 'SYNTHETIC changed registry acceptance'
        monkeypatch.setattr(bp, 'REGISTRY', registry)
    else:
        view = a['engine'].read('template-publisher', a['scope'])
        a['engine'].command('template-publisher', a['scope'], uuid4().hex,
            Command(action='WITHDRAW', expected_revision=view['revision'],
                    expected_definition_sha256=view['definition_sha256'], reason='SYNTHETIC explicit withdraw'))
    before = authority_snapshot(a['f'][1])
    with pytest.raises((Conflict, Denied, ValueError)):
        register(a, **extra)
    assert authority_snapshot(a['f'][1]) == before


def test_application_has_no_new_catalog_write_or_publish_authority(capability_catalog):
    a = capability_catalog
    with a['f'][0].connect() as connection:
        assert connection.execute("SELECT has_table_privilege(current_user,'preparation_catalog','SELECT') AS r, "
                                  "has_table_privilege(current_user,'preparation_catalog','UPDATE') AS w").fetchone() == dict(r=True, w=False)
    register(a)
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        with a['f'][0].connect() as connection:
            connection.execute('UPDATE preparation_catalog SET source=source')
    assert a['f'][3].post('/api/service-capability/releases', json={}).status_code == 404


def test_same_instance_key_concurrent_calls_commit_one_original_event(capability_catalog):
    a = capability_catalog
    release = register(a)['release']
    instance = material_instance(release)
    key = uuid4().hex
    before = authority_snapshot(a['f'][1])
    with ThreadPoolExecutor(max_workers=2) as executor:
        replies = list(executor.map(lambda _:a['catalog'].bind_instance('park-a', key, instance), range(2)))
    assert replies[0] == replies[1]
    p, _, _ = create(a['f'])
    current = snapshot(a, p)
    assert current['instances'] == [instance]
    assert authority_snapshot(a['f'][1]) == before


@pytest.mark.parametrize('bad', ['disabled', 'application_owner'])
def test_catalog_administration_requires_explicit_issued_fixture_owner(capability_catalog, bad):
    a = capability_catalog
    before = authority_snapshot(a['f'][1])
    with pytest.raises((Denied, ValueError)):
        IsolatedServiceCapabilityCatalog(a['consumer'], a['f'][0] if bad == 'application_owner' else a['f'][1],
                                         enabled_for_isolated_tests=bad != 'disabled')
    assert authority_snapshot(a['f'][1]) == before


@pytest.mark.parametrize('target', ['release', 'instance'])
def test_withdrawal_changes_head_and_cold_current_input_without_touching_old_case(capability_catalog, target):
    a = capability_catalog
    f = a['f']
    release = register(a)['release']
    instance = material_instance(release)
    a['catalog'].bind_instance('park-a', uuid4().hex, instance)
    parent, _, _ = create(f)
    history = case_history(f[1], parent['preparation_id'])
    before = snapshot(a, parent)
    key = uuid4().hex
    withdraw = a['catalog'].withdraw_release if target == 'release' else a['catalog'].withdraw_instance
    target_id = release['release_id'] if target == 'release' else instance['instance_id']
    result = withdraw('park-a', key, target_id, before['revision'], 'SYNTHETIC explicit catalog withdrawal')
    assert withdraw('park-a', key, target_id, before['revision'], 'SYNTHETIC explicit catalog withdrawal') == result
    with pytest.raises(Conflict):
        withdraw('park-a', key, target_id, before['revision'], 'SYNTHETIC different original parameters')
    after = snapshot(a, parent)
    assert after['revision'] == before['revision'] + 1 and after['sha256'] != before['sha256']
    assert after['instances'] == []
    if target == 'release': assert after['releases'] == []
    a['catalog'] = IsolatedServiceCapabilityCatalog(a['consumer'], f[1], enabled_for_isolated_tests=True)
    assert snapshot(a, parent) == after
    assert case_history(f[1], parent['preparation_id']) == history


def test_owner_cannot_erase_or_rewrite_catalog_journal_after_admission(capability_catalog):
    a = capability_catalog
    register(a)
    for sql in ("UPDATE preparation_catalog SET service_capability_catalog=NULL WHERE park_id='park-a'",
                "UPDATE preparation_catalog SET service_capability_catalog=jsonb_set(service_capability_catalog,'{events,0,key}','\"rewritten\"'::jsonb) WHERE park_id='park-a'"):
        with pytest.raises(psycopg.Error):
            with a['f'][1].connect() as connection:
                connection.execute(sql)


def test_migration_marker_repair_preserves_original_capability_history(capability_catalog):
    a = capability_catalog
    register(a)
    p, _, _ = create(a['f'])
    before = snapshot(a, p)
    permissions = authority_snapshot(a['f'][1])
    with a['f'][1].connect() as connection:
        connection.execute('DELETE FROM schema_version WHERE version=33')
    a['f'][1].migrate_service_capability_fixture()
    a['f'][1].migrate_service_capability_fixture()
    assert snapshot(a, p) == before
    assert authority_snapshot(a['f'][1]) == permissions


def test_actual_current_mapping_snapshot_proves_one_material_solution(capability_catalog):
    from parkweave.service_selection import enumerate_solutions
    a = capability_catalog
    release = register(a)['release']
    instance = material_instance(release)
    a['catalog'].bind_instance('park-a', uuid4().hex, instance)
    p, _, _ = create(a['f'])
    current = snapshot(a, p)
    verdict = enumerate_solutions(current['releases'], current['instances'],
        dict(park_id='park-a', required_goals=['LOCAL_MATERIAL_PREPARATION'],
             mapping_states=current['mapping_states']), now=a['now'][0])
    assert verdict['state'] == 'UNIQUE'
    assert verdict['selection_variant_count'] == 1 and verdict['distinct_execution_graphs'] == 1
    assert not verdict['execution_enabled'] and not verdict['new_grants']


def test_retained_function_configuration_drift_is_refused_without_schema_replacement(capability_catalog):
    a = capability_catalog
    register(a)
    with a['f'][1].connect() as connection:
        original = connection.execute("SELECT service_capability_catalog FROM preparation_catalog WHERE park_id='park-a'").fetchone()
        # A restrictive search path changes the exact installed contract, not rights.
        connection.execute('ALTER FUNCTION service_capability_prefix() SET search_path=pg_catalog')
    with pytest.raises(Denied):
        IsolatedServiceCapabilityCatalog(a['consumer'], a['f'][1], enabled_for_isolated_tests=True)
    with a['f'][1].connect() as connection:
        connection.execute('DELETE FROM schema_version WHERE version=33')
    with pytest.raises(psycopg.Error):
        a['f'][1].migrate_service_capability_fixture()
    with a['f'][1].connect() as connection:
        assert connection.execute("SELECT service_capability_catalog FROM preparation_catalog WHERE park_id='park-a'").fetchone() == original
        assert connection.execute("SELECT proconfig FROM pg_proc WHERE oid='service_capability_prefix()'::regprocedure").fetchone()['proconfig'] == ['search_path=pg_catalog']


@pytest.mark.parametrize('principal,table,capability', [
    ('fixture-a', 'capability_grants', 'READ'),
    ('fixture-a', 'capability_grants', 'EXECUTE'),
    ('fixture-a', 'preparation_grants', 'PREPARE'),
    ('prep-specialist-fixture-a', 'capability_grants', 'READ'),
    ('prep-specialist-fixture-a', 'preparation_grants', 'REVIEW_ASSIGNED'),
])
def test_fresh_mapping_cannot_replace_revoked_original_permissions(capability_catalog, principal, table, capability):
    a = capability_catalog
    value = material_instance(register(a)['release'])
    with a['f'][1].connect() as connection:
        a['f'][1].lock_principal(connection, principal, exclusive=True)
        connection.execute('UPDATE ' + table + ' SET active=false WHERE principal_id=%s AND capability=%s',
                           (principal, capability))
    before = authority_snapshot(a['f'][1])
    with pytest.raises(Denied):
        a['catalog'].bind_instance('park-a', uuid4().hex, value)
    assert authority_snapshot(a['f'][1]) == before


@pytest.fixture
def capability_resource_catalog(capability_catalog, receipt_fixture):
    from parkweave.resource_combinations import seed_synthetic
    assert receipt_fixture is capability_catalog['f']
    seed_synthetic(receipt_fixture[1])
    return capability_catalog


def coordination_instance(release, park='park-a'):
    from parkweave import resource_holds as rh, resource_combinations as rc
    value = material_instance(release, park)
    value['instance_id'] = park + '-coordination-instance'
    value['roles']['service_executor'] = 'executor-c' if park == 'park-b' else 'executor-a'
    value['resources'] = dict(primary=str(rh.RESOURCE_ID), secondary=str(rc.SECOND_RESOURCE_ID))
    value['config_sha256'] = hash_instance(value)
    return value


def test_coordination_mapping_references_existing_roles_resources_without_new_authority(capability_resource_catalog):
    a = capability_resource_catalog
    before = authority_snapshot(a['f'][1])
    release = register(a, service='synthetic-resource-coordination')['release']
    value = coordination_instance(release)
    assert a['catalog'].bind_instance('park-a', uuid4().hex, value)['instance'] == value
    assert authority_snapshot(a['f'][1]) == before


@pytest.mark.parametrize('change', ['READ', 'HOLD', 'disabled', 'foreign_park'])
def test_resource_mapping_requires_current_same_park_resource_permissions(capability_resource_catalog, change):
    from parkweave import resource_holds as rh
    a = capability_resource_catalog
    value = coordination_instance(register(a, service='synthetic-resource-coordination')['release'],
                                  'park-b' if change == 'foreign_park' else 'park-a')
    if change != 'foreign_park':
        with a['f'][1].connect() as connection:
            a['f'][1].lock_principal(connection, 'fixture-a', exclusive=True)
            rh._lock(connection, rh.RESOURCE_ID)
            if change == 'disabled':
                connection.execute('UPDATE synthetic_resources SET enabled=false WHERE id=%s', (rh.RESOURCE_ID,))
            else:
                connection.execute('UPDATE synthetic_resource_grants SET active=false WHERE principal_id=%s AND resource_id=%s AND capability=%s',
                                   ('fixture-a', rh.RESOURCE_ID, change))
    before = authority_snapshot(a['f'][1])
    with pytest.raises(Denied):
        a['catalog'].bind_instance(value['park_id'], uuid4().hex, value)
    assert authority_snapshot(a['f'][1]) == before


def test_current_release_rederives_original_reviewed_title_instead_of_trusting_resigned_metadata(capability_catalog):
    from parkweave.service_capability_contract import hash_release, validate_release
    from parkweave.service_capability_catalog import row, proof, fold
    a = capability_catalog
    release = register(a)['release']
    with a['f'][1].connect() as connection:
        record = deepcopy(fold(proof(row(connection, 'park-a')))[0][release['release_id']])
    record['release']['title'] = 'SYNTHETIC attacker resigned another reviewed title'
    record['release']['release_sha256'] = hash_release(record['release'])
    # Structural/hash validity cannot substitute for the authenticated source.
    validate_release(record['release'], now=a['now'][0])
    with pytest.raises(Conflict, match='trusted reviewed definition'):
        a['catalog']._current_release(record)


def test_second_park_collection_hash_tracks_portable_unselected_source_add_and_withdraw(capability_catalog):
    a = capability_catalog
    material = register(a)['release']
    a['catalog'].bind_instance('park-b', uuid4().hex, material_instance(material, 'park-b'))
    parent, _, _ = create(a['f'], user='fixture-c', goal='SYNTHETIC portable catalog fingerprint')
    initial = snapshot(a, parent)
    recheck = register(a, service='synthetic-local-record-recheck')['release']
    added = snapshot(a, parent)
    assert initial['revision'] == added['revision']  # B journal did not change.
    assert initial['instances'] == added['instances']
    assert initial['sha256'] != added['sha256']
    assert recheck['release_id'] in {r['release_id'] for r in added['releases']}
    with a['f'][1].connect() as connection:
        from parkweave.service_capability_catalog import row, proof
        revision = proof(row(connection, 'park-a'))['revision']
    a['catalog'].withdraw_release('park-a', uuid4().hex, recheck['release_id'], revision,
                                  'SYNTHETIC withdraw unselected portable definition')
    withdrawn = snapshot(a, parent)
    assert withdrawn['revision'] == added['revision']
    assert withdrawn['sha256'] != added['sha256']
    assert recheck['release_id'] not in {r['release_id'] for r in withdrawn['releases']}


def test_collection_hash_changes_when_current_mapping_permission_is_revoked(capability_catalog):
    a = capability_catalog
    a['catalog'].bind_instance('park-a', uuid4().hex, material_instance(register(a)['release']))
    parent, _, _ = create(a['f'])
    initial = snapshot(a, parent)
    with a['f'][1].connect() as connection:
        a['f'][1].lock_principal(connection, 'prep-specialist-fixture-a', exclusive=True)
        connection.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
    revoked = snapshot(a, parent)
    assert revoked['revision'] == initial['revision']
    assert revoked['sha256'] != initial['sha256']
    assert revoked['instances'] == []
    assert revoked['unknowns'] == ['park-a-material-instance']


def test_non_uuid_resource_reference_is_explicit_denial_not_database_cast_error(capability_resource_catalog):
    a = capability_resource_catalog
    value = coordination_instance(register(a, service='synthetic-resource-coordination')['release'])
    value['resources']['primary'] = 'SYNTHETIC-not-an-existing-resource-uuid'
    value['config_sha256'] = hash_instance(value)
    before = authority_snapshot(a['f'][1])
    with pytest.raises(Denied, match='resource UUID'):
        a['catalog'].bind_instance('park-a', uuid4().hex, value)
    assert authority_snapshot(a['f'][1]) == before
