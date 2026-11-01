"""Bounded public copies of the ORIGINAL live WinTrust state; no native calls.

Only the read-only diagnostic uses this observer. Nothing here builds a chain,
retrieves a URL, edits a cache/store/policy, frees a borrowed pointer, or issues
an acceptance capability. Missing optional evidence is never a good verdict.
"""
import ctypes as C
import copy
from scripts.windows_portable import authenticode_signature as trust
from scripts.windows_ci.crt_certificate_metadata import observe_certificate, filetime_utc

P=C.c_void_p;D=C.c_uint32;B=C.c_int32


class FileTime(C.Structure):_fields_=[('low',D),('high',D)]
class TrustStatus(C.Structure):_fields_=[('error',D),('info',D)]
class Blob(C.Structure):_fields_=[('size',D),('data',P)]
class Algorithm(C.Structure):_fields_=[('oid',P),('parameters',Blob)]
class CRLTimes(C.Structure):
    _fields_=[('version',D),('algorithm',Algorithm),('issuer',Blob),('this_update',FileTime),('next_update',FileTime)]
class CRLContext(C.Structure):
    _fields_=[('encoding',D),('der',P),('length',D),('info',P),('store',P)]
class RevocationCRL(C.Structure):
    _fields_=[('size',D),('base',P),('delta',P),('entry',P),('delta_entry',B)]
class RevocationInfo(C.Structure):
    _fields_=[('size',D),('result',D),('oid',P),('specific',P),('has_freshness',B),('freshness',D),('crl',P)]
class ChainElement(C.Structure):
    _fields_=[('size',D),('cert',P),('status',TrustStatus),('revocation',P),('issuance',P),('application',P),('extended_error',P)]
class ChainContextPrefix(C.Structure):
    _fields_=[('size',D),('status',TrustStatus),('count',D),('chains',P),('lower_count',D),('lower',P),
        ('has_freshness',B),('freshness',D),('create_flags',D)]
class ProviderPrefix(C.Structure):
    _fields_=[('size',D),('request',P),('opened',B),('parent',P),('action',P),('crypto',P),
        ('error',D),('security',D),('policy',D),('functions',P),('step_count',D),('steps',P),
        ('store_count',D),('stores',P),('encoding',D),('message',P),('signer_count',D),('signers',P),
        ('private_count',D),('private',P),('choice',D),('sip',P),('usage',P),('recall',B),
        ('system_time',FileTime),('ctl_usage',P),('flags',D),('final_error',D)]


POLICY_FLAGS=((0x20,'WTPF_TRUSTTEST'),(0x80,'WTPF_TESTCANBEVALID'),(0x100,'WTPF_IGNOREEXPIRATION'),
    (0x200,'WTPF_IGNOREREVOKATION'),(0x400,'WTPF_OFFLINEOK_IND'),(0x800,'WTPF_OFFLINEOK_COM'),
    (0x1000,'WTPF_OFFLINEOKNBU_IND'),(0x2000,'WTPF_OFFLINEOKNBU_COM'),(0x10000,'WTPF_VERIFY_V1_OFF'),
    (0x20000,'WTPF_IGNOREREVOCATIONONTS'),(0x40000,'WTPF_ALLOWONLYPERTRUST'))
CPD_FLAGS=((0x80000000,'CPD_USE_NT5_CHAIN_FLAG'),(0x10000,'CPD_REVOCATION_CHECK_NONE'),
    (0x20000,'CPD_REVOCATION_CHECK_END_CERT'),(0x40000,'CPD_REVOCATION_CHECK_CHAIN'),
    (0x80000,'CPD_REVOCATION_CHECK_CHAIN_EXCLUDE_ROOT'))


def need(ok):
    if not ok:raise ValueError('ORIGINAL_STATE_SNAPSHOT_UNAVAILABLE')
def address(value):return C.cast(value,P).value
def stamp(value):return ((value.high<<32)|value.low) or None
def status(value):return dict(error=f'{value.error:08x}',info=f'{value.info:08x}')


