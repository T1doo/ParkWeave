"""Typed native facts from concrete original producers, never report names.

Stable installation subject is separate from an observation's generation and
process/token/file. First-generation completed facts require the explicit
native stop/restart bridge before a second-generation issuer can consume them.
"""
from dataclasses import dataclass
import time
import weakref

from . import native_trial_authority as a
from .fixed_directories import FixedDirectoryLease, _exclusive_operation


@dataclass(frozen=True,repr=False)
class Subject:
    trial: tuple
    runtime: tuple
    files: tuple
    instance: str
    marker: tuple


class NativeFact:
    __slots__=('__weakref__',)
    def __reduce__(self):raise TypeError('native fact cannot be serialized')
    def __copy__(self):raise TypeError('native fact cannot be copied')
    def __deepcopy__(self,memo):raise TypeError('native fact cannot be copied')


_issued=weakref.WeakKeyDictionary()


@_exclusive_operation
def subject(lease,*,cleanup=False):
    from .fixed_windows_journal import FixedWindowsFilesystem,NativeFixedLeaseAPI
    value=a.bound_state(lease,cleanup=cleanup)
    a.need(value is not None and type(lease) is FixedDirectoryLease
        and type(lease.fs) is FixedWindowsFilesystem and type(lease.fs.api) is NativeFixedLeaseAPI)
    lease._verify();a.need(value.marker is not None)
    fs=lease.fs
    files=tuple((tuple(fs.identity(handle)),fs.api.descriptor(handle)) for handle in (fs.root,fs.lock,fs.journal))
    observed=Subject(value.key,tuple(sorted(dict(source_commit=value.manifest['source_commit'],
        manifest_sha256=value.window.manifest_sha256).items())),files,lease._verified_instance_uuid(),value.marker)
    if value.subject is None:value.subject=observed
    else:a.need(value.subject==observed)
    return observed


def _seal(lease,names,origin,observation,*,cleanup=False):
    # Private sink; only the concrete producer methods below choose names.
    value=a.bound_state(lease,cleanup=cleanup);a.need(value is not None)
    binding=subject(lease,cleanup=cleanup)
    cap=NativeFact()
    _issued[cap]=(value,binding,lease.record['generation'],tuple(names),origin,observation,value.deadline)
    value.facts.append(cap)
    return cap


def inspect(cap,lease,deadline):
    a.need(type(cap) is NativeFact and cap in _issued)
    value,binding,generation,names,origin,observation,expires=_issued[cap]
    current=a.bound_state(lease)
    a.need(current is value and deadline<=expires and time.monotonic()<expires
           and subject(lease)==binding and lease is value.generations[-1])
    if generation != lease.record['generation']:
        a.need(generation==1 and lease.record['generation']==2 and value.restart_ready
            and len(value.generations)==2 and not value.generations[0].active)
    return binding,names


def completed_token(lease,owner):
    value=a.bound_state(lease,cleanup=True)
    if value is None:return
    from .restricted_token_candidate import _RestrictedPrimaryCandidate,_native_registry
    _native_completed=_native_registry()[1]
    a.need(type(owner) is _RestrictedPrimaryCandidate and owner in _native_completed
        and owner._closed and not owner._failed)
    a.need(a.bound_state(owner,cleanup=True) is value and any(
        inv.security.security.lease is lease and owner in inv.security.security.resources for inv in value.compositions))
    evidence=_native_completed.pop(owner)
    a.need(evidence[2]==evidence[3])
    return _seal(lease,('derived_token_owner_and_default_dacl','original_primary_token_unchanged'),
        owner,evidence,cleanup=True)


