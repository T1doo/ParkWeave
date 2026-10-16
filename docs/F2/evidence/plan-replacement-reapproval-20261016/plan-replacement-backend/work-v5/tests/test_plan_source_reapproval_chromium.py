"""Four narrow actual installed Chromium source-reapproval flows; no screenshots."""
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import sync_playwright
import test_plan_source_reapproval_independent as independent
from test_plan_source_reapproval_independent import (
    facts_case,fresh_chain,link_fixture,receipt_fixture,preparation_fixture,
    source_adopt,fresh_holds,ledger,original_rows,assert_prefix_preserved,
    html_controls,full,states,effects,stored,final,
)
from test_resource_bundles_browser import open_resources,choose

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').is_file())
OUT=ROOT/'.runtime/plan-reapproval-independent/chromium'


@pytest.fixture(autouse=True)
def route_chromium_artifacts_before_business_fixtures(monkeypatch):
    # Applies before the imported original facts_case/fresh_chain dependencies.
    import sys
    routes=[]
    for name,module in list(sys.modules.items()):
        if not name.startswith('test_') or module is sys.modules[__name__]:continue
        old=getattr(module,'OUT',None)
        if isinstance(old,Path) and ('.runtime' in old.parts or str(old).startswith('.runtime/')):
            target=OUT/'helpers'/name;monkeypatch.setattr(module,'OUT',target)
            routes.append(dict(module=name,original=str(old),actual=str(target)))
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'artifact-routes.jsonl').open('a') as stream:stream.write(json.dumps(routes)+'\n')


def idle(page):page.wait_for_function('()=>!planApprovalBusy&&!deliveryBusy')


def verify(page,id,adapter):
    page.evaluate("""async({id,adapter})=>{
      await loadServiceCasePlan(id);
      const step=servicePlanView.steps.find(s=>s.adapter_id===adapter);
      document.getElementById('service-plan-reason').value='SYNTHETIC actual Chromium original '+adapter+' VERIFY';
      await servicePlanWrite('VERIFY',step.id);
    }""",dict(id=id,adapter=adapter))
    assert page.evaluate('(a)=>servicePlanView.steps.find(s=>s.adapter_id===a).state',adapter)=='VERIFIED'


