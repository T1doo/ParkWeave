"""One fresh ordinary DOM Case: partial plan -> human evidence/reply -> cold read.

Only synthetic identities/catalog/resources are installed by the fixture. No
business API setup, template/approval bridge, SQL state edit or JS navigation.
"""
import json
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright,expect

from test_local_synthetic_demo import demo_inputs,preparation_fixture,receipt_fixture
from test_local_synthetic_demo_browser import ordinary_demo
from test_demo_original_page_intake_browser import ordinary_worker,login,open_from_list,open_service_plan,settled,verify
from service_release_acceptance_support import authority_snapshot,case_history

MANUAL_GOAL='SYNTHETIC_EXTERNAL_AUTHORITY_APPROVAL'
GOALS=['LOCAL_MATERIAL_PREPARATION',MANUAL_GOAL]


def open_manual(page):
    page.locator('#manual-goal-prepare').click()
    page.wait_for_function('()=>mgView!==null&&!mgBusy')
    expect(page.locator('#manual-goal-form')).to_be_visible()


def open_task(page,kind,preparation_id):
    page.locator('[data-tab="collaboration"]').click();page.locator('#prep-tasks').click()
    card=page.locator('[data-task-kind="'+kind+'"]')
    expect(card).to_have_count(1,timeout=15000)
    card.locator('[data-personal-task="'+preparation_id+'"]').click()
    page.wait_for_function('()=>mgView!==null&&!mgBusy')
    assert page.evaluate('mgView.preparation_id')==preparation_id


def manual_action(page,action,state,revision):
    page.locator('#manual-goal-name').select_option(MANUAL_GOAL)
    page.locator('#manual-goal-action').select_option(action)
    page.locator('#manual-goal-reason').fill('SYNTHETIC original person explicitly '+action)
    if action in ('SUPPLY_EVIDENCE','REPLY'):
        if action=='REPLY':page.locator('#manual-goal-reply-kind').select_option('INFORMATION')
        refs=page.locator('#manual-goal-materials [data-manual-material]')
        expect(refs).to_have_count(2)
        for ref in refs.all():ref.check()
    page.locator('#manual-goal-purpose').check()
    if action=='ACKNOWLEDGE_REPLY':
        expect(page.locator('#manual-goal-submit')).to_be_disabled()
        expect(page.locator('#manual-goal-reply-binding')).to_contain_text('原答复事件')
        page.locator('#manual-goal-reply-confirm').check()
    page.locator('#manual-goal-submit').click()
    page.wait_for_function('''([state,revision,goal])=>!mgBusy&&mgView?.revision===revision&&
        mgView.items.find(x=>x.goal===goal)?.state===state&&mgHandles()?.length===0''',
        arg=[state,revision,MANUAL_GOAL])
    settled(page)
    result=page.evaluate('mgView')
    assert result['overall_goal_state']=='PARTIAL' and result['case_goal_completed'] is False
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    return result


