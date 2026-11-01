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


@pytest.mark.parametrize('change,stage',[
    (None,None),('state','PROVIDER_STATE'),('provider','PROVIDER_DATA'),('signer','SIGNER_DATA'),
    ('signer_size','SIGNER_LAYOUT'),('signer_error','SIGNER_POLICY'),('signer_type','SIGNER_POLICY'),
    ('short_chain','SIGNER_POLICY'),('long_chain','SIGNER_POLICY'),('certificate','CERTIFICATE_DATA'),
    ('certificate_size','CERTIFICATE_LAYOUT'),('test','CERTIFICATE_POLICY'),('cyclic','CERTIFICATE_POLICY'),
    ('error','CERTIFICATE_POLICY'),('revoked','CERTIFICATE_POLICY'),('der','CERTIFICATE_DER'),
    ('der_length','CERTIFICATE_DER'),
])
def test_strict_chain_counterexamples_and_original_call_contract(monkeypatch,change,stage):
    """Synthetic provider graph; no certificate is accepted on an actual OS."""
    import uuid
    v,calls=value();original=v.wvt
    def wvt(hwnd,action,data):
        row=C.cast(data,C.POINTER(crt.TrustData)).contents
        assert hwnd.value==C.c_void_p(-1).value
        assert C.string_at(action,16)==uuid.UUID('00aac56b-cd44-11d0-8cc2-00c04fc295ee').bytes_le
        assert (row.ui,row.revocation,row.choice,row.flags)==(2,1,1,0x80|0x1000|0x2000)
        assert row.file.contents.file==41
        status=original(hwnd,action,data)
        if change=='state':row.state=None
        return status
    v.wvt=wvt;v.provider=lambda state:None if change=='provider' else 19
    signer=crt.Signer();signer.size=C.sizeof(signer);signer.count=2
    if change=='signer_size':signer.size=0
    if change=='signer_error':signer.error=1
    if change=='signer_type':signer.type=0x10
    if change=='short_chain':signer.count=1
    if change=='long_chain':signer.count=9
    v.signer=lambda *args:None if change=='signer' else C.pointer(signer)
    encoded=C.create_string_buffer(b'SYNTHETIC_ROOT_NOT_A_REAL_CERTIFICATE')
    # Only this controlled graph's trust oracle is substituted, never production
    # root/publisher/flags. The unchanged real pin is tested separately above.
    monkeypatch.setattr(crt,'ROOT_SHA256',sha256(encoded.raw).hexdigest())
    context=crt.CertContext();context.der=C.cast(encoded,crt.P);context.length=len(encoded)
    certificate=crt.ProviderCert();certificate.size=C.sizeof(certificate);certificate.cert=C.pointer(context)
    if change=='certificate_size':certificate.size=0
    if change in ('test','cyclic','error','revoked'):setattr(certificate,change,1)
    if change=='der':context.der=None
    if change=='der_length':context.length=65537
    v.cert=lambda *args:None if change=='certificate' else C.pointer(certificate)
    def name(cert,kind,flags,oid,buffer,length):
        assert kind==3 and flags==0 and oid.value==b'2.5.4.10' and length==256
        buffer.value='Microsoft Corporation';return len(buffer.value)+1
    v.cert_name=name
    if stage is None:
        assert v._signature(41,'C:/synthetic.dll')==(crt.ROOT_SHA256,crt.ROOT_SHA256)
    else:
        with pytest.raises(crt.CRTTrustFailure) as caught:v._signature(41,'C:/synthetic.dll')
        assert caught.value.stage==stage and caught.value.verify_ok and caught.value.close_outcome=='RETURNED_SUCCESS'
    assert calls==[1,2] and not v.unknown


@pytest.mark.parametrize('expires_at',['info','security','descriptor','final_path','seek','read','eof','modules','module_path'])
def test_original_crt_end_prevents_following_queries_or_expired_result(monkeypatch,expires_at):
    v,_=value();clock=[1000.];v.deadline=1001.;calls=[]
    monkeypatch.setattr(crt,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    monkeypatch.setattr(authority,'budget',lambda resource,deadline=None,**kw:deadline)
    def query(name,result):
        calls.append(name)
        if name==expires_at:clock[0]=1002.
        return result
    info=SimpleNamespace(attributes=crt.DIRECTORY,identity=1)
    v.api=SimpleNamespace(info=lambda h:query('info',info),security=lambda h:query('security',None),
        descriptor=lambda h:query('descriptor',b'CONTROLLED'),final_path=lambda h:query('final_path','CONTROLLED'),need=crt.need)
    if expires_at in ('info','security','descriptor','final_path'):
        monkeypatch.setattr(crt,'os_security',lambda *args,**kw:None)
        operation=lambda:v._identity(41,True)
        expected=['info','security','descriptor','final_path']
    elif expires_at in ('seek','read','eof'):
        v.seek=lambda *args:query('seek',1);reads=[]
        def read(*args):
            name='read' if not reads else 'eof';reads.append(name)
            return query(name,b'x' if name=='read' else b'')
        v.api.read=read;operation=lambda:v._read(41,1);expected=['seek','read','eof']
    else:
        v._architecture=lambda *args:None;v.path=r'C:\Windows\System32'
        def modules(process,buffer,size,count,flags):
            buffer[0]=1;count._obj.value=C.sizeof(crt.P);return query('modules',1)
        def path(process,module,buffer,size):
            buffer.value=v.path+r'\vcruntime140.dll';return query('module_path',len(buffer.value))
        v.modules=modules;v.module_path=path;operation=lambda:v._loaded(41);expected=['modules','module_path']
    with pytest.raises(crt.CRTRefused):operation()
    assert calls==expected[:expected.index(expires_at)+1] and v.deadline==1001.
