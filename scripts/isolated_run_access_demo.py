"""Explicit fresh Linux run-access demo; API retains creation proof in process.

The original LOCAL worker is the only application subprocess. No production
factory, persistent runtime reuse, fixture assignments, or live model calls.
"""
from __future__ import annotations

import argparse
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import threading
import time

from psycopg.conninfo import make_conninfo
import uvicorn

from parkweave.api import create_app
from parkweave.process_env import minimal_environment
from parkweave.store import Store, digest
from scripts.linux_fixture_server import demo_database, stop_children, DemoStopUnconfirmed

REPO = Path(__file__).resolve().parents[1]
ENTERPRISES = ('fixture-a', 'fixture-b', 'fixture-c')
APPROVERS = frozenset('prep-specialist-' + identity for identity in ENTERPRISES)
BUSINESS_TABLES = ('runs', 'cases', 'preparations', 'run_assignments',
                   'service_dispatches', 'service_receipt_steps', 'service_step_receipts')


def private_json(path: Path, value: object) -> None:
    """Exclusive output in this invocation's private temporary directory."""
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def seed_fixtures(root: Path, owner: Store) -> tuple[dict[str, str], dict[str, int]]:
    """Original synthetic registry setup; zero Run, Case, or assignment creation."""
    from parkweave.preparation import seed_synthetic as seed_preparation
    from parkweave.resource_holds import seed_synthetic as seed_resources
    from parkweave.resource_combinations import seed_synthetic as seed_combinations

    with owner.connect() as connection:
        connection.execute((REPO / 'src/parkweave/roles.sql').read_text(encoding='utf-8'))
    enterprise_tokens = {identity: secrets.token_urlsafe(32) for identity in ENTERPRISES}
    specialist_tokens = {identity: secrets.token_urlsafe(32) for identity in sorted(APPROVERS)}
    executor_tokens = {'receipt-executor-' + identity: secrets.token_urlsafe(32)
                       for identity in ENTERPRISES}
    owner.seed(enterprise_tokens)
    seed_preparation(owner, specialist_tokens)
    with owner.connect() as connection:
        for identity, token in executor_tokens.items():
            enterprise = identity.removeprefix('receipt-executor-')
            principal = connection.execute('SELECT park_id,org_id FROM principals WHERE id=%s',
                                           (enterprise,)).fetchone()
            connection.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',
                               (identity, digest(token), principal['park_id'], principal['org_id'],
                                'service_executor'))
            connection.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) '
                               'VALUES(%s,%s,%s,%s)',
                               (identity, 'READ', principal['park_id'], principal['org_id']))
    seed_resources(owner)
    seed_combinations(owner)
    with owner.connect() as connection:
        counts = {table: connection.execute('SELECT count(*) AS n FROM ' + table).fetchone()['n']
                  for table in BUSINESS_TABLES}
    if any(counts.values()):
        raise RuntimeError('Fresh isolated demo requires zero initial business records')
    private_json(root / 'synthetic-sessions.json', enterprise_tokens)
    private_json(root / 'preparation-sessions.json', specialist_tokens)
    private_json(root / 'receipt-sessions.json', executor_tokens)
    tokens = {**enterprise_tokens, **specialist_tokens, **executor_tokens}
    return tokens, counts


def wait_ready(server: uvicorn.Server, api_thread: threading.Thread,
               worker: subprocess.Popen, port: int, errors: list[BaseException]) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if errors or not api_thread.is_alive() or worker.poll() is not None:
            raise RuntimeError('Owned isolated demo stopped before readiness; inspect private worker.log')
        if server.started:
            connection = HTTPConnection('127.0.0.1', port, timeout=.5)
            try:
                connection.request('GET', '/health')
                response = connection.getresponse()
                health = json.loads(response.read()) if response.status == 200 else None
                if (health and health.get('process_id') == os.getpid()
                        and health.get('schema') == 25 and health.get('data') == 'SYNTHETIC'
                        and health.get('execution_mode') == 'LOCAL'):
                    return
            except (OSError, ValueError):
                pass
            finally:
                connection.close()
        time.sleep(.1)
    raise RuntimeError('Owned isolated API readiness not confirmed')


def stop_api(server: uvicorn.Server, api_thread: threading.Thread) -> None:
    server.should_exit = True
    api_thread.join(timeout=12)
    if api_thread.is_alive():
        server.force_exit = True
        api_thread.join(timeout=3)
    if api_thread.is_alive():
        raise DemoStopUnconfirmed('Owned in-process API stop unconfirmed; temporary fixture retained')


