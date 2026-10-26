"""Fixed-object storage algorithm using explicit in-memory capability doubles.

No real filesystem/DPAPI adapter, path arguments, controller or native activation.
Fake capabilities/ACL facts are never Windows ownership or durability evidence.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
import hashlib
from types import MappingProxyType
import weakref
from threading import get_ident

from . import credential_envelope as e
from . import endpoint_plan as endpoints
from .fixed_directories import FixedDirectoryLease, _exclusive_entry
from .directories import LeaseRefused
from .windows_user_protection import IsolatedUserProtection


NAMES = MappingProxyType({e.Purpose.DATABASE: 'database.dpapi', e.Purpose.SESSION: 'synthetic-sessions.dpapi',
                         e.Purpose.CONFIG: 'instance-config.dpapi'})


class StoreRefused(RuntimeError):
    pass


class StoreFailure(StoreRefused):
    def __init__(self, primary, cleanup, journal_error):
        self.primary, self.cleanup, self.journal_error = primary, tuple(cleanup), journal_error
        self.outcome = 'UNKNOWN'
        super().__init__('ISOLATED_FIXED_SECRET_STORE_UNKNOWN')

    def public(self):
        return dict(outcome=self.outcome, primary_type=type(self.primary).__name__,
                    cleanup_types=[type(x).__name__ for x in self.cleanup],
                    journal_error_type=type(self.journal_error).__name__)


class FakeCapability:
    __slots__ = ()
    def __reduce__(self): raise TypeError('FAKE_CAPABILITY_NOT_TRANSFERABLE')


@dataclass(frozen=True, repr=False)
class ObjectInfo:
    identity: tuple
    parent: tuple
    leaf: str
    directory: bool
    owner: str
    control: int
    raw_dacl: bytes
    private_acl_checked: bool
    reparse: bool
    links: int
    size: int
    revision: int


class FakeSecretAPI(ABC):
    """Explicit in-memory fake only; all operations below must do zero OS IO.

    open_secrets holds the existing literal secrets child of the original root.
    open_file takes only Purpose, exclusively creates new files or opens them
    read-only. Partial allocations before a failed return remain the API's duty.
    owns uses exact capability, lease and parent identity, not a public token.
    inspect's private_acl_checked stands for the original private-ACL predicate;
    it is an unverified fake fact, never native ACE parsing or safety acceptance.
    creation_descriptor captures owner/raw-DACL/control before the original new
    object protection transaction; no setter is supplied or bypassed here.
    read starts at offset zero, bounded by limit. write is one call, not a loop.
    flush/close must return exactly True; close uncertainty is never retried.
    """
    @abstractmethod
    def binds(self, lease): ...
    @abstractmethod
    def open_secrets(self, lease): ...
    @abstractmethod
    def open_file(self, directory, purpose, *, create): ...
    @abstractmethod
    def owns(self, capability, lease, parent): ...
    @abstractmethod
    def inspect(self, capability): ...
    @abstractmethod
    def creation_descriptor(self, capability): ...
    @abstractmethod
    def write(self, capability, raw): ...
    @abstractmethod
    def flush(self, capability): ...
    @abstractmethod
    def read(self, capability, limit): ...
    @abstractmethod
    def close(self, capability): ...


def native_fixed_secret_store():
    raise StoreRefused('NATIVE_FIXED_SECRET_CAPABILITIES_NOT_ACCEPTED')


@_exclusive_entry
def _under_lease(lease, operation):
    # Existing FixedDirectoryLease entry gate, not another independent lock.
    lease._verify()
    return operation()


def need(condition):
    if not condition: raise StoreRefused('FIXED_SECRET_CONTRACT_REFUSED')


@dataclass(frozen=True, repr=False)
class PrivateState:
    database: dict
    sessions: dict
    config: dict


@dataclass(frozen=True, repr=False)
class _EndpointRecovery:
    state: PrivateState


@dataclass(frozen=True, repr=False)
class _AuthenticationRecovery:
    state: PrivateState
    plan: object = None


class StoreAuthentication:
    __slots__=('__weakref__',)
    def __reduce__(self): raise TypeError('STORE_AUTHENTICATION_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('STORE_AUTHENTICATION_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo): raise TypeError('STORE_AUTHENTICATION_NOT_TRANSFERABLE')


_authenticated_reads=weakref.WeakKeyDictionary()


class _ClosedEndpointRecovery:
    __slots__=('__weakref__',)
    def __reduce__(self): raise TypeError('CLOSED_RECOVERY_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('CLOSED_RECOVERY_NOT_TRANSFERABLE')
    def __deepcopy__(self,memo): raise TypeError('CLOSED_RECOVERY_NOT_TRANSFERABLE')


_closed_endpoint_recoveries=weakref.WeakKeyDictionary()


def _consume_closed_endpoint_recovery(lease,token):
    if (type(lease) is not FixedDirectoryLease or lease._operation_owner != get_ident()
            or lease._operation_depth <= 0):
        raise endpoints.EndpointRefused()
    if type(token) is not _ClosedEndpointRecovery: raise endpoints.EndpointRefused()
    record=_closed_endpoint_recoveries.pop(token,None)  # Consume before any fallible validation.
    if record is None: raise endpoints.EndpointRefused()
    store,request=record
    if (type(store) is not IsolatedFixedSecretStore or store.lease is not lease or store.failed
            or store.config_format is not e.ConfigFormat.INSTANCE_SCHEMA3
            or store._endpoint_finalizing is not token):
        raise endpoints.EndpointRefused()
    return request


class _Operation:
    def __init__(self, store):
        self.store = store; self.directory = None; self.caps = []; self.pins = {}
        self.config_format = store.config_format
        self._read_facts = {}; self._state_fact = None; self._state_consumed = False
        self.closed_caps = []; self.final_verified = False

    @staticmethod
    def _value_digest(value):
        raw = e.canonical(value)
        need(len(raw) <= 3*e.MAX_PLAINTEXT)
        return hashlib.sha256(raw).digest()

    def bind_read_state(self, state, caps):
        # Facts originate only in successful read/decode/check below, and are
        # tied to these exact held capabilities in this one operation.
        need(self._state_fact is None and type(state) is PrivateState
             and set(caps) == set(e.Purpose) and len(self.caps) == 4
             and set(caps.values()) == set(self.caps[1:]))
        facts = []
        for purpose, cap in caps.items():
            fact = self._read_facts.get(cap)
            value = state.config if purpose is e.Purpose.CONFIG else (
                state.database if purpose is e.Purpose.DATABASE else state.sessions)
            need(fact is not None and fact[0] is purpose and fact[1] == self._value_digest(value)
                 and fact[3] == self.pins[cap])
            if purpose is not e.Purpose.CONFIG:
                need(fact[2] == e.canonical(state.config['files'][purpose.value]))
            facts.append((cap, fact))
        digest = self._value_digest((state.database,state.sessions,state.config))
        self._state_fact = (state,digest,tuple(facts))

    def consume_read_state(self, state):
        need(self._state_fact is not None and not self._state_consumed)
        self._state_consumed = True  # Never retry a rejected or uncertain consumption.
        original,digest,facts = self._state_fact
        need(self.store.lease._operation_owner == get_ident() and self.store.lease._operation_depth > 0
             and self.final_verified and len(self.closed_caps) == len(self.caps) == 4
             and set(self.closed_caps) == set(self.caps) and state is original
             and digest == self._value_digest((state.database,state.sessions,state.config))
             and len(facts) == 3 and set(self._read_facts) == {cap for cap,_ in facts}
             and all(self._read_facts[cap] == fact and self.pins.get(cap) == fact[3] for cap,fact in facts))
        return endpoints.validate_record(state.config['endpoints'])

    def check_binding(self):
        s = self.store; s.lease._verify()
        need(type(self.config_format) is e.ConfigFormat and s.config_format is self.config_format)
        need(s.api.binds(s.lease) is True)
        r = s.lease.record
        need(tuple(r['root']) == s.binding.root and tuple(r['lock']) == s.binding.lock
             and tuple(r['journal']) == s.binding.journal and r['handoff'] == 'OWNED')
        s.binding.record()
        if self.config_format in (e.ConfigFormat.INSTANCE_SCHEMA3,e.ConfigFormat.PGDATA_SCHEMA4):
            need(s.lease._verified_instance_uuid() == s.binding.instance_id)

    def check(self):
        self.check_binding()
        s = self.store
        for cap, old in self.pins.items():
            parent = None if old.directory else self.directory
            need(s.api.owns(cap, s.lease, parent) is True)
            now = self.info(cap, old.leaf, old.parent, old.directory)
            need(now == old)

    def info(self, cap, leaf, parent, directory):
        info = self.store.api.inspect(cap)
        need(type(info) is ObjectInfo and type(info.directory) is bool and info.directory == directory
             and type(info.leaf) is str and info.leaf == leaf and info.parent == parent
             and type(info.owner) is str and info.owner == self.store.binding.sid)
        e.identity(info.parent)
        e.identity(info.identity); need(info.identity[0] == self.store.binding.root[0])
        need(type(info.control) is int and 0 <= info.control <= 65535 and info.control & 0x1004 == 0x1004)
        need(type(info.raw_dacl) is bytes and 8 <= len(info.raw_dacl) <= 65535 and info.private_acl_checked is True)
        need(info.reparse is False and type(info.links) is int and (directory or info.links == 1))
        need(type(info.size) is int and 0 <= info.size <= e.MAX_CIPHERTEXT
             and type(info.revision) is int and info.revision >= 0)
        return info

    def hold(self, cap, leaf, parent, directory):
        need(type(cap) is FakeCapability and cap not in self.caps
             and self.store.api.owns(cap, self.store.lease, self.directory) is True)
        self.caps.append(cap)  # Cleanup registration precedes inspect/callbacks.
        info = self.info(cap, leaf, parent, directory)
        ids = {self.store.binding.root, self.store.binding.lock, self.store.binding.journal}
        ids.update(v.identity for v in self.pins.values())
        need(info.identity not in ids)
        self.pins[cap] = info
        return cap

    def start(self):
        self.check()
        cap = self.store.api.open_secrets(self.store.lease)
        self.directory = self.hold(cap, 'secrets', self.store.binding.root, True)

    def file(self, purpose, create):
        self.check()
        cap = self.store.api.open_file(self.directory, purpose, create=create)
        self.hold(cap, NAMES[purpose], self.pins[self.directory].identity, False)
        if create:
            # Our exclusive child creation may change directory size/time, but
            # never its identity, parent, owner or raw protection descriptor.
            old = self.pins[self.directory]
            current = self.info(self.directory, 'secrets', self.store.binding.root, True)
            need(replace(current, size=old.size, revision=old.revision) == old)
            self.pins[self.directory] = current
            before = self.store.api.creation_descriptor(cap); after = self.pins[cap]
            need(type(before) is tuple and len(before) == 3 and type(before[0]) is str
                 and 0 < len(before[0]) <= 184 and type(before[1]) is int and 0 <= before[1] <= 65535
                 and type(before[2]) is bytes and 8 <= len(before[2]) <= 65535)
            need(before[0] == after.owner and before[2] == after.raw_dacl and before[1] & ~1 == after.control & ~1)
            need(after.size == 0)
        return cap

    def read(self, cap, purpose, expected_ciphertext=None):
        self.check(); raw = self.store.api.read(cap, e.MAX_CIPHERTEXT+1)
        need(type(raw) is bytes and 0 < len(raw) <= e.MAX_CIPHERTEXT and len(raw) == self.pins[cap].size)
        need(expected_ciphertext is None or raw == expected_ciphertext)
        self.check()
        plain = self.store.protection.unprotect(raw, e.entropy_bytes(self.store.binding, purpose))
        value = e.decode_plaintext(self.store.binding, purpose, plain, config_format=self.config_format)
        self.check()
        ref = dict(identity=list(self.pins[cap].identity), ciphertext_sha256=hashlib.sha256(raw).hexdigest())
        self._read_facts[cap] = (purpose,self._value_digest(value),e.canonical(ref),self.pins[cap])
        return value, ref

    def write(self, purpose, payload):
        self.check()
        plain = e.encode_plaintext(self.store.binding, purpose, payload, config_format=self.config_format)
        cap = self.file(purpose, True); before = self.pins[cap]
        raw = self.store.protection.protect(plain, e.entropy_bytes(self.store.binding, purpose))
        need(type(raw) is bytes and 0 < len(raw) <= e.MAX_CIPHERTEXT)
        self.check()
        count = self.store.api.write(cap, raw)
        need(type(count) is int and count == len(raw))
        need(self.store.api.flush(cap) is True)
        after = self.info(cap, before.leaf, before.parent, False)
        need(after.identity == before.identity and after.owner == before.owner and after.control == before.control
             and after.raw_dacl == before.raw_dacl and after.size == len(raw))
        self.pins[cap] = after
        checked, ref = self.read(cap, purpose, expected_ciphertext=raw)
        need(e.canonical(checked) == e.canonical(payload))
        return ref


class IsolatedFixedSecretStore:
    fixture_only = True
    native_acceptance = False

    def __init__(self, lease, binding, api, protection, *, config_format=e.ConfigFormat.SCHEMA2):
        need(type(lease) is FixedDirectoryLease and type(binding) is e.InstanceBinding
             and isinstance(api, FakeSecretAPI) and type(protection) is IsolatedUserProtection
             and type(config_format) is e.ConfigFormat)
        self.lease, self.binding, self.api, self.protection = lease, binding, api, protection
        self._config_format = config_format
        self._endpoint_finalizing = None
        self.failed = False; self._unknown_caps = []

    @property
    def config_format(self): return self._config_format

    def _operate(self, states, operation):
        try:
            return _under_lease(self.lease, lambda: self._operate_held(states,operation))
        except BaseException as error:
            if isinstance(error, StoreFailure): raise
            if isinstance(error, LeaseRefused) and error.args == ('FIXED_LEASE_OPERATION_BUSY',): raise
            self.failed = True
            raise StoreFailure(error, (), None) from None

    def _operate_held(self, states, operation):
        need(self.lease._operation_owner == get_ident() and self.lease._operation_depth > 0)
        need(not self.failed)
        def run():
            context = _Operation(self); primary = None; cleanup = []; result = None
            try:
                phase = self.lease.record['phase']
                need(phase in states and self.lease.record['initialized'] is states[phase])
                context.start(); result = operation(context); context.check()
            except BaseException as error: primary = error
            finally:
                # Each known capability is closed once while the lease entry
                # gate is held; an unknown close is never guessed or retried.
                for cap in reversed(context.caps):
                    try:
                        parent = None if cap is context.caps[0] else context.directory
                        if self.api.owns(cap, self.lease, parent) is not True:
                            raise StoreRefused('FIXED_SECRET_CLOSE_OWNERSHIP_UNKNOWN')
                        if self.api.close(cap) is not True: raise StoreRefused('FIXED_SECRET_CLOSE_UNKNOWN')
                        context.closed_caps.append(cap)
                    except BaseException as error:
                        self._unknown_caps.append(cap); cleanup.append(error)
                try:
                    context.check_binding()
                    context.final_verified = True
                except BaseException as error: cleanup.append(error)
            # Registration must occur AFTER successful close of EVERY held
            # capability and the final lease/binding check, still under the
            # original entry gate. Its failure shares the UNKNOWN path below.
            if primary is None and not cleanup and type(result) in (_EndpointRecovery,_AuthenticationRecovery):
                try:
                    need(self.config_format is e.ConfigFormat.INSTANCE_SCHEMA3)
                    request = context.consume_read_state(result.state)
                    if type(result) is _AuthenticationRecovery and result.plan is not None:
                        plan = result.plan
                        record = endpoints._record_held(self.lease,plan,mode=endpoints.PlanMode.NEW)
                        need(endpoints.validate_record(record) == request)
                    else:
                        token = _ClosedEndpointRecovery()
                        _closed_endpoint_recoveries[token] = (self,request)
                        self._endpoint_finalizing = token
                        try:
                            plan = endpoints._register_held(self.lease, None, endpoints.PlanMode.REOPEN,closed_recovery=token)
                        finally:
                            self._endpoint_finalizing = None
                            _closed_endpoint_recoveries.pop(token,None)
                    if type(result) is _AuthenticationRecovery:
                        authenticated = StoreAuthentication()
                        digest = context._value_digest((result.state.database,result.state.sessions,result.state.config))
                        _authenticated_reads[authenticated] = (self,self.lease.snapshot,result.state,plan,digest)
                        result = authenticated
                    else: result = (result.state, plan)
                except BaseException as error: primary = error
            if primary is not None or cleanup:
                journal_error = None; self.failed = True
                try:
                    if not self.lease.poisoned:
                        self.lease._publish(dict(phase='UNKNOWN', runtime='UNKNOWN', handoff='OWNED'))
                except BaseException as error: journal_error = error
                finally: self.lease.poisoned = True
                raise StoreFailure(primary, cleanup, journal_error) from None
            return result
        return run()

    def create(self, purpose, payload):
        need(type(purpose) is e.Purpose and purpose in (e.Purpose.DATABASE, e.Purpose.SESSION))
        phase = 'CREDENTIALS' if purpose is e.Purpose.DATABASE else 'SESSIONS'
        return self._operate({phase: False}, lambda ctx: ctx.write(purpose, payload))

    def _create_held(self, purpose, payload):
        need(type(purpose) is e.Purpose and purpose in (e.Purpose.DATABASE,e.Purpose.SESSION))
        phase = 'CREDENTIALS' if purpose is e.Purpose.DATABASE else 'SESSIONS'
        return self._operate_held({phase:False},lambda ctx:ctx.write(purpose,payload))

    def publish_config(self, database, runtime, *, endpoint_plan=None, pgdata_target=None):
        return self._operate({'CONFIG':False},self._config_writer(database,runtime,endpoint_plan,pgdata_target))

    def _publish_config_held(self, database, runtime, *, endpoint_plan, pgdata_target=None):
        return self._operate_held({'CONFIG':False},self._config_writer(database,runtime,endpoint_plan,pgdata_target))

    def _config_writer(self, database, runtime, endpoint_plan, pgdata_target):
        def publish(ctx):
            pgdata = None
            if self.config_format is e.ConfigFormat.PGDATA_SCHEMA4:
                from .pgdata_candidate import _profile_held
                pgdata = _profile_held(self.lease, pgdata_target)
            else:
                need(pgdata_target is None)
            if self.config_format in (e.ConfigFormat.INSTANCE_SCHEMA3,e.ConfigFormat.PGDATA_SCHEMA4):
                endpoint_values = endpoints._record_held(self.lease, endpoint_plan, mode=endpoints.PlanMode.NEW)
            else:
                need(endpoint_plan is None)
            refs = {}
            for purpose in (e.Purpose.DATABASE, e.Purpose.SESSION):
                cap = ctx.file(purpose, False)
                _, refs[purpose.value] = ctx.read(cap, purpose)
            payload = dict(schema=self.config_format.value, files=refs, database=database, runtime=runtime)
            if self.config_format in (e.ConfigFormat.INSTANCE_SCHEMA3,e.ConfigFormat.PGDATA_SCHEMA4): payload['endpoints'] = endpoint_values
            if pgdata is not None: payload['pgdata'] = pgdata
            result = ctx.write(e.Purpose.CONFIG, payload)
            if pgdata is not None:
                need(_profile_held(self.lease, pgdata_target) == pgdata)
            return result
        return publish

    def _read_state(self, ctx):
        caps = {e.Purpose.CONFIG: ctx.file(e.Purpose.CONFIG, False)}
        config, _ = ctx.read(caps[e.Purpose.CONFIG], e.Purpose.CONFIG)
        values = {}
        for purpose in (e.Purpose.DATABASE, e.Purpose.SESSION):
            caps[purpose] = ctx.file(purpose, False)
            values[purpose], ref = ctx.read(caps[purpose], purpose)
            need(ref == config['files'][purpose.value])
        state = PrivateState(values[e.Purpose.DATABASE], values[e.Purpose.SESSION], config)
        ctx.bind_read_state(state,caps)
        return state

    def read_existing(self):
        return self._operate({'READY_STOPPED': True, 'VERIFY_FILES': False}, self._read_state)

    def read_existing_with_endpoint_plan(self):
        need(self.config_format is e.ConfigFormat.INSTANCE_SCHEMA3)
        return self._operate({'READY_STOPPED': True}, lambda ctx: _EndpointRecovery(self._read_state(ctx)))

    def _authenticate_new_held(self, plan):
        need(self.config_format is e.ConfigFormat.INSTANCE_SCHEMA3)
        return self._operate_held({'VERIFY_FILES':False},lambda ctx:_AuthenticationRecovery(self._read_state(ctx),plan))

    def _authenticate_existing_held(self):
        need(self.config_format is e.ConfigFormat.INSTANCE_SCHEMA3)
        return self._operate_held({'READY_STOPPED':True},lambda ctx:_AuthenticationRecovery(self._read_state(ctx)))

    def _consume_authentication_held(self, token):
        need(self.lease._operation_owner == get_ident() and self.lease._operation_depth > 0 and not self.failed)
        need(type(token) is StoreAuthentication)
        record = _authenticated_reads.pop(token,None)
        need(record is not None and record[0] is self)
        _,snapshot,state,plan,digest = record
        self.lease._verify()
        need(self.lease.snapshot == snapshot and
             _Operation._value_digest((state.database,state.sessions,state.config)) == digest)
        return state,plan
