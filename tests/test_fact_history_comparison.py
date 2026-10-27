"""Bounded actual page/API/original-worker comparisons on owned PostgreSQL."""
from datetime import datetime, timedelta, timezone
import json
import time
from uuid import uuid4

from psycopg.conninfo import make_conninfo
from parkweave.store import Store
from test_local_case_entry import fresh, running, auth
from test_local_fact_entry import body, assess, wait, snapshot, chromium, fill_source


def live_dsn(root, user='parkweave_app'):
    # Observe only this already-created, running fixture. No server registration
    # or lifecycle reference that could interfere with the launcher's cleanup.
    lines = (root/'data/postmaster.pid').read_text().splitlines()
    assert lines[1] == str(root/'data') and lines[7].strip() == 'ready'
    return make_conninfo(host=lines[4], port=lines[3], dbname='parkweave', user=user)


def live_snapshot(root):
    dsn = live_dsn(root)
    with Store(dsn).connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        return {table: c.execute(f'SELECT to_jsonb(t) row FROM {table} t ORDER BY to_jsonb(t)::text').fetchall()
                for table in ('fact_assertions', 'runs', 'operations', 'principals', 'field_grants',
                              'capability_grants', 'action_grants', 'run_assignments', 'cases', 'model_steps')}


def comparison(api, h, run):
    r = api.get('/api/runs/'+run+'/fact-comparison', headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def test_actual_page_added_conflict_explicit_new_check_and_cold_pair(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    root = fresh(tmp_path); h = auth(root); saved = []
    with running(root, tmp_path/'first.log') as api:
        port = api.base_url.port
        with sync_playwright() as pw:
            browser = chromium(pw)
            try:
                page = browser.new_page(); posts = []
                page.on('request', lambda r: posts.append(r.url) if r.method == 'POST' else None)
                page.goto(str(api.base_url)+'/local-facts')
                page.locator('#session').fill(h['Authorization'][7:])
                fill_source(page, '甲地区', 'SYNTHETIC-comparison-first')
                with page.expect_response(lambda r: r.url.endswith('/api/facts') and r.request.method == 'POST') as response:
                    page.locator('#source-save').click()
                assert response.value.status == 201
                page.locator('#release').click()
                page.locator('#goal').fill('SYNTHETIC historical original check')
                page.locator('#assess-confirm').check()
                with page.expect_response(lambda r: r.url.endswith('/api/runs') and r.request.method == 'POST') as response:
                    page.locator('#assess-save').click()
                old = response.value.json()['run_id']; saved.append(wait(api, h, old))
                page.locator('#release').click()
                page.locator('#history-run').fill(old)
                fill_source(page, '乙地区', 'SYNTHETIC-comparison-added')
                with page.expect_response(lambda r: r.url.endswith('/api/facts') and r.request.method == 'POST') as response:
                    page.locator('#source-save').click()
                added = response.value.json()['fact_id']
                page.locator('#release').click()
                before = live_snapshot(root)
                with page.expect_response(lambda r: r.url.endswith('/fact-comparison')) as response:
                    page.locator('#compare-read').click()
                x = response.value.json()
                expect(page.locator('#comparison-status')).to_contain_text('当前需显式重验')
                expect(page.locator('#comparison-current')).to_contain_text('新增 1')
                expect(page.locator('#comparison-current')).to_contain_text('说明差异')
                expect(page.locator('#comparison-history')).to_contain_text('来源取值一致')
                assert page.evaluate('window.injected') is None
                assert x['historical_receipt'] == saved[0]['operation']['receipt']
                assert x['changes'][0]['added_source_ids'] == [added]
                assert len(x['changes'][0]['current_conflicting_source_ids']) == 2
                assert x['current']['results'][0]['reason'] == 'CONFLICTING_EVIDENCE'
                assert x['source_changes_observed'] and x['requires_explicit_reassessment']
                assert not x['new_assessment_created'] and not x['current']['persisted']
                assert live_snapshot(root) == before and len(posts) == 3
                assert api.get('/api/runs/'+old+'/fact-comparison', headers=auth(root, 'fixture-b')).status_code == 403
                page.locator('#goal').fill('SYNTHETIC explicit current recheck')
                page.locator('#assess-confirm').check()
                with page.expect_response(lambda r: r.url.endswith('/api/runs') and r.request.method == 'POST') as response:
                    page.locator('#assess-save').click()
                new = response.value.json()['run_id']; saved.append(wait(api, h, new))
                page.locator('#release').click()
                page.locator('#compare-pair').click()
                expect(page.locator('#comparison-new')).to_contain_text('来源取值冲突')
                expect(page.locator('#comparison-history')).to_contain_text('来源取值一致')
                left = page.locator('#comparison-history').bounding_box()
                right = page.locator('#comparison-new').bounding_box()
                assert right['x'] > left['x'] and abs(right['y']-left['y']) < 2
                assert len(posts) == 4
                page.screenshot(path=str(tmp_path/'history-current-new.png'), full_page=True)
                page.locator('#history-run').fill(new); page.locator('#run').fill(old)
                page.locator('#compare-pair').click()
                expect(page.locator('#error')).to_contain_text('时间更晚且字段一致')
                assert page.locator('#comparison').text_content() == ''
            finally:
                browser.close()
        assert saved[0]['operation']['receipt']['results'][0]['reason'] == 'CONSISTENT_EVIDENCE'
        assert saved[1]['operation']['receipt']['results'][0]['reason'] == 'CONFLICTING_EVIDENCE'
        assert api.get('/api/runs/'+old, headers=h).json() == saved[0]
    before = snapshot(root)
    assert before['cases'] == before['run_assignments'] == before['model_steps'] == []
    with running(root, tmp_path/'cold.log', port=port) as api:
        with sync_playwright() as pw:
            browser = chromium(pw)
            try:
                page = browser.new_page(); posts = []
                page.on('request', lambda r: posts.append(r.url) if r.method == 'POST' else None)
                page.goto(str(api.base_url)+'/local-facts')
                page.locator('#session').fill(h['Authorization'][7:])
                page.locator('#history-run').fill(old); page.locator('#run').fill(new)
                page.locator('#compare-pair').click()
                expect(page.locator('#comparison-history')).to_contain_text('来源取值一致')
                expect(page.locator('#comparison-new')).to_contain_text('来源取值冲突')
                assert posts == []
                for row in saved:
                    assert api.get('/api/runs/'+row['run_id'], headers=h).json() == row
            finally:
                browser.close()
    assert snapshot(root) == before
    (tmp_path/'chain-proof.json').write_text(json.dumps(dict(old=old, new=new, added=added,
        original_posts=4, comparison_posts=0, cold_posts=0, historical_preserved=True,
        business_and_permission_snapshot_unchanged=True, same_port_restart=True), indent=2))


def test_server_clock_expiry_preserves_history_and_explicit_reassessment(tmp_path):
    root = fresh(tmp_path); h = auth(root)
    with running(root, tmp_path/'expiry.log') as api:
        data = body(); data['validity']['valid_until'] = (datetime.now(timezone.utc)+timedelta(seconds=6)).isoformat()
        r = api.post('/api/facts', headers={**h, 'Idempotency-Key':uuid4().hex}, json=data)
        assert r.status_code == 201
        fact = r.json()['fact_id']; old = assess(api, h); row = wait(api, h, old)
        assert row['operation']['receipt']['results'][0]['reason'] == 'CONSISTENT_EVIDENCE'
        initial = comparison(api, h, old)
        assert not initial['source_changes_observed']
        before = live_snapshot(root); deadline = time.monotonic()+10
        while True:
            x = comparison(api, h, old)
            if x['changes'][0]['newly_expired_source_ids']:
                break
            assert time.monotonic() < deadline
            time.sleep(.15)
        assert x['historical_receipt'] == row['operation']['receipt']
        assert x['changes'][0]['newly_expired_source_ids'] == [fact]
        assert x['current']['results'][0]['reason'] == 'EXPIRED_OR_NOT_YET_VALID'
        assert x['current']['next_step_conditions'][0]['condition'] == 'PROVIDE_CURRENT_SOURCED_EVIDENCE'
        assert x['requires_explicit_reassessment'] and not x['new_assessment_created']
        assert datetime.fromisoformat(x['current']['observed_at']) >= datetime.fromisoformat(data['validity']['valid_until'])
        assert live_snapshot(root) == before
        new = assess(api, h); newer = wait(api, h, new)
        assert newer['operation']['receipt']['results'][0]['reason'] == 'EXPIRED_OR_NOT_YET_VALID'
        assert api.get('/api/runs/'+old, headers=h).json() == row
        (tmp_path/'expiry-proof.json').write_text(json.dumps(x, indent=2))


def test_current_read_revocation_refuses_comparison_and_cold_read(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    root = fresh(tmp_path); h = auth(root)
    with running(root, tmp_path/'before.log') as api:
        assert api.post('/api/facts', headers={**h, 'Idempotency-Key':uuid4().hex}, json=body()).status_code == 201
        run = assess(api, h); wait(api, h, run)
        with sync_playwright() as pw:
            browser = chromium(pw)
            try:
                page = browser.new_page(); page.goto(str(api.base_url)+'/local-facts')
                page.locator('#session').fill(h['Authorization'][7:]); page.locator('#history-run').fill(run)
                page.locator('#compare-read').click()
                expect(page.locator('#comparison-history')).to_contain_text('来源取值一致')
                # Separate original owner fixture action; never exposed by the page.
                owner = Store(live_dsn(root, 'postgres'))
                owner.revoke_field('fixture-a', 'region', 'READ')
                page.locator('#compare-read').click()
                expect(page.locator('#error')).to_contain_text('当前权限拒绝')
                assert page.locator('#comparison').text_content() == ''
                assert api.get('/api/runs/'+run+'/fact-comparison', headers=h).status_code == 403
            finally:
                browser.close()
    before = snapshot(root)
    with running(root, tmp_path/'after.log') as api:
        assert api.get('/api/runs/'+run+'/fact-comparison', headers=h).status_code == 403
        assert api.get('/api/runs/'+run, headers=h).status_code == 403
        assert api.post('/api/runs', headers={**h, 'Idempotency-Key':uuid4().hex},
                        json=dict(goal='SYNTHETIC denied', action='facts.assess',
                                  fact_fields=['region','employees','service_need'])).status_code == 403
    assert snapshot(root) == before