def serve(root: Path, owner: Store, args: argparse.Namespace) -> None:
    # Imported only after BOTH explicit CLI flags and fresh receipt creation.
    from parkweave.isolated_run_access import IsolatedRunAccessBridge

    tokens, initial_counts = seed_fixtures(root, owner)
    bridge = IsolatedRunAccessBridge(owner, owner._case_fact_fixture_receipt,
                                    root / 'demo.run-access.candidate.sqlite3',
                                    approver_ids=set(APPROVERS), enabled_for_isolated_tests=True)
    app_store = Store(make_conninfo(owner.dsn, user='parkweave_app'), mode='LOCAL')
    bridge.attach_store(app_store)
    if args.enable_isolated_local_execution:
        from parkweave.isolated_local_execution import IsolatedLocalExecutor
        IsolatedLocalExecutor(bridge, enabled_for_isolated_tests=True).attach_store(app_store)
    server = uvicorn.Server(uvicorn.Config(create_app(app_store), host='127.0.0.1', port=args.port,
                                          log_config=None, access_log=False, log_level='warning',
                                          timeout_graceful_shutdown=10))
    errors: list[BaseException] = []

    def api_main() -> None:
        try:
            server.run()
        except BaseException as error:
            errors.append(error)

    api_thread = threading.Thread(target=api_main, name='isolated-run-access-api', daemon=True)
    children: list[subprocess.Popen] = []
    env = minimal_environment(os.environ, PARKWEAVE_DSN=app_store.dsn,
                              PARKWEAVE_MODE='LOCAL', PYTHONPATH=str(REPO / 'src'))
    with (root / 'worker.log').open('x', encoding='utf-8') as log:
        try:
            api_thread.start()
            worker = subprocess.Popen([sys.executable, '-m', 'parkweave.worker'],
                                      env=env, stdout=log, stderr=log, cwd=REPO)
            children.append(worker)
            wait_ready(server, api_thread, worker, args.port, errors)
            evidence = {'environment': 'Linux isolated synthetic demo', 'temporary_fixture': True,
                        'runtime_directory': str(root), 'api_pid': os.getpid(), 'worker_pid': worker.pid,
                        'api_same_process_creation_proof': True, 'port': args.port,
                        'data': 'SYNTHETIC', 'live_model': 'DISABLED', 'execution_mode': 'LOCAL',
                        'isolated_run_access_enabled': True, 'deployment_enabled': False,
                        'isolated_local_execution_enabled': args.enable_isolated_local_execution,
                        'initial_business_counts': initial_counts, 'max_seconds': args.max_seconds}
            private_json(root / 'smoke-environment.json', evidence)
            private_json(root / 'fixture-info.json', {'environment': evidence, 'tokens': tokens,
                         'approver_ids': sorted(APPROVERS), 'token_files': {
                             'enterprise': str(root / 'synthetic-sessions.json'),
                             'specialist': str(root / 'preparation-sessions.json'),
                             'executor': str(root / 'receipt-sessions.json')}})
            print(json.dumps(evidence), flush=True)
            deadline = time.monotonic() + args.max_seconds
            while time.monotonic() < deadline:
                if errors or not api_thread.is_alive() or worker.poll() is not None:
                    raise RuntimeError('Owned isolated demo process stopped unexpectedly')
                time.sleep(.25)
        except KeyboardInterrupt:
            pass
        finally:
            # Both shutdown paths run even if one cannot confirm termination.
            failures: list[BaseException] = []
            if api_thread.ident is not None:
                try:
                    stop_api(server, api_thread)
                except BaseException as error:
                    failures.append(error)
            try:
                stop_children(children)
            except BaseException as error:
                failures.append(error)
            if failures:
                raise DemoStopUnconfirmed('Owned isolated demo stop unconfirmed; temporary fixture retained') from failures[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--enable-isolated-run-access', action='store_true',
                        help='explicitly enable the isolated synthetic bridge in this API process')
    parser.add_argument('--fresh-fixture', action='store_true',
                        help='required: create and later remove only a new private temporary fixture')
    parser.add_argument('--enable-isolated-local-execution', action='store_true',
                        help='explicitly enable only the owned synthetic handoff-report adapter')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--max-seconds', type=int, default=3600)
    args = parser.parse_args()
    if not args.enable_isolated_run_access or not args.fresh_fixture:
        parser.error('--enable-isolated-run-access and --fresh-fixture are both required')
    if not 1024 <= args.port <= 65535:
        parser.error('port must be 1024..65535')
    if not 1 <= args.max_seconds <= 28800:
        parser.error('max-seconds must be 1..28800')
    if sys.platform != 'linux':
        parser.error('Linux isolated synthetic fixture only')

    def request_stop(signum, frame):
        raise KeyboardInterrupt

    previous = signal.signal(signal.SIGTERM, request_stop)
    try:
        with demo_database(fresh=True) as (root, owner):
            serve(root, owner, args)
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    main()
