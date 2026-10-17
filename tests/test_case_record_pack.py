"""Portable current-owner records via ordinary API process and real Chromium.

Only isolated synthetic fixtures supply identities and business records. Export
uses existing GET authority; no provider, approval or real model is installed.
"""
import hashlib
import json
from pathlib import Path
import time

import pytest
from playwright.sync_api import sync_playwright, expect

from test_case_goal_results import (link_fixture, receipt_fixture, preparation_fixture,
                                   complete, start, get, snapshot, GOALS, verified)
from test_native_preparation_entry_browser import ordinary_process
from test_material_file_import_browser import open_record
from test_native_preparation_entry import snapshot as entry_snapshot
from test_preparation import headers, command as prep_act
from test_request_intents import save
from test_service_case_steps import setup, adopt, adopt_body
from test_service_dispatches import REVIEWER
from test_executor_receipts import ready


def business(f):
    return snapshot(f), entry_snapshot(f[1])


@pytest.fixture
def record_page(link_fixture, tmp_path):
    f = link_fixture
    with ordinary_process(f, tmp_path/'ordinary') as api, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        context = browser.new_context(accept_downloads=True)
        page = context.new_page(); errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            yield f, api, page, tmp_path
            assert not errors, errors
        finally:
            context.close(); browser.close()


def open_results(page, api, f, p):
    open_record(page, api, f, p)
    page.locator('#service-plan-prepare').click()
    expect(page.locator('#goal-results-panel')).to_be_visible()
    page.locator('#goal-results-read').click()
    page.wait_for_function('()=>goalResultView!==null&&!document.querySelector("#goal-results-read").disabled')


def generate(page):
    page.locator('#case-record-pack-generate').click()
    page.wait_for_function('()=>!caseRecordPackBusy')
    expect(page.locator('#case-record-pack-output')).to_be_visible()
    return page.locator('#case-record-pack-text').input_value()


def data_from_text(text):
    marker = '核对数据（UTF-8 JSON，原文按JSON转义；不包含读取凭据）：\n'
    prefix, raw = text.split(marker)
    data = json.loads(raw)
    sha = hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True,
                                   separators=(',', ':')).encode()).hexdigest()
    assert '核对数据 SHA256：'+sha+'\n' in prefix
    return data


def wait_held(page, held):
    end = time.monotonic()+10
    while not held and time.monotonic()<end:
        page.wait_for_timeout(20)
    assert held


def test_actual_original_entry_all_outputs_download_and_restart(link_fixture, tmp_path):
    f = link_fixture; p, _, _, receipt = complete(f, local=True)
    texts = []; process_ids = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        try:
            for run in range(2):
                with ordinary_process(f, tmp_path/str(run)) as api:
                    process_ids.append(api.get('/health').json()['process_id'])
                    context = browser.new_context(accept_downloads=True)
                    page = context.new_page(); errors = []
                    page.on('pageerror', lambda e: errors.append(str(e)))
                    open_results(page, api, f, p)
                    before = business(f); requests = []
                    page.on('request', lambda r: requests.append((r.method, r.url)))
                    text = generate(page); data = data_from_text(text)
                    assert data['current_required_goals'] == GOALS
                    assert len(data['results']) == 5 and data['state'] == 'LOCAL_OUTPUTS_VERIFIED'
                    assert data['results'][3]['actual_output']['receipt_id'] == receipt['current_receipt']['id']
                    assert all(r['historical_verification']['current'] for r in data['results'])
                    assert data['historical_adoption_source']['historical_adoption_only']
                    assert 'PRIVATE_GOAL_RECEIPT' not in text and 'source_snapshot' not in text
                    for forbidden in ('capability_grants', 'owner_grants', 'resource_grants', 'Bearer ', f[2]['fixture-a']):
                        assert forbidden not in text
                    assert not data['case_goal_completed'] and data['external_acceptance'] == 'NOT_SUBMITTED'
                    assert '不证明实际履约' in text and data['offline_fulfillment'] == 'NO_EVIDENCE'
                    with page.expect_download() as download:
                        page.locator('#case-record-pack-download').click()
                    target = tmp_path/('actual-'+str(run)+'.txt')
                    download.value.save_as(target)
                    assert target.read_bytes() == text.encode()
                    assert download.value.suggested_filename.startswith('ParkWeave-case-record-'+p['case_id'])
                    assert len(requests) == 4 and all(method == 'GET' and url.endswith('/goal-results') for method, url in requests)
                    assert business(f) == before and page.evaluate('JSON.stringify({...localStorage})') == '{}'
                    for width in (1200, 390, 320):
                        page.set_viewport_size({'width': width, 'height': 900})
                        page.locator('#case-record-pack').scroll_into_view_if_needed()
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                        if run == 0: page.screenshot(path=str(tmp_path/('record-'+str(width)+'.png')))
                    assert not errors; texts.append(text); context.close()
        finally:
            browser.close()
    assert process_ids[0] != process_ids[1] and texts[0] == texts[1]
    (tmp_path/'proof.json').write_text(json.dumps(dict(distinct_processes=process_ids, exact_download_bytes=True,
        all_current_goals=GOALS, export_requests_get_only=True, business_and_permissions_unchanged=True), indent=2)+'\n')


