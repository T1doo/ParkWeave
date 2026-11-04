"""Synthetic original-state/crypt32 ABI protocols; not real WinTrust evidence."""
import ctypes as C
from datetime import datetime,timedelta,timezone
from hashlib import sha256
from types import SimpleNamespace
import time
import pytest
from scripts.windows_ci import crt_memory_revocation as m,crt_crl_preparation as prep
from scripts.windows_ci import crt_state_snapshot as snap,crt_certificate_metadata as meta
from scripts.windows_portable import authenticode_signature as trust
from tests.test_crt_crl_preparation import certificates,stamp
from tests.test_crt_certificate_metadata import sequence,tlv,ALG,name,ext


def source(monkeypatch):
    leaf,issuer=certificates()
    issuer_node=meta.DER().root(issuer);tbs=issuer_node.children[0]
    extra=ext('2.5.29.31',sequence(sequence(tlv(160,tlv(160,tlv(134,m.CA_CDP.encode()))))))
    extensions=sequence(*(x.raw for x in tbs.children[-1].children[0].children),extra)
    issuer=sequence(sequence(*(x.raw for x in tbs.children[:-1]),tlv(163,extensions)),issuer_node.children[1].raw,issuer_node.children[2].raw)
    root=sequence(sequence(tlv(160,tlv(2,b'\x02')),tlv(2,b'\x01'),ALG,name('Synthetic root'),
        sequence(tlv(23,b'250101000000Z'),tlv(23,b'290101000000Z')),name('Synthetic root'),sequence(ALG,tlv(3,b'\0\x01')),
        tlv(163,sequence(ext('2.5.29.14',tlv(4,b'\x33'*20)),ext('2.5.29.35',sequence(tlv(128,b'\x33'*20)))))),ALG,tlv(3,b'\0not-signed'))
    der=(leaf,issuer,root);monkeypatch.setattr(m,'CERT_PINS',tuple(sha256(x).hexdigest() for x in der))
    monkeypatch.setattr(m,'FILE_PINS',{'msvcp140.dll':'a'*64})
    # Test-only pins/endpoints, never an admission or actual platform record.
    owner=object.__new__(m.MemoryFileProbe);owner.deadline=time.monotonic()+30;owner.failed=False;owner.unknown=[];owner.handles=[41]
    copy=m.OriginalCopies(owner);owner.state_snapshot=copy
    request=trust.TrustData();request.action=1;request.state=17;request.flags=0x3080;request.revocation=1;copy.activate(request,0)
    contexts=[trust.CertContext() for _ in range(3)];elements=[snap.ChainElement() for _ in range(3)]
    certs=(trust.ProviderCert*3)();buffers=[C.create_string_buffer(x) for x in der]
    revs=[snap.RevocationInfo() for _ in range(2)]
    base=snap.CRLContext();raw=C.create_string_buffer(b'CA_CRL');base.der=C.addressof(raw);base.length=6
    times=snap.CRLTimes();times.version=1;base.info=C.addressof(times)
    crl=snap.RevocationCRL();crl.size=C.sizeof(crl);crl.base=C.addressof(base)
    for i in range(3):
        contexts[i].der=C.addressof(buffers[i]);contexts[i].length=len(der[i])
        certs[i].size=C.sizeof(trust.ProviderCert);certs[i].cert=C.pointer(contexts[i]);certs[i].element=C.addressof(elements[i])
        elements[i].size=C.sizeof(snap.ChainElement);elements[i].cert=C.addressof(contexts[i])
        if i<2:
            revs[i].size=C.sizeof(snap.RevocationInfo);elements[i].revocation=C.addressof(revs[i])
    certs[0].revoked=0x80092013;revs[0].result=0x80092013;elements[0].status.error=0x1000040
    revs[1].crl=C.addressof(crl)
    signer=trust.Signer();signer.size=C.sizeof(signer);signer.count=3;signer.certs=C.addressof(certs)
    chain=snap.ChainContextPrefix();chain.size=C.sizeof(chain);chain.count=1;chain.status.error=0x1000040;signer.chain=C.addressof(chain)
    errors=(snap.D*38)();provider=snap.ProviderPrefix();provider.size=C.sizeof(provider);provider.request=C.addressof(request)
    provider.signer_count=1;provider.signers=C.addressof(signer);provider.step_count=38;provider.steps=C.addressof(errors)
    refs=[request,contexts,elements,certs,buffers,revs,base,raw,times,crl,signer,chain,errors,provider]
    copy.capture_provider(C.addressof(provider),17);copy.capture_signer(C.pointer(signer));copy.deactivate()
    assert copy.complete
    owner.result=dict(file='msvcp140.dll',sha256='a'*64,metadata_after='UNCHANGED',verification='REFUSED_OR_UNKNOWN',
        stage='CERTIFICATE_POLICY',activity='CHECK',execution_uncertain=False,
        wintrust_returns=[dict(action='VERIFY',signed=0,hex='00000000'),dict(action='CLOSE',signed=0,hex='00000000')])
    copy._test_refs=refs;copy._test_certificates=certs;copy._test_elements=elements
    return owner


