"""Chromium -> separate ordinary factory process; explicit synthetic initial data."""
from contextlib import contextmanager
import json,os,socket,subprocess,sys,time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from playwright.sync_api import sync_playwright,expect

from parkweave.process_env import minimal_environment
from scripts.linux_fixture_server import stop_children
from test_local_synthetic_demo import demo_inputs,prepared,preparation_fixture,receipt_fixture
from test_preparation import headers
from test_material_file_import_browser import browser_page,open_record
from service_release_acceptance_support import authority_snapshot,case_history


@contextmanager
def ordinary_demo(f,directory,*,port=None):
    directory.mkdir(parents=True,exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0 if port is None else port));port=sock.getsockname()[1]
    root=Path(__file__).resolve().parents[1]
    env=minimal_environment(os.environ,PYTHONPATH=str(root/'src'),PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_MODE='LOCAL',
        PARKWEAVE_SERVICE_PROFILE=os.environ['PARKWEAVE_SERVICE_PROFILE'],
        PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG=os.environ['PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG'])
    with (directory/'ordinary-api.log').open('w') as log:
        child=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory',
            '--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=15) as api:
                until=time.monotonic()+15
                while time.monotonic()<until:
                    assert child.poll() is None,'ordinary factory exited; see ordinary-api.log'
                    try:
                        response=api.get('/health')
                        if response.status_code==200 and response.json()['process_id']==child.pid:break
                    except httpx.TransportError:pass
                    time.sleep(.05)
                else:pytest.fail('ordinary demo process startup deadline')
                yield api
        finally:stop_children([child])


def test_ordinary_subprocess_chromium_selection_explicit_adoption_and_restart(demo_inputs,tmp_path):
    f,cfg,_,_=demo_inputs;p=prepared(f);baseline=authority_snapshot(f[1]);errors=[];traffic=[]
    with ordinary_demo(f,tmp_path/'first') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw)
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.on('request',lambda r:traffic.append(dict(method=r.method,path=urlsplit(r.url).path)))
        open_record(page,api,f,p)
        page.evaluate('(id)=>loadServiceCasePlan(id)',p['preparation_id'])
        page.wait_for_function('()=>servicePlanView!==null')
        page.locator('#service-selection-read').click()
        page.wait_for_function('()=>serviceSelectionCatalog!==null&&!serviceSelectionBusy')
        expect(page.locator('#service-selection-catalog')).to_contain_text('LOCAL_SYNTHETIC_DEMO')
        expect(page.locator('#service-selection-generate')).to_have_text('生成合成候选（无模型）')
        page.locator('#service-selection-generate').click()
        page.wait_for_function('()=>serviceSelectionView!==null&&!serviceSelectionBusy')
        assert page.evaluate('serviceSelectionView.producer.mode')=='NO_MODEL'
        assert page.evaluate('serviceSelectionHandles().length')==0
        page.locator('#service-plan-reason').fill('SYNTHETIC explicit ordinary demo adoption')
        page.locator('#service-plan-adopt').click()
        assert page.evaluate('servicePlanView.plan_id') is None
        page.locator('#service-selection-confirm').check();page.locator('#service-plan-adopt').click()
        page.wait_for_function('()=>servicePlanView?.plan_id!==null&&!servicePlanPending')
        page.locator('#goal-results-read').click();page.wait_for_function('()=>goalResultView!==null')
        page.locator('#goal-results-source-read').click()
        expect(page.locator('#goal-results-source')).to_contain_text('NO_MODEL')
        for width in (1200,390,320):
            page.set_viewport_size(dict(width=width,height=1000))
            page.locator('#goal-results-source').scroll_into_view_if_needed()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(tmp_path/f'demo-selected-{width}.png'))
        result=page.evaluate('goalResultView');assert not result['case_goal_completed']
        assert not errors;context.close();browser.close()
    before=case_history(f[1],p['preparation_id'])
    with ordinary_demo(f,tmp_path/'restart') as api,sync_playwright() as pw:
        browser,context,page=browser_page(pw);methods=[]
        page.on('request',lambda r:methods.append(r.method));open_record(page,api,f,p)
        page.evaluate('(id)=>loadServiceCasePlan(id)',p['preparation_id']);page.wait_for_function('()=>!!servicePlanView?.plan_id')
        page.locator('#goal-results-read').click();page.wait_for_function('()=>goalResultView!==null')
        assert page.evaluate('goalResultView')==result and set(methods)=={'GET'}
        assert case_history(f[1],p['preparation_id'])==before
        context.close();browser.close()
    assert authority_snapshot(f[1])==baseline
    posts=[r for r in traffic if r['method']=='POST']
    assert len(posts)==2 and posts[0]['path'].endswith('/service-selections') and posts[1]['path'].endswith('/service-case-plan')
    (tmp_path/'browser-proof.json').write_text(json.dumps(dict(ordinary_factory_subprocess=True,actual_chromium=True,
        source='SYNTHETIC',mode='NO_MODEL',posts=posts,api_prepared_initial_materials=True,explicit_adoption=True,
        startup_authority_changes=0,restart_get_only=True,widths=[1200,390,320],real_model_calls=0,
        full_business_chain='separate API test; this browser test covers selection/adoption/readback',Windows='NOT_RUN'),indent=2)+'\n')
