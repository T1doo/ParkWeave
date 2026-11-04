"""Actual PE slot boundaries; these bytes are never executed or native facts."""
import struct
import pytest
from scripts.windows_portable.crt_pe import Image
from scripts.windows_portable.payload import PayloadRefused
from scripts.windows_portable.test_payload import pe


def image(*,delay=False):
    raw=bytearray(pe(() if delay else ('kernel32.dll',),('kernel32.dll',) if delay else ()))
    opt=0x98;struct.pack_into('<I',raw,opt+56,0x2000)
    thunk=1408;iat=1472;hint=1600
    descriptor=768 if delay else 512
    struct.pack_into('<I',raw,descriptor+(16 if delay else 0),thunk-512+0x1000)
    struct.pack_into('<I',raw,descriptor+(12 if delay else 16),iat-512+0x1000)
    struct.pack_into('<QQ',raw,thunk,hint-512+0x1000,0)
    struct.pack_into('<QQ',raw,iat,0x140001700 if delay else hint-512+0x1000,0)
    raw[hint:hint+14]=b'\0\0GetLastError\0'
    return raw


@pytest.mark.parametrize('delay',[False,True])
def test_slots_preserve_actual_iat_rva_and_unresolved_delay_pointer(delay):
    raw=image(delay=delay)
    slots=Image(bytes(raw)).import_slots()
    assert slots==(('kernel32.dll','GetLastError',0x13c0,delay,0x140001700 if delay else 0x1440),)
    assert Image(bytes(raw)).symbol_imports()=={'kernel32.dll':{'GetLastError'}}
    struct.pack_into('<Q',raw,1408,(1<<63)|123)
    assert Image(bytes(raw)).import_slots()[0][1]=='#123'


@pytest.mark.parametrize('kind',['missing_iat','outside_image','nonzero_terminator','zero_ordinal'])
def test_invalid_iat_slots_refuse_before_any_process_read(kind):
    raw=image()
    if kind=='missing_iat':struct.pack_into('<I',raw,512+16,0)
    elif kind=='outside_image':struct.pack_into('<I',raw,0x98+56,0x1300)
    elif kind=='nonzero_terminator':struct.pack_into('<Q',raw,1480,1)
    else:struct.pack_into('<Q',raw,1408,1<<63)
    with pytest.raises(PayloadRefused):Image(bytes(raw)).import_slots()
