"""Exact original test bodies on owned PG; no standalone CLI or host activation."""
from contextlib import contextmanager
import hashlib
import os
import signal
import socket
import subprocess
import sys
import traceback
from unittest.mock import patch

import psycopg
from psycopg.conninfo import make_conninfo
import pytest

from scripts.case_pg_vertical.bootstrap import initial, public_summary, selection
from scripts.case_pg_vertical.owned_pg import OwnedPG
from parkweave import case_fact_clarifications as facts
from parkweave.store import Denied

BRIDGE_NODE = 'tests/test_case_pg_vertical_integration.py::test_catalog_fix_and_case_cancellation_share_owned_database'


def close_app_control(owner, store):
    # This is the just-created per-test UUID database, not a cluster-wide ACL.
    with owner.connect() as c:
        proof = owner._case_fact_fixture_receipt
        if (type(proof) is not facts.FixtureDatabaseEvidence or
                facts._fixture_databases.get(proof.nonce) is not proof or
                facts._fixture_clusters.get(proof.cluster.nonce) is not proof.cluster):
            raise Denied('original issued fixture proof required')
        identity = facts._migration_identity(c); facts._same_cluster(proof.cluster, identity)
        if (identity['database_name'], identity['database_oid'], identity['owner_name'], identity['session_name']) != (
                proof.database_name, proof.database_oid, proof.cluster.owner, proof.cluster.owner):
            raise Denied('exact original owned database required')
        c.execute('REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC')
    with store.connect() as c:
        try:c.execute('SELECT system_identifier FROM pg_catalog.pg_control_system()')
        except psycopg.errors.InsufficientPrivilege as exc:
            if exc.sqlstate != '42501':raise
            c.rollback()
            if c.execute('SELECT 1 AS value').fetchone() != {'value': 1}:
                raise AssertionError('APP_POSITIVE_CONTROL_REQUIRED')
        else:raise AssertionError('ACTUAL_APP_DENIAL_REQUIRED')


class SessionSupplier:
    def __init__(self, pg):self.pg = pg; self.calls = 0

    @pytest.hookimpl(tryfirst=True)
    def pytest_fixture_setup(self, fixturedef, request):
        if fixturedef.argname != 'pg':return None
        if fixturedef.scope != 'session' or self.calls:
            raise AssertionError('ONE_ORIGINAL_SESSION_PG_REQUIRED')
        self.pg.get_uri()  # Original issued cluster proof must already exist.
        self.calls += 1
        fixturedef.cached_result = (self.pg, fixturedef.cache_key(request), None)
        return self.pg


class Results:
    def __init__(self, rows, output):
        self.rows = rows; self.output = output; self.by_node = {r['nodeid']: r for r in rows}
        self.collected = False; self.phases = {}; self.case_acl_checks = 0

    def pytest_collection_modifyitems(self, session, config, items):
        if [i.nodeid for i in items] != [r['nodeid'] for r in self.rows]:
            self.output['stages']['COLLECTION'] = 'FAIL'
            raise pytest.UsageError('EXACT_REVIEWED_TEST_COLLECTION_REQUIRED')
        self.collected = True; self.output['stages']['COLLECTION'] = 'PASS'

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(self, fixturedef, request):
        result = yield
        if fixturedef.argname != 'fixture' or result.excinfo is not None:return
        row = self.by_node.get(request.node.nodeid)
        if row is None:raise AssertionError('UNREVIEWED_FIXTURE_REQUEST')
        if row['group'] == 'CASE' and row['nodeid'] != BRIDGE_NODE:
            store, owner, _, _ = result.get_result()
            close_app_control(owner, store)
            self.case_acl_checks += 1

    def pytest_runtest_logreport(self, report):
        row = self.by_node.get(report.nodeid)
        if row is None or report.when not in ('setup', 'call', 'teardown'):
            raise AssertionError('UNKNOWN_REPORT_REFUSED')
        key = row['id']; phases = self.phases.setdefault(key, {})
        phases[report.when] = report.outcome
        state = self.output['tests'][key]
        if report.failed:
            state = 'ERROR' if report.when != 'call' or state == 'ERROR' else 'FAIL'
            raw = str(report.longrepr)
            line = getattr(getattr(report.longrepr, 'reprcrash', None), 'lineno', 0)
            self.output['diagnostics'].append(dict(id=key, phase=report.when,
                line=line if type(line) is int and 0 <= line <= 10000 else 0,
                trace_sha256=hashlib.sha256(raw.encode()).hexdigest()))
            self.output['failure_logs'] = 'SAVED'
        elif state not in ('ERROR', 'FAIL', 'SKIP'):
            state = 'SKIP' if report.skipped else 'PASS' if phases == dict(setup='passed', call='passed', teardown='passed') else 'UNKNOWN'
        self.output['tests'][key] = state


