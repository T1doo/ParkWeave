"""Negative native admission and actual memory-layout export parser only."""
import ctypes as C
import time
import pytest
from scripts.windows_portable import native_iat_observer as observer,native_loader_images as images
from scripts.windows_portable import native_trial_authority as a
from tests.test_loader_inputs import module
from tests.test_native_trial_boundaries import controlled_state
from types import SimpleNamespace


def test_unreviewed_namespace_layout_never_reads_process_or_issues_fact(monkeypatch):
    monkeypatch.setattr(C,'WinDLL',lambda *args,**kw:pytest.fail('native before reviewed layout'),raising=False)
    assert observer._REVIEWED_LAYOUT is None
    assert observer.capture_peer(None,None,None,time.monotonic()+1,None) is None
    assert observer.capture_groups(None,None,(),time.monotonic()+1,None) is None
    assert not observer._peers
    with pytest.raises(a.TrialRefused):images.inspect(images.HeldImages(),None,None,time.monotonic()+1)


def test_server_trial_layout_is_parser_selection_and_never_invents_windows11_facts(monkeypatch):
    class Lease:pass
    lease=Lease();a._bound[lease]=controlled_state()
    monkeypatch.setattr(observer,'os',SimpleNamespace(name='nt'))
    actual=[10,0,26100,3]
    monkeypatch.setattr(observer,'sys',SimpleNamespace(getwindowsversion=lambda:SimpleNamespace(
        major=actual[0],minor=actual[1],build=actual[2],product_type=actual[3])))
    try:
        assert observer._REVIEWED_LAYOUT is None and observer.layout() is None
        selected=observer.layout(lease)
        assert (selected.nt_version,selected.peb_api_set_offset,selected.namespace_version)==((10,0,26100,3),0x68,6)
        actual[:]=[10,0,22631,1]
        assert observer.layout(lease) is None and not observer._peers
    finally:a._bound.pop(lease,None)


@pytest.mark.parametrize('forwarder',[None,'kernelbase.function'])
def test_export_parser_reads_rvas_from_memory_layout_not_file_offsets(forwarder):
    raw=module(forwarder=forwarder);mapped=bytearray(0x2000)
    mapped[:512]=raw[:512];mapped[0x1000:0x1600]=raw[512:2048]
    class Memory:
        def image_read(self,base,size,offset,length):
            assert base==0x140000000 and size==len(mapped)
            return bytes(mapped[offset:offset+length])
    image=observer.RemoteImage(Memory(),0x140000000,len(mapped))
    assert image.export_targets()['function']==((0x11c0,forwarder) if forwarder else (0x1700,None))
