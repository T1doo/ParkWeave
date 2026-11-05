"""Bounded descriptor validation, controlled FFI outputs, no native pipe."""
import ctypes as C
from types import SimpleNamespace
import json
import pytest
from scripts.windows_portable import initdb_pipe_candidate as p
from scripts.windows_portable.test_initdb_pipe_source import descriptor,SID
from scripts.windows_ci.native_failure_diagnostics import detail,SourceSites
from pathlib import Path


def server(raw,needed,valid=True,length=None):
    value=object.__new__(p._OwnedInitdbPipe);value._handle=17
    calls=[]
    def info(handle,flags):
        C.cast(flags,C.POINTER(C.c_uint32)).contents.value=0;return True
    def security(handle,flags,buffer,size,used):
        assert flags==5 and size==65536
        C.memmove(buffer,raw,len(raw));C.cast(used,C.POINTER(C.c_uint32)).contents.value=needed
        return True
    def validate(buffer):calls.append('validate');return valid
    def measured(buffer):calls.append('length');return len(raw) if length is None else length
    value._kernel=SimpleNamespace(GetFileType=lambda h:3,GetHandleInformation=info)
    value._adv=SimpleNamespace(GetKernelObjectSecurity=security,IsValidSecurityDescriptor=validate,
                               GetSecurityDescriptorLength=measured)
    return value,calls


@pytest.mark.parametrize('needed',[0,len(descriptor())])
def test_valid_descriptor_requires_independent_validation_and_length(needed):
    value,calls=server(descriptor(),needed);value._verify_native(SID)
    assert calls==['validate','length']


@pytest.mark.parametrize('needed',[1,65537,0xffffffff])
def test_nonzero_inconsistent_size_still_refused(needed):
    value,_=server(descriptor(),needed)
    with pytest.raises(p.PipeRefused):value._verify_native(SID)


def test_zero_needed_cannot_admit_invalid_descriptor_before_native_traversal():
    value,calls=server(b'\0'*20,0)
    with pytest.raises(p.PipeRefused):value._verify_native(SID)
    assert calls==[]


@pytest.mark.parametrize('length',[19,65537,len(descriptor())-1])
def test_independent_length_cannot_escape_or_truncate_components(length):
    value,_=server(descriptor(),0,length=length)
    with pytest.raises(p.PipeRefused):value._verify_native(SID)


def test_native_structural_rejection_is_preserved():
    value,calls=server(descriptor(),0,valid=False)
    with pytest.raises(p.PipeRefused):value._verify_native(SID)
    assert calls==['validate']


def test_pipe_failure_diagnostic_is_bounded_and_source_is_resolved():
    error=p.PipeFailure('READ_PIPE_SECURITY','PRIVATE', [('PRIVATE',)],0)
    public=detail(error,'PipeFailure')
    assert public['initdb_pipe']==dict(phase='READ_PIPE_SECURITY',winerror=0)
    assert 'PRIVATE' not in json.dumps(public)
    public=detail(p.PipeFailure('PRIVATE',None,[],True),'PipeFailure')
    assert public['initdb_pipe']==dict(details='UNAVAILABLE')
    sites=SourceSites(Path(__file__).resolve().parents[1],'a'*40)
    with pytest.raises(p.PipeRefused) as caught:p._need(False)
    assert detail(caught.value,'PipeRefused',sites)['source_sites']['status']=='MATCHED'