def protected_objects(lease,security):
    value=a.bound_state(lease)
    if value is None:return
    from .native_instance_security import NativeFixedStoreSecurity
    from .native_protected_objects import require_original_creation
    a.need(type(security) is NativeFixedStoreSecurity and security.lease is lease
        and a.bound_state(security) is value and lease.record['generation']==1
        and security.layout.lease is lease and security.target.lease is lease
        and security.runtime_installation.lease is lease)
    fs=lease.fs
    controls=tuple(require_original_creation(fs.api,h) for h in (fs.root,fs.lock,fs.journal))
    layout=security.layout._verify();data=security.target._verify()
    security.runtime_installation._issued_binding(lease,security.runtime)
    return _seal(lease,('protected_new_objects',),security,(controls,layout,data))


def journal_write(lease):
    if a.bound_state(lease,cleanup=True) is None:return
    from .fixed_journal import FixedJournal,FixedFormat
    a.need(type(lease.fs.storage) is FixedJournal and lease._journal_format is FixedFormat.INSTANCE_V2)
    lease._verify();a.need(lease.fs.read()==lease.snapshot)
    return _seal(lease,('original_fixed_slots_write_flush_readback',),lease.fs,
        (lease.snapshot,lease.fs.journal_id),cleanup=True)


def journal_reopen(lease):
    value=a.bound_state(lease)
    if value is None:return
    a.need(value.restart_ready and len(value.generations)==2 and lease is value.generations[1]
        and not value.generations[0].active and value.generations[0].fs.handles==[])
    return _seal(lease,('same_file_reopen',),lease.fs,(value.subject,lease.record['generation']))


def signed_crt(lease,witness):
    if a.bound_state(lease) is None:return
    from .native_system_crt import NativeSystemCRT
    a.need(type(witness) is NativeSystemCRT and witness.lease is lease)
    witness._binding();witness._verify_files()
    return _seal(lease,('signed_system_crt_files',),witness,
        tuple(sorted((name,row[1],row[2],row[3],row[4]) for name,row in witness.rows.items())))


def minimum_runtime(lease,witness,deadline):
    if a.bound_state(lease) is None:return
    from .native_acceptance_issuer import _PlatformPolicy,_REVIEWED_POLICY,_deadline
    _deadline(deadline);deadline=a.budget(lease,deadline)
    policy=_REVIEWED_POLICY
    # No guessed floor from a linker's version or the installed version.
    # The source implementation is complete; reliable reviewed policy data
    # remain an explicit required input and grant no default compatibility.
    if type(policy) is not _PlatformPolicy or not policy.minimum_crt_versions or not policy.toolset_image_scope:return
    from .native_system_crt import NativeSystemCRT
    from .crt_pe import compatible
    from hashlib import sha256
    import sys
    version=sys.getwindowsversion()
    a.need(type(witness) is NativeSystemCRT and witness.lease is lease
        and (version.major,version.minor,version.build,version.product_type)==policy.nt_version)
    witness._binding();witness.deadline=deadline;witness._verify_files()
    scope,symbols,private=witness.installation.all_crt_imports_held(lease,witness.runtime,deadline)
    minimum=dict(policy.minimum_crt_versions)
    # Image content is already bound by the external candidate manifest and
    # original held installation. Embedding those hashes back into this source
    # would create a cycle through the desktop EXE's embedded bootstrap pins.
    a.need(tuple(name for name,digest in scope)==policy.toolset_image_scope
        and len(minimum)==len(policy.minimum_crt_versions)
        and set(minimum)==set(symbols))
    observed=[]
    for name in sorted(minimum):
        floor=minimum[name]
        a.need(type(floor) is tuple and len(floor)==4 and floor[0]==14
            and all(type(v) is int and 0<=v<65536 for v in floor))
        if name.startswith('SYSTEM32/'):
            dll=name[len('SYSTEM32/'):]
            a.need(dll in witness.rows)
            h,before,digest,actual,chain=witness.rows[dll]
            raw=witness._read(h,before[0].size)
        else:
            a.need(name in private)
            raw=private[name];digest=sha256(raw).hexdigest()
            actual=compatible(raw,symbols[name])
        a.need(compatible(raw,symbols[name])==actual and actual>=floor)
        observed.append((name,digest,actual,floor))
    witness._verify_files()
    return _seal(lease,('minimum_toolset_compatibility',),witness,(policy,scope,tuple(observed)))


