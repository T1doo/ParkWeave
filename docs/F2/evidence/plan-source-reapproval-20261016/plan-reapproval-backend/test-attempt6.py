"""Real owned PostgreSQL/API minimal after-link approval continuation."""
from uuid import uuid4
from copy import deepcopy
import pytest
from parkweave import service_plan_approval as approvals
from parkweave.store import Denied
from test_case_resources import link_fixture,post as direct_bind
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from test_case_resource_delivery import prepared,quoted,submit,recover,effects,preview as delivery_preview
from test_resource_bundles import bundle,states
from test_service_plan_approval import enable,ledger,propose,decide
from test_service_case_steps import verified,adopt
from test_source_change_adoption import changed,preview as source_preview
from test_service_plan_manual_lock import stored


def approved(f,p,data):
    value=ledger(f,p);revision=value['revision'] if value else 0
    response=propose(f,p,data,revision=revision);assert response.status_code==201,response.text
    view=response.json();response=decide(f,p,view['items'][-1],view['revision']);assert response.status_code==200,response.text
    view=response.json();return view['items'][-1],view


def first(f,*,flag=True):
    p=prepared(f);hs,d=bundle(f)
    bridge=enable(f,p,enabled_for_source_reapproval_tests=flag)
    data=quoted(f,p,d);item,_=approved(f,p,data);key=uuid4().hex
    r=submit(f,p,{**data,'approval_id':item['id']},key);assert r.status_code==201,r.text
    verified(f,p,'P2')
    return p,r.json(),bridge


def source_adopt(f,p):
    card=changed(f,p);q=source_preview(f,p,card);assert q.status_code==200,q.text
    assert q.json()['can_adopt'],q.json()
    r=adopt(f,p,q.json()['adoption']);assert r.status_code==201,r.text
    return stored(f,p)['events'][-1]


def quote_second(f,p):
    hs,d=bundle(f);data=quoted(f,p,{**d,'expected_link_revision':1})
    assert data['expected_link_revision']==1
    return hs,data


def test_actual_explicit_source_adopt_reapproval_atomic_consumption_and_historical_verify(link_fixture):
    f=link_fixture;p,old,bridge=first(f);original=deepcopy(ledger(f,p)['events']);event=source_adopt(f,p)
    hs,data=quote_second(f,p);before=effects(f)
    assert submit(f,p,data).status_code==409 and effects(f)==before
    item,view=approved(f,p,data)
    assert item['purpose']=='CASE_RESOURCE_REAPPROVAL'
    context=item['context']['source_reapproval']
    assert context['link_id']==old['link']['id'] and context['link_revision']==1
    assert context['previous_approved_plan_revision']==old['delivery_binding']['approved_plan_revision']
    assert context['source_adoption_event_id']==event['id'] and context['source_adoption_revision']==event['revision']
    key=uuid4().hex;actual={**data,'approval_id':item['id']}
    result=submit(f,p,actual,key);assert result.status_code==201,result.text
    result=result.json();assert result['independent_check']['status']=='CURRENT'
    assert result['link']['revision']==2 and result['link']['id']!=old['link']['id']
    assert effects(f)==[2,6,2,2,2] and states(f,hs)==['CONFIRMED']*3
    assert ledger(f,p)['events'][:3]==original and ledger(f,p)['revision']==6
    assert recover(f,p,key).json()['receipt']==result['receipt']
    assert submit(f,p,actual,key).json()['receipt']==result['receipt']
    verified(f,p,'P2')
    cold=recover(f,p,key);assert cold.status_code==200,cold.text
    assert cold.json()['receipt']==result['receipt'] and cold.json()['independent_check']['status']=='NEEDS_RECHECK'
    assert recover(f,p,old['delivery_binding']['request_key']).status_code==200


def test_new_profile_requires_explicit_flag_and_new_adopt_not_just_existing_link(link_fixture):
    f=link_fixture;p,old,bridge=first(f,flag=False);hs,d=bundle(f)
    response=delivery_preview(f,p,{**d,'expected_link_revision':1});assert response.status_code==403,response.text
    bridge.source_reapproval_enabled=True
    response=delivery_preview(f,p,{**d,'expected_link_revision':1});assert response.status_code==409,response.text
    assert 'source adoption' in response.text
    assert effects(f)==[1,3,1,1,1] and states(f,hs)==['HELD']*3


def test_enabled_scope_direct_bind_new_key_cannot_bypass_after_link_approval(link_fixture):
    f=link_fixture;p,old,bridge=first(f);before=effects(f)
    assert direct_bind(f,p,old['combination'],revision=1).status_code==409
    assert effects(f)==before


def test_second_confirmation_fault_rolls_back_new_approval_consumption_and_capacity(link_fixture):
    import psycopg
    f=link_fixture;p,old,bridge=first(f);source_adopt(f,p);hs,data=quote_second(f,p)
    item,_=approved(f,p,data);before=effects(f);events=deepcopy(ledger(f,p))
    with f[1].connect() as c:
        c.execute("CREATE FUNCTION reapproval_fault() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'synthetic reapproval failure';END$$")
        c.execute('CREATE TRIGGER reapproval_fault BEFORE INSERT ON case_resource_links FOR EACH ROW EXECUTE FUNCTION reapproval_fault()')
    with pytest.raises(psycopg.Error):submit(f,p,{**data,'approval_id':item['id']})
    assert effects(f)==before and ledger(f,p)==events and states(f,hs)==['HELD']*3


def test_new_flag_cannot_enable_original_default_off_constructor():
    with pytest.raises(Denied):approvals.IsolatedPlanApproval(enabled_for_source_reapproval_tests=True)


def test_later_default_local_adoption_cannot_reuse_earlier_source_adopt_anchor(link_fixture):
    from test_registered_local_revision import add_resource,patch
    f=link_fixture;p,old,bridge=first(f);source_adopt(f,p)
    add_resource(f);response=patch(f,p);assert response.status_code==201,response.text
    assert stored(f,p)['events'][-1]['local_revision'].get('source_change') is None
    hs,d=bundle(f);before=effects(f)
    response=delivery_preview(f,p,{**d,'expected_link_revision':1})
    assert response.status_code==409,response.text
    assert effects(f)==before and states(f,hs)==['HELD']*3
