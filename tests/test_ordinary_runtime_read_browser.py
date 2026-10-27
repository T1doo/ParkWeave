"""Actual default ordinary factory subprocess and original UI navigation.

No production protected pin is supplied in these tests. Existing legacy dispatch
preconditions are isolated synthetic data; missing signed provider is rejected.
"""
from uuid import uuid4
import time

import pytest
from playwright.sync_api import sync_playwright, expect

from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_service_dispatches import offer
from test_native_preparation_entry_browser import ordinary_process, open_record
from test_ordinary_runtime_read import snapshot
from test_native_run_access_writer import writer_fixture, approve
from test_native_run_access_activation import activate
from test_ordinary_runtime_read import reference_factory
from test_new_enterprise_local_chain import actual_http


def test_existing_signed_access_history_opens_original_read_only_panel_with_host_binder_di(writer_fixture,monkeypatch,tmp_path):
    """Actual browser/PG/IPC; protected host binder is DI, not production OS proof."""
    h=writer_fixture;approve(h,seconds=240);assert activate(h.a).status_code==200
    app,_,_=reference_factory(h,monkeypatch)
    before=snapshot(h.f[1])
    with actual_http(app) as (api,_), sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page();seen=[];page.on('request',lambda r:seen.append((r.method,r.url)))
        open_record(page,api,h.f,h.parent)
        page.locator('#runtime-access-read').click()
        expect(page.locator('#run-access-panel')).to_be_visible()
        expect(page.locator('#run-access-summary')).to_contain_text('已有受限合成fixture READ范围生效')
        expect(page.locator('#run-access-scope')).to_contain_text(h.parent['run_id'])
        expect(page.locator('#run-access-history')).to_contain_text('APPROVE')
        expect(page.locator('#run-access-request')).to_be_hidden()
        expect(page.locator('#run-access-decision')).to_be_hidden()
        expect(page.locator('#runtime-entry-status')).to_contain_text('决定与激活命令保持关闭')
        assert any('/runtime/access-approval?' in url for _,url in seen)
        assert all(method=='GET' for method,_ in seen) and snapshot(h.f[1])==before
        page.screenshot(path=str(tmp_path/'readonly-signed-history-host-binder-di.png'),full_page=True)
        browser.close()


def test_ordinary_navigation_original_run_dispatch_exact_catalog_and_missing_approval(receipt_fixture,tmp_path):
    f=receipt_fixture;r,p,_=offer(f);assert r.status_code==201
    before=snapshot(f[1])
    with ordinary_process(f,tmp_path) as api, sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page();seen=[]
        page.on('request',lambda r:seen.append((r.method,r.url)))
        open_record(page,api,f,p)
        page.locator('#runtime-run-read').click()
        expect(page.locator('#result')).to_contain_text(p['run_id'])
        expect(page.locator('#result')).to_contain_text(p['case_id'])
        page.locator('#runtime-catalog-read').click()
        expect(page.locator('#runtime-catalog-result')).to_contain_text('synthetic-material-preparation / v1')
        expect(page.locator('#runtime-catalog-result')).to_contain_text('目录不构成资源方案批准')
        page.locator('#runtime-access-read').click()
        expect(page.locator('#runtime-entry-status')).to_contain_text('缺少普通只读 provider')
        page.locator('#runtime-dispatch-read').click()
        expect(page.locator('#dispatch-detail')).to_be_visible()
        expect(page.locator('#dispatch-summary')).to_contain_text(p['goal'] if 'goal' in p else 'SYNTHETIC')
        assert all(method=='GET' for method,_ in seen)
        assert any('/runtime/dispatch?' in url for _,url in seen)
        assert snapshot(f[1])==before
        page.screenshot(path=str(tmp_path/'runtime-navigation.png'),full_page=True)
        browser.close()


def test_ordinary_restart_fresh_browser_reads_original_binding_and_revocation_stays_denied(receipt_fixture,tmp_path):
    f=receipt_fixture;r,p,_=offer(f);assert r.status_code==201
    before=snapshot(f[1])
    for name in ('first','restarted'):
        with ordinary_process(f,tmp_path/name) as api, sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
            page=browser.new_page();seen=[];page.on('request',lambda r:seen.append(r.method))
            open_record(page,api,f,p)
            page.locator('#runtime-catalog-read').click()
            expect(page.locator('#runtime-catalog-result')).to_contain_text('原服务')
            page.locator('#runtime-run-read').click()
            expect(page.locator('#result')).to_contain_text(p['run_id'])
            assert all(method=='GET' for method in seen) and snapshot(f[1])==before
            if name=='restarted':
                with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
                revoked=snapshot(f[1])
                page.locator('#runtime-catalog-read').click()
                expect(page.locator('#prep-detail')).to_be_hidden()
                expect(page.locator('#runtime-catalog-result')).to_be_empty()
                expect(page.locator('#result')).to_be_empty()
                expect(page.locator('#page-feedback')).to_contain_text('当前身份无此事项或操作权限')
                assert snapshot(f[1])==revoked and all(method=='GET' for method in seen)
            browser.close()


@pytest.mark.parametrize('late_status',[200,403])
def test_old_bound_catalog_reply_after_preparation_aba_cannot_replace_current_view(receipt_fixture,tmp_path,late_status):
    f=receipt_fixture;r,p,_=offer(f);assert r.status_code==201
    before=snapshot(f[1])
    with ordinary_process(f,tmp_path) as api, sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        page=browser.new_page();pending=[];seen=[]
        page.on('request',lambda r:seen.append(r.method))
        def delayed(route):
            if pending:route.continue_();return
            pending.append((route,route.fetch()))
        page.route('**/runtime/catalog?*',delayed)
        open_record(page,api,f,p)
        page.locator('#runtime-catalog-read').click()
        deadline=time.monotonic()+5
        while not pending and time.monotonic()<deadline:page.wait_for_timeout(20)
        assert pending
        page.locator('#existing-preparation-id').fill(str(uuid4()))
        page.locator('#existing-preparation-id').fill(p['preparation_id'])
        page.locator('#existing-preparation-read').click()
        expect(page.locator('#existing-preparation-status')).to_contain_text('已读取原资料记录')
        page.locator('#runtime-catalog-read').click()
        expect(page.locator('#runtime-catalog-result')).to_contain_text('原服务')
        route,response=pending[0]
        if late_status==200:route.fulfill(response=response)
        else:route.fulfill(status=403,json={'detail':'record unavailable or authorization denied'})
        page.wait_for_timeout(150)
        expect(page.locator('#runtime-catalog-result')).to_contain_text('原服务')
        expect(page.locator('#prep-detail')).to_be_visible()
        assert all(method=='GET' for method in seen) and snapshot(f[1])==before
        browser.close()
