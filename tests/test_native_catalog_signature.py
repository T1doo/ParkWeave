"""Catalog ABI and unknown-cleanup protocol only; never a Windows trust result."""
import ctypes as C
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from scripts.windows_portable import native_catalog_signature as catalog,native_system_crt as crt
from parkweave import windows_handles as handles
from scripts.windows_portable.windows_directory_handles import NativeLeaseAPI,WindowsFilesystem


def test_catalog_union_uses_utf16_fixed_fields_and_distinct_typed_contexts():
    assert C.sizeof(catalog.CatalogInfo)==524 and C.sizeof(catalog.CatalogTrust)==72
    assert (catalog.CatalogTrust.ctl.offset,catalog.CatalogTrust.admin.offset)==(56,64)
    assert C.sizeof(crt.TrustData)==88
    info=catalog.CatalogInfo();info.size=C.sizeof(info)
    value=r'C:\Windows\System32\CatRoot\{f750e6c3-38ee-11d1-85e5-00c04fc295ee}\样例.cat'
    raw=value.encode('utf-16-le')
    for i in range(len(raw)//2):info.path[i]=int.from_bytes(raw[i*2:i*2+2],'little')
    assert catalog.catalog_path(info)==value
    info.path[:]=[1]*260
    with pytest.raises(crt.CRTRefused):catalog.catalog_path(info)


def trust_stub(status,close_status=0):
    value=object.__new__(crt.NativeSystemCRT);value.unknown=[];value.failed=False;calls=[]
    def wvt(hwnd,action,data):
        row=C.cast(data,C.POINTER(crt.TrustData)).contents;calls.append(row.action)
        return status if row.action==1 else close_status
    value.wvt=wvt
    return value,calls


def test_only_clean_returned_nosignature_can_select_catalog_not_unknown_close():
    value,calls=trust_stub(-2146762496)  # 0x800b0100 TRUST_E_NOSIGNATURE
    with pytest.raises(crt.SignatureRejected) as caught:value._signature(41,r'C:\Windows\System32\example.dll')
    assert caught.value.status==0x800b0100 and calls==[1,2] and not value.unknown
    value,calls=trust_stub(-2146762496,-1)
    with pytest.raises(crt.CRTRefused) as caught:value._signature(41,r'C:\Windows\System32\example.dll')
    assert type(caught.value) is not crt.SignatureRejected and value.unknown and calls==[1,2]


def test_descriptor_unknown_keeps_original_native_output_and_refuses_repeat():
    api=object.__new__(NativeLeaseAPI);readonly=object.__new__(handles.WinAPI);api.readonly=readonly
    storage=C.create_string_buffer(64);closed=[]
    def getsecurity(handle,kind,flags,owner,group,dacl,sacl,sd):
        C.cast(sd,C.POINTER(handles.PTR)).contents.value=C.addressof(storage);return 0
    readonly.getsecurity=getsecurity;readonly.valid_sd=lambda sd:False
    readonly.need=lambda ok:(_ for _ in ()).throw(RuntimeError('controlled invalid SD')) if not ok else None
    readonly.localfree=lambda pointer:closed.append(pointer.value) or pointer.value
    before=len(handles._UNKNOWN_NATIVE_QUERIES)
    try:
        with pytest.raises(BaseException):api.descriptor(41)
        assert readonly._query_unknown and closed==[C.addressof(storage)]
        record=handles._UNKNOWN_NATIVE_QUERIES[-1]
        assert record[0] is readonly and record[1]=='DESCRIPTOR_FREE' and record[2][-1].value==C.addressof(storage)
        with pytest.raises(Exception):api.descriptor(41)
        assert closed==[C.addressof(storage)]
    finally:del handles._UNKNOWN_NATIVE_QUERIES[before:]


def test_query_unknown_prevents_catalog_context_and_borrowed_pin_cleanup():
    value=object.__new__(catalog.CatalogMemberVerifier)
    value.closed=value.unknown=False;value.crt=SimpleNamespace(unknown=[])
    value.api=SimpleNamespace(readonly=SimpleNamespace(_query_unknown=True),close=Mock())
    value.resources=[];value.nodes=[]
    with pytest.raises(crt.CRTRefused):value.close()
    value.api.close.assert_not_called()


@pytest.mark.parametrize('flag',['_nt_create_pending','_query_unknown'])
def test_unknown_native_borrower_keeps_crt_and_lease_ancestor_pins(flag):
    readonly=object.__new__(handles.WinAPI);setattr(readonly,flag,True);readonly._close=Mock()
    value=object.__new__(crt.NativeSystemCRT);value.unknown=[]
    value.api=SimpleNamespace(readonly=readonly);value._close_owned=Mock()
    before=len(crt._unknown)
    try:
        with pytest.raises(crt.CRTRefused):value.close()
        assert crt._unknown[-1] is value
        value._close_owned.assert_not_called()
        fs=object.__new__(WindowsFilesystem);fs.api=value.api;fs.handles=[41,42];fs.lock=42
        with pytest.raises(Exception):fs.close()
        assert fs.handles==[41,42] and not hasattr(fs,'_close_records')
        with pytest.raises(Exception):readonly.close(41)
        readonly._close.assert_not_called()
    finally:del crt._unknown[before:]
