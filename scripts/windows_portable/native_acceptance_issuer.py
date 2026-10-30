"""Consume original native observations under a reviewed platform policy.

Execution permission, coverage reports, lifecycle READY and caller dictionaries
are not evidence. No platform policy has been accepted in this source revision.
The concrete business producer is wired; the remaining producer gaps are
reported explicitly. This module cannot open any existing product gate.
"""
from dataclasses import dataclass
import math
import sys
import time
import weakref

from .native_acceptance_contract import Area, requirement


class AcceptanceRefused(RuntimeError):
    def __init__(self, reason, missing=()):
        self.reason, self.missing = reason, tuple(missing)
        super().__init__(reason)  # No native paths, material, credentials or exception text.


@dataclass(frozen=True)
class _PlatformPolicy:
    nt_version: tuple
    system_crt_sha256: tuple
    minimum_crt_versions: tuple = ()
    # Reviewed exact image paths, not hashes of an EXE that embeds this policy.
    # Actual image hashes come from the separately pinned candidate manifest.
    toolset_image_scope: tuple = ()


# A later source review must supply an exact policy and the missing concrete
# producers. No input file, constructor argument or environment can set it.
_REVIEWED_POLICY = None


class VerifiedNativeObservation:
    __slots__ = ('__weakref__',)
    def __reduce__(self): raise TypeError('native observation cannot be serialized')
    def __copy__(self): raise TypeError('native observation cannot be copied')
    def __deepcopy__(self, memo): raise TypeError('native observation cannot be copied')


class AcceptedInstallationCapability:
    __slots__ = ('__weakref__',)
    def __reduce__(self): raise TypeError('native acceptance cannot be serialized')
    def __copy__(self): raise TypeError('native acceptance cannot be copied')
    def __deepcopy__(self, memo): raise TypeError('native acceptance cannot be copied')


_observed = weakref.WeakKeyDictionary()
_accepted = weakref.WeakKeyDictionary()


def _need(value, reason='ORIGINAL_NATIVE_ACCEPTANCE_REQUIRED'):
    if not value:
        raise AcceptanceRefused(reason)


def _deadline(deadline):
    _need(type(deadline) in (int, float) and math.isfinite(deadline)
          and 0 < deadline-time.monotonic() <= 30, 'NATIVE_ACCEPTANCE_DEADLINE')


def observe_business_restart(proof, invocation, deadline):
    """Actual producer consumption, only inside the second live callback."""
    _deadline(deadline)
    from .native_business_adapter import inspect_restart
    snapshot = inspect_restart(proof, invocation, deadline)
    from .native_trial_authority import bound_state
    if bound_state(snapshot.lease) is not None:
        from .native_trial_facts import subject
        binding=subject(snapshot.lease)
    else:binding=snapshot
    cap = VerifiedNativeObservation()
    _observed[cap] = ('business', invocation, proof, binding, deadline)
    return cap


def observe_trial_fact(proof,invocation,deadline):
    _deadline(deadline)
    from .native_trial_facts import inspect
    binding,names=inspect(proof,invocation.processes.lease,deadline)
    cap=VerifiedNativeObservation()
    _observed[cap]=('trial_fact',invocation,proof,binding,deadline)
    return cap


def _inspect(cap, invocation, deadline):
    _deadline(deadline)
    _need(type(cap) is VerifiedNativeObservation and cap in _observed)
    kind, original, proof, binding, expires = _observed[cap]
    _need(invocation is original and deadline <= expires and time.monotonic() < expires)
    if kind=='business':
        from .native_business_adapter import inspect_restart
        snapshot=inspect_restart(proof,invocation,deadline)
        from .native_trial_authority import bound_state
        if bound_state(snapshot.lease) is not None:
            from .native_trial_facts import subject
            current=subject(snapshot.lease)
        else:current=snapshot
        _need(current==binding)
        return ('complete_native_business_restart',),binding
    _need(kind=='trial_fact')
    from .native_trial_facts import inspect
    current,names=inspect(proof,invocation.processes.lease,deadline)
    _need(current==binding)
    return names,binding


def collect_trial_facts(invocation,deadline):
    from .native_trial_authority import bound_state
    from .native_trial_facts import inspect
    value=bound_state(invocation.processes.lease);_need(value is not None)
    seen=set();result=[]
    for fact in reversed(value.facts):
        _,names=inspect(fact,invocation.processes.lease,deadline)
        if not seen.intersection(names):
            result.append(observe_trial_fact(fact,invocation,deadline));seen.update(names)
    return tuple(result)


