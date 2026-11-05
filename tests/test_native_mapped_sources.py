"""Failure/ownership protocol only. No debug attachment or native observation."""
import ctypes as C
import threading
import time
import os
from types import SimpleNamespace

import pytest

from scripts.windows_portable import native_mapped_sources as mapped,native_trial_authority as a
from scripts.windows_portable.processes import _ProcessState,OwnedGroup,PrivateProcessAdapter
from scripts.windows_portable.windows_process_handles import WindowsJobProcess
from tests.test_native_trial_boundaries import controlled_state


@pytest.mark.parametrize('ready', [False, True])
def test_before_resume_waits_for_validated_continued_attach_breakpoint(monkeypatch,ready):
    lease=object();backend=object.__new__(WindowsJobProcess);calls=[]
    backend.birth=lambda process:(calls.append('identity') or (33,44))
    item=SimpleNamespace(attached=True,ready=SimpleNamespace(wait=lambda seconds:(calls.append('ready') or ready)),
                         initial_event=True,initial_breakpoint=True,exited=False)
    trace=SimpleNamespace(watch=lambda *args:(calls.append('attach') or item),failed=False)
    group=SimpleNamespace(executable=SimpleNamespace(lease=lease),started=False,
                          resources=dict(bound=True,process=11,job=22,birth=(33,44)))
    monkeypatch.setattr(a,'bound_state',lambda selected:object())
    monkeypatch.setattr(a,'budget',lambda *args:calls.append('budget'))
    monkeypatch.setattr(mapped,'session',lambda selected:trace)
    if ready:
        mapped.before_resume(backend,group,time.monotonic()+1)
        assert calls==['attach','ready','budget','identity']
    else:
        with pytest.raises(a.TrialRefused):mapped.before_resume(backend,group,time.monotonic()+1)
        assert calls==['attach','ready']


@pytest.mark.parametrize('field', ['failed','initial_event','initial_breakpoint','exited'])
def test_ready_signal_does_not_bypass_attach_state_validation(monkeypatch,field):
    lease=object();backend=object.__new__(WindowsJobProcess)
    item=SimpleNamespace(attached=True,ready=SimpleNamespace(wait=lambda seconds:True),
                         initial_event=True,initial_breakpoint=True,exited=False)
    trace=SimpleNamespace(watch=lambda *args:item,failed=False)
    setattr(trace if field=='failed' else item,field,field in ('failed','exited'))
    group=SimpleNamespace(executable=SimpleNamespace(lease=lease),started=False,
                          resources=dict(bound=True,process=11,job=22,birth=(33,44)))
    monkeypatch.setattr(a,'bound_state',lambda selected:object())
    monkeypatch.setattr(mapped,'session',lambda selected:trace)
    with pytest.raises(a.TrialRefused):mapped.before_resume(backend,group,time.monotonic()+1)


def signature_pump(monkeypatch, callback):
    """Real Python thread/registry protocol; no Windows/native observation."""
    from scripts.windows_ci import native_business_window as window
    from scripts.windows_portable import native_system_crt as crt
    clock=[1000.];context=object()
    monkeypatch.setattr(mapped,'time',SimpleNamespace(monotonic=lambda:clock[0],time=lambda:100.))
    monkeypatch.setattr(window,'current_context',lambda:context)
    trace=object.__new__(mapped.NativeMappedSources)
    value=object.__new__(crt.NativeSystemCRT)
    value.lease=object();value.api=object();value.installation=object()
    value.closed=value.failed=False;value.unknown=[];value.deadline=1. # Old constructor end.
    trace.crt=value;trace.lease=value.lease;trace.api=value.api;trace.installation=value.installation
    trace.security=SimpleNamespace(system_crt=value,lease=value.lease)
    trace.state=SimpleNamespace(key=object(),context=context,closed=False,failed=False,
        deadline=1100.,cleanup_end=1160.,window=SimpleNamespace(expires_utc=200.))
    trace.failed=trace.closed=False;trace.expected={};trace.system_path=r'c:\synthetic-system32'
    trace.delegation=mapped.PumpDelegation();results=[];errors=[]
    def run():
        try:results.append(callback(trace,value,clock))
        except BaseException as error:errors.append(error)
    trace.thread=threading.Thread(target=run)
    mapped._delegations[trace.delegation]=(trace,trace.state,os.getpid(),trace.state.key,
        trace.thread,trace.expected,trace.system_path,value,value.lease)
    try:
        # Even an issued token cannot be used from the issuing/main thread.
        with pytest.raises(a.TrialRefused):mapped.signature_budget(trace.delegation,value)
        trace.thread.start();trace.thread.join(2)
        assert not trace.thread.is_alive()
        if errors:raise errors[0]
        return results[0]
    finally:mapped._delegations.pop(trace.delegation,None)


