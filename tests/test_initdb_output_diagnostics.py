"""Controlled exit observations and anonymous public stderr; no backend/secret."""
import ctypes as C
import json
import os
from types import SimpleNamespace
import pytest
from scripts.windows_portable.initdb_output_capture import InitdbOutputCapture,PostgresOutputCapture,labels
from scripts.windows_portable.processes import PrivateProcessAdapter,OwnedProcessExited,ProcessRefused
from scripts.windows_ci.native_failure_diagnostics import detail

PRIVATE='SYNTHETIC_PRIVATE_PATH_NOT_FOR_LOGS'


def test_fixed_labels_never_return_child_text():
    raw=('initdb: error: could not read password file '+PRIVATE).encode()
    assert labels(raw)==('PASSWORD_INPUT_ERROR','INITDB_REPORTED_ERROR')
    assert PRIVATE not in json.dumps(labels(raw))


def test_live_identity_refuses_exit_with_exact_numeric_code():
    value=object.__new__(PrivateProcessAdapter);value.unknown=False
    calls=[]
    value.backend=SimpleNamespace(observe=lambda *a:(calls.append('observe') or 0xc0000135))
    group=SimpleNamespace(creating=False,stopped=False,started=True,resources={})
    with pytest.raises(OwnedProcessExited) as caught:value._live_identity(group)
    assert caught.value.code==0xc0000135 and calls==['observe']
    assert detail(caught.value,'ProcessRefused')['owned_exit_code']==0xc0000135


def test_alive_identity_still_requires_original_pid_birth_and_hash():
    value=object.__new__(PrivateProcessAdapter);value.unknown=False
    value.backend=SimpleNamespace(observe=lambda *a:None)
    group=SimpleNamespace(creating=False,stopped=False,started=True,
        resources={'pid':123,'birth':(123,456)},command=SimpleNamespace(sha256='a'*64))
    assert value._live_identity(group)==(123,(123,456),'a'*64)
    group.resources.clear()
    with pytest.raises(ProcessRefused):value._live_identity(group)


@pytest.mark.parametrize('code',[True,1.5,PRIVATE,2**32,-2**31-1])
def test_unbounded_exit_codes_refuse(code):
    with pytest.raises(ProcessRefused):OwnedProcessExited(code)


def test_no_output_read_after_any_possible_secret_write():
    value=object.__new__(InitdbOutputCapture)
    assert value.snapshot(secret_started=True)==dict(status='SUPPRESSED_AFTER_SECRET',bytes_read=0,truncated=False,labels=())
    assert value.snapshot(secret_started=None)['status']=='SUPPRESSED_AFTER_SECRET'


def test_peek_limits_single_consumer_read_without_exporting_bytes(monkeypatch):
    value=object.__new__(InitdbOutputCapture);value.read_fd=7;value.get_handle=lambda fd:8
    def peek(handle,buffer,size,read,available,left):
        C.cast(available,C.POINTER(C.c_uint32)).contents.value=65537;return True
    value.peek=peek;counts=[]
    monkeypatch.setattr(os,'read',lambda fd,count:(counts.append(count) or PRIVATE.encode()))
    result=value.snapshot(secret_started=False)
    assert counts==[65536] and result['truncated'] is True
    assert PRIVATE not in json.dumps(result)


def test_arbitrary_capture_fields_are_never_serialized():
    error=OwnedProcessExited(1);error.capture=dict(status=PRIVATE,bytes_read=1,truncated=False,labels=(PRIVATE,))
    result=detail(error,'ProcessRefused')
    assert result['initdb_output']==dict(details='UNAVAILABLE') and PRIVATE not in json.dumps(result)


@pytest.mark.skipif(os.name!='nt',reason='actual Windows anonymous pipe required')
def test_actual_anonymous_pipe_reads_only_public_test_output_and_closes():
    value=InitdbOutputCapture()
    try:
        os.write(value.write_fd,('initdb: error: could not read password file '+PRIVATE).encode())
        value.close_write();result=value.snapshot(secret_started=False)
        assert result['labels']==('PASSWORD_INPUT_ERROR','INITDB_REPORTED_ERROR')
        assert PRIVATE not in json.dumps(result)
    finally:value.close()
    assert value.read_fd is value.write_fd is None and not value.errors


def test_postgres_pipe_drain_bounds_classification_without_retaining_raw_output(monkeypatch):
    capture=object.__new__(PostgresOutputCapture)
    capture.read_fd=7
    capture.reader=None
    first=(f'FATAL: could not bind socket {PRIVATE}\n').encode()
    chunks=iter([first]+[b'x'*4096]*18+[b''])
    monkeypatch.setattr(os,'read',lambda fd,size:next(chunks))
    capture._drain()
    error=OwnedProcessExited(1)
    error.postgres_capture=capture.snapshot()
    proof=detail(error,'ProcessRefused')
    assert proof['owned_exit_code']==1
    assert proof['postgres_output']==dict(status='CLASSIFIED',bytes_read=65536,truncated=True,
                                         labels=('LISTEN_ADDRESS_UNAVAILABLE','POSTGRES_FATAL'))
    assert PRIVATE not in json.dumps(proof)
    error.postgres_capture['labels']=(PRIVATE,)
    assert detail(error,'ProcessRefused')['postgres_output']==dict(details='UNAVAILABLE')


@pytest.mark.skipif(os.name!='nt',reason='actual Windows anonymous pipe required')
def test_actual_postgres_pipe_drains_inherited_output_and_closes():
    capture=PostgresOutputCapture()
    writer=os.dup(capture.write_fd)
    try:
        capture.start()
        os.write(writer,('Execution of PostgreSQL by a user with administrative permissions '+PRIVATE).encode())
    finally:
        os.close(writer)
    try:
        capture.reader.join(2)
        assert capture.snapshot()['labels']==('ADMIN_TOKEN_ERROR',)
    finally:
        capture.close()
    assert capture.read_fd is capture.write_fd is None
