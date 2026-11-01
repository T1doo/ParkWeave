"""Offline ABI/failure protocols only; never Cryptnet, URL cache or Windows."""
import ctypes as C
from hashlib import sha256
from types import SimpleNamespace
import time
import pytest
from scripts.windows_ci import crt_cryptnet_cache_trial as n,crt_crl_preparation as prep
from tests.test_crt_crl_preparation import protocol
from tests.test_crt_memory_revocation import source


def setup(monkeypatch):
    original=source(monkeypatch);s=protocol(monkeypatch)
    monkeypatch.setattr(prep,'LEAF_SHA256',sha256(original.state_snapshot.der[0]).hexdigest())
    monkeypatch.setattr(prep,'ISSUER_SHA256',sha256(original.state_snapshot.der[1]).hexdigest())
    monkeypatch.setattr(C,'get_last_error',lambda:5,raising=False)
    loader=C.WinDLL;s.mode='good';s.get_count=0
    def get(url,oid,flags,timeout,output,asynch,credentials,verify,auxiliary):
        s.calls.append('NATIVE_GET');s.get_count+=1
        assert url.value==prep.CDP and oid.value==2 and flags==0x20024 and 0<timeout<=15000
        assert asynch is credentials is None and not output._obj.value
        issuer=C.cast(verify,C.POINTER(prep.CertContext)).contents
        assert C.string_at(issuer.der,issuer.length)==original.state_snapshot.der[1]
        aux=auxiliary._obj
        assert aux.size==C.sizeof(aux) and aux.max_bytes==16*1024*1024 and aux.last_sync
        assert not any((aux.prefetch,aux.flush,aux.response,aux.prefix,aux.resync,aux.error_headers,aux.error_content))
        if s.mode not in ('false','null'):
            raw=C.create_string_buffer(b'SYNTHETIC_CRL');context=prep.CRLContext()
            context.der=C.addressof(raw);context.length=13;context.info=C.addressof(s.info)
            s.refs.extend([raw,context]);output._obj.value=C.addressof(context)
        if s.mode=='unknown':raise OSError('PRIVATE_NATIVE_ARGUMENT')
        if s.mode=='false':aux.http_status=401
        return s.mode!='false' and s.mode!='false_with_output'
    def load(name,**kw):
        if name=='cryptnet.dll':
            assert kw==dict(use_last_error=True,winmode=0x800)
            return SimpleNamespace(CryptRetrieveObjectByUrlW=get)
        return loader(name,**kw)
    monkeypatch.setattr(C,'WinDLL',load,raising=False)
    s.value=n.NativeCachedCRL(float(s.clock+120),float(s.clock+135))
    return original.state_snapshot,s


def test_default_entry_is_plan_only_before_dll_cache_or_network(monkeypatch,capsys):
    monkeypatch.setattr(C,'WinDLL',lambda *a,**kw:pytest.fail('native call in plan'),raising=False)
    assert n.main([])==2 and 'NOT_ENABLED' in capsys.readouterr().out
    with pytest.raises(prep.PreparationRefused):n.main(['--inspect-native-cache-once'])


def test_real_api_argument_protocol_signature_and_applicability_then_known_cleanup(monkeypatch):
    original,s=setup(monkeypatch);result=s.value.acquire(original)
    assert s.get_count==1 and s.calls==['CREATE_CERT','NATIVE_GET','VERIFY_SIGNATURE','FREE_CRL','FREE_CERT']
    assert result['bytes']==13 and result['redirects']=='NATIVE_OPAQUE_MAY_FOLLOW'
    assert result['cleanup']=='OWNED_CONTEXTS_CLOSED' and result['final_url']=='NOT_OBSERVED'
    assert result['cache_effect']=='MAY_HAVE_WRITTEN_TEMPORARY_ACCOUNT_CRYPTNET_CACHE'
    assert result['policy']['leaf_listed'] is False


@pytest.mark.parametrize('mode',['false','null','false_with_output','unknown'])
def test_retrieval_failure_never_retries_or_claims_cache_rollback(monkeypatch,mode):
    original,s=setup(monkeypatch);s.mode=mode;start=len(prep._retained_unknown)
    try:
        with pytest.raises(prep.PreparationRefused) as caught:s.value.acquire(original)
        error=caught.value
        assert s.get_count==1 and error.retrieval_started
        assert error.native_returned is (mode!='unknown')
        assert not any(x=='VERIFY_SIGNATURE' for x in s.calls)
        if mode in ('unknown','false_with_output'):
            assert error.cleanup=='UNKNOWN_RETAINED' and s.value.buffers and s.value.unknown
            assert not any(x in ('FREE_CERT','FREE_CRL') for x in s.calls)
        else:assert error.cleanup=='OWNED_CONTEXTS_CLOSED' and s.calls[-1]=='FREE_CERT'
        if mode=='false':assert error.native_error=='00000005' and error.native_http_status==401
    finally:del prep._retained_unknown[start:]


def test_bad_signature_after_native_return_still_records_possible_cache_write(monkeypatch):
    original,s=setup(monkeypatch);s.verify=0
    with pytest.raises(prep.PreparationRefused) as caught:s.value.acquire(original)
    assert caught.value.reason=='CRL_SIGNATURE_REFUSED' and caught.value.retrieval_started and caught.value.native_returned
    assert caught.value.cleanup=='OWNED_CONTEXTS_CLOSED' and s.calls[-2:]==['FREE_CRL','FREE_CERT']