def native(monkeypatch,original):
    monkeypatch.setattr(C,'get_last_error',lambda:0,raising=False)
    s=SimpleNamespace(calls=[],refs=[],signature_fail=0,signature_count=0,revocation_fail=0,revocation_count=0,
        unknown=False,close_bad=False,revoked=False,expired=False,publisher='Microsoft Corporation',
        source_mode=None,returned=[],output_free_bad=False,expire_on_revocation=False,requested_times=[])
    def blob(data):
        b=C.create_string_buffer(data);s.refs.append(b);return prep.Blob(len(data),C.addressof(b))
    def info(index):
        value=prep.CRLInfo();value.version=1
        target=meta.DER().root(original.der[index+1]).children[0].children[5]
        value.issuer=blob(target.raw);now=datetime.now(timezone.utc)
        value.this_update=stamp(now-timedelta(hours=1));value.next_update=stamp(now+timedelta(days=-1 if s.expired else 1))
        ex=(prep.Extension*1)();oidbuffer=C.create_string_buffer(b'2.5.29.35\0');s.refs.extend([ex,oidbuffer])
        ex[0].oid=C.addressof(oidbuffer);ex[0].value=blob(sequence(tlv(128,bytes([0x22 if index==0 else 0x33])*20)))
        value.extensions=C.addressof(ex);value.extension_count=1
        if s.revoked and index==0:
            entries=(prep.Entry*1)();entries[0].serial=blob(b'\x23\x01');entries[0].revoked=stamp(now-timedelta(days=1))
            s.refs.append(entries);value.entries=C.addressof(entries);value.count=1
        s.refs.append(value);return C.addressof(value)
    def create_cert(encoding,data,size):
        s.calls.append('CREATE_CERT');row=trust.CertContext();row.der=C.cast(data,m.P).value;row.length=size;s.refs.append(row);return C.pointer(row)
    def create_crl(encoding,data,size):
        raw=C.string_at(data,size);s.calls.append('CREATE_CRL');row=prep.CRLContext();row.der=C.cast(data,m.P).value;row.length=size
        row.info=info(0 if raw==b'LEAF_CRL' else 1);s.refs.append(row);return C.pointer(row)
    def verify(*args):
        s.calls.append(('VERIFY',args[2]));s.signature_count+=1
        assert args[0:2]==(None,1) and args[4]==2 and args[6:]==(1,None)
        return s.signature_count!=s.signature_fail
    def cert_name(context,kind,flags,oidp,buffer,size):buffer.value=s.publisher;return len(s.publisher)+1
    def opened(provider,encoding,crypto,flags,param):
        assert provider.value==2 and encoding==0 and crypto is None and flags==0x2000 and param is None
        s.calls.append('OPEN_MEMORY');return 99
    def add_cert(store,context,disposition,out):assert (store,disposition,out)==(99,1,None);s.calls.append('ADD_CERT');return 1
    def add_crl(store,context,disposition,out):assert (store,disposition,out)==(99,1,None);s.calls.append('ADD_CRL');return 1
    def revocation(encoding,kind,count,contexts,flags,parameters,state):
        s.calls.append('REVOCATION');s.revocation_count+=1
        assert (encoding,kind,count,flags)==(0x10001,1,1,2)
        para=parameters._obj;assert para.size==C.sizeof(para) and para.crl_store==99 and para.store_count==1
        assert para.issuer and para.verify_time==para.current_time and not para.url_timeout and para.crl_info and not para.resync
        target=C.cast(C.cast(contexts,C.POINTER(m.P))[0],C.POINTER(trust.CertContext)).contents
        issuer=C.cast(para.issuer,C.POINTER(trust.CertContext)).contents
        assert C.string_at(target.der,target.length)==original.der[s.revocation_count-1]
        assert C.string_at(issuer.der,issuer.length)==original.der[s.revocation_count]
        when=C.cast(para.verify_time,C.POINTER(snap.FileTime)).contents
        s.requested_times.append((when.high<<32)|when.low)
        info=C.cast(para.crl_info,C.POINTER(snap.RevocationCRL)).contents
        assert info.size==C.sizeof(info) and not any((info.base,info.delta,info.entry,info.delta_entry))
        if s.unknown:raise RuntimeError('PRIVATE_NATIVE_ARGUMENT')
        raw=b'LEAF_CRL' if s.revocation_count==1 else b'CA_CRL'
        if s.source_mode=='different' or s.source_mode=='second_different' and s.revocation_count==2:raw=b'OTHER_VALID_CRL'
        if s.source_mode!='missing':
            buffer=C.create_string_buffer(raw);row=prep.CRLContext();row.der=C.addressof(buffer);row.length=len(raw)
            s.refs.extend([buffer,row]);s.returned.append(C.addressof(row));info.base=C.addressof(row)
        if s.source_mode=='bad_size':info.size-=8
        if s.source_mode=='delta_alias':info.delta=info.base
        if s.source_mode=='entry':info.entry=1
        if s.source_mode=='delta_entry':info.delta_entry=1
        if s.source_mode=='unknown_after_output':raise RuntimeError('PRIVATE_NATIVE_ARGUMENT')
        state._obj.has_freshness=1;state._obj.freshness=3600
        state._obj.error=0x80092013 if s.revocation_count==s.revocation_fail else 0
        if s.expire_on_revocation:s.verifier.deadline=time.monotonic()-1
        return not state._obj.error
    def free_cert(context):s.calls.append('FREE_CERT');return 1
    def free_crl(context):
        returned=C.cast(context,m.P).value in s.returned
        s.calls.append('FREE_RETURNED_CRL' if returned else 'FREE_CRL')
        return not (returned and s.output_free_bad)
    def closed(store,flags):assert (store,flags)==(99,2);s.calls.append('CLOSE_MEMORY');return not s.close_bad
    functions=dict(CertCreateCertificateContext=create_cert,CertCreateCRLContext=create_crl,CertFreeCertificateContext=free_cert,
        CertFreeCRLContext=free_crl,CryptVerifyCertificateSignatureEx=verify,CertGetNameStringW=cert_name,CertOpenStore=opened,
        CertAddCertificateContextToStore=add_cert,CertAddCRLContextToStore=add_crl,CertCloseStore=closed,CertVerifyRevocation=revocation)
    class Library:
        def __getattr__(self,key):assert key in functions;return functions[key]
    monkeypatch.setattr(C,'WinDLL',lambda *a,**kw:Library(),raising=False);monkeypatch.setattr(prep,'os',SimpleNamespace(name='nt'))
    # Override the endpoint contract only for synthetic certs that publish no CA CDP.
    return s


