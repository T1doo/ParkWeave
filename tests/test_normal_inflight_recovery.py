"""Real continuous LOCAL workers, actual process loss and original atomic ledger.

No preview provider, injected execution adapter or manual lease/state update.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from uuid import UUID, uuid4

import httpx
import psutil
import pytest
from psycopg.conninfo import make_conninfo
from parkweave.process_env import minimal_environment
from parkweave.store import Store, Conflict
from parkweave.gateway import ExecutionGateway
from normal_recovery_process import snapshot


pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux own-process fault oracle; Windows native NOT_RUN')


def wait(check, timeout=8):
    end = time.monotonic()+timeout
    while time.monotonic() < end:
        value = check()
        if value:
            return value
        time.sleep(.025)
    raise AssertionError('bounded original worker checkpoint not observed')


class Runtime:
    def __init__(self, fixture, directory):
        self.store, self.owner, self.tokens, _ = fixture
        self.directory = directory
        self.children = []
        self.logs = []
        self.base_env = minimal_environment(os.environ, PARKWEAVE_DSN=self.store.dsn,
                                            PARKWEAVE_MODE='LOCAL', PYTHONDONTWRITEBYTECODE='1')
        self.notes = {'normal_mode': 'LOCAL', 'real_model_calls': False, 'manual_lease_or_business_updates': False}

    def spawn(self, label, argv, **extra):
        logpath = self.directory/(label+'-private.log')
        log = logpath.open('w'); self.logs.append(log)
        env = dict(self.base_env, **extra)
        p = subprocess.Popen([sys.executable, *argv], env=env, stdout=log, stderr=log)
        identity = psutil.Process(p.pid).create_time()
        self.children.append((p, identity))
        return p, logpath

    def signal(self, p, sig):
        identity = next(created for child, created in self.children if child is p)
        assert p.poll() is None and psutil.Process(p.pid).create_time() == identity
        p.send_signal(sig)

    def stop(self, p):
        if p.poll() is None:
            self.signal(p, signal.SIGCONT)
            self.signal(p, signal.SIGTERM)
        p.wait(timeout=8)

    def worker(self, label, *, hold=False):
        appname = 'SYNTHETIC-inflight-'+uuid4().hex
        argv = ['-m', 'parkweave.worker', '--lease-seconds', '1']
        if hold:
            argv += ['--mock-model-wait-seconds', str(8 if hold is True else hold)]
        p, log = self.spawn(label, argv,
                            PARKWEAVE_DSN=make_conninfo(self.store.dsn, application_name=appname))
        return p, log, appname

    def row(self, run):
        with self.owner.connect() as c:
            return c.execute("SELECT r.state,r.fence,r.worker_id,r.heartbeat_count,"
                             "r.lease_until>clock_timestamp() AS valid,o.id AS operation_id,"
                             "o.state AS operation_state,o.receipt FROM runs r "
                             "JOIN operations o ON o.run_id=r.id WHERE r.id=%s", (run,)).fetchone()

    def headers(self, user='fixture-a', key=None):
        h = {'Authorization': 'Bearer '+self.tokens[user]}
        if key:
            h['Idempotency-Key'] = key
        return h

    def submit(self):
        key = 'SYNTHETIC-'+uuid4().hex
        body = {'goal': 'SYNTHETIC normal in-flight original local record'}
        r = self.api.post('/api/runs', headers=self.headers(key=key), json=body)
        assert r.status_code == 202, r.status_code
        run = r.json()['run_id']
        self.notes['initial_http_code'] = r.status_code
        return run, key, body

    def read(self, run):
        r = self.api.get('/api/runs/'+run, headers=self.headers())
        assert r.status_code == 200, r.status_code
        return r.json()

    def done(self, run):
        def drained():
            with self.owner.connect() as c:
                return c.execute("SELECT r.state='SUCCEEDED' AND NOT EXISTS "
                                 "(SELECT 1 FROM outbox WHERE run_id=r.id AND consumed_at IS NULL) AS done "
                                 "FROM runs r WHERE r.id=%s", (run,)).fetchone()['done']
        wait(drained)
        view = self.read(run)
        assert view['execution_mode'] == 'LOCAL' and view['operation']['state'] == 'VERIFIED'
        assert view['case']['state'] == 'NEEDS_INPUT' and view['case']['source'] == 'SYNTHETIC'
        assert view['success_scope'] == 'LOCAL_CASE_CREATED'
        assert view['case']['external_acceptance'] == 'NOT_SUBMITTED'
        assert view['case']['offline_fulfillment'] == 'NO_EVIDENCE'
        with self.owner.connect() as c:
            assert c.execute('SELECT count(*) n FROM cases WHERE run_id=%s', (run,)).fetchone()['n'] == 1
            assert c.execute('SELECT count(*) n FROM operations WHERE run_id=%s', (run,)).fetchone()['n'] == 1
            assert c.execute("SELECT count(*) n FROM outbox WHERE run_id=%s AND payload->>'state'='SUCCEEDED'", (run,)).fetchone()['n'] == 1
            assert c.execute('SELECT count(*) n FROM model_steps').fetchone()['n'] == 0
            assert c.execute('SELECT count(*) n FROM fixture_effects').fetchone()['n'] == 0
            assert c.execute('SELECT count(*) n FROM deliveries WHERE run_id=%s', (run,)).fetchone()['n'] == 2
            assert c.execute('SELECT count(*) n FROM deliveries d JOIN outbox o ON o.id=d.event_id WHERE d.run_id=%s AND o.consumed_at IS NULL', (run,)).fetchone()['n'] == 0
            projection = c.execute('SELECT payload FROM run_projection WHERE run_id=%s', (run,)).fetchone()['payload']
            assert projection['state'] == 'SUCCEEDED'
        self.notes.update(unique_case_operation_terminal_event=True, original_delivery_count=2,
                          zero_model_steps_and_fixture_effects=True)
        return view

    def stale(self, claim):
        before = snapshot(self.owner)
        for callback in [lambda: self.store.heartbeat(claim, 1),
                         lambda: ExecutionGateway(self.store).prepare_dispatch(claim),
                         lambda: self.store.finish(claim)]:
            with pytest.raises(Conflict, match='stale worker or expired lease'):
                callback()
        assert snapshot(self.owner) == before
        self.notes['original_cached_fence_callbacks_rejected_without_writes'] = True

    def stale_during_successor_lease(self, claim):
        # Keep all durable Run/business fields; only the live successor's three
        # legitimate LeaseKeeper renewal fields may change during observation.
        def stable():
            result = snapshot(self.owner)
            with self.owner.connect() as c:
                result['runs'] = c.execute("SELECT to_jsonb(r)-'lease_until'-'heartbeat_count'-'last_heartbeat_at' AS row "
                                           "FROM runs r ORDER BY id").fetchall()
            return result
        def successor_current():
            r = self.row(claim['id'])
            assert r['state'] == 'RUNNING' and r['valid'] and r['fence'] > claim['fence']
        successor_current(); before = stable()
        for callback in [lambda: self.store.heartbeat(claim, 1),
                         lambda: ExecutionGateway(self.store).prepare_dispatch(claim),
                         lambda: self.store.finish(claim)]:
            with pytest.raises(Conflict, match='stale worker or expired lease'):
                callback()
        successor_current(); assert stable() == before
        self.notes['stale_fence_rejected_during_live_successor_lease'] = True

    def drained_terminal(self, run, state):
        def drained():
            with self.owner.connect() as c:
                return c.execute("SELECT r.state=%s AND NOT EXISTS (SELECT 1 FROM outbox "
                                 "WHERE run_id=r.id AND consumed_at IS NULL) AS done "
                                 "FROM runs r WHERE r.id=%s", (state, run)).fetchone()['done']
        wait(drained)
        with self.owner.connect() as c:
            assert c.execute('SELECT payload FROM run_projection WHERE run_id=%s', (run,)).fetchone()['payload']['state'] == state

    @contextmanager
    def block(self, table):
        assert table in ('outbox', 'deliveries')
        with self.owner.connect() as c:
            pid = c.execute('SELECT pg_backend_pid() AS pid').fetchone()['pid']
            c.execute('LOCK TABLE '+table+' IN ACCESS EXCLUSIVE MODE')
            try:
                yield pid
            finally:
                c.rollback()

    def blocked(self, appname, table, blocker):
        with self.owner.connect() as c:
            rows = c.execute("SELECT query,wait_event_type,pg_blocking_pids(pid) AS blockers "
                             "FROM pg_stat_activity WHERE datname=current_database() "
                             "AND application_name=%s", (appname,)).fetchall()
        return any(r['wait_event_type'] == 'Lock' and blocker in r['blockers']
                   and 'INSERT INTO '+table in r['query'] for r in rows)

    def backends_gone(self, appname):
        with self.owner.connect() as c:
            return c.execute('SELECT count(*) n FROM pg_stat_activity WHERE datname=current_database() AND application_name=%s', (appname,)).fetchone()['n'] == 0


@pytest.fixture
def normal_runtime(fixture, tmp_path):
    rt = Runtime(fixture, tmp_path)
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0)); port = s.getsockname()[1]
    api, _ = rt.spawn('api', ['-m', 'uvicorn', 'parkweave.api:configured_app', '--factory',
                             '--host', '127.0.0.1', '--port', str(port)])
    rt.url = f'http://127.0.0.1:{port}'
    with httpx.Client(base_url=rt.url, timeout=3) as client:
        rt.api = client
        try:
            def healthy():
                assert api.poll() is None
                try:
                    r = client.get('/health')
                    return r.status_code == 200 and r.json()['process_id'] == api.pid
                except httpx.TransportError:
                    return False
            wait(healthy)
            yield rt
        finally:
            for child, _ in reversed(rt.children):
                rt.stop(child)
            for log in rt.logs:
                log.close()
            remaining = []
            for child, created in rt.children:
                try:
                    if psutil.Process(child.pid).create_time() == created:
                        remaining.append(child.pid)
                except psutil.NoSuchProcess:
                    pass
            rt.notes['all_known_api_worker_generations_exited'] = not remaining
            (tmp_path/'checkpoint-safe.json').write_text(json.dumps(rt.notes, indent=2)+'\n')
            assert remaining == []


def original_claim(rt, run):
    row = wait(lambda: (r if (r := rt.row(run))['state'] == 'RUNNING' else None))
    return {'id': UUID(run), 'fence': row['fence']}, row


def test_live_old_worker_resumes_after_natural_expiry_takeover_without_duplicate(normal_runtime):
    rt = normal_runtime; run, key, body = rt.submit()
    old, old_log, _ = rt.worker('original', hold=True)
    claim, initial = original_claim(rt, run)
    wait(lambda: rt.row(run)['heartbeat_count'] >= 2)
    successor, _, _ = rt.worker('successor', hold=3)
    time.sleep(.4)
    assert rt.row(run)['fence'] == claim['fence'] and rt.row(run)['valid']
    rt.signal(old, signal.SIGSTOP)
    wait(lambda: rt.row(run)['fence'] > claim['fence'])
    rt.stale_during_successor_lease(claim)
    view = rt.done(run); assert rt.row(run)['worker_id'] != initial['worker_id']
    assert old.poll() is None and successor.poll() is None
    before = snapshot(rt.owner)
    rt.signal(old, signal.SIGCONT)
    wait(lambda: 'claim fenced or authorization changed' in old_log.read_text())
    rt.stale(claim)
    duplicate = rt.api.post('/api/runs', headers=rt.headers(key=key), json=body)
    assert duplicate.status_code == 202 and duplicate.json()['run_id'] == run
    assert rt.read(run) == view and snapshot(rt.owner) == before
    rt.notes.update(real_old_process_suspended_and_resumed=True, valid_lease_competitor_did_not_steal=True,
                    natural_database_expiry_takeover=True, same_key_no_duplicate=True)


def test_process_exit_inside_original_case_transaction_rolls_back_then_takes_over(normal_runtime):
    rt = normal_runtime; run, _, _ = rt.submit()
    with rt.block('outbox') as blocker:
        old, _, appname = rt.worker('original')
        claim, _ = original_claim(rt, run)
        wait(lambda: rt.blocked(appname, 'outbox', blocker))
        assert rt.read(run)['case'] is None and rt.row(run)['operation_state'] == 'PREPARED'
        rt.stop(old)
    wait(lambda: rt.backends_gone(appname))
    assert rt.read(run)['case'] is None and rt.row(run)['operation_state'] == 'PREPARED'
    wait(lambda: not rt.row(run)['valid'])
    rt.stale(claim)
    rt.worker('successor')
    rt.done(run)
    assert rt.row(run)['fence'] > claim['fence']
    rt.stale(claim)
    rt.notes.update(actual_original_outbox_insert_blocked=True, original_process_exited_before_commit=True,
                    original_uncommitted_case_receipt_rolled_back=True, natural_database_expiry_takeover=True)


def test_exit_after_case_commit_restarts_original_consumer_without_reclaim_or_duplicate(normal_runtime):
    rt = normal_runtime; run, _, _ = rt.submit()
    with rt.block('deliveries') as blocker:
        old, _, appname = rt.worker('original')
        wait(lambda: rt.blocked(appname, 'deliveries', blocker))
        persisted = rt.row(run)
        assert persisted['state'] == 'SUCCEEDED' and persisted['fence'] == 1 and persisted['worker_id']
        claim = {'id': UUID(run), 'fence': persisted['fence']}
        committed = rt.read(run)
        assert committed['state'] == 'SUCCEEDED' and committed['operation']['state'] == 'VERIFIED'
        assert committed['case']['state'] == 'NEEDS_INPUT'
        rt.stop(old)
    wait(lambda: rt.backends_gone(appname))
    assert rt.read(run) == committed
    rt.worker('successor'); assert rt.done(run) == committed
    assert rt.row(run)['fence'] == claim['fence']
    rt.stale(claim)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        try:
            for width in (320, 390, 1200):
                context = browser.new_context(viewport={'width': width, 'height': 1100})
                page = context.new_page(); requests = []; errors = []
                page.on('request', lambda r: requests.append(r.method))
                page.on('pageerror', lambda e: errors.append(str(e)))
                try:
                    page.goto(rt.url)
                    assert page.locator('#token').input_value() == ''
                    page.locator('#token').fill(rt.tokens['fixture-a'])
                    page.locator('[data-tab="collaboration"]').click()
                    page.locator('#record-directory-read').click()
                    page.locator('#record-directory-items button').click()
                    page.locator('details.engineering-record > summary').click()
                    wait(lambda: 'LOCAL_CASE_CREATED' in page.locator('#result').inner_text())
                    assert json.loads(page.locator('#result').inner_text()) == committed
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    assert page.evaluate('Object.keys(localStorage).length===0&&Object.keys(sessionStorage).length===0')
                    assert all(method == 'GET' for method in requests) and not errors
                    page.locator('.collaboration-controls').screenshot(path=str(rt.directory/f'recovered-{width}-private.png'))
                finally:
                    context.close()
        finally:
            browser.close()
    for user in ('fixture-b', 'fixture-c'):
        assert rt.api.get('/api/runs/'+run, headers=rt.headers(user)).status_code == 403
    rt.notes.update(actual_original_delivery_insert_blocked=True, original_case_commit_survived_process_loss=True,
                    successor_did_not_reclaim_terminal_operation=True, original_projection_not_reversed=True,
                    cold_page_get_only=True, viewports=[320, 390, 1200], cross_scope_denied=True)


@pytest.mark.parametrize('change', ['execute-revoked', 'cancel'])
def test_current_authority_prevents_new_effect_after_original_process_loss(normal_runtime, change):
    rt = normal_runtime; run, _, _ = rt.submit()
    old, _, appname = rt.worker('original', hold=True)
    claim, _ = original_claim(rt, run); rt.stop(old)
    wait(lambda: rt.backends_gone(appname))
    if change == 'execute-revoked':
        rt.owner.revoke_capability('fixture-a', 'EXECUTE')
        wait(lambda: not rt.row(run)['valid'])
    else:
        assert rt.api.post('/api/runs/'+run+'/cancel', headers=rt.headers()).status_code == 200
    rt.worker('successor')
    state = 'FAILED' if change == 'execute-revoked' else 'CANCELLED'
    rt.drained_terminal(run, state)
    rt.stale(claim)
    view = rt.read(run)
    assert view['case'] is None and view['success_scope'] is None
    assert view['operation']['state'] == ('FAILED_SAFE' if change == 'execute-revoked' else 'PREPARED')
    with rt.owner.connect() as c:
        assert c.execute('SELECT count(*) n FROM cases').fetchone()['n'] == 0
    rt.notes.update(current_authority_change=change, expected_terminal=state, new_effect_count=0,
                    current_revocation_or_control_not_restored=True)
