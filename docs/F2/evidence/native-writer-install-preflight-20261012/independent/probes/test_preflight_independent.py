"""Independent preflight counterexamples. Original owned fixture setup only."""
import importlib.util
from pathlib import Path
import pytest
from psycopg.pq import TransactionStatus
from parkweave import native_run_access_preflight as preflight
from parkweave.store import Denied
from test_native_run_access_preflight import synthetic_catalog, synthetic_spec, owned_spec, Trace, check

ROOT = Path('/workspace/ParkWeave')
_loader = importlib.util.spec_from_file_location('_preflight_original_conftest', ROOT/'tests/conftest.py')
_fixture_module = importlib.util.module_from_spec(_loader)
_loader.loader.exec_module(_fixture_module)
pg = _fixture_module.pg
fixture = _fixture_module.fixture


def test_explicit_excess_dml_cannot_be_overridden_by_false_summary():
    catalog = synthetic_catalog()
    catalog['unneeded_writer_permissions'] = ['INSERT:principals.id']
    assert catalog['privileges']['writer:unneeded_write'] is False
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert report['status'] == 'REFUSED', report


def test_missing_writer_membership_is_unknown_not_false():
    catalog = synthetic_catalog()
    del catalog['roles']['synthetic_app']['writer_membership']
    report = preflight.analyze(synthetic_spec(catalog), catalog)
    assert report['status'] == 'REFUSED', report


def test_existing_predefined_server_program_role_is_not_restricted(fixture):
    _, owner, _, _ = fixture
    spec = owned_spec(fixture)
    spec['policy']['writer_role'] = 'pg_execute_server_program'
    with owner.connect() as connection:
        snapshot = preflight.collect_owned_catalog(connection, owner._case_fact_fixture_receipt, spec)
    report = preflight.analyze(spec, snapshot)
    role = snapshot['roles']['pg_execute_server_program']
    assert not any(role[key] for key in ('superuser', 'createdb', 'createrole', 'replication', 'bypass_rls'))
    assert check(report, 'role.writer')['status'] == 'REFUSED', {'role': role, 'check': check(report, 'role.writer')}


def test_pending_caller_transaction_is_refused_without_sql_or_rollback(fixture):
    _, owner, _, _ = fixture
    spec = owned_spec(fixture)
    with owner.connect() as connection:
        connection.execute('SELECT 1')
        assert connection.info.transaction_status == TransactionStatus.INTRANS
        traced = Trace(connection)
        with pytest.raises(Denied):
            preflight.collect_owned_catalog(traced, owner._case_fact_fixture_receipt, spec)
        assert not traced.queries
        assert connection.info.transaction_status == TransactionStatus.INTRANS
