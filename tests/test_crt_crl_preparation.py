"""Ordinary Linux ctypes protocol/negative cases; NOT native CRL acceptance."""
import ctypes as C
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json,subprocess,sys,time
from types import SimpleNamespace
import pytest
from scripts.windows_ci import crt_crl_preparation as prep
from scripts.windows_ci import crt_certificate_metadata as meta
from tests.test_crt_certificate_metadata import tlv,sequence,oid,name,ext,ALG


def certificates():
    def cert(subject,issuer,ski,aki,cdp=False):
        extensions=[ext('2.5.29.14',tlv(4,ski)),ext('2.5.29.35',sequence(tlv(128,aki)))]
        if cdp:extensions.append(ext('2.5.29.31',sequence(sequence(tlv(160,tlv(160,tlv(134,prep.CDP.encode())))))))
        return sequence(sequence(tlv(160,tlv(2,b'\x02')),tlv(2,b'\x01\x23'),ALG,name(issuer),
            sequence(tlv(23,b'250101000000Z'),tlv(23,b'290101000000Z')),name(subject),sequence(ALG,tlv(3,b'\0\x01')),tlv(163,sequence(*extensions))),ALG,tlv(3,b'\0synthetic-not-signed'))
    return cert('Synthetic leaf','Synthetic CA',b'\x11'*20,b'\x22'*20,True),cert('Synthetic CA','Synthetic root',b'\x22'*20,b'\x33'*20)


def stamp(value):
    v=int((value-datetime(1601,1,1,tzinfo=timezone.utc)).total_seconds()*10000000)
    return prep.FileTime(v&0xffffffff,v>>32)


def protocol(monkeypatch):
    leaf,issuer=certificates();monkeypatch.setattr(prep,'LEAF_SHA256',sha256(leaf).hexdigest());monkeypatch.setattr(prep,'ISSUER_SHA256',sha256(issuer).hexdigest())
    state=SimpleNamespace(refs=[],calls=[],verify=1,free_crl=1,throw_verify=False,throw_create=False,clock=time.monotonic(),info=prep.CRLInfo())
    def blob(data):
        buffer=C.create_string_buffer(data);state.refs.append(buffer);return prep.Blob(len(data),C.addressof(buffer))
    def exts(values):
        array=(prep.Extension*len(values))();state.refs.append(array)
        for i,(key,critical,data) in enumerate(values):
            ident=C.create_string_buffer(key.encode()+b'\0');state.refs.append(ident)
            array[i].oid=C.addressof(ident);array[i].critical=critical;array[i].value=blob(data)
        return C.addressof(array) if values else None,len(values)
    state.blob=blob;state.exts=exts
    issuer_node=meta.DER().root(issuer).children[0].children[5]
    state.info.version=1;state.info.issuer=blob(issuer_node.raw)
    now=datetime.now(timezone.utc);state.info.this_update=stamp(now-timedelta(hours=1));state.info.next_update=stamp(now+timedelta(days=1))
    state.info.extensions,state.info.extension_count=exts([('2.5.29.35',False,sequence(tlv(128,b'\x22'*20)))])
    def create_cert(encoding,data,size):
        state.calls.append('CREATE_CERT');assert encoding==1
        if state.throw_create:raise OSError('PRIVATE_NATIVE_ARGUMENT')
        value=prep.CertContext();value.der=C.cast(data,C.c_void_p).value;value.length=size;state.refs.append(value);return C.pointer(value)
    def create_crl(encoding,data,size):
        state.calls.append('CREATE_CRL');assert encoding==1
        value=prep.CRLContext();value.der=C.cast(data,C.c_void_p).value;value.length=size;value.info=C.addressof(state.info);state.refs.append(value);return C.pointer(value)
    def verify(*args):
        state.calls.append('VERIFY_SIGNATURE');assert args[:3]==(None,1,3) and args[4]==2 and args[6:]==(1,None)
        if state.throw_verify:raise OSError('PRIVATE_NATIVE_ARGUMENT')
        return state.verify
    def free_crl(context):state.calls.append('FREE_CRL');return state.free_crl
    def free_cert(context):state.calls.append('FREE_CERT');return 1
    functions=dict(CertCreateCertificateContext=create_cert,CertCreateCRLContext=create_crl,CryptVerifyCertificateSignatureEx=verify,CertFreeCRLContext=free_crl,CertFreeCertificateContext=free_cert)
    class Library:
        def __getattr__(self,name):assert name in functions;return functions[name]
    def loader(name,**kwargs):assert name=='crypt32.dll' and kwargs==dict(use_last_error=True,winmode=0x800);return Library()
    monkeypatch.setattr(C,'WinDLL',loader,raising=False);monkeypatch.setattr(prep,'os',SimpleNamespace(name='nt'))
    monkeypatch.setattr(prep,'time',SimpleNamespace(monotonic=lambda:state.clock))
    state.owner=prep.OwnedCRLValidator(float(state.clock+120),float(state.clock+135));state.leaf=leaf;state.issuer=issuer
    return state