def check(monkeypatch,owner,state):
    now=time.monotonic();value=m.MemoryRevocation(float(now+120),float(now+135))
    state.verifier=value
    return value,value.check(owner.state_snapshot,b'LEAF_CRL')


def test_original_graph_is_copied_before_close_and_offline_is_not_rewritten(monkeypatch):
    owner=source(monkeypatch);original=owner.state_snapshot
    assert m.original_constraints(owner) is original and original.request is None
    assert original.facts['signer_chain']['certificates'][0]['revocation_reason']=='80092013'
    assert type(original.ca_crl) is bytes and len(original.der)==3
    with pytest.raises(prep.PreparationRefused):m.original_constraints(dict(owner.result))


@pytest.mark.parametrize('change',['root_revoked','root_error','root_cyclic','foreign_element','provider_step','closed_unknown','other_revocation','extra_chain_error'])
def test_any_original_nonrevocation_or_unknown_error_rejects_before_memory(monkeypatch,change):
    owner=source(monkeypatch);facts=owner.state_snapshot.facts;chain=facts['signer_chain']
    if change=='root_revoked':chain['certificates'][2]['revocation_reason']='80092013'
    if change=='root_error':chain['certificates'][2]['error']='00000001'
    if change=='root_cyclic':chain['certificates'][2]['cyclic']=True
    if change=='foreign_element':owner.state_snapshot.complete=False
    if change=='provider_step':facts['provider']['trust_step_errors'][3]='00000001'
    if change=='closed_unknown':owner.result['wintrust_returns'][1]['signed']=-1
    if change=='other_revocation':chain['certificates'][0]['revocation_reason']='80092010'
    if change=='extra_chain_error':chain['chain_context']['trust']['error']='01000048'
    with pytest.raises(prep.PreparationRefused):m.original_constraints(owner)


