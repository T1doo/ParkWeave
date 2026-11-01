"""Original ctypes output lifetime only; no Windows creation or identity work."""
import ctypes as C
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from parkweave import windows_handles as handles
from scripts.windows_portable import desktop_profile as profile,native_protected_objects as protected
from scripts.windows_portable.fixed_windows_journal import NativeFixedLeaseAPI


def controlled(monkeypatch,create):
    value=object.__new__(profile.NativeDesktopProfile)
    api=object.__new__(NativeFixedLeaseAPI);api.readonly=object.__new__(handles.WinAPI)
    api.readonly._close=Mock(return_value=1)
    api.ntcreate=create;api.final_path=lambda h:r'\Device\SyntheticVolume\instance'
    api.open_relative=lambda *args:21
    value.operation_end=time.monotonic()+10
    value.api=api;value.handles=[];value.failed=value.close_attempted=False
    value.lease=SimpleNamespace(_verify=lambda:None,record={'phase':'RUNNING'},fs=SimpleNamespace(root=20),poisoned=False)
    monkeypatch.setattr(profile._NativeSecretFiles,'__init__',lambda self,*args:setattr(self,'sid_bytes',protected.sid_bytes('S-1-5-21-100')))
    value._inspect=lambda h,path,**kw:((1,h),('CONTROLLED_DESCRIPTOR',))
    value._verify=lambda:None
    return value


@pytest.mark.parametrize('outcome',['exception_empty','exception_handle','pending','failed_handle','success_empty','success_invalid','inconsistent_iosb'])
def test_profile_uncertain_create_keeps_original_outputs_and_never_closes_parents(monkeypatch,outcome):
    seen={}
    def create(output,access,attrs,iosb,*args):
        seen.update(output=output._obj,io=iosb._obj,attrs=attrs._obj)
        output._obj.value=None if outcome in ('exception_empty','success_empty') else handles.PTR(-1).value if outcome=='success_invalid' else 41
        iosb._obj.Information=2
        if outcome.startswith('exception'):raise C.ArgumentError('PRIVATE_CREATE_ARGUMENT')
        if outcome=='inconsistent_iosb':iosb._obj.Status=1
        return 0x103 if outcome=='pending' else -1073741790 if outcome=='failed_handle' else 0
    value=controlled(monkeypatch,create)
    value.api.getpath=lambda *args:pytest.fail('path query after unconfirmed create')
    before=len(protected._unknown)
    try:
        with pytest.raises(Exception):value._open(True)
        assert value.api.readonly._nt_create_pending and value.handles==[21]
        record=handles._NT_CREATE_PENDING[id(seen['io'])]
        assert record[1] is seen['output'] and record[2] is seen['io'] and record[3] is seen['attrs']
        assert record[4] is seen['attrs'].ObjectName.contents or C.addressof(record[4])==C.addressof(seen['attrs'].ObjectName.contents)
        assert record[6] is not None and record[3].SecurityDescriptor==C.addressof(record[6])
        with pytest.raises(Exception):value.close()
        assert value.lease.poisoned and value.close_attempted and value.handles==[21]
        value.api.readonly._close.assert_not_called()
    finally:
        if 'io' in seen:handles._NT_CREATE_PENDING.pop(id(seen['io']),None)
        del protected._unknown[before:]


@pytest.mark.parametrize('fresh',[True,False])
def test_profile_known_create_or_open_retains_original_handle_and_modes(monkeypatch,fresh):
    def create(output,access,attrs,iosb,allocation,attributes,share,disposition,options,ea,length):
        assert (access,attributes,share,disposition,options)==(0x120081,0x10,3,2 if fresh else 1,0x20|0x200000|1)
        assert bool(attrs._obj.SecurityDescriptor) is fresh
        output._obj.value=41;iosb._obj.Information=2 if fresh else 1;return 0
    value=controlled(monkeypatch,create)
    def path(h,buffer,length,flags):buffer.value=r'\\?\E:\Software\synthetic-profile';return len(buffer.value)
    value.api.getpath=path
    value._open(fresh)
    assert value.handles==[21,41] and value.profile==41 and value.path==r'E:\Software\synthetic-profile'
    value.close()
    assert [call.args[0] for call in value.api.readonly._close.call_args_list]==[41,21]


def test_profile_interrupted_dos_query_retains_original_buffer_and_borrowed_profile(monkeypatch):
    value=controlled(monkeypatch,lambda *args:None);value.profile=41;value.handles=[21,41]
    seen={}
    def query(handle,buffer,length,flags):
        buffer.value='PRIVATE_PARTIAL_PATH';seen['buffer']=buffer
        raise KeyboardInterrupt('PRIVATE_QUERY_ARGUMENT')
    value.api.getpath=query
    with pytest.raises(KeyboardInterrupt):value._dos_path()
    record=next(row for row in reversed(handles._UNKNOWN_NATIVE_QUERIES) if row[0] is value.api.readonly)
    assert record[1]=='DESKTOP_PROFILE_DOS_PATH' and record[2][-1][0] is value and record[2][-1][1] is seen['buffer']
    with pytest.raises(Exception):value.close()
    assert value.lease.poisoned and value.handles==[21,41]
    value.api.readonly._close.assert_not_called()