def test_signature_pump_exact_issuance_and_fixed_end(monkeypatch):
    def check(trace,crt,clock):
        end=mapped.signature_budget(trace.delegation,crt);assert end==1030.
        clock[0]=1015.;assert mapped.signature_budget(trace.delegation,crt,end)==end
        with pytest.raises(a.TrialRefused):mapped.signature_budget(mapped.PumpDelegation(),crt)
        with pytest.raises(a.TrialRefused):mapped.signature_budget(trace.delegation,SimpleNamespace(lease=crt.lease))
        with pytest.raises(a.TrialRefused):mapped.signature_budget(trace.delegation,crt,1090.)
        old=trace.security.lease;trace.security.lease=object()
        with pytest.raises(a.TrialRefused):mapped.signature_budget(trace.delegation,crt,end)
        trace.security.lease=old
        original=trace.state.key;trace.state.key=object()
        with pytest.raises(a.TrialRefused):mapped.signature_budget(trace.delegation,crt,end)
        trace.state.key=original
        clock[0]=1030.
        with pytest.raises(a.TrialRefused):mapped.signature_budget(trace.delegation,crt,end)
        trace.state.failed=crt.failed=True;clock[0]=1101.
        assert mapped.signature_budget(trace.delegation,crt,cleanup=True)==1160.
        with pytest.raises(a.TrialRefused):mapped.signature_budget(trace.delegation,crt)
        clock[0]=1160.
        with pytest.raises(a.TrialRefused):mapped.signature_budget(trace.delegation,crt,cleanup=True)
        return True
    assert signature_pump(monkeypatch,check)


def test_signature_pump_expired_work_still_uses_original_cleanup_without_main_thread_budget(monkeypatch):
    from scripts.windows_portable import native_system_crt as crt_module
    monkeypatch.setattr(a,'budget',lambda *args,**kw:pytest.fail('main-thread lease budget on pump'))
    def check(trace,crt,clock):
        calls=[]
        def wvt(hwnd,action,data):
            row=C.cast(data,C.POINTER(crt_module.TrustData)).contents;calls.append(row.action)
            if row.action==1:row.state=17;clock[0]=1031.
            return 0
        crt.wvt=wvt;crt.provider=lambda *args:pytest.fail('provider after fixed signature end')
        with pytest.raises(crt_module.CRTTrustFailure) as caught:
            crt._signature(41,'C:/synthetic-system32/kernel32.dll',delegation=trace.delegation,
                deadline=mapped.signature_budget(trace.delegation,crt))
        error=caught.value
        assert (error.stage,error.activity,error.close_outcome)==('PROVIDER_DATA','WORK_BUDGET','RETURNED_SUCCESS')
        assert error.verify_returned and error.verify_ok and calls==[1,2] and crt.deadline==1.
        assert not crt.unknown
        return True
    assert signature_pump(monkeypatch,check)


def test_catalog_expired_embedded_end_refuses_before_query_and_empty_cleanup_stays_known(monkeypatch):
    from scripts.windows_portable import native_catalog_signature as catalog,native_system_crt as crt_module
    monkeypatch.setattr(catalog,'native_file_path',lambda *args:pytest.fail('query after original signature end'))
    monkeypatch.setattr(a,'fail_resource',lambda *args:pytest.fail('empty verifier cleanup falsely failed'))
    def check(trace,crt,clock):
        trace.api=crt.api=SimpleNamespace(readonly=SimpleNamespace())
        end=mapped.signature_budget(trace.delegation,crt);clock[0]=end
        with pytest.raises(crt_module.CRTRefused):
            catalog.verify_member(trace,41,'C:/synthetic-system32/kernel32.dll',signature_deadline=end)
        verifier=trace.catalog_verifiers[0]
        assert verifier.closed and not verifier.unknown and not verifier.resources and not verifier.nodes
        assert not trace.failed and not crt.failed
        return True
    assert signature_pump(monkeypatch,check)


