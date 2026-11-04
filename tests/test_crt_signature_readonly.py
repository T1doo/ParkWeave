"""Read-only diagnostic boundary/protocol; never Windows signature evidence."""
import ctypes as C
import json,subprocess,sys,time
from pathlib import Path
from types import SimpleNamespace
import pytest

from scripts.windows_ci import crt_signature_readonly as diagnostic
from scripts.windows_portable import authenticode_signature as shared,native_system_crt as production


def test_shared_function_identity_and_stdlib_only_import_without_factory():
    assert diagnostic.ReadOnlySignature._verify_trust is production.NativeSystemCRT._verify_trust
    assert diagnostic.ReadOnlySignature._signature is production.NativeSystemCRT._signature
    assert production.ROOT_SHA256==shared.ROOT_SHA256
    assert not issubclass(diagnostic.ReadOnlySignature,production.NativeSystemCRT)
    root=Path(__file__).parents[1]
    code="import sys;sys.path.insert(0,sys.argv[1]);from scripts.windows_ci import crt_signature_readonly,native_failure_diagnostics;from scripts.windows_portable.authenticode_signature import CRTTrustFailure;assert native_failure_diagnostics.detail(CRTTrustFailure('VERIFY','CALL',False,None,'RETURNED_SUCCESS'),'CRTTrustFailure')['category']=='CRT_SIGNATURE_INSPECTION';assert not any(n in sys.modules for n in ('psycopg','pydantic','parkweave.store','scripts.windows_portable.native_system_crt','scripts.windows_portable.native_trial_authority','scripts.windows_portable.native_instance_security'))"
    subprocess.run([sys.executable,'-I','-B','-S','-c',code,str(root)],check=True,timeout=10)


def test_default_platform_and_audit_refuse_effects_before_any_native_operation(monkeypatch,capsys):
    monkeypatch.setattr(C,'WinDLL',lambda *a,**k:pytest.fail('native before diagnostic gate'),raising=False)
    assert diagnostic.main([])==2
    assert json.loads(capsys.readouterr().out)['status']=='NOT_RUN'
    if sys.platform!='win32':
        with pytest.raises(RuntimeError):diagnostic.main(['--run-readonly'])
    audit=diagnostic.ReadOnlyAudit()
    audit('open',('source.py','r',0));audit('ctypes.dlopen',('wintrust.dll',))
    for name in diagnostic.NATIVE_SYMBOLS:audit('ctypes.dlsym',(object(),name))
    for event,args in [('ctypes.dlopen',('caller.dll',)),('ctypes.dlsym',(None,'SetTokenInformation')),
            ('ctypes.dlsym',(None,'CryptProtectData')),('ctypes.dlsym',(None,'SetSecurityInfo')),
            ('open',('never-created','w',0)),('socket.__new__',()),('subprocess.Popen',()),
            ('winreg.SetValue',()),('os.chmod',()),('os.mkdir',())]:
        with pytest.raises(RuntimeError):audit(event,args)


def controlled_native(monkeypatch,close_result=0):
    calls=[]
    def get_current():return 71
    def architecture(process,machine,native):machine._obj.value=0;native._obj.value=0x8664;return 1
    def system(buffer,size):buffer.value=r'C:\Windows\System32';return len(buffer.value)
    def opened(path,access,share,security,disposition,flags,template):
        assert path.value in [r'C:\Windows\System32'+'\\'+n for n in shared.CRT_DLLS]
        assert (access,share,security,disposition,flags,template)==(0x80000000,1,None,3,0x200000,None)
        calls.append(('OPEN_READ_ONLY',path.value.rsplit('\\',1)[-1]));return 41
    def info(handle,output):
        calls.append(('FILE_INFO',handle))
        row=output._obj;row.size_low=1;row.links=1;row.volume=1;row.index_low=7;return 1
    def read(handle,buffer,size,used,overlapped):buffer[0]=b'x';used._obj.value=1;return 1
    def closed(handle):calls.append(('FILE_CLOSE',handle));return 1
    def wvt(hwnd,action,data):
        row=data._obj;calls.append(('WVT',row.action))
        assert row.flags==0x80|0x1000|0x2000 and row.file.contents.file==41
        return -2146762496 if row.action==1 else close_result
    functions=dict(GetCurrentProcess=get_current,IsWow64Process2=architecture,GetSystemDirectoryW=system,
        CreateFileW=opened,GetFileInformationByHandle=info,ReadFile=read,CloseHandle=closed,WinVerifyTrust=wvt)
    class Library:
        def __getattr__(self,name):
            assert name in diagnostic.NATIVE_SYMBOLS
            if name in functions:return functions[name]
            def unused(*args):pytest.fail('unexpected trust-provider call after rejected VERIFY')
            return unused
    monkeypatch.setattr(diagnostic,'os',SimpleNamespace(name='nt',environ={}))
    monkeypatch.setattr(C,'WinDLL',lambda name,**kw:Library(),raising=False)
    return calls


