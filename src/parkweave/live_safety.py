"""Pure opt-in preconditions. Explicit synthetic Mapping tests only this round.
Never reads env values, resolves credentials, authorizes a budget or opens a socket.
Actual shared deployment and approvals must be separately established by operator.
"""
from dataclasses import dataclass
from collections.abc import Mapping
from .intern_adapter import ModelBoundaryError

@dataclass(frozen=True)
class LiveSafety:
    enabled:bool=False
    budget_authorized:bool=False
    injection_authorized:bool=False
    rate_verified:bool=False
    shared_binding_verified:bool=False
    token_name_present:bool=False
    coordinator_names_present:bool=False
    def require(self):
        if not all(type(value) is bool and value for value in self.__dict__.values()):
            raise ModelBoundaryError('LIVE_SAFETY_BLOCKED')

def check_names(environment:Mapping,*,enabled=False,budget_authorized=False,injection_authorized=False,
                rate_verified=False,shared_binding_verified=False):
    # Do not use Mapping.get/__getitem__/dict(environment): values may be secrets.
    if not enabled:return LiveSafety()
    names=frozenset(environment.keys())
    return LiveSafety(enabled,budget_authorized,injection_authorized,rate_verified,shared_binding_verified,
        bool(names&{'PARKWEAVE_INTERN_API_TOKEN','INTERN_API_TOKEN'}),
        {'PARKWEAVE_QUOTA_DSN','PARKWEAVE_PROVIDER_ACCOUNT'}<=names)
