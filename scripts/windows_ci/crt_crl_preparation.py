"""Offline CRL preparation components; acquisition/cache writing is NOT enabled.

CryptRetrieveObjectByUrlW has no documented per-request no-redirect control and
accepts no caller-owned WinHTTP request handle. NO_AUTH does not provide that
control. Do not call it and examine the destination afterwards. Do not hand-edit
Cryptnet cache files, register another crypto scheme, or silently change scope.
The concrete crypt32 validator below operates only on supplied public bytes; it
never fetches a URL, imports into a store, issues an acceptance grant or runs PG.
"""
import ctypes as C
from datetime import datetime,timezone
from hashlib import sha256
import json
import math
import os
import re
import sys
import time
from pathlib import Path
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.windows_ci.crt_certificate_metadata import certificate,DER,oid,filetime_utc
from scripts.windows_ci.crt_state_snapshot import Blob,Algorithm,FileTime
from scripts.windows_portable.authenticode_signature import bind,CertContext

CDP='http://www.microsoft.com/pkiops/crl/Microsoft%20Windows%20Third%20Party%20Component%20CA%202013.crl'
LEAF_SHA256='224d2d27dcf6af3d93044f66a040422cc28498d8c1d26100aab1261c6b2f13c4'
ISSUER_SHA256='8ef01bb5e07987053659e039e5a72580c88c444bc1a31ab412ce81a4ad53044e'
MAX_BYTES=16*1024*1024
FETCH_SECONDS=15
JOB_SECONDS=180
P=C.c_void_p;D=C.c_uint32;B=C.c_int32
_retained_unknown=[]


class PreparationRefused(Exception):
    def __init__(self,reason):
        self.reason=reason;self.cleanup='NOT_ATTEMPTED';self.cleanup_reason=None
        # Native exception messages, certificate fields and arguments stay out.
        super().__init__('CRT_CRL_PREPARATION_REFUSED')


def need(ok,reason):
    if not ok:raise PreparationRefused(reason)


def current_window(this,next_):
    now=datetime.now(timezone.utc)
    delta=now-datetime(1601,1,1,tzinfo=timezone.utc)
    ticks=(delta.days*86400+delta.seconds)*10000000+delta.microseconds*10
    need(0<this<=ticks<=next_,'CRL_TIME_NOT_CURRENT')
    return now.isoformat().replace('+00:00','Z')


def plan():
    return dict(status='NOT_EXECUTED',reason='CRYPTNET_NO_REDIRECT_GUARANTEE_UNAVAILABLE',url=CDP,
        fetch_seconds=FETCH_SECONDS,max_bytes=MAX_BYTES,job_seconds=JOB_SECONDS,
        acquisition_implemented=False,cache_writer_implemented=False,
        network_or_cache_approved_here=False,redirects_allowed=False,authentication_allowed=False,
        usable_product=False,native_acceptance='NOT_ACCEPTED')


def prepare():
    # This refusal is before DLL loads, context creation, network/cache access.
    # A WinHTTP pre-probe cannot constrain a later opaque Cryptnet GET.
    raise PreparationRefused('CRYPTNET_NO_REDIRECT_GUARANTEE_UNAVAILABLE')


class Extension(C.Structure):_fields_=[('oid',P),('critical',B),('value',Blob)]
class Entry(C.Structure):_fields_=[('serial',Blob),('revoked',FileTime),('count',D),('extensions',P)]
class CRLInfo(C.Structure):
    _fields_=[('version',D),('algorithm',Algorithm),('issuer',Blob),('this_update',FileTime),('next_update',FileTime),
        ('count',D),('entries',P),('extension_count',D),('extensions',P)]
class CRLContext(C.Structure):_fields_=[('encoding',D),('der',P),('length',D),('info',P),('store',P)]


