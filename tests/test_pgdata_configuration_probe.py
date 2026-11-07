"""Source/profile and original cluster control-path contracts, NOT Windows AT.

Positive tests use controlled ports/context explicitly. They issue no real
source grant, identity, native fact or Windows configuration acceptance.
"""
import ast
import json
import os
from pathlib import Path
import time
from types import SimpleNamespace

import pytest

from scripts.windows_ci import native_business_window as window
from scripts.windows_portable import native_trial_authority as authority
from scripts.windows_portable import pgdata_probe_boundary as boundary
from scripts.windows_portable.native_cluster import NativeProtectedClusterProcesses
from scripts.windows_portable.native_instance_security import NativeFixedStoreSecurity
from scripts.windows_portable.fixed_directories import FixedDirectoryLease
from scripts.windows_portable.controller import DatabaseInputs,ControlFailure
from scripts.windows_portable.cluster_processes import ClusterStartFailure
from scripts.windows_portable.fixed_journal import encode,FixedFormat
from test_native_business_source_protocol import composition
from scripts.windows_portable.endpoint_plan import PlanMode


def record():
    return dict(repository='T1doo/ParkWeave',ref='refs/heads/dev/local-product-runtime-20261028',
        job='pgdata-probe',run_number=1,run_id=None,expires_utc=int(time.time())+7200,
        reviewed_parent='a'*40,workflow_sha256='b'*64,archive_sha256='c'*64,archive_bytes=100,
        manifest_sha256='d'*64,operations=sorted(window.PGDATA_OPERATIONS),work_seconds=360,cleanup_seconds=60)


@pytest.mark.parametrize('damage',[None,'operations','job','work','cleanup'])
def test_narrow_profile_is_exact_and_cannot_select_business_or_larger_budget(monkeypatch,damage):
    value=record()
    if damage=='operations':value['operations'].append('OWN_JOB_IMAGE_DEBUG_OBSERVATIONS')
    elif damage=='job':value['job']='native-business-trial'
    elif damage=='work':value['work_seconds']=900
    elif damage=='cleanup':value['cleanup_seconds']=61
    monkeypatch.setattr(window,'_read',lambda *args:json.dumps(value).encode())
    if damage:
        with pytest.raises(window.WindowRefused):window._record()
    else:
        parsed,_=window._record()
        assert window.workflow_for(parsed)==window.PGDATA_WORKFLOW and window.windows_minutes(parsed)==9


def test_unbound_real_composition_refuses_before_any_instance_operation(tmp_path,monkeypatch):
    first=composition(tmp_path,PlanMode.NEW)
    monkeypatch.setattr(first,'create',lambda *args,**kw:pytest.fail('native before source grant'))
    with pytest.raises(authority.TrialRefused):boundary.ConfigurationProbe(first,str(tmp_path/'probe'))
    assert not list(tmp_path.iterdir())


def test_original_native_cluster_stops_at_configuration_without_registration(monkeypatch):
    native=object.__new__(NativeFixedStoreSecurity)
    cluster=object.__new__(NativeProtectedClusterProcesses)
    inputs=DatabaseInputs('SYNTHETIC_PRIVATE','SYNTHETIC_PRIVATE','SYNTHETIC_PRIVATE','SYNTHETIC_PRIVATE')
    native.inputs=inputs;cluster.prerequisites=SimpleNamespace(security=native)
    cluster.mode=None;cluster.failed=False
    lease=SimpleNamespace(status=lambda:'CLUSTER',_verify=lambda:None)
    value=SimpleNamespace(window=SimpleNamespace(operations=window.PGDATA_OPERATIONS))
    invocation=SimpleNamespace(processes=SimpleNamespace(cluster=cluster))
    probe=object.__new__(boundary.ConfigurationProbe)
    probe.invocation=invocation;probe.value=value;probe.started=True;probe.reached=False
    probe.stop=boundary._ConfigurationBoundaryReached('CONTROLLED_PROTOCOL_STOP')
    monkeypatch.setattr(authority,'bound_state',lambda resource,**kw:value)
    monkeypatch.setattr(authority,'budget',lambda original,deadline=None,**kw:deadline)
    cluster._configuration=lambda *args:(inputs,'1')  # Controlled port, not a native proof.
    cluster.prerequisites.initialize_protected=lambda *args:pytest.fail('initdb after boundary')
    cluster.prerequisites.before_server=lambda *args:pytest.fail('server after boundary')
    boundary._probes[cluster]=probe
    with pytest.raises(ClusterStartFailure) as caught:
        cluster._run('NEW',lease,object(),lambda *args:pytest.fail('child registration after boundary'))
    assert caught.value.primary is probe.stop and caught.value.phase=='CONFIGURATION'
    assert probe.reached and probe.lease is lease and cluster not in boundary._probes


def test_probe_profile_without_original_registered_boundary_refuses_before_initdb(monkeypatch):
    native=object.__new__(NativeFixedStoreSecurity)
    cluster=object.__new__(NativeProtectedClusterProcesses);cluster.prerequisites=SimpleNamespace(security=native)
    monkeypatch.setattr(authority,'bound_state',lambda *args,**kw:SimpleNamespace(window=SimpleNamespace(operations=window.PGDATA_OPERATIONS)))
    with pytest.raises(authority.TrialRefused):boundary.stop_before_initdb(cluster,object(),object())


