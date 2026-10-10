"""Real localhost HTTP, Chromium cold read recovery and late response privacy."""
from contextlib import contextmanager
import socket
import threading
import time
import json
from pathlib import Path

import uvicorn
import pytest
from playwright.sync_api import sync_playwright
from parkweave.template_isolated_app import create_isolated_template_app
from test_template_upgrade import upgrade_case, link_fixture, receipt_fixture, preparation_fixture, instance, publication, snapshot


@contextmanager
def server(u):
    listener=socket.socket();listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
    api=uvicorn.Server(uvicorn.Config(create_isolated_template_app(u['f'][0],u['engine'],u['consumer'],u['checker']),host='127.0.0.1',port=port,log_level='warning',access_log=False))
    thread=threading.Thread(target=api.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    try:
        end=time.monotonic()+10
        while not api.started and thread.is_alive() and time.monotonic()<end:time.sleep(.02)
        assert api.started;yield 'http://127.0.0.1:'+str(port)
    finally:
        api.should_exit=True;thread.join(10);listener.close();assert not thread.is_alive()


def open_page(page,url,u,row):
    page.goto(url+'/template-upgrade');page.locator('#token').fill(u['f'][2]['fixture-a']);page.locator('#instance').fill(row['instance_id'])
    page.locator('#catalog').click();page.wait_for_function('()=>document.querySelector("#target").options.length===1')
    page.locator('#check').click();page.wait_for_function('()=>inspection!==null&&!busy')


@pytest.mark.parametrize('width',[320,1200])
def test_committed_lost_choice_reply_cold_get_recovery_preserves_all_business(upgrade_case,width):
    u=upgrade_case;row,_=instance(u);target=publication(u);before=snapshot(u);requests=[]
    with server(u) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page(viewport={'width':width,'height':900})
        try:
            open_page(page,base,u,row);assert '兼容' in page.locator('#result').inner_text()
            page.on('request',lambda r:requests.append((r.method,r.url)))
            def lose(route):
                response=route.fetch();assert response.status==200;route.abort('failed')
            page.route('**/api/template-upgrade/*/choices',lose)
            page.locator('#reason').fill('Explicit synthetic choice');page.locator('[data-choice="KEEP_CURRENT"]').click()
            page.wait_for_function('()=>pending!==null&&!busy&&document.querySelector("#error").textContent.includes("未知")')
            key=page.locator('#key').input_value();assert key
            page.locator('#recover').click();page.wait_for_function('()=>pending===null&&!busy')
            assert 'COMMITTED' in page.locator('#receipt').inner_text()
            assert sum(m=='POST' and url.endswith('/choices') for m,url in requests)==1
            page.reload();assert page.locator('#token').input_value()=='' and page.locator('#receipt').inner_text()==''
            page.locator('#token').fill(u['f'][2]['fixture-a']);page.locator('#instance').fill(row['instance_id']);page.locator('#key').fill(key)
            page.locator('#recover').click();page.wait_for_function('()=>document.querySelector("#receipt").textContent.includes("COMMITTED")')
            assert page.locator('[data-choice="KEEP_CURRENT"]').is_disabled()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            assert snapshot(u)==before
            out=Path('.runtime/template-upgrade/browser');out.mkdir(parents=True,exist_ok=True)
            (out/f'cold-{width}.json').write_text(json.dumps(dict(actual_loopback_http=True,chromium=True,width=width,choice_posts=1,read_only_cold_recovery=True,old_release=row['binding']['release_id'],target_release=target['release_id'],products_and_original_consumer_unchanged=True))+'\n')
        finally:browser.close()


def test_late_old_scope_check_cannot_fill_new_context_or_clear_current_inspection(upgrade_case):
    u=upgrade_case;row,_=instance(u);publication(u);before=snapshot(u)
    with server(u) as base,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page()
        try:
            page.goto(base+'/template-upgrade');page.locator('#token').fill(u['f'][2]['fixture-a']);page.locator('#instance').fill(row['instance_id']);page.locator('#catalog').click();page.wait_for_function('()=>document.querySelector("#target").options.length===1')
            page.evaluate('''()=>{const original=fetch;window.delayedResolve=null;window.oldArrived=false;window.fetch=async(...args)=>{const response=await original(...args);if(String(args[0]).includes('/check?')){window.oldArrived=true;await new Promise(resolve=>window.delayedResolve=resolve);}return response;};}''')
            page.locator('#check').click();page.wait_for_function('()=>window.oldArrived')
            page.locator('#token').fill(u['f'][2]['fixture-b']);page.evaluate('()=>window.delayedResolve()');page.wait_for_timeout(150)
            assert page.locator('#result').inner_text()=='' and page.locator('#receipt').inner_text()==''
            assert page.locator('[data-choice="KEEP_CURRENT"]').is_disabled() and page.evaluate('inspection===null&&pending===null')
            assert snapshot(u)==before
        finally:browser.close()