def test_memory_checks_use_both_fixed_pairs_with_current_revocation_without_grant(monkeypatch):
    owner=source(monkeypatch);s=native(monkeypatch,owner.state_snapshot);value,result=check(monkeypatch,owner,s)
    assert s.calls.count('CREATE_CERT')==3 and s.calls.count('CREATE_CRL')==2
    assert s.calls.count(('VERIFY',2))==s.calls.count(('VERIFY',3))==s.calls.count('REVOCATION')==2
    assert s.calls[-6:]==['CLOSE_MEMORY','FREE_CRL','FREE_CRL','FREE_CERT','FREE_CERT','FREE_CERT']
    assert result['status']=='CURRENT_MEMORY_REVOCATION_CONJUNCTION_OBSERVED'
    assert result['production_admission']=='NOT_CONNECTED' and result['equivalent_or_stronger_proven'] is False
    assert all(x['source_used']=='USED_BASE_DER_EQUALS_EXPECTED_PAIR_CRL' and x['store_origin']=='NOT_OBSERVED'
        for x in result['native_revocation'])
    assert [x['used_base_crl_sha256'] for x in result['native_revocation']]==result['crl_sha256']
    assert len({x['requested_time_filetime'] for x in result['native_revocation']})==1
    assert s.requested_times[0]==s.requested_times[1]==int(result['native_revocation'][0]['requested_time_filetime'])
    assert all(type(x['requested_time_filetime']) is str and x['native_time_semantics']=='REQUESTED_NOT_ATTESTED'
        for x in result['native_revocation'])
    assert s.calls.count('FREE_RETURNED_CRL')==2
    assert owner.state_snapshot.facts['signer_chain']['certificates'][0]['revocation_reason']=='80092013'
    assert not value.owned and not value.buffers


@pytest.mark.parametrize('kind',['cert_signature','second_crl_signature','second_revocation','publisher','revoked','expired'])
def test_independent_error_never_turns_original_offline_into_acceptance(monkeypatch,kind):
    owner=source(monkeypatch);s=native(monkeypatch,owner.state_snapshot)
    if kind=='cert_signature':s.signature_fail=1
    if kind=='second_crl_signature':s.signature_fail=4
    if kind=='second_revocation':s.revocation_fail=2
    if kind=='publisher':s.publisher='Foreign publisher'
    if kind=='revoked':s.revoked=True
    if kind=='expired':s.expired=True
    with pytest.raises(prep.PreparationRefused) as caught:check(monkeypatch,owner,s)
    assert caught.value.cleanup=='OWNED_CONTEXTS_CLOSED' and s.calls[-1]=='FREE_CERT'


def test_unknown_native_or_memory_store_close_is_retained_without_retry(monkeypatch):
    from scripts.windows_ci.crt_crl_preparation import _retained_unknown
    for kind in ('unknown','close_bad'):
        with monkeypatch.context() as patch:
            owner=source(patch);s=native(patch,owner.state_snapshot);setattr(s,kind,True);before=len(_retained_unknown)
            try:
                with pytest.raises(prep.PreparationRefused) as caught:check(patch,owner,s)
                assert caught.value.cleanup in ('UNKNOWN','UNKNOWN_RETAINED')
                assert not any(x in ('FREE_CERT','FREE_CRL') for x in s.calls)
                assert s.calls.count('CLOSE_MEMORY')==(1 if kind=='close_bad' else 0)
                assert 'PRIVATE_NATIVE_ARGUMENT' not in str(caught.value)
            finally:del _retained_unknown[before:]


