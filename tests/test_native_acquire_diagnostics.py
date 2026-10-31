"""Source diagnostics + real POSIX lease IO with controlled failure injection.

No Windows calls, fifth trial, credentials, safety setters or old UNKNOWN root.
The injected errors reproduce a causal shape, not the unknown Windows cause.
"""
import ctypes
import json
from pathlib import Path
import struct
import subprocess
from types import FunctionType,ModuleType

import pytest

from parkweave import windows_files
from parkweave.store import Denied
from scripts.windows_ci import native_business_entry as entry
from scripts.windows_ci.native_failure_diagnostics import SourceSites
from scripts.windows_portable.controller import Controller,ControlFailure
from scripts.windows_portable.directories import LeaseRefused
from scripts.windows_portable.fixed_directories import FixedPrivateDirectories
from scripts.windows_portable.fixed_journal import FixedFormat

ROOT=Path(__file__).resolve().parents[1]
PRIVATE='SYNTHETIC_PRIVATE_DO_NOT_LOG'


@pytest.fixture
def sites():return SourceSites(ROOT,'a'*40)  # Protocol label, never native/source admission.


def denied():
    try:windows_files.component('CON')  # Real fixed-source pure validation.
    except Denied as error:return error
    raise AssertionError('reserved component accepted')


def test_original_loss_is_proven_without_guessing_fourth_run_type(sites):
    old=ModuleType('original_approved_diagnostic')
    raw=subprocess.check_output(['git','show',
        '6b4ca0288f1a4b393ba499f587206f15658c2885:scripts/windows_ci/native_business_entry.py'],cwd=ROOT)
    exec(compile(raw,'<original-reviewed-entry>','exec'),old.__dict__)  # Definitions only; main never runs.
    try:struct.unpack('<Q',b'')
    except struct.error as error:binary=error
    errors=[denied(),ctypes.ArgumentError(PRIVATE),binary]
    assert [old._error_type(error) for error in errors]==['UNLISTED_EXCEPTION']*3
    expected=['Denied','CTYPES_ARGUMENT_ERROR','STRUCT_ERROR']
    report=entry._failure_diagnostic(ControlFailure('ACQUIRE',ExceptionGroup(PRIVATE,errors),[]),sites)
    assert report['control']['causes'][:3]==expected
    assert {row['category'] for row in report['exception_details']} >= {
        'ACCESS_OR_BINDING_REFUSED','FFI_ARGUMENT_CONVERSION','BINARY_LAYOUT'}
    # Same bare class names cannot pretend to be the known exact classes.
    for name in ('Denied','ArgumentError','error'):
        assert entry._error_type(type(name,(RuntimeError,),{})(PRIVATE))=='UNLISTED_EXCEPTION'
    assert PRIVATE not in json.dumps(report)


def test_source_sites_match_real_code_and_reject_forged_module_filename(sites):
    observed=sites.locate(denied())
    assert observed['status']=='MATCHED'
    assert any(row['module']=='parkweave.windows_files' and row['function']=='component'
               for row in observed['frames'])
    filename=str(ROOT/'src/parkweave/windows_files.py')
    fake=compile('def '+PRIVATE+'():\n raise Denied("'+PRIVATE+'")\n',filename,'exec')
    code=next(value for value in fake.co_consts if hasattr(value,'co_name'))
    try:FunctionType(code,vars(windows_files))()
    except Denied as error:rejected=sites.locate(error)
    assert rejected['status']=='SITE_UNAVAILABLE' and rejected['frames']==[]
    text=json.dumps([observed,rejected])
    assert PRIVATE not in text and str(ROOT) not in text


def test_diagnostic_identity_links_and_global_limits_are_explicit(sites):
    first=[denied() for _ in range(24)];second=[denied() for _ in range(24)]
    root=ExceptionGroup(PRIVATE,first)
    cleanup=ExceptionGroup(PRIVATE,second)
    failure=ControlFailure('ACQUIRE',root,[('FINAL_STATE',root),('UNKNOWN_STATE',cleanup),('RELEASE',cleanup)])
    report=entry._failure_diagnostic(failure,sites)
    assert report['cause_details']==report['cleanup_details'][0]['errors']
    assert report['cleanup_details'][1]['errors']==report['cleanup_details'][2]['errors']
    assert len(report['exception_details'])<=32 and report['details_truncated'] is True
    assert sum(item['source_sites'].get('examined_nodes',0) for item in report['exception_details'])<=64
    assert sum(len(item['source_sites']['frames']) for item in report['exception_details'])<=16
    assert PRIVATE not in json.dumps(report)


