"""Persistent Linux local material product, using the original database and APIs.

Explicit installation only, two independently chosen role passwords, no model,
real park data, system services, native Windows setters or public listener.
"""
import argparse
import getpass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import psycopg
from psycopg.rows import dict_row
import uvicorn
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware

from parkweave.api import create_app
from parkweave.local_identity import LocalSessionVault
from parkweave.process_env import minimal_environment
from parkweave.store import Store, Denied
from scripts import material_only_demo as material


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: str
    password: SecretStr


def application(path, marker, port):
    store = Store(material.dsn(path, application=True))
    app = create_app(store)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1'])
    # The focused local page uses the very same original API and permissions.
    app.router.routes[:] = [route for route in app.router.routes if getattr(route, 'path', None) != '/']
    failures = []

    @app.get('/', response_class=HTMLResponse)
    def index():
        return Path(__file__).parents[1].joinpath('src/parkweave/local_preparation_web.html').read_text()

    @app.get('/workspace', response_class=HTMLResponse)
    def original_workspace():
        return Path(__file__).parents[1].joinpath('src/parkweave/web.html').read_text()

    @app.post('/api/local/session')
    def login(data: Login, request: Request):
        # No cookie/session ambient authority; only an explicit same-origin POST.
        if (not request.client or request.client.host != '127.0.0.1'
                or request.headers.get('origin') != f'http://127.0.0.1:{port}'):
            raise HTTPException(403, 'local same-origin login required')
        now = time.monotonic()
        failures[:] = [t for t in failures if now - t < 60]
        if len(failures) >= 6:
            raise HTTPException(429, '请稍后再试')
        try:
            bearer = LocalSessionVault.unlock(path, marker, data.role, data.password.get_secret_value())
            with store.connect() as connection:
                actor = store.auth(connection, bearer, lock=True)
                expected = 'enterprise_operator' if data.role == 'enterprise' else 'park_specialist'
                if actor['id'] != marker['ids'][data.role] or actor['role'] != expected:
                    raise Denied('current local identity required')
            return dict(bearer=bearer, role=actor['role'], actor_id=actor['id'], scope='SYNTHETIC_LOCAL_PREPARATION_ONLY')
        except Denied:
            failures.append(now)
            raise HTTPException(403, '账号不可用或密码不正确') from None

    return app


def serve(value, port):
    if not 1024 <= port <= 65535:
        raise Denied('unprivileged loopback port required')
    with material.locked(value) as path:
        if (path / 'stop-unconfirmed').exists() or (path / 'sessions.json').exists():
            raise Denied('sealed, previously stopped local installation required')
        marker = json.loads((path / 'state.json').read_text())
        if (marker.get('session_storage') != 'PASSWORD_SEALED_SEPARATE_ROLES_V1'
                or marker['schema'] != 'parkweave-material-only-demo/1'
                or marker['src_tree'] != material.source_binding()['src_tree']
                or marker['bootstrap_sha256'] != material.source_binding()['bootstrap_sha256']):
            raise Denied('frozen installation source changed; no repair or migration')
        # Bind before starting any child: occupied addresses are never taken over.
        import socket
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', port))
            with material.postgres(path):
                with psycopg.connect(material.dsn(path), row_factory=dict_row) as connection:
                    connection.execute('SET TRANSACTION READ ONLY')
                    identity = connection.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()
                    oid = connection.execute("SELECT oid::bigint FROM pg_database WHERE datname='parkweave'").fetchone()['oid']
                    version = connection.execute('SELECT max(version) v FROM schema_version').fetchone()['v']
                    if (identity['system_identifier'] != marker['system_identifier'] or oid != marker['database_oid']
                            or version != 32 or material.authority(connection) != marker['authority']):
                        raise Denied('retained database or permissions changed; no automatic repair')
                env = minimal_environment(os.environ, PYTHONPATH=str(material.ROOT / 'src'),
                    PYTHONDONTWRITEBYTECODE='1', PARKWEAVE_DSN=material.dsn(path, application=True), PARKWEAVE_MODE='LOCAL')
                with (path / 'logs/worker.log').open('a') as log:
                    worker = subprocess.Popen([sys.executable, '-B', '-m', 'parkweave.worker'],
                        cwd=material.ROOT, env=env, stdout=log, stderr=log)
                    try:
                        server = uvicorn.Server(uvicorn.Config(application(path, marker, port),
                            host='127.0.0.1', port=port, access_log=False, log_level='warning'))
                        print(json.dumps(dict(url=f'http://127.0.0.1:{port}', scope='SYNTHETIC_LOCAL_PREPARATION_ONLY',
                            sessions='PASSWORD_SEALED_SEPARATE_ROLES_V1', data_retained=True)), flush=True)
                        server.run(sockets=[listener])
                    finally:
                        try:
                            from scripts.linux_fixture_server import stop_children
                            stop_children([worker])
                        except BaseException:
                            (path / 'stop-unconfirmed').touch(exist_ok=True)
                            raise


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('install', 'start'))
    parser.add_argument('--state-dir')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() == 0:
        parser.error('an unprivileged Linux process is required; Windows is not activated')
    if (args.command == 'start') != bool(args.state_dir):
        parser.error('start requires existing --state-dir; install always creates a new private directory')
    try:
        if args.command == 'install':
            passwords = {}
            for role, label in [('enterprise', '企业'), ('specialist', '专员')]:
                passwords[role] = getpass.getpass(f'{label}独立密码（至少12字符）: ')
                if passwords[role] != getpass.getpass(f'再次输入{label}密码: '):
                    raise Denied('password confirmation differs')
            provider = LocalSessionVault(passwords)
            passwords.clear()
            path = material.setup(session_provider=provider)
            print(json.dumps(dict(state_dir=str(path), installed='LOCAL_SYNTHETIC_MATERIAL_ONLY',
                next_command='start --state-dir ' + str(path), passwords_stored=False)), flush=True)
        else:
            serve(args.state_dir, args.port)
    except KeyboardInterrupt:
        return 0
    except Exception as error:
        # No exception values or local frame dumps containing password/session material.
        print('LOCAL_PRODUCT_REFUSED: ' + type(error).__name__ + '; existing state retained', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
