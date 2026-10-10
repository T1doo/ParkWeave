import json
from pathlib import Path
from conftest import pg,fixture
from test_service_plan_recovery_browser import goal_page,link_fixture,receipt_fixture,preparation_fixture,prep,open_case,lost,snapshot,wait_held
def test_recovery_response_arriving_after_original_handle_expiry_is_not_accepted(goal_page):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,stored,_=lost(page,f,p,'BEGIN');held=[]
 def hold(route):
  if not route.request.headers.get('idempotency-key'):route.continue_();return
  held.append((route,route.fetch()))
 page.route('**/service-case-plan/command-recovery',hold);before=snapshot(f);page.locator('#service-plan-retry').click();wait_held(page,held);assert held[0][1].status==200;page.evaluate('(expires)=>{Date.now=()=>expires+1}',h['expires']);held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(200);observation=dict(actual_original_key_get_before_expiry=1,response_delivered_after_expiry=True,observed=bool(page.evaluate('servicePlanRecoveryHandle?.observed')),expired_storage_retained=page.evaluate('JSON.stringify({...localStorage})')==stored,business_unchanged=snapshot(f)==before,page_errors=len(errors));Path('/workspace/ParkWeave/.runtime/independent-service-plan-cold-recovery-final-review/inflight-expiry.json').write_text(json.dumps(observation,indent=2)+'\n');assert observation['business_unchanged'] and not errors;assert not observation['observed'],'Recovery response after original 24h handle expiry was accepted'
