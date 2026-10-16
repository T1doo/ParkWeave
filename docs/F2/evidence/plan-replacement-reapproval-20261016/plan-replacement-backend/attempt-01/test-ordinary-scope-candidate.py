"""Candidate own PG / original HTTP protocol checks for explicit replacement."""
from copy import deepcopy
from uuid import uuid4
import pytest
from parkweave import catalog_publication as pub
from test_case_resources import link_fixture
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture
from test_catalog_approval_coordination import publish
from test_service_plan_approval import enable,ledger,propose,decide
from test_plan_source_reapproval import approved
from test_case_resource_delivery import prepared,quoted,submit,recover,effects,preview
from test_resource_bundles import bundle,states
from test_service_case_steps import adopt,adopt_body,verified,read
from test_service_plan_manual_lock import stored


def first(f,flag=True):
    p=prepared(f);bridge=enable(f,p,enabled_for_plan_replacement_tests=flag)
    publication=pub.IsolatedCatalogPublication(bridge,enabled_for_isolated_tests=True)
    # Original protocol INIT changes catalog binding; use original full replacement.
    r=adopt(f,p,{**adopt_body(f,p),'expected_plan_revision':stored(f,p)['revision']})
    assert r.status_code==201,r.text
    verified(f,p,'P1');hs,d=bundle(f);data=quoted(f,p,d);item,_=approved(f,p,data)
    key=uuid4().hex;r=submit(f,p,{**data,'approval_id':item['id']},key)
    assert r.status_code==201,r.text
    verified(f,p,'P2')
    return p,r.json(),bridge,publication


def replace(f,p,publication,revision=1,source_revision=2):
    old=deepcopy(stored(f,p));publish(publication,p,revision=revision,source_revision=source_revision)
    # Directory/contract change is still rejected by original local ADOPT.
    data={**adopt_body(f,p),'expected_plan_revision':old['revision']}
    r=adopt(f,p,{**data,'local_revision':True});assert r.status_code==409,r.text
    r=adopt(f,p,data);assert r.status_code==201,r.text
    new=stored(f,p);assert new['id']!=old['id'] and new['history'][-1]['id']==old['id']
    verified(f,p,'P1');return old


def test_replacement_actual_new_approval_and_atomic_delivery(link_fixture):
    f=link_fixture;p,first_value,bridge,publication=first(f);old=replace(f,p,publication)
    hs,d=bundle(f);data=quoted(f,p,{**d,'expected_link_revision':1,'expected_previous_plan_id':old['id']})
    before=effects(f);assert submit(f,p,data).status_code==409 and effects(f)==before
    item,_=approved(f,p,data);assert item['purpose']=='CASE_RESOURCE_PLAN_REPLACEMENT'
    proof=item['context']['plan_replacement'];assert proof['previous_plan_id']==old['id']
    assert proof['replacement_plan_id']==stored(f,p)['id'] and proof['compatibility']['classification']=='NEEDS_RECHECK'
    key=uuid4().hex;result=submit(f,p,{**data,'approval_id':item['id']},key)
    assert result.status_code==201,result.text
    assert result.json()['independent_check']['status']=='CURRENT'
    assert result.json()['link']['revision']==2 and effects(f)==[2,6,2,2,2]
    assert states(f,hs)==['CONFIRMED']*3
    verified(f,p,'P2');assert recover(f,p,key).json()['independent_check']['status']=='CURRENT'
    assert recover(f,p,first_value['delivery_binding']['request_key']).json()['independent_check']['status']=='NEEDS_RECHECK'
    assert submit(f,p,{**data,'approval_id':item['id']},key).json()['receipt']==result.json()['receipt']


def test_replacement_flag_and_exact_old_plan_required(link_fixture):
    f=link_fixture;p,old_value,bridge,publication=first(f,flag=False);old=replace(f,p,publication)
    hs,d=bundle(f);data={**d,'expected_link_revision':1,'expected_previous_plan_id':old['id']}
    assert preview(f,p,data).status_code==403
    enable(f,p,enabled_for_plan_replacement_tests=True)._catalog_publication=publication
    assert preview(f,p,{**data,'expected_previous_plan_id':str(uuid4())}).status_code==409
    # The old same-plan source profile is still not replacement authority.
    assert preview(f,p,{**d,'expected_link_revision':1}).status_code==403
    assert effects(f)==[1,3,1,1,1]