def bind_inputs(leaf_der,issuer_der,url,guard):
    need(url==CDP,'CDP_MISMATCH')
    need(type(leaf_der) is bytes and type(issuer_der) is bytes,'CERTIFICATE_INPUT_TYPE')
    need(0<len(leaf_der)<=65536 and 0<len(issuer_der)<=65536,'CERTIFICATE_INPUT_BOUNDS')
    need(sha256(leaf_der).hexdigest()==LEAF_SHA256 and sha256(issuer_der).hexdigest()==ISSUER_SHA256,'CERTIFICATE_PIN_MISMATCH')
    try:leaf=certificate(leaf_der,guard);issuer=certificate(issuer_der,guard)
    except PreparationRefused:raise
    except Exception:raise PreparationRefused('CERTIFICATE_METADATA_UNAVAILABLE') from None
    need(leaf['issuer_name_der_sha256']==issuer['subject_name_der_sha256'] and
        leaf['authority_key_identifier'] is not None and leaf['authority_key_identifier']==issuer['subject_key_identifier'],
        'CERTIFICATE_ISSUER_BINDING')
    need(leaf['crl_distribution_points']==[CDP] and not any(x['method_oid']=='1.3.6.1.5.5.7.48.1' for x in leaf['authority_information_access']),
        'CERTIFICATE_ENDPOINT_CONTRACT_CHANGED')
    return leaf,issuer