def test_partial_all_eight_goals_and_literal_text_are_preserved(record_page):
    f, api, page, _ = record_page; p = setup(f)
    goals = GOALS + ['SYNTHETIC 外部受理', '<img src=x onerror="window.PACK_XSS=1">', 'SYNTHETIC 未知\r\n目标 😀']
    p = save(f, p, goals=goals, text='SYNTHETIC 本次原文\r\n第二行 <script>window.PACK_XSS=1</script>').json()
    p = prep_act(f, p, 'REVIEW', REVIEWER, reason='SYNTHETIC review').json()
    p = prep_act(f, p, 'CONFIRM', reason='SYNTHETIC confirmation').json()
    r = adopt(f, p, adopt_body(f, p, partial_adoption=True)); assert r.status_code == 201, r.text
    open_results(page, api, f, p); before = business(f)
    text = generate(page); data = data_from_text(text)
    assert data['state'] == 'PARTIAL' and data['current_required_goals'] == goals
    assert [row['goal'] for row in data['results']] == goals and len(data['results']) == 8
    assert all(row['state'] == 'UNSUPPORTED' and row['human_request_state'] == 'NOT_REQUESTED' for row in data['results'][-3:])
    assert data['current_request'].startswith('SYNTHETIC 本次原文\r\n')
    assert not page.evaluate('window.PACK_XSS||false') and page.locator('#case-record-pack img,#case-record-pack script').count() == 0
    with page.expect_download() as download: page.locator('#case-record-pack-download').click()
    assert Path(download.value.path()).read_bytes() == text.encode() and business(f) == before


def test_current_extra_goal_keeps_old_adoption_and_historical_verification(record_page):
    f, api, page, _ = record_page; p = start(f); verified(f, p, 'P1')
    p = save(f, p, goals=[GOALS[0], 'SYNTHETIC 当前新增且未支持目标']).json()
    open_results(page, api, f, p); before = business(f); data = data_from_text(generate(page))
    assert data['current_required_goals'] == [GOALS[0], 'SYNTHETIC 当前新增且未支持目标']
    assert data['adopted_goals'] == [GOALS[0]] and data['historical_adoption_source']['required_goals'] == [GOALS[0]]
    assert [r['state'] for r in data['results']] == ['NEEDS_NEW_PLAN', 'UNSUPPORTED']
    assert data['results'][0]['historical_verification']['current'] is False
    assert data['results'][0]['actual_output'] is None and business(f) == before


@pytest.mark.parametrize('empty', [False, True])
def test_unadopted_and_empty_goals_remain_explicit_unknown(record_page, empty):
    f, api, page, _ = record_page; p = ready(f) if empty else setup(f, GOALS[0])
    open_results(page, api, f, p); before = business(f); data = data_from_text(generate(page))
    assert data['historical_adoption_source'] is None and data['plan_id'] is None
    assert data['current_required_goals'] == ([] if empty else [GOALS[0]])
    assert data['state'] == ('UNKNOWN' if empty else 'UNVERIFIED')
    if not empty: assert data['results'][0]['state'] == 'NOT_ADOPTED'
    assert business(f) == before


def test_unadopted_unsupported_goal_does_not_invent_human_request(record_page):
    f, api, page, _ = record_page; p = ready(f)
    p = save(f, p, goals=['SYNTHETIC 尚未采用的不支持目标']).json()
    open_results(page, api, f, p); before = business(f); text = generate(page); data = data_from_text(text)
    assert data['results'][0]['state'] == 'UNSUPPORTED'
    assert 'human_request_state' not in data['results'][0] and '不臆造人工请求' in text
    assert data['current_required_goals'] == ['SYNTHETIC 尚未采用的不支持目标'] and business(f) == before


