"""Pure native product factory. Invocation retains every original OS gate."""
from . import endpoint_plan as ep, fixed_journal as journal
from .controller import Controller
from .fixed_directories import FixedPrivateDirectories
from .native_instance_security import native_security_ports
from .native_cluster import NativeProtectedClusterProcesses
from .native_preparation_sessions import NativePreparationSessionProvider
from .local_preparation_identity import PreparationSecurity, PreparationDatabaseOperations, PreparationProfile, identity_names
from .local_preparation import LocalPreparationInvocation
from .local_preparation_transport import OwnedPreparationRequest
from .instance_processes import InstanceProcesses


def compose_native_local_preparation(*,base,mode,request,runtime,initdb_sha256,initdb_size,
                                     postgres_sha256,postgres_size,python_sha256,python_size,challenge,
                                     payload_source=None,enrollment=None,profile=PreparationProfile.MATERIAL):
    identity_names(profile)
    # Reopen discovers the mode from the original authenticated identity file.
    # No checkbox/default may choose incompatible entropy or reseed anything.
    if mode is ep.PlanMode.REOPEN:profile=PreparationProfile.MATERIAL
    security,prerequisites=native_security_ports(mode=mode,request=request,runtime=runtime,payload_source=payload_source)
    cluster=NativeProtectedClusterProcesses(prerequisites,initdb_sha256=initdb_sha256,
        initdb_size=initdb_size,postgres_sha256=postgres_sha256,postgres_size=postgres_size)
    provider=NativePreparationSessionProvider(enrollment,profile=profile)
    processes=InstanceProcesses(cluster,python_sha256=python_sha256,python_size=python_size,
        challenge=challenge,endpoint_source=security,session_provider=provider)
    protected=PreparationSecurity(security,provider)
    directories=FixedPrivateDirectories(base,format=journal.FixedFormat.INSTANCE_V2)
    controller=Controller(directories,protected,processes,database=PreparationDatabaseOperations(profile=profile))
    return LocalPreparationInvocation(controller,processes,protected,OwnedPreparationRequest())
