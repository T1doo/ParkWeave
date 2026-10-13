"""Catalog experiment only. Called after bootstrap gate, never an executable CLI.

The new cluster is owned by the existing nonroot runner. No host, API, business
Run/Case, execution grant, OS identity, existing database or secret is used.
"""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import time
import traceback
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from parkweave import native_run_access as native, native_run_access_activation as activation
from parkweave import native_run_access_preflight as preflight
from parkweave.case_fact_clarifications import capture_fixture_cluster
from parkweave.store import Store
from scripts.catalog_only.bootstrap import initial, public_summary, COMPARISON

OWNER, APP, WRITER = 'pwci_owner', 'pwci_app', 'pwci_writer'
FUNCTION_QUERY = 'SELECT system_identifier::text value FROM pg_catalog.pg_control_system()'
REVOKE = 'REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC'


def comparison(report):
    """No check name, detail, object, path or exception can reach public output."""
    result = dict(call='RETURNED', status='UNKNOWN', changes='UNKNOWN', nonpass='UNKNOWN')
    if type(report) is not dict:return result
    status = report.get('status')
    if type(status) is str and status in COMPARISON['status'] and status not in ('NOT_RUN', 'UNKNOWN'):
        result['status'] = status
    changes = report.get('changes')
    if type(changes) is list:result['changes'] = 'NONEMPTY' if changes else 'EMPTY'
    checks = report.get('checks')
    if type(checks) is list and checks and all(type(c) is dict and type(c.get('check')) is str and
            type(c.get('status')) is str and c['status'] in ('PASS', 'REFUSED', 'MISSING_CONFIG', 'NOT_CONNECTED', 'APPROVAL_REQUIRED') for c in checks):
        failed = [c for c in checks if c['status'] != 'PASS']
        result['nonpass'] = ('NONE' if not failed else 'APP_EXECUTE_ONLY' if len(failed) == 1 and
            failed[0]['check'] == 'forbidden.app:control_system_execute' and failed[0]['status'] == 'REFUSED' else 'OTHER')
    return result


def analyze_snapshot(spec, catalog, output, phase):
    try: report = preflight.analyze(spec.model_dump(), catalog)
    except BaseException:
        output['comparisons'][phase] = dict(call='RAISED', status='UNKNOWN', changes='UNKNOWN', nonpass='UNKNOWN')
        raise
    observed = comparison(report); output['comparisons'][phase] = observed
    expected = dict(call='RETURNED', status='REFUSED' if phase == 'before' else 'PASS', changes='EMPTY',
                    nonpass='APP_EXECUTE_ONLY' if phase == 'before' else 'NONE')
    if (observed != expected or any(report.get(k) is not False for k in
            ('installation_authorized', 'activation_enabled', 'production_connected'))):
        raise AssertionError('CATALOG_CONTRACT_NOT_MET')


def record_rights(catalog, output, phase):
    privileges = catalog.get('privileges', {})
    observed = [privileges.get('app:control_system_execute'), privileges.get('writer:EXECUTE:pg_control_system():')]
    for label, value in zip(('app', 'writer'), observed):
        output['rights'][phase + '_' + label] = 'ALLOW' if value is True else 'DENY' if value is False else 'UNKNOWN'
    if observed != ([True, True] if phase == 'before' else [False, True]) or any(type(v) is not bool for v in observed):
        raise AssertionError('EFFECTIVE_EXECUTE_CONTRACT_NOT_MET')


def apply_initial_acl(owner):
    with owner.connect() as c:
        for role in (APP, WRITER):
            c.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS').format(sql.Identifier(role)))
        c.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        c.execute('GRANT USAGE ON SCHEMA public TO pwci_app,pwci_writer')
        c.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO pwci_app')
        c.execute('GRANT INSERT ON authorization_audit TO pwci_app')
        # Same writer matrix as the original setup, including schema_version.
        for _, action, table, column in preflight.required_privileges('revision') + [('writer', 'SELECT', 'schema_version', None)]:
            if action == 'LOCK_UPDATE':continue
            if action == 'EXECUTE':
                c.execute('GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO pwci_writer'); continue
            c.execute(sql.SQL('GRANT ' + action + (' ({})' if column else '') + ' ON {} TO pwci_writer').format(
                *([sql.Identifier(column)] if column else []), sql.Identifier(table)))


