"""One source-issued trial authority, strictly separate from native acceptance.

Bindings name original composition resources. No global enabled mode, ambient
thread override, report, path-only token or serialized grant can authorize work.
Production calls with unbound resources still enter their original refusal.
"""
from dataclasses import dataclass, field
import math
import os
import threading
import time
import weakref


class TrialRefused(RuntimeError): pass


def need(value):
    if not value: raise TrialRefused('SOURCE_BOUND_NATIVE_TRIAL_REFUSED')


class TrialCapability:
    __slots__ = ('__weakref__',)
    def __reduce__(self): raise TypeError('trial is not transferable')
    def __copy__(self): raise TypeError('trial is not copyable')
    def __deepcopy__(self, memo): raise TypeError('trial is not copyable')


@dataclass(eq=False, repr=False)
class _State:
    window: object
    key: tuple
    payload: object
    manifest_raw: bytes
    manifest: dict
    deadline: float
    cleanup_end: float
    pid: int
    thread: int
    context: tuple
    source_pins: object
    parent_binding: tuple | None = None
    root: str | None = None
    parent: object = None
    subject: object = None
    marker: object = None
    failed: bool = False
    closed: bool = False
    generations: list = field(default_factory=list)
    facts: list = field(default_factory=list)
    restart_ready: bool = False
    compositions: tuple = ()


_issued = weakref.WeakKeyDictionary()
_bound = weakref.WeakKeyDictionary()
_registrars=weakref.WeakKeyDictionary()
_api_filesystems=weakref.WeakKeyDictionary()


def _lookup(resource):
    try:return _bound.get(resource)
    except TypeError:return None  # Unbound legacy/fake ports never gain authority.


def activate(verified_source):
    from scripts.windows_ci.native_business_window import consume_verified
    window, key, payload, raw, manifest, deadline,context,pins = consume_verified(verified_source)
    state = _State(window, key, payload, raw, manifest, deadline, deadline+window.cleanup_seconds,
                   os.getpid(), threading.get_ident(),context,pins)
    cap = TrialCapability(); _issued[cap] = state
    return cap


def state(cap, *, cleanup=False):
    need(type(cap) is TrialCapability and cap in _issued)
    value = _issued[cap]; _check(value, cleanup=cleanup)
    return value


def _check(value, *, cleanup=False):
    from scripts.windows_ci.native_business_window import current_context
    need(type(value) is _State and value.pid == os.getpid() and value.thread == threading.get_ident()
         and not value.closed and (cleanup or not value.failed)
         and time.monotonic() < (value.cleanup_end if cleanup else value.deadline)
         and time.time() < value.window.expires_utc and current_context()==value.context)


def bind_compositions(cap,first,second,enrollment):
    value = state(cap)
    from .controller import Controller
    from .local_preparation import LocalPreparationInvocation
    from .local_preparation_identity import PreparationDatabaseOperations,PreparationSecurity
    from .fixed_directories import FixedPrivateDirectories
    from .fixed_journal import FixedFormat
    from .native_instance_security import NativeFixedStoreSecurity,NativeClusterPrerequisites
    from .native_cluster import NativeProtectedClusterProcesses
    from .native_preparation_sessions import NativePreparationSessionProvider
    from .native_web_login import NativeLoginEnrollment
    from .instance_processes import InstanceProcesses
    from .local_preparation_transport import OwnedPreparationRequest
    from .native_runtime_staging import RuntimeSource
    from .endpoint_plan import PlanMode
    need(not value.compositions and first is not second and type(enrollment) is NativeLoginEnrollment)
    resources=[enrollment]
    for invocation,mode in ((first,PlanMode.NEW),(second,PlanMode.REOPEN)):
        need(type(invocation) is LocalPreparationInvocation and type(invocation.transport) is OwnedPreparationRequest
             and type(invocation.controller) is Controller and type(invocation.security) is PreparationSecurity
             and type(invocation.processes) is InstanceProcesses)
        c,s,p=invocation.controller,invocation.security,invocation.processes
        native,provider=s.security,s.provider
        need(c.security is s and c.processes is p and type(c.database) is PreparationDatabaseOperations
             and type(c.directories) is FixedPrivateDirectories and c.directories.base==str(value.parent)
             and c.directories.journal_format is FixedFormat.INSTANCE_V2
             and type(native) is NativeFixedStoreSecurity and native.mode is mode
             and native.runtime==dict(source_commit=value.manifest['source_commit'],manifest_sha256=value.window.manifest_sha256)
             and type(native.payload_source) is RuntimeSource and native.payload_source.root==str(value.payload)
             and native.payload_source.manifest==value.manifest_raw and native.lease is None and native.processes is None
             and type(p.cluster) is NativeProtectedClusterProcesses and type(p.cluster.prerequisites) is NativeClusterPrerequisites
             and p.cluster.prerequisites.security is native and p.endpoint_source is native
             and type(provider) is NativePreparationSessionProvider and p.session_provider is provider
             and provider.enrollment is (enrollment if mode is PlanMode.NEW else None)
             and p.lease is None and p.mode is None)
        for command,path in ((p.python,'runtime/python/python.exe'),(p.cluster.initdb,'runtime/postgresql/bin/initdb.exe'),
                             (p.cluster.postgres,'runtime/postgresql/bin/postgres.exe')):
            pin=value.manifest['files'][path]
            need(command.relative_executable==path and command.sha256==pin['sha256'] and command.size==pin['bytes'])
        resources.extend((c,c.database,c.directories,native,provider,p))
    need(len({id(r) for r in resources})==len(resources) and all(r not in _bound for r in resources))
    value.compositions=(first,second)
    for resource in resources:_bound[resource]=value


