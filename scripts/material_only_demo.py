"""Explicit, retained Linux SYNTHETIC material demo; never ordinary startup setup.

One private cluster/database, two principals and six business grants. No bulk
seed, roles.sql, resource/executor/assignment/approval or model provider.
"""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
from hashlib import sha256
import importlib.metadata
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'src'))
from parkweave.store import Store, Denied, digest
from parkweave.process_env import minimal_environment

PREFIX = 'parkweave-material-demo-'
_last_owned_state = None
AUTHORITY = ('principals', 'capability_grants', 'action_grants', 'preparation_grants',
             'preparation_catalog', 'run_assignments', 'field_grants',
             'synthetic_resources', 'synthetic_resource_grants')
# Only the SQL operations used by original material APIs and the normal worker.
# Empty dispatch queue is read by the normal worker; no dispatch writes granted.
SQL_RIGHTS = {
    'SELECT': ('schema_version', 'principals', 'capability_grants', 'action_grants',
               'preparation_grants', 'preparation_catalog', 'field_grants', 'run_assignments',
               'model_steps', 'dispatch_notice_outbox', 'service_dispatch_events', 'controlled_plans'),
    'SELECT,INSERT,UPDATE': ('runs', 'operations', 'outbox', 'run_projection',
                             'deliveries', 'preparations'),
    'SELECT,INSERT': ('cases', 'preparation_evidence', 'preparation_events'),
    'INSERT': ('authorization_audit',),
    # Original material invalidation SELECTs this empty table FOR UPDATE.
    'UPDATE(invalidated_from,invalidated_at)': ('controlled_plans',),
}


def dump(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.write('\n')


def pg_bin(name):
    return str(importlib.metadata.distribution('pgserver').locate_file('pgserver/pginstall/bin/' + name))


def source_binding():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    return dict(source_commit=git('rev-parse', 'HEAD'), src_tree=git('rev-parse', 'HEAD:src'),
                bootstrap_sha256=sha256(Path(__file__).read_bytes()).hexdigest())


def private_state(value):
    p = Path(value).absolute()
    if (sys.platform != 'linux' or p.resolve() != p or p.parent != Path('/tmp')
            or not p.name.startswith(PREFIX) or not p.is_dir()
            or p.stat().st_uid != os.geteuid() or p.stat().st_mode & 0o077):
        raise Denied('owned private /tmp material-demo directory required')
    for name in ('data', 'socket', 'state.json', 'sessions.json', 'entry.lock', 'logs'):
        if (p / name).is_symlink():
            raise Denied('symlink state refused')
        if (p / name).exists() and ((p / name).stat().st_uid != os.geteuid()
                                   or (p / name).stat().st_mode & 0o077):
            raise Denied('private owned state permissions required')
    return p


@contextmanager
def locked(value):
    p = private_state(value)
    with (p / 'entry.lock').open('r+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield p


def dsn(p, *, application=False, maintenance=False):
    return make_conninfo(host=str(p / 'socket'), port=5432,
                         user='parkweave_app' if application else 'postgres',
                         dbname='postgres' if maintenance else 'parkweave', connect_timeout=2)


@contextmanager
def postgres(p, *, observation=None):
    if (p / 'data/postmaster.pid').exists():
        raise Denied('existing postmaster marker; no adoption, signalling or repair')
    env = minimal_environment(os.environ)
    with (p / 'logs/postgres.log').open('a') as log:
        child = subprocess.Popen([pg_bin('postgres'), '-D', str(p / 'data'), '-h', '',
                                  '-k', str(p / 'socket'), '-p', '5432'], env=env,
                                 stdout=log, stderr=log)
        facts = dict(role='postgres', pid=child.pid, exit_code=None)
        if observation is not None:
            observation['children'].append(facts)
            observation['creation']['postgres'] = 'created'
        primary_error = None
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise RuntimeError('owned postgres exited')
                try:
                    with psycopg.connect(dsn(p, maintenance=True)):
                        break
                except psycopg.OperationalError:
                    time.sleep(.1)
            else:
                raise RuntimeError('owned postgres readiness timeout')
            yield child
        except BaseException as error:
            primary_error = error
            raise
        finally:
            cleanup_errors=[]
            try:
                if child.poll() is None:
                    child.send_signal(signal.SIGINT)
                try:
                    child.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    (p / 'stop-unconfirmed').touch(exist_ok=True)
                    raise RuntimeError('owned postgres stop unconfirmed; state retained') from None
            except BaseException as error:cleanup_errors.append(error)
            if observation is not None:
                try:facts['exit_code'] = child.poll()
                except BaseException as error:cleanup_errors.append(error)
            if cleanup_errors:
                if observation is not None:
                    for error in cleanup_errors:
                        detail = dict(type=type(error).__name__)
                        if type(getattr(error, 'errno', None)) is int:detail['errno'] = error.errno
                        observation['cleanup_errors'].append(detail)
                    raise BaseExceptionGroup('demo operation and owned postgres cleanup failed',
                        ([primary_error] if primary_error is not None else [])+cleanup_errors) from None
                raise cleanup_errors[0]


def authority(c):
    values = {}
    for table in AUTHORITY:
        rows = [dict(row) for row in c.execute('SELECT * FROM ' + table).fetchall()]
        values[table] = sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))
    raw = json.dumps(values, sort_keys=True, default=str, separators=(',', ':')).encode()
    return dict(sha256=sha256(raw).hexdigest(), counts={k: len(v) for k, v in values.items()})


