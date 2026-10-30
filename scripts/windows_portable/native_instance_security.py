"""Concrete native Security and ClusterPrerequisites, no import-time OS work.

The original OWNER, native fixed-journal and runtime-loading gates stay in
force. This supplies real protected storage/identity/database consumers rather
than FakeSecurityAPI facts. Source compilation is not native acceptance.
"""
import ctypes as C
from hashlib import sha256
import json
import os
import secrets
import time

from . import credential_envelope as e, endpoint_plan as ep
from .application_readiness import ExistingActorProbe
from .controller import CandidateRefused, DatabaseInputs, NativeDatabaseOperations
from .fixed_directories import FixedDirectoryLease
from .fixed_secret_store import _under_lease, _Operation
from .fixed_store_security import PrivateCredentials
from .fixed_windows_journal import FixedWindowsFilesystem, NativeFixedLeaseAPI
from .native_layout_candidate import _NativeLayout, _create_held
from .native_secret_store_candidate import _NativeFixedSecretStore, _ReadForReopen
from .pgdata_candidate import _NewDataTarget, _create_target_held, _path_held
from .native_database_endpoint import NativeOwnedDatabaseEndpoint


def need(value):
    if not value:raise CandidateRefused('NATIVE_INSTANCE_SECURITY_REFUSED')


_unknown_security_resources=[]


