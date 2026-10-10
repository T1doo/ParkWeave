import json
from pathlib import Path
from uuid import uuid4
import pytest
from conftest import pg,fixture
from test_service_plan_recovery_browser import goal_page,link_fixture,receipt_fixture,preparation_fixture,prep,open_case,lost,wait_recovered,wait_held,snapshot,setup,adopt,GOALS

@pytest.mark.parametrize('source',['BEGIN','VERIFY'])
def test_invalid_handle_retained_view_has_no_previous_command_private_event(goal_page,source):
 f,page,errors=goal_page;p=setup(f,GOALS[1] if source=='VERIFY' else GOALS[0]);assert adopt(f,p).status_code==201;open_case(page,f,p);page.locator('#service-plan-reason').fill('SYNTHETIC INDEPENDENT_PREVIOUS_EVENT_PRIVATE');page.locator('[data-service-action="'+source+'"]').first.click();page.wait_for_function('()=>servicePlanPending===null&&servicePlanView.revision===2');assert page.evaluate('servicePlanView.event.reason')=='SYNTHETIC INDEPENDENT_PREVIOUS_EVENT_PRIVATE';action='BEGIN' if source=='VERIFY' else 'REPORT_FAILURE';h,_,_=lost(page,f,p,action);before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.evaluate('(expires)=>{Date.now=()=>expires+1}',h['expires']);page.locator('#service-plan-retry').click();page.wait_for_function('()=>servicePlanRecoveryHandle===null&&servicePlanPending===null');x=page.evaluate('servicePlanView');private_in_event=bool(x.get('event') and x['event'].get('reason')=='SYNTHETIC INDEPENDENT_PREVIOUS_EVENT_PRIVATE');observation=dict(previous_action=source,recovery_view_readonly=x['read_only'],old_pending_removed=True,previous_raw_event_retained=private_in_event,previous_raw_sources_retained=bool(x.get('event') and x['event'].get('sources')),posts=requests.count('POST'),get_count=requests.count('GET'),business_unchanged=snapshot(f)==before,page_errors=len(errors));Path('/workspace/ParkWeave/.runtime/independent-service-plan-cold-recovery-complete-review/event-privacy-'+source+'.json').write_text(json.dumps(observation,indent=2)+'\n');assert snapshot(f)==before and requests==[] and not errors;assert not private_in_event,'Expired-handle minimal read-only view retained previous command reason in raw event';assert x.get('event') is None

@pytest.mark.parametrize('entry',['retry','release'])
@pytest.mark.parametrize('storage',['missing','changed'])
def test_hot_missing_or_changed_storage_no_get_or_delete_replacement(goal_page,entry,storage):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,_,_=lost(page,f,p,'BEGIN')
 if entry=='release':page.locator('#service-plan-retry').click();wait_recovered(page)
 name=page.evaluate('(h)=>servicePlanRecoveryName(h)',h)
 if storage=='missing':page.evaluate('(name)=>localStorage.removeItem(name)',name)
 else:page.evaluate('([name,h])=>localStorage.setItem(name,JSON.stringify({...h,key:crypto.randomUUID()}))',[name,h])
 raw=page.evaluate('JSON.stringify({...localStorage})');before=snapshot(f);requests=[];page.on('request',lambda r:requests.append(r.method));page.evaluate('()=>document.getElementById("service-plan-reason").value="SYNTHETIC preserve new draft"');page.locator('#service-plan-'+entry).click();page.wait_for_function('()=>servicePlanRecoveryHandle===null&&servicePlanPending===null');assert requests==[] and snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==raw and page.locator('#service-plan-reason').input_value()=='SYNTHETIC preserve new draft' and page.evaluate('servicePlanView.read_only') and not errors

@pytest.mark.parametrize('status',[200,403])
def test_changed_stored_handle_during_actual_get_and_current403_priority(goal_page,status):
 f,page,errors=goal_page;p=prep(f,'BEGIN');open_case(page,f,p);h,_,_=lost(page,f,p,'BEGIN');held=[]
 def hold(route):
  if not route.request.headers.get('idempotency-key'):route.continue_();return
  held.append((route,None if status==403 else route.fetch()))
 page.route('**/service-case-plan/command-recovery',hold);page.locator('#service-plan-retry').click();wait_held(page,held);name=page.evaluate('(h)=>servicePlanRecoveryName(h)',h);page.evaluate('([name,h])=>localStorage.setItem(name,JSON.stringify({...h,key:crypto.randomUUID()}))',[name,h]);stored=page.evaluate('JSON.stringify({...localStorage})')
 if status==403:
  with f[1].connect() as c:f[1].lock_principal(c,'fixture-a',exclusive=True);c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
 before=snapshot(f);route,r=held[0];r=r or route.fetch();assert r.status==status;route.fulfill(response=r);page.wait_for_function('()=>servicePlanRecoveryHandle===null&&!servicePlanRecoveryChecking');assert snapshot(f)==before and page.evaluate('JSON.stringify({...localStorage})')==stored and not errors
 if status==403:assert page.evaluate('servicePlanView') is None and page.locator('#service-plan-reason').input_value()=='' and page.locator('#service-case-plan-detail').is_hidden()
 else:assert page.evaluate('servicePlanView.read_only') and not page.evaluate('servicePlanView.command_receipt')