def setup(*, session_provider=None):
    global _last_owned_state
    if sys.platform != 'linux' or os.geteuid() == 0:
        raise Denied('existing unprivileged Linux environment required')
    p = Path(tempfile.mkdtemp(prefix=PREFIX, dir='/tmp'))
    _last_owned_state = p
    print(json.dumps(dict(setup_state_dir=str(p),state_retained=True)),flush=True)
    for name in ('logs', 'socket', 'downloads'):
        (p / name).mkdir(mode=0o700)
    (p / 'entry.lock').touch(mode=0o600)
    # No get_server(): avoid automatic old-process adoption/termination or deletion.
    with (p / 'logs/initdb.log').open('x') as log:
        subprocess.run([pg_bin('initdb'), '-D', str(p / 'data'), '-U', 'postgres',
                        '--auth-local=trust', '--auth-host=reject', '--encoding=UTF8', '--no-locale'],
                       stdout=log, stderr=log, check=True, timeout=30,
                       env=minimal_environment(os.environ))
    with locked(p), postgres(p):
        from parkweave.case_fact_clarifications import capture_fixture_cluster
        cluster = capture_fixture_cluster(dsn(p, maintenance=True), p / 'data')
        with psycopg.connect(dsn(p, maintenance=True), autocommit=True) as c:
            c.execute('CREATE DATABASE parkweave')
            c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
        owner = Store(dsn(p))
        with owner.connect() as c:
            receipt = cluster.record_created_database(c)
        owner._case_fact_fixture_receipt = receipt
        # Preserve observed creation data, never reconstruct an issued receipt from it.
        dump(p / 'creation-observation.json', asdict(receipt))
        owner.migrate()
        tokens = (session_provider.generate() if session_provider is not None else
                  dict(enterprise=secrets.token_urlsafe(32), specialist=secrets.token_urlsafe(32)))
        park, org = 'synthetic-material-park', 'synthetic-material-org'
        ids = dict(enterprise='material-demo-enterprise', specialist='material-demo-specialist')
        with owner.connect() as c:
            for actor, role in (('enterprise', 'enterprise_operator'), ('specialist', 'park_specialist')):
                c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',
                          (ids[actor], digest(tokens[actor]), park, org, role))
            for actor, cap in (('enterprise', 'READ'), ('enterprise', 'EXECUTE'), ('specialist', 'READ')):
                c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s)',
                          (ids[actor], cap, park, org))
            c.execute("INSERT INTO action_grants(principal_id,action,park_id,org_id) VALUES(%s,'case.create',%s,%s)", (ids['enterprise'], park, org))
            for actor, cap in (('enterprise', 'PREPARE'), ('specialist', 'REVIEW_ASSIGNED')):
                c.execute('INSERT INTO preparation_grants(principal_id,park_id,org_id,capability) VALUES(%s,%s,%s,%s)',
                          (ids[actor], park, org, cap))
            source = dict(kind='SYNTHETIC', id='MATERIAL_ONLY_LOCAL_DEMO', revision='1',
                          statement='仅合成资料整理定义；无资格条件，不是模板发布或正式批准。')
            c.execute("INSERT INTO preparation_catalog VALUES(%s,'synthetic-material-preparation',1,'企业资料整理（合成）',%s,'SYNTHETIC','NOT_EVALUATED')", (park, Jsonb(source)))
            c.execute('GRANT CONNECT ON DATABASE parkweave TO parkweave_app')
            c.execute('GRANT USAGE ON SCHEMA public TO parkweave_app')
            for operations, tables in SQL_RIGHTS.items():
                c.execute('GRANT ' + operations + ' ON ' + ','.join(tables) + ' TO parkweave_app')
            identity = c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()
            oid = c.execute("SELECT oid::bigint FROM pg_database WHERE datname='parkweave'").fetchone()['oid']
            snapshot = authority(c)
            assert snapshot['counts'] == dict(principals=2, capability_grants=3, action_grants=1,
                preparation_grants=2, preparation_catalog=1, run_assignments=0, field_grants=0,
                synthetic_resources=0, synthetic_resource_grants=0)
        marker = dict(schema='parkweave-material-only-demo/1', **source_binding(),
             system_identifier=identity['system_identifier'], database_oid=oid, schema_version=32,
             authority=snapshot, ids=ids, sql_rights=SQL_RIGHTS, session_expiry='NONE_MANUAL_REVOCATION_REQUIRED')
        if session_provider is None:
            dump(p / 'sessions.json', tokens)
        else:
            session_provider.publish(p, marker)
            marker['session_storage'] = 'PASSWORD_SEALED_SEPARATE_ROLES_V1'
            from scripts.local_product import runtime_source_binding
            marker['runtime_source_sha256'] = runtime_source_binding()
        dump(p / 'state.json', marker)
    return p