def observed_requirements(invocation,observations,deadline):
    names=set();binding=None
    for observation in observations:
        current_names,current=_inspect(observation,invocation,deadline)
        _need(binding is None or current==binding)
        _need(not names.intersection(current_names),'DUPLICATE_NATIVE_OBSERVATION')
        names.update(current_names);binding=current
    return tuple(sorted(names))


def issuer_status():
    required = tuple(name for area in Area for name in requirement(area).observations)
    implemented=('complete_native_business_restart','derived_token_owner_and_default_dacl',
        'original_primary_token_unchanged','protected_new_objects','dpapi_current_user_roundtrip',
        'dpapi_wrong_entropy_refused','original_initdb_pipe_and_job','original_fixed_slots_write_flush_readback',
        'same_file_reopen','exclusive_open_refused','torn_slot_refused_without_repair','interrupted_process_recovery',
        'target_filesystem_durability_scope','signed_system_crt_files','minimum_toolset_compatibility',
        'dpapi_cross_os_identity_isolation','api_set_resolution')
    return dict(native_acceptance='NOT_ACCEPTED', activation_allowed=False, usable_product=False,
        reviewed_platform_policy=False,
        implemented_producers=list(implemented),
        policy_inputs_missing=['reviewed minimum CRT versions and exact native-image scope; policy is unset',
            'reviewed exact OS tuple and namespace layout/flag/alias semantics; namespace policy is unset'],
        missing_producers=[name for name in required if name not in implemented])


def issue_accepted(invocation, observations, deadline):
    """Issue only a complete, same-live-installation, source-policy-bound cap.

    It is deliberately impossible to issue with this revision's incomplete
    producer set. The algorithm refuses the actual missing requirements rather
    than treating an execution window or a supplied complete name list as PASS.
    """
    _deadline(deadline)
    _need(type(observations) is tuple and len(observations) <= 32)
    names, binding = set(), None
    for cap in observations:
        current_names, current = _inspect(cap, invocation, deadline)
        _need(not names.intersection(current_names), 'DUPLICATE_NATIVE_OBSERVATION')
        names.update(current_names)
        _need(binding is None or binding == current, 'NATIVE_OBSERVATION_BINDING_CHANGED')
        binding = current
    missing = tuple(name for area in Area for name in requirement(area).observations if name not in names)
    if missing:
        raise AcceptanceRefused('NATIVE_ACCEPTANCE_EVIDENCE_INCOMPLETE', missing)
    from .native_trial_authority import bound_state
    _need(bound_state(invocation.controller) is None,'TRIAL_ONLY_IS_NOT_PRODUCT_ACTIVATION')
    policy = _REVIEWED_POLICY
    _need(type(policy) is _PlatformPolicy, 'REVIEWED_PLATFORM_ACCEPTANCE_POLICY_REQUIRED')
    _policy_binding(policy, invocation, binding)
    _deadline(deadline)
    cap = AcceptedInstallationCapability()
    _accepted[cap] = (invocation, observations, binding, policy, deadline)
    return cap


def _policy_binding(policy, invocation, binding):
    _need(policy is _REVIEWED_POLICY and type(policy) is _PlatformPolicy and binding is not None)
    # Product source/manifest come from the original installation and trial
    # chain. Hardcoding this package's own hash into its own policy is circular.
    binding.installation._issued_binding(binding.lease,dict(binding.runtime))
    _need(hasattr(sys, 'getwindowsversion'), 'EXACT_NATIVE_PLATFORM_REQUIRED')
    version = sys.getwindowsversion()
    _need((version.major, version.minor, version.build, version.product_type) == policy.nt_version,
          'REVIEWED_PLATFORM_POLICY_MISMATCH')
    witness = invocation.security.security.system_crt
    witness._binding()
    _need(tuple(sorted((name, row[2]) for name, row in witness.rows.items())) == policy.system_crt_sha256,
          'REVIEWED_CRT_POLICY_MISMATCH')


def require_accepted(cap, area, invocation, deadline):
    _deadline(deadline)
    _need(type(area) is Area and type(cap) is AcceptedInstallationCapability and cap in _accepted)
    original, observations, binding, policy, expires = _accepted[cap]
    _need(invocation is original and deadline <= expires and time.monotonic() < expires)
    _policy_binding(policy, invocation, binding)
    names = set()
    for observation in observations:
        current_names, current = _inspect(observation, invocation, deadline)
        _need(current == binding, 'NATIVE_ACCEPTANCE_BINDING_CHANGED')
        names.update(current_names)
    _need(set(requirement(area).observations) <= names)
    _deadline(deadline)
    return None
