"""Actual owned Linux demo startup; no installed/production database migration."""
import importlib.util
import json
import os
import shutil
from pathlib import Path
import socket
import subprocess
import sys
import time
from http.client import HTTPConnection

import pgserver
import psycopg
from psycopg.conninfo import make_conninfo
import pytest

from parkweave.process_env import minimal_environment
from parkweave.store import Denied

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('linux_demo_startup', ROOT/'scripts/linux_fixture_server.py')
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)
pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux owned demo; native Windows adapter not implemented')


def test_fresh_database_real_receipt_schema25_and_cleanup_preserves_existing_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    old = tmp_path/'.runtime'
    old.mkdir()
    sentinel = old/'synthetic-sessions.json'
    sentinel.write_bytes(b'SYNTHETIC existing state must remain unchanged')
    with demo.demo_database(True) as (runtime, owner):
        temporary = runtime.parent
        assert runtime != old and temporary.is_dir()
        assert owner._case_fact_fixture_receipt.database_name == 'parkweave'
        with owner.connect() as c:
            assert c.execute('SELECT max(version) v FROM schema_version').fetchone()['v'] == 28
            assert c.execute('SELECT count(*) n FROM cases').fetchone()['n'] == 0
            assert c.execute('SELECT count(*) n FROM run_assignments').fetchone()['n'] == 0
    assert not temporary.exists()
    assert sentinel.read_bytes() == b'SYNTHETIC existing state must remain unchanged'