def serve(value, port):
    global _last_owned_state
    if not 1024 <= port <= 65535:
        raise Denied('unprivileged port required')
    _last_owned_state = private_state(value)
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', port))
    with locked(value) as p:
        _last_owned_state = p
        if (p / 'stop-unconfirmed').exists():
            raise Denied('previous owned stop unconfirmed; no automatic repair')
        marker = json.loads((p / 'state.json').read_text())
        binding = source_binding()
        if (marker['schema'] != 'parkweave-material-only-demo/1'
                or marker['src_tree'] != binding['src_tree']
                or marker['bootstrap_sha256'] != binding['bootstrap_sha256']):
            raise Denied('frozen demo source binding changed')
        with postgres(p) as pg:
            with psycopg.connect(dsn(p), row_factory=dict_row) as c:
                c.execute('SET TRANSACTION READ ONLY')
                identity = c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()
                oid = c.execute("SELECT oid::bigint FROM pg_database WHERE datname='parkweave'").fetchone()['oid']
                version = c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']
                if (identity['system_identifier'] != marker['system_identifier'] or oid != marker['database_oid']
                        or version != 32 or authority(c) != marker['authority']):
                    raise Denied('retained database or authority changed; no repair')
            env = minimal_environment(os.environ, PYTHONPATH=str(ROOT / 'src'),
                PYTHONDONTWRITEBYTECODE='1', PARKWEAVE_DSN=dsn(p, application=True), PARKWEAVE_MODE='LOCAL')
            children = []
            with (p / 'logs/application.log').open('a') as log:
                try:
                    for command in (['uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port)], ['parkweave.worker']):
                        children.append(subprocess.Popen([sys.executable,'-B','-m',*command], cwd=ROOT,env=env,stdout=log,stderr=log))
                    deadline = time.monotonic()+20
                    while time.monotonic()<deadline:
                        if any(child.poll() is not None for child in children):
                            raise RuntimeError('owned API/worker exited; inspect private logs')
                        try:
                            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=.3) as r:
                                health=json.load(r)
                            if health['process_id']==children[0].pid and health['schema']==32 and health['data']=='SYNTHETIC':
                                break
                        except (OSError, ValueError):
                            pass
                        time.sleep(.1)
                    else:
                        raise RuntimeError('owned API readiness timeout')
                    print(json.dumps(dict(url=f'http://127.0.0.1:{port}',api_pid=children[0].pid,
                        worker_pid=children[1].pid,postgres_pid=pg.pid,scope='MATERIAL_ONLY_SYNTHETIC',
                        source_commit=marker['source_commit'],local_synthetic_demo_profile=False)),flush=True)
                    while all(child.poll() is None for child in children):
                        time.sleep(.25)
                    raise RuntimeError('owned API/worker exited')
                finally:
                    from scripts.linux_fixture_server import stop_children
                    try:
                        stop_children(children)
                    except BaseException:
                        (p / 'stop-unconfirmed').touch(exist_ok=True)
                        raise


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('setup','serve'))
    parser.add_argument('--state-dir')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if (args.command=='serve') != bool(args.state_dir):
        parser.error('serve needs existing --state-dir; setup always creates a unique private directory')
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if args.command=='setup':
            print(json.dumps(dict(state_dir=str(setup()),session_expiry='NONE_MANUAL_REVOCATION_REQUIRED')))
        else:
            serve(args.state_dir,args.port)
    except KeyboardInterrupt:
        return 130 if args.command=='setup' else 0
    except Exception as error:
        if _last_owned_state is not None:
            import traceback
            with (_last_owned_state / 'failure.log').open('a') as stream:
                stream.write(traceback.format_exc())
        print('MATERIAL_DEMO_BLOCKED: '+type(error).__name__+'; private state retained; no automatic retry',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    raise SystemExit(main())
