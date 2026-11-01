"""Controlled ctypes/clock protocol only; NOT Windows signature acceptance."""
import ctypes as C
from hashlib import sha256
import json,time
from types import SimpleNamespace
import pytest

from scripts.windows_portable import native_system_crt as crt,native_trial_authority as authority
from scripts.windows_portable.controller import ControlFailure
from scripts.windows_ci import native_business_entry as entry,native_failure_diagnostics as diagnostics

PRIVATE='PRIVATE_CERT_PATH_OR_EXCEPTION_DO_NOT_PRINT'


def value():
    v=object.__new__(crt.NativeSystemCRT);v.failed=v.closed=False;v.unknown=[]
    v.deadline=time.monotonic()+30;v.lease=object();v._trust_image='msvcp140.dll'
    calls=[]
    def wvt(hwnd,action,data):
        row=C.cast(data,C.POINTER(crt.TrustData)).contents;calls.append(row.action)
        if row.action==1:row.state=17
        return 0
    v.wvt=wvt;return v,calls


def report(error):return entry._failure_diagnostic(ControlFailure('ACQUIRE',error,[]))


def test_verify_ffi_exception_and_original_cause_are_not_misreported_as_verified():
    v,calls=value();original=v.wvt
    def wvt(hwnd,action,data):
        row=C.cast(data,C.POINTER(crt.TrustData)).contents
        if row.action==1:calls.append(1);raise C.ArgumentError(PRIVATE)
        return original(hwnd,action,data)
    v.wvt=wvt
    with pytest.raises(crt.CRTTrustFailure) as caught:v._signature(41,'C:/'+PRIVATE)
    e=caught.value
    assert (e.stage,e.activity,e.verify_returned,e.verify_ok,e.close_outcome)==('VERIFY','CALL',False,None,'RETURNED_SUCCESS')
    assert type(e.__cause__) is C.ArgumentError and calls==[1,2] and not v.unknown
    data=report(e);facts=next(row['crt_signature'] for row in data['exception_details'] if 'crt_signature' in row)
    assert facts['verify_returned_zero'] is None and facts['wvt_close']=='RETURNED_SUCCESS'
    assert any(row['type']=='CTYPES_ARGUMENT_ERROR' for row in data['exception_details'])
    assert PRIVATE not in json.dumps(data) and data['control']['outcome']=='UNKNOWN'


def test_provider_exception_is_distinct_after_known_zero_and_clean_close():
    v,calls=value()
    def provider(*args):raise TypeError(PRIVATE)
    v.provider=provider
    with pytest.raises(crt.CRTTrustFailure) as caught:v._signature(41,'C:/'+PRIVATE)
    e=caught.value
    assert e.stage=='PROVIDER_DATA' and e.activity=='CALL' and e.verify_returned and e.verify_ok
    assert type(e.__cause__) is TypeError and calls==[1,2]
    assert PRIVATE not in json.dumps(report(e))


