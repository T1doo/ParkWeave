"""Ordinary browser response timing, visible readiness and original key recovery.

Existing synthetic Run/preparation fixtures isolate this UI concern. No Run
assignment, permission provisioning, model, or JS application navigation is used.
"""
import json
import time

import pytest
from playwright.sync_api import sync_playwright, expect

from test_preparation import preparation_fixture, create
from test_material_file_import_browser import browser_page, open_record
from test_native_preparation_entry_browser import ordinary_process


def received(page, pending):
    deadline=time.monotonic()+10
    while not pending and time.monotonic()<deadline:
        page.wait_for_timeout(20)
    assert pending, 'expected intercepted real ordinary HTTP response'


def draft(page,slot,text):
    page.locator('#prep-slot').select_option(slot)
    page.locator('#prep-text').fill(text)
    page.locator('#prep-source-kind').select_option('USER_STATEMENT')
    page.locator('#prep-source-label').fill('SYNTHETIC explicit timing source '+slot)


def events(f,p):
    with f[1].connect() as c:
        return c.execute('SELECT action,payload FROM preparation_events WHERE preparation_id=%s ORDER BY revision',
                         (p['preparation_id'],)).fetchall()


def test_visible_material_submit_waits_for_current_safety_reads(preparation_fixture,tmp_path):
    f=preparation_fixture;p,_,_=create(f);pending=[];posts=[]
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw)
        def hold(route):
            pending.append((route,route.fetch()))
        page.route('**/case-cancellation-reconciliation',hold)
        page.on('request',lambda req:posts.append(req.url) if req.method=='POST' else None)
        page.goto(str(api.base_url)+'?preparation_id='+p['preparation_id'])
        page.locator('#token').fill(f[2]['fixture-a']);page.locator('#existing-preparation-read').click()
        received(page,pending);expect(page.locator('#prep-detail')).to_be_visible()
        try:
            expect(page.locator('#prep-evidence button')).to_be_disabled()
            expect(page.locator('#prep-read-status')).to_contain_text('正在核对')
            draft(page,'need_summary','SYNTHETIC editable draft during read')
            page.locator('#prep-source-label').press('Enter')
            assert posts==[] and [e['action'] for e in events(f,p)]==['CREATE']
            route,response=pending.pop();route.fulfill(response=response)
            page.unroute('**/case-cancellation-reconciliation',hold)
            expect(page.locator('#prep-read-status')).to_contain_text('已就绪')
            draft(page,'need_summary','SYNTHETIC visible ready new input')
            page.locator('#prep-evidence button').click()
            expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件')
            expect(page.locator('#prep-read-status')).to_contain_text('已就绪')
            assert len(posts)==1 and [e['action'] for e in events(f,p)]==['CREATE','ADD_EVIDENCE']
        finally:
            for route,response in pending:route.fulfill(response=response)
            context.close();browser.close()


def test_unrelated_old_plan_read_failure_does_not_poison_material_write(preparation_fixture,tmp_path):
    f=preparation_fixture;p,_,_=create(f);old_read=[];write=[];posts=[]
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw);open_record(page,api,f,p)
        def hold_read(route):old_read.append((route,route.fetch()))
        def hold_first_write(route):
            if write:route.continue_();return
            write.append((route,route.fetch()))
        page.route('**/controlled-plan',hold_read);page.route('**/commands',hold_first_write)
        page.on('request',lambda req:posts.append(req.post_data_json) if req.method=='POST' else None)
        try:
            page.locator('#plan-prepare').click();received(page,old_read)
            draft(page,'need_summary','SYNTHETIC first material with independent delayed plan read')
            page.locator('#prep-evidence button').click();received(page,write)
            assert write[0][1].status==200
            route,_=old_read.pop();route.fulfill(status=500,json={'detail':'SYNTHETIC unrelated old plan read failed'})
            expect(page.locator('#plan-error')).not_to_be_empty()
            # Diagnostic only: never used to unlock or wait for a private flag.
            diagnostic=page.evaluate('()=>({active:!!activeEntryWriteFlow,failed:activeEntryWriteFlow?.failed})')
            (tmp_path/'cross-read-diagnostic.json').write_text(json.dumps(diagnostic)+'\n')
            route,response=write[0];route.fulfill(response=response)
            expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000)
            draft(page,'material_outline','SYNTHETIC second material must remain usable')
            page.locator('#prep-evidence button').click()
            expect(page.locator('#prep-materials')).to_contain_text('SYNTHETIC second material must remain usable',timeout=15000)
            assert len(posts)==2 and [e['action'] for e in events(f,p)]==['CREATE','ADD_EVIDENCE','ADD_EVIDENCE']
            (tmp_path/'ordinary-timing-proof.json').write_text(json.dumps(dict(independent_GET_status=500,
                first_POST_status=200,material_POSTs=2,waits_use_visible_controls_and_HTTP=True,
                diagnostic=diagnostic,JS_navigation=False,assignment_created=False,real_model_calls=0))+'\n')
        finally:
            for route,response in old_read:route.fulfill(response=response)
            context.close();browser.close()


