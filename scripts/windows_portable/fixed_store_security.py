"""Concrete lifecycle wiring with explicit in-memory safety dependencies only.

No native factory, credentials, grants, socket, filesystem or database is opened
here. Fake facts are independent test observations, not production acceptance.
"""
from abc import ABC, abstractmethod
from enum import Enum
import hashlib
import json
import time

from . import credential_envelope as e, endpoint_plan as ep
from . import fixed_secret_store as storage
from .application_readiness import ExistingActorProbe
from .controller import CandidateRefused, DatabaseInputs, NativeDatabaseOperations
from .fixed_directories import FixedDirectoryLease
from .directories import LeaseRefused
from .processes import private_root


class FactKind(Enum):
    CREATION='CREATION'
    RUNTIME='RUNTIME'
    USER='USER'
    DATABASE_MATERIAL='DATABASE_MATERIAL'
    SESSION_MATERIAL='SESSION_MATERIAL'
    ENDPOINT='ENDPOINT'
    DATABASE='DATABASE'
    ACTOR='ACTOR'


class SyntheticSupport(Enum):
    LOCAL_NO_MODEL='LOCAL_NO_MODEL'


class SecurityFact:
    __slots__=()
    def __reduce__(self): raise TypeError('SECURITY_FACT_NOT_TRANSFERABLE')


class FakeSecurityAPI(ABC):
    """Explicit isolated observations. Every implementation must do zero OS IO.

    owns must bind exact fact/subject/kind/input objects, never field equality.
    owned_cluster obtains live endpoint ownership BEFORE database/actor is called;
    neither ownership lookup nor any other method may send real credentials.
    Native implementations/permission are not supplied by this interface.
    """
    @abstractmethod
    def creation_support(self,subject): ...
    @abstractmethod
    def runtime_support(self,subject,database,processes): ...
    @abstractmethod
    def current_user(self,lease): ...
    @abstractmethod
    def material(self,lease,purpose): ...
    @abstractmethod
    def owned_cluster(self,lease,inputs): ...
    @abstractmethod
    def database(self,lease,inputs,witness): ...
    @abstractmethod
    def actor(self,lease,inputs,witness,bearer): ...
    @abstractmethod
    def owns(self,fact,subject,kind,inputs): ...
    @abstractmethod
    def read(self,fact): ...


class SecurityFailure(CandidateRefused):
    def __init__(self,primary,cleanup):
        self.primary,self.cleanup=primary,tuple(cleanup)
        super().__init__('ISOLATED_SECURITY_UNKNOWN')


class PrivateCredentials:
    __slots__=()
    def __reduce__(self): raise TypeError('PRIVATE_CREDENTIALS_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('PRIVATE_CREDENTIALS_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo): raise TypeError('PRIVATE_CREDENTIALS_NOT_TRANSFERABLE')


def need(condition):
    if not condition: raise CandidateRefused('FIXED_SECURITY_CONTRACT_REFUSED')


def native_fixed_store_security():
    raise CandidateRefused('NATIVE_FIXED_STORE_SECURITY_NOT_ACCEPTED')


