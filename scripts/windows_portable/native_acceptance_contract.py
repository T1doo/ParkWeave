"""Native evidence coverage, never a READY issuer or an execution permission.

The harness supplies observations only. A reviewed platform policy and original
runtime capabilities are still required; neither a JSON report nor passing
source/protocol tests can replace any of the three product refusal gates.
"""
from dataclasses import dataclass
from enum import Enum


class Area(Enum):
    OWNER='owner'
    FIXED_JOURNAL='fixed_journal'
    LOADER='loader'


@dataclass(frozen=True)
class Requirement:
    reason: str
    observations: tuple[str,...]


def requirement(area):
    if type(area) is not Area:raise ValueError('EXACT_ACCEPTANCE_AREA_REQUIRED')
    if area is Area.OWNER:
        return Requirement('OWNER_MUTATION_PAUSED',(
            'derived_token_owner_and_default_dacl','original_primary_token_unchanged',
            'protected_new_objects','dpapi_current_user_roundtrip','dpapi_wrong_entropy_refused',
            'dpapi_cross_os_identity_isolation','original_initdb_pipe_and_job'))
    if area is Area.FIXED_JOURNAL:
        return Requirement('WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED',(
            'original_fixed_slots_write_flush_readback','same_file_reopen',
            'exclusive_open_refused','torn_slot_refused_without_repair',
            'interrupted_process_recovery','target_filesystem_durability_scope'))
    return Requirement('NATIVE_RUNTIME_LOADING_NOT_ACCEPTED',(
        'signed_system_crt_files','minimum_toolset_compatibility','api_set_resolution',
        'original_job_and_backend_loaded_sources','complete_native_business_restart'))


def coverage(observed=()):
    """Pure diagnostic only; even complete supplied coverage grants nothing."""
    if type(observed) not in (tuple,frozenset) or any(type(x) is not str for x in observed):
        raise ValueError('OBSERVATION_NAMES_REQUIRED')
    values=frozenset(observed)
    return dict(activation_allowed=False,usable_product=False,native_acceptance='NOT_ACCEPTED',
        areas={area.value:dict(reason=requirement(area).reason,
            missing=[name for name in requirement(area).observations if name not in values],
            acceptance='NOT_ACCEPTED') for area in Area})