def test_replaced_plan_keeps_old_plan_references_separate(record_page):
    f, api, page, _ = record_page; p = start(f); old = verified(f, p, 'P1')
    p = save(f, p, goals=[GOALS[0], 'SYNTHETIC 需另行人工的目标']).json()
    p = prep_act(f, p, 'REVIEW', REVIEWER, reason='SYNTHETIC current review').json()
    p = prep_act(f, p, 'CONFIRM', reason='SYNTHETIC current confirmation').json()
    body = adopt_body(f, p, partial_adoption=True); body['expected_plan_revision'] = old['revision']
    r = adopt(f, p, body); assert r.status_code == 201, r.text
    open_results(page, api, f, p); before = business(f); data = data_from_text(generate(page))
    assert data['state'] == 'PARTIAL' and data['plan_id'] != old['plan_id']
    assert data['historical_plans'] == [dict(id=old['plan_id'], revision=old['revision'], goals=[GOALS[0]])]
    assert data['current_required_goals'] == [GOALS[0], 'SYNTHETIC 需另行人工的目标'] and business(f) == before


def test_original_offline_candidate_source_is_exported_as_historical_reference(record_page):
    from test_bounded_planning import setup as candidate_setup
    from test_service_plan_candidates import generate as candidate_generate, adopt as candidate_adopt
    f, api, page, _ = record_page; p = candidate_setup(f, [GOALS[4], 'SYNTHETIC 保留的人工目标'])
    r = candidate_generate(f, p); assert r.status_code == 201, r.text; candidate = r.json()
    r = candidate_adopt(f, p, candidate); assert r.status_code == 201, r.text
    open_results(page, api, f, p); before = business(f); data = data_from_text(generate(page))
    trace = data['historical_adoption_source']
    assert trace['historical_adoption_only'] and trace['origin'] == 'SYNTHETIC_UNTRUSTED_CANDIDATE'
    assert trace['candidate']['candidate_id'] == candidate['candidate_id']
    assert trace['candidate']['verification_sha256'] == candidate['verification_sha256']
    assert data['state'] == 'PARTIAL' and data['current_required_goals'] == [GOALS[4], 'SYNTHETIC 保留的人工目标']
    assert 'producer' not in json.dumps(data) and business(f) == before


@pytest.mark.parametrize('failure', ['unavailable', 'invalid-json'])
def test_actual_read_transport_failure_clears_candidate_without_download(record_page, failure):
    f, api, page, _ = record_page; p = start(f); open_results(page, api, f, p); generate(page)
    downloads = []; page.on('download', lambda d: downloads.append(d))
    def fail(route):
        if failure == 'unavailable': route.fulfill(status=503, json={'detail': 'SYNTHETIC unavailable'})
        else: route.fulfill(status=200, body='SYNTHETIC invalid JSON', content_type='application/json')
    page.route('**/api/preparations/'+p['preparation_id']+'/goal-results', fail)
    before = business(f); page.locator('#case-record-pack-download').click(); page.wait_for_function('()=>!caseRecordPackBusy')
    assert not downloads and page.evaluate('caseRecordPackView') is None
    expect(page.locator('#case-record-pack-output')).to_be_hidden()
    assert page.locator('#case-record-pack-text').input_value() == '' and business(f) == before


def test_same_revision_source_change_refuses_old_download_then_new_read_keeps_history(record_page):
    f, api, page, _ = record_page; p = start(f); verified(f, p, 'P1'); open_results(page, api, f, p)
    old = data_from_text(generate(page)); downloads = []; page.on('download', lambda d: downloads.append(d))
    with f[1].connect() as c:
        c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
    before = business(f); page.locator('#case-record-pack-download').click(); page.wait_for_function('()=>!caseRecordPackBusy')
    assert not downloads; expect(page.locator('#case-record-pack-output')).to_be_hidden()
    expect(page.locator('#case-record-pack-status')).to_contain_text('已变化')
    assert page.locator('#case-record-pack-text').input_value() == '' and business(f) == before
    page.locator('#goal-results-read').click(); page.wait_for_function('()=>goalResultView!==null&&!document.querySelector("#goal-results-read").disabled')
    new = data_from_text(generate(page))
    assert new['plan_revision'] == old['plan_revision'] and new['preparation_revision'] == old['preparation_revision']
    assert new['results'][0]['state'] == 'NEEDS_RECHECK' and new['results'][0]['actual_output'] is None
    assert new['results'][0]['historical_verification']['id'] == old['results'][0]['historical_verification']['id']
    assert new['results'][0]['historical_verification']['current'] is False and business(f) == before


