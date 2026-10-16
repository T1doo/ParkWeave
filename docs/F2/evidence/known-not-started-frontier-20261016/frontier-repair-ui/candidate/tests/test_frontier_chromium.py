"""Narrow installed Chromium new-plan approval; native Windows/formal AT not run."""
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4
import pytest
from playwright.sync_api import sync_playwright
from parkweave.api import create_app
from test_new_enterprise_local_chain import actual_http
from frontier_fixture_support import frontier_case,capability_resource_catalog,capability_catalog,preparation_fixture,receipt_fixture
from test_service_case_steps import verified
from test_service_plan_manual_lock import stored
from test_resource_bundles import bundle,states
from test_resource_bundles_browser import open_resources,choose
from test_case_resource_delivery import effects,recover
from test_service_plan_approval import ledger
from test_case_lifecycle import read as localread,act as localact
from test_frontier_real_html import route_helper_artifacts
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.runtime/frontier-chromium'

def idle(page):page.wait_for_function('()=>!planApprovalBusy&&!deliveryBusy')


def choose_frontier(page):
 assert not page.locator('#delivery-frontier').is_checked()
 page.locator('#delivery-plan-replacement').check()
 assert page.locator('#delivery-frontier').is_enabled()
 page.locator('#delivery-frontier').check()


def verify(page,id,adapter):
 page.evaluate("""async({id,adapter})=>{
  await loadServiceCasePlan(id);
  const step=servicePlanView.steps.find(s=>s.adapter_id===adapter);
  document.getElementById('service-plan-reason').value='SYNTHETIC actual Chromium original '+adapter+' VERIFY';
  await servicePlanWrite('VERIFY',step.id);
 }""",dict(id=id,adapter=adapter))
 assert page.evaluate('(a)=>servicePlanView.steps.find(s=>s.adapter_id===a).state',adapter)=='VERIFIED'


