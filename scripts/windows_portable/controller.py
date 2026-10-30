"""Private-instance flow candidate; no concrete native security/process ports.

Not connected to the portable entry. A directory journal is only a refusal/
retry guard, never a database creation receipt or authorization substitute.
"""
from dataclasses import dataclass, field
from typing import Callable, Protocol


class CandidateRefused(RuntimeError):
    pass


def exception_chain(error):
    """Retain objects in causal postorder, without recursion or cycle loops.

    Context, explicit cause, then exception-group children precede the surfaced
    object. First retained leaf is the diagnostic primary; other group leaves
    remain equally real failures, not discarded in favor of that label.
    """
    seen, result, pending = set(), [], [(error, False)]
    while pending:
        current, expanded = pending.pop()
        if current is None:
            continue
        if expanded:
            result.append(current)
            continue
        if id(current) in seen:
            continue
        seen.add(id(current))
        pending.append((current, True))
        children = [current.__context__, current.__cause__]
        if isinstance(current, BaseExceptionGroup):
            children.extend(current.exceptions)
        pending.extend((child, False) for child in reversed(children) if child is not None)
    return tuple(result)


class ControlFailure(RuntimeError):
    def __init__(self, phase, surfaced, cleanup_errors):
        self.phase = phase
        self.outcome = 'UNKNOWN'
        self.surfaced = surfaced
        self.causes = exception_chain(surfaced) if surfaced is not None else ()
        self.primary = self.causes[0] if self.causes else None
        self.cleanup_errors = tuple(cleanup_errors)
        super().__init__(f'PRIVATE_INSTANCE_UNKNOWN:{phase}')

    def public(self):
        # No exception text, paths, DSNs, tokens, environment or page state.
        return dict(outcome=self.outcome, phase=self.phase,
                    cause_count=len(self.causes), cleanup_count=len(self.cleanup_errors),
                    causes=[type(e).__name__[:64] for e in self.causes[:16]],
                    cleanup=[dict(phase=p, types=[type(e).__name__[:64] for e in exception_chain(err)[:16]])
                             for p, err in self.cleanup_errors[:16]])


@dataclass(frozen=True, repr=False)
class DatabaseInputs:
    maintenance_dsn: str = field(repr=False)
    owner_dsn: str = field(repr=False)
    application_dsn: str = field(repr=False)
    data_directory: str = field(repr=False)


class DirectoryLease(Protocol):
    """Exclusive root-bound lease, held until all owned cleanup is observed.

    Production acquisition must validate exact root, ancestors, reparse/ACL,
    existing contents and process ownership. Checkpoints must be durable and
    atomic, contain no secrets, and cannot overwrite an unrelated directory.
    The adapter owns partial-acquisition cleanup until it returns the lease.
    """
    def status(self) -> str: ...
    def checkpoint(self, phase: str, initialized: bool, runtime: str) -> None: ...
    def mark_unknown(self, phase: str) -> None: ...
    def release(self) -> None:
        """An unconfirmed release must remain blocked to open_existing.

        The production adapter must preserve UNKNOWN/refusal using verified
        ownership before handoff, or refuse acquisition after an ambiguous
        handoff even if an older READY_STOPPED journal remains. It must never
        rewrite a journal after ownership may have been lost. The separate
        POSIX implementation requires a new real exclusive acquisition to
        complete RELEASE_PENDING; native Windows durability is not accepted.
        Fake adapters do not prove either operating-system contract.
        """
        ...


class Directories(Protocol):
    def claim_fresh(self, root) -> DirectoryLease:
        """Exclusive new root only; existing/partial/UNKNOWN is never repaired."""
        ...

    def open_existing(self, root) -> DirectoryLease: ...


