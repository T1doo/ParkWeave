"""Installed-cluster SYNTHETIC creation receipt and paused Setup Store wiring.

Only this function's confirmed CREATE DATABASE issues a process-local receipt.
It never discovers credentials, creates roles/grants, deletes a database, or
establishes Windows file ownership/ACL authority. This v1 explicitly supports
loopback sslmode=disable and trust/password/MD5/SCRAM auth only, with libpq 17+;
TLS, GSS/SSPI/OAuth and implicit credential discovery are outside its contract.
Linux tests are not native installed-Windows evidence. A privileged DDL owner
is not a sandbox adversary.
"""
from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import PurePosixPath, PureWindowsPath
from uuid import UUID, uuid4
from weakref import WeakValueDictionary

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from . import case_fact_clarifications as facts
from .store import Denied, Store

_issued = WeakValueDictionary()
_ALLOWED_DSN_FIELDS = frozenset({
    'host', 'port', 'user', 'dbname', 'password', 'connect_timeout', 'sslmode',
})


def _dsn(value, database):
    try:
        if not isinstance(value, str) or not value:
            raise ValueError
        parsed = conninfo_to_dict(value)
        if (set(parsed) - _ALLOWED_DSN_FIELDS or
                parsed.get('dbname') != database or
                parsed.get('host') not in ('127.0.0.1', '::1') or
                not parsed.get('user') or
                not parsed.get('port', '').isascii() or
                not parsed.get('port', '').isdigit() or
                not 1 <= int(parsed['port']) <= 65535):
            raise ValueError
        if 'connect_timeout' in parsed and (
                not parsed['connect_timeout'].isascii() or
                not parsed['connect_timeout'].isdigit() or
                not 1 <= int(parsed['connect_timeout']) <= 10):
            raise ValueError
        if parsed.get('sslmode') != 'disable':
            raise ValueError
        return parsed
    except Exception:
        raise Denied('installed receipt explicit loopback DSN refused') from None


def _directory(value):
    try:
        path = os.fspath(value)
        if not isinstance(path, str) or not path or '\x00' in path:
            raise ValueError
        posix, windows = PurePosixPath(path), PureWindowsPath(path)
        if (not (posix.is_absolute() or windows.is_absolute()) or
                path.startswith(('\\\\', '//')) or
                '..' in posix.parts or '..' in windows.parts):
            raise ValueError
        return path
    except Exception:
        raise Denied('installed receipt explicit data directory refused') from None


def refuse_inherited_configuration():
    if any(name.upper().startswith('PG') for name in os.environ):
        raise Denied('installed receipt inherited PostgreSQL configuration refused')


def _connect(parsed, *, autocommit):
    # No reliance on empty kwargs suppressing libpq environment defaults.
    # Inherited PG* configuration was refused before any connection.
    refuse_inherited_configuration()
    options = dict(parsed)
    options.update(hostaddr=parsed['host'], password=parsed.get('password', ''),
                   passfile=os.devnull,
                   options='-c lock_timeout=3000 -c statement_timeout=10000',
                   connect_timeout=parsed.get('connect_timeout', '2'),
                   sslmode=parsed['sslmode'], gssencmode='disable',
                   require_auth='none,password,md5,scram-sha-256')
    return psycopg.connect(**options, autocommit=autocommit, row_factory=dict_row)


def _identity(connection):
    row = facts._migration_identity(connection)
    if (not row or type(row['database_oid']) is not int or row['database_oid'] <= 0 or
            not isinstance(row['system_identifier'], str) or not row['system_identifier'] or
            not isinstance(row['postmaster_start'], datetime) or
            not row['postmaster_start'].tzinfo):
        raise Denied('installed database creation identity refused')
    return row


def _same_cluster(reference, actual):
    return all(actual[key] == reference[key] for key in (
        'system_identifier', 'data_directory', 'postmaster_start',
        'current_name', 'session_name',
    ))


@dataclass(frozen=True, repr=False)
class NativeDatabaseCreationEvidence:
    """Exact issued live object; constructed or copied objects have no authority."""
    database_oid: int
    database_name: str
    owner_name: str
    system_identifier: str
    data_directory: str
    postmaster_start: datetime
    cluster_nonce: UUID
    database_nonce: UUID
    issuer_pid: int

    def authorize_migration(self, connection):
        if (type(self) is not NativeDatabaseCreationEvidence or
                self.issuer_pid != os.getpid() or
                _issued.get(self.database_nonce) is not self):
            raise Denied('issued installed database creation evidence required')
        if connection.autocommit:
            raise Denied('explicit owner migration transaction required')
        try:
            current = _identity(connection)
            if (current['database_name'] != self.database_name or
                    current['database_oid'] != self.database_oid or
                    current['system_identifier'] != self.system_identifier or
                    current['data_directory'] != self.data_directory or
                    current['postmaster_start'] != self.postmaster_start or
                    current['owner_name'] != self.owner_name or
                    current['current_name'] != self.owner_name or
                    current['session_name'] != self.owner_name):
                raise ValueError
            facts._issue_migration_ticket(
                connection, database_oid=self.database_oid,
                database_name=self.database_name, owner_name=self.owner_name,
                system_identifier=self.system_identifier,
                data_directory=self.data_directory,
                postmaster_start=self.postmaster_start,
                cluster_nonce=self.cluster_nonce, database_nonce=self.database_nonce,
            )
        except Exception:
            raise Denied('installed creation receipt migration binding refused') from None