def test_existing_schema24_is_refused_without_retroactive_ticket_or_ddl(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = tmp_path/'.runtime/smoke-pg'
    data.parent.mkdir()
    server = pgserver.get_server(data, cleanup_mode='stop')
    try:
        with psycopg.connect(server.get_uri(), autocommit=True) as c:
            c.execute('CREATE DATABASE parkweave')
            c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
        dsn = make_conninfo(server.get_uri(), dbname='parkweave')
        with psycopg.connect(dsn) as c:
            c.execute((ROOT/'src/parkweave/schema.sql').read_text())
            for version in range(2, 25):
                c.execute((ROOT/f'src/parkweave/migration-{version:03d}.sql').read_text())
        with pytest.raises(Denied, match='preserve it and use --fresh-fixture'):
            with demo.demo_database(False):
                pytest.fail('existing schema24 must not receive a reconstructed receipt')
        # Restart only this test's cluster to independently inspect preserved data.
        server = pgserver.get_server(data, cleanup_mode='stop')
        with psycopg.connect(make_conninfo(server.get_uri(), dbname='parkweave')) as c:
            assert c.execute('SELECT max(version) FROM schema_version').fetchone()[0] == 24
            assert not c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='preparations' AND column_name='fact_clarifications'").fetchone()
        assert (data/'PG_VERSION').is_file()
    finally:
        server.cleanup()


def test_one_unconfirmed_child_does_not_skip_other_owned_child_cleanup():
    class Child:
        def __init__(self, pid, blocked):
            self.pid, self.blocked, self.returncode = pid, blocked, None
            self.terminated = False
        def poll(self):return self.returncode
        def terminate(self):self.terminated = True
        def kill(self):pass
        def wait(self, timeout):
            if self.blocked:raise subprocess.TimeoutExpired(['SYNTHETIC owned child'], timeout)
            self.returncode = 0
    first, second = Child(101, True), Child(102, False)
    with pytest.raises(demo.DemoStopUnconfirmed):
        demo.stop_children([first, second])
    assert first.terminated and second.terminated and second.returncode == 0


def test_unconfirmed_service_stop_retains_only_this_fresh_directory():
    runtime = None
    try:
        with pytest.raises(demo.DemoStopUnconfirmed):
            with demo.demo_database(True) as (runtime, owner):
                raise demo.DemoStopUnconfirmed('SYNTHETIC service stop fault')
        assert runtime is not None and runtime.parent.is_dir()
        assert not (runtime.parent/'data/postmaster.pid').exists()
    finally:
        if runtime is not None:
            shutil.rmtree(runtime.parent)


def test_actual_fresh_launcher_reports_own_ready_api_and_stops_all_owned_services(tmp_path):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    log = tmp_path/'launcher.log'
    runtime = None
    with log.open('w') as output:
        process = subprocess.Popen(
            [sys.executable, str(ROOT/'scripts/linux_fixture_server.py'), '--fresh-fixture',
             '--preparation-fixtures', '--port', str(port)], cwd=tmp_path,
            env=minimal_environment(os.environ, PYTHONPATH=str(ROOT/'src')),
            stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic()+30
            evidence = None
            while time.monotonic() < deadline:
                for line in log.read_text().splitlines():
                    if line.startswith('{'):
                        row = json.loads(line)
                        if row.get('api_pid'):
                            evidence = row
                if evidence:
                    break
                assert process.poll() is None, 'inspect owned launcher.log for startup failure'
                time.sleep(.1)
            assert evidence is not None, 'owned demo readiness deadline exceeded'
            runtime = Path(evidence['runtime_directory'])
            assert evidence['temporary_fixture'] is True and runtime.is_dir()
            connection = HTTPConnection('127.0.0.1', port, timeout=2)
            connection.request('GET', '/health')
            response = connection.getresponse()
            health = json.loads(response.read())
            connection.close()
            assert response.status == 200 and health['process_id'] == evidence['api_pid']
            assert health['schema'] == 28 and health['execution_mode'] == 'LOCAL'
            # Existing original synthetic seed only, scoped to the new temporary DB.
            sessions = json.loads((runtime/'synthetic-sessions.json').read_text())
            connection = HTTPConnection('127.0.0.1', port, timeout=2)
            connection.request('GET', '/api/preparations', headers={'Authorization': 'Bearer '+sessions['fixture-a']})
            response = connection.getresponse()
            assert response.status == 200 and json.loads(response.read())['items'] == []
            connection.close()
            assert not (tmp_path/'.runtime').exists()
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=40)
    assert process.returncode == 0
    assert runtime is not None and not runtime.parent.exists()
    with pytest.raises(OSError):
        with socket.create_connection(('127.0.0.1', port), timeout=.5):
            pytest.fail('owned API must stop with its launcher')


@pytest.mark.parametrize('retained_version',[25,26,27,28])
def test_existing_supported_linux_demo_is_read_without_upgrade_or_state_reset(tmp_path,monkeypatch,retained_version):
    from parkweave.store import Store
    from parkweave.case_fact_clarifications import capture_fixture_cluster
    monkeypatch.chdir(tmp_path)
    data=tmp_path/'.runtime/smoke-pg';data.parent.mkdir()
    server=pgserver.get_server(data,cleanup_mode='stop')
    try:
        cluster=capture_fixture_cluster(server.get_uri(),data.resolve())
        with psycopg.connect(server.get_uri(),autocommit=True) as c:
            c.execute('CREATE DATABASE parkweave')
            c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
        owner=Store(make_conninfo(server.get_uri(),dbname='parkweave'))
        with owner.connect() as c:owner._case_fact_fixture_receipt=cluster.record_created_database(c)
        owner.migrate()
        with owner.connect() as c:
            # Isolated old-marker/column fixture. No installed/native DB touched.
            c.execute('DELETE FROM schema_version WHERE version>%s',(retained_version,))
            if retained_version<28:c.execute('ALTER TABLE preparations DROP COLUMN fact_bundle')
            if retained_version<27:c.execute('ALTER TABLE preparations DROP COLUMN opportunities')
            before=c.execute('SELECT version FROM schema_version ORDER BY version').fetchall()
        server.cleanup();server=None
        with demo.demo_database(False) as (runtime,reopened):
            assert runtime==tmp_path/'.runtime'
            with reopened.connect() as c:
                assert c.execute('SELECT version FROM schema_version ORDER BY version').fetchall()==before
                assert bool(c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='preparations' AND column_name='opportunities'").fetchone())==(retained_version>=27)
                assert bool(c.execute("SELECT 1 FROM information_schema.columns WHERE table_name='preparations' AND column_name='fact_bundle'").fetchone())==(retained_version==28)
    finally:
        if server is not None:server.cleanup()
