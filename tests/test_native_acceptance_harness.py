"""Pure orchestration and controlled native-output failures; no Windows proof."""
import ctypes as C
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.windows_ci import native_acceptance_harness as h
from scripts.windows_ci import native_acceptance_storage as s
from scripts.windows_portable.native_acceptance_contract import Area,coverage,requirement


def test_plan_and_unbound_execute_do_not_load_native_or_touch_files(monkeypatch,capsys):
    native=Mock(side_effect=AssertionError('native call before approval'))
    io=Mock(side_effect=AssertionError('IO before approval'))
    monkeypatch.setattr(C,'WinDLL',native,raising=False)
    monkeypatch.setattr(h,'verify_invocation',io)
    monkeypatch.setattr(h,'NativeBackend',io)
    assert h.main([])==0
    assert json.loads(capsys.readouterr().out)['window']=='APPROVAL_RECORD_NOT_READ'
    assert h.main(['--execute','--payload','untrusted-path','--candidate-zip','untrusted.zip'])==2
    result=json.loads(capsys.readouterr().out)
    assert result['activation_allowed'] is result['usable_product'] is False
    native.assert_not_called();io.assert_not_called()


def test_even_complete_observation_coverage_cannot_issue_product_acceptance():
    observations=tuple(x for area in Area for x in requirement(area).observations)
    result=coverage(observations)
    assert not result['activation_allowed'] and not result['usable_product']
    assert all(not row['missing'] and row['acceptance']=='NOT_ACCEPTED' for row in result['areas'].values())
    from scripts.windows_portable.fixed_windows_journal import require_fixed_native_acceptance
    with pytest.raises(Exception,match='WINDOWS_FIXED_FILE_NATIVE_ACCEPTANCE_NOT_ESTABLISHED'):
        require_fixed_native_acceptance()


class Protocol:
    def __init__(self,fail=None):self.calls=[];self.fail=fail
    def phase(self,name):
        self.calls.append(name)
        if self.fail==name:raise RuntimeError('PRIVATE_ERROR_MUST_NOT_APPEAR')
        return (name+'_observation',)
    def fixed_journal(self,deadline):return self.phase('fixed_journal')
    def derived_token(self,deadline):return self.phase('derived_token')
    def dpapi_identities(self,deadline):return self.phase('dpapi_identities')
    def unknown(self):self.calls.append('unknown')
    def cleanup(self,deadline):self.calls.append('cleanup');return 'OWN_CHILDREN_DELETED_EMPTY_MARKER_RETAINED'


def test_protocol_failure_stops_later_native_operations_and_never_retries():
    value=Protocol('derived_token');result=h.run_protocol(value)
    assert value.calls==['fixed_journal','derived_token','unknown','cleanup']
    assert result['result']=='UNKNOWN' and 'PRIVATE_ERROR_MUST_NOT_APPEAR' not in json.dumps(result)
    assert not result['activation_allowed']
    value=Protocol();result=h.run_protocol(value)
    assert value.calls==[*h.PHASES,'cleanup'] and result['result']=='OBSERVED_ONLY'
    assert result['native_acceptance']=='NOT_ACCEPTED'


def negative_storage(monkeypatch,information,status,handle=17):
    from parkweave import windows_handles
    monkeypatch.setattr(windows_handles,'_NT_CREATE_PENDING',{})
    value=object.__new__(s.OwnedNativeObjects)
    value.nodes=[];value.ancestors=[];value.entries={};value.buffers=[]
    value.failed=value.closed=False;value.root=None
    value.sid=b'\x01\x01\x00\x00\x00\x00\x00\x05\x12\x00\x00\x00'
    value._anchor=Mock()
    def create(output,access,attrs,io,*args):
        C.cast(output,C.POINTER(C.c_void_p)).contents.value=handle
        C.cast(io,C.POINTER(s.IOStatus)).contents.Information=information
        return status
    value.api=SimpleNamespace(readonly=SimpleNamespace(),ntcreate=create,
        close=Mock(side_effect=AssertionError('unknown handle close')))
    return value


def test_pending_nt_create_retains_original_outputs_and_never_deletes_or_closes(monkeypatch):
    value=negative_storage(monkeypatch,0,0x103)
    with pytest.raises(RuntimeError):value._open(9,'lock.bin',create=True)
    assert value.buffers and value.api.readonly._nt_create_pending
    assert value.cleanup()=='RETAINED_UNKNOWN' and value in s._unknown
    value.api.close.assert_not_called()


