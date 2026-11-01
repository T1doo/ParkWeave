"""Borrowed in-process ctypes graph only; not Windows/provider evidence."""
import ctypes as C
import json
from types import SimpleNamespace
import pytest
from scripts.windows_ci import crt_state_snapshot as snapshot
from scripts.windows_portable import authenticode_signature as trust


def graph():
    request=trust.TrustData();request.action=1;request.state=17;request.flags=0x3080;request.revocation=1
    owner=SimpleNamespace(_signature_budget=lambda *args:None)
    reader=snapshot.StateSnapshot(owner);reader.activate(request,0)
    signer=trust.Signer();signer.size=C.sizeof(signer);signer.count=2;signer.time_low=123
    certs=(trust.ProviderCert*2)();contexts=[trust.CertContext(),trust.CertContext()]
    elements=[snapshot.ChainElement(),snapshot.ChainElement()]
    revocation=snapshot.RevocationInfo();revocation.size=C.sizeof(revocation);revocation.result=0x40;revocation.freshness=999
    for i in range(2):
        certs[i].size=C.sizeof(trust.ProviderCert);certs[i].cert=C.pointer(contexts[i]);certs[i].element=C.addressof(elements[i])
        elements[i].size=C.sizeof(snapshot.ChainElement);elements[i].cert=C.addressof(contexts[i])
    elements[0].status.error=0x1000040;elements[0].revocation=C.addressof(revocation)
    certs[0].revoked=0x80092013;signer.certs=C.addressof(certs)
    chain=snapshot.ChainContextPrefix();chain.size=C.sizeof(chain)+16;chain.count=1;chain.status.error=0x1000040;chain.freshness=888
    signer.chain=C.addressof(chain)
    errors=(snapshot.D*38)()
    provider=snapshot.ProviderPrefix();provider.size=C.sizeof(provider)+16;provider.request=C.addressof(request)
    provider.signer_count=1;provider.signers=C.addressof(signer);provider.policy=0x23c00;provider.flags=0x80080000
    provider.step_count=38;provider.steps=C.addressof(errors)
    # Keep the original fixture graph alive; observer must not free or adopt it.
    return SimpleNamespace(reader=reader,request=request,owner=owner,signer=signer,certs=certs,contexts=contexts,
        elements=elements,revocation=revocation,chain=chain,errors=errors,provider=provider)


def capture(g):
    g.reader.capture_provider(C.addressof(g.provider),17)
    g.reader.capture_signer(C.pointer(g.signer))
    return g.reader.export()


def test_same_state_provider_policy_chain_unknown_and_absent_freshness_are_distinct():
    g=graph();data=capture(g)
    assert data['provider']['status']=='READ_ORIGINAL_STATE' and data['provider']['request_bound']
    assert data['provider']['request_flags_wtd']=='00003080' and data['provider']['provider_flags_cpd']=='80080000'
    assert 'CPD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT' in data['provider']['provider_flag_names']
    assert 'WTPF_OFFLINEOKNBU_COM' in data['provider']['registry_policy_names']
    assert len(data['provider']['trust_step_errors'])==38
    chain=data['signer_chain'];assert chain['verify_as_of_filetime']==123
    assert chain['chain_context']['trust']['error']=='01000040'
    assert chain['chain_context']['freshness_seconds'] is None
    leaf=chain['certificates'][0]['element']['revocation']
    assert leaf['result_dword']=='00000040' and leaf['freshness_seconds'] is None
    assert leaf['crl']['status']=='NOT_AVAILABLE'
    assert chain['certificates'][1]['element']['revocation']['status']=='NOT_AVAILABLE'
    g.reader.deactivate()
    with pytest.raises(ValueError):g.reader.read(C.addressof(g.provider),snapshot.ProviderPrefix)
    # Numeric copies survive CLOSE; no borrowed pointer is consulted by export.
    assert g.reader.export()==data and 'pointer' not in json.dumps(data)


def test_observed_crl_dates_are_not_cache_acceptance_and_optional_delta_is_not_assumed():
    g=graph();times=snapshot.CRLTimes();times.version=1;times.this_update.low=100;times.next_update.low=200
    context=snapshot.CRLContext();context.info=C.addressof(times);context.length=128
    crl=snapshot.RevocationCRL();crl.size=C.sizeof(crl);crl.base=C.addressof(context)
    g.revocation.crl=C.addressof(crl);g.revocation.has_freshness=1;g.revocation.freshness=10
    data=capture(g)['signer_chain']['certificates'][0]['element']['revocation']
    assert data['freshness_seconds']==10
    assert data['crl']['base']==dict(status='OBSERVED_TIME_FIELDS_ONLY',this_update_filetime=100,next_update_filetime=200,validity_decision='NOT_EVALUATED')
    assert data['crl']['delta']['status']=='NOT_AVAILABLE'