def test_copies_refuse_mismatched_native_element_or_missing_second_crl(monkeypatch):
    for change in ('element','ca_crl'):
        with monkeypatch.context() as patch:
            owner=source(patch);copy=owner.state_snapshot;refs=copy._test_refs
            if change=='element':copy._test_elements[1].cert=1
            else:refs[5][1].crl=0
            copy.activate(refs[0],0);copy.capture_signer(C.pointer(refs[10]));copy.deactivate()
            assert copy.complete is False
            with pytest.raises(prep.PreparationRefused):m.original_constraints(owner)


def test_certificate_must_be_current_at_return_without_historical_timestamp_exception(monkeypatch):
    owner=source(monkeypatch);s=native(monkeypatch,owner.state_snapshot);original_all=m.all_current
    def all_current(metadata):
        if s.calls and s.calls[-1]=='FREE_CERT':raise prep.PreparationRefused('CERTIFICATE_NOT_CURRENT_NO_TIMESTAMP_EXCEPTION')
        return original_all(metadata)
    monkeypatch.setattr(m,'all_current',all_current)
    with pytest.raises(prep.PreparationRefused) as caught:check(monkeypatch,owner,s)
    assert caught.value.reason=='CERTIFICATE_NOT_CURRENT_NO_TIMESTAMP_EXCEPTION' and caught.value.cleanup=='OWNED_CONTEXTS_CLOSED'
    assert s.calls[-1]=='FREE_CERT'


def test_unknown_revocation_retains_all_raw_address_targets_after_original_frame_is_gone(monkeypatch):
    import gc,weakref
    from scripts.windows_ci.crt_crl_preparation import _retained_unknown
    owner=source(monkeypatch);s=native(monkeypatch,owner.state_snapshot);s.unknown=True;before=len(_retained_unknown)
    now=time.monotonic();value=m.MemoryRevocation(float(now+120),float(now+135))
    try:
        try:value.check(owner.state_snapshot,b'LEAF_CRL')
        except prep.PreparationRefused:pass  # Future coordinator converts error, discarding traceback.
        storage=[x for x in value.buffers if type(x) is tuple and len(x)==6]
        assert len(storage)==1
        refs=[weakref.ref(x) for x in storage[0]];addresses=(C.addressof(storage[0][0]),C.addressof(storage[0][1]))
        del storage;gc.collect()
        assert all(x() is not None for x in refs)
        parameters=refs[3]();assert parameters.stores==addresses[0] and parameters.verify_time==parameters.current_time==addresses[1]
        assert value.unknown and value.pending and not any(x in ('FREE_CRL','FREE_CERT','CLOSE_MEMORY') for x in s.calls)
    finally:del _retained_unknown[before:]


def test_second_crl_and_revocation_failure_report_exact_pair_and_public_native_status(monkeypatch):
    for mode in ('signature','revocation'):
        with monkeypatch.context() as patch:
            owner=source(patch);s=native(patch,owner.state_snapshot)
            if mode=='signature':s.signature_fail=4
            else:s.revocation_fail=2
            with pytest.raises(prep.PreparationRefused) as caught:check(patch,owner,s)
            error=caught.value
            assert error.index==1 and error.cleanup=='OWNED_CONTEXTS_CLOSED'
            assert error.stage==('CRL_SIGNATURE_AND_PROFILE' if mode=='signature' else 'CACHE_ONLY_REVOCATION')
            if mode=='signature':assert error.native_error=='00000000'  # controlled callback, not a claimed native reason
            else:
                assert len(error.revocation_status)==2 and error.revocation_status[1]['returned_good'] is False
                assert error.revocation_status[1]['error']=='80092013'


