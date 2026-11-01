"""Shared stdlib-only Authenticode verification; no native work at import.

This core emits no installation/identity/acceptance capability. Production and
read-only diagnostic receivers supply separate, bounded lifetime implementations.
The verification flags, signer/publisher/root rules and original CLOSE are shared.
"""
import ctypes as C
from hashlib import sha256
import uuid
from .controller import CandidateRefused
from .crt_pe import CRT_DLLS

P=C.c_void_p;D=C.c_uint32;B=C.c_int32
ROOT_SHA256='847df6a78497943f27fc72eb93f9a637320a02b561d0a91b09e87a7807ed7c61'


class CRTRefused(CandidateRefused):
    def __init__(self):super().__init__('SYSTEM_CRT_PREREQUISITE_UNVERIFIED')


class SignatureRejected(CRTRefused):
    """Known WinTrust return code AFTER known successful state close."""
    def __init__(self,status):
        self.status=status&0xffffffff
        super().__init__()


TRUST_PHASES=('VERIFY','PROVIDER_STATE','PROVIDER_DATA','SIGNER_DATA','SIGNER_LAYOUT','SIGNER_POLICY',
    'CERTIFICATE_DATA','CERTIFICATE_LAYOUT','CERTIFICATE_POLICY','CERTIFICATE_DER',
    'PUBLISHER_QUERY','PUBLISHER_VALUE','ROOT_PIN','CLOSE')
TRUST_ACTIVITIES=('WORK_BUDGET','CALL','CHECK','CLEANUP_BUDGET')
TRUST_CLOSE=('NOT_NEEDED','RETURNED_SUCCESS','UNKNOWN')


class CRTTrustFailure(CRTRefused):
    """Fixed diagnostic facts only; no names, certificates, paths or secrets."""
    def __init__(self,stage,activity,verify_returned,verify_ok,close_outcome,image_name=None):
        if (type(stage) is not str or stage not in TRUST_PHASES
                or type(activity) is not str or activity not in TRUST_ACTIVITIES
                or type(verify_returned) is not bool or verify_ok is not None and type(verify_ok) is not bool
                or type(close_outcome) is not str or close_outcome not in TRUST_CLOSE):raise CRTRefused()
        self.stage=stage;self.activity=activity;self.verify_returned=verify_returned
        self.verify_ok=verify_ok;self.close_outcome=close_outcome
        self.image_name=image_name if type(image_name) is str and image_name in CRT_DLLS else None
        super().__init__()


def need(ok):
    if not ok:raise CRTRefused()


class FileTrust(C.Structure):
    _fields_=[('size',D),('path',C.c_wchar_p),('file',P),('subject',P)]


class TrustChoice(C.Union):
    _fields_=[('file',C.POINTER(FileTrust)),('catalog',P)]


class TrustData(C.Structure):
    _anonymous_=('subject',)
    _fields_=[('size',D),('policy',P),('sip',P),('ui',D),('revocation',D),('choice',D),
              ('subject',TrustChoice),('action',D),('state',P),('url',P),('flags',D),('context',D),('settings',P)]


class Signer(C.Structure):
    _fields_=[('size',D),('time_low',D),('time_high',D),('count',D),('certs',P),('type',D),
              ('signer',P),('error',D),('counter_count',D),('counter',P),('chain',P)]


class CertContext(C.Structure):
    _fields_=[('encoding',D),('der',P),('length',D),('info',P),('store',P)]


class ProviderCert(C.Structure):
    _fields_=[('size',D),('cert',C.POINTER(CertContext)),('commercial',B),('root',B),
              ('self_signed',B),('test',B),('revoked',D),('confidence',D),('error',D),
              ('trust_list',P),('trust_signer',B),('ctl',P),('ctl_error',D),('cyclic',B),('element',P)]


def bind(lib,name,result,args):
    f=getattr(lib,name);f.restype=result;f.argtypes=args;return f


