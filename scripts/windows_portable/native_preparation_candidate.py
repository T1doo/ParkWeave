"""Native preparation-stage composition, never a complete running Controller.

NEW composes real layout/storage/PGDATA/token/pipe/frozen suspended creation;
REOPEN composes the real closed-read recovery without initdb or secret repair.
No old plaintext pwfile, ordinary resuming cluster backend, ready/app/DB/actor
stub, SQL, password transmission or accepted factory is introduced here.
"""
from dataclasses import dataclass,field
import json
import math
import secrets
from threading import Lock
import time

from . import credential_envelope as e,endpoint_plan as ep
from .controller import CandidateRefused,ControlFailure,DatabaseInputs
from .fixed_secret_store import _under_lease
from .fixed_directories import FixedDirectoryLease
from .native_layout_candidate import _NativeLayout,_create_held as create_layout_held
from .native_secret_store_candidate import _NativeFixedSecretStore
from .pgdata_candidate import _NewDataTarget,_create_target_held,_path_held
from .restricted_token_candidate import _RestrictedPrimaryCandidate,TokenProfile
from .initdb_pipe_candidate import _OwnedInitdbPipe
from .restricted_initdb_candidate import _freeze,_RestrictedInitdbBackend
from .runtime_payload import RuntimePayloadPrerequisite
from .processes import Command,PrivateProcessAdapter


def need(ok):
    if not ok:raise CandidateRefused('NATIVE_PREPARATION_REFUSED')


@dataclass(frozen=True,repr=False)
class FrozenPreparation:
    mode: ep.PlanMode
    runtime: bytes
    request: object
    initdb: object = field(repr=False)


