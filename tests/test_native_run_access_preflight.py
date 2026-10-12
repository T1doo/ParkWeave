"""Offline diffs and actual original-owned PG reads; no production connector."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest
from psycopg.pq import TransactionStatus

from parkweave import native_run_access_preflight as preflight
from parkweave import native_run_access as native, native_run_access_activation as activation
from parkweave.store import Denied


def synthetic_catalog():
    bodies, _ = preflight.expected_storage()
    tables = {name: dict(oid=100+index, owner='synthetic_installer', kind='r', rls=False,
                         force_rls=False, acl=['synthetic_installer=arwdDxt/synthetic_installer'])
              for index, name in enumerate(preflight.TABLES)}
    functions = {name: [dict(oid=200+index, owner='synthetic_installer', arguments='', returns='trigger',
        language='plpgsql', body_sha256=bodies[name], security_definer=False, strict=False,
        leakproof=False, volatility='v', config=None, acl=[])] for index, name in enumerate(preflight.FUNCTIONS)}
    triggers = {name: [dict(relation_oid=tables[table]['oid'], function_oid=functions[function][0]['oid'],
        type=kind, enabled='O', internal=False, constraint_oid=0, columns='', condition=None,
        arguments_count=0, arguments_hex='', deferrable=False, initially_deferred=False,
        old_table=None, new_table=None)] for name, (table, function, kind) in preflight.TRIGGERS.items()}
    privileges = {preflight._privilege_key(*row): True for row in preflight.required_privileges('revision')}
    privileges.update({key: False for key in ('app:assignment_write', 'app:identity_write',
        'app:control_system_execute', 'app:schema_create', 'writer:schema_create', 'writer:unneeded_write')})
    privileges.update({'installer:schema_create': True, 'installer:alter_targets': True})
    role = dict(superuser=False, createdb=False, createrole=False, replication=False,
                bypass_rls=False, dangerous_membership=False, owner_membership=False, writer_membership=False)
    return dict(database=dict(name='SYNTHETIC_DATABASE', oid=42, system_identifier='123456789',
                host='SYNTHETIC_HOST', port=5432, session_user='synthetic_observer', current_user='synthetic_observer'),
        schema_version=32, tables=tables,
        columns={name: dict(type='jsonb', nullable=True, default=None, identity='', generated='') for name in preflight.COLUMNS},
        functions=functions, triggers=triggers, roles={'synthetic_app': role, 'synthetic_writer': deepcopy(role),
            'synthetic_installer': {**role, 'owner_membership': True}},
        privileges=privileges, unneeded_writer_permissions=[])


def synthetic_spec(catalog=None):
    catalog = catalog or synthetic_catalog()
    db = catalog['database'];now = datetime.now(timezone.utc)
    return dict(policy=dict(environment='PRODUCTION', policy_id=str(uuid4()), revision=1,
        owner_id='SYNTHETIC_OWNER', approver_id='SYNTHETIC_APPROVER', beneficiary_id='SYNTHETIC_EXECUTOR',
        approver_actions=['APPROVE', 'REJECT', 'REVOKE'], valid_from=now.isoformat(),
        valid_until=(now+timedelta(minutes=30)).isoformat(), generations={'SYNTHETIC_ONLY': True},
        source=dict(run_id=str(uuid4()), run_revision=1, input_fingerprint='a'*64, owner_id='SYNTHETIC_OWNER',
                    park_id='SYNTHETIC_PARK', org_id='SYNTHETIC_ORG', preparation_id=str(uuid4()), preparation_revision=1,
                    preparation_state='LOCAL_CONFIRMED', review_sha256='b'*64, material_sha256='b'*64, case_id=str(uuid4())),
        database_name=db['name'], database_oid=db['oid'], system_identifier=db['system_identifier'],
        database_host=db['host'], database_port=db['port'], application_role='synthetic_app', writer_role='synthetic_writer'),
        installer_role='synthetic_installer', object_owners={name: row['owner'] for name, row in catalog['tables'].items()},
        permission_strategy='DIRECT_DML', parent_lock_column='revision', protected_location='SYNTHETIC_LOCATION_ONLY',
        api_uid=10001, writer_uid=10002, transport='LINUX_UNIX', policy_source_ref='SYNTHETIC_PUBLIC_REF',
        key_source_ref='SYNTHETIC_REFERENCE_NOT_KEY', host_pin_source_ref='SYNTHETIC_PUBLIC_PIN_REF')


def check(report, name):
    return next(row for row in report['checks'] if row['check'] == name)


def test_offline_pass_is_comparison_only_and_cannot_install_or_activate():
    catalog = synthetic_catalog();report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert report['status'] == 'PASS'
    assert not report['installation_authorized'] and not report['activation_enabled'] and not report['production_connected']
    assert report['installation_status'] == 'APPROVAL_REQUIRED' and not report['changes']
    assert report['mode'] == 'OFFLINE_UNVERIFIED_SNAPSHOT'
    assert report['windows_native'] == report['formal_at35'] == 'NOT_RUN'


def test_missing_config_and_not_connected_are_distinct_without_environment_discovery(monkeypatch):
    monkeypatch.setenv('PARKWEAVE_OWNER_DSN', 'SYNTHETIC_PRIVATE_DSN_MUST_NOT_BE_READ')
    monkeypatch.setattr('psycopg.connect', lambda *a, **k: pytest.fail('preflight must never connect'))
    report = preflight.analyze()
    assert report['status'] == 'MISSING_CONFIG'
    assert check(report, 'database_catalog')['status'] == 'NOT_CONNECTED'
    assert preflight.analyze(synthetic_spec())['status'] == 'NOT_CONNECTED'
    assert 'SYNTHETIC_PRIVATE_DSN_MUST_NOT_BE_READ' not in json.dumps(report)
    catalog = synthetic_catalog();catalog['functions']['guard_native_assignment'][0]['security_definer'] = True
    assert check(preflight.analyze({}, catalog), 'function.guard_native_assignment')['status'] == 'REFUSED'


def test_precise_missing_storage_diff_has_no_executable_sql_or_implicit_rollback():
    catalog = synthetic_catalog();catalog.update(columns={}, functions={}, triggers={})
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert report['status'] == 'APPROVAL_REQUIRED'
    assert len(report['changes']) == 9
    assert {row['action'] for row in report['changes']} == {'ADD_COLUMN', 'CREATE_FUNCTION', 'CREATE_TRIGGER'}
    assert all(row['approval_required'] and row['executable_sql'] is None for row in report['changes'])
    assert all('never drop existing ledger' in row['rollback'] for row in report['changes'])


@pytest.mark.parametrize('mutation', [dict(type='text'), dict(nullable=False), dict(default="'{}'::jsonb"), dict(identity='a'), dict(generated='s')])
def test_same_column_name_does_not_hide_incompatible_storage(mutation):
    catalog = synthetic_catalog();catalog['columns']['runs.native_run_access_protocol'].update(mutation)
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert check(report, 'column.runs.native_run_access_protocol')['status'] == 'REFUSED'
    assert check(report, 'column.runs.native_run_access_protocol')['mismatch_fields'] == list(mutation)
    assert not any(row['object'] == 'public.runs.native_run_access_protocol' for row in report['changes'])


@pytest.mark.parametrize('mutation', [dict(arguments='value integer'), dict(returns='text'), dict(language='sql'),
    dict(body_sha256='f'*64), dict(security_definer=True), dict(strict=True), dict(leakproof=True),
    dict(volatility='s'), dict(config=['search_path=public']), dict(owner='wrong_owner')])
def test_function_body_signature_security_search_path_and_owner_conflicts_are_refused(mutation):
    catalog = synthetic_catalog();catalog['functions']['guard_native_run_access_protocol'][0].update(mutation)
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert check(report, 'function.guard_native_run_access_protocol')['status'] == 'REFUSED'
    assert check(report, 'function.guard_native_run_access_protocol')['mismatch_fields'] == list(mutation)
    assert not report['changes']


def test_function_overload_and_duplicate_trigger_are_not_name_only_matches():
    catalog = synthetic_catalog();catalog['functions']['guard_native_assignment'] *= 2
    catalog['triggers']['native_assignment_bound'] *= 2
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert check(report, 'function.guard_native_assignment')['status'] == 'REFUSED'
    assert check(report, 'trigger.native_assignment_bound')['status'] == 'REFUSED'
    assert 'duplicate_count' in check(report, 'trigger.native_assignment_bound')['mismatch_fields']


@pytest.mark.parametrize('mutation', [dict(relation_oid=900), dict(function_oid=900), dict(type=19), dict(enabled='D'),
    dict(internal=True), dict(constraint_oid=7), dict(columns='3'), dict(condition='true'),
    dict(arguments_count=1), dict(arguments_hex='ff'), dict(deferrable=True), dict(initially_deferred=True),
    dict(old_table='old_rows'), dict(new_table='new_rows')])
def test_exact_trigger_semantics_and_bound_object_oids(mutation):
    catalog = synthetic_catalog();catalog['triggers']['native_assignment_bound'][0].update(mutation)
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert check(report, 'trigger.native_assignment_bound')['status'] == 'REFUSED'
    assert check(report, 'trigger.native_assignment_bound')['mismatch_fields'] == list(mutation)


@pytest.mark.parametrize('flag', ['superuser', 'createdb', 'createrole', 'replication', 'bypass_rls',
                                 'dangerous_membership', 'owner_membership', 'writer_membership'])
def test_inherited_or_set_role_authority_is_not_a_restricted_app(flag):
    catalog = synthetic_catalog();catalog['roles']['synthetic_app'][flag] = True
    assert check(preflight.analyze(synthetic_spec(catalog), catalog), 'role.app')['status'] == 'REFUSED'


def test_effective_permission_gaps_are_separate_and_require_review_not_grant():
    catalog = synthetic_catalog()
    for action, column in [('INSERT', 'native_access'), ('UPDATE', 'active')]:
        catalog['privileges'][preflight._privilege_key('writer', action, 'run_assignments', column)] = False
    catalog['privileges'][preflight._privilege_key('writer', 'LOCK_UPDATE', 'preparations')] = False
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert report['status'] == 'APPROVAL_REQUIRED'
    assert len(report['changes']) == 3
    assert all(row['action'] == 'REVIEW_REQUIRED_PERMISSION' for row in report['changes'])
    assert not any('authorization_audit' in row['object'] for row in report['changes'])


def test_unknown_physical_identity_or_acl_is_not_a_pass():
    catalog = synthetic_catalog();spec = synthetic_spec(catalog)
    catalog['database']['system_identifier'] = None
    del catalog['privileges'][preflight._privilege_key('writer', 'EXECUTE', 'pg_control_system()')]
    report = preflight.analyze(spec, catalog)
    assert report['status'] == 'NOT_CONNECTED'
    assert check(report, 'exact_database_identity')['status'] == 'NOT_CONNECTED'
    assert check(report, 'privilege.writer:EXECUTE:pg_control_system():')['status'] == 'NOT_CONNECTED'


@pytest.mark.parametrize('key', ['app:assignment_write', 'app:identity_write', 'app:control_system_execute',
                              'app:schema_create', 'writer:schema_create', 'writer:unneeded_write'])
def test_excess_effective_privileges_never_request_an_automatic_fix(key):
    catalog = synthetic_catalog();catalog['privileges'][key] = True
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert check(report, 'forbidden.'+key)['status'] == 'REFUSED' and not report['changes']


def test_baseline_identity_session_and_declared_os_scope_are_exact():
    catalog = synthetic_catalog();spec = synthetic_spec(catalog)
    catalog['schema_version'] = 31;catalog['database']['oid'] += 1;catalog['database']['current_user'] = 'set_role_app'
    spec['writer_uid'] = spec['api_uid']
    report = preflight.analyze(spec, catalog)
    for name in ('baseline_version', 'exact_database_identity', 'catalog_observer_session', 'independent_os_identity'):
        assert check(report, name)['status'] == 'REFUSED'


def test_narrow_interface_windows_and_rls_stay_pending_even_with_compatible_storage():
    catalog = synthetic_catalog();spec = synthetic_spec(catalog)
    spec.update(permission_strategy='NARROW_FUNCTIONS', transport='WINDOWS_NATIVE')
    catalog['tables']['runs']['rls'] = True
    report = preflight.analyze(spec, catalog)
    assert report['status'] == 'APPROVAL_REQUIRED'
    assert all(check(report, name)['status'] == 'APPROVAL_REQUIRED' for name in ('permission_strategy', 'transport', 'rls.runs'))


@pytest.mark.parametrize('bad', [False, [], {'writer_dsn': 'SYNTHETIC_SECRET_MUST_NOT_ECHO'}, {'policy': {'key': 'SYNTHETIC_SECRET_MUST_NOT_ECHO'}}])
def test_untyped_or_private_input_is_refused_without_values(bad):
    report = preflight.analyze(bad)
    assert report['status'] == 'REFUSED' and 'SYNTHETIC_SECRET' not in json.dumps(report)


def test_cli_distinct_exit_codes_and_no_connection_options(tmp_path):
    root = Path(__file__).absolute().parents[1]
    spec = tmp_path/'spec.json';snapshot = tmp_path/'snapshot.json'
    spec.write_text(json.dumps(synthetic_spec()));snapshot.write_text(json.dumps(synthetic_catalog()))
    def run(*args):
        return subprocess.run([sys.executable, '-m', 'parkweave.native_run_access_preflight', *args],
            cwd=root, env={'PYTHONPATH': str(root/'src')}, capture_output=True, text=True)
    assert run().returncode == 2
    assert run('--spec', str(spec)).returncode == 3
    assert run('--spec', str(spec), '--snapshot', str(snapshot)).returncode == 0
    missing = synthetic_catalog();missing['triggers'] = {}
    snapshot.write_text(json.dumps(missing))
    assert run('--spec', str(spec), '--snapshot', str(snapshot)).returncode == 5
    missing['schema_version'] = 31;snapshot.write_text(json.dumps(missing))
    assert run('--spec', str(spec), '--snapshot', str(snapshot)).returncode == 4
    rejected = run('--dsn', 'SYNTHETIC_SECRET_MUST_NOT_ECHO')
    assert rejected.returncode == 4 and 'SYNTHETIC_SECRET' not in rejected.stdout+rejected.stderr


def test_declared_installer_role_does_not_substitute_for_actual_operator_evidence():
    catalog = synthetic_catalog();del catalog['roles']['synthetic_installer']
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert check(report, 'installer_role_present')['status'] == 'NOT_CONNECTED'
    assert not report['installation_authorized']


def test_unknown_role_membership_or_excess_details_never_default_to_safe():
    catalog = synthetic_catalog();del catalog['roles']['synthetic_app']['writer_membership']
    assert preflight.analyze(synthetic_spec(catalog), catalog)['status'] == 'REFUSED'
    catalog = synthetic_catalog();del catalog['unneeded_writer_permissions']
    assert preflight.analyze(synthetic_spec(catalog), catalog)['status'] == 'REFUSED'


def test_effective_extra_dml_details_cannot_be_hidden_by_summary_false():
    catalog = synthetic_catalog();catalog['unneeded_writer_permissions'] = ['UPDATE:principals.active']
    catalog['privileges']['writer:unneeded_write'] = False
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert report['status'] == 'REFUSED'
    assert check(report, 'forbidden.writer:unneeded_write')['status'] == 'REFUSED'
    assert report['unneeded_writer_permissions'] == ['UPDATE:principals.active']


class Trace:
    def __init__(self, connection):
        self.connection = connection;self.queries = []
    def __getattr__(self, name):return getattr(self.connection, name)
    def cursor(self, *args, **kwargs):
        cursor = self.connection.cursor(*args, **kwargs);outer = self
        class Cursor:
            def execute(self, query, params=None):
                outer.queries.append(query)
                assert query.lstrip().upper().startswith(('SELECT', 'SET'))
                cursor.execute(query, params)
                return self
            def __getattr__(self, name):return getattr(cursor, name)
        return Cursor()


def owned_spec(fixture):
    _, owner, _, _ = fixture
    with owner.connect() as c:
        db = c.execute("SELECT d.oid,d.datname,pg_get_userbyid(d.datdba) owner,(SELECT system_identifier::text FROM pg_control_system()) system FROM pg_database d WHERE d.datname=current_database()").fetchone()
        catalog = synthetic_catalog();catalog['database'].update(name=db['datname'], oid=db['oid'],
            system_identifier=db['system'], host=c.info.host, port=c.info.port)
        for table in catalog['tables'].values():table['owner'] = db['owner']
        spec = synthetic_spec(catalog);spec['installer_role'] = db['owner']
        spec['policy'].update(application_role='parkweave_app', writer_role=db['owner'])
        return spec


def test_actual_owned_pg_collector_is_readonly_no_ticket_business_reads_or_locks(fixture):
    _, owner, _, _ = fixture;spec = owned_spec(fixture)
    with owner.connect() as c:
        traced = Trace(c)
        snapshot = preflight.collect_owned_catalog(traced, owner._case_fact_fixture_receipt, spec)
        assert c.info.transaction_status == TransactionStatus.IDLE
        settings = c.execute("SELECT current_setting('transaction_read_only') ro,current_setting('search_path') path").fetchone()
        assert settings['ro'] == 'off' and settings['path'] != 'pg_catalog'
    assert traced.queries[0] == 'SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'
    assert not any('FOR UPDATE' in q or 'pg_advisory' in q or 'parkweave_fixture_migration_receipt' in q for q in traced.queries)
    report = preflight.analyze(spec, snapshot)
    assert check(report, 'role.writer')['status'] == 'REFUSED'  # Original fixture owner is not a production writer.
    assert len([r for r in report['changes'] if r['action'] in {'ADD_COLUMN', 'CREATE_FUNCTION', 'CREATE_TRIGGER'}]) == 9
    assert snapshot['schema_version'] == 32 and not snapshot['functions'] and not snapshot['triggers']
    assert not snapshot['privileges']['app:assignment_write']


def install_owned_storage(owner):
    native.install_owned_test_storage(owner, owner._case_fact_fixture_receipt)
    activation.install_owned_test_activation_storage(owner, owner._case_fact_fixture_receipt)


def test_actual_installed_owned_storage_definitions_match_packaged_source(fixture):
    _, owner, _, _ = fixture;install_owned_storage(owner);spec = owned_spec(fixture)
    with owner.connect() as c:snapshot = preflight.collect_owned_catalog(c, owner._case_fact_fixture_receipt, spec)
    report = preflight.analyze(spec, snapshot)
    assert all(row['status'] == 'PASS' for row in report['checks'] if row['check'].startswith(('column.', 'function.', 'trigger.')))
    assert not any(r['action'] in {'ADD_COLUMN', 'CREATE_FUNCTION', 'CREATE_TRIGGER'} for r in report['changes'])
    assert check(report, 'role.writer')['status'] == 'REFUSED' and not report['installation_authorized']
    assert snapshot['unneeded_writer_permissions']  # Owner rights cannot be presented as least privilege.


@pytest.mark.parametrize('change,check_name', [
    ("ALTER TABLE runs ALTER COLUMN native_run_access_protocol SET DEFAULT '{}'::jsonb", 'column.runs.native_run_access_protocol'),
    ('ALTER FUNCTION guard_native_run_access_protocol() STABLE', 'function.guard_native_run_access_protocol'),
    ('ALTER TABLE runs DISABLE TRIGGER native_run_access_append_only', 'trigger.native_run_access_append_only')])
def test_actual_owned_catalog_detects_storage_conflict_without_repair(fixture, change, check_name):
    _, owner, _, _ = fixture;install_owned_storage(owner);spec = owned_spec(fixture)
    with owner.connect() as c:c.execute(change)
    with owner.connect() as c:snapshot = preflight.collect_owned_catalog(c, owner._case_fact_fixture_receipt, spec)
    report = preflight.analyze(spec, snapshot)
    assert check(report, check_name)['status'] == 'REFUSED'
    assert not any(r['action'] in {'ADD_COLUMN', 'CREATE_FUNCTION', 'CREATE_TRIGGER'} for r in report['changes'])


def test_forged_receipt_and_wrong_existing_connection_refused_before_queries(fixture, pg):
    _, owner, _, _ = fixture;spec = owned_spec(fixture)
    with owner.connect() as c:
        traced = Trace(c)
        with pytest.raises(Denied):preflight.collect_owned_catalog(traced, replace(owner._case_fact_fixture_receipt), spec)
        assert not traced.queries
    import psycopg
    with psycopg.connect(pg.get_uri()) as c:
        traced = Trace(c)
        with pytest.raises(Denied):preflight.collect_owned_catalog(traced, owner._case_fact_fixture_receipt, spec)
        assert not traced.queries


def test_actual_existing_system_role_is_unsafe_without_new_grants_or_role_changes(fixture):
    _, owner, _, _ = fixture;spec = owned_spec(fixture)
    spec['policy']['writer_role'] = 'pg_execute_server_program'
    with owner.connect() as c:snapshot = preflight.collect_owned_catalog(c, owner._case_fact_fixture_receipt, spec)
    role = snapshot['roles']['pg_execute_server_program']
    assert not any(role[flag] for flag in ('superuser', 'createdb', 'createrole', 'replication', 'bypass_rls'))
    assert role['dangerous_membership']
    assert check(preflight.analyze(spec, snapshot), 'role.writer')['status'] == 'REFUSED'