@pytest.mark.parametrize('mode',['good','false','false_with_output'])
def test_error_diagnostic_seam_cannot_lose_an_unregistered_output(monkeypatch,mode):
    original,s=setup(monkeypatch);s.mode=mode;start=len(prep._retained_unknown)
    def broken_error():raise RuntimeError('PRIVATE_DIAGNOSTIC_ARGUMENT')
    monkeypatch.setattr(C,'get_last_error',broken_error)
    try:
        if mode=='good':
            assert s.value.acquire(original)['cleanup']=='OWNED_CONTEXTS_CLOSED'
            assert s.calls[-2:]==['FREE_CRL','FREE_CERT']
        else:
            with pytest.raises(prep.PreparationRefused) as caught:s.value.acquire(original)
            if mode=='false_with_output':
                assert caught.value.cleanup=='UNKNOWN_RETAINED' and 'FREE_CERT' not in s.calls
            else:assert caught.value.cleanup=='OWNED_CONTEXTS_CLOSED' and s.calls[-1]=='FREE_CERT'
    finally:del prep._retained_unknown[start:]


def coordinator(monkeypatch,*,after_good=True,changed=False,cache_error=None,all_good=False):
    state=SimpleNamespace(probes=[],fetches=0)
    monkeypatch.setattr(n,'CERT_PINS',tuple(sha256(x).hexdigest() for x in (b'leaf',b'issuer',b'root')))
    class Probe:
        def __init__(self,*args):
            self.index=len(state.probes);state.probes.append(self)
            self.initial_identity=('ID',self.index%2)
            self.state_snapshot=SimpleNamespace(der=(b'leaf',b'issuer',b'root'),owner=self)
        def inspect(self,name):
            good=all_good or self.index>=2 and after_good
            self.result=dict(file=name,sha256=n.FILE_PINS[name],metadata_after='UNCHANGED',
                chain_sha256=list(n.CERT_PINS) if good else None,
                verification='STRICT_SHARED_SIGNATURE_CHECK_PASSED' if good else 'REFUSED_OR_UNKNOWN')
            if changed and self.index==2:self.initial_identity=('FOREIGN',)
            return self.result
        def close(self):return 'OWNED_FILE_HANDLES_CLOSED'
    class Retriever:
        def __init__(self,*args):self.started=self.native_returned=False
        def acquire(self,original):
            state.fetches+=1;self.started=True
            if cache_error:
                self.native_returned=cache_error!='UNKNOWN';raise prep.PreparationRefused(cache_error)
            self.native_returned=True;return dict(cache_effect='MAY_HAVE_WRITTEN_TEMPORARY_ACCOUNT_CRYPTNET_CACHE')
    monkeypatch.setattr(n,'MemoryFileProbe',Probe);monkeypatch.setattr(n,'NativeCachedCRL',Retriever)
    monkeypatch.setattr(n,'original_constraints',lambda x:x.state_snapshot)
    return state


def test_coordinator_success_requires_fresh_original_strict_and_keeps_before_failure(monkeypatch):
    s=coordinator(monkeypatch);row,code=n.collect_once()
    assert code==0 and s.fetches==1 and len(s.probes)==4 and row['failure'] is None
    assert all(x['verification']=='REFUSED_OR_UNKNOWN' for x in row['before'])
    assert all(x['verification']=='STRICT_SHARED_SIGNATURE_CHECK_PASSED' for x in row['after'])
    assert row['strict_implementation']=='UNCHANGED' and not row['usable_product']


@pytest.mark.parametrize('mode',['strict_still_offline','file_changed','cache_failure','cache_unknown'])
def test_coordinator_failure_is_never_retried_or_admitted(monkeypatch,mode):
    s=coordinator(monkeypatch,after_good=mode!='strict_still_offline',changed=mode=='file_changed',
        cache_error='UNKNOWN' if mode=='cache_unknown' else 'NATIVE_RETRIEVAL_REFUSED' if mode=='cache_failure' else None)
    row,code=n.collect_once()
    assert code==2 and s.fetches==1 and row['failure'] and row['native_cache_effect']=='MAY_HAVE_OCCURRED'
    assert not row['usable_product'] and len(row['original_file_cleanup'])==len(s.probes)


def test_already_strict_passed_does_not_needlessly_fetch_or_write_cache(monkeypatch):
    s=coordinator(monkeypatch,all_good=True);row,code=n.collect_once()
    assert code==0 and s.fetches==0 and row['native_cache_effect']=='NOT_REQUESTED'


def test_already_good_with_missing_core_selected_chain_never_accepts_empty_equals_empty(monkeypatch):
    s=coordinator(monkeypatch,all_good=True);old=n.MemoryFileProbe.inspect
    def inspect(probe,name):
        row=old(probe,name);row['chain_sha256']=[];probe.state_snapshot.der=();return row
    monkeypatch.setattr(n.MemoryFileProbe,'inspect',inspect)
    row,code=n.collect_once()
    assert code==2 and s.fetches==0 and row['failure']['reason']=='STRICT_SELECTED_CHAIN_UNAVAILABLE'
