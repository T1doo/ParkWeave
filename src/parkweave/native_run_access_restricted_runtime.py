"""Restricted Linux writer implementation. Import and CLI default to closed.

Real entry requires a sealed host-owned descriptor from the approved host adapter.
Dependency-injected engine tests are not OS/PG installation or startup evidence.
"""
import argparse
import re
import socket
import struct
import threading
from uuid import UUID

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row

from . import native_run_access as native, native_run_access_preflight as preflight
from . import native_run_access_writer as writer
from .store import Store, _AccessConnection, Denied

EXTRA_CHECKS = frozenset({'role_flags','membership','database_extra','ownership',
    'table_extra','column_extra','other_schema_write','routine_extra','routine_grant','temporary_namespace',
    'app_control','app_protected_write'})


def required_privileges(parent_lock_column):
    # Live schema version comparison is new; never grant it here.
    return [*preflight.required_privileges(parent_lock_column),
            ('writer', 'SELECT', 'schema_version', None)]


def private_connection_dsn(value, policy):
    """Explicit single endpoint/password only; no service, options or discovery."""
    try:
        parsed = conninfo_to_dict(value)
        if (set(parsed) != {'host', 'port', 'dbname', 'user', 'password'} or
                not parsed['password'] or (parsed['host'], int(parsed['port']),
                parsed['dbname'], parsed['user']) != (policy.database_host,
                policy.database_port, policy.database_name, policy.writer_role)):
            raise ValueError()
    except (TypeError, ValueError, psycopg.Error):
        raise Denied('exact private restricted connection input required; values not echoed') from None
    return value


def _identity(c):
    return c.execute("""SELECT d.oid database_oid,d.datname database_name,
        pg_catalog.pg_get_userbyid(d.datdba) owner_name,
        current_user current_name,session_user session_name,
        (SELECT system_identifier::text FROM pg_catalog.pg_control_system()) system_identifier
        FROM pg_catalog.pg_database d WHERE d.datname=pg_catalog.current_database()""").fetchone()


def _additional_acl(c, roles):
    # Reject all memberships, including custom NOINHERIT/SET ROLE chains.
    # Also reject TEMP/CREATE, unsupported ACL kinds and executable SECURITY
    # DEFINER/untrusted public routines; the existing snapshot covers effective DML.
    return c.execute("""SELECT
        EXISTS(SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname=ANY(%s)
            AND (r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)) role_flags,
        EXISTS(SELECT 1 FROM pg_catalog.pg_roles r,pg_catalog.pg_roles x
            WHERE r.rolname=ANY(%s) AND x.oid<>r.oid
            AND pg_catalog.pg_has_role(r.oid,x.oid,'MEMBER')) membership,
        EXISTS(SELECT 1 FROM pg_catalog.pg_roles r WHERE r.rolname=ANY(%s)
            AND (pg_catalog.has_database_privilege(r.oid,pg_catalog.current_database(),'CREATE')
              OR pg_catalog.has_database_privilege(r.oid,pg_catalog.current_database(),'TEMP'))) database_extra,
        EXISTS(SELECT 1 FROM pg_catalog.pg_roles r,pg_catalog.pg_namespace n
            WHERE r.rolname=ANY(%s)
            AND (n.nspowner=r.oid OR pg_catalog.has_schema_privilege(r.oid,n.oid,'CREATE') OR
                EXISTS(SELECT 1 FROM pg_catalog.pg_class t WHERE t.relnamespace=n.oid AND t.relowner=r.oid) OR
                EXISTS(SELECT 1 FROM pg_catalog.pg_proc p WHERE p.pronamespace=n.oid AND p.proowner=r.oid))) ownership,
        EXISTS(SELECT 1 FROM pg_catalog.pg_class t
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(t.relacl) a
            WHERE (a.privilege_type NOT IN ('SELECT','INSERT','UPDATE') OR a.is_grantable OR
                   n.nspname<>'public' AND a.privilege_type IN ('INSERT','UPDATE'))
            AND (a.grantee=0 OR a.grantee IN
              (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=ANY(%s)))) table_extra,
        EXISTS(SELECT 1 FROM pg_catalog.pg_attribute col
            JOIN pg_catalog.pg_class t ON t.oid=col.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
            CROSS JOIN LATERAL pg_catalog.aclexplode(col.attacl) a
            WHERE (a.privilege_type NOT IN ('SELECT','INSERT','UPDATE') OR a.is_grantable OR
                   n.nspname<>'public' AND a.privilege_type IN ('INSERT','UPDATE'))
            AND (a.grantee=0 OR a.grantee IN
              (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=ANY(%s)))) column_extra,
        EXISTS(SELECT 1 FROM pg_catalog.pg_class t
            JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace,
            pg_catalog.pg_roles r WHERE n.nspname<>'public' AND r.rolname=ANY(%s)
            AND t.relkind IN ('r','p','v','m','f')
            AND (pg_catalog.has_any_column_privilege(r.oid,t.oid,'INSERT,UPDATE') OR
                 pg_catalog.has_table_privilege(r.oid,t.oid,'DELETE,TRUNCATE,TRIGGER,REFERENCES'))) other_schema_write,
        EXISTS(SELECT 1 FROM pg_catalog.pg_proc p
            JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
            JOIN pg_catalog.pg_language l ON l.oid=p.prolang,
            pg_catalog.pg_roles r WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND r.rolname=ANY(%s)
            AND (p.prosecdef OR NOT l.lanpltrusted)
            AND pg_catalog.has_function_privilege(r.oid,p.oid,'EXECUTE')) routine_extra,
        EXISTS(SELECT 1 FROM pg_catalog.pg_proc p CROSS JOIN LATERAL pg_catalog.aclexplode(p.proacl) a
            WHERE a.is_grantable AND (a.grantee=0 OR a.grantee IN
                (SELECT oid FROM pg_catalog.pg_roles WHERE rolname=ANY(%s)))) routine_grant,
        pg_catalog.pg_my_temp_schema()<>0 temporary_namespace,
        pg_catalog.has_function_privilege(%s,'pg_catalog.pg_control_system()','EXECUTE') app_control,
        EXISTS(SELECT 1 FROM pg_catalog.pg_class t JOIN pg_catalog.pg_namespace n ON n.oid=t.relnamespace
            WHERE n.nspname='public' AND t.relname IN
                ('run_assignments','principals','capability_grants','preparation_grants','action_grants','field_grants')
            AND (pg_catalog.has_any_column_privilege(%s,t.oid,'INSERT,UPDATE') OR
                 pg_catalog.has_table_privilege(%s,t.oid,'DELETE'))) app_protected_write""",
        (roles, roles, roles, roles, roles, roles, roles, roles, roles, roles[0],roles[0],roles[0])).fetchone()


