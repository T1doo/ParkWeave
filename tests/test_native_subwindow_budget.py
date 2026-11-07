"""Deadline composition with real POSIX leases and controlled native seams.
No Windows constructor, signature verification, trial or acceptance is run.
"""
import math
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts.windows_portable import native_instance_security as security,native_runtime_staging as staging
from scripts.windows_portable import native_system_crt as crt,native_trial_authority as authority
from scripts.windows_portable.fixed_directories import FixedPrivateDirectories
from scripts.windows_portable.fixed_journal import FixedFormat
from scripts.windows_portable.native_acceptance_issuer import AcceptanceRefused


class BeforeNativeIO(RuntimeError):pass


@pytest.mark.parametrize('boundary',['exact','above','expired'])
def test_absolute_30_second_bound_is_stable_when_subtraction_rounds_up(monkeypatch,boundary):
    from scripts.windows_portable import native_acceptance_issuer as issuer,native_database_endpoint as endpoint
    from scripts.windows_portable.controller import CandidateRefused

    now=100.002
    upper=now+30
    assert upper-now>30
    deadline={'exact':upper,'above':math.nextafter(upper,math.inf),'expired':now}[boundary]
    clock=SimpleNamespace(monotonic=lambda:now)
    for module in (security,issuer,endpoint):monkeypatch.setattr(module,'time',clock)
    monkeypatch.setattr(security,'_under_lease',lambda lease,operation:operation())
    owner=object.__new__(security.NativeFixedStoreSecurity)
    owner.store=owner.target=owner.layout=None
    owner.failed=False
    owner._context=lambda lease:None
    if boundary=='exact':
        assert owner._run(object(),lambda end:end,deadline=deadline)==deadline
        issuer._deadline(deadline)
        assert endpoint.remaining(deadline)==30
    else:
        with pytest.raises(CandidateRefused):owner._run(object(),lambda end:end,deadline=deadline)
        with pytest.raises(AcceptanceRefused):issuer._deadline(deadline)
        with pytest.raises(CandidateRefused):endpoint.remaining(deadline)


@pytest.mark.parametrize('reused',[False,True])
def test_crt_factory_clamps_new_and_reused_witness_to_original_lease_end(tmp_path,monkeypatch,reused):
    lease=FixedPrivateDirectories(str(tmp_path),format=FixedFormat.INSTANCE_V2).claim_fresh(str(tmp_path/'owned'))
    owner=object.__new__(security.NativeFixedStoreSecurity)
    owner.lease=lease;owner.system_crt=None;owner.resources=[];owner.runtime={};owner.runtime_installation=object()
    value=security.NativeClusterPrerequisites(owner);now=time.monotonic();end=now+2
    state=SimpleNamespace(deadline=end,cleanup_end=end+60);observed=[]
    if reused:
        witness=object.__new__(crt.NativeSystemCRT)
        witness._binding=lambda:observed.append(('binding',witness.deadline))
        witness._verify_files=lambda:observed.append(('read',witness.deadline))
        owner.system_crt=witness
    else:
        def constructor(self,original,installation,runtime,deadline):
            assert original is lease;observed.append(('constructor',deadline));raise BeforeNativeIO()
        monkeypatch.setattr(crt.NativeSystemCRT,'__init__',constructor)
    try:
        with patch.object(authority,'bound_state',lambda resource,**kw:state if resource is lease else None):
            if reused:assert value.require_system_crt(lease,now+30) is witness
            else:
                with pytest.raises(BeforeNativeIO):value.require_system_crt(lease,now+30)
            assert observed and all(deadline==end for _,deadline in observed)
            with pytest.raises(AcceptanceRefused):value.require_system_crt(lease,now+40)
            assert state.deadline==end and state.cleanup_end==end+60
    finally:lease.release()


@pytest.mark.parametrize('requirements_only',[False,True])
def test_static_snapshot_also_clamps_direct_callers_before_any_image_read(tmp_path,requirements_only):
    lease=FixedPrivateDirectories(str(tmp_path),format=FixedFormat.INSTANCE_V2).claim_fresh(str(tmp_path/'owned'))
    if not requirements_only:
        lease.checkpoint('CREDENTIALS',False,'STARTING');lease.checkpoint('CLUSTER',False,'STARTING')
    installation=object.__new__(staging.NativeRuntimeInstallation)
    installation.failed=False;installation.probe=SimpleNamespace(deadline=None)
    installation._issued_binding=lambda original,runtime:None  # Controlled type/registry seam only.
    seen=[]
    def verify():
        seen.append((installation.deadline,installation.probe.deadline));raise BeforeNativeIO()
    installation.verify=verify
    now=time.monotonic();end=now+2;state=SimpleNamespace(deadline=end,cleanup_end=end+60)
    try:
        with patch.object(authority,'bound_state',lambda resource,**kw:state if resource is lease else None):
            with pytest.raises(BeforeNativeIO):
                installation._inspect_pg_snapshot(lease,{},now+30,requirements_only=requirements_only)
            assert seen==[(end,end)] and installation.failed
            assert state.deadline==end and state.cleanup_end==end+60
    finally:lease.release()


def test_crt_time_gate_cannot_revive_source_by_assigning_a_fresh_local_deadline(monkeypatch):
    clock=[1000.];fake=SimpleNamespace(monotonic=lambda:clock[0])
    monkeypatch.setattr(crt,'time',fake);monkeypatch.setattr(authority,'time',fake)
    witness=object.__new__(crt.NativeSystemCRT)
    witness.failed=witness.closed=False;witness.lease=object();witness.deadline=1030.
    state=SimpleNamespace(deadline=1002.,cleanup_end=1062.)
    with patch.object(authority,'bound_state',lambda resource,**kw:state if resource is witness.lease else None):
        witness._time();assert witness.deadline==1002.
        clock[0]=1003.;witness.deadline=1033.  # Caller attempts a fresh 30s subwindow.
        with pytest.raises(authority.TrialRefused):witness._time()
        assert state.deadline==1002. and state.cleanup_end==1062.