class Security(Protocol):
    """Unimplemented native safety dependencies, NOT permissive defaults.

    Original SESSION/CONFIG owner/DACL/control contract stays paused. Actual
    implementations require independent review; no journal flag is proof.
    Credentials/session handles below are private objects, never serialized by
    this controller. No import or transfer of NativeDatabaseCreationEvidence.
    """
    def require_creation_support(self) -> None: ...
    def require_runtime_support(self, database, processes) -> None: ...
    def bind_new_lease(self, lease) -> None: ...
    def create_credentials(self, lease): ...
    def create_sessions_exclusive(self, lease):
        """Original secure path creates and verifies new sessions before seed."""
        ...
    def publish_configuration_exclusive(self, lease, inputs: DatabaseInputs) -> None: ...
    def verify_existing_files(self, lease) -> None:
        """Read-only original owner/ACL/control, payload/config/session binding."""
        ...
    def application_probe(self, lease):
        """Read an existing protected session plus expected current actor binding.

        No token creation, fallback actor or configuration repair.
        """
        ...

    def load_existing_credentials(self, lease):
        """Read existing protected secrets only; missing/corrupt is refusal."""
        ...
    def verify_database_binding(self, lease, inputs: DatabaseInputs) -> None:
        """Read-only exact physical DB/owner/schema/files binding, not names.

        Persisted physical cluster identity must allow genuine postmaster
        restart; do not use a saved transient postmaster_start as birth proof.
        """
        ...


class Processes(Protocol):
    """No implementation here can spawn, signal or install anything.

    Register each self-owned group immediately after creation, before waits.
    Until registration succeeds the adapter owns partial-start cleanup. Opaque
    handles must bind exact executable/start identity/root, never a bare PID.
    Returned DSNs and data directory must be bound to that exact owned private
    cluster/root, never discovered or redirected to another listener. Existing
    startup must not run initdb/create roles or repair secrets.
    """
    def create_cluster(self, lease, credentials, register: Callable) -> DatabaseInputs: ...
    def open_cluster(self, lease, credentials, register: Callable) -> DatabaseInputs: ...
    def start_application(self, lease, inputs: DatabaseInputs, register: Callable):
        """Return RegisteredApplication with two distinct exact owned tokens.

        Fixed worker command must use its private readiness stdio/challenge and
        remain before claim until GO. Registration/EOF are not readiness.
        """
        ...
    def stop_owned(self, handle) -> bool:
        """True only after all owned members are confirmed exited; no PID reuse."""
        ...


