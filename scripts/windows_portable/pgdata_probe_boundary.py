"""Source-bound configuration-only stop. Never product/native acceptance.

The original factory and Controller own setup and cleanup. The native cluster
must cross this boundary after configuration and before initdb or any child.
Only the narrow source window can arm it; no user argument or dictionary can.
"""
import weakref

from . import native_trial_authority as authority
from .controller import ControlFailure,DatabaseInputs
from .cluster_processes import ClusterStartFailure

_probes=weakref.WeakKeyDictionary()


class _ConfigurationBoundaryReached(RuntimeError):pass


def stop_before_initdb(cluster,lease,inputs):
    value=authority.bound_state(cluster.prerequisites.security)
    if not authority.configuration_probe(value):return
    probe=_probes.pop(cluster,None)
    authority.need(type(probe) is ConfigurationProbe and probe.started and not probe.reached
        and probe.value is value and authority.bound_state(lease) is value
        and cluster is probe.invocation.processes.cluster and cluster.lease is lease
        and type(inputs) is DatabaseInputs and cluster.inputs is inputs
        and inputs is cluster.prerequisites.security.inputs)
    probe.reached=True;probe.lease=lease
    raise probe.stop


class ConfigurationProbe:
    def __init__(self,invocation,root):
        from .native_business_adapter import _composition
        from .endpoint_plan import PlanMode
        _composition(invocation,PlanMode.NEW)  # Original exact native composition.
        value=authority.bound_state(invocation.controller)
        authority.need(authority.configuration_probe(value) and value.root==root
            and value.compositions[0] is invocation)
        self.invocation,self.root,self.value=invocation,root,value
        self.started=self.reached=False;self.lease=None
        self.stop=_ConfigurationBoundaryReached('PGDATA_CONFIGURATION_BOUNDARY_REACHED')

    def __reduce__(self):raise TypeError('configuration probe cannot be transferred')
    def __copy__(self):raise TypeError('configuration probe cannot be copied')
    def __deepcopy__(self,memo):raise TypeError('configuration probe cannot be copied')

    def public(self):
        return dict(scope='PGDATA_CONFIGURATION_ONLY_NOT_BUSINESS',
            configuration_reached=vars(self).get('reached') is True,
            boundary='BEFORE_INITDB',outcome='UNKNOWN',usable_product=False,native_acceptance='NOT_ACCEPTED')

    def run(self):
        from .fixed_directories import FixedDirectoryLease
        from .fixed_journal import decode,FixedFormat
        authority.need(not self.started and authority.bound_state(self.invocation.controller) is self.value)
        self.started=True;cluster=self.invocation.processes.cluster
        authority.need(cluster not in _probes and cluster.mode is None and not cluster.failed)
        _probes[cluster]=self
        def no_application(*args):raise authority.TrialRefused('PGDATA_PROBE_CANNOT_ENTER_APPLICATION')
        try:
            try:self.invocation.create(self.root,no_application)
            except ControlFailure as error:
                # This exact intentional stop is the only completed observation.
                # Any other cause or cleanup fault remains the original failure.
                if not (self.reached and error.phase=='CLUSTER' and error.operation=='CREATE'
                    and not error.cleanup_errors and len(error.causes)==2
                    and error.causes[0] is self.stop and type(error.causes[1]) is ClusterStartFailure
                    and error.causes[1].phase=='CONFIGURATION' and error.causes[1].primary is self.stop):
                    raise
                lease=self.lease
                consistent=False
                try:
                    if (type(lease) is FixedDirectoryLease and not lease.active and not lease.poisoned
                        and authority.bound_state(lease,cleanup=True) is self.value):
                        # Prior acknowledged snapshot only, never post-close disk IO.
                        record=decode(lease.snapshot[0],format=FixedFormat.INSTANCE_V2)
                        consistent=(record==lease.record and record['phase']=='UNKNOWN'
                            and record['handoff']=='RELEASE_PENDING' and record['initialized'] is False)
                except BaseException:pass
                if not consistent:raise  # Preserve the original Controller failure.
                return dict(scope='PGDATA_CONFIGURATION_ONLY_NOT_BUSINESS',
                    result='CONFIGURATION_OBSERVED_AND_INTENTIONALLY_STOPPED',
                    controller_outcome='UNKNOWN',last_acknowledged_phase='UNKNOWN',
                    last_acknowledged_handoff='RELEASE_PENDING',persistent_journal_reobserved=False,
                    normal_reopen_allowed=False,configuration_reached=True,
                    initdb='NOT_STARTED',services='NOT_STARTED',debug='NOT_STARTED',desktop='NOT_STARTED',
                    activation_allowed=False,usable_product=False,native_acceptance='NOT_ACCEPTED')
            raise authority.TrialRefused('PGDATA_PROBE_BOUNDARY_NOT_OBSERVED')
        finally:
            if _probes.get(cluster) is self:_probes.pop(cluster,None)
