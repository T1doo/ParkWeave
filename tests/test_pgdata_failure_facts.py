"""Original construction/diagnostic code over synthetic ctypes outputs, not WinAT."""
import json
from threading import Lock

import pytest

from scripts.windows_portable import pgdata_candidate as pg
from scripts.windows_ci.native_failure_diagnostics import detail
from test_pgdata_native_outcomes import target
from parkweave.windows_files import Ace,Security

PRIVATE='SYNTHETIC_PRIVATE_INPUT_NOT_FOR_DIAGNOSTICS'


def construction(monkeypatch,*,close_failure=False):
    def call(handle,*args):return 0xc0000034  # synthetic exact final-name absence
    value,closed=target(call)
    if close_failure:
        def close(handle):closed.append(handle);raise OSError(PRIVATE)
        value.api.close=close
    lease=object.__new__(pg.FixedDirectoryLease)
    lease.fs=object.__new__(pg.FixedWindowsFilesystem)
    lease.fs.api=object.__new__(pg.NativeFixedLeaseAPI)
    lease.record=dict(phase='CLUSTER',initialized=False,handoff='OWNED',generation=1)
    lease.active=True
    lease.poisoned=False;lease._operation_owner=None;lease._operation_depth=0;lease._entry_lock=Lock()
    value.lease=lease;value.stage='CREATE_PGDATA'
    value._create_native=lambda key:value._open(11,'postgresql',create=True,descriptor=PRIVATE.encode())
    monkeypatch.setattr(pg,'_key_held',lambda original:('synthetic-original',1))
    with pytest.raises(pg.DataConstructionFailure) as caught:
        pg._create_target_held(lease,value,layout=object())
    return caught.value,value,closed


def test_original_creation_preserves_cause_numeric_status_and_cleanup_scope(monkeypatch):
    error,value,closed=construction(monkeypatch)
    assert type(error.__cause__) is pg.DataRefused and error.primary is error.__cause__
    facts=detail(error,'DataConstructionFailure')['pgdata']
    assert facts['stage']=='CREATE_PGDATA' and facts['check']=='NATIVE_COMPLETION'
    assert facts['native']==dict(call='NT_CREATE',returned=True,code=0xc0000034,
        iosb_status=0,information=0,handle_output='EMPTY')
    assert facts['cleanup']==dict(captured_at='PGDATA_FAILURE_BEFORE_CONTROLLER_RELEASE',
        target_close_confirmed=True,remaining_unattempted_handle_count=0,close_error_record_count=0,lease_poisoned=True,
        nt_create_unknown=False,query_unknown=False,lease_active=True,memory_phase='CLUSTER',
        memory_handoff='OWNED',initialized=False,first_generation=True,persistent_journal_reobserved=False)
    assert closed==[11] and PRIVATE not in json.dumps(facts)
    assert '11' not in json.dumps(facts)  # no handle number serialized


@pytest.mark.parametrize('damage',['stage','native_extra','native_call','native_code','fields','cleanup'])
def test_pgdata_diagnostics_drop_malformed_or_private_extensions(monkeypatch,damage):
    error,_,_=construction(monkeypatch)
    if damage=='stage':error.stage=PRIVATE
    elif damage=='native_extra':error.native['path']=PRIVATE
    elif damage=='native_call':error.native['call']=PRIVATE
    elif damage=='native_code':error.native['code']=PRIVATE
    elif damage=='fields':error.changed_fields=([],)
    else:error.cleanup['private_token']=PRIVATE
    facts=detail(error,'DataConstructionFailure')['pgdata']
    assert facts==dict(details='UNAVAILABLE') and PRIVATE not in json.dumps(facts)


def test_security_refusal_reports_only_mismatching_field_names():
    user='S-1-5-21-1001';security=Security(PRIVATE,0x9004,(Ace(0,3,pg.FILE_ALL,user),))
    with pytest.raises(pg.DataRefused) as caught:pg.check_security(security,user,root=True,directory=True)
    facts=detail(caught.value,'DataRefused')['pgdata']
    assert facts==dict(check='SECURITY_PROFILE',changed_fields=['OWNER'])
    assert PRIVATE not in json.dumps(facts)


