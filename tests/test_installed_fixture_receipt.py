"""Dormant receipt candidate: unit seams + owned Linux TCP PG, NOT native Windows.

No global pg fixture, new role, GRANT, identity, lifecycle, or Windows security
operation. Real database cleanup is limited to our confirmed receipt's exact OID.
"""
from copy import copy, deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import socket
from uuid import uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
import pytest

from parkweave import installed_fixture_receipt as native
from parkweave.store import Denied, Store

ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE = 'host=127.0.0.1 port=5432 user=postgres dbname=postgres sslmode=disable'
TARGET = 'host=127.0.0.1 port=5432 user=postgres dbname=parkweave sslmode=disable'
POISON = 'SYNTHETIC password=secret /private/path'


@pytest.mark.parametrize('which,changed', [
    ('maintenance', {'host': 'remote.invalid'}),
    ('target', {'host': 'localhost'}),
    ('maintenance', {'host': '127.0.0.1,127.0.0.2'}),
    ('target', {'host': '/tmp/socket'}),
    ('target', {'hostaddr': '127.0.0.1'}),
    ('maintenance', {'service': 'hidden'}),
    ('target', {'options': '-c role=postgres'}),
    ('target', {'passfile': '/private/credentials'}),
    ('target', {'dbname': 'other'}),
    ('maintenance', {'dbname': 'parkweave'}),
    ('target', {'port': ''}),
    ('target', {'port': '0'}),
    ('target', {'port': '65536'}),
    ('target', {'port': '5432,5433'}),
    ('target', {'user': ''}),
    ('target', {'user': 'other'}),
    ('target', {'port': '5433'}),
    ('target', {'connect_timeout': '0'}),
    ('target', {'sslmode': 'unknown'}),
    ('target', {'sslmode': 'prefer'}),
    ('target', {'sslmode': 'require'}),
    ('maintenance', {'sslmode': ''}),
])
def test_both_dsns_refused_before_any_connection(monkeypatch, which, changed):
    opened = []
    monkeypatch.setattr(native, '_connect', lambda *a, **k: opened.append((a, k)))
    dsns = {'maintenance': MAINTENANCE, 'target': TARGET}
    dsns[which] = make_conninfo(dsns[which], **changed)
    with pytest.raises(Denied):
        native.create_installed_synthetic_database_receipt(
            dsns['maintenance'], dsns['target'], '/owned/data')
    assert opened == []


@pytest.mark.parametrize('directory', [None, '', 'relative', '../data', '/owned/../data', b'/owned/data', '//remote/share'])
def test_directory_refused_before_any_connection(monkeypatch, directory):
    opened = []
    monkeypatch.setattr(native, '_connect', lambda *a, **k: opened.append((a, k)))
    with pytest.raises(Denied):
        native.create_installed_synthetic_database_receipt(MAINTENANCE, TARGET, directory)
    assert opened == []


def test_libpq_hidden_defaults_refused_without_environment_mutation(monkeypatch):
    poison = {'PGSERVICE': 'unauthorized', 'PGOPTIONS': '-c role=other',
              'PGPASSWORD': POISON, 'PGPASSFILE': '/private/passwords',
              'PGUSER': 'other', 'PGHOSTADDR': 'remote.invalid'}
    for key, value in poison.items():
        monkeypatch.setenv(key, value)
    opened = []
    monkeypatch.setattr(native.psycopg, 'connect', lambda **kw: opened.append(kw))
    with pytest.raises(Denied, match='inherited PostgreSQL configuration refused'):
        native.create_installed_synthetic_database_receipt(MAINTENANCE, TARGET, '/owned/data')
    assert opened == []
    assert {key: os.environ[key] for key in poison} == poison
    for key in poison:
        monkeypatch.delenv(key)
    native._connect(native._dsn(TARGET, 'parkweave'), autocommit=False)
    kw = opened[0]
    assert kw['host'] == kw['hostaddr'] == '127.0.0.1'
    assert kw['port'] == '5432' and kw['user'] == 'postgres' and kw['dbname'] == 'parkweave'
    assert kw['password'] == '' and kw['passfile'] == os.devnull
    assert 'service' not in kw and kw['options'] == '-c lock_timeout=3000 -c statement_timeout=10000'
    assert kw['autocommit'] is False
    assert kw['gssencmode'] == 'disable'
    assert kw['require_auth'] == 'none,password,md5,scram-sha-256'
    native._connect(native._dsn(make_conninfo(TARGET, password='explicit'), 'parkweave'), autocommit=True)
    assert opened[1]['password'] == 'explicit' and opened[1]['sslmode'] == 'disable'