@pytest.mark.parametrize('change',['wrong_request','wrong_state','step_overflow','small_provider','wrong_signer','wrong_element_cert','deadline'])
def test_binding_size_count_and_deadline_refusal_before_unbounded_or_foreign_reads(change):
    g=graph()
    if change=='wrong_request':g.provider.request=1
    if change=='step_overflow':g.provider.step_count=65;g.provider.steps=1
    if change=='small_provider':g.provider.size=4
    if change=='deadline':g.owner._signature_budget=lambda *a:(_ for _ in ()).throw(RuntimeError('PRIVATE_CONTEXT_ARGUMENT'))
    g.reader.capture_provider(C.addressof(g.provider),18 if change=='wrong_state' else 17)
    if change in ('wrong_request','wrong_state','step_overflow','small_provider','deadline'):
        assert g.reader.export()['provider']['status']=='UNAVAILABLE_BOUNDS_BINDING_OR_DEADLINE'
    else:
        if change=='wrong_signer':g.reader.provider_signer=1
        if change=='wrong_element_cert':g.elements[0].cert=1;g.elements[0].revocation=1
        g.reader.capture_signer(C.pointer(g.signer))
        assert g.reader.export()['signer_chain']['status']=='UNAVAILABLE_BOUNDS_BINDING_OR_DEADLINE'
    assert 'PRIVATE_CONTEXT_ARGUMENT' not in json.dumps(g.reader.export())


def test_snapshots_do_not_swallow_original_native_helper_exceptions(monkeypatch):
    from scripts.windows_ci.crt_signature_readonly import ReadOnlySignature
    value=object.__new__(ReadOnlySignature);called=[]
    def failed(*args):raise C.ArgumentError('PRIVATE_NATIVE_ARGUMENT')
    value.native_provider=failed;value.native_signer=failed
    value.state_snapshot=SimpleNamespace(capture_provider=lambda *a:called.append('OBSERVED'),capture_signer=lambda *a:called.append('OBSERVED'))
    with pytest.raises(C.ArgumentError):value.provider(17)
    with pytest.raises(C.ArgumentError):value.signer(1,0,False,0)
    assert not called


def test_real_shared_verifier_observation_completes_before_close_without_extra_native_calls(monkeypatch):
    import time
    from tests.test_crt_signature_readonly import controlled_native
    from scripts.windows_ci import crt_signature_readonly as diagnostic
    g=graph();calls=controlled_native(monkeypatch);original_loader=C.WinDLL;native_calls=[]
    owner=None
    def wvt(hwnd,action,data):
        phase=data._obj.action;native_calls.append(('WVT',phase))
        if phase==1:
            data._obj.state=17;g.provider.request=C.addressof(data._obj)
        else:assert owner.state_snapshot.request is None
        return 0
    def provider(state):native_calls.append(('PROVIDER',state));return C.addressof(g.provider)
    def signer(*args):native_calls.append(('SIGNER',));return C.pointer(g.signer)
    def cert(original,index):native_calls.append(('CERT',index));return C.pointer(g.certs[index])
    replacements=dict(WinVerifyTrust=wvt,WTHelperProvDataFromStateData=provider,
        WTHelperGetProvSignerFromChain=signer,WTHelperGetProvCertFromChain=cert)
    class Library:
        def __init__(self,base):self.base=base
        def __getattr__(self,name):return replacements[name] if name in replacements else getattr(self.base,name)
    monkeypatch.setattr(C,'WinDLL',lambda *a,**kw:Library(original_loader(*a,**kw)))
    owner=diagnostic.ReadOnlySignature(time.monotonic()+80,time.monotonic()+90)
    result=owner.inspect('msvcp140.dll');owner.close()
    assert result['stage']=='CERTIFICATE_POLICY' and not result['execution_uncertain']
    assert result['state_snapshot']['provider']['registry_policy_flags']=='00023c00'
    assert len(result['state_snapshot']['signer_chain']['certificates'])==2
    assert native_calls==[('WVT',1),('PROVIDER',17),('SIGNER',),('CERT',0),('WVT',2)]
    assert owner.state_snapshot.request is None and owner.state_snapshot.export()==result['state_snapshot']
    assert calls[-1]==('FILE_CLOSE',41) and not owner.unknown


def test_no_snapshot_native_api_network_cache_or_free_call_surface():
    # This observer has only memory copies. Native calls remain in the original
    # diagnostic's fixed read-only export set and shared production verifier.
    from pathlib import Path
    text=Path(snapshot.__file__).read_text()
    assert not any(token in text for token in ('WinDLL(', 'CDLL(', 'CryptRetrieveObjectByUrl(', 'CertGetCertificateChain(', 'CertFree', '.free(', 'urllib', 'requests.'))
