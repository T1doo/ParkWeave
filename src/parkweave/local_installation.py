"""Persistent Linux SYNTHETIC installation with its own live CREATE issuer.

This is independent of the ephemeral fixture issuer and Windows owner gate.
Only a newly and exclusively created directory/cluster/database can issue a
receipt. Reopen has no receipt, initdb, migration, seed or permission repair.
The journal is a refusal/retry guard, never database-creation authority.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
from uuid import uuid4
import weakref

if sys.platform == 'linux':
    import fcntl
else:
    fcntl = None

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from .process_env import minimal_environment
from .store import Denied, Store
from . import case_fact_clarifications as facts

STATE = '.local-installation.json'
LOCK = '.local-installation.lock'
SCHEMA = 'parkweave-local-installation/1'
_leases = weakref.WeakKeyDictionary()
_receipts = weakref.WeakKeyDictionary()
_starts = weakref.WeakKeyDictionary()
_initializations = weakref.WeakKeyDictionary()


def need(value):
    if not value:
        raise Denied('persistent local installation binding refused')


def _identity(info):
    return info.st_dev, info.st_ino


def _private(info, *, directory):
    need((stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
         and info.st_uid == os.geteuid() and not info.st_mode & 0o077
         and (directory or info.st_nlink == 1))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def _pg_bin(name):
    return str(importlib.metadata.distribution('pgserver').locate_file('pgserver/pginstall/bin/' + name))


def private_parent(value):
    path = Path(value).absolute()
    need(sys.platform == 'linux' and os.geteuid() != 0 and path.resolve() == path and path.is_dir())
    _private(path.stat(follow_symlinks=False), directory=True)
    return path


class PersistentInstallation:
    """One held installation entry and only its exact owned postmaster child."""
    def __reduce__(self):
        raise TypeError('local installation authority cannot be serialized')

    @classmethod
    def create_new(cls, parent):
        parent = private_parent(parent)
        path = parent / ('pw-' + uuid4().hex)
        need(len(os.fsencode(path / 'socket/.s.PGSQL.5432')) <= 107)
        path.mkdir(mode=0o700)  # Exclusive; never open/adopt an existing root.
        lease = cls._acquire(path, fresh=True)
        try:
            for name in ('socket', 'logs', 'downloads'):
                (path / name).mkdir(mode=0o700)
            empty = os.open('.libpq-no-passwords', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=lease.root)
            try:
                os.fsync(empty)
            finally:
                os.close(empty)
            lease._publish('INSTALLING')
            return lease
        except BaseException:
            lease.close()
            raise

    @classmethod
    def open_existing(cls, value):
        lease = cls._acquire(Path(value).absolute(), fresh=False)
        try:
            need(lease.record['phase'] in ('READY_STOPPED','RELEASE_PENDING'))
            need(not (lease.path / 'data' / 'postmaster.pid').exists())
            if lease.record['phase'] == 'RELEASE_PENDING':
                lease._publish('READY_STOPPED')  # exact new exclusive handoff
            return lease
        except BaseException:
            lease.close()
            raise

    @classmethod
    def _acquire(cls, path, *, fresh):
        need(sys.platform == 'linux' and os.geteuid() != 0 and path.resolve() == path)
        parent = private_parent(path.parent)
        root = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        lock = None
        try:
            _private(os.fstat(root), directory=True)
            lock = os.open(LOCK, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC
                           | (os.O_CREAT | os.O_EXCL if fresh else 0), 0o600, dir_fd=root)
            _private(os.fstat(lock), directory=False)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lease = object.__new__(cls)
            lease.path, lease.root, lease.lock = path, root, lock
            lease.root_id, lease.lock_id = _identity(os.fstat(root)), _identity(os.fstat(lock))
            lease.parent_id = _identity(parent.stat(follow_symlinks=False))
            lease.fresh, lease.closed, lease.failed = fresh, False, False
            lease.process = lease.process_birth = None
            lease.created_database = lease.initialized = False
            lease.record = None
            if not fresh:
                lease.record = lease._read_state()
            lease.instance = str(uuid4()) if fresh else lease.record['instance']
            _leases[lease] = (root, lock, lease.instance, os.getpid())
            lease.verify()
            return lease
        except BaseException:
            if lock is not None:
                os.close(lock)
            os.close(root)
            raise

    def verify(self):
        need(not self.closed and not self.failed and
             _leases.get(self) == (self.root, self.lock, self.instance, os.getpid()))
        for info, expected, directory in ((os.fstat(self.root), self.root_id, True),
                (self.path.stat(follow_symlinks=False), self.root_id, True),
                (os.fstat(self.lock), self.lock_id, False),
                ((self.path / LOCK).stat(follow_symlinks=False), self.lock_id, False)):
            _private(info, directory=directory)
            need(_identity(info) == expected)
        need(self.path.resolve() == self.path and _identity(self.path.parent.stat()) == self.parent_id)
        if self.record is not None:
            need(self._read_state() == self.record)

    def _read_state(self):
        fd = os.open(STATE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=self.root)
        try:
            info = os.fstat(fd)
            _private(info, directory=False)
            need(0 < info.st_size <= 4096)
            raw = os.read(fd, 4097)
            need(len(raw) == info.st_size)
        finally:
            os.close(fd)
        value = json.loads(raw)
        need(set(value) == {'schema','instance','root','parent','lock','phase'}
             and value['schema'] == SCHEMA and value['root'] == list(self.root_id)
             and value['parent'] == list(self.parent_id) and value['lock'] == list(self.lock_id)
             and value['phase'] in ('INSTALLING','RUNNING','READY_STOPPED','RELEASE_PENDING','UNKNOWN'))
        from uuid import UUID
        need(str(UUID(value['instance'])) == value['instance'])
        return value

    def _publish(self, phase):
        self.verify()
        value = dict(schema=SCHEMA, instance=self.instance, root=list(self.root_id),
                     parent=list(self.parent_id), lock=list(self.lock_id), phase=phase)
        name = '.local-state-new-' + str(uuid4())
        try:
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.root)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(_canonical(value))
                stream.flush()
                os.fsync(stream.fileno())
            self.verify()
            # The exact root/lock and previous full record are still held.
            os.replace(name, STATE, src_dir_fd=self.root, dst_dir_fd=self.root)
            os.fsync(self.root)
            parent_fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                need(_identity(os.fstat(parent_fd)) == self.parent_id)
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            self.record = value
            self.verify()
        except BaseException:
            self.failed = True  # Never retry an uncertain state publication.
            raise

    def initialize(self):
        self.verify()
        need(self.fresh and not self.initialized and self.record['phase'] == 'INSTALLING'
             and not (self.path / 'data').exists())
        self.initialized = True  # consume before the first external action
        with (self.path / 'logs/initdb.log').open('x') as log:
            subprocess.run([_pg_bin('initdb'), '-D', str(self.path / 'data'), '-U', 'postgres',
                '--auth-local=trust', '--auth-host=reject', '--encoding=UTF8', '--no-locale'],
                env=minimal_environment(os.environ), stdout=log, stderr=log, timeout=30, check=True)
        self.verify()
        _initializations[self] = _identity((self.path / 'data').stat())

    def dsn(self, *, maintenance=False, application=False):
        self.verify()
        return make_conninfo(host=str(self.path / 'socket'), port=5432,
            dbname='postgres' if maintenance else 'parkweave',
            user='parkweave_app' if application else 'postgres', connect_timeout=2)

    def _birth(self):
        need(self.process is not None and self.process.poll() is None)
        raw = Path('/proc', str(self.process.pid), 'stat').read_text()
        fields = raw[raw.rindex(')')+2:].split()
        need(fields[0] not in ('Z','X'))
        return self.process.pid, int(fields[19])

    def verify_process(self):
        self.verify()
        need(type(self.process) is subprocess.Popen and self.process_birth is not None
             and _starts.get(self) == (self.process, self.process_birth)
             and self._birth() == self.process_birth)
        data = self.path / 'data'
        need(data.resolve() == data and data.is_dir())
        _private(data.stat(), directory=True)

    def verify_connection(self, connection):
        self.verify_process()
        # PostgreSQL's listening socket is created by this exact postmaster;
        # SO_PEERCRED binds the connected socket without trusting a SQL PID.
        borrowed = socket.socket(fileno=connection.pgconn.socket)
        try:
            need(borrowed.family == socket.AF_UNIX)
            pid, uid, _gid = struct.unpack('3i', borrowed.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
            need((pid, uid) == (self.process.pid, os.geteuid()))
        finally:
            borrowed.detach()  # libpq retains sole close ownership
        self.verify_process()

    def connect(self, *, maintenance=False, autocommit=False):
        self.verify_process()
        from .installed_fixture_receipt import refuse_inherited_configuration
        refuse_inherited_configuration()
        empty = self.path / '.libpq-no-passwords'
        _private(empty.stat(follow_symlinks=False), directory=False)
        need(empty.stat().st_size == 0)
        connection = psycopg.connect(self.dsn(maintenance=maintenance), autocommit=autocommit,
            row_factory=dict_row, password='', passfile=str(empty), sslmode='disable',
            gssencmode='disable', require_auth='none', options='-c lock_timeout=3000 -c statement_timeout=10000')
        try:
            self.verify_connection(connection)
        except BaseException:
            connection.close()
            raise
        return connection

    @contextmanager
    def postgres(self):
        self.verify()
        need(self.process is None and not (self.path / 'data/postmaster.pid').exists())
        need(self.record['phase'] == ('INSTALLING' if self.fresh else 'READY_STOPPED'))
        if not self.fresh:
            self._publish('RUNNING')
        primary = None
        with (self.path / 'logs/postgres.log').open('a') as log:
            self.process = subprocess.Popen([_pg_bin('postgres'), '-D', str(self.path / 'data'),
                '-h', '', '-k', str(self.path / 'socket'), '-p', '5432'],
                env=minimal_environment(os.environ), stdout=log, stderr=log)
            try:
                self.process_birth = self._birth()
                _starts[self] = (self.process, self.process_birth)
                deadline = time.monotonic() + 15
                while True:
                    self.verify_process()
                    try:
                        with self.connect(maintenance=True):
                            break
                    except psycopg.OperationalError:
                        need(time.monotonic() < deadline)
                        time.sleep(.1)
                yield self.process
            except BaseException as error:
                primary = error
                raise
            finally:
                try:
                    if self.process.poll() is None:
                        self.process.send_signal(signal.SIGINT)
                    self.process.wait(timeout=15)
                    need(not (self.path / 'data/postmaster.pid').exists())
                    if not self.fresh or primary is not None:
                        self._publish('UNKNOWN' if primary is not None else 'READY_STOPPED')
                except BaseException:
                    self.failed = True  # RUNNING/INSTALLING remains refusal on reopen
                    raise
                finally:
                    _starts.pop(self, None)
                    self.process = self.process_birth = None

    def finish_new(self):
        self.verify()
        need(self.fresh and self.created_database and self.process is None
             and self.record['phase'] == 'INSTALLING' and (self.path / 'state.json').is_file()
             and not (self.path / 'data/postmaster.pid').exists())
        self._publish('READY_STOPPED')

    def close(self):
        if self.closed:
            return
        need(self.process is None)
        if not self.failed and self.record is not None and self.record['phase'] == 'READY_STOPPED':
            self._publish('RELEASE_PENDING')
        self.closed = True
        _leases.pop(self, None)
        errors = []
        for fd in (self.lock, self.root):
            try:
                os.close(fd)
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup('LOCAL_INSTALLATION_RELEASE_UNKNOWN', errors)

    def __enter__(self):
        self.verify()
        return self

    def __exit__(self, *_):
        self.close()


@dataclass(frozen=True, repr=False, eq=False)
class LocalDatabaseCreationEvidence:
    """Issuer-registered, same-process, same-owned-cluster transaction authority."""
    installation: object
    database_oid: int
    system_identifier: str
    postmaster_start: object
    cluster_nonce: object
    database_nonce: object

    def __reduce__(self):
        raise TypeError('local database creation evidence cannot be serialized')

    def authorize_migration(self, connection):
        need(type(self) is LocalDatabaseCreationEvidence and _receipts.get(self) == os.getpid())
        lease = self.installation
        need(type(lease) is PersistentInstallation and lease.fresh and not connection.autocommit)
        lease.verify_connection(connection)
        row = facts._migration_identity(connection)
        need(row['database_oid'] == self.database_oid and row['database_name'] == 'parkweave'
             and row['system_identifier'] == self.system_identifier
             and row['data_directory'] == str(lease.path / 'data')
             and row['postmaster_start'] == self.postmaster_start
             and row['owner_name'] == row['current_name'] == row['session_name'] == 'postgres')
        facts._issue_migration_ticket(connection, self.database_oid, 'parkweave', 'postgres',
            self.system_identifier, str(lease.path / 'data'), self.postmaster_start,
            self.cluster_nonce, self.database_nonce)


def create_database(lease):
    """Own exclusive fresh installation, actual CREATE, then issue exactly once."""
    need(type(lease) is PersistentInstallation and lease.fresh and lease.initialized
         and _initializations.get(lease) == _identity((lease.path / 'data').stat())
         and not lease.created_database and lease.record['phase'] == 'INSTALLING')
    lease.verify_process()
    lease.created_database = True  # Unknown CREATE is never sent twice.
    with lease.connect(maintenance=True, autocommit=True) as connection:
        before = facts._migration_identity(connection)
        need(before['database_name'] == 'postgres' and before['data_directory'] == str(lease.path / 'data')
             and before['owner_name'] == before['session_name'] == before['current_name'] == 'postgres')
        need({r['datname'] for r in connection.execute('SELECT datname FROM pg_database').fetchall()}
             == {'postgres','template0','template1'})
        need(connection.execute("SELECT 1 FROM pg_roles WHERE rolname='parkweave_app'").fetchone() is None)
        connection.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
        connection.execute('CREATE DATABASE parkweave')
        oid = connection.execute("SELECT oid::bigint FROM pg_database WHERE datname='parkweave'").fetchone()['oid']
    with lease.connect() as connection:
        after = facts._migration_identity(connection)
        need(after['database_name'] == 'parkweave' and after['database_oid'] == oid
             and all(after[k] == before[k] for k in ('system_identifier','data_directory','postmaster_start',
                 'owner_name','current_name','session_name')))
    receipt = LocalDatabaseCreationEvidence(lease, oid, after['system_identifier'],
        after['postmaster_start'], uuid4(), uuid4())
    _receipts[receipt] = os.getpid()
    return PersistentSetupStore(lease, receipt)


class PersistentSetupStore(Store):
    def __init__(self, installation, receipt):
        need(type(installation) is PersistentInstallation and type(receipt) is LocalDatabaseCreationEvidence
             and receipt.installation is installation and _receipts.get(receipt) == os.getpid())
        super().__init__(installation.dsn())
        self.installation, self._case_fact_fixture_receipt = installation, receipt

    def connect(self):
        connection = self.installation.connect()
        try:
            LocalDatabaseCreationEvidence.authorize_migration(self._case_fact_fixture_receipt, connection)
        except BaseException:
            connection.close()
            raise
        return connection
