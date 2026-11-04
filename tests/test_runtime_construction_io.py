"""Shared production NEW/reopen storage loop, actual POSIX files and lease."""
from hashlib import sha256
import ctypes as C
import os,time
from types import SimpleNamespace
import pytest

from runtime_posix_io import PosixStorage
from scripts.windows_portable import native_runtime_staging as runtime,native_trial_authority as authority
from scripts.windows_portable.fixed_directories import FixedPrivateDirectories
from scripts.windows_portable.fixed_journal import FixedFormat
from scripts.windows_portable.fixed_secret_store import _under_lease
from parkweave import windows_handles as handles


@pytest.fixture
def storage(tmp_path):
    lease=FixedPrivateDirectories(str(tmp_path),format=FixedFormat.INSTANCE_V2).claim_fresh(str(tmp_path/'owned'))
    source=tmp_path/'source';source.mkdir(mode=0o700)
    files={'app/a/b/c/data':b'actual IO'*1000,'app/empty':b'',runtime.payload.MANIFEST:b'owned synthetic manifest'}
    for path,data in files.items():
        target=source/path;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True);target.write_bytes(data);target.chmod(0o600)
    # mkdir(parents=True) uses the process umask on intermediate dirs; this is
    # POSIX test-owned setup only, not a Windows ACL repair or product path.
    for p in source.rglob('*'):
        if p.is_dir():p.chmod(0o700)
    src=SimpleNamespace(root=str(source),manifest=files[runtime.payload.MANIFEST])
    value=PosixStorage(lease,src,files);values=[value]
    yield value,src,files,values
    for v in values:v.dispose_posix_test_only()
    if lease.active:lease.release()


def test_same_production_algorithm_flush_hash_close_readonly_reopen_seal_and_repeat(storage):
    value,src,files,values=storage
    _under_lease(value.lease,lambda:value._construct_tree(src,create=True))
    assert not value.failed and value not in runtime._issued and not value._completion_pending
    assert len([e for e in value.events if e[0]=='flush'])==len(files)
    for path,data in files.items():
        h,_,row=value.rows[path];assert os.pread(h,len(data)+1,0)==data
        # Every target writer was flushed and closed before its read-only pin.
        assert row[0].size==len(data)
    assert value.lease.record['phase']=='NEW' and not value.lease.record['initialized']
    _under_lease(value.lease,value.verify)
    before=list(value.events)
    with pytest.raises(runtime.CandidateRefused):value._construct_tree(src,create=True)
    assert value.events==before
    value.close();assert value.closed and not value.handles
    done=list(value.events);value.close();assert value.events==done
    reopened=PosixStorage(value.lease,src,files);values.append(reopened)
    reopened._completion_pending=False
    # Storage IO reopen only; the actual native constructor's READY_STOPPED
    # admission is not invoked, relaxed, or claimed to pass by this test.
    _under_lease(value.lease,lambda:reopened._construct_tree(src,create=False))
    assert not any(kind in ('write','create','flush') for kind,fd in reopened.events)
    assert reopened not in runtime._issued and reopened.lease.record['phase']=='NEW'
    reopened.close()


@pytest.mark.parametrize('failure',['write','flush','cancel','deadline','extra','source_change'])
def test_no_retry_or_issuance_after_actual_io_failures_and_cancellation(storage,failure):
    value,src,files,_=storage;triggered=[]
    def inject(v,kind,fd):
        if triggered:return
        expected='flush' if failure in ('extra','source_change') else 'write' if failure in ('cancel','deadline') else failure
        if kind!=expected:return
        triggered.append(kind)
        if failure=='cancel':raise KeyboardInterrupt('PRIVATE_CANCEL_NO_LOG')
        if failure=='deadline':v.deadline=time.monotonic()-1;return
        if failure=='extra':
            with open(os.path.join(src.root,'app','unlisted-private-name'),'wb') as stream:stream.write(b'owned')
        elif failure=='source_change':
            with open(os.path.join(src.root,'app/a/b/c/data'),'ab') as stream:stream.write(b'changed')
        else:raise OSError('PRIVATE_IO_NO_LOG')
    value.inject=inject
    # Source namespace is checked once before copying; mutate later and verify
    # retained source identity/content stability rather than accept replacement.
    if failure=='extra':
        def inject(v,kind,fd):
            if kind=='flush' and not triggered:
                triggered.append(kind);os.mkdir('unlisted-private-name',0o700,dir_fd=v.dest['app'])
        value.inject=inject
    with pytest.raises(runtime.RuntimeStagingFailure):
        _under_lease(value.lease,lambda:value._construct_tree(src,create=True))
    assert triggered and value.failed and value not in runtime._issued
    n=len(value.events)
    with pytest.raises(runtime.CandidateRefused):value._construct_tree(src,create=True)
    assert len(value.events)==n


def test_close_checks_original_cleanup_budget_before_each_handle_and_never_retries(storage,monkeypatch):
    value,src,files,_=storage
    _under_lease(value.lease,lambda:value._construct_tree(src,create=True))
    initial=tuple(value.handles);checks=[]
    def budget(resource,deadline=None,*,cleanup=False):
        assert resource is value.lease and cleanup and deadline is None
        checks.append(resource)
        if len(checks)==3:raise RuntimeError('original cleanup expired')
    monkeypatch.setattr(authority,'budget',budget)
    with pytest.raises(BaseExceptionGroup):value.close()
    assert len(checks)==3 and value.close_attempts[-2:]==list(reversed(initial))[:2]
    assert tuple(value.handles)==initial[:-2] and not value.closed
    with pytest.raises(runtime.CandidateRefused):value.close()
    assert len(checks)==3


