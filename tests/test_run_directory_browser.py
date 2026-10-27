"""Original page with real PG/configured HTTP; read-only directory privacy races."""
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import subprocess
import sys
from uuid import uuid4
import httpx
import pytest
from playwright.sync_api import sync_playwright
from parkweave.domain import Intake
from normal_recovery_process import child_environment,wait,stop,snapshot


@contextmanager
def original_page(f,tmp_path,width=390):
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    log=(tmp_path/'normal-api-private.log').open('w')
    process=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port)],env=child_environment(PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_MODE='LOCAL'),stdout=log,stderr=log)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=2) as client:
            def ready():
                assert process.poll() is None
                try:return client.get('/health').status_code==200
                except httpx.TransportError:return False
            wait(ready)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            context=browser.new_context(viewport={'width':width,'height':1000});page=context.new_page()
            requests=[];errors=[]
            page.on('request',lambda r:requests.append((r.method,r.url.split(str(port),1)[-1])))
            page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                page.goto(f'http://127.0.0.1:{port}/');page.locator('[data-tab="collaboration"]').click()
                yield page,requests,errors
                assert not errors and all(method=='GET' for method,_ in requests)
            finally:context.close();browser.close()
    finally:stop(process);log.close()


def created(f,user='fixture-a'):
    run=f[0].submit(f[2][user],uuid4().hex,Intake(goal='SYNTHETIC private ordinary goal'))
    f[0].finish(f[0].claim('synthetic-normal-directory'))
    return str(run)


def list_records(page,token):
    page.locator('#token').fill(token);page.locator('#record-directory-read').click()
    wait(lambda:page.locator('#record-directory-items button').count()>0)


@pytest.mark.parametrize('width',[320,390,1200])
def test_directory_pagination_select_original_get_and_private_storage_empty(fixture,tmp_path,width):
    f=fixture;ids=sorted(created(f) for _ in range(21));before=snapshot(f[1])
    with original_page(f,tmp_path,width) as (page,requests,errors):
        page.locator('#record-directory-read').click();assert not any('/api/runs?' in path for _,path in requests)
        list_records(page,f[2]['fixture-a']);assert page.locator('#record-directory-items button').count()==20
        assert ids[0] in page.locator('#record-directory-items').inner_text()
        page.locator('#record-directory-next').click();wait(lambda:page.locator('#record-directory-items button').count()==1)
        assert ids[-1] in page.locator('#record-directory-items').inner_text()
        page.locator('#record-directory-items button').click()
        page.locator('details.engineering-record > summary').click()
        wait(lambda:'LOCAL_CASE_CREATED' in page.locator('#result').inner_text())
        assert json.loads(page.locator('#result').inner_text())['run_id']==ids[-1]
        assert page.locator('#record-directory-items').inner_text()==''
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert page.evaluate('Object.keys(localStorage).length===0&&Object.keys(sessionStorage).length===0')
        page.locator('.collaboration-controls').screenshot(path=str(tmp_path/f'directory-{width}.png'))
        page.reload();assert page.locator('#token').input_value()=='' and page.locator('#record-directory-items').inner_text()==''
        assert snapshot(f[1])==before


@pytest.mark.parametrize('switch',['identity','run','tab'])
def test_late_real_directory_response_never_returns_after_context_switch(fixture,tmp_path,switch):
    f=fixture;run=created(f);before=snapshot(f[1])
    with original_page(f,tmp_path) as (page,requests,errors):
        page.locator('#token').fill(f[2]['fixture-a']);held=[]
        def hold(route):held.append((route,route.fetch()))
        page.route('**/api/runs?limit=20',hold);page.locator('#record-directory-read').click()
        wait(lambda:page.wait_for_timeout(20) or held)
        if switch=='identity':page.locator('#token').fill(f[2]['fixture-b'])
        elif switch=='run':page.locator('#run').fill(str(uuid4()))
        else:page.locator('[data-tab="service"]').click()
        held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(100)
        assert run not in page.locator('#record-directory-items').inner_text()
        assert page.locator('#record-directory-items').inner_text()=='' and snapshot(f[1])==before


def test_current_403_clears_directory_and_run_before_late_old_200(fixture,tmp_path):
    f=fixture;run=created(f)
    with original_page(f,tmp_path) as (page,requests,errors):
        list_records(page,f[2]['fixture-a']);page.locator('#record-directory-items button').click()
        page.locator('details.engineering-record > summary').click()
        wait(lambda:'LOCAL_CASE_CREATED' in page.locator('#result').inner_text())
        held=[]
        def hold(route):
            if held:route.continue_()
            else:held.append((route,route.fetch()))
        page.route('**/api/runs?limit=20',hold);page.locator('#record-directory-read').click();wait(lambda:page.wait_for_timeout(20) or held)
        f[1].revoke_capability('fixture-a','READ');before=snapshot(f[1])
        # Start a new explicit read through the actual handler while the old GET is pending.
        page.evaluate("document.getElementById('record-directory-read').disabled=false")
        page.locator('#record-directory-read').click()
        wait(lambda:'不可读' in page.locator('#result').inner_text())
        held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(100)
        assert page.locator('#record-directory-items').inner_text()==''
        assert 'LOCAL_CASE_CREATED' not in page.locator('#result').inner_text()
        assert run not in page.locator('#result').inner_text() and snapshot(f[1])==before


def test_original_run_403_invalidates_inflight_directory_200(fixture,tmp_path):
    f=fixture;run=created(f)
    with original_page(f,tmp_path) as (page,requests,errors):
        page.locator('#token').fill(f[2]['fixture-a']);page.locator('#run').fill(run)
        page.locator('#refresh').click();page.locator('details.engineering-record > summary').click()
        wait(lambda:'LOCAL_CASE_CREATED' in page.locator('#result').inner_text())
        held=[]
        def hold(route):held.append((route,route.fetch()))
        page.route('**/api/runs?limit=20',hold);page.locator('#record-directory-read').click()
        wait(lambda:page.wait_for_timeout(20) or held)
        f[1].revoke_capability('fixture-a','READ');before=snapshot(f[1])
        page.locator('#refresh').click();wait(lambda:'请求未完成' in page.locator('#result').inner_text())
        held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(100)
        assert page.locator('#record-directory-items').inner_text()==''
        assert page.locator('#record-directory-next').is_hidden()
        assert 'LOCAL_CASE_CREATED' not in page.locator('#result').inner_text() and snapshot(f[1])==before