class RuntimeGuard:
    """Same-transaction catalog/identity and host-instance check; no grants."""
    def __init__(self, spec, host_check, *, catalog_reader=preflight._read_catalog,
                 identity_reader=_identity, extra_reader=_additional_acl):
        self._spec_json = writer._canonical(preflight.InstallationSpec.model_validate(spec).model_dump())
        self.policy_json = writer._canonical(self.spec.policy.model_dump())
        self.host_check = host_check
        self._catalog, self._identity, self._extra = catalog_reader, identity_reader, extra_reader

    @property
    def spec(self):
        return preflight.InstallationSpec.model_validate_json(self._spec_json)

    def require_live_host(self):
        from .native_run_access_restricted_host import _RuntimeAuthorization
        authority=getattr(self.host_check,'__self__',None)
        if type(authority) is not _RuntimeAuthorization or not authority.matches_guard(self):
            raise Denied('sealed live host issuance required before real restricted connection')

    def check(self, c):
        self.host_check()  # Actual host/UID/source observation in real entry.
        p = self.spec.policy
        identity = self._identity(c)
        if (identity['session_name'] != p.writer_role or identity['current_name'] != p.writer_role or
                identity['owner_name'] in (p.writer_role, p.application_role)):
            raise Denied('actual restricted nonowner login/session required')
        schemas = c.execute('SELECT pg_catalog.current_schemas(true) value').fetchone()['value']
        if not set(schemas) <= {'pg_catalog', 'public'} or 'public' not in schemas:
            raise Denied('restricted runtime refuses shadow/temporary namespace')
        extra = self._extra(c, [p.application_role, p.writer_role])
        if set(extra) != EXTRA_CHECKS or any(v is not False for v in extra.values()):
            raise Denied('restricted runtime extra authority unavailable or unsafe')
        report = preflight.analyze(self.spec.model_dump(), self._catalog(c, self.spec, identity))
        if report['status'] != 'PASS' or report['changes']:
            raise Denied('current restricted catalog/ACL differs from installed contract')
        # No material/generation/beneficiary validity predicate here: the original
        # transaction applies those to REQUEST/APPROVE/ACTIVATE, preserving REVOKE.