class SignatureVerification:
    def _signature(self,h,path,*,image_name=None,delegation=None,deadline=None):
        file=FileTrust(C.sizeof(FileTrust),path,h,None)
        data=TrustData();data.size=C.sizeof(data);data.ui=2;data.revocation=1;data.choice=1
        data.file=C.pointer(file);data.action=1;data.flags=0x80|0x1000|0x2000
        return self._verify_trust(data,(file,),image_name=image_name,delegation=delegation,deadline=deadline)

    def _verify_trust(self,data,owners,*,image_name=None,delegation=None,deadline=None):
        """Original strict trust rules, original deadlines and safe diagnostics.

        A returned zero VERIFY alone is not publisher/root acceptance. Only a
        clean known NO_SIGNATURE with known CLOSE may select catalog fallback.
        CLOSE uses the original source cleanup budget even after work expires.
        """
        action=C.create_string_buffer(uuid.UUID('00aac56b-cd44-11d0-8cc2-00c04fc295ee').bytes_le)
        calls=[];retained=(action,data,owners,calls)
        primary=close_error=None;roots=None;stage='VERIFY';activity='WORK_BUDGET';close_activity='CLEANUP_BUDGET'
        verify_started=verify_returned=False;verify_ok=None;close_outcome='NOT_NEEDED';signature_end=deadline
        def work(next_stage,fn,*args):
            nonlocal stage,activity,verify_started,signature_end
            stage=next_stage;activity='WORK_BUDGET'
            signature_end=self._signature_budget(delegation,signature_end)
            activity='CALL';calls.append((fn,args))  # Keep original pointed storage.
            if next_stage=='VERIFY':verify_started=True
            result=fn(*args);activity='CHECK';return result
        try:
            status=work('VERIFY',self.wvt,P(-1),action,C.byref(data))
            verify_returned=True;verify_ok=status==0
            if status!=0:raise SignatureRejected(status)
            stage='PROVIDER_STATE';need(data.state)
            provider=work('PROVIDER_DATA',self.provider,data.state);need(provider)
            signer=work('SIGNER_DATA',self.signer,provider,0,False,0);need(signer)
            stage='SIGNER_LAYOUT';need(signer.contents.size==C.sizeof(Signer))
            stage='SIGNER_POLICY';need(signer.contents.error==0
                 and 2<=signer.contents.count<=8 and not signer.contents.type&0x10)
            roots=[]
            for index in range(signer.contents.count):
                cert=work('CERTIFICATE_DATA',self.cert,signer,index);need(cert)
                stage='CERTIFICATE_LAYOUT';row=cert.contents;need(row.size==C.sizeof(ProviderCert) and row.cert)
                stage='CERTIFICATE_POLICY';need(not row.test and not row.cyclic and not row.error and not row.revoked)
                stage='CERTIFICATE_DER';context=row.cert.contents;need(context.der and 0<context.length<=65536)
                roots.append(sha256(C.string_at(context.der,context.length)).hexdigest())
                if index==0:
                    oid=C.create_string_buffer(b'2.5.4.10');name=C.create_unicode_buffer(256)
                    n=work('PUBLISHER_QUERY',self.cert_name,row.cert,3,0,oid,name,len(name))
                    stage='PUBLISHER_VALUE';need(1<n<len(name) and name.value=='Microsoft Corporation')
            stage='ROOT_PIN';need(roots[-1]==self._signature_root())
        except BaseException as error:primary=error
        finally:
            if verify_started:
                try:
                    self._signature_cleanup_budget(delegation)
                    data.action=2
                    close_activity='CALL';closed=self.wvt(P(-1),action,C.byref(data))
                    close_activity='CHECK';need(closed==0)
                    close_outcome='RETURNED_SUCCESS'
                except BaseException as error:
                    close_error=error;close_outcome='UNKNOWN'
                    self.unknown.append(retained);self.failed=True
                    self._retain_trust_unknown()
        if close_error is not None:
            failure=CRTTrustFailure('CLOSE',close_activity,
                verify_returned,verify_ok,close_outcome,image_name)
            cause=BaseExceptionGroup('CRT_TRUST_AND_CLOSE_UNKNOWN',[primary,close_error]) if primary is not None else close_error
            raise failure from cause
        if primary is not None:
            if type(primary) is SignatureRejected:raise primary from None
            raise CRTTrustFailure(stage,activity,verify_returned,verify_ok,close_outcome,
                image_name) from primary
        return tuple(roots)

