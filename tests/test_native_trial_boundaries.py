"""Source/controlled-call boundaries only; never Windows execution evidence."""
import ctypes as C
import os
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from parkweave.windows_handles import PTR,UnicodeString,ObjectAttributes,IOStatus,nt_status,_NT_CREATE_PENDING
from scripts.windows import lifecycle
from scripts.windows_ci import native_business_window as window,native_business_entry as entry
from scripts.windows_ci.native_business_scope import NativeBusinessScope,_retained
from scripts.windows_portable import native_trial_authority as a,native_trial_domain as domain
from scripts.windows_portable import native_protected_objects as objects
from scripts.windows_portable.fixed_windows_journal import NativeFixedLeaseAPI
from scripts.windows_portable.windows_process_handles import WindowsJobProcess
from scripts.windows_portable.windows_directory_handles import WindowsFilesystem


def test_null_source_record_refuses_before_native_candidate_rng_or_execution(monkeypatch,tmp_path,capsys):
    calls=[]
    monkeypatch.setattr(C,'WinDLL',lambda *args,**kwargs:calls.append('dll') or pytest.fail('native call'),raising=False)
    monkeypatch.setattr(window,'_verify_inputs',lambda *args:pytest.fail('candidate I/O before source approval'))
    with pytest.raises(window.WindowRefused):window.load_source_window()
    assert entry.main(['--execute','--payload',str(tmp_path/'absent'),'--candidate-zip',str(tmp_path/'absent.zip')])==2
    assert 'WindowRefused' in capsys.readouterr().out and not calls
    with pytest.raises(window.WindowRefused):window.consume_verified(window.VerifiedSource())
    assert not calls and list(tmp_path.iterdir())==[]


def controlled_state(*,work=10,cleanup=20):
    now=time.monotonic()
    return a._State(SimpleNamespace(expires_utc=time.time()+60),('PUBLIC_CONTROLLED_TEST',),Path('/unused'),b'',{},
        now+work,now+cleanup,os.getpid(),threading.get_ident(),window.current_context(),None)


def test_work_cleanup_and_frozen_context_cannot_be_extended(monkeypatch):
    class Resource:pass
    resource=Resource();value=controlled_state(work=-1,cleanup=10);a._bound[resource]=value
    try:
        with pytest.raises(a.TrialRefused):a.budget(resource,time.monotonic()+900)
        assert a.budget(resource,time.monotonic()+900,cleanup=True)==value.cleanup_end
        monkeypatch.setenv('RUNNER_TEMP','CHANGED_CONTROLLED_TEST_PATH')
        with pytest.raises(a.TrialRefused):a.budget(resource,cleanup=True)
    finally:a._bound.pop(resource,None)


def test_expired_cleanup_retains_scope_before_fallible_validation():
    value=controlled_state(work=-20,cleanup=-1)
    cap=a.TrialCapability();a._issued[cap]=value
    scope=object.__new__(NativeBusinessScope);scope.cap=cap;scope.closed=False
    sentinel=object();scope.storage=sentinel;scope.adapter=object()
    try:
        with pytest.raises(a.TrialRefused):scope.close()
        assert scope in _retained and scope.storage is sentinel and value.failed and scope.closed
    finally:
        a._issued.pop(cap,None)
        if scope in _retained:_retained.remove(scope)


def fake_api(status):
    readonly=SimpleNamespace();calls=[]
    def ntcreate(*args):
        calls.append(status)
        # Original output storage is strongly registered BEFORE the syscall.
        assert any(record[0] is api for record in objects._inflight.values())
        if status=='EXCEPTION':raise KeyboardInterrupt('controlled syscall outcome unknown')
        if status==0:
            C.cast(args[0],C.POINTER(PTR)).contents.value=17
            C.cast(args[3],C.POINTER(IOStatus)).contents.Information=1
        return status
    api=SimpleNamespace(readonly=readonly,ntcreate=ntcreate,close=lambda h:calls.append(('close',h)))
    return api,calls


@pytest.mark.parametrize('status',[0xc0000034,nt_status(0xc0000034)])
def test_exact_signed_name_absence_is_optional_marker_absence(status):
    api,calls=fake_api(status)
    assert domain._open_optional(api,1) is None and calls==[status]


def test_access_denied_is_not_absence_and_existing_marker_always_refuses_formal():
    api,calls=fake_api(0xc0000022)
    with pytest.raises(domain.LeaseRefused):domain._open_optional(api,1)
    assert calls==[0xc0000022]
    api,calls=fake_api(0)
    class Filesystem:
        def __init__(self):self.api=api;self.root=1;self.handles=[]
        def hold(self,h):self.handles.append(h);return h
    fs=Filesystem()
    with pytest.raises(domain.LeaseRefused,match='TRIAL_ONLY_DOMAIN_REFUSED'):
        domain.require_domain(fs,fresh=False)
    assert fs.handles==[17] and calls==[0]


