"""Isolated current-time CRL conjunction candidate, NEVER production admission.

The original shared file check and its REFUSED/UNKNOWN result remain unchanged.
This diagnostic copies bounded public bytes from the ORIGINAL live WVT graph,
then uses owned cert/CRL contexts and a MEMORY store. No persistent store, URL
cache, provider override or original-state mutation is permitted. Native GOOD
alone is insufficient: each single-context call must return the exact checked
base CRL bytes through pCrlInfo. This still emits no production capability.
"""
import ctypes as C
import time
from datetime import datetime,timezone
from hashlib import sha256
from scripts.windows_ci.crt_crl_preparation import (OwnedCRLValidator,PreparationRefused,CRLContext,need,current_window,
    LEAF_SHA256,ISSUER_SHA256,CDP,MAX_BYTES)
from scripts.windows_ci.crt_certificate_metadata import certificate
from scripts.windows_ci.crt_state_snapshot import (StateSnapshot,ChainElement,RevocationInfo,RevocationCRL,CRLContext as SnapshotCRL)
from scripts.windows_ci.crt_signature_readonly import ReadOnlySignature
from scripts.windows_portable import authenticode_signature as trust
P=C.c_void_p;D=C.c_uint32;B=C.c_int32
ROOT=trust.ROOT_SHA256
CERT_PINS=(LEAF_SHA256,ISSUER_SHA256,ROOT)
CA_CDP='http://crl.microsoft.com/pki/crl/products/MicRooCerAut2011_2011_03_22.crl'
FILE_PINS={'msvcp140.dll':'7c26614e1d733892c2deac7e245ce115504b1d80592dd0a01b08e3e5a55f89ca',
           'vcruntime140.dll':'d1f4225df2cd877dbf130d5668a021dce3f94118455ff5ec952061c30afc9ce7'}


class OriginalCopies(StateSnapshot):
    def __init__(self,owner):
        super().__init__(owner);self.der=();self.ca_crl=None;self.complete=False
    def capture_signer(self,pointer):
        super().capture_signer(pointer)
        try:
            need(self.facts['signer_chain']['status']=='READ_ORIGINAL_STATE','ORIGINAL_CHAIN_UNAVAILABLE')
            row=self.read(pointer,trust.Signer,exact=True);need(row.count==3,'FIXED_CHAIN_REQUIRED');certs=[]
            for i in range(3):
                source=self.read(row.certs+i*C.sizeof(trust.ProviderCert),trust.ProviderCert,exact=True)
                need(source.cert and source.element,'ORIGINAL_CONTEXT_MISSING')
                element=self.read(source.element,ChainElement)
                need(element.cert==C.cast(source.cert,P).value,'ORIGINAL_ELEMENT_CONTEXT_MISMATCH')
                context=self.read(source.cert,trust.CertContext,sized=False)
                need(context.der and 0<context.length<=65536,'ORIGINAL_CERT_DER_BOUNDS');self.guard()
                certs.append(C.string_at(context.der,context.length))
                if i==1:
                    rev=self.read(element.revocation,RevocationInfo)
                    need(rev.result==0 and rev.crl,'ORIGINAL_CA_REVOCATION_MISSING')
                    crl=self.read(rev.crl,RevocationCRL);need(crl.base and not crl.delta,'ORIGINAL_BASE_CRL_REQUIRED')
                    base=self.read(crl.base,SnapshotCRL,sized=False)
                    need(base.der and 0<base.length<=MAX_BYTES,'ORIGINAL_CRL_DER_BOUNDS');self.guard()
                    self.ca_crl=C.string_at(base.der,base.length)
            need(tuple(sha256(x).hexdigest() for x in certs)==CERT_PINS,'ORIGINAL_CERT_PIN_MISMATCH')
            self.der=tuple(certs);self.complete=True
        except Exception:
            self.complete=False  # Observer can never rewrite shared verifier results.


