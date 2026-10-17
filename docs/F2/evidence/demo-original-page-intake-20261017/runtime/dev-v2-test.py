"""Existing ordinary page intake, no API-prepared Run/materials or new product UI.

Only identities/catalog/resources are explicit synthetic installation fixtures.
All Case/preparation/intent/material/review/confirm/selection/resource writes are
actual DOM submissions. The normal worker runs separately. No Run assignment is
created, so original P3 must stay blocked.
"""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
import json,os,subprocess,sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright,expect

from parkweave.process_env import minimal_environment
from scripts.linux_fixture_server import stop_children
from test_local_synthetic_demo import demo_inputs,preparation_fixture,receipt_fixture,GOALS
from test_local_synthetic_demo_browser import ordinary_demo
from service_release_acceptance_support import authority_snapshot,case_history


@contextmanager
def ordinary_worker(f,directory):
    directory.mkdir(parents=True,exist_ok=True)
    root=Path(__file__).resolve().parents[1]
    env=minimal_environment(os.environ,PYTHONPATH=str(root/'src'),PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_MODE='LOCAL',PYTHONDONTWRITEBYTECODE='1')
    with (directory/'ordinary-worker.log').open('w') as log:
        child=subprocess.Popen([sys.executable,'-B','-m','parkweave.worker'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:yield child
        finally:stop_children([child])


def login(page,api,f,actor):
    page.goto(str(api.base_url))
    page.locator('#token').fill(f[2][actor])


def open_from_list(page,goal):
    page.locator('[data-tab="collaboration"]').click()
    page.locator('#prep-list').click()
    item=page.locator('#prep-items button').filter(has_text=goal)
    expect(item).to_have_count(1,timeout=15000);item.click()
    expect(page.locator('#prep-detail')).to_be_visible(timeout=15000)


def verify(page,adapter):
    page.locator('#service-plan-prepare').click()
    card=page.locator('[data-service-adapter="'+adapter+'"]')
    button=card.locator('[data-service-action="VERIFY"]')
    expect(button).to_be_enabled(timeout=15000)
    page.locator('#service-plan-reason').fill('SYNTHETIC explicit DOM checks '+adapter)
    button.click()
    page.wait_for_function('(id)=>servicePlanView?.steps.find(s=>s.adapter_id===id)?.state==="VERIFIED"&&!servicePlanPending',arg=adapter)


@pytest.mark.parametrize('width',[1200,320])
def test_existing_ordinary_page_new_request_materials_to_selection_without_api_initial_data(demo_inputs,tmp_path,width):
    f,cfg,pack,journal=demo_inputs
    baseline=authority_snapshot(f[1])
    with f[1].connect() as c:
        assert all(c.execute('SELECT count(*) n FROM '+t).fetchone()['n']==0 for t in
            ('runs','cases','preparations','preparation_evidence','preparation_events','run_assignments'))
    goal='SYNTHETIC new ordinary DOM request '+str(width)
    materials={'need_summary':'SYNTHETIC fresh DOM need '+str(width),
               'material_outline':'SYNTHETIC fresh DOM outline '+str(width)+' <script>window.demoInjection=true</script>'}
    traffic=[];errors=[];contexts=[]
    with ordinary_demo(f,tmp_path/'first') as api,ordinary_worker(f,tmp_path/'worker') as worker,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        def role(actor):
            context=browser.new_context(viewport=dict(width=width,height=1000));contexts.append(context);page=context.new_page()
            page.on('pageerror',lambda error:errors.append(str(error)))
            def observed(response):
                request=response.request
                if request.method=='POST':
                    traffic.append(dict(actor=actor,method=request.method,path=urlsplit(request.url).path,status=response.status,body=request.post_data_json))
            page.on('response',observed);login(page,api,f,actor);return page
        try:
            owner=role('fixture-a')
            owner.locator('#prep-catalog').click();expect(owner.locator('#prep-create')).to_be_visible()
            owner.locator('#prep-reviewer').select_option(pack['roles']['park_specialist'])
            owner.locator('#prep-goal').fill(goal);owner.locator('#prep-create button').click()
            expect(owner.locator('#prep-summary')).to_contain_text(goal,timeout=20000)
            assert worker.poll() is None
            parent_id=owner.evaluate('preparationId')  # Read-only observation, never JS navigation.
            assert parent_id
            # The original request editor is reachable before any old plan exists.
            owner.locator('#plan-prepare').click();expect(owner.locator('#request-intent-form')).to_be_visible()
            owner.locator('#request-current').fill(goal)
            owner.locator('#request-local-goal').uncheck();owner.locator('#plan-required-goals').fill('\n'.join(GOALS))
            owner.locator('#request-save').click()
            expect(owner.locator('#request-intent-status')).to_contain_text('已保存诉求/目标版本',timeout=15000)
            owner.locator('#plan-materials').click();expect(owner.locator('#prep-detail')).to_be_visible()
            for slot,text in materials.items():
                owner.locator('#prep-slot').select_option(slot);owner.locator('#prep-text').fill(text)
                owner.locator('#prep-source-kind').select_option('USER_STATEMENT')
                owner.locator('#prep-source-label').fill('SYNTHETIC new DOM source '+slot)
                owner.locator('#prep-evidence button').click()
                expect(owner.locator('#prep-materials')).to_contain_text(text,timeout=15000)
                expect(owner.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000)
            assert not owner.evaluate('Boolean(window.demoInjection)')
            reviewer=role(pack['roles']['park_specialist']);open_from_list(reviewer,goal)
            reviewer.locator('#prep-reason').fill('SYNTHETIC mapped specialist independently reviews new two slots')
            reviewer.locator('#prep-review').click();expect(reviewer.locator('#prep-summary')).to_contain_text('待企业确认',timeout=15000)
            owner.locator('#prep-refresh').click();expect(owner.locator('#prep-summary')).to_contain_text('待企业确认',timeout=15000)
            owner.locator('#prep-reason').fill('SYNTHETIC owner independently confirms new reviewed inputs')
            owner.locator('#prep-confirm').click();expect(owner.locator('#prep-summary')).to_contain_text('本地资料准备已确认',timeout=15000)
            owner.locator('#service-plan-prepare').click();expect(owner.locator('#service-selection-read')).to_be_visible()
            owner.locator('#service-selection-read').click();expect(owner.locator('#service-selection-catalog')).to_contain_text('LOCAL_SYNTHETIC_DEMO',timeout=15000)
            catalog=owner.evaluate('serviceSelectionCatalog')
            assert catalog['selection_oracle']['state']=='UNIQUE'
            assert all(i['park_id']==pack['park_id'] for i in catalog['catalog_snapshot']['instances'])
            assert set().union(*(set(i['resources'].values()) for i in catalog['catalog_snapshot']['instances']))==set(pack['resources'].values())
            owner.locator('#service-selection-generate').click()
            owner.wait_for_function('()=>serviceSelectionView!==null&&!serviceSelectionBusy')
            assert owner.evaluate('serviceSelectionView.producer.mode')=='NO_MODEL'
            owner.locator('#service-selection-confirm').check()
            owner.locator('#service-plan-reason').fill('SYNTHETIC explicit new DOM selection adoption')
            owner.locator('#service-plan-adopt').click();owner.wait_for_function('()=>!!servicePlanView?.plan_id&&!servicePlanPending')
            verify(owner,'P1')
            # Existing resource workspace uses the already configured resource IDs.
            owner.locator('[data-tab="resource"]').click();owner.locator('#resource-catalog').click()
            expect(owner.locator('#resource-form')).to_be_visible()
            starts=datetime.now(timezone.utc)+timedelta(hours=1);ends=starts+timedelta(hours=1)
            for resource in pack['resources'].values():
                owner.locator('#resource-select').select_option(resource)
                owner.locator('#resource-start').fill(starts.strftime('%Y-%m-%dT%H:%M'))
                owner.locator('#resource-end').fill(ends.strftime('%Y-%m-%dT%H:%M'))
                owner.locator('#resource-quantity').fill('1');owner.locator('#resource-ttl').fill('300')
                owner.locator('#resource-purpose').fill('SYNTHETIC new DOM selected Case resource')
                owner.locator('#resource-preview').click();expect(owner.locator('#resource-hold')).to_be_enabled()
                owner.locator('#resource-hold').click();expect(owner.locator('#resource-preview-result')).to_contain_text('占位已核对',timeout=15000)
            owner.locator('#resource-mine').click();checks=owner.locator('[data-combination-hold]');expect(checks).to_have_count(2)
            for check in checks.all():check.check()
            owner.locator('#combination-confirm').click();expect(owner.locator('#combination-feedback')).to_contain_text('确认',timeout=15000)
            open_from_list(owner,goal);owner.locator('#case-resource-load').click()
            expect(owner.locator('#case-resource-form')).to_be_visible();owner.locator('#case-resource-reason').fill('SYNTHETIC explicit new DOM Case resource association')
            owner.locator('#case-resource-form button').click();expect(owner.locator('#case-resource-summary')).to_contain_text('当前资料版本与资源关联有效',timeout=15000)
            verify(owner,'P2')
            # No test or loader assigns this newly created Run. Original page refuses.
            open_from_list(reviewer,goal);reviewer.locator('#dispatch-prepare').click()
            expect(reviewer.locator('#dispatch-current')).to_contain_text('此Run当前没有可分派的既有合法执行者',timeout=15000)
            expect(reviewer.locator('#dispatch-offer')).to_be_hidden()
            with f[1].connect() as c:
                parent=c.execute('SELECT * FROM preparations WHERE id=%s',(parent_id,)).fetchone()
                evidence=c.execute('SELECT slot,text FROM preparation_evidence WHERE preparation_id=%s',(parent_id,)).fetchall()
                events=c.execute('SELECT action,payload FROM preparation_events WHERE preparation_id=%s ORDER BY revision',(parent_id,)).fetchall()
                assert dict((e['slot'],e['text']) for e in evidence)==materials
                assert parent['reviewer_id']==pack['roles']['park_specialist'] and parent['namespace']=='SYNTHETIC'
                assert [e['action'] for e in events]==['CREATE','UPDATE_REQUEST','ADD_EVIDENCE','ADD_EVIDENCE','REVIEW','CONFIRM']
                assert not c.execute('SELECT 1 FROM run_assignments WHERE run_id=%s',(parent['run_id'],)).fetchone()
                assert not c.execute('SELECT 1 FROM service_dispatch_offers').fetchone()
            assert authority_snapshot(f[1])==baseline
            assert len([t for t in traffic if t['path']=='/api/runs'])==1
            assert len([t for t in traffic if t['path']=='/api/preparations'])==1
            assert all(t['status']<300 for t in traffic)
            assert not any(t['path'].startswith('/api/service-instance-cold-inputs') for t in traffic)
            owner.locator('#service-plan-read').click();owner.locator('#goal-results-read').click()
            owner.wait_for_function('()=>goalResultView!==null');result=owner.evaluate('goalResultView')
            assert result['state']!='LOCAL_OUTPUTS_VERIFIED' and not result['case_goal_completed']
            assert {r['adapter_id'] for r in result['results'] if r['state']=='LOCAL_OUTPUT_VERIFIED'}=={'P1','P2'}
            owner.locator('#goal-results-source-read').click();expect(owner.locator('#goal-results-source')).to_contain_text('NO_MODEL')
            assert owner.evaluate('document.documentElement.scrollWidth<=innerWidth')
            owner.screenshot(path=str(tmp_path/('existing-dom-'+str(width)+'.png')))
            assert not errors
        finally:
            for context in contexts:context.close()
            browser.close()
    history=case_history(f[1],parent_id)
    with ordinary_demo(f,tmp_path/'restart') as api,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);page=browser.new_page();methods=[]
        page.on('request',lambda req:methods.append(req.method));login(page,api,f,'fixture-a');open_from_list(page,goal)
        page.locator('#service-plan-prepare').click();page.locator('#goal-results-read').click();page.wait_for_function('()=>goalResultView!==null')
        assert page.evaluate('goalResultView')==result and set(methods)=={'GET'}
        browser.close()
    assert case_history(f[1],parent_id)==history and authority_snapshot(f[1])==baseline
    (tmp_path/'actual-existing-dom-proof.json').write_text(json.dumps(dict(scope='EXISTING_ORDINARY_DEMO_DOM_NEW_INTAKE',width=width,
        ordinary_factory=True,separate_normal_worker=True,initial_business_rows=0,business_POSTs=traffic,
        all_initial_materials_created_by_DOM=True,api_business_setup_calls=0,JS_navigation_calls=0,
        reused_original_entry=True,new_product_UI=False,review_then_separate_confirm=True,original_P1_P2_verified=True,
        new_Run_assignment_created=False,P3_missing_existing_executor_blocked=True,runtime_authority_changes=0,
        restart_GET_only=True,real_model_calls=0,Windows='NOT_RUN',formal_AT='NOT_RUN',real_business='NOT_RUN'),indent=2)+'\n')