class _NativePreparationController:
    native_acceptance=False
    launch_ready=False

    def __init__(self,mode,*,runtime,request=None,initdb=None):
        need(type(mode) is ep.PlanMode)
        e.exact(runtime,('source_commit','manifest_sha256'))
        e.digest(runtime['source_commit'],40);e.digest(runtime['manifest_sha256'])
        if mode is ep.PlanMode.NEW:
            need(type(request) is ep.EndpointRequest and type(initdb) is Command and
                 initdb.relative_executable=='runtime/postgresql/bin/initdb.exe' and initdb.model=='WINDOWS_JOB'
                 and initdb.arguments==initdb.environment==() and initdb.stdio_contract=='NONE')
            initdb=Command(initdb.relative_executable,initdb.sha256,initdb.size,model='WINDOWS_JOB')
        else:need(request is None and initdb is None)
        # Clone mutable constructor inputs, never accept a DSN/credential argument.
        request=ep.EndpointRequest(request.database_port,request.api_port) if request is not None else None
        self.spec=FrozenPreparation(mode,e.canonical(runtime),request,initdb)
        self._lock=Lock();self.started=self.failed=self.closed=False
        self.lease=self.key=self.store=self.layout=self.target=self.owner=self.pipe=self.adapter=None
        self.plan=self.inputs=None;self._secrets=None;self._owned=[];self._resources=[]
        self.phase='NOT_STARTED';self.cleanup_errors=[]

    def _check(self,deadline):
        need(not self.failed and not self.closed and self.started and time.monotonic()<deadline
             and ep._key_held(self.lease)==self.key)
        self.store._native_check()

    def _hold(self,kind,value):
        self._resources.append((kind,value));return value

    def _new_held(self,lease,deadline):
        self.key=ep._key_held(lease)
        need(self.key[-1]==1 and lease.record['phase']=='NEW')
        self.layout=self._hold('layout',object.__new__(_NativeLayout))
        _NativeLayout.__init__(self.layout,lease,deadline);create_layout_held(lease,self.layout)
        self.plan=ep._register_held(lease,self.spec.request,ep.PlanMode.NEW)
        self.store=self._hold('store',object.__new__(_NativeFixedSecretStore))
        _NativeFixedSecretStore.__init__(self.store,lease,json.loads(self.spec.runtime),deadline,layout=self.layout)
        self._check(deadline)

    def _credentials_held(self,deadline):
        self._check(deadline)
        need(self.lease.record['phase']=='CREDENTIALS' and self._secrets is None)
        # Future explicit invocation only; no generator runs at import/construct.
        value=dict(postgres=secrets.token_urlsafe(48),parkweave_app=secrets.token_urlsafe(48))
        need(value['postgres']!=value['parkweave_app'])
        self.store._create_held(e.Purpose.DATABASE,value)
        self._secrets=value;self._check(deadline)

    def _inputs_held(self,deadline,state=None):
        self._check(deadline)
        if state is None:
            self.target=self._hold('target',object.__new__(_NewDataTarget))
            _NewDataTarget.__init__(self.target,self.lease,deadline)
            _create_target_held(self.lease,self.target,layout=self.layout)
            values=self._secrets;mode=ep.PlanMode.NEW
        else:
            values=state.database;mode=ep.PlanMode.REOPEN
        need(self.inputs is None and type(values) is dict)
        record=ep._record_held(self.lease,self.plan,mode=mode)
        from psycopg.conninfo import make_conninfo
        from parkweave.installed_fixture_receipt import _dsn
        def dsn(database,user,password):
            result=make_conninfo('',host='127.0.0.1',port=str(record['database_port']),dbname=database,
                user=user,password=password,sslmode='disable',connect_timeout='2')
            parsed=_dsn(result,database)
            need(parsed['host']=='127.0.0.1' and parsed['user']==user and int(parsed['port'])==record['database_port'])
            return result
        self.inputs=DatabaseInputs(dsn('postgres','postgres',values['postgres']),
            dsn('parkweave','postgres',values['postgres']),dsn('parkweave','parkweave_app',values['parkweave_app']),
            _path_held(self.lease,self.target))
        self._check(deadline)  # DSNs are private data, not endpoint or DB authority.

    def _existing_held(self,lease,deadline):
        self.key=ep._key_held(lease)
        need(self.key[-1]>=2 and lease.record['phase']=='READY_STOPPED')
        self.store=self._hold('store',object.__new__(_NativeFixedSecretStore))
        _NativeFixedSecretStore.__init__(self.store,lease,json.loads(self.spec.runtime),deadline)
        # Use the held core: public read_for_reopen would reenter the entry gate.
        recovered=self.store._operate_held({'READY_STOPPED':True},self._read_existing)
        state,self.plan,self.target=self.store._consume_recovered_held(recovered)
        self._hold('target',self.target)
        self._inputs_held(deadline,state)

    def _read_existing(self,context):
        from .native_secret_store_candidate import _ReadForReopen
        need(not self.store._reopen_attempted);self.store._reopen_attempted=True
        return _ReadForReopen(self.store._read_state(context))

    def prepare(self,lease,*,deadline,register=None):
        if self.spec.mode is ep.PlanMode.NEW:
            from scripts.windows.lifecycle import require_setup_readiness
            require_setup_readiness()  # Original OWNER gate, before all ports/IO.
        need(type(deadline) in (int,float) and math.isfinite(deadline) and 0<deadline-time.monotonic()<=30)
        need(type(lease) is FixedDirectoryLease)
        need(self._lock.acquire(blocking=False))
        try:
            need(not self.started and not self.closed and not self.failed)
            self.started=True;self.lease=lease
            try:
                if self.spec.mode is ep.PlanMode.REOPEN:
                    need(register is None)
                    self.phase='VERIFY_EXISTING'
                    _under_lease(lease,lambda:self._existing_held(lease,deadline))
                    return dict(scope='EXISTING_FILES_PREPARATION_ONLY',ready=False,processes_started=False)
                need(callable(register))
                self.phase='NEW_LAYOUT';_under_lease(lease,lambda:self._new_held(lease,deadline))
                lease.checkpoint('CREDENTIALS',False,'STARTING')
                self.phase='CREDENTIALS';_under_lease(lease,lambda:self._credentials_held(deadline))
                lease.checkpoint('CLUSTER',False,'STARTING')
                self.phase='CLUSTER_INPUTS';_under_lease(lease,lambda:self._inputs_held(deadline))
                self.owner=self._hold('owner',_RestrictedPrimaryCandidate(TokenProfile.CREATE_CANDIDATE))
                self.owner.derive();self.owner.prepare_default_dacl();self.owner.prepare_owner()
                self.pipe=self._hold('pipe',_OwnedInitdbPipe(lease,self.owner));self.pipe.create()
                frozen=_freeze(lease,self.owner,self.pipe,self.spec.initdb,data_target=self.target)
                runtime=json.loads(self.spec.runtime)
                payload=RuntimePayloadPrerequisite(lease,manifest_sha256=runtime['manifest_sha256'],source_commit=runtime['source_commit'])
                backend=_RestrictedInitdbBackend(frozen,payload,deadline)
                self.adapter=PrivateProcessAdapter(lease,{'initdb':frozen.command},_backend=backend)
                def record(token):
                    need(not self._owned);self._owned.append(token)
                    register(token)  # Recorded before callback; no post-callback trust.
                    self._check(deadline)  # Backend already holds the exact private lease gate.
                self.phase='PINNED_SUSPENDED_INITDB'
                self.adapter.launch('initdb',record)  # Original runtime preflight remains hard-refused.
                _under_lease(lease,lambda:self._check(deadline))
                return dict(scope='SUSPENDED_INITDB_PREPARATION_ONLY',ready=False,
                            resumed=False,secret_transmitted=False)
            except BaseException as primary:
                self.failed=True;self._cleanup()
                raise ControlFailure(self.phase,primary,self.cleanup_errors) from None
        finally:self._lock.release()

    def _cleanup(self):
        # No fabricated READY_STOPPED, release or directory deletion. The outer
        # original lease holder still owns journal handoff/unknown recovery.
        if self.lease is not None:
            try:
                def unknown():
                    if not self.lease.poisoned and ep._key_held(self.lease)==self.key:
                        self.lease._publish(dict(phase='UNKNOWN',runtime='UNKNOWN',handoff='OWNED'))
                _under_lease(self.lease,unknown)
            except BaseException as error:self.cleanup_errors.append(('UNKNOWN_STATE',error))
            self.lease.poisoned=True
        for token in reversed(self._owned):
            try:
                if self.adapter.stop_owned(token) is not True:raise CandidateRefused('OWNED_EXIT_UNKNOWN')
            except BaseException as error:self.cleanup_errors.append(('STOP_OWNED',error))
        for kind,value in reversed(self._resources):
            try:
                if kind=='store':
                    value.failed=True
                    api=getattr(value,'api',None)
                    if api is not None:
                        errors=[]
                        for cap,row in tuple(getattr(api,'caps',{}).items()):
                            try:
                                if not row.close_attempted:api.close(cap)
                            except BaseException as error:errors.append(error)
                        if errors:raise BaseExceptionGroup('NATIVE_STORAGE_CLOSE_UNKNOWN',errors)
                        if getattr(api,'unknown',[]):raise CandidateRefused('NATIVE_STORAGE_CLEANUP_UNKNOWN')
                elif kind=='owner':value.close()
                elif hasattr(value,'handles') or kind=='pipe':value.close()
                if getattr(value,'cleanup_errors',[]):raise CandidateRefused('NATIVE_RESOURCE_CLEANUP_UNKNOWN')
                if kind=='layout' and getattr(getattr(value,'probe',None),'unknown',[]):
                    raise CandidateRefused('LAYOUT_USER_PROBE_CLEANUP_UNKNOWN')
            except BaseException as error:self.cleanup_errors.append((kind.upper(),error))
        self._secrets=None;self.closed=True

    def close(self):
        need(self._lock.acquire(blocking=False))
        try:
            if not self.closed:self._cleanup()
            if self.cleanup_errors:raise ControlFailure('CLOSE',None,self.cleanup_errors)
        finally:self._lock.release()


def native_preparation_controller():
    raise CandidateRefused('NATIVE_PREPARATION_CONTROLLER_NOT_ACCEPTED')
