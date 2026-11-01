"""Persistent Linux local material product, using the original database and APIs.

Explicit installation only, independently chosen profile account passwords, no model,
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
import threading
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
from parkweave.local_identity import LocalSessionVault, LocalIdentityStorageUnavailable, password_bytes, SAMPLE_SCHEMA, SAMPLE_ROLES
from parkweave.process_env import minimal_environment
from parkweave.store import Store, Denied
from parkweave.local_installation import PersistentInstallation, create_database, private_parent, STATE
from parkweave.local_workspace import full_workspace_page
from scripts import material_only_demo as material


class Login(BaseModel):
    model_config = ConfigDict(extra='forbid')
    role: str
    password: SecretStr


class LocalSetupFailure(Denied):
    def __init__(self,code,message):
        self.code,self.message=code,message
        super().__init__(code)


def private_password(prompt):
    # getpass normally falls back to echoing stdin if terminal protection is
    # unavailable. That fallback is not acceptable for installation secrets.
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            return getpass.getpass(prompt)
    except EOFError:
        raise LocalSetupFailure('PASSWORD_INPUT_INTERRUPTED',
            '密码输入已中断，请在交互终端重新运行 install；本次尚未新建安装。') from None
    except OSError:
        raise LocalSetupFailure('PRIVATE_TERMINAL_UNAVAILABLE',
            '无法安全读取终端密码，请检查终端后重新运行 install；本次尚未新建安装。') from None


def application(path, marker, port):
    store = Store(material.dsn(path, application=True))
    sample_mode=marker.get('schema')==SAMPLE_SCHEMA
    if sample_mode:
        from parkweave import local_sample
        app=local_sample.application(store,path,marker)
        labels=local_sample.LABELS
    else:
        app = create_app(store)
        labels=[('enterprise','企业 · 提交资料与确认'),('specialist','专员 · 补正与人工核对')]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1'])
    # The focused local page uses the very same original API and permissions.
    app.router.routes[:] = [route for route in app.router.routes if getattr(route, 'path', None) != '/']
    failures = []; login_lock = threading.Lock()
    original_validation = app.exception_handlers[RequestValidationError]

    @app.exception_handler(RequestValidationError)
    async def private_login_validation(request, error):
        if request.url.path == '/api/local/session':
            return JSONResponse({'detail':'invalid local login'}, status_code=422)
        return await original_validation(request, error)

    @app.get('/', response_class=HTMLResponse)
    def index():
        if sample_mode:return local_sample.workspace_page(Path(__file__).parents[1]/'src/parkweave',marker)
        return Path(__file__).parents[1].joinpath('src/parkweave/local_preparation_web.html').read_text()

    @app.get('/workspace', response_class=HTMLResponse)
    def original_workspace():
        if sample_mode:return local_sample.workspace_page(Path(__file__).parents[1]/'src/parkweave',marker)
        return full_workspace_page(Path(__file__).parents[1]/'src/parkweave',labels)

    @app.get('/materials', response_class=HTMLResponse)
    def material_workspace():
        return Path(__file__).parents[1].joinpath('src/parkweave/local_preparation_web.html').read_text()

    if sample_mode:
        from fastapi import Header
        @app.get('/api/local-sample/resources')
        def sample_resources(authorization: str | None=Header(default=None)):
            if not authorization or not authorization.startswith('Bearer '):raise HTTPException(403,'local identity required')
            return local_sample.resource_directory(store,authorization[7:])
        @app.get('/local-sample-resources.js')
        def sample_resources_client():
            return Response(Path(__file__).parents[1].joinpath('src/parkweave/local_sample_resources.js').read_text(),media_type='text/javascript')

    @app.get('/local-workspace-login.js')
    def workspace_login_client():
        return Response(Path(__file__).parents[1].joinpath('src/parkweave/local_workspace_login.js').read_text(),
                        media_type='text/javascript')

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
        # Match the original workspace's bounded password work across tabs.
        # Reserve the single password attempt before scrypt, not after failure.
        if not login_lock.acquire(blocking=False):
            raise HTTPException(429, '请稍后再试')
        try:
            now = time.monotonic()
            failures[:] = [t for t in failures if now - t < 60]
            if len(failures) >= 6:
                raise HTTPException(429, '请稍后再试')
            try:
                bearer = LocalSessionVault.unlock(path, marker, data.role, data.password.get_secret_value())
                with store.connect() as connection:
                    actor = store.auth(connection, bearer, lock=True)
                    expected = local_sample.ROLES.get(data.role) if sample_mode else {'enterprise':'enterprise_operator','specialist':'park_specialist'}.get(data.role)
                    if actor['id'] != marker['ids'][data.role] or actor['role'] != expected:
                        raise Denied('current local identity required')
                from parkweave.local_identity import canonical
                installation_id = sha256(canonical(LocalSessionVault.binding(path, marker))).hexdigest()
                return dict(bearer=bearer, role=actor['role'], actor_id=actor['id'], installation_id=installation_id,
                    actor={name:actor[name] for name in ('id','park_id','org_id','role')},
                    scope=local_sample.PROFILE if sample_mode else 'SYNTHETIC_LOCAL_PREPARATION_ONLY')
            except LocalIdentityStorageUnavailable:
                return JSONResponse(dict(code='LOCAL_IDENTITY_STORAGE_UNAVAILABLE',
                    detail='本地账户资料暂不可读取。请停止工作台；若已有原安装备份，可恢复原受保护身份文件后重开登录。无原备份时请保留目录交维护方处理，不要新建安装覆盖原资料。',
                    recovery='RESTORE_ORIGINAL_SEALED_IDENTITIES',automatic_reset=False),status_code=503)
            except Denied:
                failures.append(now)
                raise HTTPException(403, '账号不可用或密码不正确') from None
        finally:
            login_lock.release()

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
            if provider.roles==SAMPLE_ROLES:
                from parkweave import local_sample
                local_sample.initialize(owner,provider)
                sample=local_sample.create_inputs(path,material.dsn(path,application=True))
                with owner.connect() as c:
                    identity=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()
                    oid=c.execute("SELECT oid::bigint FROM pg_database WHERE datname='parkweave'").fetchone()['oid']
                    snapshot=material.authority(c)
                marker=dict(schema=SAMPLE_SCHEMA,**material.source_binding(),system_identifier=identity['system_identifier'],
                    database_oid=oid,schema_version=32,authority=snapshot,ids=local_sample.IDS,
                    sql_rights=local_sample.SQL_RIGHTS,session_expiry='NONE_MANUAL_REVOCATION_REQUIRED',sample=sample)
                provider.publish(path,marker)
                marker.update(session_storage='PASSWORD_SEALED_SEPARATE_ROLES_V1',runtime_source_sha256=runtime_source_binding())
                material.dump(path/'state.json',marker)
            else:material.populate(path, owner, session_provider=provider, persistent=True)
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


@contextmanager
def _loopback_listener(port):
    import socket
    with socket.socket() as listener:
        # Reuse this stopped server's TIME_WAIT connections, while still
        # refusing any live listener. Never use SO_REUSEPORT or take over
        # another process. Listen before PG starts so this original socket
        # owns the endpoint throughout startup, even with REUSEADDR.
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind(('127.0.0.1', port))
        listener.listen()
        yield listener


def serve(value, port):
    if not 1024 <= port <= 65535:
        raise Denied('unprivileged loopback port required')
    with installation_entry(value) as (path, installation):
        if (path / 'stop-unconfirmed').exists() or (path / 'sessions.json').exists():
            raise Denied('sealed, previously stopped local installation required')
        marker = json.loads((path / 'state.json').read_text())
        if (marker.get('session_storage') != 'PASSWORD_SEALED_SEPARATE_ROLES_V1'
                or marker['schema'] not in (('parkweave-local-material-installation/1',SAMPLE_SCHEMA) if installation else ('parkweave-material-only-demo/1',))
                or marker.get('runtime_source_sha256') != runtime_source_binding()
                or marker['src_tree'] != material.source_binding()['src_tree']
                or marker['bootstrap_sha256'] != material.source_binding()['bootstrap_sha256']):
            raise Denied('frozen installation source changed; no repair or migration')
        # Bind before starting any child: occupied addresses are never taken over.
        with _loopback_listener(port) as listener:
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
                if marker['schema']==SAMPLE_SCHEMA:
                    from parkweave.local_sample import environment
                    env.update(environment(path,marker))
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
                        print(json.dumps(dict(url=f'http://127.0.0.1:{port}', scope='LOCAL_SYNTHETIC_COLLABORATION_V1' if marker['schema']==SAMPLE_SCHEMA else 'SYNTHETIC_LOCAL_PREPARATION_ONLY',
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
    parser.add_argument('--sample-collaboration',action='store_true',help='install only: explicit 7-day SYNTHETIC services, two resources and four separately sealed accounts')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if sys.platform != 'linux' or os.geteuid() == 0:
        parser.error('an unprivileged Linux process is required; Windows is not activated')
    if (args.command == 'start') != bool(args.state_dir):
        parser.error('start requires existing --state-dir; install always creates a new private directory')
    if args.parent and args.command != 'install':
        parser.error('--parent is only valid for install')
    if args.sample_collaboration and args.command!='install':parser.error('--sample-collaboration is only valid for install')
    try:
        if args.command == 'install':
            future_parent=Path(args.parent).absolute() if args.parent else material.ROOT/'.runtime/local-product'
            if len(os.fsencode(future_parent/('pw-'+'0'*32)/'socket/.s.PGSQL.5432'))>107:
                raise LocalSetupFailure('INSTALL_PARENT_TOO_LONG',
                    '安装父目录路径过长，请使用更短的本人私有目录；本次尚未读取密码或新建安装。')
            if args.parent:
                try:private_parent(args.parent)
                except (Denied,OSError):
                    raise LocalSetupFailure('INSTALL_PARENT_UNAVAILABLE',
                        '请提供已有的本人私有安装父目录，再重新运行 install；本次尚未读取密码或新建安装。') from None
            passwords = {}
            labels=[('enterprise','企业'),('specialist','专员'),('executor','执行者'),('resource-admin','资源管理员')] if args.sample_collaboration else [('enterprise','企业'),('specialist','专员')]
            for role, label in labels:
                passwords[role] = private_password(f'{label}独立密码（至少12字符）: ')
                try:password_bytes(passwords[role])
                except Denied:
                    raise LocalSetupFailure('PASSWORD_LENGTH',
                        '每个账号的密码须为12–256个字符，请重新运行 install；本次尚未新建安装。') from None
                if passwords[role] != private_password(f'再次输入{label}密码: '):
                    raise LocalSetupFailure('PASSWORD_CONFIRMATION',
                        '两次密码输入不一致，请重新运行 install；本次尚未新建安装。')
            if len(set(passwords.values()))!=len(passwords):
                raise LocalSetupFailure('PASSWORD_DISTINCT',
                    '每个账号须使用不同的独立密码，请重新运行 install；本次尚未新建安装。')
            provider = LocalSessionVault(passwords,sample_collaboration=args.sample_collaboration)
            passwords.clear()
            path = install(provider, args.parent)
            print(json.dumps(dict(state_dir=str(path), installed='LOCAL_SYNTHETIC_COLLABORATION_ONLY' if args.sample_collaboration else 'LOCAL_SYNTHETIC_MATERIAL_ONLY',
                next_command='start --state-dir ' + str(path), passwords_stored=False)), flush=True)
        else:
            serve(args.state_dir, args.port)
    except KeyboardInterrupt:
        return 0
    except LocalSetupFailure as error:
        print('LOCAL_PRODUCT_REFUSED: '+error.code+'; '+error.message,file=sys.stderr)
        return 1
    except getpass.GetPassWarning:
        print('LOCAL_PRODUCT_REFUSED: PRIVATE_TERMINAL_REQUIRED; 请在支持隐藏密码输入的交互终端重新安装，不使用明文参数或重定向输入；本次未新建安装。',file=sys.stderr)
        return 1
    except Exception as error:
        # No exception values or local frame dumps containing password/session material.
        print('LOCAL_PRODUCT_REFUSED: ' + type(error).__name__ + '; existing state retained', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
