"""Ordinary factory entry; all positive records are isolated synthetic fixtures.

No Approval/access provider is attached to configured_app. Fixture seeding and
fault injection below are test setup, never an ordinary startup provisioner.
"""
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from parkweave.api import configured_app
from parkweave import preparation as prep
from parkweave.store import Denied
from test_preparation import preparation_fixture, headers, filled
from test_new_enterprise_local_chain import actual_http


TABLES = ('principals', 'capability_grants', 'preparation_grants', 'field_grants',
          'action_grants', 'run_assignments', 'preparation_catalog', 'preparations',
          'preparation_events', 'preparation_evidence', 'runs', 'cases', 'operations',
          'outbox', 'model_steps', 'synthetic_resource_holds', 'case_resource_links')


def snapshot(owner):
    with owner.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        return {t: c.execute(f'SELECT to_jsonb(t) row FROM {t} t ORDER BY to_jsonb(t)::text').fetchall()
                for t in TABLES}


def ordinary(f, monkeypatch):
    monkeypatch.setenv('PARKWEAVE_DSN', f[0].dsn)
    monkeypatch.setenv('PARKWEAVE_MODE', 'LOCAL')
    return configured_app()


def entry(api, f, p, actor='fixture-a'):
    return api.get('/api/preparations/' + p['preparation_id'] + '/entry', headers=headers(f[2], actor))


def test_ordinary_unprepared_identity_is_denied_without_provisioning(fixture, monkeypatch):
    f = fixture
    before = snapshot(f[1])
    with TestClient(ordinary(f, monkeypatch)) as api:
        r = entry(api, f, dict(preparation_id=str(uuid4())))
        assert r.status_code == 403 and r.json()['detail'] == 'record unavailable or authorization denied'
        with pytest.raises(Denied, match='current preparation grant required'):
            prep.entry(f[0], f[2]['fixture-a'], uuid4())
        assert api.get('/api/plan-approval/status', headers=headers(f[2])).json()['enabled'] is False
        access = api.get('/api/run-access/status', headers=headers(f[2])).json()
        assert not access['enabled'] and not access['can_approve'] and access['activation_pending']
    assert snapshot(f[1]) == before


@pytest.mark.parametrize('actor,role', [('fixture-a', 'enterprise_operator'),
                                       ('prep-specialist-fixture-a', 'park_specialist')])
def test_existing_owner_and_assigned_reviewer_cold_read_no_runtime_provider(preparation_fixture, monkeypatch, actor, role):
    f = preparation_fixture
    p = filled(f)
    before = snapshot(f[1])
    for _ in range(2):
        with TestClient(ordinary(f, monkeypatch)) as api:
            x = entry(api, f, p, actor)
            assert x.status_code == 200, x.text
            x = x.json()
            assert x['role'] == role and x['revision'] == p['revision'] and x['read_only']
            assert not x['approval_granted'] and x['qualification'] == 'NOT_EVALUATED'
            read = api.get('/api/preparations/' + p['preparation_id'], headers=headers(f[2], actor))
            assert read.status_code == 200 and len(read.json()['current_materials']) == 2
            assert api.get('/api/plan-approval/status', headers=headers(f[2], actor)).json()['enabled'] is False
    assert snapshot(f[1]) == before