@pytest.mark.parametrize('mode',['positive','lost_commit','lost_propose','lost_approve'])
def test_actual_installed_chromium_known_not_started_frontier(frontier_case,mode):
 t=frontier_case;f,p=t['f'],t['p'];assert next(s for s in t['new']['steps'] if s['adapter_id']=='P1')['coordination_state']=='VERIFIED';hs,data=bundle(f);plan=deepcopy(stored(f,p));oldledger=deepcopy(ledger(f,p));calls=[];pending={};errors=[]
 with actual_http(create_app(f[0])) as (client,requests):
  f=(*f[:3],client)
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx=browser.new_context();page=ctx.new_page()
   def requested(request):
    row=dict(method=request.method,path=urlsplit(request.url).path,status=None);calls.append(row);pending[request]=row
    key=request.header_value('idempotency-key')
    if key:row['request_key']=key
   def responded(response):
    if response.request in pending:pending[response.request]['status']=response.status
   page.on('request',requested);page.on('response',responded);page.on('pageerror',lambda e:errors.append(str(e)))
   try:
    page.goto(str(client.base_url).rstrip('/')+'/');open_resources(page,f);choose(page,hs);page.locator('#delivery-case').fill(p['preparation_id']);assert page.locator('#delivery-plan-replacement').is_enabled();choose_frontier(page);page.locator('#plan-approval-read').click();idle(page);page.locator('#delivery-preview').click();page.wait_for_function('()=>deliveryQuote!==null')
    assert page.evaluate('deliveryQuote.view.expected_previous_plan_id')==t['old']['id'] and page.evaluate('deliveryQuote.view.context.plan_id')==t['new']['id'];assert page.locator('#delivery-confirm').is_disabled();assert page.evaluate('deliveryQuote.view.replacement_frontier_profile')=='KNOWN_NOT_STARTED_V1';assert page.evaluate('deliveryQuote.view.context.plan_replacement.compatibility.schema')==2
    def lose(action):
     def handler(route):
      response=route.fetch();pending[route.request]['status']=response.status;pending[route.request]['controlled_lost_response']=action;assert response.status==(200 if action=='APPROVE' else 201);route.abort('failed')
     return handler
    def cold_approval(action):
     page.wait_for_function('()=>planApprovalHandles()?.length===1');saved=page.evaluate('planApprovalHandles().map(h=>({key:h.key,action:h.action}))[0]');assert saved['action']==action;count=len(calls);page.reload();open_resources(page,f);page.locator('#delivery-case').fill(p['preparation_id']);page.locator('#plan-approval-recover').click();idle(page);page.wait_for_function('()=>planApprovalHandles()?.length===0');assert all(c['method']=='GET' for c in calls[count:]);assert any(c['path'].endswith('/plan-approval/recovery/'+saved['key']) and c['status']==200 for c in calls[count:]);assert not page.locator('#delivery-plan-replacement').is_checked();assert not page.locator('#delivery-frontier').is_checked();assert page.evaluate('deliveryQuote===null&&planApprovalSelected.current===false');choose(page,hs);choose_frontier(page);page.locator('#plan-approval-read').click();idle(page);page.wait_for_function('()=>deliveryQuote!==null')
    if mode=='lost_propose':page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval/proposals',lose('PROPOSE'))
    page.locator('#plan-approval-propose').click();idle(page)
    if mode=='lost_propose':cold_approval('PROPOSE')
    page.wait_for_function('()=>planApprovalSelected?.state==="PROPOSED"');assert page.evaluate('planApprovalSelected.purpose')=='CASE_RESOURCE_PLAN_REPLACEMENT'
    if mode=='lost_approve':page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval/commands',lose('APPROVE'))
    page.locator('#plan-approval-approve').click();idle(page)
    if mode=='lost_approve':cold_approval('APPROVE')
    page.wait_for_function('()=>planApprovalSelected?.current_available===true');assert page.locator('#delivery-confirm').is_enabled()
    if mode=='lost_commit':page.route('**/api/preparations/'+p['preparation_id']+'/resource-delivery',lose('COMMIT'))
    page.locator('#delivery-confirm').click();idle(page)
    if mode=='lost_commit':
     page.wait_for_function('()=>deliveryHandles()?.length===1');assert page.evaluate("deliveryHandles().every(h=>Object.keys(JSON.parse(localStorage.getItem(h.name))).sort().join(',')==='actor,id,key')");count=len(calls);page.reload();open_resources(page,f);page.locator('#delivery-case').fill(p['preparation_id']);page.locator('#delivery-recover').click();idle(page);page.wait_for_function('()=>deliveryHandles()?.length===0');assert all(c['method']=='GET' for c in calls[count:]);post=next(c for c in calls if c.get('controlled_lost_response')=='COMMIT');assert any(c['path'].endswith('/resource-delivery/recovery/'+post['request_key']) and c['status']==200 for c in calls[count:])
    page.wait_for_function("()=>document.getElementById('delivery-result').dataset.state==='CURRENT'");assert effects(f)==[2,6,2,2,2] and states(f,hs)==['CONFIRMED']*3 and stored(f,p)==plan;assert ledger(f,p)['events'][:3]==oldledger['events']
    new_post=next(c for c in calls if c['method']=='POST' and c['path'].endswith('/resource-delivery') and c['status']==201)
    initial=recover(f,p,new_post['request_key']);assert initial.status_code==200,initial.text
    original_new_receipt=deepcopy(initial.json()['receipt'])
    page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',p['preparation_id'])
    for node in ('P2','P3','P4','P5'):
     if node=='P3':
      from test_service_dispatches import offer,command as dispatch_command
      from test_preparation import headers
      q=f[3].get('/api/service-dispatches/catalog?preparation_id='+p['preparation_id'],headers=headers(f[2],'prep-specialist-fixture-a'));assert q.status_code==200,q.text
      r=offer(f,p,expected_business_frontier=q.json()['business_frontier'])[0];assert r.status_code==201,r.text
      current=f[3].get('/api/service-dispatches/'+r.json()['dispatch_id'],headers=headers(f[2],'executor-a'));assert current.status_code==200,current.text
      accepted=dispatch_command(f,current.json(),'ACCEPT',expected_business_frontier=current.json()['business_frontier']);assert accepted.status_code==200,accepted.text
     if node=='P4':
      from test_executor_receipts import act as receipt
      sr=f[3].get('/api/executor-receipts/'+accepted.json()['receipt_step_id'],headers=headers(f[2],'executor-a'));assert sr.status_code==200,sr.text
      sr=receipt(f,sr.json(),'SUBMIT',expected_business_frontier=sr.json()['business_frontier']);assert sr.status_code==200,sr.text
      sr=f[3].get('/api/executor-receipts/'+accepted.json()['receipt_step_id'],headers=headers(f[2]));assert sr.status_code==200,sr.text
      sr=receipt(f,sr.json(),'ACKNOWLEDGE',expected_business_frontier=sr.json()['business_frontier']);assert sr.status_code==200,sr.text
     if node=='P5':
      current=localread(f,p);assert current.status_code==200,current.text
      assert localact(f,p,current.json(),'REVALIDATE',expected_business_frontier=current.json()['business_frontier']).status_code==200
     verify(page,p['preparation_id'],node)
    page.locator('#goal-results-read').click();page.wait_for_function('()=>goalResultView?.state==="LOCAL_OUTPUTS_VERIFIED"');assert page.evaluate('goalResultView.results.length')==6
    page.locator('[data-tab="collaboration"]').click()
    with page.expect_response(lambda response:urlsplit(response.url).path=='/api/cases/worklist' and response.status==200):page.locator('#case-worklist-read').click()
    recovered=page.evaluate('async({id,key})=>await apiCall("/api/preparations/"+id+"/resource-delivery/recovery/"+key)',dict(id=p['preparation_id'],key=new_post['request_key']))
    assert recovered['receipt']==original_new_receipt and recovered['independent_check']['status']=='CURRENT'
    old=recover(f,p,t['oldreceipt']['delivery_binding']['request_key']);assert old.status_code==200 and old.json()['receipt']==t['oldreceipt']['receipt'] and old.json()['independent_check']['status']=='NEEDS_RECHECK'
    assert len([c for c in calls if c['method']=='POST' and c['path'].endswith('/resource-delivery') and c['status']==201])==1
    assert len([c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/proposals')])==1 and len([c for c in calls if c['method']=='POST' and c['path'].endswith('/plan-approval/commands')])==1
    assert not errors
   finally:
    OUT.mkdir(parents=True,exist_ok=True);(OUT/(mode+'-'+uuid4().hex[:8]+'.json')).write_text(json.dumps(dict(mode=mode,browser_version=browser.version,actual_browser='INSTALLED_CHROMIUM',calls=calls,page_errors=errors,python_http_requests=requests,python_prerequisites=['birth-tracked V4 old P1/P2 only and new plan','catalog-change original REOPEN REVIEW CONFIRM','whole ADOPT','new P1 VERIFY','new dispatch OFFER ACCEPT','new receipt SUBMIT ACK','P5 REVALIDATE'],windows='NOT_RUN',formal_at='NOT_RUN'),indent=2)+'\n');ctx.close();browser.close()
