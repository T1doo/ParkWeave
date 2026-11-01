"""Actual PGDATA ctypes boundary with synthetic returns, never Windows evidence."""
import ctypes as C
from types import SimpleNamespace

import pytest

from scripts.windows_portable import pgdata_candidate as pg
from parkweave.windows_handles import _NT_CREATE_PENDING, _UNKNOWN_NATIVE_QUERIES


def target(call):
    value=object.__new__(pg._NewDataTarget)
    value.lease=SimpleNamespace(poisoned=False)
    value.deadline=float('inf');value.handles=[11]
    value.closed=value.failed=False;value.cleanup_errors=[];value.outcome='PROTOCOL'
    closed=[]
    value.api=SimpleNamespace(readonly=SimpleNamespace(),ntcreate=call,close=closed.append)
    return value,closed


@pytest.mark.parametrize('mode', ['pending','exception-empty','exception-handle','failure-handle',
    'success-empty','success-invalid','iosb-conflict'])
def test_unacknowledged_create_preserves_original_outputs_and_pins_without_close_or_retry(mode):
    calls=[]
    def call(handle,*args):
        calls.append(mode)
        io=C.cast(args[2],C.POINTER(pg.IOStatus)).contents
        if mode in ('exception-handle','failure-handle','iosb-conflict'):
            C.cast(handle,C.POINTER(pg.PTR))[0]=77
        if mode=='success-invalid':C.cast(handle,C.POINTER(pg.PTR))[0]=pg.PTR(-1).value
        if mode=='iosb-conflict':io.Status=1
        if mode.startswith('exception'):raise RuntimeError('SYNTHETIC_FFI_INTERRUPTION')
        return 0x103 if mode=='pending' else -1 if mode=='failure-handle' else 0
    value,closed=target(call)
    with pytest.raises(Exception):value._open(11,'postgresql',create=True,descriptor=b'fixed',anchor=True)
    assert value.api.readonly._nt_create_pending and value.handles==[11]
    value._fail()
    assert closed==[] and value.handles==[11] and not value.closed
    assert value.failed and value.lease.poisoned and value.outcome=='UNKNOWN'
    assert any(row[0] is value.api.readonly for row in _NT_CREATE_PENDING.values())
    with pytest.raises(Exception):value._open(11,'postgresql',create=True,descriptor=b'fixed',anchor=True)
    with pytest.raises(Exception):value._close_native()
    assert calls==[mode] and closed==[]


def test_acknowledged_create_owns_before_later_refusal_and_closes_once():
    def call(handle,*args):
        C.cast(handle,C.POINTER(pg.PTR))[0]=77
        C.cast(args[2],C.POINTER(pg.IOStatus)).contents.Information=1  # opened, not created
        return 0
    value,closed=target(call)
    with pytest.raises(pg.DataRefused):value._open(11,'postgresql',create=True)
    assert value.handles==[11,77] and not getattr(value.api.readonly,'_nt_create_pending',False)
    value._fail()
    assert closed==[77,11] and value.closed and value.lease.poisoned
    value._close_native();assert closed==[77,11]


@pytest.mark.parametrize('operation',['path','entries'])
def test_interrupted_query_retains_buffer_and_borrowed_handle_graph(operation):
    def interrupted(*args):raise RuntimeError('SYNTHETIC_QUERY_INTERRUPTION')
    value,closed=target(lambda *args:pytest.fail('no create allowed'))
    value.root=11;value.api.getpath=interrupted;value.query=interrupted
    with pytest.raises(RuntimeError):
        if operation=='path':value._dos_path()
        else:value._entries(11)
    assert value.api.readonly._query_unknown
    assert any(row[0] is value.api.readonly for row in _UNKNOWN_NATIVE_QUERIES)
    value._fail()
    assert closed==[] and value.handles==[11] and not value.closed and value.lease.poisoned


@pytest.mark.parametrize('mode',['false-handle','true-empty','true-invalid','exception-empty','exception-handle'])
def test_token_output_ambiguity_never_closes_or_retries_original_graph(mode,monkeypatch):
    monkeypatch.setattr(C,'get_last_error',lambda:0,raising=False)
    value,closed=target(lambda *args:pytest.fail('no create allowed'))
    calls=[]
    def open_token(process,access,handle):
        calls.append(mode)
        if mode in ('false-handle','exception-handle'):
            C.cast(handle,C.POINTER(pg.PTR))[0]=77
        if mode=='true-invalid':C.cast(handle,C.POINTER(pg.PTR))[0]=pg.PTR(-1).value
        if mode.startswith('exception'):raise RuntimeError('SYNTHETIC_TOKEN_INTERRUPTION')
        return mode.startswith('true')
    value.api.opentoken=open_token;value.api.process=lambda:-1
    value.api.need=pg._need
    with pytest.raises(Exception):value._current_user_sid()
    value._fail()
    assert value.api.readonly._query_unknown and value.handles==[11] and closed==[]
    assert value._user_token is not None and value.lease.poisoned and not value.closed
    original=value._user_token
    with pytest.raises(Exception):value._current_user_sid()
    assert calls==[mode] and value._user_token is original