def test_old_libpq_rejected_before_any_connection(monkeypatch):
    opened = []
    monkeypatch.setattr(native.psycopg.pq, 'version', lambda: 160000)
    monkeypatch.setattr(native, '_connect', lambda *a, **k: opened.append((a, k)))
    with pytest.raises(Denied, match='authentication policy unsupported'):
        native.create_installed_synthetic_database_receipt(MAINTENANCE, TARGET, '/owned/data')
    assert opened == []


class _Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _Connection:
    def __init__(self, database, existing=False, create_error=False, after_change=None):
        self.database, self.existing = database, existing
        self.create_error, self.after_change = create_error, after_change
        self.created, self.calls = False, []
        self.autocommit = database == 'postgres'

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, statement, params=None):
        self.calls.append((statement, params))
        if statement == 'CREATE DATABASE parkweave':
            if self.create_error:
                raise psycopg.OperationalError(POISON)
            self.created = True
            return _Result(None)
        return _Result({'oid': 42} if self.created or self.existing else None)


def _metadata(connection):
    result = dict(database_oid=1 if connection.database == 'postgres' else 42,
                  database_name=connection.database, owner_name='postgres',
                  current_name='postgres', session_name='postgres',
                  system_identifier='123', data_directory='/owned/data',
                  postmaster_start=datetime(2026, 1, 1, tzinfo=timezone.utc))
    if connection.after_change:
        result.update(connection.after_change)
    return result


@pytest.mark.parametrize('failure', ['existing', 'create_exception', 'target_unknown', 'owner', 'oid', 'cluster', 'start', 'directory'])
def test_creation_failure_or_unknown_never_issues_or_drops(monkeypatch, failure):
    changes = {'owner': {'owner_name': 'other'}, 'oid': {'database_oid': 43},
               'cluster': {'system_identifier': '456'},
               'start': {'postmaster_start': datetime(2026, 1, 2, tzinfo=timezone.utc)},
               'directory': {'data_directory': '/other/data'}}
    maintenance = _Connection('postgres', existing=failure == 'existing', create_error=failure == 'create_exception')
    target = _Connection('parkweave', after_change=changes.get(failure))
    opened = []

    def connect(parsed, **kwargs):
        opened.append(parsed['dbname'])
        if parsed['dbname'] == 'parkweave' and failure == 'target_unknown':
            raise psycopg.OperationalError(POISON)
        return maintenance if parsed['dbname'] == 'postgres' else target

    monkeypatch.setattr(native, '_connect', connect)
    monkeypatch.setattr(native, '_identity', _metadata)
    before = set(native._issued.keys())
    with pytest.raises(Denied) as denied:
        native.create_installed_synthetic_database_receipt(MAINTENANCE, TARGET, '/owned/data')
    assert POISON not in str(denied.value) and denied.value.__suppress_context__
    assert set(native._issued.keys()) == before
    calls = maintenance.calls + target.calls
    assert all('DROP' not in str(call) and 'GRANT' not in str(call) and 'ROLE' not in str(call) for call in calls)
    assert sum(sql == 'CREATE DATABASE parkweave' for sql, _ in calls) == (0 if failure == 'existing' else 1)
    if failure in ('existing', 'create_exception'):
        assert opened == ['postgres']


@pytest.fixture(scope='module')
def installed_tcp_cluster(tmp_path_factory):
    if os.name == 'nt':
        pytest.skip('NOT_RUN: owned Linux TCP cluster is not installed Windows evidence')
    from pgserver._commands import initdb, pg_ctl
    directory = tmp_path_factory.mktemp('installed-receipt-linux')
    data = directory / 'data'
    data.mkdir(mode=0o700)
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0))
        port = reserved.getsockname()[1]
    maintenance = make_conninfo(host='127.0.0.1', port=port, user='postgres', dbname='postgres', password='', sslmode='disable')
    target = make_conninfo(maintenance, dbname='parkweave')
    try:
        initdb(['--auth=trust', '--encoding=UTF8', '--locale=C', '-U', 'postgres'], pgdata=data)
        pg_ctl(['-w', '-l', str(directory / 'owned-pg.log'), '-o',
                f'-h 127.0.0.1 -p {port} -k "{data}"', 'start'], pgdata=data, timeout=10)
        yield maintenance, target, str(data.resolve())
    finally:
        # A start timeout may occur after PostgreSQL actually started. Stop only
        # this fixture's exact owned data path, never discover/kill processes.
        # Unknown stop retains the data/logs and fails visibly; no recursive
        # delete or generic process cleanup is attempted here.
        if (data / 'postmaster.pid').exists():
            try:
                pg_ctl(['-w', 'stop', '-m', 'fast'], pgdata=data, timeout=10)
            except Exception:
                pytest.fail('owned Linux receipt cluster stop unconfirmed; fixture directory retained', pytrace=False)
            if (data / 'postmaster.pid').exists():
                pytest.fail('owned Linux receipt cluster stop unconfirmed; fixture directory retained', pytrace=False)


