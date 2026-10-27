"""Offline CI boundary checks; no browser, product import or DB."""
import subprocess
import pytest
from scripts.ordinary_resource_browser_once import BRANCH, BrowserBoundary, require_hosted_once, redact


def test_hosted_exact_first_run_refusal_and_session_redaction():
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    valid = dict(RESOURCE_REPOSITORY='T1doo/ParkWeave', RESOURCE_REF=BRANCH, RESOURCE_EVENT='push',
                 RESOURCE_ATTEMPT='1', RESOURCE_NUMBER='1', RESOURCE_PUBLIC='true',
                 RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Linux', RESOURCE_SHA=head)
    assert require_hosted_once(valid) == head
    for key, value in [('RESOURCE_PUBLIC', 'false'), ('RESOURCE_ATTEMPT', '2'), ('RESOURCE_NUMBER', '2'),
                       ('RESOURCE_REF', 'refs/heads/main'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                       ('RESOURCE_SHA', '0' * 40), ('PARKWEAVE_DSN', 'synthetic-forbidden')]:
        with pytest.raises(RuntimeError):require_hosted_once({**valid, key:value})
    assert 'private-owned-value' not in redact({'error':'fill private-owned-value'}, ['private-owned-value'])


def test_browser_cannot_leave_origin_exceed_click_budget_or_write_in_cold_read():
    b = BrowserBoundary('http://127.0.0.1:8123', {})
    assert b.permit('GET', 'http://127.0.0.1:8123/api/resource-combinations')
    for method, url in [('GET','https://example.com/'),('GET','http://127.0.0.1:8124/'),
                        ('POST','http://127.0.0.1:8123/api/resource-combinations'),
                        ('DELETE','http://127.0.0.1:8123/api/preparations/1')]:
        assert not b.permit(method, url)
    b.allow_scope_writes({'resources':[{'id':'one'}, {'id':'two'}]}, 'prep')
    assert not b.permit('POST', 'http://127.0.0.1:8123/api/runs')
    assert not b.permit('POST', 'http://127.0.0.1:8123/api/resource-combinations?retry=1')
    for path in list(b.remaining):
        url = 'http://127.0.0.1:8123' + path
        assert b.permit('POST', url)
        assert not b.permit('POST', url)
    b.readonly()
    assert not b.permit('POST', 'http://127.0.0.1:8123/api/resource-combinations')
