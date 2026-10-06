"""Held-handle reads only; no native security changes or permission acquisition."""
import ctypes,json,struct
from types import SimpleNamespace
import pytest
from scripts.windows.descriptor_readonly_probe import NativeReader,Snapshot,diagnose_existing_handle


def acl(slack=b''):
    return struct.pack('<BBHHH',2,0,8+len(slack),0,0)+slack


@pytest.mark.parametrize('change',['NONE','SLACK','CONTROL','NULL_EMPTY'])
def test_readonly_ab_fixed_control_and_full_contract(change):
    snapshots=[Snapshot(acl(b'AAAA'),0x8004),Snapshot(acl(b'AAAA'),0x8004)]
    if change=='SLACK':snapshots[1]=Snapshot(acl(b'BBBB'),0x8004)
    if change=='CONTROL':snapshots[1]=Snapshot(acl(b'AAAA'),0x8404)
    if change=='NULL_EMPTY':snapshots=[Snapshot(None,0x8004),Snapshot(acl(),0x8004)]
    class Reader:
        def snapshot(self,handle):assert handle==7;return snapshots.pop(0)
    row=diagnose_existing_handle(7,backend=Reader(),clock=lambda:10.)
    assert row['status']=='AVAILABLE' and row['read_count']==2
    assert row['raw_read_stable']==(change=='NONE')
    assert row['strict_contract']==('UNCHANGED' if change=='NONE' else 'REFUSED')
    assert row['historical_owner_transition']=='NOT_MEASURED' and row['semantic_permission_change']=='UNKNOWN'
    if change=='CONTROL':assert row['control_changed_bits']==['DACL_AUTO_INHERITED']
    if change=='SLACK':assert row['ordered_ace_bytes']=='EQUAL' and not row['slack_equal']
    assert 'AAAA' not in json.dumps(row) and 'BBBB' not in json.dumps(row)


@pytest.mark.parametrize('handle',[False,0,-1,2**128])
def test_invalid_handle_never_requests_access(handle):
    class Reader:
        def snapshot(self,*args):raise AssertionError('must not read')
    assert diagnose_existing_handle(handle,backend=Reader())['reason']=='INVALID_HANDLE'


def test_deadline_read_failure_and_private_reason_never_escape():
    now=[10.]
    class Slow:
        def snapshot(self,*args):now[0]=15.;return Snapshot(acl(),0x8004)
    row=diagnose_existing_handle(7,backend=Slow(),clock=lambda:now[0])
    assert row['reason']=='DEADLINE' and row['read_count']==1
    class Refused:
        def snapshot(self,*args):raise RuntimeError('PRIVATE_SID_PATH_TOKEN')
    row=diagnose_existing_handle(7,backend=Refused(),clock=lambda:10.)
    assert row['status']=='UNAVAILABLE' and 'PRIVATE' not in json.dumps(row)


@pytest.mark.parametrize('valid',[True,False])
def test_native_copy_validates_acl_and_frees_returned_descriptor(valid):
    buf=ctypes.create_string_buffer(acl());control_calls=[];freed=[]
    reader=NativeReader.__new__(NativeReader)
    def security(handle,kind,flags,owner,group,dacl,sacl,descriptor):
        assert (handle,kind,flags)==(7,1,5) and group is None and sacl is None
        ctypes.cast(dacl,ctypes.POINTER(ctypes.c_void_p))[0]=ctypes.addressof(buf)
        ctypes.cast(descriptor,ctypes.POINTER(ctypes.c_void_p))[0]=99
        return 0
    def control(descriptor,value,revision):
        ctypes.cast(value,ctypes.POINTER(ctypes.c_uint16))[0]=0x8004;control_calls.append(True);return 1
    def information(dacl,value,size,kind):
        assert kind==2
        from scripts.windows.descriptor_readonly_probe import AclSizeInformation
        info=ctypes.cast(value,ctypes.POINTER(AclSizeInformation)).contents
        info.count,info.used,info.free=0,8,0;return 1
    reader.api=SimpleNamespace(GetSecurityInfo=security,GetSecurityDescriptorControl=control,IsValidAcl=lambda _:valid,GetAclInformation=information)
    reader.kernel=SimpleNamespace(LocalFree=lambda pointer:freed.append(pointer.value))
    if valid:assert reader.snapshot(7)==Snapshot(acl(),0x8004)
    else:
        with pytest.raises(ValueError):reader.snapshot(7)
    assert freed==[99] and control_calls==[True]


@pytest.mark.parametrize('mode',['VALID','WRONG_ACE_POINTER','GET_ACE_REFUSED','FREE_REFUSED'])
def test_native_ordered_ace_boundaries_and_release_refusal(mode):
    from scripts.windows.descriptor_readonly_probe import AclSizeInformation
    data=struct.pack('<BBHHH',2,0,16,1,0)+bytes((0,0,8,0,1,0,0,0))
    buf=ctypes.create_string_buffer(data);freed=[];reader=NativeReader.__new__(NativeReader)
    def security(handle,kind,flags,owner,group,dacl,sacl,descriptor):
        ctypes.cast(dacl,ctypes.POINTER(ctypes.c_void_p))[0]=ctypes.addressof(buf)
        ctypes.cast(descriptor,ctypes.POINTER(ctypes.c_void_p))[0]=99;return 0
    def control(descriptor,value,revision):
        ctypes.cast(value,ctypes.POINTER(ctypes.c_uint16))[0]=0x8004;return 1
    def information(dacl,value,size,kind):
        info=ctypes.cast(value,ctypes.POINTER(AclSizeInformation)).contents
        info.count,info.used,info.free=1,16,0;return 1
    def getace(dacl,index,value):
        assert index==0
        ctypes.cast(value,ctypes.POINTER(ctypes.c_void_p))[0]=ctypes.addressof(buf)+(12 if mode=='WRONG_ACE_POINTER' else 8)
        return 0 if mode=='GET_ACE_REFUSED' else 1
    def free(value):freed.append(value.value);return 99 if mode=='FREE_REFUSED' else None
    reader.api=SimpleNamespace(GetSecurityInfo=security,GetSecurityDescriptorControl=control,IsValidAcl=lambda _:True,GetAclInformation=information,GetAce=getace)
    reader.kernel=SimpleNamespace(LocalFree=free)
    if mode=='VALID':assert reader.snapshot(7)==Snapshot(data,0x8004)
    else:
        with pytest.raises((ValueError,RuntimeError)):reader.snapshot(7)
    assert freed==[99]


def test_cli_rejects_private_malformed_input_without_echo(capsys):
    from scripts.windows.descriptor_readonly_probe import main
    assert main(['--held-handle','PRIVATE_PATH_TOKEN'])==1
    assert 'PRIVATE' not in capsys.readouterr().out
