"""Fixed-object storage algorithm using explicit in-memory capability doubles.

No real filesystem/DPAPI adapter, path arguments, controller or native activation.
Fake capabilities/ACL facts are never Windows ownership or durability evidence.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
import hashlib
from types import MappingProxyType

from . import credential_envelope as e
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


class _Operation:
    def __init__(self, store):
        self.store = store; self.directory = None; self.caps = []; self.pins = {}

    def check(self):
        s = self.store; s.lease._verify()
        need(s.api.binds(s.lease) is True)
        r = s.lease.record
        need(tuple(r['root']) == s.binding.root and tuple(r['lock']) == s.binding.lock
             and tuple(r['journal']) == s.binding.journal and r['handoff'] == 'OWNED')
        s.binding.record()
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
            need(before[2] == after.raw_dacl and before[1] & ~1 == after.control & ~1)
            need(after.size == 0)
        return cap

    def read(self, cap, purpose, expected_ciphertext=None):
        self.check(); raw = self.store.api.read(cap, e.MAX_CIPHERTEXT+1)
        need(type(raw) is bytes and 0 < len(raw) <= e.MAX_CIPHERTEXT and len(raw) == self.pins[cap].size)
        need(expected_ciphertext is None or raw == expected_ciphertext)
        self.check()
        plain = self.store.protection.unprotect(raw, e.entropy_bytes(self.store.binding, purpose))
        value = e.decode_plaintext(self.store.binding, purpose, plain)
        self.check()
        ref = dict(identity=list(self.pins[cap].identity), ciphertext_sha256=hashlib.sha256(raw).hexdigest())
        return value, ref

    def write(self, purpose, payload):
        self.check()
        plain = e.encode_plaintext(self.store.binding, purpose, payload)
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

    def __init__(self, lease, binding, api, protection):
        need(type(lease) is FixedDirectoryLease and type(binding) is e.InstanceBinding
             and isinstance(api, FakeSecretAPI) and type(protection) is IsolatedUserProtection)
        self.lease, self.binding, self.api, self.protection = lease, binding, api, protection
        self.failed = False; self._unknown_caps = []

    def _operate(self, states, operation):
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
                    except BaseException as error:
                        self._unknown_caps.append(cap); cleanup.append(error)
                try: self.lease._verify()
                except BaseException as error: cleanup.append(error)
            if primary is not None or cleanup:
                journal_error = None; self.failed = True
                try:
                    if not self.lease.poisoned:
                        self.lease._publish(dict(phase='UNKNOWN', runtime='UNKNOWN', handoff='OWNED'))
                except BaseException as error: journal_error = error
                finally: self.lease.poisoned = True
                raise StoreFailure(primary, cleanup, journal_error) from None
            return result
        try:
            return _under_lease(self.lease, run)
        except BaseException as error:
            if isinstance(error, StoreFailure): raise
            if isinstance(error, LeaseRefused) and error.args == ('FIXED_LEASE_OPERATION_BUSY',): raise
            self.failed = True
            raise StoreFailure(error, (), None) from None

    def create(self, purpose, payload):
        need(type(purpose) is e.Purpose and purpose in (e.Purpose.DATABASE, e.Purpose.SESSION))
        phase = 'CREDENTIALS' if purpose is e.Purpose.DATABASE else 'SESSIONS'
        return self._operate({phase: False}, lambda ctx: ctx.write(purpose, payload))

    def publish_config(self, database, runtime):
        def publish(ctx):
            refs = {}
            for purpose in (e.Purpose.DATABASE, e.Purpose.SESSION):
                cap = ctx.file(purpose, False)
                _, refs[purpose.value] = ctx.read(cap, purpose)
            payload = dict(schema=2, files=refs, database=database, runtime=runtime)
            return ctx.write(e.Purpose.CONFIG, payload)
        return self._operate({'CONFIG': False}, publish)

    def read_existing(self):
        def read(ctx):
            config, _ = ctx.read(ctx.file(e.Purpose.CONFIG, False), e.Purpose.CONFIG)
            values = {}
            for purpose in (e.Purpose.DATABASE, e.Purpose.SESSION):
                values[purpose], ref = ctx.read(ctx.file(purpose, False), purpose)
                need(ref == config['files'][purpose.value])
            return PrivateState(values[e.Purpose.DATABASE], values[e.Purpose.SESSION], config)
        return self._operate({'READY_STOPPED': True, 'VERIFY_FILES': False}, read)