def inherit(parent, resource):
    value = _lookup(parent)
    if value is None: return
    _check(value)
    need(resource not in _bound)
    from .fixed_windows_journal import FixedWindowsFilesystem
    from .fixed_windows_journal import NativeFixedLeaseAPI
    from .fixed_directories import FixedDirectoryLease
    from .restricted_initdb_candidate import _RestrictedInitdbBackend
    from .processes import PrivateProcessAdapter
    from .native_database_endpoint import NativeOwnedDatabaseEndpoint
    from .restricted_token_candidate import _RestrictedPrimaryCandidate
    need(type(resource) in (FixedWindowsFilesystem,FixedDirectoryLease,_RestrictedInitdbBackend,
         PrivateProcessAdapter,NativeOwnedDatabaseEndpoint,_RestrictedPrimaryCandidate,NativeFixedLeaseAPI))
    if type(resource) is FixedWindowsFilesystem:
        from .fixed_directories import FixedPrivateDirectories
        need(type(parent) is FixedPrivateDirectories and resource.base==parent.base==str(value.parent)
             and resource.journal_format is parent.journal_format)
    elif type(resource) is FixedDirectoryLease:
        need(type(parent) is FixedWindowsFilesystem and resource.fs is parent and value.marker is not None)
    elif type(resource) is NativeFixedLeaseAPI:
        need(type(parent) is FixedWindowsFilesystem and parent.api is resource
            and type(parent._trial_fresh) is bool)
        _api_filesystems[resource]=(parent,parent._trial_fresh)
    elif type(resource) is PrivateProcessAdapter:
        need(type(parent) is FixedDirectoryLease and resource.lease is parent
             and any(inv.security.security.lease is parent for inv in value.compositions))
        from .processes import Command
        need(set(resource.commands) in ({'initdb'},{'postgres'},{'api','worker'},{'slot_probe'}))
        for name,command in resource.commands.items():
            need(type(command) is Command)
            pin=value.manifest['files'][command.relative_executable]
            need(command.sha256==pin['sha256'] and command.size==pin['bytes'])
            if name=='initdb':need(type(resource.backend) is _RestrictedInitdbBackend
                and _lookup(resource.backend) is value and command is resource.backend.frozen.command)
            elif name=='slot_probe':
                from .native_trial_interruptions import NativeInterruptionBackend,_issued as backends
                need(type(resource.backend) is NativeInterruptionBackend and resource.backend in backends
                    and resource.backend.lease is parent and command is resource.backend.command)
            elif name=='postgres':need(command.relative_executable=='runtime/postgresql/bin/postgres.exe'
                and command.arguments[:4]==('-D',next(inv.security.security.inputs.data_directory for inv in value.compositions
                    if inv.security.security.lease is parent),'-h','127.0.0.1'))
            else:need(command.relative_executable=='runtime/python/python.exe' and command.arguments[:3]==('-I','-B','-m')
                and command.arguments[3] in ('uvicorn','parkweave.worker'))
    elif type(resource) is _RestrictedInitdbBackend:
        need(resource.lease is parent.lease and resource.owner in parent.resources and resource.server in parent.resources)
    elif type(resource) is _RestrictedPrimaryCandidate:
        need(resource in parent.resources and parent.lease is not None)
    elif type(resource) is NativeOwnedDatabaseEndpoint:
        need(resource.adapter.lease is parent.lease and parent.processes.cluster._adapters.get(id(resource.token)) is resource.adapter)
    _bound[resource] = value