class _GuardedCursor:
    """Keep psycopg cursor interfaces, checking before every SQL entry method."""
    def __init__(self,connection,cursor):
        object.__setattr__(self,'_connection',connection)
        object.__setattr__(self,'_cursor',cursor)
    def __getattr__(self,name):return getattr(self._cursor,name)
    def __setattr__(self,name,value):setattr(self._cursor,name,value)
    def __enter__(self):self._cursor.__enter__();return self
    def __exit__(self,*args):return self._cursor.__exit__(*args)
    def __iter__(self):return iter(self._cursor)
    def __next__(self):return next(self._cursor)
    def execute(self,query,*args,**kwargs):
        self._connection._check_before_sql(query)
        self._cursor.execute(query,*args,**kwargs)
        return self
    def executemany(self,query,*args,**kwargs):
        self._connection._check_before_sql(query)
        return self._cursor.executemany(query,*args,**kwargs)
    def stream(self,query,*args,**kwargs):
        self._connection._check_before_sql(query)
        return self._cursor.stream(query,*args,**kwargs)
    def copy(self,query,*args,**kwargs):
        self._connection._check_before_sql(query)
        return self._cursor.copy(query,*args,**kwargs)


class _RestrictedConnection(_AccessConnection):
    def _check_before_sql(self,query):
        header = isinstance(query,str) and query in (
            'SET TRANSACTION READ ONLY','SET LOCAL search_path=pg_catalog,public,pg_temp',
            "SET LOCAL lock_timeout='5s'")
        if not getattr(self,'_runtime_checked',False) and not header and not getattr(self,'_runtime_checking',False):
            self._runtime_checking = True
            try:
                self._restricted_runtime.check(self)
                self._runtime_checked = True
            finally:self._runtime_checking = False

    def cursor(self,*args,**kwargs):
        return _GuardedCursor(self,super().cursor(*args,**kwargs))

    def execute(self,query,*args,**kwargs):
        self._check_before_sql(query)
        return super().execute(query,*args,**kwargs)

    def commit(self):
        try:
            self._restricted_runtime.check(self)
            super().commit()  # Existing actor/source/lease rechecks still run.
        except BaseException:
            self.rollback()
            self.close()
            raise


class RestrictedStore(Store):
    def __init__(self, private_dsn, guard, *, connector=None):
        super().__init__(private_connection_dsn(private_dsn, guard.spec.policy))
        self._restricted_runtime = guard
        self._injected_connector = connector is not None
        self._connector = connector or _RestrictedConnection.connect

    def _guarded_connect(self, dsn=None):
        if dsn is not None:
            raise Denied('restricted runtime cannot borrow or override a connection')
        if not self._injected_connector:self._restricted_runtime.require_live_host()
        self._restricted_runtime.host_check()
        c = self._connector(self.dsn, row_factory=dict_row, connect_timeout=2)
        c._access_store = c._approval_store = self
        c._managed_checks, c._plan_approval_checks, c._writer_checks = set(), [], []
        c._restricted_runtime = self._restricted_runtime
        c._runtime_checked = c._runtime_checking = False
        try:
            # pg_temp is explicitly last; guard rejects a created temp namespace.
            c.execute('SET LOCAL search_path=pg_catalog,public,pg_temp')
            return c
        except BaseException:
            c.rollback();c.close()
            raise

    def connect(self):
        return self._guarded_connect()