class Controller:
    def __init__(self, directories: Directories, security: Security, processes: Processes, *, database=None):
        self.directories, self.security, self.processes = directories, security, processes
        self.database = database

    def create(self, root, use):
        from .native_trial_authority import require_owner
        require_owner(self)  # Unbound production: original refusal, ZERO ports.
        return self._run(root, use, fresh=True)

    def reopen(self, root, use):
        # No new-setup gate override; this path cannot initialize or repair.
        return self._run(root, use, fresh=False)

    def _run(self, root, use, *, fresh):
        phase, lease, surfaced = 'PREPARE', None, None
        cleanup, owned = [], []
        initialized = False

        def register(handle):
            if handle is None or any(handle is previous for previous in owned):
                raise CandidateRefused('owned process registration refused')
            owned.append(handle)

        def checkpoint(next_phase, runtime='STARTING'):
            nonlocal phase
            phase = next_phase
            from .native_trial_authority import budget
            budget(self)
            lease.checkpoint(phase, initialized, runtime)

        try:
            from .native_trial_authority import budget
            budget(self)
            db = self.database if self.database is not None else NativeDatabaseOperations()
            self.security.require_runtime_support(db,self.processes)
            if fresh:
                self.security.require_creation_support()
                prepared = db.prepare_new()  # Verify original roles bytes before CREATE.
            phase = 'ACQUIRE'
            lease = (self.directories.claim_fresh(root) if fresh else self.directories.open_existing(root))
            if lease.status() != ('NEW' if fresh else 'READY_STOPPED'):
                raise CandidateRefused('fresh or confirmed stopped installation required')
            from .native_trial_authority import attach_controller
            attach_controller(self,lease,register)
            if fresh:
                self.security.bind_new_lease(lease)  # NEW plan must precede CREDENTIALS; mandatory, not optional.
                checkpoint('CREDENTIALS')
                credentials = self.security.create_credentials(lease)
            else:
                phase = 'VERIFY_FILES'
                self.security.verify_existing_files(lease)
                credentials = self.security.load_existing_credentials(lease)
                initialized = True
            checkpoint('CLUSTER')
            inputs = (self.processes.create_cluster(lease, credentials, register) if fresh else
                      self.processes.open_cluster(lease, credentials, register))
            if not owned or type(inputs) is not DatabaseInputs:
                raise CandidateRefused('registered private cluster and explicit inputs required')
            if fresh:
                checkpoint('CREATE_SCHEMA')
                owner = db.create_schema32(inputs)
                checkpoint('ROLES')
                db.grant_roles(owner, prepared)
                checkpoint('SESSIONS')
                identities = self.security.create_sessions_exclusive(lease)
                checkpoint('SEED')
                db.seed(owner, identities)
                checkpoint('CONFIG')
                self.security.publish_configuration_exclusive(lease, inputs)
                checkpoint('VERIFY_FILES')
                self.security.verify_existing_files(lease)
            checkpoint('VERIFY_DATABASE')
            db.verify_existing(inputs)
            self.security.verify_database_binding(lease, inputs)
            initialized = True
            checkpoint('READY', 'STOPPED')
            checkpoint('APPLICATION')
            before = len(owned)
            application = self.processes.start_application(lease, inputs, register)
            if len(owned) <= before:
                raise CandidateRefused('registered application ownership required')
            from .application_readiness import require_application_ready, check_before_running, activate_application
            ready = require_application_ready(lease,inputs,application,self.security.application_probe(lease),owned[before:])
            self.security.verify_database_binding(lease,inputs)  # Recheck physical source after both startup probes.
            check_before_running(ready)
            checkpoint('RUNNING', 'RUNNING')
            activate_application(ready)  # Exact worker GO only after durable RUNNING.
            budget(self)
            use(application)  # Return values stay private; never become report data.
            budget(self)
        except BaseException as error:
            surfaced = error
        finally:
            # Only returned/registered capabilities, in reverse launch order.
            for handle in reversed(owned):
                try:
                    if self.processes.stop_owned(handle) is not True:
                        raise CandidateRefused('owned exit confirmation unavailable')
                except BaseException as error:
                    cleanup.append(('STOP_OWNED', error))
            if lease is not None:
                closer=getattr(self.security,'close_owned_files',None)
                if callable(closer) and not cleanup:
                    try:closer(lease)
                    except BaseException as error:
                        cleanup.append(('CLOSE_SECURITY_FILES',error))
                        retain=getattr(self.security,'retain_owned_files',None)
                        if callable(retain):
                            try:retain(lease)
                            except BaseException as nested:cleanup.append(('RETAIN_SECURITY_FILES',nested))
                elif cleanup:
                    retain=getattr(self.security,'retain_owned_files',None)
                    if callable(retain):
                        try:retain(lease)
                        except BaseException as error:cleanup.append(('RETAIN_SECURITY_FILES',error))
                try:
                    if surfaced is not None or cleanup:
                        lease.mark_unknown(phase)
                    else:
                        lease.checkpoint('READY_STOPPED', initialized, 'STOPPED')
                except BaseException as error:
                    cleanup.append(('FINAL_STATE', error))
                    try:
                        lease.mark_unknown(phase)
                    except BaseException as nested:
                        cleanup.append(('UNKNOWN_STATE', nested))
                try:
                    lease.release()
                except BaseException as error:
                    cleanup.append(('RELEASE', error))
                    # Ownership may already be gone. Do not write/reacquire
                    # here; the lease adapter must conservatively block the
                    # unconfirmed handoff on the next open_existing.
        from .native_trial_authority import detach_controller
        detach_controller(self)
        if surfaced is not None or cleanup:
            failure = ControlFailure(phase, surfaced, cleanup)
            raise failure from surfaced
        return dict(initialization='READY', runtime='STOPPED_CONFIRMED', mode='NEW' if fresh else 'REOPEN')