def test_source_change_between_actual_two_gets_does_not_publish(record_page):
    f, api, page, _ = record_page; p = start(f); verified(f, p, 'P1'); open_results(page, api, f, p); seen = []
    def change_after_first_read(route):
        response = route.fetch(); seen.append(response.status)
        if len(seen) == 1:
            with f[1].connect() as c: c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
        route.fulfill(response=response)
    page.route('**/api/preparations/'+p['preparation_id']+'/goal-results', change_after_first_read)
    page.locator('#case-record-pack-generate').click(); page.wait_for_function('()=>!caseRecordPackBusy')
    assert seen == [200, 200]; expect(page.locator('#case-record-pack-output')).to_be_hidden()
    expect(page.locator('#case-record-pack-status')).to_contain_text('已变化')
    assert page.locator('#case-record-pack-text').input_value() == ''


@pytest.mark.parametrize('authority', ['READ', 'PREPARE'])
def test_actual_current_revoke_before_download_clears_private_memory(record_page, authority):
    f, api, page, _ = record_page; p = start(f); open_results(page, api, f, p); generate(page)
    with f[1].connect() as c:
        table = 'capability_grants' if authority == 'READ' else 'preparation_grants'
        c.execute('UPDATE '+table+' SET active=false WHERE principal_id=%s AND capability=%s', ('fixture-a', authority))
    before = business(f); seen = []; downloads = []
    page.on('response', lambda r: seen.append(r.status) if r.url.endswith('/goal-results') else None)
    page.on('download', lambda d: downloads.append(d)); page.locator('#case-record-pack-download').click()
    page.wait_for_function('()=>goalResultView===null&&servicePlanView===null')
    assert seen == [403] and not downloads and business(f) == before
    assert page.evaluate('caseRecordPackView') is None and page.locator('#case-record-pack-text').input_value() == ''
    expect(page.locator('#page-feedback')).to_contain_text('读取权已失效')


@pytest.mark.parametrize('user', ['fixture-b', 'fixture-c', REVIEWER, 'executor-a'])
def test_ordinary_api_does_not_expand_export_owner_scope(record_page, user):
    f, api, page, _ = record_page; p = start(f); before = business(f)
    r = api.get('/api/preparations/'+p['preparation_id']+'/goal-results', headers=headers(f[2], user))
    assert r.status_code == 403 and p['case_id'] not in r.text and business(f) == before
    expect(page.locator('#case-record-pack-output')).to_be_hidden()


@pytest.mark.parametrize('damage', ['missing-goal', 'row-sha', 'trace-sha', 'actor', 'revision'])
def test_incomplete_or_mismatched_actual_response_cannot_be_exported(record_page, damage):
    f, api, page, _ = record_page; p = start(f); open_results(page, api, f, p)
    def corrupt(route):
        response = route.fetch(); x = response.json()
        if damage == 'missing-goal': x['results'] = []
        elif damage == 'row-sha': x['results'][0]['result_sha256'] = '0'*64
        elif damage == 'trace-sha': x['source_trace']['trace_sha256'] = '0'*64
        elif damage == 'actor': x['actor_id'] = 'fixture-b'
        else: x['preparation_revision'] += 1
        route.fulfill(status=200, json=x)
    page.route('**/api/preparations/'+p['preparation_id']+'/goal-results', corrupt)
    before = business(f); page.locator('#case-record-pack-generate').click(); page.wait_for_function('()=>!caseRecordPackBusy')
    expect(page.locator('#case-record-pack-output')).to_be_hidden(); expect(page.locator('#case-record-pack-status')).not_to_be_empty()
    assert page.evaluate('caseRecordPackView') is None and page.locator('#case-record-pack-text').input_value() == '' and business(f) == before


