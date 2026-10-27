"""Installed Linux Chromium: real HTML -> HTTP/ASGI -> owned PostgreSQL.

Only original cold stages and explicit original GENERATE/ADOPT. No live model,
resource release, production, Windows or formal AT claim.
"""
from copy import deepcopy
import json, os
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4
import pytest
from playwright.sync_api import sync_playwright
from new_case_fixture_support import (new_case_entry, cancel33_case, capability_resource_catalog,
    capability_catalog, preparation_fixture, receipt_fixture)
from conftest import fixture, pg
from test_frontier_real_html import route_helper_artifacts
from test_new_enterprise_local_chain import actual_http, ALL_GOALS
from test_preparation import headers, command as material
from test_cancelled_case_independent_new_case import assert_old_preserved
from test_resource_bundles import states
from service_release_acceptance_support import case_history
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'src/parkweave/web.html').is_file())
OUT=Path(os.environ.get('NEW_CASE_UI_ARTIFACT_ROOT','.runtime/new-case-browser/artifacts'))


def idle(page):
    page.wait_for_function('()=>!coldBusy&&!serviceSelectionBusy&&!servicePlanPending')


@pytest.mark.parametrize('new_case_entry',[False],indirect=True)
def test_actual_chromium_cancelled_case_fresh_input_original_commands_and_explicit_adoption(new_case_entry):
    t=new_case_entry;x=t['x'];f=t['f'];old=x['p'];calls=[];pending={};errors=[]
    proven=dict(original_dom_cancel_and_key_settled=False,navigation_get_only=False,fresh_original_five_stages=False,
        original_new_assignment=False,explicit_generate=False,explicit_adopt=False,
        old_case_history_occupancy_preserved=False)
    with actual_http(t['app']) as (client,python_requests):
        http_f=f[:3]+(client,)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            ctx=browser.new_context();page=ctx.new_page()
            def requested(request):
                row=dict(method=request.method,path=urlsplit(request.url).path,status=None)
                calls.append(row);pending[request]=row
                key=request.header_value('idempotency-key')
                if key:row['request_id']=key
            def responded(response):
                if response.request in pending:pending[response.request]['status']=response.status
            page.on('request',requested);page.on('response',responded)
            page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                page.goto(str(client.base_url).rstrip('/')+'/')
                page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('change')
                page.locator('[data-tab="collaboration"]').click()
                page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',old['preparation_id'])
                page.wait_for_function('()=>!caseCancelBusy&&!caseReconBusy')
                assert page.locator('#case-cancel-new-entry').is_hidden()
                assert page.evaluate('caseCancelView.can_cancel')
                assert page.locator('#case-cancel-submit').is_disabled()
                page.locator('#case-cancel-reason').fill('SYNTHETIC original owner explicitly cancels accepted Case before any receipt; keep history and occupied resources')
                assert page.locator('#case-cancel-submit').is_disabled()
                page.locator('#case-cancel-confirm').check()
                with page.expect_response(lambda r:r.request.method=='POST' and urlsplit(r.url).path.endswith('/case-cancellation-before-receipt') and r.status==200) as cancellation_response:
                    page.locator('#case-cancel-submit').click()
                assert cancellation_response.value.status==200
                page.wait_for_function('()=>!caseCancelBusy&&caseCancelHandles().length===0&&entryWriteRequests.size===0&&!activeEntryWriteFlow&&caseCancelView?.case_state==="CANCELLED"')
                t['original']=case_history(f[1],old['preparation_id'])
                assert t['original']['cases'][0]['state']=='CANCELLED'
                assert not t['original']['service_step_receipts']
                assert len([c for c in calls if c['method']=='POST'])==1
                proven['original_dom_cancel_and_key_settled']=True
                assert page.locator('#case-cancel-new-entry').is_visible()
                assert page.locator('#case-cancel-new-open').is_disabled()
                assert not page.locator('#case-cancel-new-confirm').is_checked()
                before=len(calls);raw_before=page.evaluate('JSON.stringify({...localStorage})')
                page.locator('#case-cancel-new-confirm').check()
                assert page.locator('#case-cancel-new-open').is_enabled()
                with page.expect_response(lambda r:urlsplit(r.url).path.endswith('/case-cancellation-before-receipt') and r.status==200) as fresh_response:
                    page.locator('#case-cancel-new-open').click()
                assert fresh_response.value.status==200
                page.wait_for_function('()=>document.body.dataset.workspace==="service"&&preparationView===null')
                assert calls[before:] and all(c['method']=='GET' for c in calls[before:])
                assert any(c['path'].endswith('/case-cancellation-before-receipt') and c['status']==200 for c in calls[before:])
                assert page.evaluate('JSON.stringify({...localStorage})')==raw_before
                assert page.locator('#cold-directory-read').evaluate('(el)=>el===document.activeElement')
                assert old['case_id'] in page.locator('#cold-status').inner_text()
                for name in ['cold-goal','cold-need','cold-outline','cold-extra','cold-reason']:
                    assert page.locator('#'+name).input_value()==''
                assert_old_preserved(x,t['original']);proven['navigation_get_only']=True
                assert len([c for c in calls if c['method']=='POST'])==1
                page.locator('#cold-directory-read').click();page.wait_for_function('()=>!coldBusy&&coldDirectory!==null')
                chosen=page.evaluate('coldDirectory.instances.find(i=>i.service_id==="synthetic-material-preparation").instance_id')
                page.locator('#cold-instance').select_option(chosen)
                goal='SYNTHETIC ACTUAL_BROWSER_NEW_CASE fresh independent request'
                need='SYNTHETIC ACTUAL_BROWSER_NEW_CASE fresh material need'
                outline='SYNTHETIC ACTUAL_BROWSER_NEW_CASE fresh outline'
                for name,value in [('cold-goal',goal),('cold-need',need),('cold-outline',outline),('cold-reason','SYNTHETIC owner explicitly prepares independent browser new input')]:
                    page.locator('#'+name).fill(value)
                boxes=page.locator('input[data-cold-goal]')
                assert boxes.count()==6
                for box in boxes.all():assert box.is_enabled();box.check()
                requested_goals=page.evaluate('[...document.querySelectorAll("input[data-cold-goal]")].filter(el=>el.checked).map(el=>el.dataset.coldGoal)')
                assert len(requested_goals)==6 and set(requested_goals)==set(ALL_GOALS)
                assert page.locator('#cold-prepare').is_disabled()
                page.locator('#cold-prepare-confirm').check();page.locator('#cold-prepare').click()
                page.wait_for_function('()=>!coldBusy&&coldView!==null')
                for name in ['CREATE_RUN','CREATE_PREPARATION','SAVE_REQUEST','ADD_need_summary','ADD_material_outline']:
                    assert page.locator('#cold-stage').input_value()==name
                    if name!='CREATE_RUN':
                        assert page.locator('#cold-stage-prepare').is_enabled()
                        page.locator('#cold-stage-prepare').click();idle(page)
                    assert page.locator('#cold-stage-send').is_disabled()
                    assert not page.locator('#cold-send-confirm').is_checked()
                    page.locator('#cold-send-confirm').check();page.locator('#cold-stage-send').click();idle(page)
                    if name=='CREATE_RUN':
                        run=page.evaluate('coldView.product_observations.find(o=>o.name==="CREATE_RUN").result.run_id')
                        work=f[0].claim('SYNTHETIC actual browser independent Case original worker')
                        assert work and str(work['id'])==run
                        f[0].finish(work)
                        page.locator('#cold-recover').click();idle(page)
                    assert page.evaluate('(name)=>coldCommitted(name)',name)
                    assert_old_preserved(x,t['original'])
                prep_id=page.evaluate('coldView.product_observations.find(o=>o.name==="CREATE_PREPARATION").result.preparation_id')
                response=client.get('/api/preparations/'+prep_id,headers=headers(f[2]));assert response.status_code==200,response.text
                fresh=response.json();p={**fresh['preparation'],'preparation_id':prep_id}
                for name in ('case_id','run_id','preparation_id'):assert p[name]!=old[name]
                assert {m['text'] for m in fresh['current_materials']}=={need,outline}
                with f[1].connect() as c:
                    row=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(prep_id,)).fetchone()
                    assert row['service_case_plan'] is None
                    assert not c.execute('SELECT 1 FROM case_resource_links WHERE preparation_id=%s',(prep_id,)).fetchone()
                    assert not c.execute('SELECT 1 FROM run_assignments WHERE run_id=%s',(p['run_id'],)).fetchone()
                proven['fresh_original_five_stages']=True
                f[1].assign_status('executor-a',UUID(p['run_id']),active=True)
                proven['original_new_assignment']=True
                page.locator('#cold-open').click();page.wait_for_function('(id)=>servicePlanId===id&&servicePlanView!==null',arg=prep_id)
                assert page.evaluate('coldHandle()===null')
                for action,actor in [('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')]:
                    response=material(http_f,p,action,actor,reason='SYNTHETIC independent browser prerequisite '+action)
                    assert response.status_code==200,response.text;p=response.json()
                page.evaluate('(id)=>loadServiceCasePlan(id)',prep_id)
                page.locator('#service-selection-read').click();page.wait_for_function('()=>!serviceSelectionBusy&&serviceSelectionCatalog!==null')
                assert page.locator('#service-selection-generate').is_enabled()
                page.locator('#service-selection-generate').click();page.wait_for_function('()=>!serviceSelectionBusy&&serviceSelectionView!==null')
                assert len(t['selection_calls'])==1
                assert page.evaluate('serviceSelectionView.state')=='VERIFIED_STRUCTURE_ONLY'
                assert page.evaluate('serviceSelectionView.required_goals')==requested_goals
                proven['explicit_generate']=True
                page.locator('#service-plan-reason').fill('SYNTHETIC explicit adoption for newly entered independent Case only')
                assert not page.locator('#service-selection-confirm').is_checked()
                before_unconfirmed = len(calls)
                page.locator('#service-plan-adopt').click()
                page.wait_for_function('()=>servicePlanPending===null&&!activeEntryWriteFlow')
                assert not any(c['method']=='POST' for c in calls[before_unconfirmed:])
                with f[1].connect() as c:
                    assert c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(prep_id,)).fetchone()['service_case_plan'] is None
                page.locator('#service-selection-confirm').check()
                assert page.locator('#service-plan-adopt').is_enabled()
                page.locator('#service-plan-adopt').click();page.wait_for_function('()=>!servicePlanPending&&servicePlanView?.revision===1')
                with f[1].connect() as c:
                    plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(prep_id,)).fetchone()['service_case_plan']
                    assert plan and plan['required_goals']==requested_goals and len(plan['steps'])==5
                    assert plan['id']!=t['original']['preparations'][0]['service_case_plan']['id']
                    assert not c.execute('SELECT 1 FROM case_resource_links WHERE preparation_id=%s',(prep_id,)).fetchone()
                    assert not c.execute('SELECT 1 FROM service_dispatches WHERE preparation_id=%s',(prep_id,)).fetchone()
                proven['explicit_adopt']=True
                assert_old_preserved(x,t['original'])
                assert states(f,x['holds'])==['CONFIRMED']*len(x['holds'])
                proven['old_case_history_occupancy_preserved']=True
                old_posts=[c for c in calls if c['method']=='POST' and old['preparation_id'] in c['path']]
                assert len(old_posts)==1 and old_posts[0]['path'].endswith('/case-cancellation-before-receipt')
                assert len([c for c in calls if c['method']=='POST' and c['path'].endswith('/service-selections')])==1
                assert not errors
            finally:
                page.unroute_all(behavior='wait')
                OUT.mkdir(parents=True,exist_ok=True)
                report=dict(actual_browser='INSTALLED_CHROMIUM',browser_version=browser.version,
                    actual_html=True,actual_http_asgi=True,owned_postgresql=True,proven=proven,
                    calls=calls,page_errors=errors,python_http_requests=python_requests,
                    native_windows='NOT_RUN',formal_at='NOT_RUN',production='NOT_RUN',real_models='NOT_RUN',
                    browser_full_fulfillment='NOT_RUN_API_MODULE_SEPARATE')
                (OUT/('new-case-'+uuid4().hex[:10]+'.json')).write_text(json.dumps(report,indent=2)+'\n')
                ctx.close();browser.close()