def test_two_fixed_crt_files_once_no_factory_and_raw_long_is_preserved(monkeypatch):
    calls=controlled_native(monkeypatch)
    result,code=diagnostic.collect()
    assert code==0 and result['status']=='READONLY_DIAGNOSTIC_COMPLETED'
    assert {row['file'] for row in result['rows']}==shared.CRT_DLLS
    assert all(row['verification']=='SIGNATURE_REJECTED' and row['returned_status']=='800b0100' for row in result['rows'])
    assert all(row['expected_root_matched'] is None and not row['root_policy_reached'] for row in result['rows'])
    assert all(row['wintrust_returns']==[dict(action='VERIFY',signed=-2146762496,hex='800b0100'),dict(action='CLOSE',signed=0,hex='00000000')] for row in result['rows'])
    assert len([r for r in calls if r[0]=='OPEN_READ_ONLY'])==2
    assert len([r for r in calls if r[0]=='FILE_CLOSE'])==2
    assert len([r for r in calls if r[0]=='FILE_INFO'])==4
    assert result['native_acceptance']=='NOT_ACCEPTED' and result['usable_product'] is False and not result['business_factory_activated']


def test_unknown_wintrust_close_retains_original_graph_stops_before_second_file(monkeypatch):
    calls=controlled_native(monkeypatch,close_result=-1);before=len(diagnostic._unknown)
    try:
        result,code=diagnostic.collect()
        assert code==2 and result['status']=='UNKNOWN_STOP_NO_RETRY' and len(result['rows'])==1
        row=result['rows'][0]
        assert row['wvt_close']=='UNKNOWN' and row['verify_returned_zero'] is False
        assert row['file_cleanup']=='UNKNOWN_RETAINED_NO_CLOSE'
        assert row['metadata_after']=='NOT_ATTEMPTED_UNKNOWN'
        assert calls==[('OPEN_READ_ONLY','msvcp140.dll'),('FILE_INFO',41),('WVT',1),('WVT',2)]
        retained=diagnostic._unknown[-1]
        assert retained.handles==[41] and retained.unknown and retained.unknown[0][1].action==2
        with pytest.raises(RuntimeError):retained.close()
        assert len(calls)==4
    finally:del diagnostic._unknown[before:]


def test_readonly_receiver_has_fixed_work_and_cleanup_ends_and_no_delegation(monkeypatch):
    value=object.__new__(diagnostic.ReadOnlySignature);value.deadline=1001.;value.cleanup_end=1010.
    value.failed=False;value.unknown=[]
    clock=[1000.];monkeypatch.setattr(diagnostic,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    value._signature_budget(None,None)
    for delegation,deadline in [(object(),None),(None,1005.)]:
        with pytest.raises(RuntimeError):value._signature_budget(delegation,deadline)
    clock[0]=1002.
    with pytest.raises(RuntimeError):value._signature_budget(None,None)
    value._signature_cleanup_budget(None)
    clock[0]=1010.
    with pytest.raises(RuntimeError):value._signature_cleanup_budget(None)
    assert value.deadline==1001. and value.cleanup_end==1010.


def test_signer_summary_respects_layout_and_never_replaces_original_pointer():
    value=object.__new__(diagnostic.ReadOnlySignature);value.signer_facts=None
    class ShortRow:
        size=0
        @property
        def count(self):pytest.fail('summary read beyond unknown signer layout')
    original=SimpleNamespace(contents=ShortRow());value.native_signer=lambda *args:original
    assert value.signer(19,0,False,0) is original
    assert value.signer_facts==dict(size=0) and value.signer_observation=='SIZE_MISMATCH'
    class Unavailable:
        @property
        def contents(self):raise ValueError('PRIVATE_OBSERVER_ARGUMENT')
    original=Unavailable();value.native_signer=lambda *args:original
    assert value.signer(19,0,False,0) is original and value.signer_observation=='SUMMARY_UNAVAILABLE'


def test_ci_single_public_push_uses_existing_python_and_only_independent_readonly_entry():
    workflow=Path('.github/workflows/windows-server-engineering.yml').read_text()
    job=workflow.split('  crt-signature-readonly:',1)[1].split('  server-engineering:',1)[0]
    assert diagnostic.BEFORE in job and diagnostic.MARKER in job and 'github.run_attempt == 1' in job
    assert 'timeout-minutes: 3' in job and 'timeout-minutes: 2' in job and 'runs-on: windows-2025' in job
    assert '-I -B -S scripts/windows_ci/crt_signature_readonly.py --run-readonly' in job
    assert 'persist-credentials: false' in job and 'github.event.repository.private == false' in job
    assert not any(text in job for text in ('setup-python','pip install','native_business_driver','Engineering.ps1','controlled_job','upload-artifact'))