def completed_initdb(lease,adapter,token,transmission):
    if a.bound_state(lease) is None:return
    from .native_protected_bootstrap import InitdbTransmission,_transmitted
    from .restricted_initdb_candidate import _RestrictedInitdbBackend
    from .windows_process_handles import consume_stopped_group
    a.need(type(transmission) is InitdbTransmission and transmission in _transmitted)
    original,backend,group,server,birth,pipe,sha=_transmitted[transmission]
    a.need(original is lease and type(backend) is _RestrictedInitdbBackend
        and adapter.backend is backend and adapter._group(token) is group
        and backend.server is server and server._handle==pipe
        and server._pending_write is None and server._pending_connection is None
        and group.returncode==0 and group.stopped and not adapter.unknown)
    identity=(birth[0],birth,sha)
    consume_stopped_group(adapter,token,identity)
    _transmitted.pop(transmission)
    return _seal(lease,('original_initdb_pipe_and_job',),transmission,(identity,pipe))


def completed_dpapi(lease,provider):
    if a.bound_state(lease) is None:return
    from .native_preparation_sessions import NativePreparationSessionProvider,PreparationFile,_roundtrip_evidence
    a.need(type(provider) is NativePreparationSessionProvider and provider in _roundtrip_evidence)
    original,kind,frame=_roundtrip_evidence[provider]
    a.need(original is lease and kind is PreparationFile.IDENTITIES and provider.lease is lease)
    _roundtrip_evidence.pop(provider)
    return _seal(lease,('dpapi_current_user_roundtrip','dpapi_wrong_entropy_refused'),provider,frame)


def cross_identity_dpapi(lease,provider,cipher,entropy,deadline):
    if a.bound_state(lease) is None:return
    from .native_preparation_sessions import NativePreparationSessionProvider,PreparationFile,_roundtrip_evidence
    from .native_dpapi_peer import LocalServiceDPAPIPeer
    from hashlib import sha256
    a.need(type(provider) is NativePreparationSessionProvider and provider.lease is lease
        and provider in _roundtrip_evidence)
    original,kind,frame=_roundtrip_evidence[provider]
    a.need(original is lease and kind is PreparationFile.IDENTITIES
        and sha256(cipher).hexdigest()==frame[1] and entropy.hex()==frame[2])
    peer=LocalServiceDPAPIPeer(lease,cipher,entropy,deadline)
    evidence=peer.run()
    a.need(peer.complete and not peer.failed and all(not row['owned'] or row['closed'] for row in peer.handles))
    return _seal(lease,('dpapi_cross_os_identity_isolation',),peer,(provider,frame,evidence))


def completed_slot_probes(lease,probe):
    if a.bound_state(lease) is None:return
    from .native_trial_slot_probes import NativeSlotProbes,_completed
    a.need(type(probe) is NativeSlotProbes and probe in _completed and not probe.failed and not probe.handles)
    original,observation=_completed[probe];a.need(original is lease)
    a.need(tuple(row[0] for row in observation[3])==('BEFORE_WRITE','PARTIAL_WRITE','BEFORE_FLUSH','AFTER_FLUSH'))
    fs=lease.fs;drive=fs.handles[0]
    guid=fs.api.final_path(drive)
    a.need(fs.api.filesystem(drive)=='NTFS' and fs.api.drive_type(guid)==3
        and fs.api.info(drive).volume==fs.root_id[0])
    import sys
    version=sys.getwindowsversion()
    scope=('PROCESS_INTERRUPTION_ONLY_NOT_POWER_LOSS',guid,fs.root_id[0],
        (version.major,version.minor,version.build,version.product_type),
        tuple((row[0],row[3]) for row in observation[3]))
    _completed.pop(probe)
    return _seal(lease,('exclusive_open_refused','torn_slot_refused_without_repair','interrupted_process_recovery',
        'target_filesystem_durability_scope'),probe,(observation,scope))