def test_verify_consuming_work_deadline_cannot_start_provider_but_closes_with_original_cleanup(monkeypatch):
    v,calls=value();clock=[1000.];v.deadline=1001.
    monkeypatch.setattr(crt,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    observed=[]
    def budget(resource,deadline=None,*,cleanup=False):
        assert resource is v.lease;observed.append((deadline,cleanup))
        if cleanup:assert clock[0]<1010;return 1010.
        return deadline
    monkeypatch.setattr(authority,'budget',budget)
    def wvt(hwnd,action,data):
        row=C.cast(data,C.POINTER(crt.TrustData)).contents;calls.append(row.action)
        if row.action==1:row.state=17;clock[0]=1002.
        return 0
    v.wvt=wvt;v.provider=lambda state:pytest.fail('provider called after original work deadline')
    with pytest.raises(crt.CRTTrustFailure) as caught:v._signature(41,r'C:\synthetic.dll')
    e=caught.value
    assert (e.stage,e.activity,e.close_outcome)==('PROVIDER_DATA','WORK_BUDGET','RETURNED_SUCCESS')
    assert e.verify_returned and e.verify_ok and calls==[1,2]
    assert observed==[(1001.,False),(None,True)] and v.deadline==1001.


def test_expired_cleanup_never_calls_close_or_allows_catalog_fallback(monkeypatch):
    v,calls=value()
    def budget(resource,deadline=None,*,cleanup=False):
        if cleanup:raise authority.TrialRefused(PRIVATE)
        return deadline
    monkeypatch.setattr(authority,'budget',budget)
    def no_signature(hwnd,action,data):calls.append(C.cast(data,C.POINTER(crt.TrustData)).contents.action);return -2146762496
    v.wvt=no_signature
    with pytest.raises(crt.CRTTrustFailure) as caught:v._signature(41,'C:/'+PRIVATE)
    e=caught.value
    assert e.stage=='CLOSE' and e.activity=='CLEANUP_BUDGET' and e.close_outcome=='UNKNOWN'
    assert e.verify_returned and e.verify_ok is False and calls==[1] and v.unknown and v.failed
    assert type(e) is not crt.SignatureRejected and isinstance(e.__cause__,BaseExceptionGroup)
    assert PRIVATE not in json.dumps(report(e))


@pytest.mark.parametrize('failure',['PUBLISHER_VALUE','ROOT_PIN'])
def test_zero_wintrust_does_not_relax_original_publisher_or_root_policy(failure):
    v,calls=value();v.provider=lambda state:19
    signer=crt.Signer();signer.size=C.sizeof(signer);signer.count=2
    v.signer=lambda *args:C.pointer(signer)
    raw=C.create_string_buffer(b'synthetic untrusted certificate')
    context=crt.CertContext();context.der=C.cast(raw,crt.P);context.length=len(raw)
    certificate=crt.ProviderCert();certificate.size=C.sizeof(certificate);certificate.cert=C.pointer(context)
    v.cert=lambda *args:C.pointer(certificate)
    def name(cert,kind,flags,oid,buffer,length):
        buffer.value=PRIVATE if failure=='PUBLISHER_VALUE' else 'Microsoft Corporation';return len(buffer.value)+1
    v.cert_name=name
    with pytest.raises(crt.CRTTrustFailure) as caught:v._signature(41,'C:/'+PRIVATE)
    assert caught.value.stage==failure and caught.value.verify_ok and calls==[1,2] and not v.unknown
    assert PRIVATE not in json.dumps(report(caught.value))


def test_renderer_only_outputs_known_exact_class_finite_fields_and_fixed_image_names():
    e=crt.CRTTrustFailure('ROOT_PIN','CHECK',True,True,'RETURNED_SUCCESS','vcruntime140.dll')
    good=diagnostics.detail(e,entry._error_type(e));assert good['crt_signature']['image_name']=='vcruntime140.dll'
    e.image_name=PRIVATE;e.args=(PRIVATE,)
    assert 'image_name' not in diagnostics.detail(e,entry._error_type(e))['crt_signature']
    e.stage=PRIVATE
    assert diagnostics.detail(e,entry._error_type(e))['crt_signature']==dict(details='UNAVAILABLE')
    fake=type('CRTTrustFailure',(RuntimeError,),{})(PRIVATE)
    assert entry._error_type(fake)=='UNLISTED_EXCEPTION'
    assert PRIVATE not in json.dumps([good,diagnostics.detail(e,entry._error_type(e)),diagnostics.detail(fake,entry._error_type(fake))])


def test_image_name_is_per_call_and_never_stale_across_other_system_images():
    v,calls=value()
    def provider(*args):raise TypeError(PRIVATE)
    v.provider=provider
    with pytest.raises(crt.CRTTrustFailure) as first:
        v._signature(41,'C:/System32/msvcp140.dll',image_name='msvcp140.dll')
    assert first.value.image_name=='msvcp140.dll'
    # Legacy/stale instance data is irrelevant to a later mapped-image call.
    v._trust_image='vcruntime140.dll'
    with pytest.raises(crt.CRTTrustFailure) as other:v._signature(42,'C:/System32/kernel32.dll')
    assert other.value.image_name is None
    assert 'image_name' not in diagnostics.detail(other.value,entry._error_type(other.value))['crt_signature']
    assert calls==[1,2,1,2]
