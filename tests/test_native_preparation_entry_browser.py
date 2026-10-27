"""Real Chromium -> ordinary configured_app subprocess -> isolated owned PG.

Positive preconditions are existing synthetic fixtures. No provider or Approval
fixture crosses into the API process; delayed replies are client fault injection.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from uuid import uuid4

import httpx
import pytest
from playwright.sync_api import sync_playwright, expect

from parkweave.process_env import minimal_environment
from scripts.linux_fixture_server import stop_children
from test_preparation import preparation_fixture, filled, headers
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_case_goal_results import complete
from test_service_plan_manual_lock import stored, lock
from test_source_change_adoption import changed
from test_native_preparation_entry import snapshot


@contextmanager
def ordinary_process(f, tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    repo = Path(__file__).resolve().parents[1]
    env = minimal_environment(os.environ, PYTHONPATH=str(repo/'src'),
                              PARKWEAVE_DSN=f[0].dsn, PARKWEAVE_MODE='LOCAL')
    with (tmp_path/'ordinary-api.log').open('w') as log:
        child = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'parkweave.api:configured_app',
                                  '--factory', '--host', '127.0.0.1', '--port', str(port),
                                  '--log-level', 'warning', '--no-access-log'], cwd=repo,
                                 env=env, stdout=log, stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=10) as api:
                deadline = time.monotonic()+15
                while time.monotonic() < deadline:
                    assert child.poll() is None, 'owned API exited; see ordinary-api.log'
                    try:
                        health = api.get('/health')
                        if health.status_code == 200 and health.json()['process_id'] == child.pid:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(.05)
                else: pytest.fail('owned ordinary API readiness deadline exceeded')
                yield api
        finally:
            stop_children([child])


def open_record(page, api, f, p):
    page.goto(str(api.base_url) + '?preparation_id=' + p['preparation_id'])
    page.locator('#token').fill(f[2]['fixture-a'])
    page.locator('#existing-preparation-read').click()
    expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')


def test_ordinary_process_opens_original_source_preview_and_explicit_adoption(link_fixture, tmp_path):
    f = link_fixture
    p, _, _, _ = complete(f, local=True)
    assert lock(f, p, 'P1').status_code == 200
    card = changed(f, p)
    old = stored(f, p)
    before = snapshot(f[1])
    with ordinary_process(f, tmp_path) as api, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        seen = []
        page.on('request', lambda r: seen.append(dict(method=r.method, path=r.url.split(str(api.base_url).rstrip('/'))[-1])))
        open_record(page, api, f, p)
        assert snapshot(f[1]) == before
        page.locator('#opp-read').click()
        preview = page.locator('[data-opp-plan-preview="' + card['id'] + '"]')
        expect(preview).to_be_enabled()
        preview.click()
        expect(page.locator('#opp-plan-status')).to_contain_text('尚未采纳或核验')
        expect(page.locator('#opp-plan-impact')).to_contain_text('P2、P3、P4、P5')
        assert all(r['method'] == 'GET' for r in seen)
        # The ORIGINAL plan GET persists observed invalidation flags. Entry GET
        # above is read-only; this original source algorithm is deliberately kept.
        inspected = stored(f, p)
        assert inspected['id'] == old['id'] and inspected['revision'] == old['revision']
        assert inspected['events'] == old['events'] and inspected['history'] == old['history']
        assert inspected['steps'][0] == old['steps'][0]
        for current, previous in zip(inspected['steps'][1:], old['steps'][1:]):
            assert current['invalidated'] is True
            assert {k:v for k,v in current.items() if k != 'invalidated'} == {k:v for k,v in previous.items() if k != 'invalidated'}
        observed = snapshot(f[1])
        assert {t:v for t,v in observed.items() if t != 'preparations'} == {t:v for t,v in before.items() if t != 'preparations'}
        before_parent = before['preparations'][0]['row']
        observed_parent = observed['preparations'][0]['row']
        assert {k:v for k,v in observed_parent.items() if k != 'service_case_plan'} == {k:v for k,v in before_parent.items() if k != 'service_case_plan'}
        assert api.get('/api/plan-approval/status', headers=headers(f[2])).json()['enabled'] is False
        assert api.get('/api/run-access/status', headers=headers(f[2])).json()['enabled'] is False
        page.locator('#service-plan-reason').fill('SYNTHETIC explicit source adoption through existing ordinary entry')
        page.locator('#opp-plan-confirm').check()
        expect(page.locator('#opp-plan-adopt')).to_be_enabled()
        with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/service-case-plan')) as response:
            page.locator('#opp-plan-adopt').click()
        assert response.value.status == 201
        expect(page.locator('#service-plan-history')).to_contain_text('SYNTHETIC explicit source adoption through existing ordinary entry')
        now = stored(f, p)
        assert now['revision'] == old['revision']+1
        assert now['id'] == old['id'] and now['steps'][0] == old['steps'][0]
        assert [s['id'] for s in now['steps']] == [s['id'] for s in old['steps']]
        assert now['events'][:-1] == old['events'] and now['history'] == old['history']
        after = snapshot(f[1])
        assert {t:v for t,v in after.items() if t != 'preparations'} == {t:v for t,v in before.items() if t != 'preparations'}
        posts = [r for r in seen if r['method'] == 'POST']
        assert posts == [dict(method='POST', path='/api/preparations/'+p['preparation_id']+'/service-case-plan')]
        (tmp_path/'source-entry-proof.json').write_text(json.dumps(dict(
            scope='ISOLATED_SYNTHETIC_PRECONDITIONS_ORDINARY_FACTORY_SUBPROCESS',
            original_plan=old['id'], old_revision=old['revision'], new_revision=now['revision'],
            stable_steps=True, preserved_p1=True, approval_enabled=False, native_access_enabled=False,
            observed_requests=seen), indent=2)+'\n')
        page.screenshot(path=str(tmp_path/'source-entry.png'), full_page=True)
        browser.close()


def test_api_process_restart_new_browser_only_reads_original(preparation_fixture, tmp_path):
    f = preparation_fixture
    p = filled(f)
    before = snapshot(f[1])
    for name in ('first', 'restarted'):
        with ordinary_process(f, tmp_path/name) as api, sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
            page = browser.new_page()
            requests = []
            page.on('request', lambda r: requests.append(r.method))
            open_record(page, api, f, p)
            expect(page.locator('#prep-materials')).to_contain_text('SYNTHETIC source text')
            assert all(method == 'GET' for method in requests)
            assert snapshot(f[1]) == before
            browser.close()


@pytest.mark.parametrize('late_status', [200, 403])
def test_entry_id_aba_and_late_reply_cannot_replace_current_view(preparation_fixture, tmp_path, late_status):
    f = preparation_fixture
    p = filled(f)
    before = snapshot(f[1])
    with ordinary_process(f, tmp_path) as api, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        pending = []
        requests = []
        page.on('request', lambda r: requests.append(r.method))
        def hold_first(route):
            if pending: route.continue_(); return
            pending.append((route, route.fetch()))
        page.route('**/api/preparations/*/entry', hold_first)
        page.goto(str(api.base_url))
        page.locator('#token').fill(f[2]['fixture-a'])
        page.locator('#existing-preparation-id').fill(p['preparation_id'])
        page.locator('#existing-preparation-read').click()
        deadline = time.monotonic()+5
        while not pending and time.monotonic() < deadline: page.wait_for_timeout(20)
        assert pending
        page.locator('#existing-preparation-id').fill(str(uuid4()))
        page.locator('#existing-preparation-id').fill(p['preparation_id'])
        page.locator('#existing-preparation-read').click()
        expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')
        route, response = pending[0]
        if late_status == 200: route.fulfill(response=response)
        else: route.fulfill(status=403, json={'detail':'record unavailable or authorization denied'})
        page.wait_for_timeout(150)
        expect(page.locator('#prep-materials')).to_contain_text('SYNTHETIC source text')
        expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')
        assert all(method == 'GET' for method in requests) and snapshot(f[1]) == before
        browser.close()


def test_unknown_original_material_result_keeps_context_and_get_recovery(preparation_fixture, tmp_path):
    f = preparation_fixture
    p = filled(f)
    with ordinary_process(f, tmp_path) as api, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        seen = []
        page.on('request', lambda r: seen.append((r.method, r.url)))
        open_record(page, api, f, p)
        sent = []
        def lose_reply(route):
            if route.request.method != 'POST': route.continue_(); return
            response = route.fetch()
            assert response.status == 200
            sent.append(route.request.headers['idempotency-key'])
            route.abort('failed')
        page.route('**/api/preparations/*/commands', lose_reply)
        page.locator('#prep-text').fill('SYNTHETIC committed material with lost response')
        page.locator('#prep-source-label').fill('SYNTHETIC explicit existing source')
        page.locator('#prep-evidence button').click()
        expect(page.locator('#prep-command-retry')).to_be_visible()
        assert len(sent) == 1
        before = snapshot(f[1])
        page.locator('#existing-preparation-read').click()
        expect(page.locator('#existing-preparation-status')).to_contain_text('只读核对尚未确认')
        page.locator('#existing-preparation-id').fill(str(uuid4()))
        expect(page.locator('#existing-preparation-id')).to_have_value(p['preparation_id'])
        page.locator('#prep-recovery-read').click()
        expect(page.locator('#prep-materials')).to_contain_text('SYNTHETIC committed material with lost response')
        assert snapshot(f[1]) == before
        assert len([r for r in seen if r[0] == 'POST']) == 1
        assert any('/command-recovery' in url and method == 'GET' for method, url in seen)
        browser.close()
