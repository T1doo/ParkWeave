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
    assert cold.json()['receipt']==result['receipt'] and cold.json()['independent_check']['status']=='CURRENT'
    assert recover(f,p,old['delivery_binding']['request_key']).status_code==200


def test_new_profile_requires_explicit_flag_and_new_adopt_not_just_existing_link(link_fixture):
    f=link_fixture;p,old,bridge=first(f,flag=False);hs,d=bundle(f)
    response=delivery_preview(f,p,{**d,'expected_link_revision':1});assert response.status_code==403,response.text
    bridge=enable(f,p,enabled_for_source_reapproval_tests=True)
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


def test_twice_reapproved_then_full_replacement_preserves_original_consumed_receipts(link_fixture):
    from test_service_case_steps import adopt_body
    f=link_fixture;p,old,bridge=first(f);saved=[]
    for revision in (1,2):
        source_adopt(f,p)
        if revision==1:hs,d=bundle(f)
        else:
            from datetime import datetime,timedelta
            from test_resource_holds import body
            from test_resource_combinations import hold
            from parkweave import resource_holds as rh,resource_combinations as rc
            base=body(f,ttl=300);start=datetime.fromisoformat(base['starts_at'])+timedelta(hours=9);hs=[]
            for i in range(3):
                request={**base,'starts_at':(start+timedelta(hours=i*3)).isoformat(),'ends_at':(start+timedelta(hours=i*3+1)).isoformat()}
                response=hold(f,rh.RESOURCE_ID if i%2==0 else rc.SECOND_RESOURCE_ID,request);assert response.status_code==201,response.text
                hs.append(response.json()['hold'])
            d={'members':[{'hold_id':h['id'],'expected_revision':h['resource_revision']} for h in hs]}
        data=quoted(f,p,{**d,'expected_link_revision':revision});item,_=approved(f,p,data)
        key=uuid4().hex;result=submit(f,p,{**data,'approval_id':item['id']},key)
        assert result.status_code==201,result.text
        saved.append((key,result.json()['receipt']));verified(f,p,'P2')
    for key,receipt in saved:
        result=recover(f,p,key);assert result.status_code==200,result.text
        assert result.json()['receipt']==receipt
    from test_request_intents import save
    request=save(f,p,goals=['LOCAL_CASE_RESOURCE_ASSOCIATION'],text='SYNTHETIC explicit replacement request after two approvals')
    assert request.status_code==200,request.text
    p={**p,'revision':request.json()['revision']}
    plan=stored(f,p);replacement=adopt(f,p,{**adopt_body(f,p),'expected_plan_revision':plan['revision']})
    assert replacement.status_code==201,replacement.text
    assert stored(f,p)['id']!=plan['id']
    for key,receipt in saved:
        result=recover(f,p,key);assert result.status_code==200,result.text
        assert result.json()['receipt']==receipt and result.json()['independent_check']['status']=='NEEDS_RECHECK'


@pytest.mark.parametrize('fault',['STRIP_PROFILE','SELF_ANCHOR','STRIP_PROOFS'])
def test_rehashed_owned_fixture_profile_downgrade_and_self_reference_are_conflicts(link_fixture,fault):
    from psycopg.types.json import Jsonb
    from parkweave import controlled_plans as cp,service_plan_approval as a,preparation as prep
    from parkweave.store import digest
    f=link_fixture;p,old,bridge=first(f);source_adopt(f,p);hs,data=quote_second(f,p)
    item,_=approved(f,p,data);key=uuid4().hex;result=submit(f,p,{**data,'approval_id':item['id']},key)
    assert result.status_code==201,result.text
    value=result.json();receipt=deepcopy(value['receipt']);events=deepcopy(ledger(f,p));proposal,approval,consume=events['events'][3:]
    context=proposal['binding']['context']
    for command in (proposal['request']['delivery'],consume['request']['delivery']):
        if fault=='STRIP_PROFILE':command.pop('expected_link_revision')
        elif fault=='SELF_ANCHOR':command['expected_link_revision']=2
    if fault=='STRIP_PROFILE':
        context.pop('source_reapproval');proposal['binding']['purpose']='CASE_RESOURCE_DELIVERY'
        receipt['delivery_binding']['context'].pop('source_reapproval')
    elif fault=='SELF_ANCHOR':
        for current in (context['source_reapproval'],receipt['delivery_binding']['context']['source_reapproval']):
            current.update(link_id=value['link']['id'],link_revision=2,snapshot_sha256='a'*64)
    new_binding_sha=cp._hash(proposal['binding'])
    approval['request']['expected_binding_sha256']=new_binding_sha
    receipt['plan_approval']['binding_sha256']=new_binding_sha
    if fault=='STRIP_PROOFS':receipt['plan_approval']=None
    fp=digest(prep.canonical(dict(preparation_id=p['preparation_id'],action='CASE_RESOURCE_DELIVERY',**consume['request']['delivery'])))
    receipt['delivery_binding']['fingerprint']=fp
    consume['receipt'].update(fingerprint=fp,receipt_sha256=cp._hash(receipt))
    previous=None
    for event in events['events']:
        event['previous_sha256']=previous;event['fingerprint']=a._fingerprint(p['preparation_id'],event['request'])
        event['sha256']=cp._hash({k:v for k,v in event.items() if k!='sha256'});previous=event['sha256']
    snapshot=deepcopy(value['link']['snapshot']);snapshot['delivery_binding']=receipt['delivery_binding'];snapshot['plan_approval']=receipt['plan_approval']
    with f[1].connect() as c:
        c.execute('ALTER TABLE preparations DISABLE TRIGGER candidate_plan_approval_prefix')
        c.execute('UPDATE preparations SET candidate_plan_approvals=%s,candidate_plan_approval_head=%s WHERE id=%s',
            (Jsonb(events),Jsonb(dict(revision=events['revision'],sha256=previous)),p['preparation_id']))
        c.execute('ALTER TABLE preparations ENABLE TRIGGER candidate_plan_approval_prefix')
        c.execute('UPDATE synthetic_resource_combination_receipts SET payload=%s,fingerprint=%s WHERE actor_id=%s AND request_key=%s',(Jsonb(receipt),fp,'fixture-a',key))
        c.execute('UPDATE case_resource_links SET snapshot=%s,fingerprint=%s WHERE id=%s',(Jsonb(snapshot),fp,value['link']['id']))
    response=recover(f,p,key);assert response.status_code==409,response.text
    assert set(response.json())=={'detail'} and isinstance(response.json()['detail'],str) and response.json()['detail']
    from test_preparation import headers
    for endpoint in ('resource-plan-binding','service-case-plan','goal-results'):
        read=f[3].get('/api/preparations/'+p['preparation_id']+'/'+endpoint,headers=headers(f[2]))
        assert read.status_code==409,(fault,endpoint,read.text)
