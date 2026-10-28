"""Cloud PE bytes and controlled native-call protocol; not Windows acceptance."""
import ctypes as C
import struct
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.windows_portable import native_system_crt as n
from scripts.windows_portable.crt_pe import Image,compatible,requirements
from scripts.windows_portable.payload import PayloadRefused
from scripts.windows_portable.test_payload import pe
from parkweave.windows_files import Security,Ace


def dll():
    raw=bytearray(pe());opt=0x98
    struct.pack_into('<II',raw,opt+112,0x1100,0x100)
    struct.pack_into('<IIIIIII',raw,768+16,1,1,1,0x1180,0x1190,0x11a0,0)
    struct.pack_into('<I',raw,896,0x1300);struct.pack_into('<I',raw,912,0x11b0)
    struct.pack_into('<H',raw,928,0);raw[944:953]=b'function\0';raw[1280]=0xc3
    struct.pack_into('<II',raw,opt+112+16,0x1400,0x180)
    for offset,name,child in ((1536,16,0x80000020),(1568,1,0x80000040),(1600,1033,0x60)):
        struct.pack_into('<HH',raw,offset+12,0,1);struct.pack_into('<II',raw,offset+16,name,child)
    struct.pack_into('<IIII',raw,1632,0x1480,92,0,0)
    struct.pack_into('<HHH',raw,1664,92,52,0);raw[1670:1702]='VS_VERSION_INFO\0'.encode('utf-16-le')
    struct.pack_into('<13I',raw,1704,0xfeef04bd,0x10000,(14<<16)|42,34438<<16,0,0,0,0,0,2,0,0,0)
    return raw


def test_pe_machine_resource_exports_ordinals_and_forwarder_refusal():
    raw=dll();assert compatible(bytes(raw),('function','#1'))==(14,42,34438,0)
    with pytest.raises(PayloadRefused):compatible(bytes(raw),('missing',))
    struct.pack_into('<I',raw,896,0x11c0);raw[960:979]=b'unknown.forwarder\0\0'
    with pytest.raises(PayloadRefused):compatible(bytes(raw),('function',))
    raw=dll();struct.pack_into('<H',raw,0x84,0x14c)
    with pytest.raises(PayloadRefused):Image(bytes(raw))
    raw=dll();struct.pack_into('<I',raw,1704,0)
    with pytest.raises(PayloadRefused):compatible(bytes(raw),('function',))
    raw=dll();struct.pack_into('<I',raw,1712,15<<16)
    with pytest.raises(PayloadRefused):compatible(bytes(raw),('function',))


def test_import_names_ordinals_and_delay_form_are_not_dll_name_only():
    for delay in (False,True):
        raw=bytearray(pe(delay=('vcruntime140.dll',)) if delay else pe(('vcruntime140.dll',)))
        descriptor=768 if delay else 512
        struct.pack_into('<I',raw,descriptor+(16 if delay else 0),0x1380)
        struct.pack_into('<QQQ',raw,1408,0x13c0,(1<<63)|17,0)
        struct.pack_into('<H',raw,1472,0);raw[1474:1483]=b'function\0'
        assert Image(bytes(raw)).crt_imports()=={'vcruntime140.dll':{'function','#17'}}
        if delay:
            struct.pack_into('<I',raw,descriptor,0)
            with pytest.raises(PayloadRefused):Image(bytes(raw)).crt_imports()