class StateSnapshot:
    def __init__(self,owner):
        self.owner=owner;self.request=None;self.state=None;self.provider_address=None;self.provider_signer=None
        self.facts=dict(provider=dict(status='NOT_REACHED'),signer_chain=dict(status='NOT_REACHED'))

    def activate(self,request,returned):
        if returned==0 and type(request) is trust.TrustData and request.action==1 and request.state:
            self.request=request;self.state=request.state

    def deactivate(self):self.request=None;self.state=None

    def guard(self):
        self.owner._signature_budget(None,None)
        need(self.request is not None and self.request.action==1 and self.request.state==self.state and self.state)

    def read(self,pointer,kind,*,sized=True,exact=False):
        self.guard();location=address(pointer);need(location is not None and location>0)
        need(location%C.alignment(kind)==0)
        if sized:
            size=D.from_address(location).value
            need(size==C.sizeof(kind) if exact else C.sizeof(kind)<=size<=4096)
        self.guard()
        return kind.from_buffer_copy(C.string_at(location,C.sizeof(kind)))

    def capture_provider(self,pointer,state):
        # Only observer errors are summarized. Caller invokes the original
        # native helper outside this try, so native exceptions still propagate.
        phase='STATE_BINDING'
        try:
            self.guard();need(state==self.state)
            phase='PROVIDER_LAYOUT'
            row=self.read(pointer,ProviderPrefix)
            phase='REQUEST_AND_SIGNER_BINDING'
            need(row.request==C.addressof(self.request) and row.signer_count in range(1,9) and row.signers)
            self.provider_address=address(pointer);self.provider_signer=row.signers
            result=dict(status='READ_ORIGINAL_STATE',request_bound=True,request_flags_wtd=f'{self.request.flags:08x}',
                request_revocation_checks=self.request.revocation,provider_flags_cpd=f'{row.flags:08x}',
                provider_flag_names=[name for flag,name in CPD_FLAGS if row.flags&flag],
                registry_policy_flags=f'{row.policy:08x}',registry_policy_names=[name for flag,name in POLICY_FLAGS if row.policy&flag],
                registry_security_flags=f'{row.security:08x}',error=f'{row.error:08x}',final_error=f'{row.final_error:08x}',
                step_count=row.step_count,system_time_filetime=stamp(row.system_time))
            phase='TRUST_STEP_ARRAY';need(row.step_count<=64 and (row.step_count==0 or row.steps))
            values=[]
            for i in range(row.step_count):
                self.guard();values.append(f'{D.from_address(row.steps+i*C.sizeof(D)).value:08x}')
            result['trust_step_errors']=values;self.facts['provider']=result
        except Exception:self.facts['provider']=dict(status='UNAVAILABLE_BOUNDS_BINDING_OR_DEADLINE',phase=phase)

    def capture_signer(self,pointer):
        phase='PRIMARY_BINDING';index=None
        try:
            self.guard();need(self.provider_address and address(pointer)==self.provider_signer)
            phase='SIGNER_LAYOUT'
            row=self.read(pointer,trust.Signer,exact=True)
            need(2<=row.count<=8 and row.certs)
            result=dict(status='READ_ORIGINAL_STATE',verify_as_of_filetime=((row.time_high<<32)|row.time_low) or None,
                verify_as_of_semantics='PROVIDER_VERIFICATION_TIME_OR_TIMESTAMP',certificate_count=row.count,
                signer_error=f'{row.error:08x}',signer_kind=f'{row.type:08x}',chain_context=dict(status='NOT_AVAILABLE'),certificates=[])
            result['verify_as_of_utc']=filetime_utc(result['verify_as_of_filetime'])
            if row.chain:
                phase='CHAIN_CONTEXT'
                chain=self.read(row.chain,ChainContextPrefix)
                need(1<=chain.count<=4)
                result['chain_context']=dict(status='OBSERVED',trust=status(chain.status),simple_chain_count=chain.count,
                    has_freshness=bool(chain.has_freshness),freshness_seconds=chain.freshness if chain.has_freshness else None,
                    create_flags=f'{chain.create_flags:08x}')
            for i in range(row.count):
                index=i;phase='CERTIFICATE_LAYOUT'
                cert=self.read(row.certs+i*C.sizeof(trust.ProviderCert),trust.ProviderCert,exact=True)
                need(cert.cert)
                item=dict(index=i,error=f'{cert.error:08x}',revocation_reason=f'{cert.revoked:08x}',
                    test=bool(cert.test),cyclic=bool(cert.cyclic),commercial=bool(cert.commercial),
                    self_signed=bool(cert.self_signed),provider_trusted_root=bool(cert.root),element=dict(status='NOT_AVAILABLE'))
                phase='PUBLIC_CERTIFICATE_METADATA'
                context=self.read(cert.cert,trust.CertContext,sized=False)
                item['public_metadata']=dict(status='UNAVAILABLE_CERTIFICATE_DER_BOUNDS')
                if context.der and 0<context.length<=65536:
                    self.guard()
                    item['public_metadata']=observe_certificate(C.string_at(context.der,context.length),self.guard)
                if cert.element:
                    phase='CHAIN_ELEMENT'
                    element=self.read(cert.element,ChainElement)
                    phase='ELEMENT_CERTIFICATE_BINDING'
                    need(element.cert==address(cert.cert))
                    phase='REVOCATION_INFO_OR_CRL'
                    item['element']=dict(status='OBSERVED',trust=status(element.status),revocation=self.revocation(element.revocation))
                result['certificates'].append(item)
            self.facts['signer_chain']=result
        except Exception:self.facts['signer_chain']=dict(status='UNAVAILABLE_BOUNDS_BINDING_OR_DEADLINE',phase=phase,index=index)

    def revocation(self,pointer):
        if not pointer:return dict(status='NOT_AVAILABLE')
        row=self.read(pointer,RevocationInfo)
        result=dict(status='OBSERVED',result_dword=f'{row.result:08x}',has_freshness=bool(row.has_freshness),
            freshness_seconds=row.freshness if row.has_freshness else None,crl=dict(status='NOT_AVAILABLE'))
        if row.crl:
            crl=self.read(row.crl,RevocationCRL)
            result['crl']=dict(status='OBSERVED',base=self.crl_times(crl.base),delta=self.crl_times(crl.delta))
        return result

    def crl_times(self,pointer):
        if not pointer:return dict(status='NOT_AVAILABLE')
        context=self.read(pointer,CRLContext,sized=False)
        need(context.info and 0<context.length<=16*1024*1024)
        times=self.read(context.info,CRLTimes,sized=False);need(times.version in (0,1))
        return dict(status='OBSERVED_TIME_FIELDS_ONLY',this_update_filetime=stamp(times.this_update),
            next_update_filetime=stamp(times.next_update),validity_decision='NOT_EVALUATED')

    def export(self):
        # Only copied public facts survive CLOSE. No borrowed C pointer,
        # DER, raw extended-error string or platform grant escapes. Public CRT
        # certificate names/URIs are copied bounded observations, never fetched.
        return copy.deepcopy(self.facts)
