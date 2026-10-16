"""Actual user fact input/worker/cold read; original field grants only."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

import pgserver
import pytest
from psycopg.conninfo import make_conninfo
from parkweave.store import Store
from scripts.local_case_entry import retained_database
from test_local_case_entry import fresh, running, auth

FIELDS = ['region', 'employees', 'service_need']


def body(value='甲地区', field='region', expired=False):
    now = datetime.now(timezone.utc)
    return dict(schema_version='parkweave-domain/1.0-draft', field=field, value=value,
                unit='people' if field == 'employees' else 'text',
                source_ref=dict(id='SYNTHETIC-' + uuid4().hex, kind='SYNTHETIC', revision='1'),
                source_excerpt='SYNTHETIC excerpt: ' + str(value), purpose='SERVICE_PREPARATION',
                validity=dict(valid_from=(now-timedelta(days=2)).isoformat(),
                              valid_until=(now+timedelta(days=-1 if expired else 2)).isoformat(), timezone='UTC'))


def assess(api, h, goal='SYNTHETIC current three-field consistency', key=None):
    r = api.post('/api/runs', headers={**h, 'Idempotency-Key': key or uuid4().hex},
                 json=dict(goal=goal, action='facts.assess', fact_fields=FIELDS))
    assert r.status_code == 202
    return r.json()['run_id']


def wait(api, h, run):
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        r = api.get('/api/runs/' + run, headers=h)
        if r.status_code == 200 and r.json()['state'] == 'SUCCEEDED':
            return r.json()
        time.sleep(.1)
    pytest.fail('original worker assessment deadline exceeded')


def snapshot(root):
    with retained_database(root) as (_, dsn):
        with Store(dsn).connect() as c:
            c.execute('SET TRANSACTION READ ONLY')
            return {table: c.execute(f'SELECT to_jsonb(t) row FROM {table} t ORDER BY to_jsonb(t)::text').fetchall()
                    for table in ('fact_assertions', 'runs', 'operations', 'principals', 'field_grants',
                                  'capability_grants', 'action_grants', 'run_assignments', 'cases', 'model_steps')}


def chromium(pw):
    return pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])


def fill_source(page, value, source):
    page.locator('#value').fill(value)
    page.locator('#source-id').fill(source)
    page.locator('#source-version').fill('1')
    page.locator('#excerpt').fill('SYNTHETIC <img src=x onerror="window.injected=true"> 原文不是授权')
    now = datetime.now()
    page.locator('#valid-from').fill((now-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'))
    page.locator('#valid-until').fill((now+timedelta(days=1)).strftime('%Y-%m-%dT%H:%M'))
    page.locator('#source-confirm').check()


def test_two_browser_inputs_worker_conditions_and_cold_read(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    root = fresh(tmp_path); h = auth(root); saved = []
    with running(root, tmp_path/'first.log') as api:
        port = api.base_url.port
        with sync_playwright() as pw:
            browser = chromium(pw)
            try:
                page = browser.new_page(); writes = []
                page.on('request', lambda r: writes.append(r.url) if r.method == 'POST' else None)
                page.goto(str(api.base_url)+'/local-entry')
                page.locator('a[href="/local-facts"]').click()
                page.locator('#session').fill(h['Authorization'][7:])
                for number, value in enumerate(('甲地区', '乙地区'), 1):
                    fill_source(page, value, f'SYNTHETIC-source-{number}')
                    with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/api/facts')) as response:
                        page.locator('#source-save').click()
                    assert response.value.status == 201
                    page.locator('#release').click()
                    page.locator('#goal').fill(f'SYNTHETIC input {number}')
                    page.locator('#assess-confirm').check()
                    with page.expect_response(lambda r: r.request.method == 'POST' and r.url.endswith('/api/runs')) as response:
                        page.locator('#assess-save').click()
                    run = response.value.json()['run_id']
                    row = wait(api, h, run); saved.append(row)
                    page.locator('#result-read').click()
                    expect(page.locator('#result')).to_contain_text('下一步条件')
                    assert page.evaluate('window.injected') is None
                    page.locator('#release').click()
                assert len(writes) == 4
                page.screenshot(path=str(tmp_path/'two-inputs.png'), full_page=True)
            finally:
                browser.close()
        first = saved[0]['operation']['receipt']; second = saved[1]['operation']['receipt']
        assert first['results'][0]['reason'] == 'CONSISTENT_EVIDENCE'
        assert second['results'][0]['reason'] == 'CONFLICTING_EVIDENCE'
        assert len(first['results'][0]['evidence']) == 1 and len(second['results'][0]['evidence']) == 2
        assert second['next_step_conditions'][0]['condition'] == 'RESOLVE_CONFLICT_WITH_SOURCED_EVIDENCE'
        assert second['next_step_conditions'][1]['condition'] == 'PROVIDE_SOURCED_EVIDENCE'
        assert first['verification'] == second['verification'] == 'UNVERIFIED'
        assert first['qualification_decision'] == second['qualification_decision'] == 'NOT_EVALUATED'
        for row in saved:
            assert row['case'] is None
            assert api.get('/api/runs/'+row['run_id'], headers=h).json() == row
            for actor in ('fixture-b', 'fixture-c'):
                assert api.get('/api/runs/'+row['run_id'], headers=auth(root, actor)).status_code == 403
    before = snapshot(root)
    assert before['cases'] == before['run_assignments'] == before['model_steps'] == []
    with running(root, tmp_path/'second.log', port=port) as api:
        with sync_playwright() as pw:
            browser = chromium(pw)
            try:
                page = browser.new_page(); posts = []
                page.on('request', lambda r: posts.append(r.url) if r.method == 'POST' else None)
                page.goto(str(api.base_url)+'/local-facts')
                page.locator('#session').fill(h['Authorization'][7:])
                for row in saved:
                    page.locator('#run').fill(row['run_id'])
                    with page.expect_response(lambda r: r.url.endswith('/api/runs/'+row['run_id'])) as response:
                        page.locator('#result-read').click()
                    assert response.value.json() == row
                    expect(page.locator('#result')).to_contain_text('下一步条件')
                assert posts == []
            finally:
                browser.close()
    assert snapshot(root) == before
    (tmp_path/'user-path.json').write_text(json.dumps(dict(runs=[r['run_id'] for r in saved],
        original_page_posts=4, cold_page_posts=0, same_port_restart=True,
        first_reason=first['results'][0]['reason'], second_reason=second['results'][0]['reason'],
        qualification_decision='NOT_EVALUATED', snapshot_unchanged=True), indent=2))


def test_expired_zero_and_original_key_conflicts_and_scoped_recovery(tmp_path):
    root = fresh(tmp_path); h = auth(root)
    with running(root, tmp_path/'api.log') as api:
        facts = []
        for value, field, expired in ((0, 'employees', False), ('旧诉求', 'service_need', True)):
            data = body(value, field, expired); key = uuid4().hex
            hdr = {**h, 'Idempotency-Key': key}
            r = api.post('/api/facts', headers=hdr, json=data); assert r.status_code == 201
            assert api.post('/api/facts', headers=hdr, json=data).json() == r.json()
            assert api.post('/api/facts', headers=hdr, json=data|{'source_excerpt':'changed'}).status_code == 409
            recovered = api.get('/api/local-facts/requests/'+key, params={'kind':'FACT','field':field}, headers=h)
            assert recovered.json()['record_id'] == r.json()['fact_id']
            for who in ('fixture-b','fixture-c'):
                assert api.get('/api/facts/'+r.json()['fact_id'], headers=auth(root, who)).status_code == 403
                assert api.get('/api/local-facts/requests/'+key, params={'kind':'FACT','field':field}, headers=auth(root, who)).json()['status'] == 'NOT_FOUND'
            facts.append(r.json()['fact_id'])
        key = uuid4().hex; run = assess(api,h,key=key); row = wait(api,h,run)
        receipt = row['operation']['receipt']
        assert [r['reason'] for r in receipt['results']] == ['MISSING_EVIDENCE','CONSISTENT_EVIDENCE','EXPIRED_OR_NOT_YET_VALID']
        assert receipt['results'][1]['evidence'][0]['value'] == 0
        assert receipt['next_step_conditions'][1]['condition'] == 'AUTHORITATIVE_VERIFICATION_REQUIRED'
        assert receipt['next_step_conditions'][2]['condition'] == 'PROVIDE_CURRENT_SOURCED_EVIDENCE'
        assert api.get('/api/local-facts/requests/'+key, params={'kind':'ASSESSMENT'}, headers=h).json()['record_id'] == run
        assert api.post('/api/runs', headers={**h,'Idempotency-Key':key}, json=dict(goal='different',action='facts.assess',fact_fields=FIELDS)).status_code == 409
        assert api.get('/api/local-facts/requests/'+uuid4().hex, params={'kind':'ASSESSMENT'}, headers=h).json()['status'] == 'NOT_FOUND'


@pytest.mark.parametrize('revoke', ['READ','WRITE','EXECUTE','IDENTITY'])
def test_revocation_stays_revoked_across_restart(tmp_path, revoke):
    root = fresh(tmp_path);h=auth(root);data=body();key=uuid4().hex
    with running(root,tmp_path/'before.log') as api:
        fact = api.post('/api/facts',headers={**h,'Idempotency-Key':key},json=data).json()['fact_id']
        run=assess(api,h);wait(api,h,run)
    with retained_database(root):
        # Explicit original owner revocation is a negative-test precondition only.
        owner=Store(make_conninfo(pgserver.get_server(root/'data',cleanup_mode='stop').get_uri(),dbname='parkweave'))
        if revoke in ('READ','WRITE'):owner.revoke_field('fixture-a','region',revoke)
        elif revoke=='EXECUTE':owner.revoke_capability('fixture-a','EXECUTE')
        else:owner.revoke('fixture-a')
    before=snapshot(root)
    with running(root,tmp_path/'after.log') as api:
        expected_read=403 if revoke in ('READ','IDENTITY') else 200
        assert api.get('/api/facts/'+fact,headers=h).status_code==expected_read
        assert api.get('/api/runs/'+run,headers=h).status_code==expected_read
        assert api.get('/api/local-facts/requests/'+key,params={'kind':'FACT','field':'region'},headers=h).status_code==expected_read
        expected_write=201 if revoke=='READ' else 403
        assert api.post('/api/facts',headers={**h,'Idempotency-Key':uuid4().hex},json=body()).status_code==expected_write
        expected_assess=202 if revoke=='WRITE' else 403
        assert api.post('/api/runs',headers={**h,'Idempotency-Key':uuid4().hex},json=dict(goal='SYNTHETIC after revoke',action='facts.assess',fact_fields=FIELDS)).status_code==expected_assess
    after=snapshot(root)
    for table in ('principals','field_grants','capability_grants','action_grants','run_assignments'):
        assert after[table]==before[table]


def test_browser_lost_replies_exact_key_get_and_delayed_cross_identity(tmp_path):
    from playwright.sync_api import sync_playwright, expect
    root=fresh(tmp_path);h=auth(root)
    with running(root,tmp_path/'lost.log') as api:
        with sync_playwright() as pw:
            browser=chromium(pw)
            try:
                page=browser.new_page();posts=[]
                def drop(route):
                    posts.append(route.request.url);route.fetch();route.abort('failed')
                page.route('**/api/facts',drop)
                page.goto(str(api.base_url)+'/local-facts');page.locator('#session').fill(h['Authorization'][7:])
                fill_source(page,'甲地区','SYNTHETIC-lost-fact');page.locator('#source-save').click()
                expect(page.locator('#error')).not_to_be_empty()
                assert page.locator('#source-save').is_disabled()
                old_handle=page.evaluate("sessionStorage.getItem('parkweave-local-facts-pending-v1')");page.reload()
                assert page.locator('#source-save').is_disabled() and page.locator('#assess-save').is_disabled()
                assert page.evaluate("sessionStorage.getItem('parkweave-local-facts-pending-v1')")==old_handle
                page.locator('#session').fill(h['Authorization'][7:])
                def wrong_fingerprint(route):
                    original=route.fetch();value=original.json();value['fingerprint']='0'*64
                    route.fulfill(response=original,json=value)
                page.route('**/api/local-facts/requests/**',wrong_fingerprint)
                page.locator('#recover').click()
                expect(page.locator('#error')).to_contain_text('指纹不一致')
                assert page.locator('#release').is_hidden() and page.locator('#source-save').is_disabled()
                assert len(posts)==1
                page.unroute('**/api/local-facts/requests/**',wrong_fingerprint)
                page.locator('#recover').click()
                expect(page.locator('#source-status')).to_contain_text('只GET确认')
                assert page.locator('#error').text_content()==''
                page.locator('#release').click();page.route('**/api/runs',drop)
                page.locator('#goal').fill('SYNTHETIC lost assessment');page.locator('#assess-confirm').check();page.locator('#assess-save').click()
                expect(page.locator('#error')).not_to_be_empty()
                page.locator('#recover').click()
                expect(page.locator('#run')).to_have_value(__import__('re').compile(r'^[a-f0-9-]{36}$'))
                run=page.locator('#run').input_value();row=wait(api,h,run)
                assert len(posts)==2
                held=[];page.route('**/api/runs/'+run,lambda route:held.append(route))
                page.locator('#result-read').click();page.wait_for_timeout(100)
                assert len(held)==1
                page.locator('#session').fill(auth(root,'fixture-b')['Authorization'][7:])
                assert page.locator('#assess-save').is_disabled()
                page.locator('#session').fill(h['Authorization'][7:])
                held[0].fulfill(status=200,json=row)
                page.wait_for_timeout(100)
                assert page.locator('#result').text_content()==''
                assert page.locator('#assess-save').is_disabled()
                page.unroute('**/api/runs/'+run)
                page.locator('#recover').click()
                expect(page.locator('#result')).to_contain_text('下一步条件')
                held=[];page.route('**/api/runs/'+run,lambda route:held.append(route))
                page.locator('#result-read').click();page.wait_for_timeout(100)
                page.locator('#run').fill(str(uuid4()));page.locator('#run').fill(run)
                page.locator('#result-read').click();page.wait_for_timeout(100)
                assert len(held)==2
                held[1].fulfill(status=200,json=row)
                expect(page.locator('#result')).to_contain_text('下一步条件')
                stale=json.loads(json.dumps(row));stale['operation']['receipt']['assessment_goal']='STALE_EARLIER_A'
                held[0].fulfill(status=200,json=stale);page.wait_for_timeout(100)
                assert 'STALE_EARLIER_A' not in page.locator('#result').text_content()
                assert len(posts)==2
            finally:browser.close()
