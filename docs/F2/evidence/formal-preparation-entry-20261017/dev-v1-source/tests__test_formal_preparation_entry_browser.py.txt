"""Actual browser/HTTP negative entry only, no real-source acceptance proof."""
import time
import pytest
from playwright.sync_api import sync_playwright,expect

from test_preparation import preparation_fixture,filled
from test_native_preparation_entry import snapshot
from test_native_preparation_entry_browser import ordinary_process,open_record


def browser_page(pw):
    b=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    return b,b.new_page()


def test_default_formal_entry_stays_closed_after_ordinary_process_restart_and_current_revocation(preparation_fixture,tmp_path):
    f=preparation_fixture;p=filled(f);before=snapshot(f[1])
    for label in ('first','restart'):
        with ordinary_process(f,tmp_path/label) as api,sync_playwright() as pw:
            b,page=browser_page(pw);seen=[];page.on('request',lambda r:seen.append(r.method))
            open_record(page,api,f,p);page.locator('#formal-preparation-check').click()
            expect(page.locator('#formal-preparation-status')).to_contain_text('正式来源入口当前不可用')
            expect(page.locator('#formal-preparation-result')).to_contain_text('尚缺产品实现')
            expect(page.locator('#formal-preparation-result')).to_contain_text('尚缺外部输入')
            expect(page.locator('#formal-preparation-result')).to_contain_text('不代表真实来源验收')
            expect(page.locator('#prep-detail')).to_be_hidden()
            assert all(method=='GET' for method in seen) and snapshot(f[1])==before
            page.screenshot(path=str(tmp_path/(label+'-formal-closed.png')),full_page=True)
            if label=='restart':
                with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
                after=snapshot(f[1]);page.locator('#formal-preparation-check').click()
                expect(page.locator('#formal-preparation-result')).to_be_empty()
                expect(page.locator('#formal-preparation-status')).not_to_contain_text('正在')
                assert snapshot(f[1])==after
            b.close()


@pytest.mark.parametrize('late_status',[200,403])
def test_late_formal_read_after_identity_aba_cannot_replace_current_condition_report(preparation_fixture,tmp_path,late_status):
    f=preparation_fixture;before=snapshot(f[1])
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        b,page=browser_page(pw);pending=[];seen=[];page.on('request',lambda r:seen.append(r.method))
        def hold(route):
            if pending:route.continue_();return
            pending.append((route,route.fetch()))
        page.route('**/api/formal-preparations/entry-status',hold)
        page.goto(str(api.base_url));page.locator('#token').fill(f[2]['fixture-a']);page.locator('#formal-preparation-check').click()
        until=time.monotonic()+5
        while not pending and time.monotonic()<until:page.wait_for_timeout(20)
        assert pending
        page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').fill(f[2]['fixture-a'])
        page.locator('#formal-preparation-check').click()
        expect(page.locator('#formal-preparation-status')).to_contain_text('未提供已有正式来源的绑定配置')
        route,response=pending[0]
        if late_status==200:
            # Client-only response damage makes a stale overwrite observable;
            # actual server request was a real200 closed-condition response.
            body=response.json();body['reason']='FORMAL_SOURCE_TYPE_REFUSED';route.fulfill(status=200,json=body)
        else:route.fulfill(status=403,json={'detail':'record unavailable or authorization denied'})
        page.wait_for_timeout(150)
        expect(page.locator('#formal-preparation-status')).to_contain_text('未提供已有正式来源的绑定配置')
        expect(page.locator('#formal-preparation-result')).to_contain_text('尚缺产品实现')
        assert all(method=='GET' for method in seen) and snapshot(f[1])==before;b.close()
