"""Actual Chromium -> ordinary configured_app subprocess -> owned synthetic PG."""
import json
from contextlib import ExitStack
from urllib.parse import urlsplit
from uuid import UUID
import pytest
from playwright.sync_api import sync_playwright,expect
from test_local_synthetic_demo import demo_inputs,prepared,preparation_fixture,receipt_fixture
from test_local_synthetic_demo_browser import ordinary_demo
from test_demo_original_page_intake_browser import login
from test_executor_receipts import create
from service_release_acceptance_support import authority_snapshot,case_history


def open_receipt(page):
    page.locator('[data-tab="collaboration"]').click();page.locator('#receipt-list').click()
    item=page.locator('#receipt-items button').filter(has_text='SYNTHETIC资料准备')
    expect(item).to_have_count(1,timeout=15000);item.click()
    expect(page.locator('#receipt-detail')).to_be_visible(timeout=15000)


@pytest.mark.parametrize('mode',['committed_reply_lost','not_observed_then_late','revoked','restart','bad_current','success'])
def test_ordinary_manual_submit_cold_recovery_never_reposts(demo_inputs,tmp_path,mode):
    f,_,pack,_=demo_inputs;parent=prepared(f)
    # Explicit owned synthetic authority/record initialization before normal startup.
    f[1].assign_status(pack['roles']['service_executor'],UUID(parent['run_id']),active=True)
    created=create(f,parent)[0];assert created.status_code==201,created.text
    row=created.json();baseline=authority_snapshot(f[1]);traffic=[];errors=[];saved=[]
    with ExitStack() as servers,sync_playwright() as pw:
        api=servers.enter_context(ordinary_demo(f,tmp_path/'ordinary'))
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        context=browser.new_context(viewport=dict(width=320,height=1000));page=context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:traffic.append(dict(method=r.method,path=urlsplit(r.url).path)))
        login(page,api,f,'executor-a');open_receipt(page)
        def lost(route):
            saved.append(dict(headers=route.request.all_headers(),body=route.request.post_data_json,url=route.request.url))
            if mode!='not_observed_then_late':assert route.fetch().status==200
            route.abort('failed')
        if mode!='success':page.route('**/api/executor-receipts/*/commands',lost)
        page.locator('#receipt-text').fill('SYNTHETIC private original manual receipt')
        page.locator('#receipt-source').fill('SYNTHETIC private original log v1')
        page.locator('#receipt-submit-button').click()
        if mode=='success':
            expect(page.locator('#receipt-summary')).to_contain_text('回执已记录',timeout=15000)
            page.wait_for_function('()=>!receiptSubmitBusy&&!activeEntryWriteFlow&&!receiptSubmitStoredPending()')
            assert page.evaluate('receiptSubmitHandle===null')
            assert len([r for r in traffic if r['method']=='POST'])==1
            assert any(r['path'].endswith('/submit-recovery') for r in traffic)
            assert page.locator('#receipt-text').input_value()==''
            marker=len(traffic);before=case_history(f[1],parent['preparation_id'])
            page.reload();page.locator('#token').fill(f[2]['executor-a']);open_receipt(page)
        else:
            expect(page.locator('#receipt-submit-recover')).to_be_visible(timeout=15000)
            page.wait_for_function('()=>!receiptSubmitBusy&&!activeEntryWriteFlow')
            assert len(saved)==1
            handles=page.evaluate('()=>Object.entries(localStorage).filter(([n])=>n.startsWith(receiptSubmitStorage))')
            assert len(handles)==1 and 'private' not in handles[0][1] and f[2]['executor-a'] not in handles[0][1]
            assert not any(r['path'].endswith('/submit-recovery') for r in traffic)
            def refuse_another_write():
                marker=len(traffic)
                with f[1].connect() as c:count=c.execute('SELECT count(*) n FROM runs').fetchone()['n']
                page.locator('#token').fill(f[2]['fixture-a']);page.locator('[data-tab="service"]').click()
                page.locator('#goal').fill('SYNTHETIC blocked until manual receipt original is proven')
                page.locator('#intake button').click()
                expect(page.locator('#result')).to_contain_text('原人工回执结果待只读核对')
                assert not any(r['method']=='POST' for r in traffic[marker:])
                with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM runs').fetchone()['n']==count
            page.locator('#receipt-list').click();refuse_another_write()
            if mode=='restart':
                port=api.base_url.port;servers.close();api=servers.enter_context(ordinary_demo(f,tmp_path/'restart',port=port))
            page.reload();refuse_another_write()
            page.locator('#token').fill(f[2]['executor-a']);open_receipt(page)
            marker=len(traffic);before=case_history(f[1],parent['preparation_id'])
            if mode=='revoked':
                with f[1].connect() as c:
                    f[1].lock_principal(c,'executor-a',exclusive=True)
                    c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
            page.locator('#receipt-submit-recover').click()
            if mode=='revoked':
                expect(page.locator('#receipt-detail')).to_be_hidden(timeout=15000)
                assert page.evaluate('receiptView===null&&receiptContext===null')
                assert page.evaluate('(name)=>localStorage.getItem(name)',handles[0][0])==handles[0][1]
            else:
                page.wait_for_function('()=>!receiptSubmitBusy')
                if mode=='not_observed_then_late':
                    assert page.evaluate('receiptSubmitProof===null')
                    expect(page.locator('#receipt-submit-button')).to_be_disabled()
                    assert page.evaluate('(name)=>localStorage.getItem(name)',handles[0][0])==handles[0][1]
                    # Harness delivers the captured original; recovery UI never POSTs it.
                    r=api.post(saved[0]['url'],headers=saved[0]['headers'],json=saved[0]['body']);assert r.status_code==200,r.text
                    before=case_history(f[1],parent['preparation_id']);page.locator('#receipt-submit-recover').click()
                expect(page.locator('#receipt-submit-release')).to_be_visible(timeout=15000)
                if mode=='bad_current':
                    path='**/api/executor-receipts/'+row['step']['id']
                    def corrupt(route):
                        reply=route.fetch();assert reply.status==200
                        data=reply.json();data['receipt_history']=None;route.fulfill(response=reply,json=data)
                    page.route(path,corrupt);page.locator('#receipt-submit-release').click()
                    expect(page.locator('#receipt-error')).to_contain_text('当前回执与原人工提交证明不匹配',timeout=15000)
                    assert page.evaluate('(name)=>localStorage.getItem(name)',handles[0][0])==handles[0][1]
                    page.unroute(path,corrupt)
                page.locator('#receipt-submit-release').click()
                expect(page.locator('#receipt-submit-recover')).to_be_hidden(timeout=15000)
                expect(page.locator('#receipt-summary')).to_contain_text('回执已记录')
                assert page.evaluate('(name)=>localStorage.getItem(name)',handles[0][0]) is None
        assert case_history(f[1],parent['preparation_id'])==before
        assert traffic[marker:] and {r['method'] for r in traffic[marker:]}=={'GET'}
        assert not errors and page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(tmp_path/(mode+'.png')))
        (tmp_path/'proof.json').write_text(json.dumps(dict(mode=mode,ordinary_subprocess=True,actual_chromium=True,
            cold_reload=True,ordinary_API_process_restart=mode=='restart',same_HTTP_port_restart=mode=='restart',
            recovery_requests=traffic[marker:],original_POST_count=1,no_automatic_ACK_or_P4=True,Windows='NOT_RUN'),indent=2)+'\n')
        context.close();browser.close()
    if mode!='revoked':assert authority_snapshot(f[1])==baseline