def make_spec(owner, root):
    with owner.connect() as c:
        db = c.execute("SELECT current_database() name,(SELECT oid FROM pg_database WHERE datname=current_database()) oid").fetchone()
        system = c.execute(FUNCTION_QUERY).fetchone()['value']
    now = datetime.now(timezone.utc)
    # These UUIDs/UIDs are declarations for the catalog contract, not real
    # business records, OS separation, a host policy, or authority to execute.
    return preflight.InstallationSpec.model_validate(dict(
        policy=dict(environment='PRODUCTION', policy_id=str(uuid4()), revision=1,
            owner_id='SYNTHETIC_OWNER', approver_id='SYNTHETIC_APPROVER', beneficiary_id='SYNTHETIC_EXECUTOR',
            approver_actions=['APPROVE', 'REJECT', 'REVOKE'], valid_from=now.isoformat(),
            valid_until=(now+timedelta(minutes=10)).isoformat(), generations={'CATALOG_ONLY_SYNTHETIC': True},
            source=dict(run_id=str(uuid4()), case_id=str(uuid4()), preparation_id=str(uuid4()), run_revision=1,
                preparation_revision=1, preparation_state='LOCAL_CONFIRMED', owner_id='SYNTHETIC_OWNER',
                park_id='SYNTHETIC_PARK', org_id='SYNTHETIC_ORG', input_fingerprint='a'*64,
                review_sha256='b'*64, material_sha256='c'*64),
            database_name=db['name'], database_oid=db['oid'], system_identifier=system,
            database_host=str(root/'cluster/socket'), database_port=55441, application_role=APP, writer_role=WRITER),
        installer_role=OWNER, object_owners={name: OWNER for name in preflight.TABLES},
        permission_strategy='DIRECT_DML', parent_lock_column='revision', protected_location=str(root),
        api_uid=10001, writer_uid=10002, transport='LINUX_UNIX',
        policy_source_ref='CATALOG_ONLY_SYNTHETIC_DECLARATION', key_source_ref='NO_KEY_OR_HOST_USED',
        host_pin_source_ref='NO_HOST_OR_OS_ISOLATION_VERIFIED'))


def role_call(dsn, role, spec, allowed):
    # Real separate SQL session; no SET ROLE or privileged owner connection.
    with psycopg.connect(make_conninfo(dsn, user=role), autocommit=True, row_factory=dict_row) as c:
        row = c.execute("""SELECT current_user actual,session_user session,current_database() database,
            (SELECT oid FROM pg_database WHERE datname=current_database()) oid,
            (SELECT rolsuper FROM pg_roles WHERE rolname=current_user) superuser""").fetchone()
        if (row != dict(actual=role, session=role, database=spec.policy.database_name, oid=spec.policy.database_oid, superuser=False)
                or c.info.host != spec.policy.database_host or c.info.port != spec.policy.database_port):
            raise AssertionError('EXACT_NONOWNER_SESSION_REQUIRED')
        try:
            with c.transaction(): result = c.execute(FUNCTION_QUERY).fetchone()
        except psycopg.errors.InsufficientPrivilege as exc:
            if allowed or exc.sqlstate != '42501':raise
            # Positive control after the failed transaction has rolled back.
            if c.execute('SELECT 1 value').fetchone() != {'value': 1}:
                raise AssertionError('SESSION_RECOVERY_REQUIRED')
        else:
            if not allowed or result != {'value': spec.policy.system_identifier}:
                raise AssertionError('FUNCTION_EXECUTION_CONTRACT_NOT_MET')


