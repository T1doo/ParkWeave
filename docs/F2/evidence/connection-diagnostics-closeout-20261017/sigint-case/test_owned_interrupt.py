"""Independent interruption smoke using only the existing owned fixtures."""
from pathlib import Path
import json,os,threading
import pytest
from conftest import pg,fixture
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_native_run_access_writer import writer_fixture
import owned_connection_diagnostics as diagnostics


def test_owned_sigint_cleanup(writer_fixture):
    h=writer_fixture
    diagnostic=diagnostics.current()
    assert diagnostic is not None
    conn=h.f[0].connect()
    backend_pid=conn.info.backend_pid
    try:
        with conn:
            assert conn.execute('SELECT 1 value').fetchone()['value']==1
            ready=dict(pytest_pid=os.getpid(),writer_pid=h.writer_process.pid,
                       writer_process_started=h.pin.process_started,held_backend_pid=conn.info.backend_pid)
            diagnostic.emit('SMOKE_READY',**ready)
            Path(__file__).resolve().parents[1].joinpath('sigint-ready.json').write_text(json.dumps(ready)+'\n')
            threading.Event().wait(45)
            pytest.fail('owned controller did not send expected SIGINT within smoke budget')
    finally:
        diagnostic.emit('SMOKE_TEST_FINALLY',held_backend_pid=backend_pid,
                        held_connection_closed=conn.closed)