class NativeFixedStoreSecurity:
    native_acceptance=False

    def __init__(self,mode,*,request,runtime,payload_source=None):
        need(type(mode) is ep.PlanMode and ((mode is ep.PlanMode.NEW and type(request) is ep.EndpointRequest)
             or (mode is ep.PlanMode.REOPEN and request is None)))
        e.exact(runtime,('source_commit','manifest_sha256'))
        e.digest(runtime['source_commit'],40);e.digest(runtime['manifest_sha256'])
        self.mode=mode;self.request=request;self.runtime=json.loads(e.canonical(runtime))
        self.lease=self.store=self.layout=self.target=self.plan=self.inputs=self.endpoint=None
        self.state=self._state_digest=self._credential=self._secrets=self._sessions=None
        self.database=self.processes=None;self.failed=self.closed=False;self.resources=[]
        self.system_crt=None;self._iat_images=None
        self.payload_source=payload_source;self.runtime_installation=None

    def require_runtime_support(self,database,processes):
        from .instance_processes import InstanceProcesses
        from .native_runtime_staging import RuntimeSource
        need(os.name=='nt' and C.sizeof(C.c_void_p)==8 and isinstance(database,NativeDatabaseOperations)
             and type(processes) is InstanceProcesses and not self.failed and not self.closed
             and self.database is None and type(processes.cluster.prerequisites) is NativeClusterPrerequisites
             and processes.cluster.prerequisites.security is self)
        need(type(self.payload_source) is RuntimeSource)
        self.payload_source.plan(self.runtime)  # Reject invalid source plan before acquiring/creating a root.
        self.database,self.processes=database,processes

    def require_creation_support(self):
        from .native_trial_authority import require_owner
        require_owner(self)
        need(self.mode is ep.PlanMode.NEW and not self.failed and not self.closed)

    def _hold(self,value):
        self.resources.append(value)
        return value

    def _context(self,lease):
        need(not self.failed and not self.closed and type(lease) is FixedDirectoryLease
             and type(lease.fs) is FixedWindowsFilesystem and type(lease.fs.api) is NativeFixedLeaseAPI
             and self.lease is lease)
        if self.store is not None:
            need(type(self.store) is _NativeFixedSecretStore and self.store.lease is lease)
            self.store._native_check()
        if self.state is not None:
            need(_Operation._value_digest((self.state.database,self.state.sessions,self.state.config))==self._state_digest)

    def _run(self,lease,operation,*,deadline=None):
        def held():
            try:
                # Every explicitly invoked operation gets its own bounded
                # observation window; a running UI has no 30-second lifetime.
                end=time.monotonic()+10 if deadline is None else deadline
                from .native_trial_authority import budget
                end=budget(self,end)
                need(0<end-time.monotonic()<=30)
                if self.store is not None:self.store.api.deadline=end
                if self.target is not None:self.target.deadline=end
                if self.layout is not None:self.layout.deadline=end
                self._context(lease)
                result=operation(end)
                budget(self,end)
                self._context(lease)
                return result
            except BaseException:
                self.failed=True
                raise
        return _under_lease(lease,held)

    def _new_store(self,lease,deadline,*,layout=None):
        store=self._hold(object.__new__(_NativeFixedSecretStore))
        _NativeFixedSecretStore.__init__(store,lease,self.runtime,deadline,layout=layout)
        return store

    def bind_new_lease(self,lease):
        self.require_creation_support()
        need(self.lease is None)
        self.lease=lease
        self._runtime_files(lease,create=True)
        # Refuse missing/unverifiable prerequisites before credentials, DPAPI
        # identity enrollment, initdb, or database writes.
        self.processes.cluster.prerequisites.require_system_crt(lease,time.monotonic()+30)
        def bind(deadline):
            need(lease.record['phase']=='NEW')
            self.layout=self._hold(object.__new__(_NativeLayout))
            _NativeLayout.__init__(self.layout,lease,deadline)
            _create_held(lease,self.layout)
            self.plan=ep._register_held(lease,self.request,ep.PlanMode.NEW)
            self.store=self._new_store(lease,deadline,layout=self.layout)
        return self._run(lease,bind)

    def _runtime_files(self,lease,*,create):
        from .native_runtime_staging import NativeRuntimeInstallation,RuntimeSource
        need(type(self.payload_source) is RuntimeSource and self.runtime_installation is None)
        def stage():
            try:
                from .native_trial_authority import budget
                self._context(lease)
                self.runtime_installation=self._hold(object.__new__(NativeRuntimeInstallation))
                NativeRuntimeInstallation.__init__(self.runtime_installation,lease,self.payload_source,
                    self.runtime,create=create,deadline=budget(self,time.monotonic()+120))
                self._context(lease)
            except BaseException:
                self.failed=True
                raise
        return _under_lease(lease,stage)

    def create_credentials(self,lease):
        self.require_creation_support()
        def create(_):
            need(self._credential is None and lease.record['phase']=='CREDENTIALS')
            value=dict(postgres=secrets.token_urlsafe(48),parkweave_app=secrets.token_urlsafe(48))
            need(value['postgres']!=value['parkweave_app'])
            self.store._create_held(e.Purpose.DATABASE,value)
            self._secrets=value;self._credential=PrivateCredentials()
            return self._credential
        return self._run(lease,create)

    def create_sessions_exclusive(self,lease):
        self.require_creation_support()
        def create(_):
            need(self._sessions is None and lease.record['phase']=='SESSIONS')
            value={name:secrets.token_urlsafe(48) for name in ('fixture-a','fixture-b','fixture-c')}
            self.store._create_held(e.Purpose.SESSION,value)
            self._sessions=value
            return dict(value)
        return self._run(lease,create)

    def configuration(self,lease,credentials,deadline):
        def configure(end):
            need(credentials is self._credential and type(credentials) is PrivateCredentials
                 and self.inputs is None and lease.record['phase']=='CLUSTER')
            if self.mode is ep.PlanMode.NEW:
                self.target=self._hold(object.__new__(_NewDataTarget))
                _NewDataTarget.__init__(self.target,lease,end)
                _create_target_held(lease,self.target,layout=self.layout)
            ports=ep._record_held(lease,self.plan,mode=self.mode)
            from psycopg.conninfo import make_conninfo
            def dsn(database,user):
                return make_conninfo(host='127.0.0.1',port=str(ports['database_port']),dbname=database,
                    user=user,password=self._secrets[user],connect_timeout=2,sslmode='disable')
            self.inputs=DatabaseInputs(dsn('postgres','postgres'),dsn('parkweave','postgres'),
                dsn('parkweave','parkweave_app'),_path_held(lease,self.target))
            return self.inputs
        return self._run(lease,configure,deadline=deadline)

    def require_inputs(self,lease,inputs):
        def check(_):
            need(type(inputs) is DatabaseInputs and inputs is self.inputs)
            need(inputs.data_directory==_path_held(lease,self.target))
            return ep._record_held(lease,self.plan,mode=self.mode)
        return self._run(lease,check)

    def _cache(self,state):
        need(e.canonical(state.config['runtime'])==e.canonical(self.runtime))
        self.state=state
        self._state_digest=_Operation._value_digest((state.database,state.sessions,state.config))

    def verify_existing_files(self,lease):
        if self.mode is ep.PlanMode.REOPEN and self.lease is None:self.lease=lease
        if self.mode is ep.PlanMode.REOPEN:
            self._runtime_files(lease,create=False)
            self.processes.cluster.prerequisites.require_system_crt(lease,time.monotonic()+30)
        def verify(deadline):
            if self.mode is ep.PlanMode.REOPEN:
                need(self.store is None and self.state is None and lease.record['phase']=='READY_STOPPED')
                self.store=self._new_store(lease,deadline)
                recovered=self.store._operate_held({'READY_STOPPED':True},
                    lambda context:_ReadForReopen(self.store._read_state(context)))
                state,self.plan,self.target=self.store._consume_recovered_held(recovered)
                self._hold(self.target);self._cache(state)
            else:
                need(lease.record['phase']=='VERIFY_FILES')
                state=self.store._operate_held({'VERIFY_FILES':False},self.store._read_state)
                need(state.database==self._secrets and state.sessions==self._sessions)
                self._cache(state)
        return self._run(lease,verify)

    def load_existing_credentials(self,lease):
        def load(_):
            need(self.mode is ep.PlanMode.REOPEN and self.state is not None and self._credential is None)
            self._secrets=dict(self.state.database);self._sessions=dict(self.state.sessions)
            self._credential=PrivateCredentials()
            return self._credential
        return self._run(lease,load)

    def _database(self,inputs,*,deadline=None):
        need(inputs is self.inputs and type(self.endpoint) is NativeOwnedDatabaseEndpoint)
        from parkweave.installed_fixture_receipt import _dsn,_identity
        with self.endpoint.connect(_dsn(inputs.owner_dsn,'parkweave'),deadline=deadline) as connection:
            self.endpoint.verify_connection(connection)
            connection.execute('SET TRANSACTION READ ONLY')
            observed=_identity(connection)
            need(observed['database_name']=='parkweave' and observed['data_directory']==inputs.data_directory
                 and observed['owner_name']==observed['current_name']==observed['session_name']=='postgres')
            row=connection.execute('SELECT max(version) AS version FROM schema_version').fetchone()
            need(row['version']==32)
            from .native_trial_authority import bound_state
            if bound_state(self.lease) is not None:
                from .native_iat_observer import layout,capture_peer
                if layout() is not None:
                    from .native_loader_images import capture
                    end=connection._deadline
                    self._iat_images=capture(self.lease,self,end)
                    capture_peer(self.lease,self.system_crt,connection._endpoint_witness,end,self._iat_images)
            binding=self.target._verify()
            return dict(system_identifier=observed['system_identifier'],database_oid=observed['database_oid'],
                database_name='parkweave',owner='postgres',data_identity=list(binding.root_id),schema_version=32)

    def publish_configuration_exclusive(self,lease,inputs):
        self.require_creation_support()
        def publish(_):
            self.store._publish_config_held(self._database(inputs),self.runtime,
                endpoint_plan=self.plan,pgdata_target=self.target)
            self._cache(self.store._operate_held({'CONFIG':False},self.store._read_state))
        return self._run(lease,publish)

    def verify_database_binding(self,lease,inputs):
        def verify(_):
            need(self.state is not None and e.canonical(self._database(inputs))==e.canonical(self.state.config['database']))
        return self._run(lease,verify)

    def application_probe(self,lease):
        def probe(_):
            need(self.state is not None)
            bearer=self.state.sessions['fixture-a']
            from parkweave.installed_fixture_receipt import _dsn
            with self.endpoint.connect(_dsn(self.inputs.owner_dsn,'parkweave')) as connection:
                connection.execute('SET TRANSACTION READ ONLY')
                row=connection.execute('SELECT id,park_id,org_id,role,active,token_hash FROM principals WHERE id=%s',('fixture-a',)).fetchone()
            expected=dict(id='fixture-a',park_id='park-a',org_id='org-a',role='enterprise_operator',
                active=True,token_hash=sha256(bearer.encode()).hexdigest())
            need(row==expected)
            return ExistingActorProbe(bearer,('fixture-a','park-a','org-a','enterprise_operator'))
        return self._run(lease,probe)

    def close_owned_files(self,lease):
        need(self.lease is lease)
        errors=[]
        for value in reversed(self.resources):
            try:
                from .native_trial_authority import budget
                budget(self,cleanup=True)
                if type(value) is _NativeFixedSecretStore:
                    api=getattr(value,'api',None)
                    if api is not None:
                        for cap,row in reversed(tuple(getattr(api,'caps',{}).items())):
                            budget(self,cleanup=True)
                            if not row.close_attempted:api.close(cap)
                elif hasattr(value,'close'):value.close()
                from .restricted_token_candidate import _RestrictedPrimaryCandidate
                if type(value) is _RestrictedPrimaryCandidate:
                    from .native_trial_facts import completed_token
                    completed_token(lease,value)
            except BaseException as error:errors.append(error)
            # Previous uncertain close attempts may already have removed their
            # integer handles from the active set. Preserve them; never retry.
            api=getattr(value,'api',None)
            caps=getattr(api,'caps',{})
            probe=getattr(value,'probe',None)
            native=getattr(getattr(value,'protection',None),'native',None)
            if (getattr(value,'cleanup_errors',None) or getattr(api,'unknown',None)
                    or getattr(native,'unknown',None)
                    or getattr(probe,'unknown',None)
                    or any(row.get('attempted') and not row.get('closed') for row in getattr(probe,'temporary',()))
                    or any(row.close_attempted and not row.closed for row in caps.values())):
                errors.append(CandidateRefused('PREVIOUS_NATIVE_RESOURCE_CLOSE_UNKNOWN'))
        self.closed=True;self._secrets=self._sessions=self._credential=self.state=None
        if errors:
            self.retain_owned_files(lease)
            raise BaseExceptionGroup('NATIVE_SECURITY_RESOURCE_CLOSE_UNKNOWN',errors)

    def retain_owned_files(self,lease):
        need(self.lease is lease)
        if not any(value is self for value in _unknown_security_resources):
            _unknown_security_resources.append(self)


