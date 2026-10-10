"""Actual Chromium on the original preparation page, HTTP and isolated PG."""
from pathlib import Path
import json
import time
import pytest
from playwright.sync_api import sync_playwright
from test_handling_deadline import deadline_http,preparation_fixture,filled,create,attach,snapshot,get

OUT=Path('.runtime/handling-deadline/browser')

def page_for(browser,f,actor='fixture-a',width=1200):
    context=browser.new_context(viewport={'width':width,'height':1000});page=context.new_page();page.goto(str(f[3].base_url))
    assert page.locator('#token').input_value()==''
    page.locator('#token').fill(f[2][actor]);page.locator('#token').dispatch_event('change');page.locator('[data-tab="collaboration"]').click()
    return context,page

def open_prep(page,p,role='enterprise_operator'):
    page.evaluate('(x)=>loadPreparation(x.id,{role:x.role})',dict(id=p['preparation_id'],role=role))
    page.wait_for_function('()=>preparationView!==null')

def read(page,state):
    page.locator('#handling-deadline-read').click();page.wait_for_function('(state)=>deadlineView?.state===state',arg=state)

def browser_run():return sync_playwright()

@pytest.mark.parametrize('width',[320,1200])
def test_original_page_calendar_and_cold_reauthentication_only_get(deadline_http,width):
    f,requests=deadline_http;p=filled(f);attach(f,p);before=snapshot(f);initial=get(f,p).json();posts=[]
    with browser_run() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=page_for(browser,f,width=width)
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
        open_prep(page,p);read(page,'SYNTHETIC_CALCULATED')
        assert '正式办理期限仍待确认' in page.locator('#handling-deadline-status').inner_text()
        assert initial['deadline_utc'] in page.locator('#handling-deadline-result').inner_text()
        assert 'PRIVATE_DEADLINE_SOURCE' not in page.content() and page.evaluate('globalThis.DEADLINE_BAD!==true')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        OUT.mkdir(parents=True,exist_ok=True);page.screenshot(path=str(OUT/('calendar-'+str(width)+'.png')),full_page=True)
        page.reload();assert page.locator('#token').input_value()=='' and page.evaluate('localStorage.length')==0
        assert page.evaluate('deadlineView===null');page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('change')
        page.locator('[data-tab="collaboration"]').click();open_prep(page,p);read(page,'SYNTHETIC_CALCULATED')
        assert page.evaluate('deadlineView.deadline_utc')==initial['deadline_utc'] and not errors and not posts
        ctx.close();browser.close()
    assert snapshot(f)==before and all(r['method']=='GET' for r in requests if r['path'].endswith('handling-deadline'))

@pytest.mark.parametrize('actor,role',[('fixture-a','enterprise_operator'),('prep-specialist-fixture-a','park_specialist')])
def test_default_off_unknown_for_original_existing_roles(deadline_http,actor,role):
    f,_=deadline_http;p=filled(f);before=snapshot(f)
    with browser_run() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=page_for(browser,f,actor,width=320)
        open_prep(page,p,role);read(page,'UNKNOWN');assert '待确认' in page.locator('#handling-deadline-status').inner_text()
        assert page.locator('#handling-deadline-result').locator('button').count()==0 and page.evaluate('localStorage.length')==0
        ctx.close();browser.close()
    assert snapshot(f)==before

@pytest.mark.parametrize('switch',['identity','case'])
def test_late_old_deadline_cannot_publish_into_new_identity_or_case(deadline_http,switch):
    f,_=deadline_http;p=filled(f);other,_,_=create(f);attach(f,p);held=[];before=snapshot(f)
    with browser_run() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=page_for(browser,f)
        open_prep(page,p)
        page.route('**/handling-deadline',lambda route:held.append((route,route.fetch())))
        page.locator('#handling-deadline-read').click();page.wait_for_function('()=>document.querySelector("#handling-deadline-read").disabled')
        limit=time.monotonic()+3
        while not held and time.monotonic()<limit:page.wait_for_timeout(20)
        assert len(held)==1
        if switch=='identity':page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('change')
        else:open_prep(page,other)
        route,response=held[0];route.fulfill(response=response);page.wait_for_timeout(150)
        assert page.evaluate('deadlineView===null') and page.locator('#handling-deadline-result').inner_text()==''
        assert page.locator('#handling-deadline-status').inner_text()=='办理期限待确认。'
        ctx.close();browser.close()
    assert snapshot(f)==before

def test_actual_read_revocation_clears_private_page_and_deadline(deadline_http):
    f,_=deadline_http;p=filled(f);attach(f,p)
    with browser_run() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=page_for(browser,f)
        open_prep(page,p);read(page,'SYNTHETIC_CALCULATED')
        with f[1].connect() as c:
            f[1].lock_principal(c,'fixture-a',exclusive=True)
            c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
        before=snapshot(f)
        with page.expect_response(lambda r:r.url.endswith('handling-deadline')) as response:page.locator('#handling-deadline-read').click()
        assert response.value.status==403;page.wait_for_function('()=>deadlineView===null&&preparationView===null')
        assert page.locator('#handling-deadline-result').inner_text()=='' and page.locator('#prep-detail').is_hidden()
        assert snapshot(f)==before and page.evaluate('localStorage.length')==0
        ctx.close();browser.close()

def test_mismatched_actual_response_view_unknown_no_clock_write(deadline_http):
    f,_=deadline_http;p=filled(f);attach(f,p);before=snapshot(f)
    with browser_run() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=page_for(browser,f);open_prep(page,p)
        def damaged(route):
            response=route.fetch();raw=response.json();raw['preparation_revision']+=1
            route.fulfill(response=response,json=raw)
        page.route('**/handling-deadline',damaged);page.locator('#handling-deadline-read').click()
        page.wait_for_function('()=>document.querySelector("#handling-deadline-error").textContent!==""')
        assert page.evaluate('deadlineView===null') and page.locator('#handling-deadline-result').inner_text()=='' and snapshot(f)==before
        ctx.close();browser.close()
