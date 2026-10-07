"""Dormant installed-cluster SYNTHETIC creation receipt; no lifecycle wiring.

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
from .store import Denied

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


def _connect(parsed, *, autocommit):
    # No reliance on empty kwargs suppressing libpq environment defaults.
    # Inherited PG* configuration was refused before any connection.
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
        maintenance_dsn, target_owner_dsn, expected_data_directory):
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
    directory = _directory(expected_data_directory)
    if any(name.upper().startswith('PG') for name in os.environ):
        raise Denied('installed receipt inherited PostgreSQL configuration refused')
    if psycopg.pq.version() < 170000:
        raise Denied('installed receipt explicit authentication policy unsupported')
    if any(maintenance[key] != target[key] for key in ('host', 'port', 'user')):
        raise Denied('installed receipt explicit connection pair refused')
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