class NativeDatabaseOperations:
    """Real original consumers; ports and production activation remain absent."""
    ROLES_SHA256 = '604d084e12d84e9cad808ddd4a7e61289390faca49fd657d2ffe711b5a43afc3'

    def bind_owned_endpoint(self,endpoint):
        from .native_database_endpoint import NativeOwnedDatabaseEndpoint
        if type(endpoint) is not NativeOwnedDatabaseEndpoint or getattr(self,'_owned_endpoint',None) is not None:
            raise CandidateRefused('one exact native database endpoint required')
        endpoint.verify()
        self._owned_endpoint=endpoint

    def prepare_new(self):
        from hashlib import sha256
        from pathlib import Path
        from parkweave import store
        raw = Path(store.__file__).with_name('roles.sql').read_bytes()
        if sha256(raw).hexdigest() != self.ROLES_SHA256:
            raise CandidateRefused('original roles integrity refused')
        return raw

    def create_schema32(self, inputs):
        from .initialize import create_fresh_native_schema32
        return create_fresh_native_schema32(inputs.maintenance_dsn, inputs.owner_dsn,
                                          inputs.application_dsn, inputs.data_directory,
            **({'endpoint':self._owned_endpoint} if getattr(self,'_owned_endpoint',None) is not None else {}))

    def _owner(self, owner):
        from parkweave.installed_fixture_receipt import _InstalledSyntheticSetupStore, NativeDatabaseCreationEvidence
        if (type(owner) is not _InstalledSyntheticSetupStore or
                type(getattr(owner, '_case_fact_fixture_receipt', None)) is not NativeDatabaseCreationEvidence):
            raise CandidateRefused('exact live native owner required')
        endpoint=getattr(self,'_owned_endpoint',None)
        if endpoint is not None and owner._owned_database_endpoint is not endpoint:
            raise CandidateRefused('same original native owner endpoint required')

    def grant_roles(self, owner, prepared):
        from hashlib import sha256
        self._owner(owner)
        if type(prepared) is not bytes or sha256(prepared).hexdigest() != self.ROLES_SHA256:
            raise CandidateRefused('original roles integrity refused')
        with owner.connect() as connection:
            if connection.execute('SELECT max(version) AS version FROM schema_version').fetchone()['version'] != 32:
                raise CandidateRefused('schema32 required before roles')
            connection.execute(prepared.decode('utf-8'))

    def seed(self, owner, identities):
        self._owner(owner)
        if (type(identities) is not dict or set(identities) != {'fixture-a', 'fixture-b', 'fixture-c'} or
                any(type(v) is not str or not 1 <= len(v) <= 512 for v in identities.values()) or
                len(set(identities.values())) != 3):
            raise CandidateRefused('original distinct synthetic session identities required')
        from parkweave.store import Store
        Store.seed(owner, identities)

    def verify_existing(self, inputs):
        from parkweave.installed_fixture_receipt import _dsn, _connect_bound
        from scripts.windows.lifecycle import check_dsn_scope
        parsed = _dsn(inputs.application_dsn, 'parkweave')
        if parsed['host'] != '127.0.0.1':
            raise CandidateRefused('original Setup host required')
        def read_only():
            connection = _connect_bound(parsed, autocommit=False,endpoint=getattr(self,'_owned_endpoint',None))
            try:
                connection.execute('SET TRANSACTION READ ONLY')
            except BaseException:
                connection.close()
                raise
            return connection

        check_dsn_scope(inputs.application_dsn, app=True, connector=read_only)
        with read_only() as connection:
            row = connection.execute('SELECT max(version) AS version FROM schema_version').fetchone()
            if not row or type(row['version']) is not int or row['version'] != 32:
                raise CandidateRefused('existing schema32 required; no migration on reopen')
