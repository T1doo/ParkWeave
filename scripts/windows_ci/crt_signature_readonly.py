"""One read-only System32 signature diagnostic; never a business trial/grant.

VERIFY/CLOSE allocate/free process-local WinTrust state. Cache-only policy is
unchanged; this does not claim that Windows internals leave no cache/audit data.
No source path, DLL name, trust store, identity or permission is caller supplied.
"""
import ctypes as C
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import sys
import time

if __package__ in (None,''):
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from scripts.windows_portable import authenticode_signature as trust
from scripts.windows_ci.crt_state_snapshot import StateSnapshot

BEFORE='db62db90abbbecab743cd24e946c8363e8b29f28'
MARKER='ci: read-only CRT state snapshot PW_CRT_RO_20261101_B'
JOB='crt-signature-readonly'
NATIVE_SYMBOLS=frozenset(('GetSystemDirectoryW','GetCurrentProcess','IsWow64Process2','CreateFileW',
    'GetFileInformationByHandle','ReadFile','CloseHandle','WinVerifyTrust','WTHelperProvDataFromStateData',
    'WTHelperGetProvSignerFromChain','WTHelperGetProvCertFromChain','CertGetNameStringW'))
_unknown=[]
P=C.c_void_p;D=C.c_uint32;B=C.c_int32


def need(value):
    if not value:raise RuntimeError('READONLY_CRT_DIAGNOSTIC_REFUSED')


class FileTime(C.Structure):_fields_=[('low',D),('high',D)]
class FileInfo(C.Structure):
    _fields_=[('attributes',D),('created',FileTime),('accessed',FileTime),('written',FileTime),
        ('volume',D),('size_high',D),('size_low',D),('links',D),('index_high',D),('index_low',D)]