class MemoryFileProbe(ReadOnlySignature):
    def __init__(self,work_end,cleanup_end):
        super().__init__(work_end,cleanup_end);self.state_snapshot=OriginalCopies(self);self.initial_identity=None
    def identity(self,handle):
        result=super().identity(handle)
        if self.initial_identity is None:self.initial_identity=result
        return result


def original_constraints(probe):
    """Classify original facts only. This function never returns a product grant."""
    need(type(probe) is MemoryFileProbe and type(probe.state_snapshot) is OriginalCopies,'ORIGINAL_PROBE_REQUIRED')
    row=probe.result;snapshot=probe.state_snapshot
    need(snapshot.complete and len(probe.handles)==1 and not probe.unknown and not probe.failed,'ORIGINAL_PROBE_INCOMPLETE')
    need(row.get('sha256')==FILE_PINS.get(row.get('file')) and row.get('metadata_after')=='UNCHANGED','ORIGINAL_FILE_MISMATCH')
    need(row.get('wintrust_returns')==[dict(action='VERIFY',signed=0,hex='00000000'),dict(action='CLOSE',signed=0,hex='00000000')]
        and not row.get('execution_uncertain',False),'ORIGINAL_WINTRUST_UNKNOWN_OR_REJECTED')
    need(row.get('verification') in ('REFUSED_OR_UNKNOWN','STRICT_SHARED_SIGNATURE_CHECK_PASSED'),'ORIGINAL_STATUS_REQUIRED')
    if row['verification']=='REFUSED_OR_UNKNOWN':need(row.get('stage')=='CERTIFICATE_POLICY' and row.get('activity')=='CHECK','ORIGINAL_FAILURE_NOT_REVOCATION')
    provider=snapshot.facts['provider'];chain=snapshot.facts['signer_chain']
    need(provider.get('status')=='READ_ORIGINAL_STATE' and provider.get('request_bound') is True
        and provider.get('request_flags_wtd')=='00003080' and provider.get('request_revocation_checks')==1
        and provider.get('error')==provider.get('final_error')=='00000000'
        and provider.get('step_count',0)>0 and len(provider.get('trust_step_errors',[]))==provider['step_count']
        and all(x=='00000000' for x in provider.get('trust_step_errors',[])),
        'ORIGINAL_PROVIDER_ERROR')
    need(chain.get('signer_error')=='00000000' and not int(chain.get('signer_kind','ffffffff'),16)&0x10
        and chain.get('certificate_count')==3,'ORIGINAL_SIGNER_ERROR')
    need(chain.get('chain_context',{}).get('trust',{}).get('error') in ('00000000','01000040'),'ORIGINAL_CHAIN_ERROR')
    need(len(chain['certificates'])==3,'ORIGINAL_CHAIN_INCOMPLETE')
    for i,cert in enumerate(chain['certificates']):
        need(cert['index']==i and cert['error']=='00000000' and not cert['test'] and not cert['cyclic'],'ORIGINAL_CERTIFICATE_ERROR')
        need(cert['element'].get('status')=='OBSERVED' and cert['element'].get('trust',{}).get('error') in
            (('00000000',) if i==2 else ('00000000','01000040')),'ORIGINAL_ELEMENT_ERROR')
        need(cert['revocation_reason'] in (('00000000',) if i==2 else ('00000000','80092013')),'ORIGINAL_REVOCATION_ERROR')
    return snapshot


class RevocationStatus(C.Structure):
    _fields_=[('size',D),('index',D),('error',D),('reason',D),('has_freshness',B),('freshness',D)]
class RevocationParameters(C.Structure):
    _fields_=[('size',D),('issuer',P),('store_count',D),('stores',P),('crl_store',P),('verify_time',P),
        ('url_timeout',D),('check_freshness',B),('freshness',D),('current_time',P),('crl_info',P),('resync',P),('chain',P)]


def all_current(metadata):
    now=datetime.now(timezone.utc)
    for row in metadata:
        before=datetime.fromisoformat(row['not_before_utc'].replace('Z','+00:00'))
        after=datetime.fromisoformat(row['not_after_utc'].replace('Z','+00:00'))
        need(before<=now<=after,'CERTIFICATE_NOT_CURRENT_NO_TIMESTAMP_EXCEPTION')
    return now