def test_acquisition_refuses_before_any_dll_network_cache_or_writes_and_no_force_parameter(monkeypatch):
    monkeypatch.setattr(C,'WinDLL',lambda *a,**kw:pytest.fail('DLL before unsupported no-redirect gate'),raising=False)
    with pytest.raises(prep.PreparationRefused) as error:prep.prepare()
    assert error.value.reason=='CRYPTNET_NO_REDIRECT_GUARANTEE_UNAVAILABLE'
    p=prep.plan();assert p['fetch_seconds']==15 and p['max_bytes']==16*1024*1024 and p['job_seconds']==180
    assert not p['redirects_allowed'] and not p['authentication_allowed'] and not p['cache_writer_implemented']
    code='import sys;sys.path.insert(0,sys.argv[1]);from scripts.windows_ci.crt_crl_preparation import prepare,plan;print(plan());\ntry: prepare()\nexcept Exception as e: assert e.reason=="CRYPTNET_NO_REDIRECT_GUARANTEE_UNAVAILABLE"'
    r=subprocess.run([sys.executable,'-I','-B','-S','-c',code,str(__import__('pathlib').Path.cwd())],capture_output=True,text=True,timeout=10)
    assert r.returncode==0


def test_exact_endpoint_and_fixed_certificate_pins_checked_before_native_contexts(monkeypatch):
    s=protocol(monkeypatch)
    for url,leaf,issuer in [(prep.CDP+'?next=x',s.leaf,s.issuer),('https://www.microsoft.com/else',s.leaf,s.issuer),(prep.CDP,s.leaf+b'x',s.issuer),(prep.CDP,s.leaf,s.issuer+b'x')]:
        with pytest.raises(prep.PreparationRefused):s.owner.validate(leaf,issuer,b'public-test-crl',url)
        assert not s.calls
    s.owner.close()


def test_owned_contexts_from_copied_bytes_reverse_close_and_no_product_acceptance(monkeypatch):
    s=protocol(monkeypatch);result=s.owner.validate(s.leaf,s.issuer,b'public-test-crl')
    assert s.calls==['CREATE_CERT','CREATE_CRL','VERIFY_SIGNATURE','FREE_CRL','FREE_CERT']
    assert result['cleanup']=='OWNED_CONTEXTS_CLOSED' and result['policy']['leaf_listed'] is False
    assert not result['cache_written'] and not result['usable_product'] and result['native_acceptance']=='NOT_ACCEPTED'
    assert not s.owner.owned and not s.owner.buffers
    s.owner.close();assert s.calls.count('FREE_CERT')==1


