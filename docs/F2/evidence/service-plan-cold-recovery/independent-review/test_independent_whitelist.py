import json
from uuid import uuid4
import pytest
from conftest import pg,fixture
from test_service_plan_recovery_browser import goal_page,link_fixture,receipt_fixture,preparation_fixture,prep,open_case,lost,wait_recovered,wait_held,snapshot

@pytest.mark.parametrize('storage',['expired','missing','changed'])
def test_invalid_projection_drops_unlisted_view_step_event_history_properties(goal_page,storage):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,_,_=lost(page,f,p,'BEGIN');page.evaluate('()=>{const x=servicePlanView;x.observations={text:"SYNTHETIC INDEPENDENT_PRIVATE_UNLISTED"};x.binding_issues=["SYNTHETIC INDEPENDENT_PRIVATE_UNLISTED"];x.private_body="SYNTHETIC INDEPENDENT_PRIVATE_UNLISTED";x.event={reason:"SYNTHETIC INDEPENDENT_PRIVATE_UNLISTED",sources:{body:"SYNTHETIC INDEPENDENT_PRIVATE_UNLISTED"}};for(const s of x.steps){s.future_source_body="SYNTHETIC INDEPENDENT_PRIVATE_UNLISTED";s.verified_sources={text:"SYNTHETIC INDEPENDENT_PRIVATE_UNLISTED"};}for(const e of x.events)e.future_body="SYNTHETIC INDEPENDENT_PRIVATE_UNLISTED";x.history.push({id:crypto.randomUUID(),revision:1,body:"SYNTHETIC INDEPENDENT_PRIVATE_UNLISTED"});document.getElementById("service-plan-reason").value="SYNTHETIC new private unsent draft";}');name=page.evaluate('(h)=>servicePlanRecoveryName(h)',h)
 if storage=='expired':page.evaluate('(expires)=>{Date.now=()=>expires+1}',h['expires'])
 elif storage=='missing':page.evaluate('(name)=>localStorage.removeItem(name)',name)
 else:page.evaluate('([name,h])=>localStorage.setItem(name,JSON.stringify({...h,key:crypto.randomUUID()}))',[name,h])
 stored=page.evaluate('JSON.stringify({...localStorage})');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.locator('#service-plan-retry').click();page.wait_for_function('()=>servicePlanRecoveryHandle===null&&servicePlanPending===null');x=page.evaluate('servicePlanView');assert 'INDEPENDENT_PRIVATE_UNLISTED' not in json.dumps(x) and x['event'] is None and x['binding_issues'] is None and x['case_goal_completed'] is False and x['new_grants'] is False and x['automatic_execution'] is False and x['read_only'];assert all(set(s)=={'id','adapter_id','adapter','depends_on','state','actual_business_state','allowed_actions','source_sha256','verified_sources','verified_sha256','issues'} for s in x['steps']);assert all(set(e)=={'id','revision','action','step_id'} for e in x['events']) and all(set(h)=={'id','revision'} for h in x['history']);assert page.locator('#service-plan-reason').input_value()=='SYNTHETIC new private unsent draft' and snapshot(f)==before and requests==[] and not errors;assert page.evaluate('JSON.stringify({...localStorage})')==(stored if storage=='changed' else '{}')

def test_valid_same_handle_gets_never_renew_expiry_or_submit_body(goal_page):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,stored,_=lost(page,f,p,'BEGIN');page.evaluate('()=>{window.actualRecoveryNow=Date.now;Date.now=()=>actualRecoveryNow()+1000}');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append((r.method,r.headers.get('idempotency-key'))))
 for i in range(3):page.locator('#service-plan-retry').click();wait_recovered(page);assert page.evaluate('servicePlanRecoveryHandle.expires')==h['expires'] and page.evaluate('JSON.stringify({...localStorage})')==stored and snapshot(f)==before
 assert requests and all(method=='GET' and key==h['key'] for method,key in requests) and not errors

def test_actual_original_post403_beats_expired_handle_and_clears_private_memory(goal_page):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);held=[]
 def hold(route):
  if route.request.method!='POST':route.continue_();return
  held.append(route)
 page.route('**/service-case-plan/commands',hold);page.locator('#service-plan-reason').fill('SYNTHETIC INDEPENDENT_PRIVATE_PENDING_POST');page.locator('[data-service-action="BEGIN"]').click();wait_held(page,held);h=page.evaluate('servicePlanRecoveryHandle');page.evaluate('(expires)=>{Date.now=()=>expires+1}',h['expires']);stored=page.evaluate('JSON.stringify({...localStorage})')
 with f[1].connect() as c:f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
 before=snapshot(f);r=held[0].fetch();assert r.status==403;held[0].fulfill(response=r);page.wait_for_function('()=>servicePlanView===null&&servicePlanPending===null');assert page.locator('#service-case-plan-detail').is_hidden() and page.locator('#service-plan-reason').input_value()=='' and page.evaluate('JSON.stringify({...localStorage})')==stored and snapshot(f)==before and not errors
