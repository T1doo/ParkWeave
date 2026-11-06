"""Real child pipes and desktop protocol seams; no native WebView evidence."""
import ctypes as C
import queue
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.windows_ci import native_desktop_trial as ui
from scripts.windows_portable import desktop_profile


def child_session(monkeypatch,program):
    session=object.__new__(ui.Session)
    session.cap=object();session.end=time.monotonic()+5
    session.workspace=SimpleNamespace(check=lambda:None)
    session.unknown=session.closed=session.close_attempted=session.abort_attempted=False
    session.abort_result='NOT_ATTEMPTED';session.failure_details=None
    session.duplicate=C.c_void_p(123);session.responses=queue.Queue()
    close=Mock(return_value=1)
    session.profile=SimpleNamespace(verify=lambda:None,close=Mock(),api=SimpleNamespace(
        readonly=SimpleNamespace(k=SimpleNamespace(CloseHandle=close))))
    monkeypatch.setattr(ui.a,'state',lambda *args,**kwargs:SimpleNamespace(cleanup_end=session.end+2))
    session.proc=subprocess.Popen([sys.executable,'-I','-B','-S','-c',program],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    def read():
        while True:
            line=session.proc.stdout.readline()
            if not line:session.responses.put(None);return
            session.responses.put(line)
    session.reader=threading.Thread(target=read,daemon=True);session.reader.start()
    ui._retained.append(session)
    return session,close


def dispose(session):
    if session.proc.poll() is None:session.proc.terminate()
    session.proc.wait(timeout=2);session.reader.join(timeout=1)
    for pipe in (session.proc.stdin,session.proc.stdout,session.proc.stderr):
        if not pipe.closed:pipe.close()
    if session in ui._retained:ui._retained.remove(session)


def test_real_child_unknown_never_resends_write_or_releases_profile(monkeypatch):
    session,close=child_session(monkeypatch,"import sys,time;sys.stdin.readline();sys.stdout.buffer.write(b'UI1\\tUNKNOWN\\tSET\\t80004005\\n');sys.stdout.buffer.flush();time.sleep(30)")
    try:
        with pytest.raises(RuntimeError,match='UNKNOWN_NO_RETRY'):session.call('SET',ui.encoded('密码'),ui.encoded('SYNTHETIC_INPUT'))
        assert session.unknown and session.abort_attempted and session.proc.poll() is not None
        assert session.failure_details==dict(operation='SET',hresult='80004005')
        with pytest.raises(Exception):session.call('SET','again')
        session.profile.close.assert_not_called();close.assert_not_called()
        assert not session.closed and session.duplicate.value==123 and session in ui._retained
    finally:dispose(session)


def test_real_child_close_ack_exit_eof_then_profile_close_once(monkeypatch):
    session,close=child_session(monkeypatch,"import sys;assert sys.stdin.readline()=='CLOSE\\n';sys.stdout.buffer.write(b'UI1\\tOK\\tCLOSED_ORIGINAL_HOST_AND_UI_JOB_ZERO\\n');sys.stdout.buffer.flush()")
    try:
        session.finish()
        assert session.closed and not session.unknown and session.duplicate.value is None
        session.profile.close.assert_called_once();close.assert_called_once_with(123)
        with pytest.raises(Exception):session.finish()
        assert close.call_count==1 and session not in ui._retained
    finally:dispose(session)


@pytest.mark.parametrize('stage',['00000007','0000000d','00000012','00000013'])
def test_host_stage_refusal_stays_distinct_from_ui_hresult(monkeypatch,stage):
    line=f'UI1\tUNKNOWN\tOPEN_VIEW_FAILED\t{stage}\n'.encode('ascii')
    program=f'import sys;sys.stdin.readline();sys.stdout.buffer.write({line!r});sys.stdout.buffer.flush()'
    session,close=child_session(monkeypatch,program)
    try:
        with pytest.raises(RuntimeError,match='UNKNOWN_NO_RETRY'):session.call('OPEN')
        assert session.failure_details==dict(operation='OPEN_VIEW_FAILED',host_stage=stage)
        assert session.unknown and not session.closed
        close.assert_not_called()
    finally:dispose(session)


def test_chain_refusal_records_only_bounded_certificate_position_and_status(monkeypatch):
    line=b'UI1\tUNKNOWN\tOPEN_VIEW_FAILED\t00000018\t2\t80092013\n'
    program=f'import sys;sys.stdin.readline();sys.stdout.buffer.write({line!r});sys.stdout.buffer.flush()'
    session,close=child_session(monkeypatch,program)
    try:
        with pytest.raises(RuntimeError,match='UNKNOWN_NO_RETRY'):session.call('OPEN')
        assert session.failure_details==dict(operation='OPEN_VIEW_FAILED',host_stage='00000018',
                                             chain_index=2,provider_status='80092013')
        assert session.unknown and not session.closed
        close.assert_not_called()
    finally:dispose(session)


@pytest.mark.parametrize('during_constructor',[False,True])
def test_callback_failure_aborts_before_controller_unwinds_and_keeps_unknown(monkeypatch,during_constructor):
    trial=object.__new__(ui.NativeDesktopTrial);trial.sessions=[];trial.cap=object();trial.driver='unused'
    profile=SimpleNamespace(close=Mock())
    monkeypatch.setattr(ui,'NativeDesktopProfile',lambda *args:profile)
    order=[]
    def initialize(self,*args):
        self.closed=False;self.abort_attempted=False
        if during_constructor:raise RuntimeError('SYNTHETIC_CONSTRUCTOR_FAILURE')
    def abort(self):
        if not self.abort_attempted:order.append('abort-original-ui');self.abort_attempted=True
    monkeypatch.setattr(ui.Session,'__init__',initialize);monkeypatch.setattr(ui.Session,'abort',abort)
    with pytest.raises(RuntimeError):
        with trial.session(object(),object(),True):raise RuntimeError('SYNTHETIC_READBACK_FAILURE')
    order.append('controller-unwind')
    assert order==['abort-original-ui','controller-unwind'] and len(trial.sessions)==1
    profile.close.assert_not_called()


def test_profile_original_business_source_end_and_query_expiry_stop_following_io(monkeypatch):
    clock=[100.];monkeypatch.setattr(desktop_profile.time,'monotonic',lambda:clock[0])
    value=object.__new__(desktop_profile.NativeDesktopProfile)
    value.lease=object();value.workspace=SimpleNamespace(deadline=102.)
    monkeypatch.setattr(ui.a,'bound_state',lambda *args,**kwargs:SimpleNamespace(deadline=101.))
    value._budget(10);assert value.operation_end==101.
    calls=[]
    def query():calls.append('first');clock[0]=101.1;return 1
    with pytest.raises(RuntimeError):value._query(query)
    with pytest.raises(RuntimeError):value._query(lambda:calls.append('forbidden-after-end'))
    assert calls==['first']


def test_ui_command_sequence_waits_exact_revision_and_only_client_read_verifies():
    from pathlib import Path
    source=Path('scripts/windows_ci/native_desktop_trial.py').read_text()
    assert "self.reference(session,revision)" in source
    assert "_request('GET','/api/preparations/'" in source
    assert "_request('POST'" not in source and 'ExecuteScript' not in source
    host=Path('scripts/windows_desktop/host.cpp').read_text()
    assert 'if(trialView)return 0' in host and 'TRIAL_ONLY' in host
    import json
    assert json.loads(Path('scripts/windows_ci/native_business_window.json').read_text()) is None


@pytest.mark.parametrize('specialist,account,label', [
    (False,'fixture-a','企业 A'), (True,'prep-specialist-fixture-a','专员 A'),
])
def test_trial_selects_the_exact_native_material_account_rendered_at_root(specialist,account,label):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from parkweave.local_workspace import mount_workspace
    from scripts.windows_portable.native_web_login import MATERIAL_LABELS

    app=mount_workspace(FastAPI(),Mock(),12345,MATERIAL_LABELS)
    result=TestClient(app,base_url='http://127.0.0.1:12345').get('/')
    assert result.status_code==200
    assert f'<option value="{account}">{label}</option>' in result.text
    assert '<select id="role" aria-label="账号">' in result.text
    trial=object.__new__(ui.NativeDesktopTrial)
    trial.passwords={account:'SYNTHETIC_INPUT'}
    session=Mock()
    trial.login(session,specialist)
    assert session.call.call_args_list[0].args==('SELECT',ui.encoded('账号'),ui.encoded(label))
