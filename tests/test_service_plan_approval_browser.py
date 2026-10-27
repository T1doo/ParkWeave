"""Real original resource page, HTTP and PG Approval cold/reply/privacy checks."""
import json,time
from pathlib import Path
from uuid import uuid4

import pytest
from test_case_resource_delivery_browser import delivery_page, ready_page, settled
from test_service_plan_approval import enable, read, ledger, approved
from test_case_resource_delivery import prepared, effects, quoted
from test_case_resources import link_fixture
from test_preparation import preparation_fixture, headers
from test_executor_receipts import receipt_fixture
from test_resource_bundles import bundle, states
from test_resource_bundles_browser import open_resources, choose

OUT=Path('.runtime/service-plan-approval/browser')


def ready(f,page):
    p=prepared(f);hs,d=bundle(f);enable(f,p)
    open_resources(page,f);choose(page,hs);page.locator('#delivery-case').fill(p['preparation_id'])
    page.locator('#delivery-preview').click();page.wait_for_function('()=>deliveryQuote!==null')
    return p,hs,d


def idle(page):
    page.wait_for_function('()=>!planApprovalBusy&&!deliveryBusy')


def propose_page(page):
    page.locator('#plan-approval-propose').click();idle(page)
    page.wait_for_function('()=>planApprovalSelected?.state==="PROPOSED"')


def approve_page(page):
    propose_page(page);page.locator('#plan-approval-approve').click();idle(page)
    page.wait_for_function('()=>planApprovalSelected?.current_available===true')


def lose(route):
    response=route.fetch();assert response.ok;route.abort('failed')


def test_original_http_page_explicit_proposal_approval_atomic_delivery_and_three_widths(delivery_page):
    f,page,_=delivery_page;p,hs,d=ready(f,page)
    assert page.locator('#delivery-confirm').is_disabled() and effects(f)==[0]*5
    approve_page(page);assert ledger(f,p)['revision']==2 and page.locator('#delivery-confirm').is_enabled()
    OUT.mkdir(parents=True,exist_ok=True)
    for width in (1200,390,320):
        page.set_viewport_size({'width':width,'height':1000});page.locator('#plan-approval-panel').scroll_into_view_if_needed()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(OUT/f'approved-{width}.png'))
    page.locator('#delivery-confirm').click();idle(page)
    page.wait_for_function('()=>document.querySelector("#delivery-result").dataset.state==="CURRENT"')
    assert effects(f)==[1,3,1,1,1] and states(f,hs)==['CONFIRMED']*3 and ledger(f,p)['revision']==3
    assert page.evaluate('planApprovalHandles().length')==0


@pytest.mark.parametrize('action',['PROPOSE','APPROVE','REVOKE'])
def test_committed_lost_approval_response_cold_page_only_get_no_private_storage(delivery_page,action):
    f,page,_=delivery_page;p,hs,d=ready(f,page)
    if action!='PROPOSE':propose_page(page)
    if action=='REVOKE':page.locator('#plan-approval-approve').click();idle(page)
    endpoint='/proposals' if action=='PROPOSE' else '/commands'
    page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval'+endpoint,lose)
    page.locator('#plan-approval-'+action.lower()).click();idle(page)
    assert ledger(f,p)['revision']=={'PROPOSE':1,'APPROVE':2,'REVOKE':3}[action]
    assert page.evaluate('planApprovalHandles().length')==1 and effects(f)==[0]*5
    raw=page.evaluate('JSON.stringify({...localStorage})')
    assert f[2]['fixture-a'] not in raw and 'reason' not in raw and 'members' not in raw and 'binding_sha256' not in raw
    seen=[];page.on('request',lambda r:seen.append((r.method,r.url)));page.reload();open_resources(page,f)
    page.locator('#plan-approval-recover').click();idle(page)
    page.wait_for_function('()=>planApprovalHandles().length===0')
    assert all(method=='GET' for method,url in seen) and effects(f)==[0]*5
    assert page.evaluate('planApprovalSelected.state')=={'PROPOSE':'PROPOSED','APPROVE':'APPROVED','REVOKE':'REVOKED'}[action]


def test_approved_cold_new_page_reads_original_exact_command_then_delivers_once(delivery_page):
    f,page,_=delivery_page;p,hs,d=ready(f,page);approve_page(page)
    before=ledger(f,p);seen=[];page.reload();open_resources(page,f);choose(page,hs);page.locator('#delivery-case').fill(p['preparation_id'])
    page.on('request',lambda r:seen.append((r.method,r.url)));page.locator('#plan-approval-read').click();idle(page)
    page.wait_for_function('()=>planApprovalSelected?.current_available===true')
    assert all(m=='GET' for m,u in seen) and ledger(f,p)==before and page.locator('#delivery-confirm').is_enabled()
    page.locator('#delivery-confirm').click();idle(page);assert effects(f)==[1,3,1,1,1]