def test_actual_locked_pg_symbol_graph_and_existing_python_crt_parser():
    import zipfile
    archive=Path('/workspace/parkweave-loader-candidate-20261028/Windows-runtime-candidate-2970671314ec.zip')
    if not archive.is_file():pytest.skip('explicit acquired byte fixture unavailable')
    with zipfile.ZipFile(archive) as z:
        files={p:z.read(p) for p in z.namelist() if p.startswith('runtime/postgresql/') and p.lower().endswith(('.exe','.dll'))}
        r=requirements(files)
        # Actual frozen PG imports, not a fabricated identity/acceptance record.
        assert {k:len(v) for k,v in r['symbols'].items()}=={'msvcp140.dll':18,'vcruntime140.dll':26}
        assert set(r['processes'])=={'runtime/postgresql/bin/initdb.exe','runtime/postgresql/bin/postgres.exe'}
        assert compatible(z.read('runtime/python/vcruntime140.dll'),r['symbols']['vcruntime140.dll'])[:2]==(14,42)
        # This parser result does NOT authorize borrowing the Python domain DLL.


def test_system_acl_is_distinct_from_private_acl_and_rejects_writes():
    user='S-1-5-21-123';system='S-1-5-18'
    n.os_security(Security(system,4,(Ace(0,0,0x120089,user),)))
    for mask in (2,4,0x40,0x100,0x10000,0x40000,0x80000,0x1000000,0x10000000,0x40000000):
        with pytest.raises(n.CRTRefused):n.os_security(Security(system,4,(Ace(0,0,mask,user),)))
    n.os_security(Security(system,4,(Ace(0,0,4,user),)),ancestor=True)
    with pytest.raises(n.CRTRefused):n.os_security(Security(user,4,(Ace(0,0,0x120089,user),)))


def test_cloud_constructor_and_forged_caps_fail_before_native_calls(monkeypatch):
    native=Mock(side_effect=AssertionError('native call'))
    monkeypatch.setattr(C,'WinDLL',native,raising=False)
    with pytest.raises(n.CRTRefused):n.NativeSystemCRT(None,None,{},time.monotonic()+10)
    native.assert_not_called()
    forged=object.__new__(n.NativeSystemCRT);forged.failed=False;forged.closed=False;forged.unknown=[]
    with pytest.raises(n.CRTRefused):forged._binding()


def test_wintrust_offline_flags_and_failed_close_retain_original_storage():
    value=object.__new__(n.NativeSystemCRT);value.unknown=[];value.failed=False;value.handles=[41]
    value.api=SimpleNamespace(close=Mock())
    calls=[]
    def trust(hwnd,action,data):
        row=C.cast(data,C.POINTER(n.TrustData)).contents
        calls.append((row.action,row.ui,row.revocation,row.flags))
        assert hwnd.value==C.c_void_p(-1).value
        return -1  # Both verification and state close are unknown, no fake success.
    value.wvt=trust
    with pytest.raises(n.CRTRefused):value._signature(41,r'C:\Windows\System32\vcruntime140.dll')
    assert [x[0] for x in calls]==[1,2]
    assert all(x[1]==2 and x[2]==1 and x[3]&0x1000 for x in calls)
    assert value.unknown and value in n._unknown
    with pytest.raises(n.CRTRefused):value.close()
    value.api.close.assert_not_called();assert value.handles==[41] and len(calls)==2


def test_module_sampling_rejects_path_hijack_duplicates_and_truncation():
    value=object.__new__(n.NativeSystemCRT);value._time=lambda:None;value._architecture=lambda p:None
    value.path=r'C:\Windows\System32'
    names={1:value.path+'\\vcruntime140.dll',2:value.path+'\\msvcp140.dll'}
    def modules(process,buffer,capacity,count,flags):
        buffer[0]=1;buffer[1]=2;C.cast(count,C.POINTER(n.D)).contents.value=2*C.sizeof(n.P);return 1
    def path(process,module,buffer,size):
        buffer.value=names[module];return len(buffer.value)
    value.modules=modules;value.module_path=path
    assert set(value._loaded(7)['crt'])==n.CRT_DLLS
    names[2]=r'C:\Untrusted\msvcp140.dll'
    with pytest.raises(n.CRTRefused):value._loaded(7)

    names[2]=names[1]
    with pytest.raises(n.CRTRefused):value._loaded(7)
    def truncated(process,buffer,capacity,count,flags):
        C.cast(count,C.POINTER(n.D)).contents.value=capacity+8;return 1
    value.modules=truncated
    with pytest.raises(n.CRTRefused):value._loaded(7)