def test_deadline_and_dos_path_refusals_have_distinct_fixed_checks(monkeypatch):
    value,_=target(lambda *args:pytest.fail('no native call'))
    value.deadline=0
    with pytest.raises(pg.DataRefused) as deadline:value._time()
    assert detail(deadline.value,'DataRefused')['pgdata']['check']=='DEADLINE'
    with pytest.raises(pg.DataRefused) as path:pg.pg_command_path(PRIVATE)
    assert detail(path.value,'DataRefused')['pgdata']['check']=='DOS_PATH_KIND'


def test_diagnostic_record_failure_cannot_lose_returned_handle_or_replace_primary():
    import ctypes as C
    observed=[]
    def call(handle,*args):
        C.cast(handle,C.POINTER(pg.PTR))[0]=77
        C.cast(args[2],C.POINTER(pg.IOStatus)).contents.Information=1
        return 0
    value,closed=target(call)
    def unavailable(*args,**kwargs):observed.append(tuple(value.handles));raise RuntimeError(PRIVATE)
    value._native=unavailable
    with pytest.raises(pg.DataRefused) as caught:value._open(11,'postgresql',create=True)
    assert caught.value.check=='EXCLUSIVE_CREATE'
    assert observed==[(11,),(11,77)]
    value._fail();assert closed==[77,11] and value.closed


def test_token_error_diagnostic_failure_preserves_ambiguous_original_output(monkeypatch):
    import ctypes as C
    errors=[]
    def last_error():
        errors.append(1)
        if len(errors)==2:raise RuntimeError(PRIVATE)
        return 0
    monkeypatch.setattr(C,'get_last_error',last_error,raising=False)
    value,closed=target(lambda *args:pytest.fail('no create'))
    def open_token(process,access,handle):C.cast(handle,C.POINTER(pg.PTR))[0]=77;return False
    value.api.opentoken=open_token;value.api.process=lambda:-1;value.api.need=pg._need
    with pytest.raises(pg.DataRefused) as caught:value._current_user_sid()
    assert caught.value.check=='TOKEN_OUTPUT' and len(errors)==2
    assert value.api.readonly._query_unknown and value._user_token.value==77
    value._fail();assert closed==[] and not value.closed


def test_subscope_close_ack_unknown_is_not_reported_as_zero_retained_resources(monkeypatch):
    error,value,closed=construction(monkeypatch,close_failure=True)
    facts=detail(error,'DataConstructionFailure')['pgdata']['cleanup']
    assert facts['remaining_unattempted_handle_count']==0
    assert facts['close_error_record_count']==1 and not facts['target_close_confirmed']
    assert closed==[11] and not value.closed
    assert PRIVATE not in json.dumps(facts)


def test_incomplete_diagnostic_context_cannot_replace_primary():
    from types import SimpleNamespace
    primary=pg.DataRefused(PRIVATE)
    error=pg.DataConstructionFailure(SimpleNamespace(),primary)
    assert error.primary is primary
    assert detail(error,'DataConstructionFailure')['pgdata']==dict(details='UNAVAILABLE')


def test_original_entry_keeps_pgdata_facts_and_cleanup_unknown_without_private_arguments(monkeypatch):
    from pathlib import Path
    from scripts.windows_ci import native_business_entry as entry
    from scripts.windows_ci.native_failure_diagnostics import SourceSites
    from scripts.windows_portable.controller import ControlFailure
    from scripts.windows_portable.directories import LeaseRefused
    error,_,_=construction(monkeypatch)
    control=ControlFailure('CLUSTER',error,[('FINAL_STATE',LeaseRefused(PRIVATE))])
    report=entry._failure_diagnostic(control,SourceSites(Path(__file__).resolve().parents[1],'a'*40))
    assert report['control']['outcome']=='UNKNOWN'
    assert report['control']['cleanup']==[dict(phase='FINAL_STATE',types=['LeaseRefused'])]
    assert any(row.get('pgdata',{}).get('stage')=='CREATE_PGDATA' for row in report['exception_details'])
    assert PRIVATE not in json.dumps(report)