class NativeClusterPrerequisites:
    """Actual protected inputs, PGDATA checks and owned SQL readiness."""
    def __init__(self,security):
        need(type(security) is NativeFixedStoreSecurity)
        self.security=security

    def configuration(self,lease,credentials,deadline):
        return self.security.configuration(lease,credentials,deadline)

    def before_initdb(self,lease,inputs,password_file,deadline):
        # The legacy path-based cluster is deliberately unsupported. The native
        # factory uses initialize_protected with an original named-pipe server.
        raise CandidateRefused('PLAINTEXT_INITDB_PASSWORD_FILE_NOT_SUPPORTED')

    def initialize_protected(self,lease,inputs,specification,register,deadline):
        from .native_protected_bootstrap import initialize
        return initialize(self.security,lease,inputs,specification,register,deadline)

    def require_system_crt(self,lease,deadline):
        from .native_system_crt import NativeSystemCRT
        need(self.security.lease is lease)
        if self.security.system_crt is None:
            value=self.security._hold(object.__new__(NativeSystemCRT))
            NativeSystemCRT.__init__(value,lease,self.security.runtime_installation,self.security.runtime,deadline)
            self.security.system_crt=value
        else:
            self.security.system_crt.deadline=deadline
            self.security.system_crt._binding();self.security.system_crt._verify_files()
        return self.security.system_crt

    def before_server(self,lease,inputs,mode,deadline):
        self.require_system_crt(lease,deadline)
        def verify(_):
            need(inputs is self.security.inputs and mode==self.security.mode.value)
            self.security.target._verify()
            first=self.security.target._walk()
            need(self.security.target._walk()==first)
        self.security._run(lease,verify,deadline=deadline)
        # Outside the held PGDATA operation: the payload contract calls the
        # public lease status gate. REOPEN must retain the same loading refusal
        # as NEW, even after a future independent fixed-journal acceptance.
        from .runtime_payload import RuntimePayloadPrerequisite
        payload=RuntimePayloadPrerequisite(lease,**self.security.runtime,
            native_installation=self.security.runtime_installation)
        return payload.require_for_cluster(lease,deadline)

    def server_ready(self,lease,inputs,adapter,token,deadline):
        need(inputs is self.security.inputs and self.security.endpoint is None)
        need(self.security.system_crt is not None)
        self.security.system_crt.observe_group(adapter,token,deadline)
        endpoint=NativeOwnedDatabaseEndpoint(adapter,token,crt_witness=self.security.system_crt)
        from .native_trial_authority import inherit
        inherit(self.security,endpoint)
        endpoint.wait_for_listener(deadline)
        from parkweave.installed_fixture_receipt import _dsn,_identity
        with endpoint.connect(_dsn(inputs.maintenance_dsn,'postgres'),deadline=deadline,autocommit=True) as connection:
            row=_identity(connection)
            need(row['database_name']=='postgres' and row['data_directory']==inputs.data_directory
                 and row['owner_name']==row['current_name']==row['session_name']=='postgres')
            if self.security.mode is ep.PlanMode.NEW:
                need(connection.execute("SELECT 1 FROM pg_roles WHERE rolname='parkweave_app'").fetchone() is None)
                # Store only a salted SCRAM verifier in the role DDL, never the
                # plaintext password in SQL/argv/environment or a password file.
                import base64,hashlib,hmac
                salt=secrets.token_bytes(16);password=self.security._secrets['parkweave_app'].encode()
                salted=hashlib.pbkdf2_hmac('sha256',password,salt,4096)
                stored=sha256(hmac.digest(salted,b'Client Key','sha256')).digest()
                server=hmac.digest(salted,b'Server Key','sha256')
                b64=lambda value:base64.b64encode(value).decode('ascii')
                verifier='SCRAM-SHA-256$4096:'+b64(salt)+'$'+b64(stored)+':'+b64(server)
                from psycopg import sql
                connection.execute(sql.SQL('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Literal(verifier)))
        self.security.endpoint=endpoint
        self.security.database.bind_owned_endpoint(endpoint)


def native_security_ports(*,mode,request,runtime,payload_source=None):
    security=NativeFixedStoreSecurity(mode,request=request,runtime=runtime,payload_source=payload_source)
    return security,NativeClusterPrerequisites(security)