class RestrictedEngine:
    """Independent dispatch implementation; original canonical business types."""
    def __init__(self, spec, private_input, boot_id, host_check, *, store_factory=None):
        config = preflight.InstallationSpec.model_validate(spec)
        p = config.policy
        if (p is None or p.environment != 'PRODUCTION' or config.transport != 'LINUX_UNIX' or
                config.permission_strategy != 'DIRECT_DML' or config.api_uid in (None,0) or
                config.writer_uid in (None,0) or config.api_uid == config.writer_uid or
                not re.fullmatch(r'fixture_[a-f0-9]{32}', p.database_name) or
                not isinstance(private_input, dict) or set(private_input) != {'writer_dsn','key'}):
            raise Denied('explicit restricted isolated trial contract required')
        try:
            key = bytes.fromhex(private_input['key'])
            if len(key) != 32:raise ValueError()
            dsn = private_connection_dsn(private_input['writer_dsn'], p)
            self.boot_id = str(UUID(boot_id))
        except (ValueError, TypeError):
            raise Denied('private runtime input invalid; values not echoed') from None
        self._policy_json = writer._canonical(p.model_dump())
        self._key, self._dsn = key, dsn
        self._guard = RuntimeGuard(config.model_dump(), host_check)
        self._injected_store = store_factory is not None
        self._store_factory = store_factory or (lambda: RestrictedStore(self._dsn, self._guard))

    @property
    def policy(self):
        return writer.WriterPolicy.model_validate_json(self._policy_json)

    def execute(self, request, verify_channel):
        if not isinstance(request,dict):raise Denied('typed writer message required')
        op = request.get('operation');expected = {'operation','nonce','run_id'}
        if op == 'VERIFY':expected.add('receipts')
        elif op in ('COMMAND','ACTIVATE'):expected.update(('token','request_key','command'))
        elif op != 'VALIDATE':raise Denied('unknown restricted writer operation')
        if (set(request) != expected or request['run_id'] != self.policy.source.run_id or
                not isinstance(request['nonce'],str) or not re.fullmatch('[a-f0-9]{32}',request['nonce']) or
                type(verify_channel) is not bool or verify_channel != (op in ('VALIDATE','VERIFY'))):
            raise Denied('strict restricted message/channel/scope required')
        if op in ('COMMAND','ACTIVATE') and (
                not isinstance(request['token'],str) or not 1<=len(request['token'])<=256 or
                not isinstance(request['request_key'],str) or not 1<=len(request['request_key'])<=256):
            raise Denied('bounded original request key and current actual session required')
        if op == 'VERIFY':
            # No Store, PG, host permission state or business locks for history MAC.
            return writer.WriterContext.verify(writer.WriterContext(None,self.policy,self._key),request['receipts'])
        if not self._injected_store:
            from .native_run_access_restricted_host import _RuntimeAuthorization
            authority=getattr(self._guard.host_check,'__self__',None)
            if type(authority) is not _RuntimeAuthorization or not authority.matches(self):
                raise Denied('sealed live host issuance required before real restricted backend')
        self._guard.host_check()
        store = self._store_factory()
        context = writer.WriterContext(store,self.policy,self._key)
        if op == 'VALIDATE':
            with store._guarded_connect() as c:
                c.execute('SET TRANSACTION READ ONLY')
                writer.WriterContext.validate(context,c)
                value = writer._public_database(c)
                return dict(database_name=value['database_name'],database_oid=value['database_oid'],
                    system_identifier=self.policy.system_identifier,started=value['started'].isoformat())
        bridge = native.NativeRunAccess(store,writer=context)
        store._native_run_access = bridge
        if op == 'COMMAND':
            data = native.RunCommand.model_validate(request['command'])
            return bridge.command(request['token'],UUID(request['run_id']),request['request_key'],data)
        from .native_run_access_activation import Activate
        data = Activate.model_validate(request['command'])
        return bridge.activate(request['token'],UUID(request['run_id']),request['request_key'],data)


class _PeerHandler(writer._Handler):
    def handle(self):
        pid, uid, gid = struct.unpack('3i',self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
        if pid <= 0 or (uid,gid) != self.server.expected_api_peer:
            return  # Refuse before frame read or engine call; never trust HELLO.
        super().handle()


class _PeerServer(writer._Server):
    def __init__(self,path,engine,verify_channel,api_peer):
        self.engine,self.verify_channel,self.expected_api_peer = engine,verify_channel,api_peer
        self._slots = threading.BoundedSemaphore(8)
        # Reuse bounded lifecycle, but the reference's unguarded Handler is absent.
        import socketserver
        socketserver.UnixStreamServer.__init__(self,path,_PeerHandler)


def serve_restricted(engine, authorization=None):
    from .native_run_access_restricted_host import _RuntimeAuthorization
    if type(authorization) is not _RuntimeAuthorization or not authorization.matches(engine):
        raise Denied('sealed live host authorization required before listener startup')
    authorization.check()
    authorization.check_launch_window()
    servers = []
    try:
        for path, verify in ((authorization.layout.command_path,False),(authorization.layout.verify_path,True)):
            authorization.assert_new_endpoint(path)
            servers.append(_PeerServer(path,engine,verify,
                (authorization.layout.api_uid,authorization.layout.api_gid)))
        authorization.check_endpoints()
        thread = threading.Thread(target=servers[1].serve_forever,daemon=True)
        thread.start();servers[0].serve_forever()
    finally:
        for server in servers:server.server_close()
        # Only the approved host may stop its own child; no path cleanup/adoption.


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self,message):self.exit(4,'REFUSED: private host descriptor required; values not echoed\n')
    parser = Parser(allow_abbrev=False,description='Default-closed restricted writer; approved host FD only')
    parser.add_argument('--host-fd',type=int)
    args = parser.parse_args(argv)
    if args.host_fd is None or args.host_fd < 3:
        print('REFUSED: no live host authorization; actual_run=NOT_RUN')
        return 4
    from .native_run_access_restricted_host import load_host_ticket
    try:
        engine, authorization = load_host_ticket(args.host_fd)
        serve_restricted(engine,authorization)
    except (Denied,OSError,ValueError,TypeError,KeyError):
        print('REFUSED: live private runtime boundary unavailable; values not echoed')
        return 4
    return 0


if __name__ == '__main__':
    from .native_run_access_restricted_runtime import main as canonical_main
    raise SystemExit(canonical_main())