@pytest.mark.parametrize('mode,reason',[
    ('missing','REVOCATION_BASE_SOURCE_UNAVAILABLE'),
    ('bad_size','REVOCATION_BASE_SOURCE_UNAVAILABLE'),
    ('different','REVOCATION_SOURCE_BYTES_DIFFER'),
    ('second_different','REVOCATION_SOURCE_BYTES_DIFFER'),
    ('delta_alias','REVOCATION_DELTA_OR_ENTRY_UNSUPPORTED'),
    ('entry','REVOCATION_DELTA_OR_ENTRY_UNSUPPORTED'),
    ('delta_entry','REVOCATION_DELTA_OR_ENTRY_UNSUPPORTED')])
def test_native_good_without_exact_returned_crl_source_is_never_bound(monkeypatch,mode,reason):
    owner=source(monkeypatch);s=native(monkeypatch,owner.state_snapshot);s.source_mode=mode
    with pytest.raises(prep.PreparationRefused) as caught:check(monkeypatch,owner,s)
    error=caught.value
    assert error.reason==reason and error.stage=='REVOCATION_SOURCE_BINDING'
    assert error.index==(1 if mode=='second_different' else 0)
    assert error.revocation_status[-1]['returned_good'] is True
    assert error.revocation_status[-1]['source_used']=='MISSING_OR_UNBOUND'
    assert error.cleanup=='OWNED_CONTEXTS_CLOSED'
    assert s.calls.count('FREE_RETURNED_CRL')==(0 if mode=='missing' else 2 if mode in ('delta_alias','second_different') else 1)


def test_known_failed_revocation_still_owns_returned_context_before_status_check(monkeypatch):
    owner=source(monkeypatch);s=native(monkeypatch,owner.state_snapshot);s.revocation_fail=1
    with pytest.raises(prep.PreparationRefused) as caught:check(monkeypatch,owner,s)
    assert caught.value.reason=='MEMORY_REVOCATION_NOT_GOOD'
    assert s.calls.count('FREE_RETURNED_CRL')==1 and caught.value.cleanup=='OWNED_CONTEXTS_CLOSED'


def test_unknown_call_with_changed_output_retains_graph_without_freeing_it(monkeypatch):
    import gc
    from scripts.windows_ci.crt_crl_preparation import _retained_unknown
    owner=source(monkeypatch);s=native(monkeypatch,owner.state_snapshot);s.source_mode='unknown_after_output'
    before=len(_retained_unknown);now=time.monotonic();value=m.MemoryRevocation(float(now+120),float(now+135))
    try:
        try:value.check(owner.state_snapshot,b'LEAF_CRL')
        except prep.PreparationRefused:pass
        gc.collect();storage=next(x for x in value.buffers if type(x) is tuple and len(x)==6)
        assert value.unknown and value.pending and storage[5].base
        assert not any(x in ('FREE_RETURNED_CRL','FREE_CRL','FREE_CERT','CLOSE_MEMORY') for x in s.calls)
    finally:del _retained_unknown[before:]


def test_returned_context_free_failure_is_unknown_and_never_retried(monkeypatch):
    from scripts.windows_ci.crt_crl_preparation import _retained_unknown
    owner=source(monkeypatch);s=native(monkeypatch,owner.state_snapshot);s.output_free_bad=True;before=len(_retained_unknown)
    try:
        with pytest.raises(prep.PreparationRefused) as caught:check(monkeypatch,owner,s)
        assert caught.value.cleanup=='UNKNOWN' and caught.value.cleanup_kind=='RETURNED_BASE_CRL'
        assert s.calls.count('FREE_RETURNED_CRL')==1 and 'CLOSE_MEMORY' not in s.calls
    finally:del _retained_unknown[before:]


def test_known_return_registers_outputs_even_when_work_deadline_just_expired(monkeypatch):
    owner=source(monkeypatch);s=native(monkeypatch,owner.state_snapshot);s.expire_on_revocation=True
    with pytest.raises(prep.PreparationRefused) as caught:check(monkeypatch,owner,s)
    assert caught.value.reason=='WORK_DEADLINE' and caught.value.cleanup=='OWNED_CONTEXTS_CLOSED'
    assert s.calls.count('FREE_RETURNED_CRL')==1 and s.calls.count('CLOSE_MEMORY')==1
