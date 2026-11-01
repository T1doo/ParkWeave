"""Prepared, NOT ENABLED: native URL cache retrieval then original strict WVT.

This route explicitly permits opaque native redirects and temporary-account
Cryptnet cache writes. It does not implement the withdrawn no-redirect plan.
No native work occurs at import or default entry. A future exact source-bound
workflow and specific execution scope are required; env checks issue no grant.
"""
import ctypes as C
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sys
import time
if __package__ in (None,''):sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.windows_ci.crt_crl_preparation import (OwnedCRLValidator,CRLContext,PreparationRefused,
    CDP,MAX_BYTES,need,bind_inputs,current_window)
from scripts.windows_ci.crt_memory_revocation import MemoryFileProbe,original_constraints,FILE_PINS,CERT_PINS
from scripts.windows_ci.crt_signature_readonly import ReadOnlyAudit
from scripts.windows_ci.crt_state_snapshot import FileTime
from scripts.windows_portable import authenticode_signature as trust

P=C.c_void_p;D=C.c_uint32;B=C.c_int32
FLAGS=0x4|0x20|0x20000  # WIRE_ONLY | VERIFY_CONTEXT_SIGNATURE | NO_AUTH
_retained=[]


class RetrieveAux(C.Structure):
    _fields_=[('size',D),('last_sync',P),('max_bytes',D),('prefetch',P),('flush',P),('response',P),
        ('prefix',P),('resync',P),('proxy_cache',B),('http_status',D),('error_headers',P),('error_content',P)]


class CacheAudit(ReadOnlyAudit):
    def __call__(self,event,args):
        if event=='ctypes.dlopen' and args[0].lower()=='cryptnet.dll':return
        if event=='ctypes.dlsym' and args[1] in ('CryptRetrieveObjectByUrlW','CertCreateCertificateContext',
            'CertCreateCRLContext','CertFreeCertificateContext','CertFreeCRLContext','CryptVerifyCertificateSignatureEx'):return
        return super().__call__(event,args)


class NativeCachedCRL(OwnedCRLValidator):
    def __init__(self,work_end,cleanup_end):
        super().__init__(work_end,cleanup_end)
        self.net=C.WinDLL('cryptnet.dll',use_last_error=True,winmode=0x800)
        self.get=trust.bind(self.net,'CryptRetrieveObjectByUrlW',B,
            [C.c_wchar_p,P,D,D,C.POINTER(P),P,P,P,C.POINTER(RetrieveAux)])
        self.started=False;self.native_returned=False;self.native_error=None;self.http_status=None

    def acquire(self,source):
        need(original_constraints(source.owner) is source and source.request is None,'ORIGINAL_SOURCE_REQUIRED')
        leaf,issuer=bind_inputs(source.der[0],source.der[1],CDP,self.guard)
        primary=None;result=None
        try:
            buffer=C.create_string_buffer(source.der[1]);self.buffers.append(buffer)
            signer=self.call(self.create_cert,1,buffer,len(source.der[1]))
            need(bool(signer),'ISSUER_CONTEXT_CREATE_REFUSED');self.owned.append((signer,self.free_cert,'CERT'))
            row=signer.contents
            need(row.der and row.length==len(source.der[1]) and C.string_at(row.der,row.length)==source.der[1],
                'ISSUER_CONTEXT_BYTES_DIFFER')
            output=P();sync=FileTime();aux=RetrieveAux();aux.size=C.sizeof(aux)
            aux.last_sync=C.addressof(sync);aux.max_bytes=MAX_BYTES
            url=C.create_unicode_buffer(CDP)
            # Optional allocated-response/error outputs remain NULL; no hidden
            # allocations with a second cleanup API are requested.
            self.buffers.append((output,sync,aux,url,signer))
            timeout=min(15000,int((self.deadline-time.monotonic())*1000));need(timeout>0,'WORK_DEADLINE')
            self.guard();self.started=True
            good=self.call(self.get,url,P(2),FLAGS,timeout,C.byref(output),None,None,
                C.cast(signer,P),C.byref(aux))
            self.native_returned=True
            if not good and output.value:
                # Failed-return ppvObject ownership is not documented. Do not
                # guess it is a successful CRL context, free or inspect it.
                self.retain();raise PreparationRefused('FAILED_RETRIEVAL_OUTPUT_OWNERSHIP_UNKNOWN')
            if output.value:
                context=C.cast(output,C.POINTER(CRLContext))
                self.owned.append((context,self.free_crl,'CRL'))
            # Ownership precedes diagnostic reads, too: failures in a last-error
            # seam or future auxiliary interpretation must not strand output.
            code=C.get_last_error() if not good else None
            self.native_error=f'{code&0xffffffff:08x}' if type(code) is int else None
            self.http_status=int(aux.http_status) or None
            need(good and output.value,'NATIVE_RETRIEVAL_REFUSED')
            self.guard();row=context.contents
            need(row.der and 0<row.length<=MAX_BYTES,'RETRIEVED_CRL_BOUNDS')
            raw=C.string_at(row.der,row.length)
            # The API's signature flag is not treated as our full policy check,
            # nor as a promise cache writes waited for these later checks.
            need(self.call(self.verify,None,1,3,context,2,signer,1,None),'CRL_SIGNATURE_REFUSED')
            policy=self.check_crl(context,leaf,issuer);need(not policy['leaf_listed'],'CURRENT_CERTIFICATE_REVOKED')
            result=dict(crl_sha256=sha256(raw).hexdigest(),bytes=len(raw),policy=policy,
                native_signature_requested=True,automatic_authentication='INHIBITED',
                redirects='NATIVE_OPAQUE_MAY_FOLLOW',final_url='NOT_OBSERVED',
                cache_effect='MAY_HAVE_WRITTEN_TEMPORARY_ACCOUNT_CRYPTNET_CACHE',
                last_sync_filetime=str((sync.high<<32)|sync.low),native_timeout_ms=timeout,
                requested_byte_limit=MAX_BYTES)
        except PreparationRefused as error:primary=error
        except BaseException:primary=PreparationRefused('NATIVE_RETRIEVAL_INTERNAL_FAILURE')
        try:self.close()
        except BaseException:
            if primary is None:primary=PreparationRefused('RETRIEVAL_CLEANUP_UNKNOWN')
            primary.cleanup='UNKNOWN'
        if primary is not None:
            if primary.cleanup=='NOT_ATTEMPTED':primary.cleanup='UNKNOWN_RETAINED' if self.unknown else 'OWNED_CONTEXTS_CLOSED'
            primary.retrieval_started=self.started;primary.native_returned=self.native_returned
            primary.native_error=self.native_error;primary.native_http_status=self.http_status
            raise primary from None
        self.guard_after_close(result['policy'])
        result['cleanup']='OWNED_CONTEXTS_CLOSED';return result

    def guard_after_close(self,policy):
        try:
            need(time.monotonic()<self.deadline,'WORK_DEADLINE')
            current_window(policy['this_update_filetime'],policy['next_update_filetime'])
        except PreparationRefused as error:
            error.cleanup='OWNED_CONTEXTS_CLOSED';error.retrieval_started=self.started
            error.native_returned=self.native_returned;error.native_error=self.native_error;error.native_http_status=self.http_status
            raise