class MemoryRevocation(OwnedCRLValidator):
    def __init__(self,deadline,cleanup_end):
        super().__init__(deadline,cleanup_end)
        self.stage='MEMORY_PRECHECK';self.index=None;self.revocation_facts=[];self.cleanup_native_error=None
        self.open_store=trust.bind(self.dll,'CertOpenStore',P,[P,D,P,D,P])
        self.add_cert=trust.bind(self.dll,'CertAddCertificateContextToStore',B,[P,C.POINTER(trust.CertContext),D,P])
        self.add_crl=trust.bind(self.dll,'CertAddCRLContextToStore',B,[P,P,D,P])
        self.close_store=trust.bind(self.dll,'CertCloseStore',B,[P,D])
        self.revocation=trust.bind(self.dll,'CertVerifyRevocation',B,[D,D,D,P,D,C.POINTER(RevocationParameters),C.POINTER(RevocationStatus)])
        self.cert_name=trust.bind(self.dll,'CertGetNameStringW',D,[C.POINTER(trust.CertContext),D,D,P,C.c_wchar_p,D])

    def require_native(self,value,reason):
        if not value:
            error=PreparationRefused(reason);code=C.get_last_error()
            error.native_error=f'{code&0xffffffff:08x}' if type(code) is int else None
            raise error
        return value

    def free_owned(self,fn,*args):
        value=fn(*args)
        if not value:
            code=C.get_last_error();self.cleanup_native_error=f'{code&0xffffffff:08x}' if type(code) is int else None
        return value

    def create(self,data,fn,free,kind):
        buffer=C.create_string_buffer(data);self.buffers.append(buffer)
        context=self.call(fn,1,buffer,len(data))
        self.require_native(bool(context),'NATIVE_CONTEXT_CREATE_REFUSED')
        self.owned.append((context,lambda value:self.free_owned(free,value),kind));self.guard()
        row=context.contents;need(row.der and row.length==len(data) and C.string_at(row.der,row.length)==data,'OWNED_CONTEXT_BYTES_MISMATCH')
        return context

    def own_revocation_outputs(self,info):
        # Official wincrypt.h: every updated non-NULL context is caller-owned.
        # Register BOTH fields immediately after a known return, before any
        # deadline/profile/status check can fail. Even an equal pointer value
        # can represent a separate reference; do not deduplicate owned refs.
        # An unknown call never reaches here; its whole output graph is retained.
        for field in ('base','delta'):
            pointer=getattr(info,field)
            if pointer:
                context=C.cast(pointer,C.POINTER(CRLContext))
                self.owned.append((context,lambda value:self.free_owned(self.free_crl,value),
                    'RETURNED_'+field.upper()+'_CRL'))

    def bind_revocation_source(self,info,expected):
        self.guard()
        need(info.size==C.sizeof(info) and info.base,'REVOCATION_BASE_SOURCE_UNAVAILABLE')
        need(not info.delta and not info.entry and not info.delta_entry,'REVOCATION_DELTA_OR_ENTRY_UNSUPPORTED')
        row=C.cast(info.base,C.POINTER(CRLContext)).contents
        need(row.der and 0<row.length<=MAX_BYTES,'REVOCATION_SOURCE_BOUNDS')
        # Compare the entire DER, not a freshness number, pointer/store identity
        # or handler success. This also rejects a different valid cached CRL.
        self.guard();raw=C.string_at(row.der,row.length)
        need(raw==expected,'REVOCATION_SOURCE_BYTES_DIFFER')
        self.guard()
        return sha256(raw).hexdigest()

    def check(self,source,leaf_crl):
        need(type(source) is OriginalCopies and source.complete and source.request is None,'CLOSED_ORIGINAL_COPIES_REQUIRED')
        need(original_constraints(source.owner) is source,'ORIGINAL_PROBE_REQUIRED')
        need(not self.owned and not self.buffers,'VALIDATION_NOT_REUSABLE')
        need(tuple(sha256(x).hexdigest() for x in source.der)==CERT_PINS,'ORIGINAL_CERT_PIN_MISMATCH')
        need(type(leaf_crl) is bytes and 0<len(leaf_crl)<=MAX_BYTES and type(source.ca_crl) is bytes,'CRL_INPUT_BOUNDS')
        need(0<len(source.ca_crl)<=MAX_BYTES,'CRL_INPUT_BOUNDS')
        metadata=[certificate(x,self.guard) for x in source.der];all_current(metadata)
        need(metadata[0]['crl_distribution_points']==[CDP] and metadata[1]['crl_distribution_points']==[CA_CDP],'FIXED_CDP_BINDING')
        for i in range(2):need(metadata[i]['issuer_name_der_sha256']==metadata[i+1]['subject_name_der_sha256']
            and metadata[i]['authority_key_identifier']==metadata[i+1]['subject_key_identifier'],'CERTIFICATE_ISSUER_BINDING')
        primary=None;result=None;policies=[]
        try:
            certs=[];self.stage='OWN_CERTIFICATES'
            for i,x in enumerate(source.der):
                self.index=i;certs.append(self.create(x,self.create_cert,self.free_cert,'CERT'))
            self.stage='CERTIFICATE_SIGNATURES'
            for i in range(2):
                self.index=i;self.require_native(self.call(self.verify,None,1,2,certs[i],2,certs[i+1],1,None),'CERTIFICATE_SIGNATURE_REFUSED')
            self.stage='PUBLISHER';self.index=0
            attr=C.create_string_buffer(b'2.5.4.10');name=C.create_unicode_buffer(256)
            n=self.call(self.cert_name,certs[0],3,0,attr,name,len(name))
            self.require_native(n,'PUBLISHER_QUERY_REFUSED')
            need(1<n<len(name) and name.value=='Microsoft Corporation','PUBLISHER_MISMATCH')
            crls=[]
            for i,raw in enumerate((leaf_crl,source.ca_crl)):
                self.stage='CRL_SIGNATURE_AND_PROFILE';self.index=i
                crl=self.create(raw,self.create_crl,self.free_crl,'CRL');crls.append(crl)
                self.require_native(self.call(self.verify,None,1,3,crl,2,certs[i+1],1,None),'CRL_SIGNATURE_REFUSED')
                policy=self.check_crl(crl,metadata[i],metadata[i+1]);need(not policy['leaf_listed'],'CURRENT_CERTIFICATE_REVOKED')
                policies.append(policy)
            # MEMORY provider only. No system-store name or path is accepted.
            self.stage='MEMORY_STORE';self.index=None
            store=self.call(self.open_store,P(2),0,None,0x2000,None)
            self.require_native(bool(store),'MEMORY_STORE_CREATE_REFUSED')
            self.owned.append((store,lambda h:self.free_owned(self.close_store,h,2),'MEMORY_STORE'))
            for i,cert in enumerate(certs):
                self.index=i;self.require_native(self.call(self.add_cert,store,cert,1,None),'MEMORY_CERT_INSERT_REFUSED')
            for i,crl in enumerate(crls):
                self.index=i;self.require_native(self.call(self.add_crl,store,crl,1,None),'MEMORY_CRL_INSERT_REFUSED')
            statuses=[]
            now=all_current(metadata);delta=now-datetime(1601,1,1,tzinfo=timezone.utc)
            ticks=(delta.days*86400+delta.seconds)*10000000+delta.microseconds*10
            # One explicit requested time binds both target/issuer pairs.
            # pftTimeToUse is a request, not an attestation the handler used it;
            # independently require each already-checked CRL to cover this time.
            for policy in policies:
                need(policy['this_update_filetime']<=ticks<=policy['next_update_filetime'],
                    'CRL_NOT_VALID_AT_COMMON_REQUEST_TIME')
            when=trust.D*2;value=when(ticks&0xffffffff,ticks>>32)
            for i in range(2):
                self.stage='CACHE_ONLY_REVOCATION';self.index=i
                stores=(P*1)(store);contexts=(P*1)(C.cast(certs[i],P).value)
                para=RevocationParameters();para.size=C.sizeof(para);para.issuer=C.cast(certs[i+1],P).value
                para.store_count=1;para.stores=C.addressof(stores);para.crl_store=store
                para.verify_time=C.addressof(value);para.current_time=C.addressof(value)
                state=RevocationStatus();state.size=C.sizeof(state)
                # Zero all fields for each call: the handler may free non-NULL
                # incoming contexts. Never feed the previous call's outputs back.
                info=RevocationCRL();info.size=C.sizeof(info);para.crl_info=C.addressof(info)
                # para holds raw addresses; C.byref(para) alone does NOT own
                # stores/value. Retain the whole graph through UNKNOWN calls.
                self.buffers.append((stores,value,contexts,para,state,info))
                good=self.call(self.revocation,0x10001,1,1,contexts,0x2,C.byref(para),C.byref(state))
                self.own_revocation_outputs(info)
                fact=dict(index=i,returned_good=bool(good),error=f'{state.error:08x}',has_freshness=bool(state.has_freshness),
                    freshness_seconds=state.freshness if state.has_freshness else None,source_used='MISSING_OR_UNBOUND',
                    store_origin='NOT_OBSERVED',
                    requested_time_filetime=str(ticks),native_time_semantics='REQUESTED_NOT_ATTESTED',
                    target_certificate_sha256=CERT_PINS[i],issuer_certificate_sha256=CERT_PINS[i+1])
                self.revocation_facts.append(fact)
                need(good and state.size==C.sizeof(state) and state.error==0,'MEMORY_REVOCATION_NOT_GOOD')
                self.stage='REVOCATION_SOURCE_BINDING'
                digest=self.bind_revocation_source(info,(leaf_crl,source.ca_crl)[i])
                fact.update(source_used='USED_BASE_DER_EQUALS_EXPECTED_PAIR_CRL',used_base_crl_sha256=digest)
                statuses.append(dict(fact))
            self.guard();all_current(metadata)
            for policy in policies:current_window(policy['this_update_filetime'],policy['next_update_filetime'])
            result=dict(status='CURRENT_MEMORY_REVOCATION_CONJUNCTION_OBSERVED',crl_sha256=[sha256(x).hexdigest() for x in (leaf_crl,source.ca_crl)],
                native_revocation=statuses,certificate_sha256=list(CERT_PINS),crl_policy=policies,
                historical_timestamp_exception=False,original_strict_result='PRESERVED_NOT_REWRITTEN',
                equivalent_or_stronger_proven=False,production_admission='NOT_CONNECTED',usable_product=False)
        except PreparationRefused as error:primary=error
        except BaseException:primary=PreparationRefused('MEMORY_VALIDATION_INTERNAL_FAILURE')
        try:self.close()
        except BaseException as error:
            if primary is None:primary=PreparationRefused('CLEANUP_REFUSED_OR_UNKNOWN')
            primary.cleanup='UNKNOWN';primary.cleanup_reason=error.reason if type(error) is PreparationRefused else 'UNLISTED_CLEANUP_FAILURE'
        if primary is not None:
            if primary.cleanup=='NOT_ATTEMPTED':primary.cleanup='UNKNOWN_RETAINED' if self.unknown else 'OWNED_CONTEXTS_CLOSED'
            primary.stage=self.stage;primary.index=self.index;primary.revocation_status=list(self.revocation_facts)
            primary.cleanup_native_error=self.cleanup_native_error
            primary.cleanup_kind=self.owned[-1][2] if self.owned else None
            raise primary from None
        try:
            need(time.monotonic()<self.deadline,'WORK_DEADLINE');all_current(metadata)
            for policy in policies:current_window(policy['this_update_filetime'],policy['next_update_filetime'])
        except PreparationRefused as error:error.cleanup='OWNED_CONTEXTS_CLOSED';raise error from None
        result['cleanup']='OWNED_CONTEXTS_AND_MEMORY_STORE_CLOSED';return result