def test_source_changed_page_preserves_history_disables_submit_and_explicit_revoke(delivery_page):
    f,page,_=delivery_page;p,hs,d=ready(f,page);approve_page(page);before=ledger(f,p)
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=capacity+1')
    page.locator('#plan-approval-read').click();idle(page)
    assert not page.evaluate('planApprovalSelected.current_available') and page.locator('#delivery-confirm').is_disabled()
    assert ledger(f,p)==before and effects(f)==[0]*5
    page.locator('#plan-approval-revoke').click();idle(page)
    page.wait_for_function('()=>planApprovalSelected?.state==="REVOKED"')
    assert ledger(f,p)['events'][:2]==before['events'] and effects(f)==[0]*5


@pytest.mark.parametrize('status',[200,403])
def test_late_actual_approval_get_does_not_clear_or_fill_other_case_view(delivery_page,status):
    f,page,_=delivery_page;p,hs,d=ready(f,page);approve_page(page);responses=[]
    if status==403:
        with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
    def delay(route):responses.append((route,route.fetch()))
    page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval',delay)
    page.locator('#plan-approval-read').click()
    end=time.monotonic()+10
    while not responses and time.monotonic()<end:page.wait_for_timeout(20)
    assert responses and responses[0][1].status==status
    page.locator('#delivery-case').fill(str(uuid4()))
    page.evaluate('document.querySelector("#plan-approval-result").textContent="NEW CASE VIEW"')
    route,response=responses.pop();route.fulfill(response=response);idle(page)
    assert page.locator('#plan-approval-result').inner_text()=='NEW CASE VIEW' and effects(f)==[0]*5


def test_current_revocation_clears_private_approval_and_resource_dom(delivery_page):
    f,page,_=delivery_page;p,hs,d=ready(f,page);approve_page(page)
    with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='READ'")
    page.locator('#plan-approval-read').click();idle(page)
    assert page.locator('#plan-approval-result').inner_text()=='' and page.locator('#resource-hold-items').inner_text()==''
    assert page.evaluate('planApprovalView===null&&planApprovalSelected===null&&deliveryQuote===null') and effects(f)==[0]*5


@pytest.mark.parametrize('damage',['extra-private-field','wrong-action','not-observed','stored-replacement'])
def test_bad_or_changed_original_handle_never_accepts_proof_or_posts(delivery_page,damage):
    f,page,_=delivery_page;p,hs,d=ready(f,page);page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval/proposals',lose)
    page.locator('#plan-approval-propose').click();idle(page);h=page.evaluate('planApprovalHandles()[0]');before=ledger(f,p)
    if damage=='extra-private-field':
        page.evaluate('h=>{const x=JSON.parse(h.raw);x.reason="PRIVATE";localStorage.setItem(h.name,JSON.stringify(x));}',h)
    elif damage=='wrong-action':
        page.evaluate('h=>{const x=JSON.parse(h.raw);x.action="APPROVE";x.approval_id=crypto.randomUUID();localStorage.setItem(h.name,JSON.stringify(x));}',h)
    elif damage=='not-observed':
        page.evaluate('h=>{const x=JSON.parse(h.raw);localStorage.removeItem(h.name);x.key=crypto.randomUUID();localStorage.setItem(planApprovalStorage+x.actor+"."+x.key,JSON.stringify(x));}',h)
    else:
        def replace(route):
            response=route.fetch()
            page.evaluate('h=>{const x=JSON.parse(h.raw);x.revision+=1;localStorage.setItem(h.name,JSON.stringify(x));}',h)
            route.fulfill(response=response)
        page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval/recovery/*',replace)
    seen=[];page.on('request',lambda r:seen.append((r.method,r.url)));page.locator('#plan-approval-recover').click();idle(page)
    assert all(m=='GET' for m,u in seen) and ledger(f,p)==before and effects(f)==[0]*5
    assert page.locator('#plan-approval-result').inner_text()=='' and page.locator('#delivery-confirm').is_disabled()


def test_delivery_lost_reply_with_approval_consumption_recovers_only_original_get(delivery_page):
    f,page,_=delivery_page;p,hs,d=ready(f,page);approve_page(page)
    page.route('**/api/preparations/'+p['preparation_id']+'/resource-delivery',lose)
    page.locator('#delivery-confirm').click();idle(page)
    assert effects(f)==[1,3,1,1,1] and ledger(f,p)['revision']==3
    seen=[];page.reload();open_resources(page,f);page.on('request',lambda r:seen.append((r.method,r.url)))
    page.locator('#delivery-recover').click();idle(page)
    page.wait_for_function('()=>deliveryHandles().length===0')
    assert all(m=='GET' for m,u in seen) and effects(f)==[1,3,1,1,1] and ledger(f,p)['revision']==3
