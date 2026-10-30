"""Actual Controller/PG/API business trial; no gate override or report issuer.

The default entry is refused by the original OWNER gate before RNG/OS calls.
An eventual approved trial admission must be separate from product acceptance.
This adapter uses no Windows test-owner DSN, external service or fake provider.
"""
from dataclasses import dataclass
import math
import threading
import time
import weakref

from . import endpoint_plan as ep
from .controller import CandidateRefused
from .local_preparation import LocalPreparationInvocation
from .local_preparation_transport import OwnedPreparationRequest
from .native_cluster import NativeProtectedClusterProcesses
from .native_instance_security import NativeFixedStoreSecurity
from .native_preparation_sessions import NativePreparationSessionProvider
from .preparation_business_trial import PreparationBusinessTrial
from .processes import PrivateProcessAdapter
from .windows_process_handles import WindowsJobProcess, consume_stopped_group


def need(value):
    if not value:
        raise CandidateRefused('ORIGINAL_NATIVE_BUSINESS_TRIAL_REQUIRED')


@dataclass(frozen=True, repr=False)
class _Snapshot:
    lease: object
    installation: object
    runtime: tuple
    files: tuple
    instance: str
    generation: int
    database: bytes
    groups: tuple


class BusinessRestartObservation:
    __slots__ = ('__weakref__',)
    def __reduce__(self): raise TypeError('native observation cannot be serialized')
    def __copy__(self): raise TypeError('native observation cannot be copied')
    def __deepcopy__(self, memo): raise TypeError('native observation cannot be copied')


_issued = weakref.WeakKeyDictionary()


def _composition(invocation, mode):
    need(type(invocation) is LocalPreparationInvocation
         and type(invocation.transport) is OwnedPreparationRequest)
    processes = invocation.processes
    security = invocation.security.security
    provider = invocation.security.provider
    need(type(security) is NativeFixedStoreSecurity and security.mode is mode
         and type(provider) is NativePreparationSessionProvider
         and type(processes.cluster) is NativeProtectedClusterProcesses
         and processes.cluster.prerequisites.security is security
         and processes.endpoint_source is security and processes.session_provider is provider)
    return processes, security


def _snapshot(invocation, deadline):
    processes, security = _composition(invocation, invocation.security.security.mode)
    lease, inputs = processes.lease, processes.inputs
    need(type(deadline) in (int, float) and math.isfinite(deadline)
         and 0 < deadline - time.monotonic() <= 30 and not processes.failed)
    def held(_):
        lease._verify()
        need(lease.record['phase'] == 'RUNNING' and processes.application is not None)
        from .pgdata_candidate import _path_held
        need(inputs is security.inputs and inputs.data_directory == _path_held(lease, security.target))
        installation = security.runtime_installation
        installation._issued_binding(lease, security.runtime)
        installation.deadline = installation.probe.deadline = deadline
        installation.verify()
        database = security._database(inputs, deadline=deadline)
        from .native_trial_authority import bound_state
        if bound_state(lease) is not None:
            from .native_trial_facts import protected_objects,signed_crt,minimum_runtime
            if lease.record['generation']==1:
                protected_objects(lease,security)
                from .native_trial_slot_probes import NativeSlotProbes
                NativeSlotProbes(lease,security).run()
            signed_crt(lease,security.system_crt)
            minimum_runtime(lease,security.system_crt,deadline)
        from .credential_envelope import canonical
        groups = []
        # Only currently live postgres/API/worker are restart subjects. The
        # already completed initdb is not relabelled as a live server.
        for token, owner, stopped, attempted in processes._owned.values():
            if stopped:continue  # Original registered auxiliary Job already confirmed closed.
            adapter = owner if type(owner) is PrivateProcessAdapter else processes.cluster._adapters.get(id(token))
            need(type(adapter) is PrivateProcessAdapter)
            group = adapter._group(token)
            if group.stopped:
                continue
            need(not stopped and not attempted and type(adapter.backend) is WindowsJobProcess
                 and group.resources.get('bound'))
            identity = adapter.live_identity(token)
            groups.append((adapter, token, identity))
        need(len(groups) == 3 and len({id(token) for _, token, _ in groups}) == 3)
        names = sorted(adapter._group(token).command.relative_executable for adapter, token, _ in groups)
        need(names == ['runtime/postgresql/bin/postgres.exe', 'runtime/python/python.exe', 'runtime/python/python.exe'])
        from .native_iat_observer import capture_groups
        capture_groups(lease,security.system_crt,tuple(groups),deadline,security._iat_images)
        files = (tuple(lease.fs.root_id), tuple(lease.fs.lock_id), tuple(lease.fs.identity()))
        return _Snapshot(lease, installation, tuple(sorted(security.runtime.items())), files,
            lease._verified_instance_uuid(), lease.record['generation'], canonical(database), tuple(groups))
    return security._run(lease, held, deadline=deadline)


