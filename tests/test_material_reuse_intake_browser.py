"""Two fresh ordinary-page Cases, explicit material reuse and independent review.

Only installation identities/catalog/Grants are SYNTHETIC fixtures. No business
setup APIs, assignment, isolated approval or browser JS business writes are used.
"""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

from test_local_synthetic_demo import demo_inputs, preparation_fixture, receipt_fixture
from test_local_synthetic_demo_browser import ordinary_demo
from test_demo_original_page_intake_browser import ordinary_worker, login, settled, open_from_list
from service_release_acceptance_support import authority_snapshot, case_history, stable_hash


def create_from_page(page, pack, goal):
    page.locator('[data-tab="service"]').click()
    page.locator('#prep-catalog').click()
    expect(page.locator('#prep-create')).to_be_visible()
    page.locator('#prep-reviewer').select_option(pack['roles']['park_specialist'])
    page.locator('#prep-goal').fill(goal)
    page.locator('#prep-create button').click()
    expect(page.locator('#prep-summary')).to_contain_text(goal, timeout=20000)
    settled(page, preparation=True)
    return page.evaluate('preparationId')  # Observation only.


def own_request(page, goal):
    page.locator('#plan-prepare').click()
    expect(page.locator('#request-intent-form')).to_be_visible()
    page.locator('#request-current').fill(goal)
    page.locator('#request-local-goal').uncheck()
    page.locator('#plan-required-goals').fill('LOCAL_MATERIAL_PREPARATION')
    page.locator('#request-save').click()
    expect(page.locator('#request-intent-status')).to_contain_text('已保存诉求/目标版本', timeout=15000)
    settled(page)
    page.locator('#plan-materials').click()
    settled(page, preparation=True)


def add_material(page, slot, text):
    page.locator('#prep-slot').select_option(slot)
    page.locator('#prep-text').fill(text)
    page.locator('#prep-source-kind').select_option('DOCUMENT_EXCERPT')
    page.locator('#prep-source-label').fill('SYNTHETIC own source ' + slot)
    page.locator('#prep-evidence button').click()
    expect(page.locator('#prep-materials')).to_contain_text(text, timeout=15000)
    expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件', timeout=15000)
    settled(page, preparation=True)


def review_and_confirm(owner, reviewer, goal):
    open_from_list(reviewer, goal)
    reviewer.locator('#prep-reason').fill('SYNTHETIC independent specialist review: ' + goal)
    reviewer.locator('#prep-review').click()
    expect(reviewer.locator('#prep-summary')).to_contain_text('待企业确认', timeout=15000)
    settled(reviewer, preparation=True)
    owner.locator('#prep-refresh').click()
    expect(owner.locator('#prep-summary')).to_contain_text('待企业确认', timeout=15000)
    settled(owner, preparation=True)
    expect(owner.locator('#prep-confirm')).to_be_enabled()
    owner.locator('#prep-reason').fill('SYNTHETIC independent owner confirmation: ' + goal)
    owner.locator('#prep-confirm').click()
    expect(owner.locator('#prep-summary')).to_contain_text('本地资料准备已确认', timeout=15000)
    settled(owner, preparation=True)
    expect(owner.locator('#prep-confirm')).to_be_disabled()


def download_pack(page, destination):
    page.locator('#material-pack-generate').click()
    expect(page.locator('#material-pack-status')).to_contain_text('已生成当前读取快照', timeout=15000)
    text = page.locator('#material-pack-text').input_value()
    with page.expect_download() as event:
        page.locator('#material-pack-download').click()
    download = event.value
    actual = Path(download.path()).read_bytes()
    assert actual == text.encode() and 'Case目标未完成' in text
    destination.write_bytes(actual)
    return dict(filename=download.suggested_filename, sha256=hashlib.sha256(actual).hexdigest(), text=text)


def materials(owner, pid):
    with owner.connect() as connection:
        return connection.execute('SELECT * FROM preparation_evidence WHERE preparation_id=%s ORDER BY slot,version', (pid,)).fetchall()


def observed_review_sha(parent, rows):
    latest = {row['slot']: row for row in rows}  # Input rows ordered by slot/version.
    fields = ('id', 'slot', 'version', 'text', 'source_kind', 'source_label', 'source_sha256', 'authenticity')
    return stable_hash(dict(preparation_id=str(parent['id']), service_id=parent['service_id'],
        service_version=parent['service_version'], materials=[{field: latest[slot][field] for field in fields} for slot in sorted(latest)]))


