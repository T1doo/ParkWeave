"""Current shared material pack through real HTTP, PG and original Chromium DOM.

Optional browser dependency: playwright 1.58.0 and /usr/bin/chromium. Fresh
owned conftest databases only. No production authority or native changes.
"""
import hashlib
import json
import socket
import threading
import time
from pathlib import Path
import pytest
import uvicorn
from parkweave.api import create_app
from test_preparation import preparation_fixture, create, filled, add, command
from test_readiness import rows

playwright = pytest.importorskip('playwright.sync_api')
EVIDENCE = Path(__file__).resolve().parents[1] / 'docs/F2/evidence/material-text-pack'


@pytest.fixture
def browser_page(preparation_fixture):
    f = preparation_fixture
    listener = socket.socket(); listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_app(f[0]), host='127.0.0.1', port=port,
                                          log_level='warning', access_log=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.02)
        assert server.started, 'owned HTTP server failed to start'
        with playwright.sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
            context = browser.new_context(accept_downloads=True)
            page = context.new_page(); errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{port}/')
            yield f, page, errors
            assert not errors, errors
            context.close(); browser.close()
    finally:
        server.should_exit = True; thread.join(timeout=10); listener.close()
        assert not thread.is_alive(), 'owned HTTP server did not stop'


def open_preparation(page, f, p, user='fixture-a'):
    page.locator('#token').fill(f[2][user])
    page.locator('#token').dispatch_event('change')
    page.evaluate('async id => {await loadPreparation(id)}', p['preparation_id'])
    page.wait_for_function("()=>readinessView !== null && !document.querySelector('#material-pack-generate').disabled")


def generate(page):
    page.locator('#material-pack-generate').click()
    page.wait_for_function('()=>!materialPackBusy')
    return page.locator('#material-pack-text').input_value()


@pytest.mark.parametrize('user', ['fixture-a', 'prep-specialist-fixture-a'])
def test_real_http_current_text_copy_download_and_no_writes(browser_page, user):
    f, page, _ = browser_page
    p = filled(f)
    p = add(f, p, 'material_outline', 'Actual shared v2 <script>window.packInjection=true</script>\n已批准（企业原文，未经核实）').json()
    p = command(f, p, 'REQUEST_CHANGES', 'prep-specialist-fixture-a', reason='Actual reviewer directory gap', correction_slots=['material_outline']).json()
    before = rows(f); open_preparation(page, f, p, user)
    requests = []
    page.on('request', lambda r: requests.append((r.method, r.url)))
    text = generate(page)
    assert p['case_id'] in text and '资料 revision：'+str(p['revision']) in text
    assert 'Actual shared v2' in text and '/ v2' in text and 'Actual reviewer directory gap' in text
    assert '须补交新版' in text and 'PENDING / UNKNOWN' in text and 'Case目标未完成' in text
    assert '\\n已批准' in text and not page.evaluate('Boolean(window.packInjection)')
    page.locator('#material-pack-copy').click(); page.wait_for_function('()=>!materialPackBusy')
    assert '已重新核对并复制' in page.locator('#material-pack-status').inner_text()
    with page.expect_download() as download_info:
        page.locator('#material-pack-download').click()
    download = download_info.value
    payload = Path(download.path()).read_bytes()
    assert payload == text.encode('utf-8') and download.suggested_filename.endswith('-r'+str(p['revision'])+'.txt')
    assert rows(f) == before and sum(url.endswith('/readiness') for _, url in requests) == 6 and all(method == 'GET' for method, _ in requests)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if user == 'fixture-a':
        screenshots = []
        for width in (1200, 390, 320):
            page.set_viewport_size({'width': width, 'height': 900})
            page.locator('#material-pack-panel').scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            dest = EVIDENCE / ('current-pack-'+str(width)+'.png')
            page.screenshot(path=str(dest)); screenshots.append({'file': dest.name, 'sha256': hashlib.sha256(dest.read_bytes()).hexdigest()})
        (EVIDENCE / 'browser-output.json').write_text(json.dumps({'scope':'SYNTHETIC_READ_ONLY_SHARED_MATERIAL_PACK', 'copy':'PASS', 'download':'PASS', 'requests':6, 'all_requests_get_readiness':True, 'database_rows_unchanged':True, 'text_sha256':hashlib.sha256(payload).hexdigest(), 'screenshots':screenshots}, indent=2)+'\n')


def test_missing_materials_are_gaps_without_invented_requirements(browser_page):
    f, page, _ = browser_page; p, _, _ = create(f)
    before = rows(f); open_preparation(page, f, p); text = generate(page)
    assert text.count('尚未提供此材料') == 2 and 'UNKNOWN' in text
    assert '不填造正文或证明' in text and rows(f) == before


def test_current_version_change_refuses_old_page_then_refreshes(browser_page):
    f, page, _ = browser_page; p = filled(f); open_preparation(page, f, p)
    assert generate(page)
    p = add(f, p, 'material_outline', 'Actual newer shared version').json()
    before = rows(f)
    page.locator('#material-pack-copy').click(); page.wait_for_function('()=>!materialPackBusy')
    assert page.locator('#material-pack-text').input_value() == ''
    assert '已变化' in page.locator('#material-pack-status').inner_text() and rows(f) == before
    open_preparation(page, f, p); assert 'Actual newer shared version' in generate(page)