def inspect_restart(observation, invocation, deadline):
    """Issuer input: revalidate the still-live original second invocation.

    No dictionary/name list can stand in for this registry-issued observation.
    It proves this business restart only; OWNER/journal/loader policy remains
    independently required. It expires as soon as this invocation stops.
    """
    need(type(observation) is BusinessRestartObservation and observation in _issued)
    original, expected, expires = _issued[observation]
    need(type(deadline) in (int, float) and math.isfinite(deadline)
         and deadline <= expires and time.monotonic() < expires
         and invocation is original and _snapshot(invocation, deadline) == expected)
    return expected


class NativeBusinessTestAdapter:
    """Business-window budget; NOT a source-approved OS execution window.

    Native initialization retains original per-operation budgets. A future
    trial execution entry must separately enforce its approved total deadline.
    This adapter neither issues that permission nor skips any original gate.
    """
    def __init__(self, first, reopened, root, *, business_seconds=180):
        _, a = _composition(first, ep.PlanMode.NEW)
        _, b = _composition(reopened, ep.PlanMode.REOPEN)
        need(first is not reopened and first.controller is not reopened.controller
             and first.processes is not reopened.processes and a is not b
             and first.security.provider is not reopened.security.provider
             and a.runtime == b.runtime
             and first.controller.directories.base == reopened.controller.directories.base)
        self.first, self.reopened, self.root = first, reopened, root
        self.trial = PreparationBusinessTrial(seconds=business_seconds)
        self.started = False
        self._entry_lock = threading.Lock()

    def run(self, *, consume=lambda observation: None):
        from .native_trial_authority import require_owner,bound_state
        require_owner(self.first.controller)  # Source-bound TRIAL_ONLY or original refusal.
        need(self._entry_lock.acquire(blocking=False))
        try:
            need(not self.started and callable(consume))
            self.started = True
        finally:
            self._entry_lock.release()
        deadline = self.trial.begin()
        first_snapshot = None
        def first_use(workspace):
            nonlocal first_snapshot
            self.trial.create(workspace)
            first_snapshot = _snapshot(self.first, min(deadline, time.monotonic() + 20))
        need(time.monotonic() < deadline)
        self.first.create(self.root, first_use, deadline=deadline)
        need(first_snapshot is not None and not first_snapshot.lease.active)
        # Consumes original before-close observations. Merely obtaining a
        # STOPPED_CONFIRMED dictionary never proves a native process stopped.
        for adapter, token, identity in first_snapshot.groups:
            consume_stopped_group(adapter, token, identity)
        trial=bound_state(self.first.controller)
        if trial is not None:
            need(len(trial.generations)==1 and trial.generations[0] is first_snapshot.lease)
            trial.restart_ready=True
        observed = False
        def reopened_use(workspace):
            nonlocal observed
            self.trial.reopened(workspace)
            now = _snapshot(self.reopened, min(deadline, time.monotonic() + 20))
            before = first_snapshot
            need(now.lease is not before.lease and now.installation is not before.installation
                 and now.runtime == before.runtime and now.files == before.files
                 and now.instance == before.instance and now.generation == before.generation + 1
                 and now.database == before.database)
            need(not {identity[1] for _, _, identity in before.groups}.intersection(
                identity[1] for _, _, identity in now.groups))
            from .native_trial_facts import journal_reopen
            journal_reopen(now.lease)
            proof = BusinessRestartObservation()
            _issued[proof] = (self.reopened, now, deadline)
            try:
                consume(proof)  # Only while original second HANDLEs/lease live.
                inspect_restart(proof, self.reopened, min(deadline, time.monotonic() + 20))
                observed = True
            finally:
                _issued.pop(proof, None)
        need(time.monotonic() < deadline)  # Never knowingly start after expiry.
        self.reopened.reopen(self.root, reopened_use, deadline=deadline)
        need(observed)
        return dict(result='NATIVE_BUSINESS_RESTART_OBSERVED',
            activation_allowed=False, usable_product=False, native_acceptance='NOT_ACCEPTED')
