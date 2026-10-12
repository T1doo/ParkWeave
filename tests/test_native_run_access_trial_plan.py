"""Pure supplied inputs only; never use original PG fixtures or reference flow."""
from copy import deepcopy
import json

import pytest

from parkweave import native_run_access_trial_plan as trial
from test_native_run_access_preflight import synthetic_catalog, synthetic_spec


def inputs():
    catalog = synthetic_catalog()
    catalog['database'].update(name='fixture_'+'a'*32, host='127.0.0.1')
    spec = synthetic_spec(catalog)
    return spec, catalog, dict(platform='linux', trial_root='/tmp/parkweave-trial-'+'b'*32,
        source_sha='c'*40, identities='EXISTING_DISTINCT_IDENTITIES')


def test_complete_plan_stays_unapproved_with_no_repurposed_reference_command():
    spec, catalog, host = inputs();result = trial.prepare(spec, catalog, host)
    assert result['status'] == 'APPROVAL_REQUIRED'
    assert result['writer_argv'] is None and result['writer_runtime'] == 'NOT_IMPLEMENTED'
    assert result['actual_run'] == 'NOT_RUN'
    assert all(result[key] is False for key in ('launch_authorized', 'installation_authorized', 'activation_enabled', 'production_connected'))
    assert len(result['pending_actions']) == 5
    assert not any(p['action'] == 'LOCK_UPDATE' for p in result['writer_permission_requirements'])
    assert not any(p['object'] == 'authorization_audit' for p in result['writer_permission_requirements'])
    assert result['lock_requirement']['technical_update_column'] == 'revision'
    scope = result['declared_case_scope']
    assert scope['source_sha256'] == trial._digest(spec['policy']['source'])
    assert scope['public_source']['case_id'] == spec['policy']['source']['case_id']


def test_preflight_missing_unknown_and_conflicts_are_retained():
    assert trial.prepare()['status'] == 'MISSING_CONFIG'
    spec, catalog, host = inputs()
    assert trial.prepare(spec, None, host)['status'] == 'NOT_CONNECTED'
    catalog['privileges']['app:assignment_write'] = True
    assert trial.prepare(spec, catalog, host)['status'] == 'REFUSED'


@pytest.mark.parametrize('change', [dict(platform='win32'), dict(identities='CREATE_NEW_USERS'),
    dict(trial_root='/workspace/shared'), dict(trial_root='/tmp/parkweave-trial-'+'b'*32+'/../shared'),
    dict(approved=True), dict(execute=True), dict(writer_dsn='SYNTHETIC_PRIVATE_VALUE')])
def test_direction_or_input_file_cannot_grant_execution(change):
    spec, catalog, host = inputs();host.update(change)
    result = trial.prepare(spec, catalog, host)
    assert result['status'] == 'REFUSED'
    assert not result['launch_authorized'] and 'SYNTHETIC_PRIVATE_VALUE' not in json.dumps(result)


@pytest.mark.parametrize('change', [dict(permission_strategy='NARROW_FUNCTIONS'), dict(transport='WINDOWS_NATIVE'),
                                   dict(api_uid=0), dict(writer_uid=0), dict(writer_uid=10001)])
def test_only_declared_nonroot_distinct_linux_direct_dml_route(change):
    spec, catalog, host = inputs();spec.update(change)
    assert trial.prepare(spec, catalog, host)['status'] == 'REFUSED'


@pytest.mark.parametrize('change', [dict(database_name='production'), dict(database_host='10.0.0.1'),
                                   dict(database_host='/tmp/unrelated')])
def test_only_exact_new_local_uuid_target_declaration(change):
    spec, catalog, host = inputs();spec['policy'].update(change)
    catalog['database'].update({k.removeprefix('database_'): v for k, v in change.items()})
    assert trial.prepare(spec, catalog, host)['status'] == 'REFUSED'


@pytest.mark.parametrize('suffix', ['/../outside', '/sockets/../../outside', '/./postgres',
                                  '//postgres', '/postgres/', '/postgres\x00', 'extra/postgres'])
def test_database_socket_declaration_requires_canonical_contained_path(suffix):
    spec, catalog, host = inputs()
    value = host['trial_root']+suffix
    spec['policy']['database_host'] = catalog['database']['host'] = value
    assert trial.prepare(spec, catalog, host)['status'] == 'REFUSED'


def test_canonical_contained_database_socket_is_only_an_unverified_declaration():
    spec, catalog, host = inputs()
    value = host['trial_root']+'/postgres'
    spec['policy']['database_host'] = catalog['database']['host'] = value
    result = trial.prepare(spec, catalog, host)
    assert result['status'] == 'APPROVAL_REQUIRED'
    assert result['actual_run'] == 'NOT_RUN' and not result['launch_authorized']


@pytest.mark.parametrize('field', ['owner_id', 'approver_id', 'beneficiary_id',
                                  'park_id', 'org_id', 'preparation_state'])
def test_free_text_scope_is_bound_by_digest_without_public_echo(field):
    spec, catalog, host = inputs()
    before = trial.prepare(spec, catalog, host)
    sentinel = 'Bearer SYNTHETIC_PRIVATE_SENTINEL_NOT_A_REAL_CREDENTIAL'
    if field in ('owner_id', 'approver_id', 'beneficiary_id'):
        spec['policy'][field] = sentinel
    if field not in ('approver_id', 'beneficiary_id'):
        spec['policy']['source'][field] = sentinel
    result = trial.prepare(spec, catalog, host)
    assert result['status'] == 'APPROVAL_REQUIRED'
    assert sentinel not in json.dumps(result)
    assert result['plan_digest'] != before['plan_digest']
    assert result['declared_case_scope'] != before['declared_case_scope']


def test_expired_interval_cannot_be_renewed_by_planner():
    spec, catalog, host = inputs()
    spec['policy'].update(valid_from='2026-01-01T00:00:00+00:00', valid_until='2026-01-01T00:30:00+00:00')
    assert trial.prepare(spec, catalog, host)['status'] == 'REFUSED'


def test_plan_digest_binds_inputs_without_touching_source_or_private_references(monkeypatch):
    spec, catalog, host = inputs();before = deepcopy((spec, catalog, host))
    import os, socket, subprocess, psycopg
    def forbidden(*args, **kwargs):pytest.fail('sensitive operation must not run')
    for obj, name in ((os, 'chmod'), (os, 'chown'), (os, 'umask'), (subprocess, 'Popen'),
                      (psycopg, 'connect'), (socket.socket, 'bind'), (socket.socket, 'connect')):
        monkeypatch.setattr(obj, name, forbidden)
    result = trial.prepare(spec, catalog, host)
    assert (spec, catalog, host) == before
    assert trial.prepare(spec, catalog, host)['plan_digest'] == result['plan_digest']
    spec['policy']['source']['preparation_revision'] += 1
    assert trial.prepare(spec, catalog, host)['plan_digest'] != result['plan_digest']
    assert 'SYNTHETIC_REFERENCE_NOT_KEY' not in json.dumps(result)


def test_cli_is_plan_only_and_hides_rejected_argument_values(capsys):
    assert trial.main([]) == 2
    assert json.loads(capsys.readouterr().out)['actual_run'] == 'NOT_RUN'
    with pytest.raises(SystemExit) as error:trial.main(['--execute', 'SYNTHETIC_PRIVATE_VALUE'])
    assert error.value.code == 4
    assert 'SYNTHETIC_PRIVATE_VALUE' not in capsys.readouterr().err