@pytest.mark.parametrize('resource_name',['PrivateProcessAdapter','_RestrictedPrimaryCandidate','_RestrictedInitdbBackend','NativeOwnedDatabaseEndpoint'])
def test_narrow_state_cannot_bind_process_token_or_endpoint_adapters(monkeypatch,resource_name):
    from scripts.windows_portable.processes import PrivateProcessAdapter
    from scripts.windows_portable.restricted_token_candidate import _RestrictedPrimaryCandidate
    from scripts.windows_portable.restricted_initdb_candidate import _RestrictedInitdbBackend
    from scripts.windows_portable.native_database_endpoint import NativeOwnedDatabaseEndpoint
    value=SimpleNamespace(window=SimpleNamespace(operations=window.PGDATA_OPERATIONS))
    monkeypatch.setattr(authority,'_lookup',lambda original:value)
    monkeypatch.setattr(authority,'_check',lambda *args,**kw:None)
    classes=locals()
    with pytest.raises(authority.TrialRefused):authority.inherit(object(),object.__new__(classes[resource_name]))


def test_probe_workflow_and_packaging_are_disabled_and_complete():
    from scripts.windows_portable.build import RUNTIME_SOURCES
    source=Path(window.PGDATA_WORKFLOW).read_text()
    assert source.count('false &&')==2 and 'timeout-minutes: 6' in source and 'timeout-minutes: 9' in source
    assert 'retention-days: 1' in source and 'contents: read' in source
    assert 'desktop-synthetic' not in source and 'trial-ui-driver.exe' not in source
    assert json.loads(Path(window.RECORD).read_text()) is None
    assert 'scripts/windows_portable/pgdata_probe_boundary.py' in RUNTIME_SOURCES
    scope=ast.parse(Path('scripts/windows_ci/native_business_scope.py').read_text())
    run=next(n for n in ast.walk(scope) if isinstance(n,ast.FunctionDef) and n.name=='run')
    guarded=next(n for n in run.body if isinstance(n,ast.If) and 'configuration_probe' in ast.unparse(n.test))
    assert isinstance(guarded.body[-1],ast.Return)


@pytest.mark.parametrize('fault',[None,'configuration','cleanup','poisoned'])
@pytest.mark.skipif(os.name != 'posix', reason='actual POSIX journal required')
def test_original_controller_and_real_posix_journal_stop_or_preserve_failure(tmp_path,monkeypatch,fault):
    from scripts.windows_portable.fixed_directories import FixedPrivateDirectories
    from scripts.windows_portable import native_trial_facts
    first=composition(tmp_path,PlanMode.NEW);native=first.security.security;cluster=first.processes.cluster
    root=str(tmp_path/'fresh-protocol-instance')
    value=SimpleNamespace(window=SimpleNamespace(operations=window.PGDATA_OPERATIONS),
        root=root,parent=tmp_path,compositions=(first,),generations=[],deadline=time.monotonic()+20,cleanup_end=time.monotonic()+25)
    # Controlled context/ports only; never insert into real authority registries.
    monkeypatch.setattr(authority,'bound_state',lambda *args,**kw:value)
    monkeypatch.setattr(authority,'attach_controller',lambda *args:None)
    monkeypatch.setattr(authority,'detach_controller',lambda *args:None)
    monkeypatch.setattr(native_trial_facts,'journal_write',lambda *args:None)
    first.controller.directories=FixedPrivateDirectories(str(tmp_path),format=FixedFormat.INSTANCE_V2)
    monkeypatch.setattr(first.security,'require_runtime_support',lambda *args:None)
    monkeypatch.setattr(first.security,'require_creation_support',lambda *args:None)
    monkeypatch.setattr(first.security,'bind_new_lease',lambda lease:None)
    monkeypatch.setattr(first.security,'create_credentials',lambda lease:object())
    def close(*args):
        if fault=='cleanup':raise OSError('CONTROLLED_CLEANUP_NOT_ACKNOWLEDGED')
    monkeypatch.setattr(first.security,'close_owned_files',close)
    inputs=DatabaseInputs('CONTROLLED','CONTROLLED','CONTROLLED','CONTROLLED')
    def configuration(lease,*args):
        if fault=='configuration':raise RuntimeError('CONTROLLED_CONFIGURATION_REFUSAL')
        if fault=='poisoned':lease.poisoned=True
        native.inputs=inputs;return inputs,'1'
    monkeypatch.setattr(cluster,'_configuration',configuration)
    monkeypatch.setattr(cluster.prerequisites,'initialize_protected',lambda *args:pytest.fail('initdb must not start'))
    monkeypatch.setattr(first.processes,'start_application',lambda *args:pytest.fail('application must not start'))
    probe=boundary.ConfigurationProbe(first,root)
    if fault:
        with pytest.raises(ControlFailure) as caught:probe.run()
        assert caught.value.phase=='CLUSTER'
        assert probe.reached is (fault!='configuration')
    else:
        result=probe.run()
        assert result['controller_outcome']=='UNKNOWN' and result['configuration_reached']
        assert result['initdb']==result['services']==result['debug']==result['desktop']=='NOT_STARTED'
        assert not result['usable_product'] and not result['normal_reopen_allowed']
    assert cluster not in boundary._probes
    with pytest.raises(authority.TrialRefused):probe.run()