class IsolatedFixedStoreSecurity:
    fixture_only=True
    native_acceptance=False

    def __init__(self,mode,*,request,api,store_factory,runtime):
        need(type(mode) is ep.PlanMode and isinstance(api,FakeSecurityAPI) and callable(store_factory))
        need((mode is ep.PlanMode.NEW and type(request) is ep.EndpointRequest) or
             (mode is ep.PlanMode.REOPEN and request is None))
        e.exact(runtime,('source_commit','manifest_sha256'))
        e.digest(runtime['source_commit'],40);e.digest(runtime['manifest_sha256'])
        self.mode,self.request,self.api,self.store_factory=mode,request,api,store_factory
        self.runtime=json.loads(e.canonical(runtime));self.failed=False
        self.lease=self.binding=self.store=self.plan=None
        self._credential=self._secrets=self._sessions=self._inputs=None
        self._authentication=self._auth_registered=None;self._auth_used=False
        self._state=self._state_registered=None;self._state_digest=None

    def _fact(self,fact,subject,kind,inputs=None):
        need(type(fact) is SecurityFact and self.api.owns(fact,subject,kind,inputs) is True)
        return self.api.read(fact)

    def require_creation_support(self):
        try:
            need(not self.failed and self.mode is ep.PlanMode.NEW)
            need(self._fact(self.api.creation_support(self),self,FactKind.CREATION) is SyntheticSupport.LOCAL_NO_MODEL)
        except BaseException as error:
            self.failed=True
            raise SecurityFailure(error,()) from None

    def require_runtime_support(self,database,processes):
        # Refusal, never a way to bless native DB operations through fake facts.
        try:
            need(not self.failed and not isinstance(database,NativeDatabaseOperations))
            fact=self.api.runtime_support(self,database,processes)
            need(self._fact(fact,self,FactKind.RUNTIME,(database,processes)) is SyntheticSupport.LOCAL_NO_MODEL)
        except BaseException as error:
            self.failed=True
            raise SecurityFailure(error,()) from None

    def _current_sid(self,lease):
        sid=self._fact(self.api.current_user(lease),lease,FactKind.USER)
        need(type(sid) is str)
        return sid

    def _context(self,lease):
        need(not self.failed and type(lease) is FixedDirectoryLease and self.lease is lease)
        need(ep._key_held(lease)==self._key and self._current_sid(lease)==self.binding.sid)
        need(self.store.lease is lease and self.store.binding is self.binding and
             self.store.config_format is e.ConfigFormat.INSTANCE_SCHEMA3 and not self.store.failed)

    def _run(self,lease,operation):
        need(not self.failed and type(lease) is FixedDirectoryLease)
        def held():
            try:
                if self.lease is not None:self._context(lease)
                result=operation()
                self._context(lease)
                return result
            except BaseException as primary:
                self.failed=True;self._credential=self._authentication=self._state=None
                cleanup=[]
                try:
                    if not lease.poisoned:lease._publish(dict(phase='UNKNOWN',runtime='UNKNOWN',handoff='OWNED'))
                except BaseException as error:cleanup.append(error)
                finally:lease.poisoned=True
                raise SecurityFailure(primary,cleanup) from None
        try:return storage._under_lease(lease,held)
        except BaseException as error:
            if isinstance(error,SecurityFailure):raise
            if isinstance(error,LeaseRefused)and error.args==('FIXED_LEASE_OPERATION_BUSY',):raise
            self.failed=True;self._credential=self._authentication=self._state=None
            raise SecurityFailure(error,()) from None

    def _bind(self,lease):
        need(self.lease is None)
        key=ep._key_held(lease);sid=self._current_sid(lease)
        binding=e.InstanceBinding(key[0],sid,key[1],key[2],key[3]);binding.record()
        store=self.store_factory(lease,binding)
        need(type(store) is storage.IsolatedFixedSecretStore and store.lease is lease and
             store.binding is binding and store.config_format is e.ConfigFormat.INSTANCE_SCHEMA3)
        self.lease,self.binding,self.store,self._key=lease,binding,store,key

    def bind_new_lease(self,lease):
        def bind():
            need(self.mode is ep.PlanMode.NEW and lease.record['phase']=='NEW')
            self._bind(lease)
            self.plan=ep._register_held(lease,self.request,ep.PlanMode.NEW)
        return self._run(lease,bind)

    def _material(self,purpose):
        kind=FactKind.DATABASE_MATERIAL if purpose is e.Purpose.DATABASE else FactKind.SESSION_MATERIAL
        value=self._fact(self.api.material(self.lease,purpose),self.lease,kind)
        e.validate_payload(self.binding,purpose,value,config_format=e.ConfigFormat.INSTANCE_SCHEMA3)
        return json.loads(e.canonical(value))  # Do not retain a provider-owned mutable dict.

    def create_credentials(self,lease):
        def create():
            self._context(lease);need(self.mode is ep.PlanMode.NEW and self.plan is not None)
            value=self._material(e.Purpose.DATABASE)
            self.store._create_held(e.Purpose.DATABASE,value)
            need(self._credential is None)
            self._secrets=(value['postgres'],value['parkweave_app'])
            self._credential=PrivateCredentials()
            return self._credential
        return self._run(lease,create)

    def create_sessions_exclusive(self,lease):
        def create():
            self._context(lease);need(self.mode is ep.PlanMode.NEW and self._sessions is None)
            value=self._material(e.Purpose.SESSION)
            self.store._create_held(e.Purpose.SESSION,value)
            self._sessions=json.loads(e.canonical(value))
            return dict(self._sessions)
        return self._run(lease,create)

    def _require_inputs(self,lease,inputs):
        self._context(lease)
        need(type(inputs) is DatabaseInputs and inputs is self._inputs)
        return ep._record_held(lease,self.plan,mode=self.mode)

    def require_inputs(self,lease,inputs):
        return self._run(lease,lambda:self._require_inputs(lease,inputs))

    def configuration(self,lease,credentials,deadline):
        def configure():
            self._context(lease)
            need(credentials is self._credential and type(credentials) is PrivateCredentials and self._inputs is None
                 and type(deadline) in (int,float) and time.monotonic()<deadline and lease.record['phase']=='CLUSTER')
            ports=ep._record_held(lease,self.plan,mode=self.mode)
            from psycopg.conninfo import make_conninfo
            from parkweave.installed_fixture_receipt import _dsn
            def dsn(database,user,password):
                result=make_conninfo('',host='127.0.0.1',port=str(ports['database_port']),dbname=database,
                    user=user,password=password,sslmode='disable',connect_timeout='2')
                parsed=_dsn(result,database)
                need(parsed['host']=='127.0.0.1' and parsed['user']==user and int(parsed['port'])==ports['database_port'])
                return result
            owner,app=self._secrets
            inputs=DatabaseInputs(dsn('postgres','postgres',owner),dsn('parkweave','postgres',owner),
                                  dsn('parkweave','parkweave_app',app),str(private_root(lease)/'data'/'postgresql'))
            need(time.monotonic()<deadline)
            self._inputs=inputs
            return inputs
        return self._run(lease,configure)

    def _endpoint(self,lease,inputs):
        ports=self._require_inputs(lease,inputs)
        witness=self.api.owned_cluster(lease,inputs)
        observed=self._fact(witness,lease,FactKind.ENDPOINT,inputs)
        need(type(observed) is tuple and observed==('127.0.0.1',ports['database_port']))
        return witness

    def _database(self,lease,inputs):
        witness=self._endpoint(lease,inputs)  # MUST precede any independent DB credential use.
        value=self._fact(self.api.database(lease,inputs,witness),lease,FactKind.DATABASE,inputs)
        need(type(value) is dict)
        return json.loads(e.canonical(value))

    def publish_configuration_exclusive(self,lease,inputs):
        def publish():
            need(self.mode is ep.PlanMode.NEW)
            observed=self._database(lease,inputs)
            self.store._publish_config_held(observed,self.runtime,endpoint_plan=self.plan)
        return self._run(lease,publish)

    def _cache_state(self,token):
        # No caller-supplied PrivateState/dict is an authentication source.
        state,plan=self.store._consume_authentication_held(token)
        need(type(state) is storage.PrivateState)
        need(e.canonical(state.config['runtime'])==e.canonical(self.runtime))
        if self.mode is ep.PlanMode.NEW:need(plan is self.plan)
        else:need(self.plan is None)
        need(ep._record_held(self.lease,plan,mode=self.mode)==state.config['endpoints'])
        self.plan=plan
        self._state=self._state_registered=state
        self._state_digest=storage._Operation._value_digest((state.database,state.sessions,state.config))
        return state,plan

    def verify_existing_files(self,lease):
        def verify():
            need(self._auth_registered is None)
            if self.mode is ep.PlanMode.REOPEN:
                if self.lease is None:self._bind(lease)
                token=self.store._authenticate_existing_held()
                self._authentication=self._auth_registered=token
            else:
                self._context(lease)
                token=self.store._authenticate_new_held(self.plan)
                state,plan=self._cache_state(token)
                need((state.database['postgres'],state.database['parkweave_app'])==self._secrets and state.sessions==self._sessions)
                self._authentication=self._auth_registered=token;self._auth_used=True
        return self._run(lease,verify)

    def load_existing_credentials(self,lease):
        def load():
            self._context(lease)
            need(self.mode is ep.PlanMode.REOPEN and not self._auth_used and
                 self._authentication is self._auth_registered and self._authentication is not None)
            self._auth_used=True
            state,_=self._cache_state(self._authentication)
            need(self._credential is None)
            self._secrets=(state.database['postgres'],state.database['parkweave_app'])
            self._credential=PrivateCredentials()
            return self._credential
        return self._run(lease,load)

    def _state_checked(self):
        need(self._state is not None and self._state is self._state_registered and
             storage._Operation._value_digest((self._state.database,self._state.sessions,self._state.config))==self._state_digest)
        return self._state

    def verify_database_binding(self,lease,inputs):
        def verify():
            state=self._state_checked()
            need(e.canonical(self._database(lease,inputs))==e.canonical(state.config['database']))
        return self._run(lease,verify)

    def application_probe(self,lease):
        def probe():
            state=self._state_checked();bearer=state.sessions['fixture-a']
            witness=self._endpoint(lease,self._inputs)
            actor=self._fact(self.api.actor(lease,self._inputs,witness,bearer),lease,FactKind.ACTOR,self._inputs)
            expected=dict(id='fixture-a',park_id='park-a',org_id='org-a',role='enterprise_operator',active=True,
                          token_hash=hashlib.sha256(bearer.encode()).hexdigest())
            need(e.canonical(actor)==e.canonical(expected))
            return ExistingActorProbe(bearer,tuple(expected[k]for k in ('id','park_id','org_id','role')))
        return self._run(lease,probe)