@pytest.mark.parametrize('width', [1200, 320])
def test_two_new_ordinary_cases_reuse_outline_independently_review_download_and_cold_read(demo_inputs, tmp_path, width):
    f, cfg, pack, journal = demo_inputs
    authority = authority_snapshot(f[1])
    with f[1].connect() as connection:
        assert all(connection.execute('SELECT count(*) n FROM ' + table).fetchone()['n'] == 0
                   for table in ('runs', 'cases', 'preparations', 'preparation_evidence', 'preparation_events', 'run_assignments'))
    source_goal = 'SYNTHETIC original archive request ' + str(width)
    target_goal = 'SYNTHETIC independent second request ' + str(width)
    source_need = 'SYNTHETIC source-only request summary ' + str(width)
    target_need = 'SYNTHETIC new target-only request summary ' + str(width)
    outline_v1 = 'SYNTHETIC reusable outline v1 中文 ' + str(width) + ' <script>window.reuseInjected=true</script>'
    outline_v2 = 'SYNTHETIC later source-only outline v2 ' + str(width)
    traffic, requests, errors, contexts = [], [], [], []
    with ordinary_demo(f, tmp_path / 'first') as api, ordinary_worker(f, tmp_path / 'worker') as worker, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        def role(actor):
            context = browser.new_context(viewport=dict(width=width, height=1000), accept_downloads=True)
            contexts.append(context)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(dict(actor=actor, method=request.method, path=urlsplit(request.url).path)))
            def response_received(response):
                request = response.request
                if request.method == 'POST':
                    traffic.append(dict(actor=actor, path=urlsplit(request.url).path, status=response.status, body=request.post_data_json))
            page.on('response', response_received)
            login(page, api, f, actor)
            return page
        try:
            owner = role('fixture-a')
            source_id = create_from_page(owner, pack, source_goal)
            own_request(owner, source_goal)
            add_material(owner, 'need_summary', source_need)
            add_material(owner, 'material_outline', outline_v1)
            reviewer = role(pack['roles']['park_specialist'])
            review_and_confirm(owner, reviewer, source_goal)
            source_before = case_history(f[1], source_id)
            source_parent_before = source_before['preparations'][0]
            original = next(row for row in materials(f[1], source_id) if row['slot'] == 'material_outline')

            target_id = create_from_page(owner, pack, target_goal)
            assert source_id != target_id and not materials(f[1], target_id)
            owner.locator('#material-reuse-read').click()
            expect(owner.locator('#material-reuse-form')).to_be_visible(timeout=15000)
            expect(owner.locator('#material-reuse-source option')).to_have_count(1)
            owner.locator('#material-reuse-source').select_option(str(original['id']))
            expect(owner.locator('#material-reuse-confirm')).to_be_disabled()
            owner.locator('#material-reuse-preview').click()
            expect(owner.locator('#material-reuse-selected')).to_contain_text(outline_v1, timeout=15000)
            preview = owner.evaluate('materialReuseView.source_preview')
            assert preview['source_preparation_id'] == source_id and preview['source_evidence_version'] == 1
            assert preview['source_evidence_sha256'] == hashlib.sha256(outline_v1.encode()).hexdigest()
            for reference, field in (('source_case_id', 'case_id'), ('source_run_id', 'run_id'),
                                      ('source_preparation_revision', 'revision'), ('source_snapshot_sha256', 'review_sha256')):
                assert str(preview[reference]) == str(source_parent_before[field])
            assert preview['source_snapshot_sha256'] == observed_review_sha(source_parent_before, materials(f[1], source_id))
            expect(owner.locator('#material-reuse-confirm')).to_be_disabled()
            owner.locator('#material-reuse-purpose').check()
            owner.locator('#material-reuse-reason').fill('SYNTHETIC same-service second Case, reuse only this outline snapshot')
            owner.locator('#material-reuse-confirm').click()
            expect(owner.locator('#prep-materials')).to_contain_text(outline_v1, timeout=15000)
            owner.wait_for_function('()=>materialReusePending===null&&!materialReuseLoading')
            settled(owner, preparation=True)
            copied = materials(f[1], target_id)
            assert len(copied) == 1 and copied[0]['slot'] == 'material_outline'
            assert copied[0]['id'] != original['id'] and copied[0]['version'] == 1
            assert copied[0]['text'] == original['text'] and copied[0]['authenticity'] == 'UNVERIFIED'
            assert all(copied[0][field] == original[field] for field in ('source_kind', 'source_label', 'source_sha256'))
            target_before_review = case_history(f[1], target_id)['preparations'][0]
            assert target_before_review['state'] == 'IN_PREPARATION' and target_before_review['review_sha256'] is None
            assert target_before_review['request_intent'] is None
            assert case_history(f[1], source_id) == source_before
            open_from_list(reviewer, target_goal)
            expect(reviewer.locator('#prep-review')).to_be_disabled()  # Own new summary is required.
            expect(owner.locator('#prep-confirm')).to_be_disabled()
            owner.screenshot(path=str(tmp_path / 'target-outline-only.png'))

            own_request(owner, target_goal)
            add_material(owner, 'need_summary', target_need)
            expect(owner.locator('#prep-confirm')).to_be_disabled()  # Two slots still need this Case's review.
            review_and_confirm(owner, reviewer, target_goal)
            target_pack = download_pack(owner, tmp_path / 'target-downloaded-pack.txt')
            assert target_need in target_pack['text'] and outline_v1 in target_pack['text']
            assert source_need not in target_pack['text'] and source_goal not in target_pack['text']
            assert not owner.evaluate('Boolean(window.reuseInjected)')
            assert owner.evaluate('document.documentElement.scrollWidth<=innerWidth')
            owner.screenshot(path=str(tmp_path / 'target-confirmed-download.png'))
            frozen_target = case_history(f[1], target_id)

            # Later source edits use the original reopen/add/review/confirm controls.
            open_from_list(owner, source_goal)
            owner.locator('#prep-reason').fill('SYNTHETIC source later changes independently')
            owner.locator('#prep-reopen').click()
            expect(owner.locator('#prep-summary')).to_contain_text('待准备 / 重新核对', timeout=15000)
            settled(owner, preparation=True)
            expect(owner.locator('#prep-confirm')).to_be_disabled()
            add_material(owner, 'material_outline', outline_v2)
            review_and_confirm(owner, reviewer, source_goal)
            source_pack = download_pack(owner, tmp_path / 'source-downloaded-pack.txt')
            assert outline_v2 in source_pack['text'] and source_need in source_pack['text']
            assert target_need not in source_pack['text'] and outline_v1 not in source_pack['text']
            assert case_history(f[1], target_id) == frozen_target
            open_from_list(owner, target_goal)
            owner.locator('#material-reuse-read').click()
            expect(owner.locator('#material-reuse-history')).to_contain_text('原来源后来已更新', timeout=15000)
            reuse_history = owner.evaluate('materialReuseView.history')
            assert len(reuse_history) == 1 and reuse_history[0]['source_status'] == 'HISTORICAL_SOURCE_CHANGED'
            expected_proof = dict({key: value for key, value in preview.items() if key != 'text'},
                source_actor_id='fixture-a', target_evidence_id=str(copied[0]['id']), target_version=1,
                target_sha256=hashlib.sha256(outline_v1.encode()).hexdigest(), requires_independent_review=True,
                snapshot_mode='INDEPENDENT_COPY', reason='SYNTHETIC same-service second Case, reuse only this outline snapshot')
            assert expected_proof['purpose'] == 'SAME_SERVICE_MATERIAL_OUTLINE'
            assert reuse_history[0]['material_reuse'] == expected_proof
            assert download_pack(owner, tmp_path / 'target-after-source-update-pack.txt') == target_pack
            owner.screenshot(path=str(tmp_path / 'target-historical-source.png'))
            assert worker.poll() is None and not errors
            assert all(row['status'] < 300 for row in traffic)
            assert len([row for row in traffic if row['path'] == '/api/runs']) == 2
            assert len([row for row in traffic if row['path'] == '/api/preparations']) == 2
            assert len([row for row in traffic if row['path'].endswith('/material-reuse')]) == 1
            assert len([row for row in traffic if row['path'].endswith('/request-intent')]) == 2
            assert authority_snapshot(f[1]) == authority
        except Exception:
            states = []
            for index, context in enumerate(contexts):
                for page in context.pages:
                    states.append(dict(url_path=urlsplit(page.url).path, summary=page.locator('#prep-summary').inner_text(),
                        feedback=page.locator('#prep-command-feedback').inner_text(), reuse=page.locator('#material-reuse-status').inner_text(),
                        error=page.locator('#material-reuse-error').inner_text()))
                    page.screenshot(path=str(tmp_path / ('failure-' + str(index) + '.png')))
            (tmp_path / 'failure-state.json').write_text(json.dumps(dict(states=states, received_POSTs=traffic, sent_requests=requests, page_errors=errors), ensure_ascii=False, indent=2) + '\n')
            raise
        finally:
            for context in contexts:
                context.close()
            browser.close()

    histories = {pid: case_history(f[1], pid) for pid in (source_id, target_id)}
    source_parent, target_parent = (histories[pid]['preparations'][0] for pid in (source_id, target_id))
    assert source_parent['case_id'] != target_parent['case_id'] and source_parent['run_id'] != target_parent['run_id']
    assert all(parent['state'] == 'LOCAL_CONFIRMED' for parent in (source_parent, target_parent))
    assert source_parent['request_intent']['request_text'] == source_goal
    assert target_parent['request_intent']['request_text'] == target_goal
    assert all(parent['request_intent']['required_goals'] == ['LOCAL_MATERIAL_PREPARATION'] for parent in (source_parent, target_parent))
    assert target_parent['review_sha256'] == observed_review_sha(target_parent, materials(f[1], target_id))
    assert target_parent['review_sha256'] != source_parent_before['review_sha256']
    assert all(not histories[pid]['run_assignments'] for pid in histories)
    target_events = sorted(histories[target_id]['preparation_events'], key=lambda event: event['revision'])
    assert [event['action'] for event in target_events] == ['CREATE', 'ADD_EVIDENCE', 'UPDATE_REQUEST', 'ADD_EVIDENCE', 'REVIEW', 'CONFIRM']
    assert target_events[-2]['actor_id'] == pack['roles']['park_specialist'] and target_events[-1]['actor_id'] == 'fixture-a'
    assert target_events[1]['payload']['material_reuse'] == expected_proof
    assert all(event['payload']['snapshot_sha256'] == target_parent['review_sha256'] for event in target_events[-2:])
    assert all(row['state'] == 'NEEDS_INPUT' for history in histories.values() for row in history['cases'])

    # A different ordinary API process and fresh two-role browser sessions, GET only.
    cold_requests = []
    with ordinary_demo(f, tmp_path / 'cold') as api, sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        try:
            for actor in ('fixture-a', pack['roles']['park_specialist']):
                context = browser.new_context(viewport=dict(width=width, height=1000), accept_downloads=True)
                page = context.new_page()
                page.on('request', lambda request: cold_requests.append(dict(method=request.method, path=urlsplit(request.url).path)))
                page.on('pageerror', lambda error: errors.append(str(error)))
                login(page, api, f, actor)
                for goal, pid, expected_pack in ((source_goal, source_id, source_pack), (target_goal, target_id, target_pack)):
                    open_from_list(page, goal)
                    assert page.evaluate('preparationId') == pid
                    expect(page.locator('#prep-summary')).to_contain_text('本地资料准备已确认')
                    assert download_pack(page, tmp_path / ('cold-' + actor + '-' + pid + '.txt')) == expected_pack
                    if actor == 'fixture-a' and pid == target_id:
                        page.locator('#material-reuse-read').click()
                        expect(page.locator('#material-reuse-history')).to_contain_text('原来源后来已更新', timeout=15000)
                        assert page.evaluate('materialReuseView.history') == reuse_history
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path=str(tmp_path / ('cold-' + actor + '.png')))
                context.close()
        finally:
            browser.close()
    assert cold_requests and {row['method'] for row in cold_requests} == {'GET'} and not errors
    assert {pid: case_history(f[1], pid) for pid in histories} == histories
    assert authority_snapshot(f[1]) == authority
    (tmp_path / 'actual-material-reuse-user-flow.json').write_text(json.dumps(dict(
        scope='SYNTHETIC_LOCAL_TWO_NEW_ORDINARY_DOM_CASES_SAME_OWNER_SAME_SERVICE', width=width,
        initial_business_rows=0, API_business_setup_calls=0, JS_business_or_navigation_calls=0,
        preparation_ids=[source_id, target_id], source_preview=preview, provenance=reuse_history,
        authority_before_after_sha256=stable_hash(authority), case_history_sha256={pid: stable_hash(value) for pid, value in histories.items()},
        source_pack={k: v for k, v in source_pack.items() if k != 'text'}, target_pack={k: v for k, v in target_pack.items() if k != 'text'},
        sent_requests=requests, received_POSTs=traffic, cold_requests=cold_requests,
        independent_request_review_confirmation=True, target_snapshot_unchanged_after_source_edit=True,
        cold_API_and_two_fresh_role_contexts=True, runtime_authority_changes=0, Run_assignments_created=0,
        real_model_calls=0, Windows='NOT_RUN', formal_AT35='NOT_RUN', cross_enterprise_template_AT08='NOT_RUN', real_business='NOT_RUN'), ensure_ascii=False, indent=2) + '\n')
