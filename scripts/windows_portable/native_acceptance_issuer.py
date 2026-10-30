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
    source_commit: str
    manifest_sha256: str
    nt_version: tuple
    system_crt_sha256: tuple


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
    cap = VerifiedNativeObservation()
    _observed[cap] = ('complete_native_business_restart', invocation, proof, snapshot, deadline)
    return cap


def _inspect(cap, invocation, deadline):
    _deadline(deadline)
    _need(type(cap) is VerifiedNativeObservation and cap in _observed)
    name, original, proof, snapshot, expires = _observed[cap]
    _need(invocation is original and deadline <= expires and time.monotonic() < expires)
    # Closed dispatch: names/reports supplied by a caller cannot register a
    # producer. Additional requirements need their own original native proof.
    _need(name == 'complete_native_business_restart')
    from .native_business_adapter import inspect_restart
    _need(inspect_restart(proof, invocation, deadline) == snapshot)
    return name, snapshot


def issuer_status():
    required = tuple(name for area in Area for name in requirement(area).observations)
    return dict(native_acceptance='NOT_ACCEPTED', activation_allowed=False, usable_product=False,
        reviewed_platform_policy=False,
        implemented_producers=['complete_native_business_restart'],
        missing_producers=[name for name in required if name != 'complete_native_business_restart'])


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
        name, current = _inspect(cap, invocation, deadline)
        _need(name not in names, 'DUPLICATE_NATIVE_OBSERVATION')
        names.add(name)
        _need(binding is None or binding == current, 'NATIVE_OBSERVATION_BINDING_CHANGED')
        binding = current
    missing = tuple(name for area in Area for name in requirement(area).observations if name not in names)
    if missing:
        raise AcceptanceRefused('NATIVE_ACCEPTANCE_EVIDENCE_INCOMPLETE', missing)
    policy = _REVIEWED_POLICY
    _need(type(policy) is _PlatformPolicy, 'REVIEWED_PLATFORM_ACCEPTANCE_POLICY_REQUIRED')
    _policy_binding(policy, invocation, binding)
    _deadline(deadline)
    cap = AcceptedInstallationCapability()
    _accepted[cap] = (invocation, observations, binding, policy, deadline)
    return cap


def _policy_binding(policy, invocation, binding):
    _need(policy is _REVIEWED_POLICY and type(policy) is _PlatformPolicy and binding is not None)
    _need(binding.runtime == tuple(sorted(dict(source_commit=policy.source_commit,
        manifest_sha256=policy.manifest_sha256).items())))
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
        name, current = _inspect(observation, invocation, deadline)
        _need(current == binding, 'NATIVE_ACCEPTANCE_BINDING_CHANGED')
        names.add(name)
    _need(set(requirement(area).observations) <= names)
    _deadline(deadline)
    return None
