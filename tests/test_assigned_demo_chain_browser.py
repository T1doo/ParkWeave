"""Existing synthetic authority -> ordinary DOM P1-P5, no runtime provisioning.

Unlike the fresh-Run intake slice, the exact Run assignment is fixture initial
state BEFORE the ordinary server starts. It never enters the normal loader.
"""
from datetime import datetime,timedelta,timezone
import json
from urllib.parse import urlsplit
from uuid import UUID

import pytest
from playwright.sync_api import sync_playwright,expect

from test_local_synthetic_demo import demo_inputs,prepared,preparation_fixture,receipt_fixture
from test_local_synthetic_demo_browser import ordinary_demo
from test_demo_original_page_intake_browser import login,open_from_list,open_service_plan,verify,settled
from service_release_acceptance_support import authority_snapshot,case_history


def run_existing_assigned_chain(demo_inputs,tmp_path,width,*,continuation=None):
    f,_,pack,_=demo_inputs
    parent=prepared(f)
    # Only owned synthetic fixture initialization; never runtime authority.
    f[1].assign_status(pack['roles']['service_executor'],UUID(parent['run_id']),active=True)
    baseline=authority_snapshot(f[1]);goal='SYNTHETIC资料准备'
    traffic=[];errors=[];contexts=[]
    with ordinary_demo(f,tmp_path/'first') as api,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        def role(actor):
            context=browser.new_context(viewport=dict(width=width,height=1000));contexts.append(context);page=context.new_page()
            page.on('pageerror',lambda e:errors.append(str(e)))
            def response(reply):
                req=reply.request
                if req.method=='POST':traffic.append(dict(actor=actor,path=urlsplit(req.url).path,status=reply.status,body=req.post_data_json))
            page.on('response',response);login(page,api,f,actor);return page
        try:
            owner=role(pack['roles']['enterprise_operator'])
            reviewer=role(pack['roles']['park_specialist'])
            executor=role(pack['roles']['service_executor'])
            open_from_list(owner,goal);open_service_plan(owner)
            owner.locator('#service-selection-read').click()
            expect(owner.locator('#service-selection-catalog')).to_contain_text('LOCAL_SYNTHETIC_DEMO',timeout=15000)
            owner.locator('#service-selection-generate').click()
            expect(owner.locator('#service-selection-confirm')).to_be_enabled(timeout=15000)
            owner.locator('#service-selection-confirm').check()
            owner.locator('#service-plan-reason').fill('SYNTHETIC explicit existing Run DOM adoption')
            owner.locator('#service-plan-adopt').click();settled(owner)
            verify(owner,'P1')
            owner.locator('[data-tab="resource"]').click();owner.locator('#resource-catalog').click()
            expect(owner.locator('#resource-form')).to_be_visible()
            starts=datetime.now(timezone.utc)+timedelta(hours=1);ends=starts+timedelta(hours=1)
            for resource in pack['resources'].values():
                owner.locator('#resource-select').select_option(resource)
                owner.locator('#resource-start').fill(starts.strftime('%Y-%m-%dT%H:%M'))
                owner.locator('#resource-end').fill(ends.strftime('%Y-%m-%dT%H:%M'))
                owner.locator('#resource-quantity').fill('1');owner.locator('#resource-ttl').fill('300')
                owner.locator('#resource-purpose').fill('SYNTHETIC existing assigned Run resources')
                owner.locator('#resource-preview').click();expect(owner.locator('#resource-hold')).to_be_enabled()
                owner.locator('#resource-hold').click()
                expect(owner.locator('#resource-preview-result')).to_contain_text('占位已核对',timeout=15000);settled(owner)
            owner.locator('#resource-mine').click();holds=owner.locator('[data-combination-hold]');expect(holds).to_have_count(2)
            for hold in holds.all():hold.check()
            owner.locator('#combination-confirm').click()
            expect(owner.locator('#combination-feedback')).to_contain_text('确认',timeout=15000);settled(owner)
            open_from_list(owner,goal);owner.locator('#case-resource-load').click()
            expect(owner.locator('#case-resource-form')).to_be_visible()
            owner.locator('#case-resource-reason').fill('SYNTHETIC explicit existing Run resource association')
            owner.locator('#case-resource-form button').click()
            expect(owner.locator('#case-resource-summary')).to_contain_text('当前资料版本与资源关联有效',timeout=15000);settled(owner)
            verify(owner,'P2')
            open_from_list(reviewer,goal);reviewer.locator('#dispatch-prepare').click()
            expect(reviewer.locator('#dispatch-offer')).to_be_visible(timeout=15000)
            reviewer.locator('#dispatch-executor').select_option(pack['roles']['service_executor'])
            reviewer.locator('#dispatch-offer-reason').fill('SYNTHETIC offer to preexisting authorized executor')
            reviewer.locator('#dispatch-offer-button').click()
            expect(reviewer.locator('#dispatch-summary')).to_contain_text('等待执行者决定',timeout=15000);settled(reviewer)
            executor.locator('[data-tab="collaboration"]').click();executor.locator('#dispatch-list').click()
            item=executor.locator('#dispatch-items button').filter(has_text=goal);expect(item).to_have_count(1);item.click()
            expect(executor.locator('#dispatch-summary')).to_contain_text('等待执行者决定')
            executor.locator('#dispatch-decision-reason').fill('SYNTHETIC executor independently accepts')
            executor.locator('#dispatch-accept').click()
            expect(executor.locator('#dispatch-summary')).to_contain_text('执行者已接单',timeout=15000);settled(executor)
            open_from_list(owner,goal);verify(owner,'P3')
            executor.locator('#dispatch-receipt').click()
            expect(executor.locator('#receipt-submit')).to_be_visible(timeout=15000)
            executor.locator('#receipt-text').fill('SYNTHETIC original assigned executor DOM receipt')
            executor.locator('#receipt-source').fill('SYNTHETIC local manual work record')
            executor.locator('#receipt-submit-button').click()
            expect(executor.locator('#receipt-summary')).to_contain_text('回执已记录，待企业核对',timeout=15000);settled(executor)
            owner.locator('[data-tab="collaboration"]').click();owner.locator('#receipt-list').click()
            receipt=owner.locator('#receipt-items button').filter(has_text=goal)
            expect(receipt).to_have_count(1,timeout=15000);receipt.click()
            expect(owner.locator('#receipt-decisions')).to_be_visible(timeout=15000)
            owner.locator('#receipt-reason').fill('SYNTHETIC owner independently checks original receipt')
            owner.locator('#receipt-ack').click()
            expect(owner.locator('#receipt-summary')).to_contain_text('企业已本地核对回执',timeout=15000);settled(owner)
            open_from_list(owner,goal);verify(owner,'P4')
            open_from_list(owner,goal);owner.locator('#local-case-prepare').click()
            expect(owner.locator('#local-case-detail')).to_be_visible(timeout=15000)
            owner.locator('#local-case-reason').fill('SYNTHETIC explicit current local conditions check')
            owner.locator('#local-case-validate').click()
            expect(owner.locator('#local-case-summary')).to_contain_text('当前一轮已显式校验',timeout=15000);settled(owner)
            open_from_list(owner,goal);verify(owner,'P5')
            open_service_plan(owner);owner.locator('#goal-results-read').click()
            expect(owner.locator('#goal-results-status')).to_contain_text('本地',timeout=15000)
            result=owner.evaluate('goalResultView')  # Observation only; all actions are DOM.
            assert result['state']=='LOCAL_OUTPUTS_VERIFIED' and len(result['results'])==6
            assert not result['case_goal_completed'] and {x['state'] for x in result['results']}=={'LOCAL_OUTPUT_VERIFIED'}
            assert result['source_trace']['candidate']['producer']['mode']=='NO_MODEL'
            if continuation is not None:
                result=continuation(f,parent,owner,reviewer,executor,result,tmp_path)
            assert authority_snapshot(f[1])==baseline and not errors
            assert all(x['status']<300 for x in traffic)
            assert not any(x['path'] in ('/api/runs','/api/preparations') or 'run-access' in x['path'] or 'plan-approval' in x['path'] for x in traffic)
            assert owner.evaluate('document.documentElement.scrollWidth<=innerWidth')
            owner.screenshot(path=str(tmp_path/f'assigned-full-chain-{width}.png'))
        except BaseException:
            for i,context in enumerate(contexts):
                for page in context.pages:
                    page.screenshot(path=str(tmp_path/f'failure-{i}.png'))
            (tmp_path/'failure-traffic.json').write_text(json.dumps(dict(traffic=traffic,page_errors=errors),ensure_ascii=False,indent=2)+'\n')
            raise
        finally:
            for context in contexts:context.close()
            browser.close()
    history=case_history(f[1],parent['preparation_id'])
    with ordinary_demo(f,tmp_path/'restart') as api,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=browser.new_page(viewport=dict(width=width,height=1000));methods=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:methods.append(req.method));login(page,api,f,pack['roles']['enterprise_operator'])
        open_from_list(page,goal);open_service_plan(page);page.locator('#goal-results-read').click()
        expect(page.locator('#goal-results-status')).to_contain_text('本地',timeout=15000)
        assert page.evaluate('goalResultView')==result and set(methods)=={'GET'}
        browser.close()
    assert authority_snapshot(f[1])==baseline and case_history(f[1],parent['preparation_id'])==history and not errors
    (tmp_path/'actual-assigned-full-chain.json').write_text(json.dumps(dict(
        scope='ISOLATED_SYNTHETIC_EXISTING_RUN_ORDINARY_DOM_P1_P5',width=width,
        initial_preparation_and_materials='EXISTING_SYNTHETIC_API_FIXTURE',
        initial_exact_Run_executor_assignment='EXPLICIT_FIXTURE_BEFORE_ORDINARY_PROCESS',
        runtime_authority_changes=0,business_POSTs=traffic,DOM_business_actions=True,
        JS_application_navigation=0,api_business_setup_after_startup=0,
        original_adapters=['P1','P2','P3','P4','P5'],local_outputs=6,
        case_goal_completed=False,restart_GET_only=True,real_model_calls=0,
        continuation='NONE' if continuation is None else continuation.__name__,
        Windows='NOT_RUN',formal_AT='NOT_RUN',real_business='NOT_RUN'),ensure_ascii=False,indent=2)+'\n')
    return parent,result,history,traffic


@pytest.mark.parametrize('width',[1200,320])
def test_existing_assigned_run_original_ordinary_DOM_full_chain_and_restart(demo_inputs,tmp_path,width):
    run_existing_assigned_chain(demo_inputs,tmp_path,width)