def create_installed_synthetic_database_receipt(
        maintenance_dsn, target_owner_dsn, expected_data_directory, *, application_dsn=None):
    """Explicit new parkweave CREATE only; no repair/retry/drop or default hook.

    BOTH DSNs are validated before any connection. Caller must already have
    authority to use these explicit credentials and create this synthetic DB.
    A CREATE exception or subsequent mismatch issues nothing, even if the
    database may now exist. Preserve that result for independent review.
    Fixed client session timeouts bound issuer queries/CREATE only; they do not
    claim to bound the existing Store loader's complete migration transaction.
    """
    maintenance = _dsn(maintenance_dsn, 'postgres')
    target = _dsn(target_owner_dsn, 'parkweave')
    application = _dsn(application_dsn, 'parkweave') if application_dsn is not None else None
    directory = _directory(expected_data_directory)
    refuse_inherited_configuration()
    if psycopg.pq.version() < 170000:
        raise Denied('installed receipt explicit authentication policy unsupported')
    if any(maintenance[key] != target[key] for key in ('host', 'port', 'user')):
        raise Denied('installed receipt explicit connection pair refused')
    if application is not None and (
            application['user'] != 'parkweave_app' or
            any(application[key] != target[key] for key in ('host', 'port'))):
        raise Denied('installed receipt application connection pair refused')
    try:
        with _connect(maintenance, autocommit=True) as connection:
            before = _identity(connection)
            if (before['database_name'] != 'postgres' or
                    before['data_directory'] != directory or
                    before['current_name'] != maintenance['user'] or
                    before['session_name'] != maintenance['user'] or
                    before['owner_name'] != maintenance['user']):
                raise ValueError
            if connection.execute(
                    'SELECT oid FROM pg_database WHERE datname=%s', ('parkweave',)).fetchone():
                raise Denied('installed synthetic target already exists')
            if application is not None:
                role = connection.execute(
                    'SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolcanlogin FROM pg_roles WHERE rolname=%s',
                    ('parkweave_app',)).fetchone()
                if (not role or role['rolname'] != 'parkweave_app' or
                        role.get('rolcanlogin') is not True or
                        any(role[key] is not False for key in ('rolsuper', 'rolcreatedb', 'rolcreaterole'))):
                    raise Denied('installed receipt application role refused')
            connection.execute('CREATE DATABASE parkweave')
            # Read the created OID on the original maintenance connection and
            # compare again at the target. Privileged external DDL remains an
            # explicitly unsupported adversary, not an implied name-level CAS.
            created = connection.execute(
                'SELECT oid FROM pg_database WHERE datname=%s', ('parkweave',)).fetchone()
            if (not created or type(created['oid']) is not int or created['oid'] <= 0 or
                    not _same_cluster(before, _identity(connection))):
                raise ValueError
        with _connect(target, autocommit=False) as connection:
            after = _identity(connection)
            if (not _same_cluster(before, after) or
                    after['database_name'] != 'parkweave' or
                    after['database_oid'] != created['oid'] or
                    after['owner_name'] != maintenance['user']):
                raise ValueError
    except Denied as error:
        if str(error) == 'installed synthetic target already exists':
            raise Denied('installed synthetic target already exists') from None
        raise Denied('installed synthetic creation unconfirmed; no receipt issued') from None
    except Exception:
        raise Denied('installed synthetic creation unconfirmed; no receipt issued') from None
    result = NativeDatabaseCreationEvidence(
        after['database_oid'], 'parkweave', after['owner_name'],
        after['system_identifier'], after['data_directory'], after['postmaster_start'],
        uuid4(), uuid4(), os.getpid(),
    )
    _issued[result.database_nonce] = result
    return result


class _InstalledSyntheticSetupStore(Store):
    """Only the issuer factory builds this process-local owner Store.

    Owner connections retain the issuer's explicit transport/authentication and
    bind the issued object before returning a connection to any schema/role DDL.
    The application connector is used only for Setup's read-only role check.
    """

    def __init__(self, owner_dsn, application_dsn, receipt):
        super().__init__(owner_dsn)
        self._owner_connection = _dsn(owner_dsn, 'parkweave')
        self._application_connection = _dsn(application_dsn, 'parkweave')
        self._case_fact_fixture_receipt = receipt

    def connect(self):
        connection = _connect(self._owner_connection, autocommit=False)
        try:
            NativeDatabaseCreationEvidence.authorize_migration(self._case_fact_fixture_receipt, connection)
        except BaseException:
            connection.close()
            raise
        return connection

    def connect_application(self):
        return _connect(self._application_connection, autocommit=False)


def create_installed_synthetic_store(maintenance_dsn, owner_dsn, application_dsn, expected_data_directory):
    """One confirmed CREATE, receipt and Store in this process; no adoption path.

    All three DSNs and the application role are checked before CREATE. Failed or
    unknown creation remains a refusal; the caller must preserve the database.
    No receipt serialization, subprocess handoff, retry, repair or DROP exists.
    """
    # Setup's later lifecycle gate accepts IPv4 loopback/localhost, while the
    # standalone issuer accepts IPv4/IPv6 literals. Their intersection is only
    # 127.0.0.1. Check it before CREATE, never by expanding either contract.
    parsed = (_dsn(maintenance_dsn, 'postgres'), _dsn(owner_dsn, 'parkweave'),
              _dsn(application_dsn, 'parkweave'))
    if any(info['host'] != '127.0.0.1' for info in parsed):
        raise Denied('installed Setup host refused before creation')
    receipt = create_installed_synthetic_database_receipt(
        maintenance_dsn, owner_dsn, expected_data_directory, application_dsn=application_dsn)
    return _InstalledSyntheticSetupStore(owner_dsn, application_dsn, receipt)