@contextmanager
def scoped_test_io(pg):
    """Original tests may use only this PG socket and in-process ASGI."""
    connect = psycopg.connect
    def guarded(conninfo='', **kwargs):
        pg.validate_connection(conninfo, kwargs)
        return connect(conninfo, **kwargs)
    def blocked(*_args, **_kwargs):raise PermissionError('UNREVIEWED_PROCESS_OR_NETWORK_ACTION')
    with patch.object(psycopg, 'connect', guarded), patch.object(psycopg.Connection, 'connect', staticmethod(guarded)), \
            patch.object(subprocess, 'Popen', blocked), patch.object(socket.socket, 'connect', blocked), \
            patch.object(socket.socket, 'bind', blocked):
        yield


def run(root, source_sha):
    output = initial(source_sha); output['stages'].update(GATE='PASS', DEPENDENCIES='PASS')
    stage = 'PG16_START'; pg = OwnedPG(root)
    previous = {s: signal.getsignal(s) for s in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
    def deadline(*_):raise KeyboardInterrupt('ONE_TRIAL_DEADLINE')
    try:
        for s in previous:signal.signal(s, deadline)
        signal.setitimer(signal.ITIMER_REAL, 900)
        pg.start(); output['stages'][stage] = 'PASS'
        stage = 'COLLECTION'; rows = selection(); supplier = SessionSupplier(pg); results = Results(rows, output)
        # Prevent installed entry-point plugins or user pytest options from widening the run.
        with patch.dict(os.environ, {'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTEST_ADDOPTS': '',
                'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(root)}, clear=False), scoped_test_io(pg):
            code = pytest.main([r['nodeid'] for r in rows] + ['-q', '-p', 'no:cacheprovider',
                '--tb=short', '--basetemp='+str(root/'pytest-tmp'), '--junitxml='+str(root/'private-junit.xml')],
                plugins=[supplier, results])
        if not results.collected:raise AssertionError('COLLECTION_NOT_OBSERVED')
        stage = 'TESTS'
        expected_acl = sum(r['group'] == 'CASE' and r['nodeid'] != BRIDGE_NODE for r in rows)
        if (code != 0 or supplier.calls != 1 or 'pgserver' in sys.modules or results.case_acl_checks != expected_acl or
                any(v != 'PASS' for v in output['tests'].values())):
            raise AssertionError('COMPLETE_ORIGINAL_TESTS_AND_ADAPTER_REQUIRED')
        output['stages'][stage] = 'PASS'; stage = 'FIXTURE_CLEANUP'
        if not pg.fixtures_removed():raise AssertionError('ALL_NEW_FIXTURE_DATABASES_MUST_BE_DROPPED')
        output['stages'][stage] = 'PASS'
    except BaseException:
        output['stages'][stage] = 'FAIL'
        try:
            (root/'probe-failure.log').write_text(traceback.format_exc()); output['failure_logs'] = 'SAVED'
        except BaseException:output['failure_logs'] = 'UNAVAILABLE'
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        try:output['stages']['PG_CLEANUP'] = pg.stop()
        except BaseException:
            output['stages']['PG_CLEANUP'] = 'FAIL'
            try:
                (root/'cleanup-failure.log').write_text(traceback.format_exc())
                if output['failure_logs'] != 'UNAVAILABLE':output['failure_logs'] = 'SAVED'
            except BaseException:output['failure_logs'] = 'UNAVAILABLE'
        finally:
            for s, handler in previous.items():signal.signal(s, handler)
    return public_summary(output)