def test_cleanup_deadline_covers_direct_walk_close_and_token_finally(monkeypatch):
    from scripts.windows_portable import native_trial_authority as authority
    monkeypatch.setattr(C,'get_last_error',lambda:0,raising=False)
    def expired(*args,**kwargs):raise pg.DataRefused('ORIGINAL_CLEANUP_EXPIRED')
    monkeypatch.setattr(authority,'budget',expired)
    value,closed=target(lambda *args:pytest.fail('no create allowed'))
    with pytest.raises(pg.DataRefused):value._close_one(11)
    assert value.handles==[11] and closed==[]
    def open_token(process,access,handle):
        C.cast(handle,C.POINTER(pg.PTR))[0]=77
        return True
    value.api.process=lambda:-1;value.api.opentoken=open_token;value.api.need=pg._need
    value.api.tokeninfo=lambda *args:False
    with pytest.raises(BaseExceptionGroup):value._current_user_sid()
    assert value.handles==[11,77] and closed==[]
    value._fail()
    assert not value.closed and value.handles==[11,77] and closed==[]


def test_completed_query_cannot_accept_results_after_original_deadline(monkeypatch):
    value,closed=target(lambda *args:pytest.fail('no create allowed'))
    now=[1.0];value.deadline=2.0
    monkeypatch.setattr(pg.time,'monotonic',lambda:now[0])
    def query(*args):now[0]=3.0;return True
    value.query=query
    with pytest.raises(pg.DataRefused):value._entries(11)
    assert closed==[] and value.handles==[11]


def test_completed_pgdata_walk_opens_do_not_exhaust_original_inflight_bound():
    from scripts.windows_portable import native_protected_objects as protected
    returned=[1000]
    def call(handle,*args):
        returned[0]+=1
        C.cast(handle,C.POINTER(pg.PTR))[0]=returned[0]
        C.cast(args[2],C.POINTER(pg.IOStatus)).contents.Information=1
        return 0
    value,closed=target(call)
    before=set(protected._inflight)
    for _ in range(4100):
        handle=value._open(11,'entry')
        value._close_one(handle)
    assert set(protected._inflight)==before and value.handles==[11]
    assert len(closed)==4100 and len(set(closed))==4100


def test_unacknowledged_and_changed_create_outputs_cannot_be_handed_off():
    from scripts.windows_portable import native_protected_objects as protected
    api=SimpleNamespace(readonly=SimpleNamespace())
    handle,io,attrs=pg.PTR(),pg.IOStatus(),pg.ObjectAttributes()
    def call(phandle,*args):
        C.cast(phandle,C.POINTER(pg.PTR))[0]=77
        return 0
    api.ntcreate=call
    protected.submit_create(api,handle,io,attrs,(),access=1,attributes=0,share=1,disposition=1,options=0)
    key=id(io)
    for held in ([],[77,77]):
        with pytest.raises(Exception):protected.transfer_completed_create(api,handle,io,attrs,held)
        assert key in protected._inflight
    io.Information=2
    with pytest.raises(Exception):protected.transfer_completed_create(api,handle,io,attrs,[77])
    assert key in protected._inflight
    io.Information=0;api.readonly._query_unknown=True
    with pytest.raises(Exception):protected.transfer_completed_create(api,handle,io,attrs,[77])
    assert key in protected._inflight


def test_expired_identity_observation_does_not_issue_following_acl_query(monkeypatch):
    value,closed=target(lambda *args:pytest.fail('no create allowed'))
    now=[1.0];value.deadline=2.0;value.root=11
    monkeypatch.setattr(pg.time,'monotonic',lambda:now[0])
    calls=[]
    def info(handle):calls.append('info');now[0]=3.0;return object()
    value.api.info=info
    value.api.descriptor=lambda *args:pytest.fail('expired observation must not continue')
    value._verify=lambda:SimpleNamespace(root_id=(5,11))
    with pytest.raises(pg.DataRefused):value._walk()
    assert calls==['info'] and closed==[]