@pytest.mark.parametrize('start,expected',[(1000.,1010.),(1025.,1030.)])
def test_catalog_keeps_ten_second_cap_and_original_embedded_end(monkeypatch,start,expected):
    from scripts.windows_portable import native_catalog_signature as catalog
    monkeypatch.setattr(catalog,'native_file_path',lambda *args:r'C:\synthetic-system32\kernel32.dll')
    monkeypatch.setattr(catalog,'bind',lambda *args:None)
    monkeypatch.setattr(catalog.CatalogMemberVerifier,'verify',lambda self:self.deadline)
    def check(trace,crt,clock):
        trace.api=crt.api=SimpleNamespace(readonly=SimpleNamespace())
        trace.pending={'file':dict(handle=41,owned=True,attempted=False)}
        trace.files=[trace.pending['file']]
        crt.path=r'C:\synthetic-system32';crt.trust=crt.crypto=object()
        end=mapped.signature_budget(trace.delegation,crt);clock[0]=start
        monkeypatch.setattr(catalog,'time',SimpleNamespace(monotonic=lambda:clock[0]))
        assert catalog.verify_member(trace,41,crt.path+r'\kernel32.dll',signature_deadline=end)==expected
        assert trace.catalog_verifiers[0].closed and end==1030.
        return True
    assert signature_pump(monkeypatch,check)


def test_unbound_trace_refuses_before_native_or_thread(monkeypatch):
    monkeypatch.setattr(C,'WinDLL',lambda *args,**kw:pytest.fail('native before trial scope'),raising=False)
    with pytest.raises(a.TrialRefused):mapped.NativeMappedSources(None,None)


def test_foreign_original_group_cannot_be_duplicated_queued_or_attached():
    class Lease:pass
    local,foreign=Lease(),Lease();a._bound[local]=controlled_state()
    backend=object.__new__(WindowsJobProcess)
    state=_ProcessState(None,SimpleNamespace(lease=foreign));token=OwnedGroup()
    adapter=object.__new__(PrivateProcessAdapter);adapter.lease=foreign;adapter.backend=backend
    adapter._issued={id(token):(token,state)}
    trace=object.__new__(mapped.NativeMappedSources);trace.lease=local;trace.failed=trace.closed=False
    trace.closing=threading.Event();trace.security=SimpleNamespace(processes=SimpleNamespace(
        _owned={id(token):[token,adapter,False,False]}))
    trace._duplicate=lambda handle:pytest.fail('duplicated before original lease binding')
    try:
        with pytest.raises(a.TrialRefused):trace.watch(backend,11,22,(33,44),state,time.monotonic()+1)
    finally:a._bound.pop(local,None)


def controlled_trace():
    trace=object.__new__(mapped.NativeMappedSources);trace.lock=threading.Lock()
    trace.events=[];trace.files=[];trace.pending=None;trace.incomplete=set();trace.failed=False
    trace.crt=SimpleNamespace(unknown=[])
    watch=mapped.Watch(11,12,(12,13),14,None,None,threading.Event(),threading.Event(),
        attached=True,initial_event=True,modules={})
    trace.watches={12:watch};return trace,watch


def test_pending_load_is_published_before_file_processing_or_snapshot():
    trace,watch=controlled_trace();event=mapped.DebugEvent();event.code=6;event.pid=12;event.tid=15
    event.data.load.base=4096
    trace._identity=lambda *args:None
    def file(*args):
        assert watch.pending_images==1 and watch.epoch==1
        assert trace._snapshot_locked(watch,time.monotonic()+1) is None
        return None
    trace._file=file
    def continued(*args):
        assert watch.pending_images==1
        return 1
    trace.continue_event=continued
    trace._event(event)
    assert watch.pending_images==0 and watch.epoch==2 and trace.pending is None


def test_continue_unknown_retains_original_event_file_and_pending_epoch():
    trace,watch=controlled_trace();event=mapped.DebugEvent();event.code=6;event.pid=12;event.tid=15
    event.data.load.file=99;event.data.load.base=4096
    trace._file=lambda *args:None;trace.continue_event=lambda *args:0
    with pytest.raises(a.TrialRefused):trace._event(event)
    assert trace.files[0]['handle']==99 and not trace.files[0]['attempted']
    assert trace.pending['attempted'] and not trace.pending['continued'] and watch.pending_images==1


def test_only_original_breakin_thread_and_address_is_handled_other_exceptions_are_preserved():
    trace,watch=controlled_trace();calls=[]
    watch.breakin_threads={15:(77,0x1234,0x5678)}
    trace.thread_id=lambda h:15
    trace.thread_process_id=lambda h:12
    def start(handle,kind,output,size,used):
        output._obj.value=0x1234;used._obj.value=C.sizeof(C.c_void_p);return 0
    trace.thread_start=start
    trace.continue_event=lambda pid,tid,status:calls.append(status) or 1
    for code,tid in ((0xc0000005,15),(0x80000003,16),(0x80000003,15),(0x80000003,15)):
        event=mapped.DebugEvent();event.code=1;event.pid=12;event.tid=tid
        event.data.exception.first_chance=1;event.data.exception.record.code=code
        event.data.exception.record.address=0x5678
        trace._event(event)
    assert calls==[0x80010001,0x80010001,0x10002,0x80010001]