class OwnedCRLValidator:
    """Actual synchronous crypt32 implementation, not a borrowed WVT context.

    Not called by prepare() while acquisition is unavailable. Tests on Linux use
    controlled ABI callbacks and cannot establish Windows signature acceptance.
    """
    def __init__(self,deadline,cleanup_end):
        now=time.monotonic()
        need(type(deadline) is float and type(cleanup_end) is float and math.isfinite(deadline) and math.isfinite(cleanup_end)
            and now<deadline<=now+120 and deadline<cleanup_end<=min(now+135,deadline+15),'DEADLINE_INVALID')
        need(os.name=='nt' and C.sizeof(P)==8,'WINDOWS_AMD64_REQUIRED')
        self.deadline=deadline;self.cleanup_end=cleanup_end;self.owned=[];self.pending=None;self.unknown=False;self.closed=False
        self.buffers=[]
        self.dll=C.WinDLL('crypt32.dll',use_last_error=True,winmode=0x800)
        self.create_cert=bind(self.dll,'CertCreateCertificateContext',C.POINTER(CertContext),[D,P,D])
        self.create_crl=bind(self.dll,'CertCreateCRLContext',C.POINTER(CRLContext),[D,P,D])
        self.free_cert=bind(self.dll,'CertFreeCertificateContext',B,[C.POINTER(CertContext)])
        self.free_crl=bind(self.dll,'CertFreeCRLContext',B,[C.POINTER(CRLContext)])
        self.verify=bind(self.dll,'CryptVerifyCertificateSignatureEx',B,[P,D,D,P,D,P,D,P])

    def guard(self,cleanup=False):
        need(not self.closed and not self.unknown and self.pending is None,'NATIVE_STATE_UNKNOWN_OR_CLOSED')
        need(time.monotonic()<(self.cleanup_end if cleanup else self.deadline),'CLEANUP_DEADLINE' if cleanup else 'WORK_DEADLINE')

    def retain(self):
        self.unknown=True
        if self not in _retained_unknown:_retained_unknown.append(self)

    def call(self,fn,*args,cleanup=False):
        self.guard(cleanup);self.pending=(fn,args)
        try:result=fn(*args)
        except BaseException:
            self.retain();raise PreparationRefused('NATIVE_OUTCOME_UNKNOWN') from None
        self.pending=None
        return result

    def blob(self,value,limit=MAX_BYTES):
        self.guard();need(0<value.size<=limit and value.data,'NATIVE_BLOB_BOUNDS')
        return C.string_at(value.data,value.size)

    def identifier(self,pointer):
        self.guard();need(pointer,'NATIVE_OID_UNAVAILABLE');chars=[]
        for i in range(128):
            self.guard();b=C.c_ubyte.from_address(pointer+i).value
            if not b:
                text=bytes(chars).decode('ascii');need(re.fullmatch(r'[0-9]+(?:\.[0-9]+)+',text) is not None,'NATIVE_OID_FORMAT');return text
            chars.append(b)
        raise PreparationRefused('NATIVE_OID_BOUNDS')

    def extensions(self,pointer,count):
        need(count<=64 and (not count or pointer),'NATIVE_EXTENSION_BOUNDS');result={}
        for i in range(count):
            self.guard();row=Extension.from_address(pointer+i*C.sizeof(Extension));key=self.identifier(row.oid)
            need(key not in result,'DUPLICATE_EXTENSION');result[key]=(bool(row.critical),self.blob(row.value,65536))
        return result

    def check_crl(self,context,leaf,issuer):
        self.guard();row=context.contents;need(row.info and row.der and 0<row.length<=MAX_BYTES,'CRL_CONTEXT_BOUNDS')
        info=CRLInfo.from_address(row.info);need(info.version in (0,1),'CRL_VERSION')
        need(sha256(self.blob(info.issuer,8192)).hexdigest()==issuer['subject_name_der_sha256'],'CRL_ISSUER_NAME_MISMATCH')
        this=(info.this_update.high<<32)|info.this_update.low;next_=(info.next_update.high<<32)|info.next_update.low
        current_window(this,next_)
        ext=self.extensions(info.extensions,info.extension_count)
        need(info.version==1 or not ext,'V1_CRL_HAS_EXTENSIONS')
        need('2.5.29.27' not in ext,'DELTA_CRL_REQUIRES_BASE')
        need('2.5.29.28' not in ext and '2.5.29.46' not in ext,'SCOPED_OR_ADDITIONAL_CRL_REQUIRES_REVIEW')
        need(all(not critical or key in ('2.5.29.35','2.5.29.20') for key,(critical,raw) in ext.items()),'UNKNOWN_CRITICAL_CRL_EXTENSION')
        need('2.5.29.35' in ext,'CRL_AUTHORITY_KEY_MISSING')
        try:
            if '2.5.29.20' in ext:
                number=DER(self.guard).root(ext['2.5.29.20'][1])
                need(number.tag==2 and 0<len(number.value)<=20 and not number.value[0]&128,'CRL_NUMBER_FORMAT')
            authority=DER(self.guard).root(ext['2.5.29.35'][1]);need(authority.tag==48,'CRL_AUTHORITY_KEY_FORMAT')
            keys=[x.value.hex() for x in authority.children if x.tag==128]
            need(keys==[issuer['subject_key_identifier']],'CRL_AUTHORITY_KEY_MISMATCH')
        except PreparationRefused:raise
        except Exception:raise PreparationRefused('CRL_AUTHORITY_KEY_FORMAT') from None
        need(info.count<=1000000 and (not info.count or info.entries),'CRL_ENTRY_BOUNDS')
        match=None;target=int(leaf['serial_hex'],16)
        for i in range(info.count):
            self.guard();entry=Entry.from_address(info.entries+i*C.sizeof(Entry))
            serial=self.blob(entry.serial,32);entry_ext=self.extensions(entry.extensions,entry.count)
            need(info.version==1 or not entry_ext,'V1_CRL_HAS_EXTENSIONS')
            need('2.5.29.29' not in entry_ext,'INDIRECT_CRL_ENTRY_UNSUPPORTED')
            need(all(not critical for critical,raw in entry_ext.values()),'CRITICAL_ENTRY_EXTENSION_UNSUPPORTED')
            reason=None
            if '2.5.29.21' in entry_ext:
                try:
                    code=DER(self.guard).root(entry_ext['2.5.29.21'][1])
                    need(code.tag==10 and len(code.value)==1 and code.value[0] in (0,1,2,3,4,5,6,9,10),'CRL_REASON_FORMAT_OR_DELTA_REMOVAL')
                    reason=code.value[0]
                except PreparationRefused:raise
                except Exception:raise PreparationRefused('CRL_REASON_FORMAT_OR_DELTA_REMOVAL') from None
            if int.from_bytes(serial,'little')==target:
                need(match is None,'DUPLICATE_LEAF_REVOCATION_ENTRY')
                revoked=(entry.revoked.high<<32)|entry.revoked.low
                need(revoked>0,'CRL_ENTRY_TIME_INVALID');match=dict(revoked_utc=filetime_utc(revoked),reason_code=reason)
        self.guard();checked=current_window(this,next_)
        return dict(this_update_utc=filetime_utc(this),next_update_utc=filetime_utc(next_),
            this_update_filetime=this,next_update_filetime=next_,checked_at_utc=checked,entry_count=info.count,
            leaf_listed=match is not None,leaf_entry=match,revocation_acceptance='NOT_DECIDED_REQUIRES_FRESH_ORIGINAL_CACHE_ONLY_VERIFIER')

    def validate(self,leaf_der,issuer_der,crl_der,url=CDP):
        need(not self.owned and not self.buffers,'VALIDATION_NOT_REUSABLE')
        leaf,issuer=bind_inputs(leaf_der,issuer_der,url,self.guard)
        need(type(crl_der) is bytes and 0<len(crl_der)<=MAX_BYTES,'CRL_INPUT_BOUNDS')
        result=None;primary=None
        try:
            for data,create,free,kind in ((issuer_der,self.create_cert,self.free_cert,'CERT'),(crl_der,self.create_crl,self.free_crl,'CRL')):
                buffer=C.create_string_buffer(data);self.buffers.append(buffer)
                context=self.call(create,1,buffer,len(data))
                need(bool(context),'NATIVE_CONTEXT_CREATE_REFUSED');self.owned.append((context,free,kind))
                self.guard();row=context.contents
                need(row.der and row.length==len(data) and C.string_at(row.der,row.length)==data,'OWNED_CONTEXT_BYTES_MISMATCH')
            issuer_context=self.owned[0][0];crl_context=self.owned[1][0]
            # SUBJECT_CRL, ISSUER_CERT, disable MD2/MD4; no chain building/store.
            need(self.call(self.verify,None,1,3,crl_context,2,issuer_context,1,None)!=0,'CRL_SIGNATURE_REFUSED')
            policy=self.check_crl(crl_context,leaf,issuer)
            result=dict(status='CRL_PUBLIC_SIGNATURE_AND_APPLICABILITY_VERIFIED_NOT_PRODUCT_ACCEPTANCE',crl_sha256=sha256(crl_der).hexdigest(),
                crl_bytes=len(crl_der),issuer_sha256=ISSUER_SHA256,leaf_sha256=LEAF_SHA256,policy=policy,
                cache_written=False,usable_product=False,native_acceptance='NOT_ACCEPTED')
        except PreparationRefused as error:primary=error
        except BaseException:primary=PreparationRefused('VALIDATION_INTERNAL_FAILURE')
        try:self.close()
        except BaseException as error:
            if primary is None:primary=PreparationRefused('CLEANUP_REFUSED_OR_UNKNOWN')
            primary.cleanup='UNKNOWN';primary.cleanup_reason=error.reason if type(error) is PreparationRefused else 'UNLISTED_CLEANUP_FAILURE'
        if primary is not None:
            if primary.cleanup=='NOT_ATTEMPTED':primary.cleanup='UNKNOWN_RETAINED' if self.unknown else 'OWNED_CONTEXTS_CLOSED'
            raise primary from None
        try:
            need(time.monotonic()<self.deadline,'WORK_DEADLINE')
            result['policy']['checked_after_cleanup_utc']=current_window(result['policy']['this_update_filetime'],result['policy']['next_update_filetime'])
        except PreparationRefused as error:
            error.cleanup='OWNED_CONTEXTS_CLOSED';raise error from None
        result['cleanup']='OWNED_CONTEXTS_CLOSED';return result

    def close(self):
        if self.closed:return
        if self.unknown:return
        while self.owned:
            context,free,kind=self.owned[-1]
            try:need(self.call(free,context,cleanup=True)!=0,'CONTEXT_FREE_REFUSED')
            except BaseException:self.retain();raise
            self.owned.pop()
        self.buffers.clear();self.closed=True


if __name__=='__main__':
    print(json.dumps(plan()));raise SystemExit(2)
