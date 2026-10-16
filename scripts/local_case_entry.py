"""Explicit Linux SYNTHETIC setup, then restartable local Case entry.

No test imports, runtime assignment, approval bridge, migration on resume,
credential discovery, or real model. State is retained in an owned /tmp folder.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import pgserver
import psycopg
from psycopg.conninfo import make_conninfo
from parkweave.process_env import minimal_environment
from parkweave.store import Store, Denied
from scripts.linux_fixture_server import stop_children, DemoStopUnconfirmed

REPO = Path(__file__).resolve().parents[1]
NAMESPACE = 'PARKWEAVE_LOCAL_CASE_SYNTHETIC_V1'


def state_path(value):
    path = Path(value).absolute()
    if (sys.platform != 'linux' or path.resolve() != path or
            path.parent != Path('/tmp') or not path.name.startswith('parkweave-local-case-') or
            not path.is_dir() or path.stat().st_uid != os.geteuid() or
            path.stat().st_mode & 0o077):
        raise Denied('owned private Linux /tmp local-case directory required')
    for name in ('local-case.json', 'data', '.runtime', 'entry.lock'):
        if (path / name).is_symlink():
            raise Denied('symlink state refused')
    return path


@contextmanager
def locked_state(value):
    root = state_path(value)
    with (root / 'entry.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Denied('another local-case launcher owns this state') from None
        yield root


def setup():
    if sys.platform != 'linux':
        raise Denied('Linux synthetic fixture only')
    # Original receipt requires a newly created, live, empty cluster under /tmp.
    root = Path(tempfile.mkdtemp(prefix='parkweave-local-case-', dir='/tmp'))
    server = None
    try:
        with locked_state(root):
            server = pgserver.get_server(root / 'data', cleanup_mode='stop')
            from parkweave.case_fact_clarifications import capture_fixture_cluster
            cluster = capture_fixture_cluster(server.get_uri(), (root / 'data').resolve())
            with psycopg.connect(server.get_uri(), autocommit=True) as c:
                c.execute('CREATE DATABASE parkweave')
                c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
            owner = Store(make_conninfo(server.get_uri(), dbname='parkweave'))
            with owner.connect() as c:
                owner._case_fact_fixture_receipt = cluster.record_created_database(c)
            owner.migrate()
            with owner.connect() as c:
                c.execute((REPO / 'src/parkweave/roles.sql').read_text())
            env = minimal_environment(os.environ, PYTHONPATH=str(REPO / 'src'), PARKWEAVE_DSN=owner.dsn)
            subprocess.run([sys.executable, '-m', 'parkweave.cli', 'seed-synthetic'],
                           cwd=root, env=env, check=True, stdout=subprocess.DEVNULL)
            with owner.connect() as c:
                system_id = str(c.execute('SELECT system_identifier FROM pg_control_system()').fetchone()['system_identifier'])
            marker = dict(namespace=NAMESPACE, schema=32, system_identifier=system_id,
                          data='SYNTHETIC', setup_complete=True)
            (root / 'local-case.json').write_text(json.dumps(marker, indent=2) + '\n')
            return root
    except BaseException:
        # Failed setup is preserved for diagnosis, never auto-repaired on serve.
        print('Setup failed; retained directory: ' + str(root), file=sys.stderr)
        raise
    finally:
        if server is not None:
            server.cleanup()


@contextmanager
def retained_database(value):
    with locked_state(value) as root:
        marker = json.loads((root / 'local-case.json').read_text())
        if (not isinstance(marker, dict) or marker.get('namespace') != NAMESPACE or marker.get('schema') != 32 or
                marker.get('setup_complete') is not True or marker.get('data') != 'SYNTHETIC' or
                not (root / 'data/PG_VERSION').is_file()):
            raise Denied('completed original local-case setup required; no repair')
        if (root / 'stop-unconfirmed.json').exists():
            raise Denied('previous child stop unconfirmed; retained state blocked')
        if (root / 'data/postmaster.pid').exists():
            raise Denied('existing PostgreSQL process marker; no adoption or repair')
        server = pgserver.get_server(root / 'data', cleanup_mode='stop')
        try:
            owner = Store(make_conninfo(server.get_uri(), dbname='parkweave'))
            with owner.connect() as c:
                c.execute('SET TRANSACTION READ ONLY')
                identity = c.execute('SELECT system_identifier FROM pg_control_system()').fetchone()
                version = c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']
                role = c.execute("SELECT rolsuper,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname='parkweave_app'").fetchone()
                if (str(identity['system_identifier']) != marker.get('system_identifier') or version != 32 or
                        role is None or any(role.values())):
                    raise Denied('retained database identity/schema/app-role mismatch; no repair')
            # No seed, migrate, issued receipt reconstruction, or grants here.
            yield root, make_conninfo(owner.dsn, user='parkweave_app')
        finally:
            server.cleanup()


def serve(value, port):
    if not 1024 <= port <= 65535:
        raise Denied('port must be 1024..65535')
    # Check before opening the database. Never adopt a pre-existing listener.
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('127.0.0.1', port))
    with retained_database(value) as (root, dsn):
        env = minimal_environment(os.environ, PYTHONPATH=str(REPO / 'src') + ':' + str(REPO),
                                  PARKWEAVE_DSN=dsn, PARKWEAVE_MODE='LOCAL')
        children = []
        with (root / '.runtime/entry.log').open('a') as log:
            try:
                for command in (
                    ['uvicorn', 'scripts.local_case_entry_app:app', '--factory', '--host', '127.0.0.1', '--port', str(port)],
                    ['parkweave.worker'],
                ):
                    children.append(subprocess.Popen([sys.executable, '-m', *command], cwd=REPO,
                                                     env=env, stdout=log, stderr=log))
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if any(p.poll() is not None for p in children):
                        raise RuntimeError('owned child exited; inspect private entry.log')
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=.3) as response:
                            health = json.load(response)
                        if (health.get('process_id') == children[0].pid and health.get('schema') == 32 and
                                health.get('data') == 'SYNTHETIC' and health.get('execution_mode') == 'LOCAL'):
                            break
                    except (OSError, ValueError):
                        pass
                    time.sleep(.1)
                else:
                    raise RuntimeError('owned API readiness timeout')
                print(json.dumps(dict(url=f'http://127.0.0.1:{port}/local-entry', state_dir=str(root),
                                      api_pid=children[0].pid, worker_pid=children[1].pid,
                                      scope='ISOLATED_SYNTHETIC_LOCAL_CASE_ONLY', real_model=False)), flush=True)
                while all(p.poll() is None for p in children):
                    time.sleep(.25)
                raise RuntimeError('owned child exited; state retained')
            finally:
                try:
                    stop_children(children)
                except DemoStopUnconfirmed:
                    (root / 'stop-unconfirmed.json').write_text(json.dumps({'blocked': 'OWNED_CHILD_STOP_UNCONFIRMED'}) + '\n')
                    raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('setup-synthetic', 'serve'))
    parser.add_argument('--state-dir')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args(argv)
    if (args.command == 'serve') != bool(args.state_dir):
        parser.error('serve requires --state-dir; setup-synthetic creates a fresh directory')
    previous = signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if args.command == 'setup-synthetic':
            print(json.dumps(dict(state_dir=str(setup()), scope='ISOLATED_SYNTHETIC_SETUP_ONLY')), flush=True)
        else:
            serve(args.state_dir, args.port)
        return 0
    except KeyboardInterrupt:
        return 0
    except (Denied, OSError, ValueError, RuntimeError, subprocess.SubprocessError, psycopg.Error) as exc:
        # Never print connection strings, tokens, or raw exception payloads.
        detail = str(exc) if isinstance(exc, Denied) else type(exc).__name__
        print('LOCAL_ENTRY_BLOCKED: ' + detail + '; state retained; no automatic repair', file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    raise SystemExit(main())
