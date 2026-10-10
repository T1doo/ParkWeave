"""Actual HTTP browser oracles independent of candidate recovery internals."""
from pathlib import Path
from uuid import uuid4
import time
import pytest
from test_service_plan_approval_browser import delivery_page,ready,propose_page,approve_page,idle,lose
from test_service_plan_approval import (link_fixture,receipt_fixture,preparation_fixture,ledger)
from test_case_resource_delivery import effects,prepared
from test_resource_bundles_browser import open_resources
OUT=Path('.runtime/independent-service-plan-approval-review/browser-extra')

def held_response(page,held):
    end=time.monotonic()+10
    while not held and time.monotonic()<end:page.wait_for_timeout(20)
    assert held

@pytest.mark.parametrize('action',['PROPOSE','APPROVE','REVOKE'])
@pytest.mark.parametrize('target',['case','identity'])
def test_late_committed_original_post_keeps_new_context_and_original_opaque_handle(delivery_page,action,target):
    f,page,errors=delivery_page;p,hs,d=ready(f,page)
    if action!='PROPOSE':propose_page(page)
    if action=='REVOKE':page.locator('#plan-approval-approve').click();idle(page)
    endpoint='proposals' if action=='PROPOSE' else 'commands';held=[]
    def hold(route):
        r=route.fetch();assert r.ok;held.append((route,r))
    page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval/'+endpoint,hold)
    page.locator('#plan-approval-'+action.lower()).click();held_response(page,held)
    old=ledger(f,p);storage=page.evaluate('JSON.stringify({...localStorage})')
    if target=='case':page.locator('#delivery-case').fill(str(uuid4()))
    else:page.locator('#token').fill(f[2]['fixture-b']);page.locator('#token').dispatch_event('input')
    page.locator('#plan-approval-result').evaluate('(el)=>el.textContent="SYNTHETIC NEW ORIGINAL CONTEXT"')
    held[0][0].fulfill(response=held[0][1]);page.wait_for_timeout(100)
    assert page.locator('#plan-approval-result').inner_text()=='SYNTHETIC NEW ORIGINAL CONTEXT'
    assert page.evaluate('planApprovalView===null&&planApprovalSelected===null')
    assert page.evaluate('JSON.stringify({...localStorage})')==storage and ledger(f,p)==old and effects(f)==[0]*5 and not errors

def test_recovery_handle_expires_during_actual_http_wait_and_cannot_fill_current_view(delivery_page):
    f,page,errors=delivery_page;p,hs,d=ready(f,page)
    pattern='**/api/preparations/'+p['preparation_id']+'/plan-approval/proposals'
    page.route(pattern,lose);page.locator('#plan-approval-propose').click();idle(page);h=page.evaluate('planApprovalHandles()[0]')
    original=ledger(f,p);storage=page.evaluate('JSON.stringify({...localStorage})');held=[]
    def hold(route):
        r=route.fetch();assert r.status==200;held.append((route,r))
    page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval/recovery/*',hold)
    requests=[];page.on('request',lambda r:requests.append(r.method))
    page.locator('#plan-approval-recover').click();held_response(page,held)
    page.evaluate('(deadline)=>Date.now=()=>deadline',h['expires'])
    held[0][0].fulfill(response=held[0][1]);idle(page)
    assert page.evaluate('planApprovalView===null&&planApprovalSelected===null&&deliveryQuote===null')
    assert page.locator('#plan-approval-result').inner_text()=='' and page.locator('#delivery-confirm').is_disabled()
    assert set(requests)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==storage
    assert ledger(f,p)==original and effects(f)==[0]*5 and not errors

def test_storage_failure_refuses_proposal_before_post_and_keeps_business_unchanged(delivery_page):
    f,page,errors=delivery_page;p,hs,d=ready(f,page);requests=[];page.on('request',lambda r:requests.append(r.method))
    page.evaluate('()=>{Storage.prototype.setItem=function(){throw Error("SYNTHETIC STORAGE UNAVAILABLE")}}')
    page.locator('#plan-approval-propose').click();idle(page)
    assert 'POST' not in requests and ledger(f,p) is None and effects(f)==[0]*5
    assert page.evaluate('planApprovalView===null&&planApprovalSelected===null&&deliveryQuote===null') and not errors
