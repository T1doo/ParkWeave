"""Persistent Linux local material product, using the original database and APIs.

Explicit installation only, two independently chosen role passwords, no model,
real park data, system services, native Windows setters or public listener.
"""
import argparse
import asyncio
from contextlib import asynccontextmanager, contextmanager
import getpass
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import warnings

import psycopg
from psycopg.rows import dict_row
import uvicorn
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware

from parkweave.api import create_app
from parkweave.local_identity import LocalSessionVault
from parkweave.process_env import minimal_environment
from parkweave.store import Store, Denied
from parkweave.local_installation import PersistentInstallation, create_database, private_parent, STATE
from scripts import material_only_demo as material


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: str
    password: SecretStr


def private_password(prompt):
    # getpass normally falls back to echoing stdin if terminal protection is
    # unavailable. That fallback is not acceptable for installation secrets.
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        return getpass.getpass(prompt)


def application(path, marker, port):
    store = Store(material.dsn(path, application=True))
    app = create_app(store)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1'])
    # The focused local page uses the very same original API and permissions.
    app.router.routes[:] = [route for route in app.router.routes if getattr(route, 'path', None) != '/']
    failures = []
    original_validation = app.exception_handlers[RequestValidationError]

    @app.exception_handler(RequestValidationError)
    async def private_login_validation(request, error):
        if request.url.path == '/api/local/session':
            return JSONResponse({'detail':'invalid local login'}, status_code=422)
        return await original_validation(request, error)

    @app.get('/', response_class=HTMLResponse)
    def index():
        return Path(__file__).parents[1].joinpath('src/parkweave/local_preparation_web.html').read_text()

    @app.get('/workspace', response_class=HTMLResponse)
    def original_workspace():
        return Path(__file__).parents[1].joinpath('src/parkweave/web.html').read_text()

    @app.get('/local-command-pending.js')
    def pending_client():
        return Response(Path(__file__).parents[1].joinpath('src/parkweave/local_command_pending.js').read_text(),
                        media_type='text/javascript')

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
            from parkweave.local_identity import canonical
            installation_id = sha256(canonical(LocalSessionVault.binding(path, marker))).hexdigest()
            return dict(bearer=bearer, role=actor['role'], actor_id=actor['id'], installation_id=installation_id,
                actor={name:actor[name] for name in ('id','park_id','org_id','role')},
                scope='SYNTHETIC_LOCAL_PREPARATION_ONLY')
        except Denied:
            failures.append(now)
            raise HTTPException(403, '账号不可用或密码不正确') from None

    return app


def runtime_source_binding():
    """Bind actual runtime bytes, including uncommitted edits, not just HEAD."""
    root = material.ROOT
    files = [p for p in (root / 'src' / 'parkweave').rglob('*')
             if p.suffix in ('.py', '.sql', '.html', '.json', '.js')]
    files.extend([Path(__file__), Path(material.__file__)])
    digest = sha256()
    for path in sorted(files):
        if path.is_symlink() or path.resolve() != path.absolute() or not path.is_file():
            raise Denied('unaliased original runtime source files required')
        digest.update(str(path.relative_to(root)).encode() + b'\0')
        digest.update(sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def install(provider, parent=None):
    if type(provider) is not LocalSessionVault:
        raise Denied('exact sealed local identity provider required before installation')
    if parent is None:
        parent = material.ROOT
        for leaf in ('.runtime', 'local-product'):
            parent = parent / leaf
            try:
                parent.mkdir(mode=0o700)
            except FileExistsError:
                pass
            private_parent(parent)
    with PersistentInstallation.create_new(parent) as lease:
        path = lease.path
        print(json.dumps(dict(setup_state_dir=str(path), persistent_directory=True)), flush=True)
        lease.initialize()
        with lease.postgres():
            owner = create_database(lease)
            material.populate(path, owner, session_provider=provider, persistent=True)
        lease.finish_new()
        return path


@contextmanager
def installation_entry(value):
    path = Path(value).absolute()
    if (path / STATE).exists():
        with PersistentInstallation.open_existing(path) as lease:
            yield path, lease
    else:
        # Compatibility reads of the previous temporary candidate. No adoption
        # of a long-lived directory without the new original journal/lock.
        with material.locked(value) as path:
            yield path, None


def serve(value, port):
    if not 1024 <= port <= 65535:
        raise Denied('unprivileged loopback port required')
    with installation_entry(value) as (path, installation):
        if (path / 'stop-unconfirmed').exists() or (path / 'sessions.json').exists():
            raise Denied('sealed, previously stopped local installation required')
        marker = json.loads((path / 'state.json').read_text())
        if (marker.get('session_storage') != 'PASSWORD_SEALED_SEPARATE_ROLES_V1'
                or marker['schema'] != ('parkweave-local-material-installation/1' if installation else 'parkweave-material-only-demo/1')
                or marker.get('runtime_source_sha256') != runtime_source_binding()
                or marker['src_tree'] != material.source_binding()['src_tree']
                or marker['bootstrap_sha256'] != material.source_binding()['bootstrap_sha256']):
            raise Denied('frozen installation source changed; no repair or migration')
        # Bind before starting any child: occupied addresses are never taken over.
        import socket
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', port))
            with (installation.postgres() if installation else material.postgres(path)):
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
                        original_lifespan = server.config.app.router.lifespan_context

                        @asynccontextmanager
                        async def monitored_lifespan(app):
                            async def watch_worker():
                                while worker.poll() is None:
                                    await asyncio.sleep(.25)
                                server.should_exit = True
                            async with original_lifespan(app):
                                monitor = asyncio.create_task(watch_worker())
                                try:
                                    yield
                                finally:
                                    monitor.cancel()
                                    await asyncio.gather(monitor, return_exceptions=True)
                        server.config.app.router.lifespan_context = monitored_lifespan
                        print(json.dumps(dict(url=f'http://127.0.0.1:{port}', scope='SYNTHETIC_LOCAL_PREPARATION_ONLY',
                            sessions='PASSWORD_SEALED_SEPARATE_ROLES_V1', data_retained=True)), flush=True)
                        try:
                            server.run(sockets=[listener])
                        except KeyboardInterrupt:
                            # Uvicorn re-raises a handled SIGINT/SIGTERM after
                            # draining HTTP. Owned worker/PG cleanup still runs.
                            pass
                        if worker.poll() is not None:
                            raise Denied('owned worker exited; no partial running service')
                    finally:
                        try:
                            from scripts.linux_fixture_server import stop_children
                            stop_children([worker])
                        except BaseException:
                            (path / 'stop-unconfirmed').touch(exist_ok=True)
                            raise


def main():
    os.umask(0o077)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('install', 'start'))
    parser.add_argument('--state-dir')
    parser.add_argument('--parent', help='existing private installation parent; install only')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() == 0:
        parser.error('an unprivileged Linux process is required; Windows is not activated')
    if (args.command == 'start') != bool(args.state_dir):
        parser.error('start requires existing --state-dir; install always creates a new private directory')
    if args.parent and args.command != 'install':
        parser.error('--parent is only valid for install')
    try:
        if args.command == 'install':
            passwords = {}
            for role, label in [('enterprise', '企业'), ('specialist', '专员')]:
                passwords[role] = private_password(f'{label}独立密码（至少12字符）: ')
                if passwords[role] != private_password(f'再次输入{label}密码: '):
                    raise Denied('password confirmation differs')
            provider = LocalSessionVault(passwords)
            passwords.clear()
            path = install(provider, args.parent)
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
