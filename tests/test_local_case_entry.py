"""Real isolated launcher → configured ASGI → original worker → owned PG.

Fixed synthetic setup is separate from user commands. No business test helpers.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from uuid import uuid4

import httpx
import pytest
from parkweave.process_env import minimal_environment
from parkweave.store import Denied, Store
from scripts.local_case_entry import REPO, locked_state, retained_database, state_path

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux synthetic launcher only')
ENV = minimal_environment(os.environ, PYTHONPATH=str(REPO / 'src') + ':' + str(REPO))


def fresh(tmp_path):
    result = subprocess.run([sys.executable, '-m', 'scripts.local_case_entry', 'setup-synthetic'],
                            cwd=tmp_path, env=ENV, capture_output=True, text=True, timeout=45)
    (tmp_path / 'setup.log').write_text(result.stderr)
    assert result.returncode == 0, 'inspect setup.log'
    root = Path(json.loads(result.stdout)['state_dir'])
    (tmp_path / 'state.json').write_text(json.dumps({'state_dir': str(root)}))
    return root


@contextmanager
def running(root, log_path, port=None):
    if port is None:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
    with log_path.open('w') as output:
        child = subprocess.Popen([sys.executable, '-m', 'scripts.local_case_entry', 'serve',
                                  '--state-dir', str(root), '--port', str(port)],
                                 cwd=log_path.parent, env=ENV, stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 35
            report = None
            while time.monotonic() < deadline:
                for line in log_path.read_text().splitlines():
                    if line.startswith('{'):
                        report = json.loads(line)
                if report:
                    break
                assert child.poll() is None, 'inspect launcher log'
                time.sleep(.1)
            assert report and report['api_pid'] != child.pid
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=5) as api:
                assert api.get('/health').json()['process_id'] == report['api_pid']
                yield api
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=40)
        assert child.returncode == 0
        assert not (root / 'data/postmaster.pid').exists()
        with pytest.raises(OSError):
            socket.create_connection(('127.0.0.1', port), timeout=.2)


def auth(root, actor='fixture-a'):
    sessions = json.loads((root / '.runtime/synthetic-sessions.json').read_text())
    return {'Authorization': 'Bearer ' + sessions[actor]}


def snapshot(root):
    with retained_database(root) as (_, dsn):
        with Store(dsn).connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            return {table: c.execute(f'SELECT to_jsonb(t) row FROM {table} t ORDER BY to_jsonb(t)::text').fetchall()
                    for table in ('principals', 'capability_grants', 'action_grants', 'run_assignments',
                                  'cases', 'runs', 'operations')}


def test_actual_page_new_case_original_worker_and_readonly_restart(tmp_path):
    from playwright.sync_api import sync_playwright
    root = fresh(tmp_path)
    h = auth(root)
    with running(root, tmp_path / 'first-launch.log') as api:
        port = api.base_url.port
        scope = api.get('/api/local-entry/scope', headers=h)
        assert scope.status_code == 200 and scope.json()['can_submit_local_case']
        assert scope.json()['full_chain'] == 'BLOCKED_NO_RUNTIME_ASSIGNMENT_CATALOG_APPROVAL'
        assert api.get('/api/local-entry/scope').status_code == 401
        assert api.get('/api/local-entry/scope', headers={'Authorization': 'Bearer wrong'}).status_code == 403
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                         args=['--no-sandbox'])
            try:
                page = browser.new_page()
                page.goto(str(api.base_url) + '/local-entry')
                page.locator('#session').fill(h['Authorization'][7:])
                page.locator('#check').click()
                page.wait_for_function("document.querySelector('#scope').textContent.includes('当前授权允许')")
                page.screenshot(path=str(tmp_path / 'local-entry-scope.png'), full_page=True)
                page.locator('a[href="/"]').click()
                page.locator('#token').fill(h['Authorization'][7:])
                page.locator('#goal').fill('SYNTHETIC new independent local Case from ordinary page')
                with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/api/runs')) as response:
                    page.locator('#intake button').click()
                assert response.value.status == 202
                run_id = response.value.json()['run_id']
            finally:
                browser.close()
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            result = api.get('/api/runs/' + run_id, headers=h)
            if result.json()['state'] == 'SUCCEEDED':
                break
            time.sleep(.15)
        assert result.status_code == 200 and result.json()['state'] == 'SUCCEEDED'
        assert result.json()['success_scope'] == 'LOCAL_CASE_CREATED'
        saved = result.json()
        assert api.get('/api/runs/' + run_id, headers=auth(root, 'fixture-b')).status_code == 403
        assert api.get('/api/plan-approval/status', headers=h).json()['enabled'] is False
        assert api.get('/api/run-access/status', headers=h).json()['enabled'] is False
    before = snapshot(root)
    assert before['run_assignments'] == []
    with running(root, tmp_path / 'second-launch.log', port=port) as api:
        assert api.get('/api/runs/' + run_id, headers=h).json() == saved
        assert api.get('/api/runs', headers=h).status_code == 200
        assert api.get('/api/local-entry/scope', headers=h).json()['can_submit_local_case']
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                         args=['--no-sandbox'])
            try:
                page = browser.new_page()
                writes = []
                page.on('request', lambda r: writes.append(r.url) if r.method == 'POST' else None)
                page.goto(str(api.base_url) + '/')
                page.locator('#token').fill(h['Authorization'][7:])
                page.locator('[data-tab="collaboration"]').click()
                page.locator('#run').fill(run_id)
                with page.expect_response(lambda r: r.request.method == 'GET' and r.url.endswith('/api/runs/' + run_id)) as response:
                    page.locator('#refresh').click()
                assert response.value.json() == saved
                assert writes == []
            finally:
                browser.close()
    assert snapshot(root) == before
    (tmp_path / 'user-path.json').write_text(json.dumps(dict(run_id=run_id,
        same_port_restart=True, original_page_post_count=1, cold_page_post_count=0,
        state=saved['state'], success_scope=saved['success_scope'],
        case_state=saved['case']['state'], business_and_permission_snapshot_unchanged=True), indent=2))


def test_restart_never_reseeds_revoked_identity_or_missing_capability(tmp_path):
    root = fresh(tmp_path)
    # Explicit negative fixture action through original owner method, outside user flow.
    with retained_database(root) as (_, dsn):
        from psycopg.conninfo import make_conninfo
        # pgserver URI specifies its actual maintenance user, not an inferred OS identity.
        import pgserver
        owner = Store(make_conninfo(pgserver.get_server(root / 'data', cleanup_mode='stop').get_uri(), dbname='parkweave'))
        owner.revoke('fixture-a')
        owner.revoke_capability('fixture-b', 'EXECUTE')
    before = snapshot(root)
    with running(root, tmp_path / 'revoked-launch.log') as api:
        assert api.get('/api/local-entry/scope', headers=auth(root)).status_code == 403
        b = auth(root, 'fixture-b')
        assert api.get('/api/local-entry/scope', headers=b).json()['can_submit_local_case'] is False
        assert api.post('/api/runs', headers={**b, 'Idempotency-Key': uuid4().hex}, json={'goal': 'SYNTHETIC denied'}).status_code == 403
    assert snapshot(root) == before


def test_foreign_symlink_and_concurrent_state_refused_without_repair(tmp_path):
    with pytest.raises(Denied):
        state_path(tmp_path)
    root = fresh(tmp_path)
    link = tmp_path / 'state-link'
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(Denied):
        state_path(link)
    marker = (root / 'local-case.json').read_bytes()
    with locked_state(root):
        with pytest.raises(Denied, match='another local-case launcher'):
            with locked_state(root):
                pytest.fail('concurrent launch must fail')
    assert (root / 'local-case.json').read_bytes() == marker

    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); s.listen()
        port = s.getsockname()[1]
        result = subprocess.run([sys.executable, '-m', 'scripts.local_case_entry', 'serve',
                                 '--state-dir', str(root), '--port', str(port)], cwd=REPO,
                                env=ENV, capture_output=True, text=True, timeout=10)
        assert result.returncode == 1 and s.fileno() != -1
        assert not (root / 'data/postmaster.pid').exists()
    assert (root / 'local-case.json').read_bytes() == marker


@pytest.mark.parametrize('broken', [[], {'namespace': 'FOREIGN'}, 'wrong-system-id', 'unconfirmed-stop'])
def test_bad_marker_or_unconfirmed_stop_blocks_without_repair(tmp_path, broken):
    root = fresh(tmp_path)
    before = snapshot(root)
    marker_path = root / 'local-case.json'
    original = marker_path.read_bytes()
    if broken == 'wrong-system-id':
        value = json.loads(original); value['system_identifier'] = '0'
        marker_path.write_text(json.dumps(value))
    elif broken == 'unconfirmed-stop':
        (root / 'stop-unconfirmed.json').write_text('{"blocked":"OWNED_CHILD_STOP_UNCONFIRMED"}')
    else:
        marker_path.write_text(json.dumps(broken))
    changed = marker_path.read_bytes()
    result = subprocess.run([sys.executable, '-m', 'scripts.local_case_entry', 'serve',
                             '--state-dir', str(root), '--port', '18793'], cwd=tmp_path,
                            env=ENV, capture_output=True, text=True, timeout=15)
    assert result.returncode == 1 and 'Traceback' not in result.stderr
    assert 'LOCAL_ENTRY_BLOCKED' in result.stderr
    assert marker_path.read_bytes() == changed
    assert not (root / 'data/postmaster.pid').exists()
    # Restore only this explicit test input, then independently read original rows.
    marker_path.write_bytes(original)
    if broken == 'unconfirmed-stop':
        (root / 'stop-unconfirmed.json').unlink()
    assert snapshot(root) == before
