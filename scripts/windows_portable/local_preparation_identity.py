"""Private synthetic identity/seed adapters and the protected provider contract.

The existing SESSION envelope has three enterprise identities. The required
reviewer provider must protect and bind separate reviewer material without
relabelling that old envelope. The native implementation is in
native_preparation_sessions; native_composition supplies the concrete Security
and cluster ports while preserving their original activation gates.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol

from parkweave.store import Store
from parkweave import preparation

from .controller import CandidateRefused, NativeDatabaseOperations

ENTERPRISES = ('fixture-a', 'fixture-b', 'fixture-c')
REVIEWERS = tuple('prep-specialist-' + name for name in ENTERPRISES)


@dataclass(frozen=True, repr=False)
class PreparationIdentities:
    values: tuple = field(repr=False)

    @classmethod
    def from_mapping(cls, values):
        names = ENTERPRISES + REVIEWERS
        if (type(values) is not dict or set(values) != set(names)
                or any(type(v) is not str or not 1 <= len(v) <= 512
                       or any(ord(c) < 33 or ord(c) > 126 for c in v) for v in values.values())
                or len(set(values.values())) != len(names)):
            raise CandidateRefused('six distinct protected synthetic identities required')
        return cls(tuple((name, values[name]) for name in names))

    def mapping(self):
        # Revalidate even manually constructed objects; never trust provider aliases.
        result = dict(self.values)
        canonical = type(self).from_mapping(result)
        if self.values != canonical.values:
            raise CandidateRefused('canonical private identity material required')
        return result

    def enterprises(self):
        values = self.mapping()
        return {name: values[name] for name in ENTERPRISES}

    def __reduce__(self):
        raise TypeError('private identity material cannot be serialized')


class PreparationSessionProvider(Protocol):
    """Protected storage dependency, never an acceptance flag.

    All methods use the exact existing lease. NEW is exclusive and uncertainty
    must not be retried. REOPEN only reads; no minting, file repair or grants.
    verify_binding must bind ALL six hashes, protected storage and enterprise
    SESSION to the same physical installation and inputs. A dict is not proof.
    NativePreparationSessionProvider implements these storage methods using
    actual native handles and DPAPI, separately from runtime acceptance.
    """
    def require_support(self, security, database, processes): ...
    def create_exclusive(self, lease, enterprises: dict) -> PreparationIdentities: ...
    def load_existing(self, lease) -> PreparationIdentities: ...
    def publish_binding_exclusive(self, lease, inputs, identities): ...
    def verify_binding(self, lease, inputs, identities): ...


class PreparationSecurity:
    """Explicit delegation; original native admission and creation gates remain."""
    native_acceptance = False

    def __init__(self, security, provider: PreparationSessionProvider):
        self.security, self.provider = security, provider
        self._identities = None
        self._lease = None

    def require_runtime_support(self, database, processes):
        # The actual database remains a NativeDatabaseOperations subclass.
        # IsolatedFixedStoreSecurity therefore still refuses it.
        self.security.require_runtime_support(database, processes)
        self.provider.require_support(self.security, database, processes)

    def require_creation_support(self):
        return self.security.require_creation_support()

    def bind_new_lease(self, lease):
        return self.security.bind_new_lease(lease)

    def create_credentials(self, lease):
        return self.security.create_credentials(lease)

    def _remember(self, lease, value):
        if self._identities is not None or type(value) is not PreparationIdentities:
            raise CandidateRefused('one private identity binding per invocation required')
        self._identities = PreparationIdentities.from_mapping(value.mapping())
        self._lease = lease
        return self._identities

    def create_sessions_exclusive(self, lease):
        enterprises = self.security.create_sessions_exclusive(lease)
        if type(enterprises) is not dict or set(enterprises) != set(ENTERPRISES):
            raise CandidateRefused('original enterprise SESSION required')
        value = self.provider.create_exclusive(lease, dict(enterprises))
        if type(value) is not PreparationIdentities or value.enterprises() != enterprises:
            raise CandidateRefused('reviewer material cannot replace enterprise SESSION')
        return self._remember(lease, value)

    def load_existing_credentials(self, lease):
        credentials = self.security.load_existing_credentials(lease)
        self._remember(lease, self.provider.load_existing(lease))
        return credentials  # Preserve the original opaque cluster capability.

    def verify_existing_files(self, lease):
        return self.security.verify_existing_files(lease)

    def publish_configuration_exclusive(self, lease, inputs):
        self.security.publish_configuration_exclusive(lease, inputs)
        self.provider.publish_binding_exclusive(lease, inputs, self.identities(lease))

    def identities(self, lease):
        if self._lease is not lease or self._identities is None:
            raise CandidateRefused('same held preparation identity material required')
        self._identities.mapping()
        return self._identities

    def verify_database_binding(self, lease, inputs):
        self.security.verify_database_binding(lease, inputs)
        self.provider.verify_binding(lease, inputs, self.identities(lease))

    def application_probe(self, lease):
        probe = self.security.application_probe(lease)
        values = self.identities(lease).mapping()
        if probe.expected() != dict(id='fixture-a', park_id='park-a', org_id='org-a',
                                    role='enterprise_operator') or probe.bearer != values['fixture-a']:
            raise CandidateRefused('original enterprise readiness identity required')
        return probe

    def close_owned_files(self,lease):
        close=getattr(self.security,'close_owned_files',None)
        try:
            if callable(close):return close(lease)
        finally:
            self._identities=None

    def retain_owned_files(self,lease):
        retain=getattr(self.security,'retain_owned_files',None)
        if callable(retain):retain(lease)


class _SeedTransaction(Store):
    """Borrow one already-authorized owner connection without committing it."""
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


def seed_preparation_transaction(connection, identities):
    """SQL consumer seam; caller owns commit/rollback and native authorization.

    Not a native factory or evidence issuer. Never call with an application
    connection to try to establish owner authority.
    """
    if type(identities) is not PreparationIdentities or connection.autocommit is not False:
        raise CandidateRefused('explicit identities and one owner transaction required')
    values = identities.mapping()
    transaction = _SeedTransaction(connection)
    Store.seed(transaction, identities.enterprises())
    preparation.seed_synthetic(transaction, values)


class PreparationDatabaseOperations(NativeDatabaseOperations):
    """Original schema/roles/evidence consumers plus one atomic local seed."""
    def seed(self, owner, identities):
        self._owner(owner)  # Same exact native owner/evidence type checks.
        if type(identities) is not PreparationIdentities:
            raise CandidateRefused('explicit preparation identities required')
        identities.mapping()  # Reject before connecting.
        # owner.connect() retains the REAL live issuer authorization. No receipt
        # is created/copied here. Both existing seed consumers share its single
        # transaction; failure rolls back rather than repairing/retrying grants.
        with owner.connect() as connection:
            seed_preparation_transaction(connection, identities)