@pytest.mark.parametrize('mode',['stale_revision_409','body_validation_422','unknown_409','unknown_422','bad_json_422'])
def test_only_complete_original_definitive_rejection_releases_handle(demo_inputs,tmp_path,mode):
    from test_executor_receipts import act
    f,_,pack,_=demo_inputs;parent=prepared(f)
    f[1].assign_status(pack['roles']['service_executor'],UUID(parent['run_id']),active=True)
    row=create(f,parent)[0].json();auth=authority_snapshot(f[1]);traffic=[];responses=[]
    with ordinary_demo(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        context=browser.new_context();page=context.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:traffic.append(dict(method=r.method,path=urlsplit(r.url).path)))
        login(page,api,f,'executor-a');open_receipt(page)
        if mode=='stale_revision_409':
            # Another original authorized synthetic client wins after this page's GET.
            r=act(f,row,'SUBMIT');assert r.status_code==200,r.text
        def fault(route):
            if mode=='body_validation_422':
                body=route.request.post_data_json;body['unknown_field']='SYNTHETIC invalid body'
                reply=route.fetch(post_data=json.dumps(body));assert reply.status==422
                responses.append(dict(status=reply.status,payload=reply.json(),actual_server=True))
                route.fulfill(response=reply)
            elif mode=='bad_json_422':
                responses.append(dict(status=422,actual_server=False));route.fulfill(status=422,body='{',content_type='application/json')
            else:
                status=409 if mode=='unknown_409' else 422
                responses.append(dict(status=status,actual_server=False));route.fulfill(status=status,json={'detail':'SYNTHETIC uncertain transport response'})
        if mode!='stale_revision_409':page.route('**/api/executor-receipts/*/commands',fault)
        before=case_history(f[1],parent['preparation_id'])
        page.locator('#receipt-text').fill('SYNTHETIC retain this draft')
        page.locator('#receipt-source').fill('SYNTHETIC current manual label')
        page.locator('#receipt-submit-button').click()
        page.wait_for_function('()=>!receiptSubmitBusy&&!activeEntryWriteFlow')
        if mode in ('stale_revision_409','body_validation_422'):
            expect(page.locator('#receipt-submit-status')).to_contain_text('服务器已明确拒绝',timeout=15000)
            assert not page.evaluate('receiptSubmitStoredPending()')
            assert page.locator('#receipt-text').input_value()=='SYNTHETIC retain this draft'
            assert page.evaluate('receiptView===null&&receiptContext===null')
            page.locator('#receipt-refresh').click();expect(page.locator('#receipt-detail')).to_be_visible()
            assert page.evaluate('receiptView!==null')
        else:
            expect(page.locator('#receipt-submit-recover')).to_be_visible(timeout=15000)
            assert page.evaluate('receiptSubmitStoredPending()')
            page.locator('#receipt-submit-recover').click();page.wait_for_function('()=>!receiptSubmitBusy')
            assert page.evaluate('receiptSubmitProof===null&&receiptSubmitStoredPending()')
            expect(page.locator('#receipt-submit-button')).to_be_disabled()
        assert len([r for r in traffic if r['method']=='POST'])==1
        assert case_history(f[1],parent['preparation_id'])==before and authority_snapshot(f[1])==auth
        assert not errors
        (tmp_path/'definitive-proof.json').write_text(json.dumps(dict(mode=mode,actual_chromium=True,
            ordinary_subprocess=True,actual_stale_409=mode=='stale_revision_409',
            actual_backend_body_422=mode=='body_validation_422',responses=responses,
            page_requests=traffic,unknown_status_never_released=mode.startswith('unknown') or mode=='bad_json_422'),indent=2)+'\n')
        context.close();browser.close()