@pytest.mark.parametrize('flag',['_nt_create_pending','_query_unknown'])
def test_unacknowledged_native_borrower_refuses_close_before_any_pin_removal(storage,flag):
    value,src,files,_=storage
    _under_lease(value.lease,lambda:value._construct_tree(src,create=True))
    initial=tuple(value.handles);attempts=tuple(value.close_attempts);setattr(value.api.readonly,flag,True)
    with pytest.raises(BaseExceptionGroup):value.close()
    assert tuple(value.handles)==initial and tuple(value.close_attempts)==attempts and not value.closed


def test_query_registration_retains_original_storage_on_pending_exception_and_blocks_close(monkeypatch):
    monkeypatch.setattr(handles.C,'get_last_error',lambda:997,raising=False)
    for result in ('pending','interrupt'):
        api=SimpleNamespace();buf=C.create_string_buffer(128);output=C.c_uint32()
        def call(*args):
            assert any(row[0] is api and row[-1][-1] is output for row in handles._ACTIVE_NATIVE_QUERIES.values())
            if result=='interrupt':raise KeyboardInterrupt()
            return 0
        with pytest.raises(BaseException):handles.query_call(api,'CONTROLLED',(call),(buf,C.byref(output)),(buf,output))
        assert api._query_unknown
        assert handles._UNKNOWN_NATIVE_QUERIES[-1][2][-1][-1] is output
        with pytest.raises(Exception):handles.query_call(api,'FORBIDDEN',lambda:1,())


def test_same_length_change_in_writer_close_gap_is_refused_by_final_readonly_hash(storage):
    value,src,files,_=storage;changed=[]
    original_close=value.api.close
    def close_and_change(fd):
        path=os.readlink('/proc/self/fd/'+str(fd));original_close(fd)
        if path.endswith('/app/a/b/c/data') and not changed:
            before=os.stat(path)
            with open(path,'r+b') as stream:stream.write(b'X'*before.st_size);stream.flush();os.fsync(stream.fileno())
            after=os.stat(path)
            assert (before.st_dev,before.st_ino,before.st_size,before.st_nlink,before.st_mode)==(after.st_dev,after.st_ino,after.st_size,after.st_nlink,after.st_mode)
            changed.append(path)
    value.api.close=close_and_change
    with pytest.raises(runtime.RuntimeStagingFailure) as caught:
        _under_lease(value.lease,lambda:value._construct_tree(src,create=True))
    assert changed and caught.value.stage=='READBACK_FILE' and caught.value.relative_path=='app/a/b/c/data'
    assert value.failed and value not in runtime._issued


def test_failed_close_is_attempted_once_never_reported_closed_or_retried(storage):
    value,src,files,_=storage
    _under_lease(value.lease,lambda:value._construct_tree(src,create=True))
    target=value.handles[-1];original=value.api.close;calls=[]
    def close(fd):
        calls.append(fd)
        if fd==target:raise OSError('PRIVATE_CLOSE_UNKNOWN')
        original(fd)
    value.api.close=close
    with pytest.raises(BaseExceptionGroup):value.close()
    assert calls.count(target)==1 and not value.closed and value.failed and value.cleanup_errors
    with pytest.raises(runtime.CandidateRefused):value.close()
    assert calls.count(target)==1
    os.close(target)  # Test-owned synchronous failure was injected BEFORE os.close.


def test_native_create_original_outputs_survive_exception_failed_handle_and_pending(monkeypatch):
    from scripts.windows_portable import native_protected_objects as protected
    for status in ('exception','pending','failed-with-handle','invalid-success','inconsistent-io'):
        value=object.__new__(runtime.NativeRuntimeInstallation)
        value.failed=value.closed=False;value.handles=[];value.cleanup_errors=[];value._gate=lambda:None
        value.deadline=time.monotonic()+60;value.lease=object()
        value.probe=SimpleNamespace(sid_bytes=protected.sid_bytes('S-1-5-21-100'))
        value.api=SimpleNamespace(readonly=SimpleNamespace())
        def ntcreate(h,access,oa,io,*rest):
            # The submit helper holds all original pointers before native entry.
            actual_h=C.cast(h,C.POINTER(handles.PTR)).contents
            assert any(C.addressof(row[1])==C.addressof(actual_h) for row in protected._inflight.values())
            actual_h.value=41 if status!='invalid-success' else None
            if status=='inconsistent-io':C.cast(io,C.POINTER(handles.IOStatus)).contents.Status=0xc0000022
            if status=='exception':raise KeyboardInterrupt()
            return 0x103 if status=='pending' else 0xc0000022 if status=='failed-with-handle' else 0
        value.api.ntcreate=ntcreate
        before=set(handles._NT_CREATE_PENDING)
        with pytest.raises(BaseException):value._create(29,'owned-name',False)
        assert value.api.readonly._nt_create_pending and not value.handles
        row=next(handles._NT_CREATE_PENDING[k] for k in set(handles._NT_CREATE_PENDING)-before)
        assert row[0] is value.api.readonly and row[3].RootDirectory==29
        assert row[4].Length==len('owned-name'.encode('utf-16-le')) and row[-1] is not None
        with pytest.raises(BaseException):value._create(29,'owned-name',False)


def test_known_sync_query_success_and_failure_release_registry_without_unknown(monkeypatch):
    monkeypatch.setattr(handles.C,'get_last_error',lambda:5,raising=False)
    api=SimpleNamespace();before=set(handles._ACTIVE_NATIVE_QUERIES)
    for result in (1,0):assert handles.query_call(api,'CONTROLLED',lambda:result,())==result
    assert set(handles._ACTIVE_NATIVE_QUERIES)==before and not getattr(api,'_query_unknown',False)
