"""Real original HTML, installed Chromium, ASGI and owned PostgreSQL cancel flow.

The fixture is prepared by original business commands; no response DTO is mocked.
Native Windows, formal AT, production and real models remain NOT_RUN.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from playwright.sync_api import sync_playwright, Error as PlaywrightError
from parkweave.api import create_app
from parkweave.store import Store, Denied
from parkweave import case_cancellation_before_receipt as cb
from test_new_enterprise_local_chain import actual_http
from test_case_cancellation import snapshot
from test_preparation import headers
from test_executor_receipts import ready
from cancel33_fixture_support import (cancel33_case, capability_resource_catalog, capability_catalog,
    preparation_fixture, receipt_fixture)
from test_schema33_before_receipt_cancellation import stable_after_cancel
from test_frontier_real_html import route_helper_artifacts
from conftest import fixture, pg

OUT = Path(os.environ.get('CANCEL33_UI_ARTIFACT_ROOT', '.runtime/cancel33-browser/artifacts'))
SCOPE = 'SYNTHETIC_CASE_CANCEL_AFTER_ACCEPT_BEFORE_FIRST_RECEIPT'


def enter(page, f, p):
    page.locator('#token').fill(f[2]['fixture-a'])
    page.locator('#token').dispatch_event('change')
    page.locator('[data-tab="collaboration"]').click()
    page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})', p['preparation_id'])
    page.wait_for_function('()=>!caseCancelBusy&&!caseReconBusy')


@pytest.mark.parametrize('mode', ['positive', 'lost_commit', 'lost_commit_execute_revoked',
    'lost_commit_read_revoked', 'lost_commit_foreign_case'])
def test_actual_chromium_schema33_explicit_cancel_and_cold_get(cancel33_case, mode):
    t = cancel33_case
    f, p = t['f'], t['p']
    other = None
    original = deepcopy(snapshot(f))
    calls, pending, errors = [], {}, []
    proven = dict(explicit_confirmation=False, original_history_preserved=False,
        detached_store_refused=False, protocol_only_store_refused=False,
        same_process_original_issued_protocol_and_approval_reattached=False,
        cold_http_get_only=False, cold_http_recovery_committed=False,
        expected_recovery_denied=False, next_case_ui_restored=False)
    path = '/api/preparations/' + p['preparation_id'] + '/case-cancellation-before-receipt'
    with actual_http(create_app(f[0])) as (client, python_requests):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            ctx = browser.new_context()
            page = ctx.new_page()
            def requested(request):
                row = dict(method=request.method, path=urlsplit(request.url).path, status=None)
                calls.append(row)
                pending[request] = row
                key = request.header_value('idempotency-key')
                if key:
                    row['request_id'] = key
            def responded(response):
                if response.request in pending:
                    pending[response.request]['status'] = response.status
            page.on('request', requested)
            page.on('response', responded)
            page.on('pageerror', lambda error: errors.append(str(error)))
            try:
                page.goto(str(client.base_url).rstrip('/') + '/')
                enter(page, f, p)
                assert page.evaluate('caseCancelView.scope') == SCOPE
                assert page.evaluate('caseCancelView.can_cancel')
                assert page.locator('#case-cancel-form').is_visible()
                assert not page.locator('#case-cancel-confirm').is_checked()
                assert page.locator('#case-cancel-submit').is_disabled()
                page.locator('#case-cancel-reason').fill('SYNTHETIC original owner explicit cancel; preserve accepted responsibility and occupied resources')
                assert page.locator('#case-cancel-submit').is_disabled()
                assert not any(c['method'] == 'POST' for c in calls)
                page.locator('#case-cancel-confirm').check()
                assert page.locator('#case-cancel-submit').is_enabled()
                if mode != 'positive':
                    def drop_post(route):
                        if route.request.method != 'POST':
                            route.continue_()
                            return
                        response = route.fetch()
                        pending[route.request]['status'] = response.status
                        pending[route.request]['lost_reply'] = True
                        assert response.status == 200
                        route.abort('failed')
                    page.route('**' + path, drop_post)
                    # The browser normally checks immediately. Lose that GET too so the
                    # original opaque handle survives an actual page and app restart.
                    page.route('**' + path + '/recovery/*', lambda route: route.abort('failed'))
                page.locator('#case-cancel-submit').click()
                page.wait_for_function('()=>!caseCancelBusy')
                posts = [c for c in calls if c['method'] == 'POST' and c['path'] == path]
                assert len(posts) == 1 and posts[0]['status'] == 200
                proven['explicit_confirmation'] = True
                key = posts[0]['request_id']
                committed = deepcopy(snapshot(f))
                stable_after_cancel(original, committed)
                proven['original_history_preserved'] = True
                detached = Store(f[0].dsn)
                with pytest.raises(Denied):
                    cb.recover(detached, f[2]['fixture-a'], UUID(p['preparation_id']), key)
                proven['detached_store_refused'] = True
                t['protocol'].attach_store(detached)
                with pytest.raises(Denied):
                    cb.recover(detached, f[2]['fixture-a'], UUID(p['preparation_id']), key)
                proven['protocol_only_store_refused'] = True
                t['bridge'].attach_store(detached)
                t['protocol'].attach_store(detached)
                cold = cb.recover(detached, f[2]['fixture-a'], UUID(p['preparation_id']), key)
                assert cold['status'] == 'COMMITTED' and cold['current']['case_state'] == 'CANCELLED'
                proven['same_process_original_issued_protocol_and_approval_reattached'] = True
                if mode == 'positive':
                    page.wait_for_function('()=>caseCancelHandles().length===0&&caseCancelView?.case_state==="CANCELLED"')
                else:
                    page.wait_for_function('()=>caseCancelHandles().length===1')
                    saved = page.evaluate('caseCancelHandles().map(h=>JSON.parse(localStorage.getItem(h.name)))[0]')
                    assert sorted(saved) == ['actor', 'case', 'expires', 'id', 'key', 'revision', 'stage', 'v']
                    assert saved['v'] == 2 and saved['stage'] == 'BEFORE_RECEIPT' and saved['key'] == key
                    encoded = page.evaluate('JSON.stringify({...localStorage})')
                    assert f[2]['fixture-a'] not in encoded and 'preserve accepted responsibility' not in encoded
                    if mode.endswith(('execute_revoked', 'foreign_case')):
                        with f[1].connect() as connection:
                            connection.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
                    if mode.endswith('read_revoked'):
                        with f[1].connect() as connection:
                            connection.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
                    if mode.endswith('foreign_case'):
                        page.evaluate("()=>{const h=caseCancelHandles()[0];const value=JSON.parse(localStorage.getItem(h.name));value.case=crypto.randomUUID();localStorage.setItem(h.name,JSON.stringify(value));}")
                    page.unroute('**' + path + '/recovery/*')
                    before_cold = len(calls)
                    # A separately constructed Store/app must recover persisted proof.
                    cold_store = Store(f[0].dsn)
                    t['bridge'].attach_store(cold_store)
                    t['protocol'].attach_store(cold_store)
                    with actual_http(create_app(cold_store)) as (cold_client, cold_requests):
                        # Keep the same origin for localStorage by forwarding all future
                        # real HTTP to the cold app, without replacing any response body.
                        def forward(route):
                            response = route.fetch(url=str(cold_client.base_url).rstrip('/') + urlsplit(route.request.url).path)
                            route.fulfill(status=response.status, headers=response.headers, body=response.body())
                        page.route('**/api/**', forward)
                        page.reload()
                        if mode.endswith(('read_revoked', 'foreign_case')):
                            with pytest.raises(PlaywrightError, match='已离开原事项|当前身份无'):
                                enter(page, f, p)
                            assert page.evaluate('preparationView===null&&caseCancelView===null')
                            assert page.locator('#prep-detail').is_hidden()
                            assert page.evaluate('caseCancelHandles().length') == 1
                            expected_403 = '/api/preparations/' + p['preparation_id'] + ('/material-reuse' if mode.endswith('foreign_case') else '')
                            assert any(c['path'] == expected_403 and c['status'] == 403 for c in calls[before_cold:])
                            assert all(c['method'] == 'GET' for c in calls[before_cold:])
                            assert len([c for c in calls if c['method'] == 'POST']) == 1
                            assert snapshot(f) == committed
                            assert not errors
                            proven['expected_recovery_denied'] = True
                            proven['cold_http_get_only'] = True
                            page.unroute_all(behavior='wait')
                            assert not errors
                            return
                        enter(page, f, p)
                        assert page.locator('#case-cancel-recover').is_visible()
                        assert page.evaluate("document.getElementById('prep-detail').classList.contains('case-cancel-recovery-only')")
                        assert page.locator('#prep-decision').is_hidden()
                        assert page.locator('#prep-evidence').is_hidden()
                        assert all(c['method'] == 'GET' for c in calls[before_cold:])
                        page.locator('#case-cancel-recover').click()
                        page.wait_for_function('()=>!caseCancelBusy&&caseCancelHandles().length===0')
                        assert any(c['path'] == path + '/recovery/' + key and c['status'] == 200 for c in calls[before_cold:])
                        assert all(c['method'] == 'GET' for c in calls[before_cold:])
                        assert all(c['method'] == 'GET' for c in cold_requests)
                        proven['cold_http_get_only'] = True
                        proven['cold_http_recovery_committed'] = True
                        if mode.endswith('execute_revoked'):
                            assert not any(c['path'].endswith('/material-reuse') for c in calls[before_cold:])
                page.unroute('**/api/**')
                assert page.evaluate('caseCancelView.case_state') == 'CANCELLED'
                assert page.locator('#case-cancel-form').is_hidden()
                assert page.locator('#case-cancel-submit').is_disabled()
                assert '预约仍占容量' in page.locator('#case-cancel-status').inner_text()
                assert snapshot(f) == committed
                assert len([c for c in calls if c['method'] == 'POST']) == 1
                assert not errors
                if mode == 'lost_commit':
                    other = ready(f)
                    before_navigation = deepcopy(snapshot(f))
                    enter(page, f, other)
                    assert not page.evaluate("document.getElementById('prep-detail').classList.contains('case-cancel-recovery-only')")
                    assert page.locator('#prep-decision').is_visible()
                    assert page.locator('#prep-reopen').is_visible()
                    assert page.locator('#prep-reopen').is_enabled()
                    assert page.evaluate('preparationView.preparation.id') == other['preparation_id']
                    assert snapshot(f) == before_navigation
                    proven['next_case_ui_restored'] = True
            finally:
                OUT.mkdir(parents=True, exist_ok=True)
                report = dict(mode=mode, browser_version=browser.version,
                    actual_browser='INSTALLED_CHROMIUM', actual_html=True, actual_http_asgi=True,
                    owned_postgresql=True, proven=proven, cross_process_restart='NOT_RUN',
                    calls=calls, page_errors=errors,
                    python_http_requests=python_requests, native_windows='NOT_RUN',
                    formal_at='NOT_RUN', production='NOT_RUN', real_models='NOT_RUN')
                (OUT / (mode + '-' + uuid4().hex[:10] + '.json')).write_text(json.dumps(report, indent=2) + '\n')
                page.unroute_all(behavior='wait')
                ctx.close()
                browser.close()