@pytest.mark.parametrize('kind',['wrong_issuer','expired','future','delta','scope','freshest','unknown_critical','wrong_aki','bad_number','entry_overflow','extension_overflow','signature_false'])
def test_crl_counterexamples_refuse_and_close_known_owned_contexts(monkeypatch,kind):
    s=protocol(monkeypatch);info=s.info;values=[('2.5.29.35',False,sequence(tlv(128,b'\x22'*20)))]
    if kind=='wrong_issuer':info.issuer=s.blob(name('Foreign CA'))
    if kind=='expired':info.next_update=stamp(datetime.now(timezone.utc)-timedelta(minutes=1))
    if kind=='future':info.this_update=stamp(datetime.now(timezone.utc)+timedelta(hours=1))
    if kind=='delta':values.append(('2.5.29.27',True,tlv(2,b'\x01')))
    if kind=='scope':values.append(('2.5.29.28',True,sequence()))
    if kind=='freshest':values.append(('2.5.29.46',False,sequence()))
    if kind=='unknown_critical':values.append(('1.2.3.4',True,tlv(4,b'x')))
    if kind=='wrong_aki':values[0]=('2.5.29.35',False,sequence(tlv(128,b'\x99'*20)))
    if kind=='bad_number':values.append(('2.5.29.20',True,tlv(2,b'\xff')))
    if kind=='entry_overflow':info.count=1000001;info.entries=1
    info.extensions,info.extension_count=s.exts(values)
    if kind=='extension_overflow':info.extension_count=65;info.extensions=1
    if kind=='signature_false':s.verify=0
    with pytest.raises(prep.PreparationRefused) as caught:s.owner.validate(s.leaf,s.issuer,b'public-test-crl')
    assert caught.value.cleanup=='OWNED_CONTEXTS_CLOSED'
    assert s.calls[-2:]==['FREE_CRL','FREE_CERT'] and not s.owner.unknown


def test_revocation_serial_is_native_little_endian_and_observation_does_not_accept_leaf(monkeypatch):
    s=protocol(monkeypatch);entries=(prep.Entry*1)();s.refs.append(entries)
    entries[0].serial=s.blob(b'\x23\x01');entries[0].revoked=stamp(datetime.now(timezone.utc)-timedelta(days=1))
    entries[0].extensions,entries[0].count=s.exts([('2.5.29.21',False,tlv(10,b'\x01'))])
    s.info.entries=C.addressof(entries);s.info.count=1
    result=s.owner.validate(s.leaf,s.issuer,b'public-test-crl');policy=result['policy']
    assert policy['leaf_listed'] and policy['leaf_entry']['reason_code']==1
    assert policy['revocation_acceptance']=='NOT_DECIDED_REQUIRES_FRESH_ORIGINAL_CACHE_ONLY_VERIFIER'


def test_primary_signature_failure_not_hidden_by_free_failure_and_no_unknown_retry(monkeypatch):
    s=protocol(monkeypatch);s.verify=0;s.free_crl=0;before=len(prep._retained_unknown)
    try:
        with pytest.raises(prep.PreparationRefused) as caught:s.owner.validate(s.leaf,s.issuer,b'public-test-crl')
        assert caught.value.reason=='CRL_SIGNATURE_REFUSED' and caught.value.cleanup=='UNKNOWN' and caught.value.cleanup_reason=='CONTEXT_FREE_REFUSED'
        assert s.calls==['CREATE_CERT','CREATE_CRL','VERIFY_SIGNATURE','FREE_CRL']
        assert len(s.owner.owned)==2 and s.owner.buffers and s.owner.unknown
        s.owner.close();assert s.calls.count('FREE_CRL')==1
        assert len(prep._retained_unknown)==before+1
    finally:del prep._retained_unknown[before:]


@pytest.mark.parametrize('stage',['throw_create','throw_verify'])
def test_native_exception_retains_original_arguments_and_contexts_without_secret_output(monkeypatch,stage):
    s=protocol(monkeypatch);setattr(s,stage,True);before=len(prep._retained_unknown)
    try:
        with pytest.raises(prep.PreparationRefused) as caught:s.owner.validate(s.leaf,s.issuer,b'public-test-crl')
        assert caught.value.reason=='NATIVE_OUTCOME_UNKNOWN' and caught.value.cleanup=='UNKNOWN_RETAINED'
        assert s.owner.pending is not None and s.owner.buffers and s.owner.unknown
        assert not any(x.startswith('FREE') for x in s.calls)
        assert 'PRIVATE_NATIVE_ARGUMENT' not in str(caught.value)
    finally:del prep._retained_unknown[before:]