class ReadOnlySignature(trust.SignatureVerification):
    """Separate receiver, never a NativeSystemCRT or installation capability."""
    def __init__(self,work_end,cleanup_end):
        need(os.name=='nt' and C.sizeof(P)==8 and sys.version_info>=(3,12))
        self.deadline=min(work_end,time.monotonic()+30);self.cleanup_end=cleanup_end
        self.failed=False;self.unknown=[];self.handles=[];self.pending=None
        self.result={}
        self.returns=[];self.chain=[];self.signer_facts=None;self.chain_observation='NOT_REACHED'
        self.signer_observation='NOT_REACHED';self.root_policy_reached=False
        self.state_snapshot=StateSnapshot(self)
        self.k=C.WinDLL('kernel32.dll',use_last_error=True,winmode=0x800)
        bind=trust.bind
        self.system=bind(self.k,'GetSystemDirectoryW',D,[C.c_wchar_p,D])
        self.current=bind(self.k,'GetCurrentProcess',P,[])
        self.arch=bind(self.k,'IsWow64Process2',B,[P,C.POINTER(C.c_uint16),C.POINTER(C.c_uint16)])
        self.open=bind(self.k,'CreateFileW',P,[C.c_wchar_p,D,D,P,D,D,P])
        self.info=bind(self.k,'GetFileInformationByHandle',B,[P,C.POINTER(FileInfo)])
        self.read=bind(self.k,'ReadFile',B,[P,P,D,C.POINTER(D),P])
        self.close_handle=bind(self.k,'CloseHandle',B,[P])
        self.trust=C.WinDLL('wintrust.dll',use_last_error=True,winmode=0x800)
        self.crypto=C.WinDLL('crypt32.dll',use_last_error=True,winmode=0x800)
        self.native_wvt=bind(self.trust,'WinVerifyTrust',C.c_int32,[P,P,C.POINTER(trust.TrustData)])
        self.native_provider=bind(self.trust,'WTHelperProvDataFromStateData',P,[P])
        self.native_signer=bind(self.trust,'WTHelperGetProvSignerFromChain',C.POINTER(trust.Signer),[P,D,B,D])
        self.native_cert=bind(self.trust,'WTHelperGetProvCertFromChain',C.POINTER(trust.ProviderCert),[C.POINTER(trust.Signer),D])
        self.cert_name=bind(self.crypto,'CertGetNameStringW',D,[C.POINTER(trust.CertContext),D,D,P,C.c_wchar_p,D])

    def _signature_root(self):
        self.root_policy_reached=True;return trust.ROOT_SHA256
    def _signature_budget(self,delegation,deadline):
        need(delegation is None and deadline is None and not self.failed and not self.unknown
            and time.monotonic()<self.deadline)
    def _signature_cleanup_budget(self,delegation):
        need(delegation is None and time.monotonic()<self.cleanup_end)
    def _retain_trust_unknown(self):
        if self not in _unknown:_unknown.append(self)

    def call(self,fn,*args):
        self._signature_budget(None,None);self.pending=(fn,args)
        try:
            result=fn(*args)
            if not result and C.get_last_error()==997:raise RuntimeError('READONLY_CALL_PENDING_UNKNOWN')
        except BaseException:
            self.unknown.append(self.pending);self.failed=True;self._retain_trust_unknown();raise
        self.pending=None;return result

    def wvt(self,hwnd,action,data):
        # Observe raw LONGs only; return the exact value to the shared verifier.
        phase=data._obj.action
        if phase==2:self.state_snapshot.deactivate()
        status=self.native_wvt(hwnd,action,data)
        need(type(status) is int and -(2**31)<=status<2**31)
        self.returns.append(dict(action='VERIFY' if phase==1 else 'CLOSE',signed=status,hex=f'{status&0xffffffff:08x}'))
        if phase==1:self.state_snapshot.activate(data._obj,status)
        return status

    def provider(self,state):
        result=self.native_provider(state)
        self.state_snapshot.capture_provider(result,state)
        return result

    def signer(self,*args):
        result=self.native_signer(*args)
        try:
            if result:
                row=result.contents;self.signer_facts=dict(size=row.size)
                if row.size==C.sizeof(trust.Signer):
                    self.signer_facts.update(count=row.count,error=row.error,kind=row.type)
                    self.signer_observation='BOUNDED_PROVIDER_SUMMARY'
                    self.state_snapshot.capture_signer(result)
                else:self.signer_observation='SIZE_MISMATCH'
        except Exception:self.signer_observation='SUMMARY_UNAVAILABLE'
        return result

    def cert(self,signer,index):
        result=self.native_cert(signer,index)
        # Bounded public certificate summary, no subject, DER or native address.
        # Inspection cannot change the shared verifier's original return value.
        try:
            if result and 0<=index<8:
                row=result.contents
                if row.size==C.sizeof(trust.ProviderCert) and row.cert:
                    context=row.cert.contents
                    if context.der and 0<context.length<=65536:
                        self.chain.append(dict(index=index,sha256=sha256(C.string_at(context.der,context.length)).hexdigest(),
                            error=row.error,revocation_reason=row.revoked,test=bool(row.test),cyclic=bool(row.cyclic)))
                        self.chain_observation='BOUNDED_PROVIDER_SUMMARY'
        except Exception:self.chain_observation='SUMMARY_UNAVAILABLE'
        return result

    def identity(self,handle):
        row=FileInfo();need(self.call(self.info,handle,C.byref(row)))
        size=(row.size_high<<32)|row.size_low
        need(not row.attributes&(0x400|0x10) and row.links>=1 and 0<size<=128*1024*1024)
        return (row.attributes,row.volume,row.index_high,row.index_low,size,row.links,row.written.high,row.written.low)

    def inspect(self,name):
        need(name in trust.CRT_DLLS and not self.handles)
        machine,native=C.c_uint16(),C.c_uint16()
        process=self.call(self.current)
        need(self.call(self.arch,process,C.byref(machine),C.byref(native)) and machine.value==0 and native.value==0x8664)
        directory=C.create_unicode_buffer(4096);n=self.call(self.system,directory,len(directory))
        need(0<n<len(directory) and directory.value.lower().endswith('\\system32'))
        path=C.create_unicode_buffer(directory.value.rstrip('\\')+'\\'+name)
        # GENERIC_READ, SHARE_READ, OPEN_EXISTING, OPEN_REPARSE_POINT. No write,
        # DELETE, WRITE_DAC, WRITE_OWNER, CREATE, token or registry operations.
        handle=self.call(self.open,path,0x80000000,1,None,3,0x200000,None)
        need(handle not in (None,0,P(-1).value));self.handles.append(handle)
        before=self.identity(handle);remaining=before[4];digest=sha256()
        while remaining:
            buffer=C.create_string_buffer(min(1024*1024,remaining));used=D()
            need(self.call(self.read,handle,buffer,len(buffer),C.byref(used),None) and 0<used.value<=len(buffer))
            digest.update(buffer.raw[:used.value]);remaining-=used.value
        result=self.result=dict(file=name,bytes=before[4],sha256=digest.hexdigest(),verification='NOT_COMPLETED')
        try:
            roots=self._signature(handle,path.value,image_name=name)
            result.update(verification='STRICT_SHARED_SIGNATURE_CHECK_PASSED',chain_sha256=list(roots))
        except trust.SignatureRejected as error:
            result.update(verification='SIGNATURE_REJECTED',returned_status=f'{error.status:08x}')
        except trust.CRTTrustFailure as error:
            result.update(verification='REFUSED_OR_UNKNOWN',stage=error.stage,activity=error.activity,
                verify_returned=error.verify_returned,verify_returned_zero=error.verify_ok,wvt_close=error.close_outcome,
                execution_uncertain=not error.verify_returned or error.close_outcome!='RETURNED_SUCCESS')
        if result.get('execution_uncertain',False) or self.unknown:
            result['metadata_after']='NOT_ATTEMPTED_UNKNOWN'
        else:
            need(self.identity(handle)==before);result['metadata_after']='UNCHANGED'
        root_match=None
        if result['verification']=='STRICT_SHARED_SIGNATURE_CHECK_PASSED':root_match=True
        elif (self.root_policy_reached and self.signer_facts and self.chain
                and len(self.chain)==self.signer_facts.get('count') and self.chain_observation=='BOUNDED_PROVIDER_SUMMARY'):
            root_match=self.chain[-1]['sha256']==trust.ROOT_SHA256
        result.update(wintrust_returns=list(self.returns),signer=self.signer_facts,provider_chain=list(self.chain),
            signer_observation=self.signer_observation,chain_observation=self.chain_observation,
            root_policy_reached=self.root_policy_reached,expected_root_matched=root_match,state_snapshot=self.state_snapshot.export())
        return result

    def close(self):
        need(not getattr(self,'close_attempted',False));self.close_attempted=True
        if self.unknown:self._retain_trust_unknown();return 'UNKNOWN_RETAINED_NO_CLOSE'
        for handle in reversed(self.handles):
            try:
                self._signature_cleanup_budget(None);self.pending=(self.close_handle,(handle,))
                need(self.close_handle(handle))
            except BaseException:
                self.unknown.append(self.pending);self._retain_trust_unknown();raise
            self.pending=None
        self.handles.clear();return 'OWNED_FILE_HANDLES_CLOSED'


