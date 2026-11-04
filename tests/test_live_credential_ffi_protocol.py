"""CREDENTIALW layout/ownership protocol on controlled ctypes allocations.

No Windows DLL is loaded and no OS credential is read/created. This exercises
the production ownership code with pure Python function seams, not Windows ABI
execution or current-user Credential Manager acceptance.
"""
import ctypes as c
from types import SimpleNamespace
import pytest
from parkweave import live_credentials as m
from parkweave.intern_adapter import ModelBoundaryError


def api(mode='good'):
    owned=SimpleNamespace(frees=0,blob=c.create_string_buffer(b'private synthetic blob'))
    def read(target,kind,flags,out):
        assert target.value==m.TARGET and kind==1 and flags==0
        Type=read.argtypes[-1]._type_._type_
        value=Type();value.Type=1;value.TargetName=m.TARGET if mode!='wrong-target' else 'WRONG'
        value.CredentialBlobSize=len(b'private synthetic blob')
        value.CredentialBlob=c.cast(owned.blob,c.POINTER(c.c_ubyte));owned.value=value
        c.cast(out,read.argtypes[-1])[0]=c.pointer(value)
        if mode=='read-unknown':raise RuntimeError('private exception text')
        return 0 if mode=='false-output' else 1
    def free(pointer):
        owned.frees+=1
        assert owned.blob.raw[:len(b'private synthetic blob')]==b'\0'*len(b'private synthetic blob')
        if mode=='free-unknown':raise RuntimeError('private free text')
    owned.CredReadW=read;owned.CredFree=free
    return owned


def test_fixed_windows_amd64_layout_and_original_owned_release_protocol():
    Type=m._credential_type()
    if c.sizeof(c.c_void_p)!=8:pytest.skip('AMD64 layout only')
    assert c.sizeof(Type)==80
    assert [getattr(Type,name).offset for name in ('Flags','Type','TargetName','Comment','LastWritten',
        'CredentialBlobSize','CredentialBlob','Persist','AttributeCount','Attributes','TargetAlias','UserName')]==[0,4,8,16,24,32,40,48,52,56,64,72]
    controlled=api();before=len(m._retained)
    assert m._read_credential(controlled)==b'private synthetic blob'
    assert controlled.frees==1 and len(m._retained)==before


@pytest.mark.parametrize('mode',['false-output','read-unknown','free-unknown'])
def test_unknown_read_or_free_keeps_original_graph_and_never_retries(mode):
    controlled=api(mode);before=len(m._retained)
    with pytest.raises(ModelBoundaryError) as error:m._read_credential(controlled)
    assert 'private' not in str(error.value)
    assert controlled.frees==(1 if mode=='free-unknown' else 0)
    assert len(m._retained)==before+1
    graph=m._retained[-1]
    assert graph['api'] is controlled and graph['target'].value==m.TARGET
    assert graph['pointer'] and graph['argument'] is not None
    assert graph['free_attempted']==(mode=='free-unknown') and graph['free_returned'] is False


def test_wipe_failure_retains_allocation_without_free_or_retry(monkeypatch):
    controlled=api();before=len(m._retained)
    def refused(*args):raise RuntimeError('private wipe text')
    monkeypatch.setattr(c,'memset',refused)
    with pytest.raises(ModelBoundaryError,match='LIVE_CREDENTIAL_RELEASE_UNKNOWN'):m._read_credential(controlled)
    assert controlled.frees==0 and len(m._retained)==before+1
    assert m._retained[-1]['free_attempted'] is False


def test_known_owned_wrong_target_is_released_once_without_fallback():
    controlled=api('wrong-target');before=len(m._retained)
    with pytest.raises(ModelBoundaryError,match='LIVE_CREDENTIAL_UNAVAILABLE'):m._read_credential(controlled)
    assert controlled.frees==1 and len(m._retained)==before
