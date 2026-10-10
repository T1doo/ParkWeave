"""The existing author and three workspaces, with fresh authenticated contexts."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import uuid4
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from test_new_enterprise_local_chain import (fresh_chain,link_fixture,receipt_fixture,preparation_fixture,
    ALL_GOALS,call,ok,input_body,enable_approval,original_rows,publish,new_case,permission_snapshot)
from test_resource_bundles_browser import open_resources,choose
from test_service_plan_approval_browser import approve_page,idle
from parkweave import resource_holds as rh,resource_combinations as rc

OUT=Path('.runtime/new-enterprise-chain/browser')


def template_page(browser,u,width=1200):
    context=browser.new_context(viewport={'width':width,'height':1000});page=context.new_page();page.goto(u['base']+'/template')
    page.wait_for_function('()=>status!==null')
    page.locator('#template-park').fill('park-a');page.locator('#template-id').fill(u['scope'].template_id)
    page.locator('#template-id').dispatch_event('change');page.locator('#template-actor').select_option('template-author')
    page.locator('#template-refresh').click();page.wait_for_function('()=>view!==null')
    return context,page


def author_publish(page):
    for goal in ALL_GOALS:page.locator('[data-template-goal="'+goal+'"]').check()
    page.locator('#template-name').fill('SYNTHETIC explicitly reviewed multi-step fresh input template')
    page.locator('#template-reason').fill('SYNTHETIC explicit original author action')
    page.locator('[data-template-action="SAVE_DRAFT"]').click();page.wait_for_function('()=>tp===null&&view?.state==="DRAFT"&&Array.isArray(view.draft?.required_goals)')
    assert set(page.evaluate('view.draft.required_goals'))==set(ALL_GOALS)
    assert [s['id'] for s in page.evaluate('view.draft.steps')]==['P1','P2','P3','P4','P5']
    page.locator('[data-template-action="SUBMIT"]').click();page.wait_for_function('()=>tp===null&&view.state==="SUBMITTED"')
    for actor,action,state in [('template-reviewer','REVIEW','REVIEWED'),('template-publisher','CANDIDATE_PUBLISH','PUBLISHED')]:
        page.locator('#template-actor').select_option(actor);page.locator('#template-refresh').click();page.wait_for_function('()=>view!==null')
        assert page.locator('[data-template-goal]:checked').count()==6
        page.locator('#template-reason').fill('SYNTHETIC explicit independent '+action)
        page.locator('[data-template-action="'+action+'"]').click();page.wait_for_function('(state)=>tp===null&&view.state===state',arg=state)


def cold_product(browser,u,actor,width=1200):
    ctx=browser.new_context(viewport={'width':width,'height':1000});page=ctx.new_page();page.goto(u['base']+'/')
    assert page.locator('#token').input_value()=='' and page.evaluate('localStorage.length')==0
    page.locator('#token').fill(u['f'][2][actor]);page.locator('#token').dispatch_event('change')
    page.locator('[data-tab="collaboration"]').click()
    return ctx,page


def prepare_page(page,row,role):
    page.evaluate('(data)=>loadPreparation(data.id,{role:data.role})',dict(id=row['preparation_id'],role=role))
    page.wait_for_function('()=>preparationView!==null')


def verify_page(page,row,adapter):
    page.evaluate('(id)=>loadServiceCasePlan(id)',row['preparation_id']);page.wait_for_function('()=>servicePlanView!==null')
    page.locator('#service-plan-reason').fill('SYNTHETIC owner explicitly checks actual '+adapter)
    page.locator('[data-service-adapter="'+adapter+'"] [data-service-action="VERIFY"]').click()
    page.wait_for_function('(adapter)=>servicePlanPending===null&&servicePlanView.steps.find(s=>s.adapter_id===adapter)?.state==="VERIFIED"',arg=adapter)


def access_read(page,row):
    page.wait_for_function('()=>runAccessStatusView?.enabled===true')
    page.locator('#run-access-open').click();page.locator('#run-access-id').fill(row['run_id']);page.locator('#run-access-read').click()
    page.wait_for_function('()=>runAccessView!==null')


def create_three_holds(page,u,owner):
    open_resources(page,u['f'],owner);start=datetime.now(timezone.utc)+timedelta(hours=1);hs=[]
    for i,id in enumerate([rh.RESOURCE_ID,rc.SECOND_RESOURCE_ID,rh.RESOURCE_ID]):
        page.locator('#resource-select').select_option(str(id))
        page.locator('#resource-start').fill((start+timedelta(hours=3*i)).strftime('%Y-%m-%dT%H:%M'))
        page.locator('#resource-end').fill((start+timedelta(hours=3*i+1)).strftime('%Y-%m-%dT%H:%M'))
        page.locator('#resource-ttl').fill('300');page.locator('#resource-purpose').fill('SYNTHETIC explicitly selected current Case resource '+str(i))
        page.locator('#resource-preview').click();page.wait_for_function('()=>resourcePreview!==null')
        with page.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/holds')) as response:
            page.locator('#resource-hold').click()
        actual=response.value;assert actual.status==201,actual.text();hs.append(actual.json()['hold'])
        page.wait_for_function('(id)=>document.querySelector("#resource-current [data-hold-id]")?.dataset.holdId===id',arg=hs[-1]['id'])
    choose(page,hs)
    return hs


@pytest.mark.parametrize('width,owner',[(320,'fixture-a'),(1200,'fixture-b')])
def test_actual_cold_author_enterprise_reviewer_executor_whole_original_page_chain(fresh_chain,width,owner):
    u=fresh_chain;requests=[];errors=[];contexts=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        try:
            ctx,author=template_page(browser,u,width);contexts.append(ctx);author_publish(author)
            # A brand new enterprise browser context submits only its own current inputs.
            ctx=browser.new_context(viewport={'width':width,'height':1000});contexts.append(ctx);enterprise=ctx.new_page();enterprise.goto(u['base']+'/template')
            assert enterprise.locator('#consumer-token').input_value()==''
            enterprise.locator('#consumer-token').fill(u['f'][2][owner]);enterprise.locator('#consumer-catalog').click()
            enterprise.wait_for_function('()=>catalog!==null&&document.querySelector("#consumer-release").options.length===1')
            data=input_body(dict(release_id=enterprise.locator('#consumer-release').input_value(),release_sha256=enterprise.locator('#consumer-release option').get_attribute('data-hash')),owner)
            for id,field in [('consumer-goal','goal'),('consumer-need-summary',None),('consumer-material-outline',None),('consumer-need-source',None),('consumer-outline-source',None)]:
                value=data[field] if field else data['materials'][0 if 'need' in id else 1]['source_label' if id.endswith('source') else 'text']
                enterprise.locator('#'+id).fill(value)
            enterprise.locator('#consumer-reviewer').select_option('prep-specialist-'+owner)
            enterprise.locator('#consumer-create').click();enterprise.wait_for_function('()=>cp===null&&instance?.state==="PENDING_RUN"')
            row=enterprise.evaluate('instance');work=u['f'][0].claim('new-enterprise-original-browser-worker');assert str(work['id'])==row['run_id'];u['f'][0].finish(work)
            enterprise.locator('#consumer-resume').click();enterprise.wait_for_function('()=>cp===null&&instance?.state==="PLAN_ADOPTED"')
            row=enterprise.evaluate('instance');assert set(row['service_case_plan']['required_goals'])==set(ALL_GOALS)
            enable_approval(u,[row])
            ctx,reviewer=cold_product(browser,u,'prep-specialist-'+owner,width);contexts.append(ctx)
            ctx,operator=cold_product(browser,u,owner,width);contexts.append(ctx)
            for page in [author,enterprise,reviewer,operator]:page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(dict(method=r.method,path=r.url.split(u['base'])[-1])))
            prepare_page(reviewer,row,'park_specialist');reviewer.locator('#prep-reason').fill('SYNTHETIC independent current source review');reviewer.locator('#prep-review').click();reviewer.wait_for_function('()=>prepCommandPending===null&&preparationView?.preparation.state==="REVIEWED"')
            prepare_page(operator,row,'enterprise_operator');operator.locator('#prep-reason').fill('SYNTHETIC explicit current enterprise confirmation');operator.locator('#prep-confirm').click();operator.wait_for_function('()=>prepCommandPending===null&&preparationView?.preparation.state==="LOCAL_CONFIRMED"');verify_page(operator,row,'P1')
            assert call(u,'/api/service-dispatches/catalog?preparation_id='+row['preparation_id'],actor='prep-specialist-'+owner)['executors']==[]
            access_read(operator,row);operator.locator('#run-access-target').select_option('executor-'+owner[-1]);now=datetime.now(timezone.utc)
            operator.locator('#run-access-valid-from').fill(now.isoformat().replace('+00:00','Z'));operator.locator('#run-access-valid-until').fill((now+timedelta(minutes=20)).isoformat().replace('+00:00','Z'));operator.locator('#run-access-reason').fill('SYNTHETIC explicitly request only this new Run')
            operator.locator('#run-access-request button').click();operator.wait_for_function('()=>runAccessPending===null&&runAccessView?.state==="REQUESTED"')
            access_read(reviewer,row)
            requested=reviewer.evaluate('runAccessView.request.requested_validity')
            reviewer.locator('#run-access-approved-from').fill(requested['valid_from'].replace('+00:00','Z'));reviewer.locator('#run-access-approved-until').fill(requested['valid_until'].replace('+00:00','Z'))
            reviewer.locator('#run-access-decision-reason').fill('SYNTHETIC independent explicit single Run approval');reviewer.locator('#run-access-approve').click();reviewer.wait_for_function('()=>runAccessPending===null&&runAccessView?.state==="APPROVED"')
            hs=create_three_holds(operator,u,owner);operator.locator('#delivery-case').fill(row['preparation_id']);operator.locator('#delivery-preview').click();operator.wait_for_function('()=>deliveryQuote!==null')
            approve_page(operator)
            # At 320, lose the actual committed delivery reply and recover after cold reload.
            deliveries=[]
            if width==320:
                def lose(route):
                    response=route.fetch();assert response.status==201;deliveries.append(response.json());route.abort('failed')
                operator.route('**/api/preparations/'+row['preparation_id']+'/resource-delivery',lose)
            with operator.expect_response(lambda r:r.request.method=='POST' and r.url.endswith('/resource-delivery')) if width!=320 else _no_response():
                operator.locator('#delivery-confirm').click()
            idle(operator)
            if width==320:
                assert deliveries and operator.evaluate('deliveryHandles().length')==1
                operator.reload();assert operator.locator('#token').input_value()=='';operator.unroute('**/api/preparations/'+row['preparation_id']+'/resource-delivery')
                before=len(requests);open_resources(operator,u['f'],owner);operator.locator('#delivery-recover').click();idle(operator);operator.wait_for_function('()=>deliveryHandles().length===0')
                assert all(r['method']=='GET' for r in requests[before:])
            verify_page(operator,row,'P2')
            reviewer.evaluate('(id)=>loadDispatch(id)',row['preparation_id']);reviewer.wait_for_function('()=>dispatchView!==null');reviewer.locator('#dispatch-executor').select_option('executor-'+owner[-1]);reviewer.locator('#dispatch-offer-reason').fill('SYNTHETIC original explicitly offers responsibility');reviewer.locator('#dispatch-offer-button').click();reviewer.wait_for_function('()=>dispatchView?.current_offer?.state==="OFFERED"')
            ctx,executor=cold_product(browser,u,'executor-'+owner[-1],width);contexts.append(ctx);executor.on('pageerror',lambda e:errors.append(str(e)));executor.on('request',lambda r:requests.append(dict(method=r.method,path=r.url.split(u['base'])[-1])))
            executor.evaluate('(id)=>loadDispatch(id)',row['preparation_id']);executor.wait_for_function('()=>dispatchView!==null');executor.locator('#dispatch-decision-reason').fill('SYNTHETIC actual counterparty accepts');executor.locator('#dispatch-accept').click();executor.wait_for_function('()=>dispatchView?.current_offer?.state==="ACCEPTED"');dispatch=executor.evaluate('dispatchView');verify_page(operator,row,'P3')
            executor.locator('#dispatch-receipt').click();executor.wait_for_function('()=>receiptView!==null');executor.locator('#receipt-local-execution-reason').fill('SYNTHETIC explicitly generate actual local output');executor.locator('#receipt-local-execution-button').click();executor.wait_for_function('()=>receiptLocalPending===null&&receiptView?.current_receipt?.adapter_execution');receipt=executor.evaluate('receiptView.current_receipt')
            assert hashlib.sha256(receipt['text'].encode()).hexdigest()==receipt['source_sha256']
            operator.evaluate('(id)=>loadReceipt(id)',dispatch['receipt_step_id']);operator.wait_for_function('()=>receiptView!==null');operator.locator('#receipt-reason').fill('SYNTHETIC owner checks actual report bytes');operator.locator('#receipt-ack').click();operator.wait_for_function('()=>receiptView?.step.state==="LOCAL_ACKNOWLEDGED"');verify_page(operator,row,'P4')
            operator.evaluate('(id)=>loadLocalCase(id)',row['preparation_id']);operator.wait_for_function('()=>localCaseView!==null');operator.locator('#local-case-reason').fill('SYNTHETIC explicit actual current local recheck');operator.locator('#local-case-validate').click();operator.wait_for_function('()=>localCaseView?.local_record_state==="READY"');verify_page(operator,row,'P5')
            before=original_rows(u,row);ctx,result_page=cold_product(browser,u,owner,width);contexts.append(ctx);cold_requests=[];result_page.on('request',lambda r:cold_requests.append(r.method))
            result_page.evaluate('(id)=>loadServiceCasePlan(id)',row['preparation_id']);result_page.wait_for_function('()=>servicePlanView!==null');result_page.locator('#goal-results-read').click();result_page.wait_for_function('()=>goalResultView!==null&&!document.getElementById("goal-results-read").disabled')
            result=result_page.evaluate('goalResultView');assert result['state']=='LOCAL_OUTPUTS_VERIFIED' and result_page.locator('[data-goal-state="LOCAL_OUTPUT_VERIFIED"]').count()==6
            assert all(x['actual_output'] for x in result['results']) and not result['case_goal_completed'];assert set(cold_requests)=={'GET'} and original_rows(u,row)==before
            assert permission_snapshot(u['f'][1])==u['permissions']
            assert result_page.evaluate('document.documentElement.scrollWidth<=innerWidth') and result_page.evaluate('localStorage.length')==0
            assert not errors,errors
            OUT.mkdir(parents=True,exist_ok=True);result_page.screenshot(path=str(OUT/f'whole-{owner}-{width}.png'))
            (OUT/f'whole-{owner}-{width}.json').write_text(json.dumps(dict(actual_http=True,actual_pg=True,chromium=True,width=width,owner=owner,cold_role_contexts=len(contexts),template_goals=len(result['results']),case_id=row['case_id'],execution_id=receipt['adapter_execution']['report']['execution_id'],actual_report_hash=receipt['source_sha256'],cold_final_get_only=True,delivery_reply_lost=width==320,case_completed=False,original_permissions_unchanged=True,requests=requests))+'\n')
        except Exception:
            OUT.mkdir(parents=True,exist_ok=True)
            snapshots=[]
            for ctx in contexts:
                for page in ctx.pages:
                    if page.url.endswith('/'):
                        snapshots.append(page.evaluate('()=>({preparationView,prepCommandPending,prepError:document.getElementById("prep-error").textContent,feedback:document.getElementById("page-feedback").textContent,dispatchView,receiptView,localCaseView})'))
            (OUT/f'failure-{owner}-{width}-{uuid4().hex}.json').write_text(json.dumps(dict(errors=errors,requests=requests,snapshots=snapshots)))
            raise
        finally:
            for ctx in contexts:ctx.close()
            browser.close()


class _no_response:
    def __enter__(self):return self
    def __exit__(self,*args):return False


def test_goal_selection_unknown_save_keeps_original_body_and_cas(fresh_chain):
    u=fresh_chain
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=template_page(browser,u)
        try:
            for goal in ALL_GOALS:page.locator('[data-template-goal="'+goal+'"]').check()
            keys=[]
            def lose(route):
                response=route.fetch();assert response.status==200;keys.append(route.request.headers['idempotency-key']);route.abort('failed')
            path='**/api/template-candidate/park-a/'+u['scope'].template_id+'/commands';page.route(path,lose)
            page.locator('[data-template-action="SAVE_DRAFT"]').click();page.wait_for_function('()=>tp?.state==="UNKNOWN"')
            assert page.locator('[data-template-goal]:disabled').count()==6
            original=page.evaluate('tp.body');page.unroute(path);page.locator('#template-retry').click();page.wait_for_function('()=>tp===null&&view?.revision===1')
            assert page.evaluate('view.draft.required_goals')==original['draft']['required_goals'] and len(keys)==1
            assert len(page.evaluate('view.history'))==1
            page.locator('#template-actor').select_option('template-reviewer');assert page.locator('[data-template-goal]:checked').count()==0
        finally:ctx.close();browser.close()


def test_no_goal_or_modified_registry_does_not_create_publishable_template(fresh_chain):
    u=fresh_chain
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=template_page(browser,u)
        try:
            for el in page.locator('[data-template-goal]:checked').all():el.uncheck()
            posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None)
            page.locator('[data-template-action="SAVE_DRAFT"]').click();page.wait_for_function('()=>document.querySelector("#template-error").textContent.includes("至少一个")');assert not posts and page.evaluate('view.revision')==0
            page.locator('[data-template-goal="LOCAL_MATERIAL_PREPARATION"]').check();page.evaluate('()=>status.registered_steps[0].adapter_revision=999')
            page.locator('[data-template-action="SAVE_DRAFT"]').click();page.wait_for_function('()=>tp===null&&document.querySelector("#template-error").textContent.includes("合同")');assert len(posts)==1 and page.evaluate('view.revision')==0
            assert u['engine'].public_catalog('park-a')['items']==[]
        finally:ctx.close();browser.close()


@pytest.mark.parametrize('damage',['changed-nested-hash','missing-source','extra-source-key','wrong-source-type'])
def test_review_reply_requires_exact_nested_saved_event_before_releasing_original_request(fresh_chain,damage):
    u=fresh_chain;row=new_case(u,publish(u));path='/api/preparations/'+row['preparation_id']
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx,page=cold_product(browser,u,'prep-specialist-fixture-a')
        try:
            prepare_page(page,row,'park_specialist')
            def corrupt(route):
                response=route.fetch();assert response.ok;body=response.json()
                event=next((e for e in body['history'] if e['action']=='REVIEW'),None)
                if event:
                    source=event['payload']['delivery_review_source']
                    if damage=='changed-nested-hash':source['catalog_sha256']='0'*64
                    elif damage=='missing-source':event['payload'].pop('delivery_review_source')
                    elif damage=='extra-source-key':source['unexpected']='SYNTHETIC must not be ignored'
                    else:event['payload']['delivery_review_source']=list(source.values())
                route.fulfill(response=response,json=body)
            page.route('**'+path,corrupt)
            page.locator('#prep-reason').fill('SYNTHETIC exact source acknowledgement remains required');page.locator('#prep-review').click()
            page.wait_for_function('()=>prepCommandPending?.state==="UNKNOWN"')
            assert page.evaluate('preparationView.preparation.state')=='IN_PREPARATION'
            assert page.locator('#prep-review').is_disabled() and page.locator('#prep-command-retry').is_visible()
            original=page.evaluate('({body:prepCommandPending.body,key:prepCommandPending.key})')
            actual=call(u,path,actor='prep-specialist-fixture-a');assert actual['preparation']['state']=='REVIEWED'
            assert len([e for e in actual['history'] if e['action']=='REVIEW'])==1
            page.unroute('**'+path);page.locator('#prep-command-retry').click();page.wait_for_function('()=>prepCommandPending===null&&preparationView?.preparation.state==="REVIEWED"')
            saved=call(u,path,actor='prep-specialist-fixture-a');assert saved==actual
            assert original['body']['expected_revision']==row['preparation']['preparation']['revision']
            assert permission_snapshot(u['f'][1])==u['permissions']
        finally:ctx.close();browser.close()
