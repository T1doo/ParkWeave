"""Negative native admission and actual memory-layout export parser only."""
import ctypes as C
import time
import pytest
from scripts.windows_portable import native_iat_observer as observer,native_loader_images as images
from scripts.windows_portable import native_trial_authority as a
from tests.test_loader_inputs import module


def test_unreviewed_namespace_layout_never_reads_process_or_issues_fact(monkeypatch):
    monkeypatch.setattr(C,'WinDLL',lambda *args,**kw:pytest.fail('native before reviewed layout'),raising=False)
    assert observer._REVIEWED_LAYOUT is None
    assert observer.capture_peer(None,None,None,time.monotonic()+1,None) is None
    assert observer.capture_groups(None,None,(),time.monotonic()+1,None) is None
    assert not observer._peers
    with pytest.raises(a.TrialRefused):images.inspect(images.HeldImages(),None,None,time.monotonic()+1)


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
