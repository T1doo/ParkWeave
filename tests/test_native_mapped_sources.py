"""Failure/ownership protocol only. No debug attachment or native observation."""
import ctypes as C
import threading
import time
from types import SimpleNamespace

import pytest

from scripts.windows_portable import native_mapped_sources as mapped,native_trial_authority as a
from scripts.windows_portable.processes import _ProcessState,OwnedGroup,PrivateProcessAdapter
from scripts.windows_portable.windows_process_handles import WindowsJobProcess
from tests.test_native_trial_boundaries import controlled_state


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