@pytest.mark.parametrize('failure',['conflict','malformed_json'])
def test_current_required_read_failure_keeps_draft_and_requires_visible_refresh(preparation_fixture,tmp_path,failure):
    f=preparation_fixture;p,_,_=create(f)
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw);open_record(page,api,f,p)
        text='SYNTHETIC manual draft retained after '+failure;draft(page,'need_summary',text)
        def fail(route):
            if failure=='conflict':route.fulfill(status=409,json={'detail':'SYNTHETIC current safety read conflict'})
            else:route.fulfill(status=200,content_type='application/json',body='{broken JSON')
        page.route('**/material-corrections',fail);page.locator('#prep-refresh').click()
        expect(page.locator('#prep-read-status')).to_contain_text('读取已失效')
        expect(page.locator('#prep-evidence button')).to_be_disabled();expect(page.locator('#prep-text')).to_have_value(text)
        assert [e['action'] for e in events(f,p)]==['CREATE']
        page.unroute('**/material-corrections',fail);page.locator('#prep-refresh').click()
        expect(page.locator('#prep-read-status')).to_contain_text('已就绪');page.locator('#prep-evidence button').click()
        expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件')
        assert [e['action'] for e in events(f,p)]==['CREATE','ADD_EVIDENCE']
        context.close();browser.close()


@pytest.mark.parametrize('change,late_status',[('identity_aba',403),('navigation',200)])
def test_late_read_after_identity_or_navigation_cannot_clear_new_visible_ready_page(preparation_fixture,tmp_path,change,late_status):
    f=preparation_fixture;p,_,_=create(f);pending=[];seen=[]
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw);open_record(page,api,f,p)
        def intercept(route):
            seen.append(route.request.url)
            if len(seen)==1:pending.append((route,route.fetch()))
            else:route.continue_()
        page.route('**/material-corrections',intercept);page.locator('#prep-refresh').click();received(page,pending)
        expect(page.locator('#prep-read-status')).to_contain_text('正在核对')
        if change=='identity_aba':
            page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').fill(f[2]['fixture-a'])
        else:
            page.locator('[data-tab="resource"]').click();page.locator('[data-tab="service"]').click()
        page.locator('#existing-preparation-id').fill(p['preparation_id']);page.locator('#existing-preparation-read').click()
        expect(page.locator('#prep-read-status')).to_contain_text('已就绪')
        text='SYNTHETIC new visible draft after '+change;draft(page,'need_summary',text)
        route,response=pending.pop()
        if late_status==200:route.fulfill(response=response)
        else:route.fulfill(status=403,json={'detail':'SYNTHETIC old identity response denied'})
        page.wait_for_timeout(100)
        expect(page.locator('#prep-read-status')).to_contain_text('已就绪');expect(page.locator('#prep-text')).to_have_value(text)
        page.locator('#prep-evidence button').click();expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件')
        assert [e['action'] for e in events(f,p)]==['CREATE','ADD_EVIDENCE']
        context.close();browser.close()