def test_native_abi_and_process_architecture_are_explicitly_x64():
    assert [C.sizeof(t) for t in (n.FileTrust,n.TrustData,n.Signer,n.ProviderCert,n.CertContext)]==[32,88,64,88,40]
    value=object.__new__(n.NativeSystemCRT)
    def arch(process,machine,native):
        C.cast(machine,C.POINTER(C.c_uint16)).contents.value=0
        C.cast(native,C.POINTER(C.c_uint16)).contents.value=0x8664
        return 1
    value.arch=arch;value._architecture(71)
    def wow(process,machine,native):
        arch(process,machine,native);C.cast(machine,C.POINTER(C.c_uint16)).contents.value=0x14c;return 1
    value.arch=wow
    with pytest.raises(n.CRTRefused):value._architecture(71)


def test_wintrust_success_and_microsoft_name_do_not_replace_pinned_root():
    value=object.__new__(n.NativeSystemCRT);value.unknown=[];value.failed=False
    calls=[]
    def trust(hwnd,action,data):
        row=C.cast(data,C.POINTER(n.TrustData)).contents;calls.append(row.action)
        if row.action==1:row.state=17
        return 0
    value.wvt=trust;value.provider=lambda state:19
    signer=n.Signer();signer.size=C.sizeof(signer);signer.count=2
    value.signer=lambda *args:C.pointer(signer)
    raw=C.create_string_buffer(b'Untrusted certificate bytes')
    context=n.CertContext();context.der=C.cast(raw,n.P);context.length=len(raw)
    cert=n.ProviderCert();cert.size=C.sizeof(cert);cert.cert=C.pointer(context)
    value.cert=lambda *args:C.pointer(cert)
    def name(cert,kind,flags,oid,buffer,length):buffer.value='Microsoft Corporation';return 22
    value.cert_name=name
    with pytest.raises(n.CRTRefused):value._signature(41,r'C:\Windows\System32\msvcp140.dll')
    assert calls==[1,2] and not value.unknown


def test_cross_installation_and_wrong_executable_pin_rejected_before_native_queries(monkeypatch):
    from scripts.windows_portable.processes import PrivateProcessAdapter
    from scripts.windows_portable.native_database_endpoint import NativeOwnedDatabaseEndpoint
    cap=object.__new__(n.NativeSystemCRT);a,b=object(),object();cap.lease=a
    cap._binding=Mock(side_effect=AssertionError('native lease query before scope check'))
    monkeypatch.setitem(n._issued,cap,(a,))  # Controlled negative scope seam, not a native issuance.
    adapter=object.__new__(PrivateProcessAdapter);adapter.lease=b
    adapter._group=Mock(side_effect=AssertionError('foreign group queried'))
    with pytest.raises(n.CRTRefused):cap.require_group_binding(adapter,object())
    with pytest.raises(n.CRTRefused):NativeOwnedDatabaseEndpoint(adapter,object(),crt_witness=cap)
    adapter._group.assert_not_called();cap._binding.assert_not_called()
    adapter.lease=a;relative='runtime/postgresql/bin/postgres.exe'
    cap.installation=SimpleNamespace(files=((relative,10,'a'*64),))
    group=SimpleNamespace(executable=SimpleNamespace(lease=a),
        command=SimpleNamespace(relative_executable=relative,size=10,sha256='b'*64))
    adapter._group=Mock(return_value=group)
    with pytest.raises(n.CRTRefused):cap.require_group_binding(adapter,object())
    cap._binding.assert_not_called()
    group.command.sha256='a'*64;group.executable.lease=b
    with pytest.raises(n.CRTRefused):cap.require_group_binding(adapter,object())
    cap._binding.assert_not_called()
