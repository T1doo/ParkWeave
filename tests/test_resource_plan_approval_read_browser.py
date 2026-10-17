"""Real Chromium/HTTP/PG; source adapter is explicit signed SYNTHETIC DI only."""
from datetime import datetime,timedelta,timezone
import time
from uuid import uuid4
import pytest
from playwright.sync_api import sync_playwright,expect

from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_new_enterprise_local_chain import actual_http
from test_native_preparation_entry_browser import open_record,ordinary_process
from test_ordinary_runtime_read import snapshot
from resource_approval_read_support import seeded,factory


def browser_page(pw):
    browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    return browser,browser.new_page()


def test_original_preparation_read_only_approval_navigation_and_fresh_factory_restart(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,_,query=seeded(f,tmp_path,monkeypatch);before=snapshot(f[1])
    for name in ('first','fresh-factory'):
        with actual_http(factory(f,monkeypatch,source.provider)) as (api,_),sync_playwright() as pw:
            browser,page=browser_page(pw);seen=[];page.on('request',lambda r:seen.append(r.method))
            open_record(page,api,f,p);page.locator('#resource-plan-approval-read').click()
            expect(page.locator('#resource-plan-approval-status')).to_contain_text('本次读取已核对已有资源方案批准')
            expect(page.locator('#resource-plan-approval-result')).to_contain_text(source.record()['approval_id'])
            expect(page.locator('#resource-plan-approval-result')).to_contain_text('合成契约样本，不证明真实批准')
            page.locator('#resource-plan-approval-original').click()
            expect(page.locator('#resource-plan-approval-status')).to_contain_text('本次读取已核对已有资源方案批准')
            assert all(x=='GET' for x in seen) and snapshot(f[1])==before
            page.screenshot(path=str(tmp_path/(name+'-resource-approval.png')),full_page=True);browser.close()


def test_default_process_no_provider_remains_unavailable_after_process_restart(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,_,_=seeded(f,tmp_path,monkeypatch);before=snapshot(f[1])
    for name in ('ordinary-first','ordinary-restarted'):
        with ordinary_process(f,tmp_path/name) as api,sync_playwright() as pw:
            browser,page=browser_page(pw);seen=[];page.on('request',lambda r:seen.append(r.method))
            open_record(page,api,f,p);page.locator('#resource-plan-approval-read').click()
            expect(page.locator('#resource-plan-approval-status')).to_contain_text('读取契约当前不可用')
            expect(page.locator('#resource-plan-approval-result')).to_be_empty()
            expect(page.locator('#resource-plan-approval-original')).to_be_hidden()
            assert all(x=='GET' for x in seen) and snapshot(f[1])==before;browser.close()
    assert not source.calls


def test_permission_revocation_clears_original_approval_and_expiry_timer_never_grants_action(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,app,_=seeded(f,tmp_path,monkeypatch)
    with actual_http(app) as (api,_),sync_playwright() as pw:
        browser,page=browser_page(pw);seen=[];page.on('request',lambda r:seen.append(r.method));open_record(page,api,f,p)
        record=source.record();record['valid_until']=(datetime.now(timezone.utc)+timedelta(seconds=3)).isoformat();source.write(record)
        page.locator('#resource-plan-approval-read').click()
        expect(page.locator('#resource-plan-approval-status')).to_contain_text('本次读取已核对已有资源方案批准')
        expect(page.locator('#resource-plan-approval-status')).to_contain_text('已过有效期',timeout=6000)
        with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
        before=snapshot(f[1]);page.locator('#resource-plan-approval-read').click()
        expect(page.locator('#prep-detail')).to_be_hidden();expect(page.locator('#resource-plan-approval-result')).to_be_empty()
        assert all(x=='GET' for x in seen) and snapshot(f[1])==before;browser.close()


def test_long_validity_rearms_browser_timer_until_actual_expiry(receipt_fixture,tmp_path,monkeypatch):
    f=receipt_fixture;p,source,app,_=seeded(f,tmp_path,monkeypatch);now=datetime.now(timezone.utc)
    record=source.record();record['valid_until']=(now+timedelta(days=30)).isoformat();source.write(record)
    before=snapshot(f[1])
    with actual_http(app) as (api,_),sync_playwright() as pw:
        browser,page=browser_page(pw);page.clock.install(time=now);seen=[];page.on('request',lambda r:seen.append(r.method))
        open_record(page,api,f,p);page.locator('#resource-plan-approval-read').click()
        expect(page.locator('#resource-plan-approval-status')).to_contain_text('本次读取已核对已有资源方案批准')
        # Installed Playwright coerces each jump to int32; cross the limit in two jumps.
        page.clock.fast_forward(20*24*60*60*1000)
        page.clock.fast_forward(5*24*60*60*1000)
        expect(page.locator('#resource-plan-approval-status')).to_contain_text('本次读取已核对已有资源方案批准')
        page.clock.fast_forward(6*24*60*60*1000)
        expect(page.locator('#resource-plan-approval-status')).to_contain_text('已过有效期')
        assert all(x=='GET' for x in seen) and snapshot(f[1])==before;browser.close()


@pytest.mark.parametrize('late_status',[200,403])
def test_late_old_approval_after_preparation_aba_cannot_replace_current_revoked_record(receipt_fixture,tmp_path,monkeypatch,late_status):
    f=receipt_fixture;p,source,app,_=seeded(f,tmp_path,monkeypatch);before=snapshot(f[1])
    with actual_http(app) as (api,_),sync_playwright() as pw:
        browser,page=browser_page(pw);pending=[];seen=[];page.on('request',lambda r:seen.append(r.method))
        def delayed(route):
            if pending:route.continue_();return
            pending.append((route,route.fetch()))
        page.route('**/runtime/resource-plan-approval?*',delayed)
        open_record(page,api,f,p);page.locator('#resource-plan-approval-read').click()
        until=time.monotonic()+5
        while not pending and time.monotonic()<until:page.wait_for_timeout(20)
        assert pending
        page.locator('#existing-preparation-id').fill(str(uuid4()));page.locator('#existing-preparation-id').fill(p['preparation_id'])
        page.locator('#existing-preparation-read').click();expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')
        record=source.record();record.update(state='REVOKED',revoked_at=datetime.now(timezone.utc).isoformat(),record_revision=2);source.write(record)
        page.locator('#resource-plan-approval-read').click();expect(page.locator('#resource-plan-approval-status')).to_contain_text('原批准已撤销')
        route,response=pending[0]
        if late_status==200:route.fulfill(response=response)
        else:route.fulfill(status=403,json={'detail':'record unavailable or authorization denied'})
        page.wait_for_timeout(150);expect(page.locator('#resource-plan-approval-status')).to_contain_text('原批准已撤销')
        expect(page.locator('#prep-detail')).to_be_visible();assert all(x=='GET' for x in seen) and snapshot(f[1])==before;browser.close()