@pytest.fixture
def native_database(installed_tcp_cluster):
    maintenance, target, data = installed_tcp_cluster
    receipt = native.create_installed_synthetic_database_receipt(maintenance, target, data)
    try:
        yield receipt, maintenance, target
    finally:
        # No broad/FORCE drop or owner repair. Only our confirmed CREATE's OID.
        with psycopg.connect(maintenance, autocommit=True, row_factory=dict_row,
                             connect_timeout=2, options='-c lock_timeout=1000 -c statement_timeout=5000') as c:
            current = c.execute('SELECT oid FROM pg_database WHERE datname=%s', ('parkweave',)).fetchone()
            assert current and current['oid'] == receipt.database_oid
            c.execute('DROP DATABASE parkweave')


def test_real_inherited_libpq_configuration_refused_before_create(installed_tcp_cluster, monkeypatch):
    maintenance, target, data = installed_tcp_cluster
    poison = {'PGSERVICE': 'missing_service', 'PGOPTIONS': '-c role=unauthorized',
              'PGPASSWORD': POISON, 'PGPASSFILE': '/private/not-read'}
    for name, value in poison.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(Denied, match='inherited PostgreSQL configuration refused') as refused:
        native.create_installed_synthetic_database_receipt(maintenance, target, data)
    assert POISON not in str(refused.value)
    assert {name: os.environ[name] for name in poison} == poison
    for name in poison:
        monkeypatch.delenv(name)
    with psycopg.connect(maintenance) as connection:
        assert connection.execute("SELECT 1 FROM pg_database WHERE datname='parkweave'").fetchone() is None


def test_real_confirmed_create_and_loader_same_transaction(native_database):
    receipt, _, target = native_database
    assert type(receipt) is native.NativeDatabaseCreationEvidence
    with pytest.raises(FrozenInstanceError):
        receipt.database_oid = 1
    owner = Store(target)
    owner._case_fact_fixture_receipt = receipt
    owner.migrate()
    with owner.connect() as c:
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 25
        assert c.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') t").fetchone()['t'] is None


def test_existing_schema24_never_receives_new_receipt_or_changes(native_database):
    receipt, maintenance, target = native_database
    with Store(target).connect() as c:
        c.execute((ROOT / 'src/parkweave/schema.sql').read_text())
        for version in range(2, 25):
            c.execute((ROOT / f'src/parkweave/migration-{version:03d}.sql').read_text())
    before = set(native._issued.keys())
    with pytest.raises(Denied, match='target already exists'):
        native.create_installed_synthetic_database_receipt(maintenance, target, receipt.data_directory)
    with pytest.raises(Denied, match='isolated database creation receipt required'):
        Store(target).migrate()  # Existing schema24 cannot acquire an implicit receipt.
    calls = []

    class ArbitraryMethodObject:
        def authorize_migration(self, connection):
            calls.append(connection)

    forged_owner = Store(target)
    forged_owner._case_fact_fixture_receipt = ArbitraryMethodObject()
    with pytest.raises(Denied, match='issued .* creation evidence required'):
        forged_owner.migrate()
    assert calls == []
    with Store(target).connect() as c:
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 24
        assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='preparations' AND column_name='fact_clarifications'").fetchone()
    assert set(native._issued.keys()) == before


@pytest.mark.parametrize('forgery', ['copy', 'deepcopy', 'manual', 'subtype', 'changed', 'pid'])
def test_copied_forged_subtyped_or_other_process_receipt_refused(native_database, monkeypatch, forgery):
    receipt, _, target = native_database
    if forgery == 'copy':
        invalid = copy(receipt)
    elif forgery == 'deepcopy':
        invalid = deepcopy(receipt)
    elif forgery == 'manual':
        invalid = native.NativeDatabaseCreationEvidence(**vars(receipt))
    elif forgery == 'subtype':
        class Subtype(native.NativeDatabaseCreationEvidence):
            pass
        invalid = Subtype(**vars(receipt))
    elif forgery == 'changed':
        invalid = replace(receipt, database_nonce=uuid4())
    else:
        invalid = receipt
        monkeypatch.setattr(native.os, 'getpid', lambda: receipt.issuer_pid + 1)
    with Store(target).connect() as c:
        with pytest.raises(Denied, match='issued installed database'):
            invalid.authorize_migration(c)
        assert c.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') t").fetchone()['t'] is None