def test_unexpected_open_information_registers_handle_without_adopting_file(monkeypatch):
    value=negative_storage(monkeypatch,1,0)  # FILE_OPENED is never FILE_CREATED.
    with pytest.raises(RuntimeError):value._open(9,'lock.bin',create=True)
    assert len(value.nodes)==1 and value.nodes[0].handle==17 and not value.nodes[0].created
    assert value.cleanup()=='RETAINED_UNKNOWN'
    value.api.close.assert_not_called()


def test_partial_write_is_not_finished_retried_or_deleted():
    value=object.__new__(s.OwnedNativeObjects)
    value.failed=value.closed=False;value.buffers=[];value.verify=Mock();value.seek=lambda *args:1
    calls=[]
    def write(handle,buffer,size,count,overlap):
        calls.append(size);C.cast(count,C.POINTER(C.c_uint32)).contents.value=2;return 1
    value.api=SimpleNamespace(need=lambda ok:None,writefile=write,readonly=SimpleNamespace(),close=Mock())
    row=SimpleNamespace(handle=17,size=0)
    with pytest.raises(RuntimeError):value.write(row,0,b'abcd')
    assert calls==[4] and value.cleanup()=='RETAINED_UNKNOWN'
    value.api.close.assert_not_called()


def test_cleanup_failure_does_not_become_observation_success():
    value=Protocol()
    def bad(deadline):raise RuntimeError('private cleanup detail')
    value.cleanup=bad
    result=h.run_protocol(value)
    assert result['result']=='UNKNOWN' and result['cleanup']=='RETAINED_UNKNOWN'
    assert value in h._unknown
    assert not result['activation_allowed']


def test_null_source_record_and_forged_caps_cannot_start_native(monkeypatch,capsys):
    from scripts.windows_ci import native_acceptance_entry as entry,native_acceptance_window as window
    native=Mock(side_effect=AssertionError('native IO before source approval'))
    monkeypatch.setattr(h,'NativeBackend',native)
    assert entry.main(['--execute'])==2
    assert json.loads(capsys.readouterr().out)['activation_allowed'] is False
    with pytest.raises(RuntimeError):window.consume(object(),{})
    native.assert_not_called()


def test_native_query_close_unknown_keeps_original_token_and_attempt():
    from parkweave import windows_handles as w
    value=object.__new__(w.WinAPI);value._query_tokens=[]
    value.need=lambda ok:None if ok else (_ for _ in ()).throw(RuntimeError('refused'))
    value.process=lambda:1
    def opened(process,rights,token):C.cast(token,C.POINTER(w.PTR)).contents.value=17;return 1
    def information(token,kind,buf,capacity,used):
        C.cast(used,C.POINTER(w.U32)).contents.value=16
        if buf is not None:C.cast(buf,C.POINTER(w.PTR)).contents.value=23
        return 1
    value.opentoken=opened;value.tokeninfo=information;value.sid=lambda pointer:'CONTROLLED_QUERY_ONLY'
    value.close=Mock(side_effect=RuntimeError('controlled close unknown'))
    with pytest.raises(RuntimeError):value._user_sid()
    row=value._query_tokens[0]
    assert row['output'].value==17 and row['owned'] and row['close_attempted'] and not row['closed']
    assert value in w._UNKNOWN_QUERY_TOKENS and value.close.call_count==1


def test_single_use_window_cap_refuses_environment_change_without_copying_secret(monkeypatch):
    from scripts.windows_ci import native_acceptance_window as window
    before={'PSYCOPG_IMPL':'binary'}
    for after in ({'PSYCOPG_IMPL':'python'},{'PSYCOPG_IMPL':'binary','PGPASSWORD':'DO_NOT_COPY_SECRET'}):
        cap=window._SourceWindow()
        monkeypatch.setitem(window._issued,cap,(SimpleNamespace(expires_utc=h.time.time()+600),(),window._context(before)))
        with pytest.raises(RuntimeError):window.consume(cap,after)
        assert cap not in window._issued  # No replay after a failed consume.
    assert 'DO_NOT_COPY_SECRET' not in str(window._context(after))


def test_reviewed_metadata_is_data_and_workflow_is_not_enabled():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    assert json.loads((root/'scripts/windows_ci/native_acceptance_window.json').read_text()) is None
    workflow=(root/'.github/workflows/native-local-acceptance-once.yml').read_text()
    assert 'false && github.event.repository.private == false' in workflow
    assert 'timeout-minutes: 6' in workflow and 'persist-credentials: false' in workflow
    assert 'upload-artifact' not in workflow and 'actions/cache' not in workflow
    from scripts.windows import lifecycle
    assert lifecycle.setup_readiness()['reason']==requirement(Area.OWNER).reason