def run(root, source_sha):
    output = initial(source_sha); output['cases'].update(GATE='PASS', DEPENDENCIES='PASS')
    stage = 'PG16_START'; pg = None; cluster = root/'cluster'; created = False
    initdb_started = False; initdb_complete = False
    previous_handlers = {s: signal.getsignal(s) for s in (signal.SIGALRM, signal.SIGTERM, signal.SIGINT)}
    def deadline(*_):raise TimeoutError('CATALOG_ONLY_DEADLINE_OR_CANCEL')
    try:
        for s in previous_handlers:signal.signal(s, deadline)
        signal.setitimer(signal.ITIMER_REAL, 480)
        if (os.geteuid() == 0 or root.is_symlink() or root.parent != Path('/tmp') or
                not root.name.startswith('parkweave-catalog-') or root.stat().st_uid != os.geteuid() or
                stat.S_IMODE(root.stat().st_mode) != 0o700):
            raise PermissionError('NEW_PRIVATE_RUNNER_DIRECTORY_REQUIRED')
        cluster.mkdir(mode=0o700); created = True
        data = cluster/'data'; socket = cluster/'socket'; socket.mkdir(mode=0o700)
        binary = Path('/usr/lib/postgresql/16/bin')
        for name in ('initdb', 'postgres'):
            s = (binary/name).lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
                raise PermissionError('INSTALLED_PG16_REGULAR_BINARY_REQUIRED')
        with (root/'initdb.log').open('wb') as log:
            initdb_started = True
            subprocess.run([str(binary/'initdb'), '-D', str(data), '--username='+OWNER,
                '--auth-local=trust', '--auth-host=reject', '--no-locale', '--encoding=UTF8'],
                env={'LANG':'C.UTF-8','PATH':'/usr/bin:/bin'}, stdout=log, stderr=log, timeout=60, check=True)
            initdb_complete = True
        if (data/'PG_VERSION').read_text().strip() != '16':raise AssertionError('PG16_REQUIRED')
        logpath = root/'postgres.log'
        with logpath.open('wb') as log:
            pg = subprocess.Popen([str(binary/'postgres'), '-D', str(data), '-k', str(socket), '-p', '55441',
                '-c', 'listen_addresses=', '-c', 'unix_socket_permissions=0700', '-c', 'log_statement=none',
                '-c', 'log_min_error_statement=panic', '-c', 'log_error_verbosity=terse'],
                env={'LANG':'C.UTF-8'}, stdout=log, stderr=log)
        until = time.monotonic()+10
        while b'database system is ready to accept connections' not in logpath.read_bytes()[:1048576]:
            if pg.poll() is not None or time.monotonic() >= until:raise TimeoutError('OWNED_PG_NOT_READY')
            time.sleep(.05)
        if int((data/'postmaster.pid').read_text().splitlines()[0]) != pg.pid:
            raise AssertionError('EXACT_OWNED_POSTMASTER_REQUIRED')
        # Explicit new empty file prevents libpq's default ~/.pgpass lookup.
        # Local trust is confined to our private socket; no existing key is used.
        passfile = root/'empty.pgpass'
        fd = os.open(passfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        maintenance = make_conninfo(host=str(socket), port=55441, dbname='postgres', user=OWNER,
            passfile=str(passfile), sslmode='disable', gssencmode='disable',
            connect_timeout=2, options='-c statement_timeout=5000 -c lock_timeout=1000')
        proof = capture_fixture_cluster(maintenance, data)
        output['cases'][stage] = 'PASS'; stage = 'OWNED_EMPTY_STORAGE'
        name = 'fixture_'+uuid4().hex
        with psycopg.connect(maintenance, autocommit=True) as c:
            c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        owner = Store(make_conninfo(maintenance, dbname=name))
        with owner.connect() as c:owner._case_fact_fixture_receipt = proof.record_created_database(c)
        owner.migrate()
        native.install_owned_test_storage(owner, owner._case_fact_fixture_receipt)
        activation.install_owned_test_activation_storage(owner, owner._case_fact_fixture_receipt)
        apply_initial_acl(owner); spec = make_spec(owner, root)
        output['cases'][stage] = 'PASS'; stage = 'BEFORE_RIGHTS'
        output['rights'].update(before_app='UNKNOWN', before_writer='UNKNOWN')
        with owner.connect() as c:before = preflight.collect_owned_catalog(c, owner._case_fact_fixture_receipt, spec)
        record_rights(before, output, 'before')
        output['cases'][stage] = 'PASS'; stage = 'BEFORE_CALLS'
        role_call(owner.dsn, APP, spec, True); role_call(owner.dsn, WRITER, spec, True)
        output['cases'][stage] = 'PASS'; stage = 'BEFORE_COMPARE'
        analyze_snapshot(spec, before, output, 'before')
        output['cases'][stage] = 'PASS'; stage = 'APPLY_FIX'
        # Only this one statement changes the committed before/after ACL state.
        with owner.connect() as c:c.execute(REVOKE)
        output['cases'][stage] = 'PASS'; stage = 'AFTER_RIGHTS'
        output['rights'].update(after_app='UNKNOWN', after_writer='UNKNOWN')
        with owner.connect() as c:after = preflight.collect_owned_catalog(c, owner._case_fact_fixture_receipt, spec)
        record_rights(after, output, 'after')
        output['cases'][stage] = 'PASS'; stage = 'APP_CALL_DENIED'
        role_call(owner.dsn, APP, spec, False)
        output['cases'][stage] = 'PASS'; stage = 'WRITER_CALL_ALLOWED'
        role_call(owner.dsn, WRITER, spec, True)
        output['cases'][stage] = 'PASS'; stage = 'AFTER_COMPARE'
        analyze_snapshot(spec, after, output, 'after')
        output['cases'][stage] = 'PASS'
    except BaseException:
        output['cases'][stage] = 'FAIL'
        try:
            (root/'probe-failure.log').write_text(traceback.format_exc())
            output['failure_logs'] = 'SAVED'
        except BaseException:output['failure_logs'] = 'UNAVAILABLE'
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        try:
            if pg is not None and pg.poll() is None:
                pg.terminate()
                try:pg.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    pg.kill(); pg.wait(timeout=5)
                    raise RuntimeError('FORCED_STOP_CLUSTER_CLEANUP_UNCONFIRMED')
            if pg is not None and (type(pg.poll()) is not int or pg.poll() != 0):
                raise RuntimeError('NORMAL_OWNED_PG_STOP_UNCONFIRMED')
            if created:
                if initdb_started and not initdb_complete:
                    output['cases']['CLEANUP'] = 'UNKNOWN'
                    return public_summary(output)
                if cluster.is_symlink() or cluster.stat().st_uid != os.geteuid():
                    raise PermissionError('OWNED_CLUSTER_REMOVAL_REFUSED')
                shutil.rmtree(cluster)
                output['cases']['CLEANUP'] = 'PASS'
        except BaseException:
            output['cases']['CLEANUP'] = 'FAIL'
            try:
                (root/'cleanup-failure.log').write_text(traceback.format_exc())
                if output['failure_logs'] != 'UNAVAILABLE':output['failure_logs'] = 'SAVED'
            except BaseException:output['failure_logs'] = 'UNAVAILABLE'
        finally:
            for s, handler in previous_handlers.items():signal.signal(s, handler)
    return public_summary(output)
