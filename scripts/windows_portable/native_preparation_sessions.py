"""Native DPAPI preparation identities bound to original held file capabilities.

No import-time Windows calls. NEW remains behind the original owner gate.
REOPEN reads only; neither missing ciphertext nor a missing binding is repaired.
Native execution/acceptance is separate from this implementation.
"""
from enum import Enum
import hashlib
import json
import secrets
import time

from . import credential_envelope as e
from .controller import CandidateRefused, DatabaseInputs
from .fixed_secret_store import _under_lease
from .local_preparation_identity import ENTERPRISES, REVIEWERS, PreparationIdentities
from .native_secret_store_candidate import _NativeFixedSecretStore


class PreparationFile(Enum):
    IDENTITIES = 'preparation-identities.dpapi'
    BINDING = 'preparation-binding.dpapi'


def need(value):
    if not value:
        raise CandidateRefused('NATIVE_PREPARATION_IDENTITIES_REFUSED')


class NativePreparationSessionProvider:
    """Separate protected reviewer storage; original enterprise SESSION unchanged."""
    native_acceptance = False

    def __init__(self):
        self.security = self.lease = self._identities = None
        self._created = self._published = False
        self.failed = False

    def require_support(self, security, database, processes):
        from .local_preparation_identity import PreparationDatabaseOperations
        from .instance_processes import InstanceProcesses
        need(not self.failed and self.security is None
             and type(database) is PreparationDatabaseOperations and type(processes) is InstanceProcesses)
        self.security = security

    def _store(self, lease):
        need(not self.failed and self.security is not None)
        store = getattr(self.security, 'store', None)
        need(type(store) is _NativeFixedSecretStore and store.lease is lease
             and (self.lease is None or self.lease is lease))
        store._native_check()
        self.lease = lease
        return store

    def _operation(self, lease, operation):
        def held():
            store = self._store(lease)
            try:
                return operation(store)
            except BaseException:
                self.failed = True
                raise
        return _under_lease(lease, held)

    def _aad(self, store, kind):
        return dict(schema='parkweave-native-preparation-identities/1',
                    installation=store.binding.record(), runtime=json.loads(store.runtime), purpose=kind.name)

    def _file(self, store, kind, value=None):
        """Hold original parent+file handles through DPAPI, flush and reread."""
        api = store.api
        # Give each explicitly invoked operation a bounded native query window.
        # Never extend the caller's original deadline.
        need(time.monotonic() < api.deadline)
        parent = file = None
        primary = None
        cleanup = []
        result = None
        try:
            parent = api.open_secrets(store.lease)
            file = api.open_preparation_file(parent, kind, create=value is not None)
            before = api.inspect(file)
            aad = self._aad(store, kind)
            entropy = hashlib.sha256(e.canonical(aad)).digest()
            if value is not None:
                raw = e.canonical(dict(binding=aad, value=value))
                need(0 < len(raw) <= e.MAX_PLAINTEXT)
                cipher = store.protection.protect(raw, entropy)
                need(api.write(file, cipher) == len(cipher) and api.flush(file) is True)
            observed = api.inspect(file)
            need(observed.identity == before.identity and observed.parent == before.parent
                 and observed.owner == before.owner and observed.raw_dacl == before.raw_dacl)
            raw = api.read(file, e.MAX_CIPHERTEXT + 1)
            need(len(raw) == observed.size and 0 < len(raw) <= e.MAX_CIPHERTEXT)
            if value is not None:
                need(raw == cipher)
            decoded = store.protection.unprotect(raw, entropy)
            parsed = json.loads(decoded, object_pairs_hook=e.pairs)
            need(e.canonical(parsed) == decoded and set(parsed) == {'binding', 'value'}
                 and e.canonical(parsed['binding']) == e.canonical(aad))
            result = parsed['value']
            if value is not None:
                need(e.canonical(result) == e.canonical(value))
            need(api.inspect(file) == observed)
        except BaseException as error:
            primary = error
        finally:
            for cap in (file, parent):
                if cap is not None:
                    try:
                        need(api.close(cap) is True)
                    except BaseException as error:
                        cleanup.append(error)
        if primary is not None or cleanup:
            self.failed = True
            raise BaseExceptionGroup('NATIVE_PREPARATION_STORAGE_UNKNOWN',
                ([primary] if primary is not None else []) + cleanup) from None
        return result

    def create_exclusive(self, lease, enterprises):
        from scripts.windows.lifecycle import require_setup_readiness
        require_setup_readiness()  # Before RNG, DPAPI, files or native queries.
        need(not self._created and type(enterprises) is dict and set(enterprises) == set(ENTERPRISES))
        self._created = True
        identities = PreparationIdentities.from_mapping({**enterprises,
            **{name: secrets.token_urlsafe(48) for name in REVIEWERS}})
        self._operation(lease, lambda store: self._file(store, PreparationFile.IDENTITIES, identities.mapping()))
        self._identities = identities
        return identities

    def load_existing(self, lease):
        need(self._identities is None and not self._created)
        def load(store):
            state = getattr(self.security, 'state', None)
            need(state is not None)
            identities = PreparationIdentities.from_mapping(self._file(store, PreparationFile.IDENTITIES))
            need(identities.enterprises() == state.sessions)
            return identities
        self._identities = self._operation(lease, load)
        return self._identities

    def _binding(self, store, inputs, identities):
        need(type(inputs) is DatabaseInputs and type(identities) is PreparationIdentities
             and identities is self._identities and inputs is self.security.inputs)
        state = self.security.state
        need(state is not None and identities.enterprises() == state.sessions)
        return dict(database=state.config['database'], endpoints=state.config['endpoints'],
                    original_files=state.config['files'],
                    identities={name: hashlib.sha256(value.encode('ascii')).hexdigest()
                                for name, value in identities.mapping().items()})

    def publish_binding_exclusive(self, lease, inputs, identities):
        from scripts.windows.lifecycle import require_setup_readiness
        require_setup_readiness()
        need(not self._published and self._created)
        self._published = True
        return self._operation(lease, lambda store: self._file(store, PreparationFile.BINDING,
            self._binding(store, inputs, identities)))

    def verify_binding(self, lease, inputs, identities):
        def verify(store):
            expected = self._binding(store, inputs, identities)
            observed = self._file(store, PreparationFile.BINDING)
            need(e.canonical(expected) == e.canonical(observed))
            need(self._file(store, PreparationFile.IDENTITIES) == identities.mapping())
        return self._operation(lease, verify)