def plan():
    return dict(status='NOT_ENABLED',scope='NATIVE_URL_CACHE_THEN_UNCHANGED_STRICT_FILE_CHECK',url=CDP,
        job_minutes=3,work_seconds=120,cleanup_seconds=15,timeout_ms=15000,max_bytes=MAX_BYTES,
        redirects='MAY_FOLLOW_NOT_FULLY_OBSERVABLE',cache_write='TEMPORARY_ACCOUNT_POSSIBLE_EVEN_ON_FAILURE',
        no_auth_flag=True,no_cert_store_import=True,no_security_settings=True,business_factory=False,
        execution_scope_not_approved_here=True,workflow_enabled=False,usable_product=False)


def collect_once():
    start=time.monotonic();end=start+120;cleanup_end=end+15
    probes=[];before=[];after=[];acquired=None;retriever=None;failure=None;cleanup=[];phase='ORIGINAL_BEFORE'
    def inspect(name,rows):
        value=MemoryFileProbe(end,cleanup_end);probes.append(value)
        try:row=value.inspect(name)
        except BaseException:
            rows.append((value,dict(value.result)));raise
        rows.append((value,row))
        need(row.get('sha256')==FILE_PINS[name] and row.get('metadata_after')=='UNCHANGED'
            and not row.get('execution_uncertain',False),'FIXED_HELD_FILE_UNAVAILABLE')
        return value
    def selected_chain(probe,row):
        if row['verification']=='STRICT_SHARED_SIGNATURE_CHECK_PASSED':
            # These hashes are returned only after the original shared check
            # completed every cert, Publisher and RootPin. No CA-CRL copy is
            # required for a file that already satisfies that strict contract.
            values=row.get('chain_sha256')
            need(type(values) is list and tuple(values)==CERT_PINS,'STRICT_SELECTED_CHAIN_UNAVAILABLE')
            return tuple(values)
        source=original_constraints(probe)
        values=tuple(sha256(raw).hexdigest() for raw in source.der)
        need(values==CERT_PINS,'ORIGINAL_SELECTED_CHAIN_UNAVAILABLE')
        return values
    try:
        for name in sorted(FILE_PINS):inspect(name,before)
        selected_before=[selected_chain(p,row) for p,row in before]
        need(all(value==selected_before[0] for value in selected_before),'SELECTED_CHAINS_DIFFER')
        if not all(row['verification']=='STRICT_SHARED_SIGNATURE_CHECK_PASSED' for p,row in before):
            source=next(p.state_snapshot for p,row in before if row['verification']!='STRICT_SHARED_SIGNATURE_CHECK_PASSED')
            phase='NATIVE_CRYPTNET_RETRIEVAL';retriever=NativeCachedCRL(end,cleanup_end);acquired=retriever.acquire(source)
        phase='ORIGINAL_AFTER'
        for name in sorted(FILE_PINS):inspect(name,after)
        for i,((a,old),(b,new)) in enumerate(zip(before,after)):
            need(a.initial_identity==b.initial_identity and old['sha256']==new['sha256'],'HELD_FILE_OR_SELECTED_CERTIFICATES_CHANGED')
            need(new['verification']=='STRICT_SHARED_SIGNATURE_CHECK_PASSED','ORIGINAL_STRICT_CHECK_STILL_REFUSED')
            need(selected_chain(b,new)==selected_before[i],'HELD_FILE_OR_SELECTED_CERTIFICATES_CHANGED')
        need(time.monotonic()<end,'WORK_DEADLINE')
    except PreparationRefused as error:
        failure=dict(phase=phase,reason=error.reason,cleanup=error.cleanup,
            native_error=getattr(error,'native_error',None),native_http_status=getattr(error,'native_http_status',None))
    except BaseException:failure=dict(phase=phase,reason='UNLISTED_CACHE_TRIAL_FAILURE')
    finally:
        for i,probe in reversed(list(enumerate(probes))):
            try:state=probe.close()
            except BaseException:state='UNKNOWN'
            cleanup.append(dict(index=i,status=state))
            if state!='OWNED_FILE_HANDLES_CLOSED':_retained.append(probe)
    if any(x['status']!='OWNED_FILE_HANDLES_CLOSED' for x in cleanup):
        failure=failure or dict(phase='FILE_CLEANUP',reason='UNKNOWN')
    return dict(status='ORIGINAL_STRICT_CHECKS_PASSED_NOT_PRODUCT_ACCEPTANCE' if failure is None else 'REFUSED_OR_UNKNOWN_NO_RETRY',
        source_commit=os.environ.get('GITHUB_SHA'),seconds=round(time.monotonic()-start,3),
        before=[row for p,row in before],after=[row for p,row in after],retrieval=acquired,failure=failure,
        native_retrieval_started=bool(retriever and retriever.started),
        native_retrieval_returned=bool(retriever and retriever.native_returned),
        native_cache_effect='MAY_HAVE_OCCURRED' if retriever and retriever.started else 'NOT_REQUESTED',
        original_file_cleanup=cleanup,strict_implementation='UNCHANGED',usable_product=False),0 if failure is None else 2


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if argv!=['--inspect-native-cache-once']:print(json.dumps(plan()));return 2
    expected=dict(GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Windows',
        GITHUB_REPOSITORY='T1doo/ParkWeave',GITHUB_REF='refs/heads/dev/local-product-runtime-20261028',
        GITHUB_JOB='crt-cryptnet-cache-once',GITHUB_EVENT_NAME='push',GITHUB_RUN_ATTEMPT='1',
        PW_CRYPTNET_SCOPE='REDIRECTS_AND_TEMPORARY_URL_CACHE',PW_CRYPTNET_PUBLIC='true')
    need(os.name=='nt' and C.sizeof(P)==8 and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
        and all(os.environ.get(k)==v for k,v in expected.items())
        and re.fullmatch('[a-f0-9]{40}',os.environ.get('GITHUB_SHA','')) is not None,'EXACT_FUTURE_CACHE_TRIAL_REQUIRED')
    need(not any(x in sys.modules for x in ('psycopg','scripts.windows_portable.native_trial_authority',
        'scripts.windows_portable.native_instance_security')),'NO_BUSINESS_FACTORY')
    sys.addaudithook(CacheAudit());result,code=collect_once();print(json.dumps(result));return code


if __name__=='__main__':
    try:code=main()
    except PreparationRefused as error:print(json.dumps(dict(status='NOT_EXECUTED',reason=error.reason)));code=2
    except BaseException:print(json.dumps(dict(status='REFUSED_OR_UNKNOWN_NO_RETRY',reason='UNLISTED_ENTRY_FAILURE')));code=2
    raise SystemExit(code)