@pytest.mark.parametrize('late_status,newer_state',[(200,'READY'),(403,'READY'),(200,'INVALID')])
def test_late_superseded_read_cannot_unlock_or_clear_current_read(preparation_fixture,tmp_path,late_status,newer_state):
    f=preparation_fixture;p,_,_=create(f);pending=[];seen=[]
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw);open_record(page,api,f,p)
        text='SYNTHETIC current same-Case refresh draft';draft(page,'need_summary',text)
        def intercept(route):
            seen.append(route.request.url)
            if len(seen)==1:pending.append((route,route.fetch()))
            elif len(seen)==2 and newer_state=='INVALID':route.fulfill(status=409,json={'detail':'SYNTHETIC newer read incomplete'})
            else:route.continue_()
        page.route('**/material-corrections',intercept);page.locator('#prep-refresh').click();received(page,pending)
        expect(page.locator('#prep-evidence button')).to_be_disabled()
        page.locator('#prep-refresh').click()
        expected='已就绪' if newer_state=='READY' else '读取已失效'
        expect(page.locator('#prep-read-status')).to_contain_text(expected)
        route,response=pending.pop()
        if late_status==200:route.fulfill(response=response)
        else:route.fulfill(status=403,json={'detail':'SYNTHETIC stale identity response denied'})
        page.wait_for_timeout(100)  # Allow the released HTTP callback, never inspect private readiness.
        expect(page.locator('#prep-read-status')).to_contain_text(expected)
        expect(page.locator('#prep-text')).to_have_value(text);expect(page.locator('#prep-detail')).to_be_visible()
        if newer_state=='INVALID':expect(page.locator('#prep-evidence button')).to_be_disabled()
        else:
            page.locator('#prep-evidence button').click();expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件')
        context.close();browser.close()


@pytest.mark.parametrize('fault',['lost_reply','wrong_exact_event'])
def test_own_unknown_write_keeps_original_key_and_requires_explicit_GET_recovery(preparation_fixture,tmp_path,fault):
    f=preparation_fixture;p,_,_=create(f);writes=[];faults=[];recovery=[]
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw);open_record(page,api,f,p)
        def command(route):
            writes.append(dict(key=route.request.headers['idempotency-key'],body=route.request.post_data_json))
            if len(writes)==1 and fault=='lost_reply':
                response=route.fetch();assert response.status==200;faults.append('committed reply lost');route.abort('failed')
            else:route.continue_()
        def read(route):
            if fault=='wrong_exact_event' and writes and not faults:
                response=route.fetch();value=response.json();value['history']=[];faults.append('current revision with missing original event');route.fulfill(response=response,json=value)
            else:route.continue_()
        page.route('**/commands',command);page.route('**/api/preparations/'+p['preparation_id'],read)
        page.on('request',lambda req:recovery.append(req.headers.get('idempotency-key')) if req.method=='GET' and req.url.endswith('/command-recovery') else None)
        original='SYNTHETIC original immutable body '+fault
        draft(page,'need_summary',original);page.locator('#prep-evidence button').click()
        expect(page.locator('#prep-command-retry')).to_be_visible();expect(page.locator('#prep-read-status')).to_contain_text('待核对')
        expect(page.locator('#prep-evidence button')).to_be_disabled();assert len(writes)==1
        expect(page.locator('#prep-text')).to_have_value(original)
        page.locator('#prep-recovery-read').click();expect(page.locator('#prep-recovery-status')).to_contain_text('原材料提交已有保存事件')
        assert len(writes)==1 and recovery==[writes[0]['key']]
        expect(page.locator('#prep-text')).to_have_value(original)
        page.locator('#prep-recovery-release').click();expect(page.locator('#prep-read-status')).to_contain_text('已就绪')
        draft(page,'material_outline','SYNTHETIC separately explicit second input');page.locator('#prep-evidence button').click()
        expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件')
        assert len(writes)==2 and writes[0]['key']!=writes[1]['key']
        assert [e['action'] for e in events(f,p)]==['CREATE','ADD_EVIDENCE','ADD_EVIDENCE']
        context.close();browser.close()


@pytest.mark.parametrize('path,status',[('material-reuse',500),('fact-clarifications',403)])
def test_optional_auxiliary_failure_preserves_authorized_manual_material_flow(preparation_fixture,tmp_path,path,status):
    f=preparation_fixture;p,_,_=create(f);faults=[]
    with ordinary_process(f,tmp_path/'ordinary') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw);open_record(page,api,f,p)
        def fail(route):
            faults.append(status);route.fulfill(status=status,json={'detail':'SYNTHETIC optional field/source unavailable'})
        page.route('**/'+path,fail)
        for slot in ('need_summary','material_outline'):
            draft(page,slot,'SYNTHETIC authorized manual '+slot);page.locator('#prep-evidence button').click()
            expect(page.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件')
            expect(page.locator('#prep-read-status')).to_contain_text('已就绪');expect(page.locator('#prep-detail')).to_be_visible()
        assert faults==[status,status]
        assert [e['action'] for e in events(f,p)]==['CREATE','ADD_EVIDENCE','ADD_EVIDENCE']
        context.close();browser.close()