@pytest.mark.parametrize('width',[1200,320])
def test_fresh_ordinary_partial_case_human_evidence_reply_and_cold_read(demo_inputs,tmp_path,width):
    f,_,pack,_=demo_inputs;authority=authority_snapshot(f[1]);traffic=[];errors=[];views=[];contexts=[]
    goal='SYNTHETIC new ordinary human collaboration '+str(width)
    with f[1].connect() as c:
        assert all(c.execute('SELECT count(*) n FROM '+t).fetchone()['n']==0 for t in
                   ('runs','cases','preparations','preparation_evidence','run_assignments'))
    with ordinary_demo(f,tmp_path/'first') as api,ordinary_worker(f,tmp_path/'worker') as worker,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        def role(actor):
            context=browser.new_context(viewport=dict(width=width,height=1000));contexts.append(context)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            def response(reply):
                request=reply.request
                if request.method=='POST':traffic.append(dict(actor=actor,path=urlsplit(request.url).path,
                    status=reply.status,body=request.post_data_json))
            page.on('response',response);login(page,api,f,actor);return page
        try:
            owner=role(pack['roles']['enterprise_operator']);reviewer=role(pack['roles']['park_specialist'])
            owner.locator('#prep-catalog').click();expect(owner.locator('#prep-create')).to_be_visible()
            owner.locator('#prep-reviewer').select_option(pack['roles']['park_specialist'])
            owner.locator('#prep-goal').fill(goal);owner.locator('#prep-create button').click()
            expect(owner.locator('#prep-summary')).to_contain_text(goal,timeout=20000);settled(owner,preparation=True)
            preparation_id=owner.evaluate('preparationId');assert worker.poll() is None
            owner.locator('#plan-prepare').click();expect(owner.locator('#request-intent-form')).to_be_visible()
            owner.locator('#request-current').fill(goal);owner.locator('#request-local-goal').uncheck()
            owner.locator('#plan-required-goals').fill('\n'.join(GOALS));owner.locator('#request-save').click()
            expect(owner.locator('#request-intent-status')).to_contain_text('已保存诉求/目标版本',timeout=15000);settled(owner)
            owner.locator('#plan-materials').click();settled(owner,preparation=True)
            for slot in ('need_summary','material_outline'):
                owner.locator('#prep-slot').select_option(slot)
                owner.locator('#prep-text').fill('SYNTHETIC current evidence '+slot+' for '+str(width))
                owner.locator('#prep-source-kind').select_option('USER_STATEMENT')
                owner.locator('#prep-source-label').fill('SYNTHETIC original person document '+slot)
                owner.locator('#prep-evidence button').click()
                expect(owner.locator('#prep-command-feedback')).to_contain_text('已核对原操作保存事件',timeout=15000)
                settled(owner,preparation=True)
            open_from_list(reviewer,goal);reviewer.locator('#prep-reason').fill('SYNTHETIC original reviewer material check')
            reviewer.locator('#prep-review').click();expect(reviewer.locator('#prep-summary')).to_contain_text('待企业确认',timeout=15000)
            settled(reviewer,preparation=True)
            owner.locator('#prep-refresh').click();settled(owner,preparation=True)
            owner.locator('#prep-reason').fill('SYNTHETIC owner independent local confirmation')
            owner.locator('#prep-confirm').click();expect(owner.locator('#prep-summary')).to_contain_text('本地资料准备已确认',timeout=15000)
            settled(owner,preparation=True);open_service_plan(owner)
            expect(owner.locator('#service-plan-partial-label')).to_be_visible()
            owner.locator('#service-plan-partial-confirm').check()
            owner.locator('#service-plan-reason').fill('SYNTHETIC keep unsupported goal and adopt independent P1')
            owner.locator('#service-plan-adopt').click();settled(owner)
            assert owner.evaluate('servicePlanView.required_goals')==GOALS
            verify(owner,'P1');open_from_list(owner,goal);open_manual(owner)
            views.append(manual_action(owner,'REQUEST','REQUESTED',1))
            open_task(reviewer,'MANUAL_ACCEPT_REQUEST',preparation_id)
            views.append(manual_action(reviewer,'TAKE','UNDER_MANUAL_REVIEW',2))
            views.append(manual_action(reviewer,'REQUEST_EVIDENCE','WAITING_OWNER_EVIDENCE',3))
            open_task(owner,'MANUAL_SUPPLY_EVIDENCE',preparation_id)
            views.append(manual_action(owner,'SUPPLY_EVIDENCE','AWAITING_SPECIALIST_REVIEW',4))
            open_task(reviewer,'MANUAL_REVIEW_REQUEST',preparation_id)
            views.append(manual_action(reviewer,'TAKE','UNDER_MANUAL_REVIEW',5))
            views.append(manual_action(reviewer,'REPLY','WAITING_OWNER_ACKNOWLEDGEMENT',6))
            open_task(owner,'MANUAL_ACKNOWLEDGE_REPLY',preparation_id)
            views.append(manual_action(owner,'ACKNOWLEDGE_REPLY','COORDINATION_ENDED',7))
            final=views[-1];item=final['items'][0]
            for view in views:
                assert all(view[key]==final[key] for key in ('preparation_id','case_id','run_id','plan_id','source_sha256','materials'))
                assert view['preparation_id']==preparation_id
                assert all(material['integrity_current'] for material in view['materials'])
            assert item['responsible_actor_id'] is None and item['goal_state']=='UNSUPPORTED'
            assert not item['reply']['truth_verified'] and not item['reply']['awareness_proves_reading']
            assert item['reply']['source_current']
            history=item['history'];assert [e['request']['action'] for e in history]==[
                'REQUEST','TAKE','REQUEST_EVIDENCE','SUPPLY_EVIDENCE','TAKE','REPLY','ACKNOWLEDGE_REPLY']
            assert all(event['request']['expected_source_sha256']==final['source_sha256'] for event in history)
            refs=[{k:m[k] for k in ('id','version','source_sha256')} for m in final['materials']]
            assert history[3]['request']['evidence']==refs==history[5]['request']['evidence']
            assert history[6]['request']['reply_event_id']==history[5]['id']
            assert history[6]['request']['reply_fingerprint']==history[5]['fingerprint']
            for page in (owner,reviewer):
                page.locator('#prep-tasks').click();expect(page.locator('[data-task-kind^="MANUAL_"]')).to_have_count(0)
            open_from_list(owner,goal);open_service_plan(owner);owner.locator('#goal-results-read').click()
            owner.wait_for_function('()=>goalResultView!==null');result=owner.evaluate('goalResultView')
            assert result['state']=='PARTIAL' and [r['state'] for r in result['results']]==['LOCAL_OUTPUT_VERIFIED','UNSUPPORTED']
            assert not result['case_goal_completed'] and authority_snapshot(f[1])==authority and not errors
            assert all(r['status']<300 for r in traffic)
            assert not any('template-consumer' in r['path'] or 'plan-approval' in r['path'] or 'run-access' in r['path'] for r in traffic)
            owner.screenshot(path=str(tmp_path/'human-ended.png'))
        finally:
            (tmp_path/'human-phase-proof.json').write_text(json.dumps(dict(width=width,views=views,POSTs=traffic,
                page_errors=errors,all_business_actions_DOM=True,JS_navigation=0,business_API_setup=0,
                authority_changes=0,real_model_calls=0,formal_AT=False),ensure_ascii=False,indent=2)+'\n')
            for context in contexts:context.close()
            browser.close()
    persisted=case_history(f[1],preparation_id)
    with ordinary_demo(f,tmp_path/'restart') as api,sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        for actor in (pack['roles']['enterprise_operator'],pack['roles']['park_specialist']):
            context=browser.new_context(viewport=dict(width=width,height=1000));page=context.new_page();methods=[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda request:methods.append(request.method));login(page,api,f,actor)
            open_from_list(page,goal);open_manual(page);cold=page.evaluate('mgView')
            assert all(cold[key]==final[key] for key in ('preparation_id','case_id','run_id','plan_id','source_sha256','materials'))
            assert cold['items'][0]['history']==history and cold['items'][0]['state']=='COORDINATION_ENDED'
            assert cold['items'][0]['reply']['source_current'] and not errors
            assert set(methods)=={'GET'};context.close()
        browser.close()
    assert authority_snapshot(f[1])==authority and case_history(f[1],preparation_id)==persisted
    (tmp_path/'human-persistent-proof.json').write_text(json.dumps(dict(preparation_id=preparation_id,
        case_id=final['case_id'],run_id=final['run_id'],plan_id=final['plan_id'],history=history,
        required_goals=GOALS,case_goal_completed=False,goal_state='PARTIAL',cold_two_roles_GET_only=True,
        full_case_history_unchanged=True,source='SYNTHETIC',Windows='NOT_RUN'),ensure_ascii=False,indent=2)+'\n')
