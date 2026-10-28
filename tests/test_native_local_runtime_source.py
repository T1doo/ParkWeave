"""Cloud source/protocol checks, never native Windows acceptance."""
import ctypes as C
import selectors
import socket
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from psycopg import pq
from psycopg.rows import dict_row
from psycopg.conninfo import make_conninfo

from scripts.windows_portable import native_protected_bootstrap as bootstrap
from scripts.windows_portable.native_composition import compose_native_local_preparation
from scripts.windows_portable.endpoint_plan import PlanMode,EndpointRequest
from scripts.windows_portable.native_database_endpoint import _OwnedConnection


def test_concrete_factory_is_pure_and_new_retains_original_gate(tmp_path):
    from scripts.windows import lifecycle
    from scripts.windows_portable import native_instance_security as native
    with patch.object(native._NativeLayout,'__init__',side_effect=AssertionError('native IO')):
        invocation=compose_native_local_preparation(base=str(tmp_path),mode=PlanMode.NEW,
            request=EndpointRequest(55431,58761),runtime=dict(source_commit='a'*40,manifest_sha256='b'*64),
            initdb_sha256='c'*64,initdb_size=1,postgres_sha256='d'*64,postgres_size=1,
            python_sha256='e'*64,python_size=1,challenge='f'*32)
        assert invocation.processes.endpoint_source is invocation.security.security
        assert invocation.processes.cluster.prerequisites.security is invocation.security.security
        with pytest.raises(lifecycle.BoundaryError) as caught:
            invocation.create(str(tmp_path/'new'),lambda value:pytest.fail('unexpected running workspace'))
        assert caught.value.parkweave_lifecycle_reason=='OWNER_MUTATION_PAUSED'
        with pytest.raises(lifecycle.BoundaryError):
            bootstrap.initialize(None,None,None,None,None,time.monotonic()+5)
        assert list(tmp_path.iterdir())==[]


class Function:
    def __init__(self,call):self.call=call
    def __call__(self,*args):return self.call(*args)


def test_pending_write_keeps_original_buffer_until_observed_completion(monkeypatch):
    calls=[]
    kernel=SimpleNamespace(**{name:Function(lambda *args:1) for name in (
        'CreateEventW','WriteFile','GetOverlappedResult','CancelIoEx','WaitForSingleObject','CloseHandle')})
    kernel.CreateEventW=Function(lambda *args:17)
    kernel.WriteFile=Function(lambda *args:calls.append('write') or 0)
    kernel.CancelIoEx=Function(lambda *args:calls.append('cancel') or 1)
    kernel.GetOverlappedResult=Function(lambda *args:0)
    monkeypatch.setattr(C,'get_last_error',lambda:997,raising=False)
    server=SimpleNamespace(_kernel=kernel,_handle=19,_pending_write=None,_closed=False)
    writer=bootstrap._PipeWrite(server,'PUBLIC_TEST_PASSWORD')
    with pytest.raises(bootstrap.CandidateRefused):writer.send(time.monotonic()+.02)
    assert not writer.cancel_and_observe(time.monotonic()+.02)
    assert bootstrap._active_writes[id(writer)] is writer and server._pending_write is writer
    assert bytes(writer.buffer)==b'PUBLIC_TEST_PASSWORD\n'
    writer.cancel_and_observe(time.monotonic()+.02)
    assert calls==['write','cancel']
    monkeypatch.setattr(C,'get_last_error',lambda:995)
    assert writer.cancel_and_observe(time.monotonic()+.02)
    writer.finish()
    assert bytes(writer.buffer)==b'\0'*len(writer.buffer)
    assert server._pending_write is None and id(writer) not in bootstrap._active_writes


def test_owned_sql_wait_honors_absolute_budget_on_real_postgresql(pg):
    # Actual cloud libpq/PG behavior only. No Windows witness is substituted.
    raw=pq.PGconn.connect_start(pg.get_uri().encode())
    while True:
        status=raw.connect_poll()
        if status==pq.PollingStatus.OK:break
        assert status in (pq.PollingStatus.READING,pq.PollingStatus.WRITING)
        with selectors.DefaultSelector() as selector:
            selector.register(raw.socket,selectors.EVENT_READ if status==pq.PollingStatus.READING else selectors.EVENT_WRITE)
            assert selector.select(2)
    connection=_OwnedConnection(raw,row_factory=dict_row)
    connection._deadline=time.monotonic()+.15
    started=time.monotonic()
    try:
        with pytest.raises(Exception):connection.execute('SELECT pg_sleep(5)')
        assert time.monotonic()-started<1
    finally:connection.close()
    assert raw.status==pq.ConnStatus.BAD


def test_libpq18_connect_start_has_not_sent_startup_bytes():
    if not 180000<=pq.version()<190000:pytest.skip('pinned libpq18 protocol family only')
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
        listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(2)
        raw=pq.PGconn.connect_start(make_conninfo(host='127.0.0.1',hostaddr='127.0.0.1',
            port=listener.getsockname()[1],user='postgres',dbname='postgres',
            password='PUBLIC_PROTOCOL_TEST_ONLY',passfile='/dev/null',
            sslmode='disable',gssencmode='disable',require_auth='scram-sha-256').encode())
        try:
            assert raw.status in (pq.ConnStatus.STARTED,pq.ConnStatus.MADE)
            peer,_=listener.accept()
            with peer:
                peer.settimeout(.05)
                with pytest.raises(TimeoutError):peer.recv(1024)
                # Only explicit polling may progress beyond TCP establishment;
                # libpq may yield WRITING before it serializes startup.
                for _ in range(4):
                    status=raw.connect_poll()
                    if status==pq.PollingStatus.READING:break
                    assert status==pq.PollingStatus.WRITING
                    with selectors.DefaultSelector() as selector:
                        selector.register(raw.socket,selectors.EVENT_WRITE)
                        assert selector.select(1)
                else:pytest.fail('startup did not enter read state')
                peer.settimeout(1)
                startup=peer.recv(1024)
                assert b'user\0postgres\0' in startup and b'PUBLIC_PROTOCOL_TEST_ONLY' not in startup
        finally:raw.finish()


def test_runtime_package_contains_native_factory_dependency_files():
    from scripts.windows_portable.build import RUNTIME_SOURCES
    import ast
    packaged=set(RUNTIME_SOURCES)
    for name in packaged:
        source=Path(name)
        assert source.is_file(),name
        if not name.startswith('scripts/windows_portable/'):continue
        for node in ast.walk(ast.parse(source.read_text())):
            if isinstance(node,ast.ImportFrom) and node.level==1:
                names=[node.module] if node.module else [alias.name for alias in node.names]
                for module in names:
                    path='scripts/windows_portable/'+module.split('.')[0]+'.py'
                    assert path in packaged,(name,path)
