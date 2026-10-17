"""Opt-in diagnostics for this pytest process's newly created PG fixture only.

No resident observer, query text, DSN, authentication values or RPC payloads.
Connection budgets, exceptions, transactions and test assertions are unchanged.
"""
from contextlib import contextmanager
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import threading
import time

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
import pytest

_current = None


def current():
    return _current


def emit(kind, **values):
    if _current is not None:
        _current.emit(kind, **values)


@contextmanager
def stage(value):
    if _current is None:
        yield
        return
    before = _current.stage
    _current.stage = value
    _current.emit('stage_begin', stage=value)
    try:
        yield
    finally:
        _current.emit('stage_end', stage=value)
        _current.stage = before


def writer_dsn(dsn, label):
    if _current is None:
        return dsn
    name = 'pwdiag-w-' + sha256(_current.node.encode()).hexdigest()[:10] + '-' + label
    _current.emit('owned_writer_application', application_name=name)
    return make_conninfo(dsn, application_name=name)


class Diagnostics:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=False)
        self.fd = os.open(self.directory / 'connections.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.lock = threading.RLock()
        self.node, self.phase, self.stage = '', 'configure', 'NONE'
        self.sequence = 0
        self.servers = {}
        self.database_nodes = {}
        self.database_servers = {}
        self.active = {}
        self.sampled = set()
        self.patch = pytest.MonkeyPatch()
        self.original_connect = psycopg.Connection.connect.__func__
        self.original_close = psycopg.Connection.close

    def emit(self, kind, **values):
        row = dict(kind=kind, monotonic_ns=time.monotonic_ns(), utc_ns=time.time_ns(),
                   process_id=os.getpid(), thread_id=threading.get_ident(),
                   native_thread_id=threading.get_native_id(), thread_name=threading.current_thread().name,
                   node=self.node, phase=self.phase, stage=self.stage)
        row.update(values)
        with self.lock:
            os.write(self.fd, (json.dumps(row, default=str, separators=(',', ':')) + '\n').encode())

    def install(self):
        diagnostic = self

        def connect(cls, conninfo='', **kwargs):
            try:
                params = conninfo_to_dict(conninfo)
            except (psycopg.Error, ValueError, TypeError):
                return diagnostic.original_connect(cls, conninfo, **kwargs)
            db = kwargs.get('dbname', params.get('dbname', 'postgres'))
            endpoint = (kwargs.get('host', params.get('host')), str(kwargs.get('port', params.get('port', '5432'))))
            server = diagnostic.servers.get(endpoint)
            if server is None or not (db == 'postgres' or re.fullmatch(r'fixture_[a-f0-9]{32}', db)):
                return diagnostic.original_connect(cls, conninfo, **kwargs)
            diagnostic.database_servers[db] = endpoint
            with diagnostic.lock:
                diagnostic.sequence += 1
                number = diagnostic.sequence
            node = diagnostic.database_nodes.get(db, diagnostic.node)
            name = 'pwdiag-' + sha256(node.encode()).hexdigest()[:10] + '-' + str(os.getpid()) + '-' + str(number)
            meta = dict(attempt=number, application_name=name, database=db, fixture_node=node, cluster=server['label'],
                        connection_class=cls.__name__, connect_timeout=kwargs.get('connect_timeout', params.get('connect_timeout')))
            frames = []
            frame = sys._getframe(1)
            while frame and len(frames) < 5:
                path = Path(frame.f_code.co_filename)
                if any(part in ('src', 'tests') for part in path.parts) and path.is_relative_to(Path.cwd()):
                    frames.append(dict(file=str(path), function=frame.f_code.co_name, line=frame.f_lineno))
                frame = frame.f_back
            del frame
            diagnostic.emit('connect_begin', **meta, callsite=frames)
            start = time.monotonic_ns()
            try:
                conn = diagnostic.original_connect(cls, conninfo, **{**kwargs, 'application_name': name})
            except BaseException as error:
                diagnostic.emit('connect_failed', **meta, elapsed_ns=time.monotonic_ns()-start,
                                error_type=type(error).__name__)
                diagnostic.failure_sample(db, number)
                raise
            else:
                meta['backend_pid'] = conn.info.backend_pid
                diagnostic.active[id(conn)] = meta
                diagnostic.emit('connect_end', **meta, elapsed_ns=time.monotonic_ns()-start)
                return conn

        def close(conn):
            meta = diagnostic.active.get(id(conn))
            if meta is None:
                return diagnostic.original_close(conn)
            diagnostic.emit('close_begin', **meta)
            try:
                return diagnostic.original_close(conn)
            finally:
                diagnostic.emit('close_end', **meta, closed=conn.closed)
                diagnostic.active.pop(id(conn), None)

        self.patch.setattr(psycopg.Connection, 'connect', classmethod(connect))
        self.patch.setattr(psycopg, 'connect', psycopg.Connection.connect)
        self.patch.setattr(psycopg.Connection, 'close', close)

    def bind_owned_server(self, server, data):
        # Called only after this session creates the new fixture server.
        maintenance = server.get_uri()
        params = conninfo_to_dict(maintenance)
        endpoint = (params.get('host'), params.get('port', '5432'))
        label = 'postgres' if not self.servers else 'postgres-' + str(len(self.servers)+1)
        self.servers[endpoint] = dict(maintenance=maintenance, pg_log=data/'log', label=label)
        with self.original_connect(psycopg.Connection, maintenance, connect_timeout=2, autocommit=True) as conn:
            actual = conn.execute('SHOW data_directory').fetchone()[0]
            assert Path(actual).resolve() == data.resolve(), 'diagnostic logging requires this newly owned PGDATA'
            for statement in (
                "ALTER SYSTEM SET log_connections = 'on'",
                "ALTER SYSTEM SET log_disconnections = 'on'",
                "ALTER SYSTEM SET log_line_prefix = '%m [%p] session=%c app=%a '",
                "ALTER SYSTEM SET log_parameter_max_length_on_error = '0'",
            ):
                conn.execute(statement)
            conn.execute('SELECT pg_reload_conf()')
        self.emit('owned_pg_logging_enabled', postmaster_pid=server.get_pid(), cluster=label,
                  settings=['log_connections', 'log_disconnections', 'log_line_prefix', 'log_parameter_max_length_on_error'])

    def failure_sample(self, db, attempt):
        # One short maintenance connection per failing fixture database, never resident.
        with self.lock:
            server = self.servers.get(self.database_servers.get(db))
            if db in self.sampled or server is None:
                return
            self.sampled.add(db)
        self.emit('failure_sample_begin', failed_attempt=attempt, database=db)
        begin = time.monotonic_ns()
        conn = None
        try:
            dsn = make_conninfo(server['maintenance'], connect_timeout=2, application_name='pwdiag-failure-sample',
                               options='-c statement_timeout=1000 -c lock_timeout=500')
            with self.original_connect(psycopg.Connection, dsn, autocommit=True, row_factory=dict_row) as conn:
                rows = conn.execute('SELECT pid,application_name,datname,usename,state,wait_event_type,wait_event,'
                                    'backend_start,xact_start,query_start,state_change FROM pg_stat_activity '
                                    'WHERE datname=%s AND backend_type=\'client backend\' ORDER BY pid LIMIT 64', (db,)).fetchall()
                self.emit('failure_activity', failed_attempt=attempt, database=db, rows=rows)
            self.emit('failure_sample_closed', failed_attempt=attempt, elapsed_ns=time.monotonic_ns()-begin)
        except Exception as error:
            self.emit('failure_sample_unavailable', failed_attempt=attempt,
                      error_type=type(error).__name__, elapsed_ns=time.monotonic_ns()-begin)
        finally:
            self.emit('failure_sample_end', failed_attempt=attempt, connected=conn is not None,
                      returned_connection_closed=conn.closed if conn is not None else None,
                      elapsed_ns=time.monotonic_ns()-begin)
        self.save_pg_log()

    def save_pg_log(self):
        for server in self.servers.values():
            if server['pg_log'].is_file():
                (self.directory / (server['label']+'.log')).write_bytes(server['pg_log'].read_bytes())

    def finish(self):
        self.save_pg_log()
        self.emit('diagnostic_finish', successful_connections_without_observed_close=list(self.active.values()),
                  sampled_databases=len(self.sampled))
        self.patch.undo()
        os.close(self.fd)


def pytest_addoption(parser):
    parser.addoption('--owned-connection-diagnostics', default=None)


def pytest_configure(config):
    global _current
    directory = config.getoption('--owned-connection-diagnostics')
    if directory:
        _current = Diagnostics(directory)
        config._owned_connection_diagnostics = _current
        _current.install()


def mark(item, phase):
    if _current is not None:
        _current.node, _current.phase = item.nodeid, phase
        _current.emit('pytest_phase')


def pytest_runtest_setup(item): mark(item, 'setup')
def pytest_runtest_call(item): mark(item, 'call')
def pytest_runtest_teardown(item): mark(item, 'teardown')


def pytest_runtest_logreport(report):
    if _current is not None:
        _current.emit('pytest_report', report_node=report.nodeid, report_phase=report.when, outcome=report.outcome)
        if report.failed:
            for db,node in _current.database_nodes.items():
                if node == report.nodeid:
                    _current.failure_sample(db, None)
            _current.save_pg_log()


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    global _current
    if _current is not None:
        _current.finish()
        _current = None