@pytest.mark.parametrize('mode',['positive','lost_commit','lost_propose','lost_approve'])
def test_actual_installed_chromium_explicit_source_reapproval_to_six_goals(facts_case,mode):
    t=facts_case;f,p=t['f'],t['p']
    # Original HTTP source refresh/ADOPT/P1 prerequisites, no filled Case cloning.
    source_adopt(t);hs,data=fresh_holds(t);old=original_rows(t);oldplan=deepcopy(stored(f,p));oldledger=deepcopy(ledger(f,p))
    calls=[];pending={};errors=[];controls=html_controls(t,{})
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        ctx=browser.new_context();page=ctx.new_page()
        def on_request(request):
            row=dict(method=request.method,path=urlsplit(request.url).path,status=None)
            # Register before header_value can yield to a fast response callback.
            calls.append(row);pending[request]=row
            key=request.header_value('idempotency-key')
            if key:row['request_key']=key
        def on_response(response):
            if response.request in pending:pending[response.request]['status']=response.status
        page.on('request',on_request);page.on('response',on_response);page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(str(f[3].base_url).rstrip('/')+'/');open_resources(page,f);choose(page,hs)
            page.locator('#delivery-case').fill(p['preparation_id'])
            assert page.locator('#delivery-reapproval').is_enabled()
            page.locator('#delivery-reapproval').check()
            page.locator('#plan-approval-read').click();idle(page)
            page.locator('#delivery-preview').click();page.wait_for_function('()=>deliveryQuote!==null')
            assert page.evaluate('deliveryQuote.view.expected_link_revision')==1
            assert page.locator('#delivery-confirm').is_disabled()
            assert not any(c['method']=='POST' and c['path'].endswith('/resource-delivery') for c in calls)
            def lose_approval(action):
                def handler(route):
                    response=route.fetch()
                    pending[route.request]['status']=response.status
                    pending[route.request]['approval_response_controlled_lost']=action
                    assert response.status==(201 if action=='PROPOSE' else 200)
                    route.abort('failed')
                return handler
            def cold_approval(action):
                page.wait_for_function('()=>planApprovalHandles()?.length===1')
                assert page.evaluate("planApprovalHandles().every(h=>Object.keys(JSON.parse(localStorage.getItem(h.name))).sort().join(',')==='action,actor,approval_id,expires,id,key,revision,started,v')")
                saved=page.evaluate('planApprovalHandles().map(h=>({key:h.key,action:h.action}))[0]')
                assert saved['action']==action
                count=len(calls);page.reload();open_resources(page,f);page.locator('#delivery-case').fill(p['preparation_id'])
                page.locator('#plan-approval-recover').click();idle(page);page.wait_for_function('()=>planApprovalHandles()?.length===0')
                assert all(c['method']=='GET' for c in calls[count:])
                assert any(c['path'].endswith('/plan-approval/recovery/'+saved['key']) and c['status']==200 for c in calls[count:])
                assert not page.locator('#delivery-reapproval').is_checked()
                assert page.evaluate('planApprovalSelected.current===false&&planApprovalSelected.delivery===null&&deliveryQuote===null')
                # Explicitly choose original HELD members and new profile again.
                choose(page,hs);page.locator('#delivery-reapproval').check()
                page.locator('#plan-approval-read').click();idle(page)
                page.wait_for_function('()=>deliveryQuote!==null')
                assert page.evaluate('deliveryQuote.view.expected_link_revision')==1
            if mode=='lost_propose':page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval/proposals',lose_approval('PROPOSE'))
            page.locator('#plan-approval-propose').click();idle(page)
            if mode=='lost_propose':cold_approval('PROPOSE')
            page.wait_for_function('()=>planApprovalSelected?.state==="PROPOSED"')
            assert page.evaluate('planApprovalSelected.purpose')=='CASE_RESOURCE_REAPPROVAL'
            if mode=='lost_approve':page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval/commands',lose_approval('APPROVE'))
            page.locator('#plan-approval-approve').click();idle(page)
            if mode=='lost_approve':cold_approval('APPROVE')
            page.wait_for_function('()=>planApprovalSelected?.current_available===true')
            assert page.locator('#delivery-confirm').is_enabled()
            if mode=='lost_commit':
                def lose(route):
                    response=route.fetch()
                    pending[route.request]['status']=response.status
                    pending[route.request]['committed_response_controlled_lost']=True
                    assert response.status==201
                    route.abort('failed')
                page.route('**/api/preparations/'+p['preparation_id']+'/resource-delivery',lose)
            page.locator('#delivery-confirm').click();idle(page)
            if mode=='lost_commit':
                page.wait_for_function('()=>deliveryHandles()?.length===1')
                assert page.evaluate("deliveryHandles().every(h=>Object.keys(JSON.parse(localStorage.getItem(h.name))).sort().join(',')==='actor,id,key')")
                count=len(calls);page.reload();open_resources(page,f);page.locator('#delivery-case').fill(p['preparation_id'])
                page.locator('#delivery-recover').click();idle(page);page.wait_for_function('()=>deliveryHandles()?.length===0')
                assert all(c['method']=='GET' for c in calls[count:])
                committed=next(c for c in calls if c.get('committed_response_controlled_lost'))
                assert any(c['path'].endswith('/resource-delivery/recovery/'+committed['request_key']) and c['status']==200 for c in calls[count:])
            page.wait_for_function("()=>document.getElementById('delivery-result').dataset.state==='CURRENT'")
            assert effects(f)==[2,6,2,2,2] and states(f,hs)==['CONFIRMED']*3
            assert_prefix_preserved(old,original_rows(t));assert ledger(f,p)['events'][:len(oldledger['events'])]==oldledger['events']
            assert stored(f,p)==oldplan,'resource transaction never auto-verifies P2-P5'
            page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',p['preparation_id'])
            for adapter in ('P2','P3','P4','P5'):
                if adapter!='P2':controls[{'P3':'reoffer_accept','P4':'new_report_ack','P5':'revalidate_local'}[adapter]]()
                verify(page,p['preparation_id'],adapter)
            page.locator('#goal-results-read').click();page.wait_for_function('()=>goalResultView?.state==="LOCAL_OUTPUTS_VERIFIED"')
            assert page.evaluate('goalResultView.results.length')==6
            page.locator('[data-tab="collaboration"]').click()
            with page.expect_response(lambda response:urlsplit(response.url).path=='/api/cases/worklist' and response.status==200):page.locator('#case-worklist-read').click()
            page.wait_for_function('()=>!document.getElementById("case-worklist-read").disabled')
            for _ in range(4):
                if page.locator('#case-worklist-next').is_hidden():break
                with page.expect_response(lambda response:urlsplit(response.url).path=='/api/cases/worklist' and response.status==200):page.locator('#case-worklist-next').click()
                page.wait_for_function('()=>!document.getElementById("case-worklist-next").disabled')
            final(t)
            assert len([c for c in calls if c['method']=='POST' and c['path'].endswith('/resource-delivery') and c['status']==201])==1
            assert len([c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/proposals')])==1
            assert len([c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/commands')])==1
            assert not errors
        finally:
            # Contains no body, Authorization, complete headers, token, screenshot,
            # full DOM or storage values. Original exact key is opaque metadata.
            OUT.mkdir(parents=True,exist_ok=True)
            (OUT/(mode+'-calls.json')).write_text(json.dumps(dict(mode=mode,actual_browser='INSTALLED_CHROMIUM',executable='/usr/bin/chromium',browser_version=browser.version,calls=calls,page_errors=errors,python_control_http_total='NOT_RECORDED',screenshots='NOT_TAKEN',negative_modes='NODE_ONLY',windows='NOT_RUN',formal_at='NOT_RUN'),indent=2)+'\n')
            ctx.close();browser.close()
