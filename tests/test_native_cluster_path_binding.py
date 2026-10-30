"""Controlled capability-call seams only; no native admission, PG or OS calls."""
from dataclasses import replace
from pathlib import PureWindowsPath
from types import SimpleNamespace
import time

import pytest

from scripts.windows_portable import cluster_processes as base
from scripts.windows_portable import native_instance_security as native
from scripts.windows_portable.controller import DatabaseInputs,CandidateRefused
from scripts.windows_portable.endpoint_plan import PlanMode
from scripts.windows_portable.instance_processes import InstanceProcesses
from scripts.windows_portable.native_cluster import NativeProtectedClusterProcesses
from scripts.windows_portable.pgdata_candidate import pg_command_path


@pytest.fixture
def bound(monkeypatch):
    # These two representations name the same held target in production. The
    # stand-ins here validate dispatch/identity checks, not a real Windows lease.
    guid=PureWindowsPath(r'\\?\Volume{11111111-2222-3333-4444-555555555555}\pw\one')
    command=pg_command_path(r'\\?\C:\pw\one\data\postgresql')[0]
    lease=SimpleNamespace(_verify=lambda:None,status=lambda:'CLUSTER')
    security=native.NativeFixedStoreSecurity(PlanMode.REOPEN,request=None,
        runtime=dict(source_commit='a'*40,manifest_sha256='b'*64))
    inputs=DatabaseInputs('host=127.0.0.1 port=55432 user=postgres dbname=postgres sslmode=disable',
        'host=127.0.0.1 port=55432 user=postgres dbname=parkweave sslmode=disable',
        'host=127.0.0.1 port=55432 user=parkweave_app dbname=parkweave sslmode=disable',command)
    security.inputs=inputs;security.lease=lease;security.target=object();security.plan=object()
    calls=[]
    def under(actual,operation,**kwargs):
        assert actual is lease
        return operation(time.monotonic()+5)
    def path(actual,target):
        assert actual is lease and target is security.target
        calls.append('HELD_PGDATA_PATH');return command
    def endpoints(actual,plan,*,mode):
        assert actual is lease and plan is security.plan and mode is PlanMode.REOPEN
        return dict(database_port=55432,api_port=58761)
    monkeypatch.setattr(security,'_run',under)
    monkeypatch.setattr(native,'_path_held',path)
    monkeypatch.setattr(native.ep,'_record_held',endpoints)
    monkeypatch.setattr(base,'private_root',lambda actual:guid)
    prerequisites=native.NativeClusterPrerequisites(security)
    monkeypatch.setattr(prerequisites,'configuration',lambda *args:inputs)
    cluster=NativeProtectedClusterProcesses(prerequisites,initdb_sha256='c'*64,initdb_size=1,
        postgres_sha256='d'*64,postgres_size=1)
    cluster.lease=lease
    return SimpleNamespace(guid=guid,command=command,lease=lease,security=security,inputs=inputs,
        cluster=cluster,prerequisites=prerequisites,calls=calls)


def test_native_configuration_uses_original_held_command_path_not_guid_string(bound):
    b=bound
    assert b.inputs.data_directory!=str(b.guid/'data'/'postgresql')
    inputs,port=b.cluster._configuration(b.lease,object(),time.monotonic()+5)
    assert inputs is b.inputs and port=='55432' and b.calls==['HELD_PGDATA_PATH']
    legacy=base.FixedClusterProcesses(b.prerequisites,initdb_sha256='c'*64,initdb_size=1,
        postgres_sha256='d'*64,postgres_size=1)
    legacy.lease=b.lease
    with pytest.raises(CandidateRefused):legacy._configuration(b.lease,object(),time.monotonic()+5)


def test_native_instance_checks_same_cluster_security_and_inputs(bound,monkeypatch):
    b=bound
    def opened(lease,credentials,register):
        assert lease is b.lease
        b.cluster.lease=lease;b.cluster.inputs=b.inputs;register(object());return b.inputs
    monkeypatch.setattr(b.cluster,'open_cluster',opened)
    instance=InstanceProcesses(b.cluster,python_sha256='e'*64,python_size=1,challenge='f'*32,endpoint_source=b.security)
    assert instance.open_cluster(b.lease,object(),lambda token:None) is b.inputs
    assert b.calls==['HELD_PGDATA_PATH']
    copied=replace(b.inputs)
    with pytest.raises(CandidateRefused):b.cluster.require_bound_inputs(b.lease,copied,b.security)
    with pytest.raises(CandidateRefused):b.cluster.require_bound_inputs(object(),b.inputs,b.security)
    other=native.NativeFixedStoreSecurity(PlanMode.REOPEN,request=None,runtime=b.security.runtime)
    with pytest.raises(CandidateRefused):b.cluster.require_bound_inputs(b.lease,b.inputs,other)
    assert b.calls==['HELD_PGDATA_PATH']


def test_security_rejects_cloned_or_wrong_path_inputs_without_normalizing(bound):
    b=bound
    with pytest.raises(CandidateRefused):b.security.require_inputs(b.lease,replace(b.inputs))
    assert b.calls==[]
    wrong=replace(b.inputs,data_directory=b.command.lower())
    b.security.inputs=wrong
    with pytest.raises(CandidateRefused):b.security.require_inputs(b.lease,wrong)
    assert b.calls==['HELD_PGDATA_PATH']
