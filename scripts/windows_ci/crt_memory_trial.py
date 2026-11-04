"""Not-enabled one-run memory CRL diagnostic, never business/production trial.

A future separately approved job must use this exact frozen source. There is no
workflow activation in this change. Current-user/system/URL stores are never
written. Original strict refusals remain refusals in both probe observations.
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
from scripts.windows_ci.crt_memory_revocation import MemoryFileProbe,MemoryRevocation,original_constraints,FILE_PINS
from scripts.windows_ci.crt_fixed_http import FixedCRLFetcher,FetchRefused
from scripts.windows_ci.crt_crl_preparation import PreparationRefused,CDP,need,current_window
from scripts.windows_ci.crt_certificate_metadata import certificate
from scripts.windows_ci.crt_memory_revocation import all_current
from scripts.windows_ci.crt_signature_readonly import ReadOnlyAudit

EXTRA=frozenset(('WinHttpOpen','WinHttpConnect','WinHttpOpenRequest','WinHttpSetOption','WinHttpSetTimeouts',
    'WinHttpSendRequest','WinHttpReceiveResponse','WinHttpQueryHeaders','WinHttpReadData','WinHttpCloseHandle',
    'CertCreateCertificateContext','CertCreateCRLContext','CertFreeCertificateContext','CertFreeCRLContext',
    'CryptVerifyCertificateSignatureEx','CertOpenStore','CertAddCertificateContextToStore','CertAddCRLContextToStore',
    'CertCloseStore','CertVerifyRevocation'))
_retained=[]


class MemoryAudit(ReadOnlyAudit):
    def __call__(self,event,args):
        if event=='ctypes.dlopen' and args[0].lower()=='winhttp.dll':return
        if event=='ctypes.dlsym' and args[1] in EXTRA:return
        return super().__call__(event,args)


def plan():
    return dict(status='NOT_ENABLED',route='ISOLATED_MEMORY_CRL_CONJUNCTION_CANDIDATE',url=CDP,
        windows_job_minutes=3,work_seconds=120,cleanup_seconds=15,fetch_seconds=15,max_bytes=16777216,
        network_requires_specific_execution_approval=True,workflow_enabled=False,
        explicit_persistent_store_write_calls=False,os_internal_disk_side_effects='NOT_AUDITED',production_connected=False,
        equivalent_or_stronger_proven=False,usable_product=False)


def collect_once():
    start=time.monotonic();work_end=start+120;cleanup_end=work_end+15
    probes=[];before=[];after=[];memory=None;primary=None;cleanup=[];comparison=None;fetch_facts=None;phase='ORIGINAL_BEFORE'
    def probe(name,target):
        value=MemoryFileProbe(work_end,cleanup_end);probes.append(value)
        try:observed=value.inspect(name)
        except BaseException:
            observed=dict(value.result);observed.update(state_snapshot=value.state_snapshot.export(),wintrust_returns=list(value.returns))
            target.append((value,observed));raise
        target.append((value,observed));original_constraints(value)
    try:
        # Keep original read-only file handles pinned across the fetch and all
        # independent checks. Every WVT state is closed by the unchanged core.
        for name in sorted(FILE_PINS):
            probe(name,before)
        source=before[0][0].state_snapshot
        need(all(p.state_snapshot.der==source.der and p.state_snapshot.ca_crl==source.ca_crl for p,row in before),
            'ORIGINAL_CERTIFICATES_OR_CA_CRL_DIFFER')
        phase='FIXED_HTTP_FETCH';fetcher=FixedCRLFetcher(work_end,cleanup_end);leaf_crl=fetcher.fetch()
        fetch_facts=dict(url=CDP,bytes=len(leaf_crl),sha256=sha256(leaf_crl).hexdigest(),
            redirect_policy='NEVER',authentication='DISABLED',url_cache_write='NOT_CALLED')
        phase='MEMORY_CONJUNCTION';verifier=MemoryRevocation(work_end,cleanup_end);memory=verifier.check(source,leaf_crl)
        phase='ORIGINAL_AFTER'
        for name in sorted(FILE_PINS):
            probe(name,after)
        for (a,old),(b,new) in zip(before,after):
            need(a.initial_identity==b.initial_identity and old['sha256']==new['sha256']
                and a.state_snapshot.der==b.state_snapshot.der and a.state_snapshot.ca_crl==b.state_snapshot.ca_crl,
                'HELD_ORIGINAL_FILE_OR_CERTIFICATES_CHANGED')
        comparison='SAME_HELD_FILE_IDENTITIES_BYTES_SELECTED_CERTIFICATES_AND_CA_CRL'
    except PreparationRefused as error:primary=dict(category='MEMORY_EVIDENCE_REFUSED',reason=error.reason,cleanup=error.cleanup,
        stage=getattr(error,'stage',None),index=getattr(error,'index',None),native_error=getattr(error,'native_error',None),
        revocation_status=getattr(error,'revocation_status',[]),cleanup_reason=error.cleanup_reason,
        cleanup_native_error=getattr(error,'cleanup_native_error',None),cleanup_kind=getattr(error,'cleanup_kind',None))
    except FetchRefused as error:primary=dict(category='FIXED_FETCH_REFUSED',reason=error.reason,cleanup=error.cleanup)
    except BaseException:primary=dict(category='DIAGNOSTIC_REFUSED_OR_UNKNOWN',reason='UNLISTED_DIAGNOSTIC_FAILURE')
    finally:
        if primary is not None:primary['phase']=phase
        for index,value in reversed(list(enumerate(probes))):
            try:state=value.close()
            except BaseException:state='UNKNOWN'
            cleanup.append(dict(probe_index=index,file=value.result.get('file'),status=state))
            if state!='OWNED_FILE_HANDLES_CLOSED':_retained.append(value)
    if any(x['status']!='OWNED_FILE_HANDLES_CLOSED' for x in cleanup):
        if primary is None:primary=dict(category='ORIGINAL_FILE_CLEANUP_UNKNOWN',reason='UNKNOWN',phase='ORIGINAL_FILE_CLEANUP')
    if primary is None:
        try:
            need(time.monotonic()<work_end,'WORK_DEADLINE')
            all_current([certificate(x) for x in before[0][0].state_snapshot.der])
            for policy in memory['crl_policy']:current_window(policy['this_update_filetime'],policy['next_update_filetime'])
        except PreparationRefused as error:primary=dict(category='FINAL_FRESHNESS_REFUSED',reason=error.reason,phase='FINAL_FRESHNESS')
    result=dict(scope='ISOLATED_MEMORY_CRL_DIAGNOSTIC_NOT_NATIVE_BUSINESS',source_commit=os.environ.get('GITHUB_SHA'),
        status='CANDIDATE_CONJUNCTION_OBSERVED_NOT_ADMITTED' if primary is None else 'REFUSED_OR_UNKNOWN_NO_RETRY',
        seconds=round(time.monotonic()-start,3),before=[x for p,x in before],after=[x for p,x in after],
        fetched_leaf_crl=fetch_facts,independent_memory_checks=memory,file_comparison=comparison,failure=primary,original_file_cleanup=cleanup,
        original_strict_results='PRESERVED_NOT_REWRITTEN',equivalent_or_stronger_proven=False,
        production_admission='NOT_CONNECTED',usable_product=False,explicit_persistent_store_write_calls=False,
        os_internal_disk_side_effects='NOT_AUDITED')
    return result,0 if primary is None else 2


def main(argv=None):
    argv=sys.argv[1:] if argv is None else argv
    if argv!=['--inspect-memory-once']:
        print(json.dumps(plan()));return 2
    expected=dict(GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Windows',
        GITHUB_REPOSITORY='T1doo/ParkWeave',GITHUB_REF='refs/heads/dev/local-product-runtime-20261028',
        GITHUB_JOB='crt-memory-candidate',GITHUB_EVENT_NAME='push',GITHUB_RUN_ATTEMPT='1',PW_MEMORY_PUBLIC='true')
    need(os.name=='nt' and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
        and C.sizeof(C.c_void_p)==8 and all(os.environ.get(k)==v for k,v in expected.items())
        and re.fullmatch('[a-f0-9]{40}',os.environ.get('GITHUB_SHA','')) is not None,'FUTURE_EXACT_READONLY_CI_REQUIRED')
    need(not any(n in sys.modules for n in ('psycopg','parkweave.store','scripts.windows_portable.native_system_crt',
        'scripts.windows_portable.native_trial_authority','scripts.windows_portable.native_instance_security')),'NO_BUSINESS_FACTORY')
    sys.addaudithook(MemoryAudit());result,code=collect_once();print(json.dumps(result));return code


if __name__=='__main__':
    try:code=main()
    except PreparationRefused as error:
        print(json.dumps(dict(status='NOT_EXECUTED',reason=error.reason,usable_product=False)));code=2
    except BaseException:
        print(json.dumps(dict(status='REFUSED_OR_UNKNOWN_NO_RETRY',reason='UNLISTED_ENTRY_FAILURE',usable_product=False)));code=2
    raise SystemExit(code)