@pytest.mark.parametrize('target', ['identity-aba', 'case', 'draft'])
@pytest.mark.parametrize('denied', [False, True])
def test_late_download_read_cannot_overwrite_new_context(record_page, target, denied):
    f, api, page, _ = record_page; p = start(f); other = start(f) if target == 'case' else None
    open_results(page, api, f, p); generate(page); held = []; downloads = []
    page.on('download', lambda d: downloads.append(d))
    page.route('**/api/preparations/'+p['preparation_id']+'/goal-results', lambda r: held.append((r, r.fetch())))
    page.locator('#case-record-pack-download').click(); wait_held(page, held)
    if target == 'identity-aba':
        page.locator('#token').fill(f[2]['fixture-b']); page.locator('#token').fill(f[2]['fixture-a'])
    elif target == 'case':
        # Switch using original in-page entry so the held old HTTP response can
        # actually be delivered; a full page navigation cancels that request.
        page.locator('#existing-preparation-id').fill(other['preparation_id'])
        page.locator('#existing-preparation-read').click()
        expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')
        page.locator('#service-plan-prepare').click(); expect(page.locator('#goal-results-panel')).to_be_visible()
        page.locator('#goal-results-read').click(); page.wait_for_function('()=>goalResultView!==null&&!document.querySelector("#goal-results-read").disabled')
    else: page.locator('#service-plan-reason').fill('SYNTHETIC newer user draft')
    page.locator('#case-record-pack-status').evaluate('(e)=>{e.textContent="SYNTHETIC NEW CONTEXT"}')
    before = business(f); route, response = held[0]
    if denied: route.fulfill(status=403, json={'detail': 'SYNTHETIC prior context denial'})
    else: route.fulfill(response=response)
    page.wait_for_timeout(100)
    assert not downloads and page.locator('#case-record-pack-status').inner_text() == 'SYNTHETIC NEW CONTEXT'
    assert page.evaluate('caseRecordPackView') is None and page.locator('#case-record-pack-text').input_value() == '' and business(f) == before
    if target == 'case': assert page.evaluate('goalResultView.preparation_id') == other['preparation_id']
    if target == 'draft': assert page.locator('#service-plan-reason').input_value() == 'SYNTHETIC newer user draft'


@pytest.mark.parametrize('denied', [False, True])
def test_inflight_export_with_original_committed_lost_write_preserves_handle(record_page, denied):
    f, api, page, _ = record_page; p = start(f); verified(f, p, 'P1'); open_results(page, api, f, p)
    page.locator('[data-service-open="materials"]').click()
    page.wait_for_function('()=>preparationView!==null&&objectionView!==null')
    generate(page); held = []
    page.route('**/api/preparations/'+p['preparation_id']+'/goal-results', lambda r: held.append((r, None if denied else r.fetch())))
    page.locator('#case-record-pack-download').click(); wait_held(page, held)
    def lose(route):
        response = route.fetch(); assert response.status == 200; route.abort('failed')
    page.route('**/api/preparations/'+p['preparation_id']+'/commands', lose)
    page.locator('#prep-slot').select_option('material_outline')
    page.locator('#prep-text').fill('SYNTHETIC PRIVATE_RECORD_PACK_INFLIGHT')
    page.locator('#prep-source-label').fill('SYNTHETIC changed source')
    page.locator('#prep-evidence button').click(); page.wait_for_function('()=>prepCommandPending?.state==="UNKNOWN"')
    stored = page.evaluate('JSON.stringify({...localStorage})'); assert stored != '{}' and 'PRIVATE_RECORD_PACK' not in stored
    if denied:
        with f[1].connect() as c: c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
    before = business(f); route, response = held[0]
    if denied: response = route.fetch(); assert response.status == 403
    route.fulfill(response=response); page.wait_for_timeout(150)
    assert page.evaluate('caseRecordPackView') is None and page.locator('#case-record-pack-text').input_value() == ''
    assert page.evaluate('JSON.stringify({...localStorage})') == stored and business(f) == before
    if denied:
        assert page.evaluate('goalResultView===null&&servicePlanView===null&&preparationView===null')
        expect(page.locator('#page-feedback')).to_contain_text('读取权已失效')
    else:
        assert page.evaluate('prepCommandPending?.state==="UNKNOWN"')
        assert page.locator('#prep-text').input_value() == 'SYNTHETIC PRIVATE_RECORD_PACK_INFLIGHT'
        expect(page.locator('#case-record-pack-status')).to_contain_text('原操作结果待只读核对')
