"""Actual journal boundary/close code with synthetic calls, no Windows syscalls."""
import ctypes as C
import gc
from types import SimpleNamespace
import weakref

import pytest

from scripts.windows_portable.fixed_windows_journal import FixedWindowsFilesystem
from scripts.windows_portable.directories import LeaseRefused


@pytest.mark.parametrize('operation',['signature','seek','write'])
@pytest.mark.parametrize('outcome',['exception','pending'])
def test_unacknowledged_journal_io_retains_borrowed_storage_and_blocks_all_closes(monkeypatch,operation,outcome):
    monkeypatch.setattr(C,'get_last_error',lambda:997,raising=False)
    refs=[];closed=[]
    def interrupted(*args):
        if operation=='signature':refs.append(weakref.ref(args[1]._obj))
        if operation=='write':refs.extend((weakref.ref(args[1]),weakref.ref(args[3]._obj)))
        if outcome=='exception':raise RuntimeError('SYNTHETIC_FFI_INTERRUPTION')
        return False
    def seek(*args):return True
    api=SimpleNamespace(readonly=SimpleNamespace(k=SimpleNamespace(SetFilePointerEx=seek)),
        getinfo=interrupted,writefile=interrupted,close=closed.append)
    api.need=lambda ok:None if ok else (_ for _ in ()).throw(LeaseRefused('SYNTHETIC_CALL_REFUSED'))
    if operation=='seek':api.readonly.k.SetFilePointerEx=interrupted
    fs=FixedWindowsFilesystem('C:\\synthetic-not-opened',api=api)
    fs.journal=11;fs.handles=[11,12];fs.lock=12
    try:
        if operation=='signature':fs.signature()
        elif operation=='seek':fs._seek(0)
        else:fs.write_at(0,b'SYNTHETIC_SLOT_BYTES')
    except Exception as error:error.__traceback__=None
    else:pytest.fail('unacknowledged call must refuse')
    gc.collect()
    assert api.readonly._query_unknown and all(ref() is not None for ref in refs)
    with pytest.raises(Exception):fs.close()
    assert closed==[] and fs.handles==[11,12]
    original=weakref.ref(fs);del fs;gc.collect()
    assert original() is not None  # Source call storage, not a saved traceback, retains the pins.


@pytest.mark.parametrize('count',[0,2,5,6])
def test_acknowledged_partial_write_count_preserves_original_slot_contract(count):
    def seek(*args):return True
    def write(handle,buffer,size,written,overlapped):
        C.cast(written,C.POINTER(C.c_uint32))[0]=count
        return True
    api=SimpleNamespace(readonly=SimpleNamespace(k=SimpleNamespace(SetFilePointerEx=seek)),writefile=write)
    api.need=lambda ok:None
    fs=FixedWindowsFilesystem('C:\\synthetic-not-opened',api=api);fs.journal=11
    if count<=5:assert fs.write_at(0,b'12345')==count
    else:
        with pytest.raises(LeaseRefused):fs.write_at(0,b'12345')
