"""Real POSIX lease IO plus controlled Windows metadata/type boundaries.

These tests check source algorithms, not native identity or acceptance.
No Windows constructor, token setter, DPAPI, database or trial is executed.
"""
from pathlib import Path
import subprocess
from types import ModuleType,SimpleNamespace
import time

import pytest

from scripts.windows_portable import native_runtime_staging as runtime
from scripts.windows_portable import native_secret_store_candidate as secret
from scripts.windows_portable import native_instance_security as security
from scripts.windows_portable import native_trial_authority as authority
from scripts.windows_portable import endpoint_plan as endpoint
from scripts.windows_portable.fixed_directories import FixedPrivateDirectories
from scripts.windows_portable.fixed_journal import FixedFormat
from scripts.windows_portable.fixed_secret_store import _under_lease,StoreRefused
from scripts.windows_portable.controller import CandidateRefused
from scripts.windows_portable.directories import LeaseRefused

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def installation(tmp_path,monkeypatch):
    lease=FixedPrivateDirectories(str(tmp_path),format=FixedFormat.INSTANCE_V2).claim_fresh(str(tmp_path/'owned-case'))
    counts=dict(read=0,sid=0,descriptor=0,path=0)
    original_read=lease.fs.read
    def read():counts['read']+=1;return original_read()
    monkeypatch.setattr(lease.fs,'read',read)
    class Metadata:
        def descriptor(self,h):counts['descriptor']+=1;return ('SYNTHETIC_SD',)
        def final_path(self,h):counts['path']+=1;return 'SYNTHETIC_PATH'
    api=Metadata();lease.fs.api=api
    # Explicit controlled platform seam: all fixed journal/UUID work below is
    # the original real POSIX implementation, never a fake native capability.
    monkeypatch.setattr(secret,'FixedWindowsFilesystem',type(lease.fs))
    monkeypatch.setattr(secret,'NativeFixedLeaseAPI',Metadata)
    probe=object.__new__(secret._NativeSecretFiles)
    probe.failed=False;probe.lease=lease;probe.api=api;probe.deadline=time.monotonic()+10
    probe.key=_under_lease(lease,lambda:endpoint._key_held(lease));probe.sid_bytes=b'SYNTHETIC_SID'
    def sid():counts['sid']+=1;return probe.sid_bytes
    probe.current_sid_bytes=sid
    value=object.__new__(runtime.NativeRuntimeInstallation)
    value.lease=lease;value.probe=probe;value.api=api;value.key=probe.key
    value.deadline=probe.deadline;value.failed=value.closed=False
    value.root_sd=('SYNTHETIC_SD',);value.root_path='SYNTHETIC_PATH'
    yield value,counts
    if lease.active:lease.release()


def test_same_gate_three_real_slot_reads_become_one_without_caching_next_gate(installation):
    value,counts=installation
    previous=ModuleType('original_frozen_runtime_source')
    previous.__package__='scripts.windows_portable'
    raw=subprocess.check_output(['git','show','442541c1f84bb9ac6a12772ada16a5aed2174198:scripts/windows_portable/native_runtime_staging.py'],cwd=ROOT)
    exec(compile(raw,'<original-reviewed-runtime>','exec'),previous.__dict__)
    def observed(call):
        for key in counts:counts[key]=0
        _under_lease(value.lease,lambda:(call(),call()))
        # The outer entry independently verifies once; each inner gate remains
        # a fresh actual slot verification and SID query, with no cross-gate cache.
        return dict(counts)
    before=observed(lambda:previous.NativeRuntimeInstallation._gate(value))
    after=observed(value._gate)
    assert before==dict(read=7,sid=2,descriptor=2,path=2)
    assert after==dict(read=3,sid=2,descriptor=2,path=2)


@pytest.mark.parametrize('changed',['key','sid','api','deadline','poisoned','unknown'])
def test_original_binding_identity_deadline_and_unknown_refusals_remain(installation,changed):
    value,counts=installation
    if changed=='key':value.key=('foreign',)
    elif changed=='sid':value.probe.current_sid_bytes=lambda:b'OTHER_SYNTHETIC_SID'
    elif changed=='api':value.probe.api=object()
    elif changed=='deadline':value.probe.deadline=time.monotonic()-1
    elif changed=='poisoned':value.lease.poisoned=True
    else:value.lease.mark_unknown('ACQUIRE')
    with pytest.raises((CandidateRefused,StoreRefused,LeaseRefused)):
        _under_lease(value.lease,value._gate)


@pytest.mark.parametrize('remaining',[50,850,None])
def test_bulk_constructor_gets_one_fixed_cap_clamped_to_original_total(tmp_path,monkeypatch,remaining):
    lease=FixedPrivateDirectories(str(tmp_path),format=FixedFormat.INSTANCE_V2).claim_fresh(str(tmp_path/'owned-case'))
    source=runtime.RuntimeSource(r'C:\synthetic',b'not-read-by-controlled-constructor')
    value=security.NativeFixedStoreSecurity(endpoint.PlanMode.NEW,request=endpoint.EndpointRequest(55431,58761),
        runtime=dict(source_commit='a'*40,manifest_sha256='b'*64),payload_source=source)
    value.lease=lease
    value._context=lambda original:None  # Type/OS boundary only; no native constructor follows.
    origin=time.monotonic();end=None if remaining is None else origin+remaining
    state=None if end is None else SimpleNamespace(deadline=end,cleanup_end=end+60)
    monkeypatch.setattr(authority,'bound_state',lambda resource,**kw:state if resource is value else None)
    observed=[]
    class StopBeforeNative(RuntimeError):pass
    def constructor(self,original,*args,deadline,**kwargs):
        observed.append(deadline);raise StopBeforeNative()
    monkeypatch.setattr(runtime.NativeRuntimeInstallation,'__init__',constructor)
    try:
        with pytest.raises(StopBeforeNative):value._runtime_files(lease,create=True)
        assert len(observed)==1 and value.failed
        expected=origin+600 if end is None else min(origin+600,end)
        assert expected<=observed[0]<=expected+.1
        assert state is None or state.deadline==end and state.cleanup_end==end+60
    finally:lease.release()