@pytest.mark.parametrize('field', ['database_oid', 'database_name', 'system_identifier', 'postmaster_start', 'data_directory', 'owner_name', 'current_name', 'session_name'])
def test_live_binding_mismatch_never_issues_ticket(native_database, monkeypatch, field):
    receipt, _, target = native_database
    real_identity = native._identity

    def changed(connection):
        identity = real_identity(connection)
        identity[field] = (identity[field] + 1 if field == 'database_oid' else
                           identity[field] + timedelta(seconds=1) if field == 'postmaster_start' else 'changed')
        return identity

    monkeypatch.setattr(native, '_identity', changed)
    with Store(target).connect() as c:
        with pytest.raises(Denied, match='migration binding refused'):
            receipt.authorize_migration(c)
        assert c.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') t").fetchone()['t'] is None


def test_real_foreign_database_and_autocommit_refused(native_database):
    receipt, maintenance, target = native_database
    with psycopg.connect(target, autocommit=True) as c:
        with pytest.raises(Denied, match='explicit owner migration transaction'):
            receipt.authorize_migration(c)
    with psycopg.connect(maintenance) as c:
        with pytest.raises(Denied, match='migration binding refused'):
            receipt.authorize_migration(c)


def test_real_owned_cluster_restart_invalidates_receipt(native_database, installed_tcp_cluster):
    from pgserver._commands import pg_ctl
    receipt, _, target = native_database
    _, _, data = installed_tcp_cluster
    # Exact fixture-owned Linux server only; no installed/native action.
    pg_ctl(['-w', 'restart', '-m', 'fast'], pgdata=Path(data), timeout=10)
    with Store(target).connect() as c:
        with pytest.raises(Denied, match='migration binding refused'):
            receipt.authorize_migration(c)
        assert c.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') t").fetchone()['t'] is None


@pytest.mark.parametrize('boundary', ['commit', 'rollback'])
def test_real_ticket_removed_and_new_transaction_rebinds(native_database, boundary):
    receipt, _, target = native_database
    with Store(target).connect() as c:
        receipt.authorize_migration(c)
        old = c.execute('SELECT backend_pid,transaction_id FROM pg_temp.parkweave_fixture_migration_receipt').fetchone()
        assert old['backend_pid'] == c.execute('SELECT pg_backend_pid() p').fetchone()['p']
        getattr(c, boundary)()
        assert c.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') t").fetchone()['t'] is None
        receipt.authorize_migration(c)
        new = c.execute('SELECT backend_pid,transaction_id FROM pg_temp.parkweave_fixture_migration_receipt').fetchone()
        assert old['backend_pid'] == new['backend_pid'] and old['transaction_id'] != new['transaction_id']
    with Store(target).connect() as other:
        assert other.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') t").fetchone()['t'] is None


@pytest.mark.parametrize('field', ['database_oid', 'database_name', 'owner_name', 'system_identifier', 'data_directory', 'postmaster_start', 'backend_pid', 'transaction_id'])
def test_real_sql025_rejects_changed_ticket_and_rolls_back(native_database, field):
    receipt, _, target = native_database
    owner = Store(target)
    owner._case_fact_fixture_receipt = receipt
    owner.migrate()
    mutations = {'database_oid': 'database_oid=0', 'database_name': "database_name='other'",
                 'owner_name': "owner_name='other'", 'system_identifier': "system_identifier='other'",
                 'data_directory': "data_directory='/other'", 'postmaster_start': "postmaster_start=postmaster_start+interval '1 second'",
                 'backend_pid': 'backend_pid=0', 'transaction_id': 'transaction_id=0'}
    with pytest.raises(psycopg.errors.RaiseException, match='does not match'):
        with owner.connect() as c:
            receipt.authorize_migration(c)
            c.execute('UPDATE pg_temp.parkweave_fixture_migration_receipt SET ' + mutations[field])
            c.execute((ROOT / 'src/parkweave/migration-025.sql').read_text())
    with owner.connect() as c:
        assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 25
        assert c.execute("SELECT to_regclass('pg_temp.parkweave_fixture_migration_receipt') t").fetchone()['t'] is None
