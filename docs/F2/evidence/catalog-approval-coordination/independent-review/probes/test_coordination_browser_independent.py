"""Real loopback HTTP unknown replies across explicit catalog generations."""
from copy import deepcopy
from pathlib import Path
import pytest
from test_service_plan_approval_browser import delivery_page,idle,propose_page,lose
from test_service_plan_approval import link_fixture,receipt_fixture,preparation_fixture,ledger
from test_catalog_approval_coordination import setup,publish,catalog
from test_case_resource_delivery import effects,recover
from test_resource_bundles import states
from test_resource_bundles_browser import open_resources,choose
from test_case_resource_delivery_browser import settled
OUT=Path('.runtime/independent-catalog-approval-coordination-final-review/browser-extra')

def coordinated(f,page):
    p,hs,data,bridge,protocol=setup(f)
    open_resources(page,f);choose(page,hs);page.locator('#delivery-case').fill(p['preparation_id']);page.locator('#delivery-preview').click();page.wait_for_function('()=>deliveryQuote!==null')
    return p,hs,protocol

def parent_state(f,p):
    with f[1].connect() as c:return c.execute('SELECT service_case_plan,candidate_plan_approvals,candidate_plan_approval_head FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()

@pytest.mark.parametrize('action',['PROPOSE','APPROVE','REVOKE'])
@pytest.mark.parametrize('generation',['same_source','ABA'])
def test_committed_unknown_reply_then_publication_cold_get_preserves_original_only(delivery_page,action,generation):
    f,page,errors=delivery_page;p,hs,protocol=coordinated(f,page)
    if action!='PROPOSE':propose_page(page)
    if action=='REVOKE':page.locator('#plan-approval-approve').click();idle(page)
    endpoint='proposals' if action=='PROPOSE' else 'commands'
    page.route('**/api/preparations/'+p['preparation_id']+'/plan-approval/'+endpoint,lose)
    page.locator('#plan-approval-'+action.lower()).click();idle(page)
    assert page.evaluate('planApprovalHandles().length')==1
    original=deepcopy(ledger(f,p));stored=page.evaluate('JSON.stringify({...localStorage})')
    assert f[2]['fixture-a'] not in stored and 'members' not in stored and 'binding_sha256' not in stored and 'reason' not in stored
    if generation=='same_source':publish(protocol,p,source_revision=1)
    else:publish(protocol,p);publish(protocol,p,revision=2,source_revision=1)
    before=parent_state(f,p);source=catalog(f,p);requests=[];page.on('request',lambda r:requests.append(r.method))
    page.reload();open_resources(page,f);page.locator('#plan-approval-recover').click();idle(page);page.wait_for_function('()=>planApprovalHandles().length===0')
    assert set(requests)=={'GET'}
    assert page.evaluate('planApprovalSelected.state')=={'PROPOSE':'PROPOSED','APPROVE':'APPROVED','REVOKE':'REVOKED'}[action]
    assert not page.evaluate('planApprovalSelected.current_available') and page.locator('#delivery-confirm').is_disabled()
    assert ledger(f,p)==original and parent_state(f,p)==before and catalog(f,p)==source and effects(f)==[0]*5 and states(f,hs)==['HELD']*3 and not errors


def test_consumed_delivery_unknown_then_withdraw_cold_get_retains_actual_history(delivery_page):
    f,page,errors=delivery_page;p,hs,protocol=coordinated(f,page)
    propose_page(page);page.locator('#plan-approval-approve').click();idle(page);page.wait_for_function('()=>planApprovalSelected?.current_available')
    page.route('**/api/preparations/'+p['preparation_id']+'/resource-delivery',lose)
    page.locator('#delivery-confirm').click();settled(page);handle=page.evaluate('deliveryHandles()[0]');assert handle and effects(f)==[1,3,1,1,1]
    original=deepcopy(ledger(f,p));before_receipt=recover(f,p,handle['key']).json()['receipt'];publish(protocol,p,action='WITHDRAW')
    before=parent_state(f,p);source=catalog(f,p);requests=[];page.on('request',lambda r:requests.append(r.method))
    page.reload();open_resources(page,f);page.locator('#delivery-recover').click();settled(page);page.wait_for_function('()=>deliveryHandles().length===0')
    assert set(requests)=={'GET'} and page.locator('#delivery-result').get_attribute('data-state')=='NEEDS_RECHECK'
    result=recover(f,p,handle['key']);assert result.status_code==200 and result.json()['receipt']==before_receipt and result.json()['independent_check']['status']=='NEEDS_RECHECK'
    assert ledger(f,p)==original and parent_state(f,p)==before and catalog(f,p)==source and effects(f)==[1,3,1,1,1] and states(f,hs)==['CONFIRMED']*3 and not errors
    OUT.mkdir(parents=True,exist_ok=True);page.set_viewport_size({'width':390,'height':1000});page.locator('#delivery-result').scroll_into_view_if_needed();page.screenshot(path=str(OUT/'withdrawn-cold-history-390.png'))