@pytest.mark.parametrize('capability', ['READ', 'PREPARE'])
def test_revocation_uses_real_403_and_clears_output(browser_page, capability):
    f, page, _ = browser_page; p = filled(f); open_preparation(page, f, p); assert generate(page)
    with f[1].connect() as c:
        if capability == 'READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        else:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
    before = rows(f); responses = []
    page.on('response', lambda r: responses.append(r.status) if r.url.endswith('/readiness') else None)
    page.locator('#material-pack-download').click(); page.wait_for_function("()=>document.querySelector('#prep-detail').hidden")
    assert responses == [403] and page.locator('#material-pack-text').input_value() == '' and rows(f) == before


def test_same_revision_source_change_refuses_pack(browser_page):
    f, page, _ = browser_page; p = filled(f); open_preparation(page, f, p)
    with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=jsonb_set(source,'{kind}','\"UNVERIFIED\"') WHERE park_id='park-a'")
    assert generate(page) == ''
    assert '已变化' in page.locator('#material-pack-status').inner_text()


def hold_first_read(page, id):
    held = []
    def hold(route):
        if not held:
            response = route.fetch(); held.append((route, response))
        else:route.continue_()
    page.route('**/api/preparations/'+id+'/readiness', hold)
    page.evaluate("window.packTask=materialPackAction('generate'); void 0")
    for _ in range(100):
        page.wait_for_timeout(20)
        if held:break
    assert len(held) == 1 and held[0][1].status == 200
    return held[0]


def test_change_between_reads_refuses_delayed_snapshot(browser_page):
    f, page, _ = browser_page; p = filled(f); open_preparation(page, f, p)
    route, response = hold_first_read(page, p['preparation_id'])
    add(f, p, 'material_outline', 'Interleaved new version')
    route.fulfill(response=response)
    page.wait_for_function('()=>!materialPackBusy')
    assert page.locator('#material-pack-text').input_value() == ''
    assert '已变化' in page.locator('#material-pack-status').inner_text()


def test_delayed_old_identity_response_and_duplicate_generation_cannot_publish(browser_page):
    f, page, _ = browser_page; p = filled(f); open_preparation(page, f, p)
    route, response = hold_first_read(page, p['preparation_id'])
    page.evaluate("materialPackAction('generate'); void 0")
    page.locator('#token').fill(f[2]['fixture-b']); page.locator('#token').dispatch_event('change')
    route.fulfill(response=response); page.evaluate('async()=>{await window.packTask}')
    assert page.locator('#material-pack-text').input_value() == ''
    assert page.locator('#material-pack-output').is_hidden()


def test_delayed_old_case_response_cannot_replace_new_case(browser_page):
    f, page, _ = browser_page; p = filled(f); other, _, _ = create(f)
    open_preparation(page, f, p); route, response = hold_first_read(page, p['preparation_id'])
    page.evaluate('async id=>{await loadPreparation(id)}', other['preparation_id'])
    route.fulfill(response=response); page.evaluate('async()=>{await window.packTask}')
    assert page.locator('#material-pack-text').input_value() == ''
    assert '尚未提供此材料' in generate(page)
    assert p['case_id'] not in page.locator('#material-pack-text').input_value()


def test_unknown_client_operation_locks_and_clears_pack(browser_page):
    f, page, _ = browser_page; p = filled(f); open_preparation(page, f, p); assert generate(page)
    page.evaluate("prepCommandPending={state:'UNKNOWN'};renderPrepCommandPending()")
    assert page.locator('#material-pack-generate').is_disabled()
    assert page.locator('#material-pack-text').input_value() == ''


def test_unshared_facts_never_enter_pack_and_shared_brief_keeps_boundaries(browser_page):
    from test_material_preparation_drafts import preview, save, body
    from test_case_fact_clarifications_integration import current_parent
    f, page, _ = browser_page
    # Explicitly use the same owned preparation fixture served by HTTP.
    from test_case_fact_clarifications_integration import seed_facts_through_original_api, declare, confirm, confirm_body
    p, _, _ = create(f); selected = seed_facts_through_original_api(f)
    assert declare(f, p).status_code == 200; p = current_parent(f, p)
    assert confirm(f, p, confirm_body(f, p, selected)).status_code == 200; p = current_parent(f, p)
    open_preparation(page, f, p, 'prep-specialist-fixture-a'); text = generate(page)
    assert 'PRIVATE_REGION_SELECTED' not in text and 'PRIVATE_SERVICE_NEED_SELECTED' not in text
    x = preview(f, p).json(); assert save(f, p, body(x)).status_code == 201; p = current_parent(f, p)
    before = rows(f); open_preparation(page, f, p, 'prep-specialist-fixture-a'); text = generate(page)
    assert 'PRIVATE_REGION_SELECTED' in text and 'PRIVATE_SERVICE_NEED_SELECTED' in text
    assert 'PRIVATE_CONFLICTING_REGION' not in text and 'PRIVATE_FACT_EXCERPT_' not in text
    assert rows(f) == before


def test_other_enterprise_original_http_denies_pack_source(browser_page):
    f, page, _ = browser_page; p = filled(f)
    page.locator('#token').fill(f[2]['fixture-b']); page.locator('#token').dispatch_event('change')
    response = page.request.get(page.url.rstrip('/')+'/api/preparations/'+p['preparation_id']+'/readiness', headers={'Authorization':'Bearer '+f[2]['fixture-b']})
    assert response.status == 403 and 'SYNTHETIC material list' not in response.text()
    assert page.locator('#material-pack-text').input_value() == ''
