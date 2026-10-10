"""Original page's snapshot semantics and cold GET-only lost-result recovery."""
from test_isolated_execution_preview_browser import preview_page, open_page, lost, recovered
from test_isolated_execution_preview import preparation_fixture, snapshot


def test_original_page_never_claims_atomic_current_after_lost_response_cold_recovery(preview_page):
    f, p, engine, page, errors = preview_page
    open_page(page, f, p)
    before = snapshot(f)
    storage, post = lost(page, f, p)
    requests = []
    page.on('request', lambda request: requests.append(request.method))
    page.reload()
    open_page(page, f, p)
    recovered(page)
    assert page.evaluate('executionPreviewView.result') == post['result']
    assert page.evaluate('executionPreviewView.source_atomicity') is False
    assert page.evaluate('executionPreviewView.history[0].source_state') == 'SNAPSHOT_MATCH'
    text = page.locator('#execution-preview-result').inner_text()
    assert '不保证提交时全部来源不变' in text and 'CURRENT' not in text
    assert 'PRIVATE_PREVIEW' not in text
    assert page.evaluate('JSON.stringify({...localStorage})') == storage
    for width in (320, 390, 1200):
        page.set_viewport_size({'width':width, 'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    assert set(requests) == {'GET'} and snapshot(f) == before and not errors
