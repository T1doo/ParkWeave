"""Chromium -> ordinary subprocess -> owned PG; only explicit synthetic initial authority."""
import json
from contextlib import ExitStack
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from playwright.sync_api import sync_playwright,expect

from test_local_synthetic_demo import demo_inputs,prepared,preparation_fixture,receipt_fixture
from test_local_synthetic_demo_browser import ordinary_demo
from test_demo_original_page_intake_browser import login
from test_service_dispatches import offer
from service_release_acceptance_support import authority_snapshot,case_history


def open_dispatch(page):
    page.locator('[data-tab="collaboration"]').click();page.locator('#dispatch-list').click()
    item=page.locator('#dispatch-items button').filter(has_text='SYNTHETIC资料准备')
    expect(item).to_have_count(1,timeout=15000);item.click()
    expect(page.locator('#dispatch-detail')).to_be_visible(timeout=15000)


@pytest.mark.parametrize('mode',['committed_reply_lost','not_observed_then_late','revoked','restart','bad_current'])
def test_ordinary_accept_lost_reply_cold_recovery_is_get_only(demo_inputs,tmp_path,mode):
    f,_,pack,_=demo_inputs;parent=prepared(f)
    # Explicit existing synthetic assignment BEFORE starting the ordinary factory.
    f[1].assign_status(pack['roles']['service_executor'],UUID(parent['run_id']),active=True)
    offered=offer(f,parent)[0];assert offered.status_code==201;row=offered.json()
    baseline=authority_snapshot(f[1]);traffic=[];errors=[];saved=[]
    with ExitStack() as servers,sync_playwright() as pw:
        api=servers.enter_context(ordinary_demo(f,tmp_path/'ordinary'))
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        context=browser.new_context(viewport=dict(width=320,height=1000));page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:traffic.append(dict(method=r.method,path=urlsplit(r.url).path)))
        login(page,api,f,'executor-a');open_dispatch(page)
        def lost(route):
            saved.append(dict(headers=route.request.all_headers(),body=route.request.post_data_json,url=route.request.url))
            if mode!='not_observed_then_late':assert route.fetch().status==200
            route.abort('failed')
        page.route('**/api/service-dispatches/*/commands',lost)
        page.locator('#dispatch-decision-reason').fill('SYNTHETIC private reason never persisted')
        page.locator('#dispatch-accept').click()
        expect(page.locator('#dispatch-accept-recover')).to_be_visible(timeout=15000)
        page.wait_for_function('()=>!dispatchAcceptBusy&&!activeEntryWriteFlow')
        assert len(saved)==1
        handles=page.evaluate('()=>Object.entries(localStorage).filter(([n])=>n.startsWith(dispatchAcceptStorage))')
        assert len(handles)==1 and 'reason' not in handles[0][1] and f[2]['executor-a'] not in handles[0][1]
        assert all(not r['path'].endswith('/accept-recovery') for r in traffic)
        def refuse_other_write():
            # The owner could create a Run. The opaque unresolved lease must
            # survive identity/navigation before the original view is hydrated.
            marker=len(traffic)
            with f[1].connect() as c:count=c.execute('SELECT count(*) n FROM runs').fetchone()['n']
            page.locator('#token').fill(f[2]['fixture-a'])
            page.locator('[data-tab="service"]').click()
            page.locator('#goal').fill('SYNTHETIC must not create while original accept is unknown')
            page.locator('#intake button').click()
            expect(page.locator('#result')).to_contain_text('原接单结果待只读核对')
            assert not any(r['method']=='POST' for r in traffic[marker:])
            with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==count
        page.locator('#dispatch-list').click()  # Clears in-memory dispatch presentation.
        refuse_other_write()
        if mode=='restart':
            port=api.base_url.port;servers.close()
            api=servers.enter_context(ordinary_demo(f,tmp_path/'restart',port=port))
        # Reload erases all JavaScript state. Ordinary list/read uses persisted opaque key.
        page.reload();refuse_other_write()
        page.locator('#token').fill(f[2]['executor-a']);open_dispatch(page)
        marker=len(traffic);before=case_history(f[1],parent['preparation_id'])
        if mode=='revoked':
            with f[1].connect() as c:
                f[1].lock_principal(c,'executor-a',exclusive=True)
                c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
        page.locator('#dispatch-accept-recover').click()
        if mode=='revoked':
            expect(page.locator('#dispatch-detail')).to_be_hidden(timeout=15000)
            assert page.evaluate('dispatchView===null&&dispatchContext===null')
            assert page.evaluate('(name)=>localStorage.getItem(name)',handles[0][0])==handles[0][1]
        else:
            page.wait_for_function('()=>!dispatchAcceptBusy')
            if mode=='not_observed_then_late':
                assert page.evaluate('dispatchAcceptProof===null')
                expect(page.locator('#dispatch-accept')).to_be_disabled()
                assert page.evaluate('(name)=>localStorage.getItem(name)',handles[0][0])==handles[0][1]
                # Only the captured original request arrives; recovery never sends it.
                r=api.post(saved[0]['url'],headers=saved[0]['headers'],json=saved[0]['body'])
                assert r.status_code==200,r.text
                before=case_history(f[1],parent['preparation_id'])
                page.locator('#dispatch-accept-recover').click()
            expect(page.locator('#dispatch-accept-release')).to_be_visible(timeout=15000)
            if mode=='bad_current':
                # The real server response is obtained, then this fault harness
                # corrupts one field. Never claim the backend produced it.
                path='**/api/service-dispatches/'+row['dispatch_id']
                def corrupt(route):
                    reply=route.fetch();assert reply.status==200
                    data=reply.json();data['history']=None
                    route.fulfill(response=reply,json=data)
                page.route(path,corrupt)
                page.locator('#dispatch-accept-release').click()
                expect(page.locator('#dispatch-error')).to_contain_text('当前分派与原接单证明不匹配',timeout=15000)
                assert page.evaluate('(name)=>localStorage.getItem(name)',handles[0][0])==handles[0][1]
                page.unroute(path,corrupt)
            page.locator('#dispatch-accept-release').click()
            expect(page.locator('#dispatch-accept-recover')).to_be_hidden(timeout=15000)
            expect(page.locator('#dispatch-summary')).to_contain_text('执行者已接单')
            assert page.evaluate('(name)=>localStorage.getItem(name)',handles[0][0]) is None
        assert case_history(f[1],parent['preparation_id'])==before
        assert traffic[marker:] and {r['method'] for r in traffic[marker:]}=={'GET'}
        assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(tmp_path/(mode+'.png')))
        (tmp_path/'proof.json').write_text(json.dumps(dict(mode=mode,ordinary_subprocess=True,
            actual_chromium=True,cold_reload=True,ordinary_API_process_restart=mode=='restart',recovery_requests=traffic[marker:],
            original_POST_count=len(saved),no_automatic_P3=True,Windows='NOT_RUN'),indent=2)+'\n')
        context.close();browser.close()
    if mode!='revoked':assert authority_snapshot(f[1])==baseline