def bound_state(resource, *, cleanup=False):
    value = _lookup(resource)
    if value is not None: _check(value, cleanup=cleanup)
    return value


def budget(resource, deadline=None, *, cleanup=False):
    value = bound_state(resource, cleanup=cleanup)
    if value is None: return deadline
    end = value.cleanup_end if cleanup else value.deadline
    if deadline is not None:
        need(type(deadline) in (int,float) and math.isfinite(deadline))
        end = min(end, deadline)
    need(time.monotonic() < end)
    return end


def fail_resource(resource):
    value=_lookup(resource)
    if value is not None:value.failed=True


def require_owner(resource):
    value = bound_state(resource)
    if value is None:
        from scripts.windows.lifecycle import require_setup_readiness
        return require_setup_readiness()
    need(value.root is not None and value.parent is not None)


def require_creation_target(api,parent,name,*,directory):
    require_owner(api)
    value=bound_state(api)
    if value is None:return  # Independently accepted production OWNER only.
    import re
    fs,fresh=_api_filesystems[api]
    need(fresh and value.parent_binding is not None)
    info=api.info(parent);identity=(info.volume,info.identity);descriptor=api.descriptor(parent)
    if directory:
        need((identity,descriptor,api.final_path(parent))==value.parent_binding
            and name==value.root.rsplit('\\',1)[-1])
        return
    root=getattr(fs,'root',None)
    need(root is not None)
    root_info=api.info(root)
    if identity==(root_info.volume,root_info.identity):
        from .directories import LOCK
        from .fixed_directories import FIXED_JOURNAL
        from .native_trial_domain import MARKER
        need(name in (LOCK,FIXED_JOURNAL,MARKER));return
    need(len(value.generations)==1 and value.generations[0].fs is fs)
    from .native_layout_candidate import _leaf_held
    original=next(inv.security.security for inv in value.compositions if inv.security.security.lease is value.generations[0])
    row=_leaf_held(value.generations[0],original.layout,'tmp')
    need(parent==row[1] and identity==row[2] and descriptor==row[3]
        and re.fullmatch(r'[.]pw-native-(?:probe[.](?:lock|slots|torn)|interrupt-(?:before_write|partial_write|before_flush|after_flush)[.]slots)',name))


def require_fixed(filesystem):
    value = bound_state(filesystem)
    if value is None:
        from .fixed_windows_journal import require_fixed_native_acceptance
        return require_fixed_native_acceptance()
    from .fixed_journal import FixedFormat
    need(str(filesystem.base) == str(value.parent) and filesystem.journal_format is FixedFormat.INSTANCE_V2)


def allow_loader(prerequisite, lease, deadline):
    value = bound_state(lease)
    if value is None: return False
    budget(lease, deadline)
    need(prerequisite.lease is lease and prerequisite.source_commit == value.manifest['source_commit']
         and prerequisite.manifest_sha256 == value.window.manifest_sha256)
    prerequisite.native_installation._issued_binding(lease,
        dict(source_commit=prerequisite.source_commit,manifest_sha256=prerequisite.manifest_sha256))
    return True  # Explicit trial operation permission, NEVER loader acceptance.


def fail(cap):
    value = _issued.get(cap)
    need(value is not None and value.pid == os.getpid() and value.thread == threading.get_ident())
    value.failed = True


def finish(cap):
    value = state(cap, cleanup=True)
    value.closed = True
    _issued.pop(cap, None)


def attach_controller(controller,lease,register):
    value=bound_state(controller)
    if value is None:return
    need(_lookup(lease) is value and controller not in _registrars
         and any(inv.controller is controller for inv in value.compositions))
    _registrars[controller]=(lease,register)


def detach_controller(controller):_registrars.pop(controller,None)


def register_auxiliary(processes,owner,token):
    value=bound_state(processes);need(value is not None)
    from .native_trial_interruptions import NativeInterruptionBackend,_issued as backends
    from .processes import PrivateProcessAdapter
    need(type(owner) is PrivateProcessAdapter and type(owner.backend) is NativeInterruptionBackend
        and owner.backend in backends and _lookup(owner) is value and owner._group(token).resources.get('job'))
    invocation=next((inv for inv in value.compositions if inv.processes is processes),None)
    need(invocation is not None and invocation.controller in _registrars)
    lease,register=_registrars[invocation.controller]
    need(owner.lease is lease and processes.lease is lease)
    processes._register(owner,register)(token)