class ReadOnlyAudit:
    def __call__(self,event,args):
        if event=='open':
            mode=args[1] if len(args)>1 else None;flags=args[2] if len(args)>2 else 0
            need(not(type(mode) is str and any(c in mode for c in 'wax+')) and not(type(flags) is int and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
        elif event=='ctypes.dlopen':need(args[0].lower() in ('kernel32.dll','wintrust.dll','crypt32.dll'))
        elif event=='ctypes.dlsym':need(args[1] in NATIVE_SYMBOLS)
        elif event.startswith(('subprocess.','socket.','winreg.')) or event in ('os.system','os.mkdir','os.remove','os.rename','os.chmod','os.putenv','os.unsetenv'):
            need(False)


def main(argv=None):
    if argv is None:argv=sys.argv[1:]
    if argv!=['--run-readonly']:
        print(json.dumps(dict(status='NOT_RUN',native_acceptance='NOT_ACCEPTED',usable_product=False)));return 2
    expected=dict(GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Windows',
        GITHUB_REPOSITORY='T1doo/ParkWeave',GITHUB_REF='refs/heads/dev/local-product-runtime-20261028',
        GITHUB_JOB=JOB,GITHUB_EVENT_NAME='push',GITHUB_RUN_ATTEMPT='1',PW_RO_PUBLIC='true',
        PW_RO_BEFORE=BEFORE,PW_RO_MESSAGE=MARKER)
    need(os.name=='nt' and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
        and all(os.environ.get(k)==v for k,v in expected.items())
        and re.fullmatch('[a-f0-9]{40}',os.environ.get('GITHUB_SHA','')) is not None)
    need(not any(n in sys.modules for n in ('psycopg','parkweave.store','scripts.windows_portable.native_system_crt',
        'scripts.windows_portable.native_trial_authority','scripts.windows_portable.native_instance_security')))
    sys.addaudithook(ReadOnlyAudit())
    result,code=collect()
    print(json.dumps(result));return code


def collect():
    """Bounded diagnostic orchestration; no acceptance issuance on any result."""
    start=time.monotonic();work_end=start+80;cleanup_end=start+90;rows=[];unknown=False
    for name in sorted(trust.CRT_DLLS):
        context=None;row=dict(file=name,verification='NOT_COMPLETED')
        try:
            context=ReadOnlySignature(work_end,cleanup_end);row=context.inspect(name)
        except BaseException:
            unknown=True
            if context is not None:
                row.update(context.result)
                row.update(wintrust_returns=list(context.returns),signer=context.signer_facts,provider_chain=list(context.chain))
                row['state_snapshot']=context.state_snapshot.export()
            row['diagnostic_error']='BOUNDED_READONLY_OPERATION_REFUSED_OR_UNKNOWN'
        finally:
            if context is not None:
                try:row['file_cleanup']=context.close()
                except BaseException:row['file_cleanup']='UNKNOWN';unknown=True
                unknown=unknown or bool(context.unknown) or row.get('execution_uncertain',False)
        rows.append(row)
        if unknown:break
    result=dict(scope='READONLY_SYSTEM_CRT_SIGNATURE_DIAGNOSTIC',status='UNKNOWN_STOP_NO_RETRY' if unknown else 'READONLY_DIAGNOSTIC_COMPLETED',
        source_commit=os.environ.get('GITHUB_SHA'),rows=rows,seconds=round(time.monotonic()-start,3),
        security_settings_changed=False,business_factory_activated=False,native_acceptance='NOT_ACCEPTED',usable_product=False)
    return result,2 if unknown else 0


if __name__=='__main__':raise SystemExit(main())