def test_original_work_deadline_expires_then_known_contexts_close_without_renewal(monkeypatch):
    s=protocol(monkeypatch);original=s.owner.verify;end=s.owner.deadline
    def completed(*args):
        result=original(*args);s.clock=end+1;return result
    s.owner.verify=completed
    with pytest.raises(prep.PreparationRefused) as caught:s.owner.validate(s.leaf,s.issuer,b'public-test-crl')
    assert caught.value.reason=='WORK_DEADLINE' and caught.value.cleanup=='OWNED_CONTEXTS_CLOSED'
    assert s.owner.deadline==end and s.calls[-2:]==['FREE_CRL','FREE_CERT']


def test_cleanup_deadline_refuses_before_free_and_keeps_primary_failure(monkeypatch):
    s=protocol(monkeypatch);s.verify=0;original=s.owner.verify;before=len(prep._retained_unknown)
    def completed(*args):
        result=original(*args);s.clock=s.owner.cleanup_end+1;return result
    s.owner.verify=completed
    try:
        with pytest.raises(prep.PreparationRefused) as caught:s.owner.validate(s.leaf,s.issuer,b'public-test-crl')
        assert caught.value.reason=='CRL_SIGNATURE_REFUSED' and caught.value.cleanup=='UNKNOWN' and caught.value.cleanup_reason=='CLEANUP_DEADLINE'
        assert s.owner.unknown and len(s.owner.owned)==2 and not any(x.startswith('FREE') for x in s.calls)
    finally:del prep._retained_unknown[before:]


@pytest.mark.parametrize('invalid',['indirect','critical','duplicate_leaf','bad_remove_reason'])
def test_entry_applicability_and_duplicate_leaf_are_not_silently_accepted(monkeypatch,invalid):
    s=protocol(monkeypatch);entries=(prep.Entry*2)();s.refs.append(entries)
    for entry in entries:
        entry.serial=s.blob(b'\x23\x01');entry.revoked=stamp(datetime.now(timezone.utc)-timedelta(days=1))
    values=[]
    if invalid=='indirect':values=[('2.5.29.29',True,sequence())]
    if invalid=='critical':values=[('1.2.3.4',True,tlv(4,b'x'))]
    if invalid=='bad_remove_reason':values=[('2.5.29.21',False,tlv(10,b'\x08'))]
    entries[0].extensions,entries[0].count=s.exts(values);s.info.entries=C.addressof(entries);s.info.count=2 if invalid=='duplicate_leaf' else 1
    with pytest.raises(prep.PreparationRefused) as caught:s.owner.validate(s.leaf,s.issuer,b'public-test-crl')
    assert caught.value.cleanup=='OWNED_CONTEXTS_CLOSED'
    assert s.calls[-2:]==['FREE_CRL','FREE_CERT']


@pytest.mark.parametrize('stage',['before_validate','during_entries','during_cleanup'])
def test_expiry_uses_current_wall_clock_at_check_scan_end_and_return(monkeypatch,stage):
    s=protocol(monkeypatch);now=datetime.now(timezone.utc);clock=[now]
    s.info.this_update=stamp(now-timedelta(minutes=1));s.info.next_update=stamp(now+timedelta(seconds=1))
    class ClockDate(datetime):
        @classmethod
        def now(cls,tz=None):return clock[0]
    monkeypatch.setattr(prep,'datetime',ClockDate)
    if stage=='before_validate':clock[0]=now+timedelta(seconds=2)
    if stage=='during_entries':
        entries=(prep.Entry*1)();s.refs.append(entries);entries[0].serial=s.blob(b'\x02');s.info.entries=C.addressof(entries);s.info.count=1
        original=s.owner.extensions
        def extensions(pointer,count):
            result=original(pointer,count)
            if count==0:clock[0]=now+timedelta(seconds=2)
            return result
        s.owner.extensions=extensions
    if stage=='during_cleanup':
        free=s.owner.free_cert
        def free_cert(pointer):
            result=free(pointer);clock[0]=now+timedelta(seconds=2);return result
        s.owner.free_cert=free_cert
    with pytest.raises(prep.PreparationRefused) as caught:s.owner.validate(s.leaf,s.issuer,b'public-test-crl')
    assert caught.value.reason=='CRL_TIME_NOT_CURRENT' and caught.value.cleanup=='OWNED_CONTEXTS_CLOSED'
    assert s.calls[-2:]==['FREE_CRL','FREE_CERT']