def test_exceptional_ntcreate_retains_original_outputs_and_forbids_retry():
    api,calls=fake_api('EXCEPTION')
    prior=set(objects._inflight);pending=set(_NT_CREATE_PENDING)
    try:
        with pytest.raises(domain.LeaseRefused,match='OUTCOME_UNKNOWN'):domain._open_optional(api,1)
        assert api.readonly._nt_create_pending and len(calls)==1
        with pytest.raises(Exception):domain._open_optional(api,1)
        assert len(calls)==1 and not any(isinstance(x,tuple) for x in calls)
    finally:
        # Test-only outputs; no kernel handles were created in this protocol.
        for key in set(objects._inflight)-prior:objects._inflight.pop(key)
        for key in set(_NT_CREATE_PENDING)-pending:_NT_CREATE_PENDING.pop(key)


def test_direct_protected_creation_has_original_owner_gate_before_query():
    api=object.__new__(NativeFixedLeaseAPI)
    api.info=lambda h:pytest.fail('native metadata query before original gate')
    with pytest.raises(lifecycle.BoundaryError) as caught:
        objects.create(api,1,'unused',directory=True)
    assert caught.value.parkweave_lifecycle_reason=='OWNER_MUTATION_PAUSED'


def test_job_close_unknown_retains_original_handle_and_never_retries():
    calls=[]
    def close(h):
        calls.append(h)
        if h==11:raise OSError('controlled unknown close')
    backend=object.__new__(WindowsJobProcess);backend.original=SimpleNamespace(close=close)
    group=SimpleNamespace(resources=dict(thread=11,process=12,job=13))
    with pytest.raises(BaseExceptionGroup):backend.close_observed(group)
    records=group.resources['native_close_records']
    assert next(row for row in records if row['value']==11)==dict(name='thread',value=11,attempted=True,closed=False,kind='HANDLE')
    assert calls==[11,12,13]
    with pytest.raises(Exception):backend.close_observed(group)
    assert calls==[11,12,13]


def test_filesystem_close_unknown_retains_original_handle_and_never_retries():
    calls=[]
    def close(h):
        calls.append(h)
        if h==1:raise OSError('controlled unknown close')
    fs=WindowsFilesystem('C:\\unused',api=SimpleNamespace(close=close));fs.handles=[1,2,3];fs.lock=2
    with pytest.raises(BaseExceptionGroup):fs.close()
    assert calls==[3,1,2] and not next(row for row in fs._close_records if row['handle']==1)['closed']
    with pytest.raises(Exception):fs.close()
    assert calls==[3,1,2]


def test_filesystem_cleanup_deadline_stops_before_next_close():
    calls=[];value=controlled_state()
    def close(h):calls.append(h);value.cleanup_end=time.monotonic()-1
    fs=WindowsFilesystem('C:\\unused',api=SimpleNamespace(close=close));fs.handles=[1,2,3];fs.lock=2
    a._bound[fs]=value
    try:
        with pytest.raises(BaseExceptionGroup):fs.close()
        assert calls==[3] and fs.handles==[1,2]
    finally:a._bound.pop(fs,None)


def test_completed_token_cannot_be_relabelled_as_another_trial():
    from scripts.windows_portable.native_trial_facts import completed_token
    from scripts.windows_portable.restricted_token_candidate import _RestrictedPrimaryCandidate,_native_registry
    class Lease:pass
    lease=Lease();owner=object.__new__(_RestrictedPrimaryCandidate);owner._closed=True;owner._failed=False
    first,second=controlled_state(),controlled_state()
    a._bound[lease]=first;a._bound[owner]=second
    evidence=('PUBLIC_CONTROLLED_COMPLETION',);_native_registry()[1][owner]=evidence
    try:
        with pytest.raises(a.TrialRefused):completed_token(lease,owner)
        assert _native_registry()[1][owner] is evidence and not first.facts
    finally:
        a._bound.pop(lease,None);a._bound.pop(owner,None);_native_registry()[1].pop(owner,None)


def test_unset_minimum_runtime_policy_never_guesses_a_floor_or_reads_native():
    from scripts.windows_portable.native_trial_facts import minimum_runtime
    from scripts.windows_portable.native_acceptance_issuer import _REVIEWED_POLICY
    class Lease:pass
    class UnavailableWitness:
        def __getattr__(self,name):pytest.fail('native observation without reviewed policy')
    lease=Lease();value=controlled_state();a._bound[lease]=value
    try:
        assert _REVIEWED_POLICY is None
        assert minimum_runtime(lease,UnavailableWitness(),time.monotonic()+1) is None and not value.facts
    finally:a._bound.pop(lease,None)


@pytest.mark.parametrize('deadline',[float('inf'),float('nan'),-1])
def test_minimum_runtime_deadline_refused_before_native_reads(deadline):
    from scripts.windows_portable.native_trial_facts import minimum_runtime
    from scripts.windows_portable.native_runtime_staging import NativeRuntimeInstallation
    from scripts.windows_portable.native_acceptance_issuer import AcceptanceRefused
    class Lease:pass
    class UnavailableWitness:
        def __getattr__(self,name):pytest.fail('native read before deadline validation')
    lease=Lease();value=controlled_state();a._bound[lease]=value
    try:
        with pytest.raises(AcceptanceRefused):minimum_runtime(lease,UnavailableWitness(),deadline)
        installation=object.__new__(NativeRuntimeInstallation)
        with pytest.raises(AcceptanceRefused):installation.all_crt_imports_held(lease,{},deadline)
    finally:a._bound.pop(lease,None)