def test_operation_is_fixed_source_diagnostic_not_caller_text_or_authority(sites):
    for operation in (PRIVATE,object()):
        report=entry._failure_diagnostic(ControlFailure('ACQUIRE',denied(),[],operation=operation),sites)
        assert report['control']['operation']=='UNLISTED_OPERATION'
        assert PRIVATE not in json.dumps(report)
    assert 'operation' not in ControlFailure('ACQUIRE',denied(),[]).public()
    calls=[]
    class DirectoryPort:
        def open_existing(self,root):calls.append('reopen');raise LeaseRefused(PRIVATE)
    class SecurityPort:
        def require_runtime_support(self,*args):calls.append('support')
    # REOPEN must not call a creation/prepare/credential method. No root or
    # original native resource is acquired in this controlled algorithm check.
    controller=Controller(DirectoryPort(),SecurityPort(),object(),database=object())
    with pytest.raises(ControlFailure) as caught:controller._run('not-opened',lambda _:None,fresh=False)
    report=entry._failure_diagnostic(caught.value,sites)
    assert calls==['support','reopen'] and report['control']['operation']=='REOPEN'
    assert report['control']['outcome']=='UNKNOWN'


def test_detail_flag_includes_cause_and_cleanup_slice_limits(sites):
    failure=ControlFailure('ACQUIRE',ExceptionGroup(PRIVATE,[ValueError(PRIVATE) for _ in range(20)]),[])
    report=entry._failure_diagnostic(failure,sites)
    assert len(report['cause_details'])==16 and report['details_truncated'] is True
    failure=ControlFailure('ACQUIRE',None,[('RELEASE',ExceptionGroup(PRIVATE,
        [ValueError(PRIVATE) for _ in range(20)]))])
    report=entry._failure_diagnostic(failure,sites)
    assert len(report['cleanup_details'][0]['errors'])==16 and report['details_truncated'] is True


@pytest.mark.parametrize('close_ack_lost',[False,True])
def test_actual_posix_lease_poison_cascade_never_writes_or_reports_clean_success(tmp_path,monkeypatch,sites,close_ack_lost):
    directories=FixedPrivateDirectories(str(tmp_path),format=FixedFormat.INSTANCE_V2)
    lease=directories.claim_fresh(str(tmp_path/'synthetic-case'))
    journal=tmp_path/'synthetic-case'/'.parkweave-lease.slots';before=journal.read_bytes()
    counts=dict(verify=0,write=0,close=0);original_close=lease.fs.close
    def verify():
        counts['verify']+=1
        struct.unpack('<Q',b'')  # Actual stdlib error, a controlled injected cause.
    def write(*args):
        counts['write']+=1
        pytest.fail('poisoned lease attempted a journal write')
    def close():
        counts['close']+=1;original_close()  # Actually close our own real POSIX FDs once.
        if close_ack_lost:raise LeaseRefused(PRIVATE)  # Controlled lost-close acknowledgement.
    monkeypatch.setattr(lease.fs,'verify',verify)
    monkeypatch.setattr(lease.fs,'write_at',write)
    monkeypatch.setattr(lease.fs,'close',close)
    class DirectoryPort:
        def claim_fresh(self,root):return lease
    class SecurityPort:
        def require_runtime_support(self,*args):pass
        def require_creation_support(self):pass
        def close_owned_files(self,*args):pass  # No secret files in this protocol.
    class DatabasePort:
        def prepare_new(self):return b'protocol-only-no-SQL-execution'
    controller=Controller(DirectoryPort(),SecurityPort(),object(),database=DatabasePort())
    # Test the original algorithm directly, never bypass the public native gate
    # or supply a fake native capability. Real lease IO above is POSIX only.
    with pytest.raises(ControlFailure) as caught:controller._run(str(tmp_path/'synthetic-case'),lambda _:None,fresh=True)
    failure=caught.value
    assert failure.phase=='ACQUIRE' and type(failure.primary) is struct.error
    assert lease.poisoned is True and lease.active is False
    assert counts==dict(verify=1,write=0,close=1) and journal.read_bytes()==before
    phases=[phase for phase,_ in failure.cleanup_errors]
    assert phases==['FINAL_STATE','UNKNOWN_STATE']+(['RELEASE'] if close_ack_lost else [])
    report=entry._failure_diagnostic(failure,sites)
    assert report['control']['outcome']=='UNKNOWN' and report['control']['causes']==['STRUCT_ERROR']
    assert report['control']['operation']=='CREATE'
    assert report['control']['cleanup_count']==(3 if close_ack_lost else 2)
    assert report['control']['cleanup'][1]['types']==['LeaseRefused','LeaseRefused']
    if close_ack_lost:
        assert report['control']['cleanup'][2]['types']==['LeaseRefused','ExceptionGroup']
    assert any(frame['module']=='scripts.windows_portable.fixed_directories'
        and frame['function']=='FixedDirectoryLease._verify'
        for item in report['exception_details'] for frame in item['source_sites']['frames'])
    assert PRIVATE not in json.dumps(report) and str(tmp_path) not in json.dumps(report)
    # Neither repeated recovery nor close may retry the original IO.
    with pytest.raises(LeaseRefused):lease.mark_unknown('ACQUIRE')
    with pytest.raises(LeaseRefused):lease.release()
    assert counts==dict(verify=1,write=0,close=1)