@pytest.mark.parametrize('damage,status,detail', [
    ('prepare', 403, 'current preparation grant required'),
    ('review', 403, 'current assigned preparation reviewer required'),
    ('reviewer', 403, 'current assigned preparation reviewer required'),
    ('read', 403, 'current capability grant required'),
    ('identity', 403, 'current authorization required'),
    ('catalog', 409, 'current SYNTHETIC preparation catalog required'),
    ('catalog-source', 409, 'current SYNTHETIC preparation catalog required'),
    ('exact-version', 409, 'current SYNTHETIC preparation catalog required'),
])
def test_current_missing_inputs_refuse_and_stay_missing_after_factory_restart(preparation_fixture, monkeypatch, damage, status, detail):
    f = preparation_fixture
    p = filled(f)
    with f[1].connect() as c:
        if damage == 'prepare': c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        elif damage == 'review': c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a'")
        elif damage == 'reviewer': c.execute("UPDATE principals SET active=false WHERE id='prep-specialist-fixture-a'")
        elif damage == 'read': c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        elif damage == 'identity': c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
        elif damage == 'catalog': c.execute("UPDATE preparation_catalog SET source='{}'::jsonb WHERE park_id='park-a'")
        elif damage == 'catalog-source': c.execute("UPDATE preparation_catalog SET source=%s WHERE park_id='park-a'", (Jsonb({'kind':'UNKNOWN'}),))
        else:
            c.execute("INSERT INTO preparation_catalog SELECT park_id,service_id,2,name,source,namespace,qualification FROM preparation_catalog WHERE park_id='park-a' AND version=1")
            c.execute("UPDATE preparation_catalog SET source='{}'::jsonb WHERE park_id='park-a' AND version=1")
    before = snapshot(f[1])
    for _ in range(2):
        with TestClient(ordinary(f, monkeypatch)) as api:
            r = entry(api, f, p)
            assert r.status_code == status
            assert r.json()['detail'] == (detail if status == 409 else 'record unavailable or authorization denied')
            if status == 403:
                with pytest.raises(Denied, match=detail):
                    prep.entry(f[0], f[2]['fixture-a'], UUID(p['preparation_id']))
    assert snapshot(f[1]) == before


@pytest.mark.parametrize('actor', ['fixture-b', 'fixture-c', 'prep-specialist-fixture-b', 'prep-specialist-fixture-c'])
def test_cross_tenant_or_unassigned_record_never_opens(preparation_fixture, monkeypatch, actor):
    f = preparation_fixture
    p = filled(f)
    before = snapshot(f[1])
    with TestClient(ordinary(f, monkeypatch)) as api:
        r = entry(api, f, p, actor)
        assert r.status_code == 403 and r.json()['detail'] == 'record unavailable or authorization denied'
        r = api.get('/api/preparations/' + str(uuid4()) + '/entry', headers=headers(f[2], actor))
        assert r.status_code == 403 and r.json()['detail'] == 'record unavailable or authorization denied'
    assert snapshot(f[1]) == before


def test_browser_direct_read_and_current_revocation(preparation_fixture, monkeypatch):
    from playwright.sync_api import sync_playwright, expect
    f = preparation_fixture
    p = filled(f)
    before = snapshot(f[1])
    with actual_http(ordinary(f, monkeypatch)) as (api, _), sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
        page = browser.new_page()
        seen = []
        page.on('request', lambda r: seen.append((r.method, r.url)))
        page.goto(str(api.base_url) + '?preparation_id=' + p['preparation_id'])
        assert not any('/entry' in url for _, url in seen)
        page.locator('#token').fill(f[2]['fixture-a'])
        page.locator('#existing-preparation-read').click()
        expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')
        expect(page.locator('#prep-materials')).to_contain_text('SYNTHETIC source text')
        assert all(method == 'GET' for method, _ in seen)
        assert snapshot(f[1]) == before
        # A new page/factory performs only reads of the original record.
        page.close()
        page = browser.new_page()
        page.on('request', lambda r: seen.append((r.method, r.url)))
        page.goto(str(api.base_url))
        page.locator('#token').fill(f[2]['prep-specialist-fixture-a'])
        page.locator('#existing-preparation-id').fill(p['preparation_id'])
        page.locator('#existing-preparation-read').click()
        expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')
        expect(page.locator('#opportunity-panel')).to_be_hidden()
        page.locator('#token').fill(f[2]['fixture-a'])
        with f[1].connect() as c:
            c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
        revoked = snapshot(f[1])
        page.locator('#existing-preparation-read').click()
        expect(page.locator('#existing-preparation-status')).to_contain_text('当前身份无此事项或操作权限')
        expect(page.locator('#prep-detail')).to_be_hidden()
        expect(page.locator('#prep-materials')).to_be_empty()
        assert all(method == 'GET' for method, _ in seen)
        assert snapshot(f[1]) == revoked
        browser.close()
