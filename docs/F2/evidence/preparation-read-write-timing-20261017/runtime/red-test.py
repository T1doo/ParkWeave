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
            assert posts==[] and [e['action'] for e in events(f,p)]==['CREATE']
            route,response=pending.pop();route.fulfill(response=response)
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
