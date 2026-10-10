"""Independent effect sets, transaction/anchor proof, authorization ABA oracles."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4,UUID
import json
import psycopg,pytest
from psycopg.types.json import Jsonb
from test_service_plan_approval import (link_fixture,receipt_fixture,preparation_fixture,setup,
    approved,read,ledger,propose,decide,enable)
from test_case_resource_delivery import submit,recover,effects,quoted,prepared
from test_resource_bundles import states,bundle
from test_service_case_steps import verified,read as plan_read
from test_preparation import headers
from parkweave import case_resource_delivery as delivery,service_plan_approval as approval
from parkweave.store import Store,Conflict

def snapshot(f,p):
    with f[1].connect() as c:
        return {'parent':c.execute('SELECT service_case_plan,candidate_plan_approvals,candidate_plan_approval_head FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone(),
            **{t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in ('synthetic_resource_holds','synthetic_resource_combinations','synthetic_resource_combination_receipts','resource_case_claims','case_resource_links')}}

def test_all_eight_approved_alternatives_allow_one_effect_and_seven_explicit_revocations(link_fixture):
    f=link_fixture;p,hs,data,_=setup(f);items=[]
    for i in range(8):
        x=propose(f,p,data,revision=i*2);assert x.status_code==201
        item=x.json()['items'][-1];y=decide(f,p,item,i*2+1);assert y.status_code==200;items.append(item)
    old=deepcopy(ledger(f,p));r=submit(f,p,{**data,'approval_id':items[0]['id']});assert r.status_code==201
    for index,item in enumerate(items[1:]):
        assert decide(f,p,item,17+index,'REVOKE').status_code==200
    final=ledger(f,p);assert final['revision']==24 and final['events'][:16]==old['events']
    assert [i['state'] for i in read(f,p).json()['items']]==['CONSUMED']+['REVOKED']*7
    assert effects(f)==[1,3,1,1,1] and states(f,hs)==['CONFIRMED']*3
    before=snapshot(f,p);assert propose(f,p,data,revision=24).status_code==409 and snapshot(f,p)==before

@pytest.mark.parametrize('damage',['head-alone','clear-head','valid-prefix','null-ledger','old-hash'])
def test_sql_app_cannot_change_original_anchor_or_history(link_fixture,damage):
    f=link_fixture;p,hs,data,_=setup(f);approved(f,p,data);before=snapshot(f,p)
    with pytest.raises(psycopg.Error):
        with f[0].connect() as c:
            if damage=='head-alone':c.execute("UPDATE preparations SET candidate_plan_approval_head=jsonb_set(candidate_plan_approval_head,'{sha256}',to_jsonb(%s::text)) WHERE id=%s",('0'*64,p['preparation_id']))
            elif damage=='clear-head':c.execute('UPDATE preparations SET candidate_plan_approval_head=NULL WHERE id=%s',(p['preparation_id'],))
            elif damage=='null-ledger':c.execute('UPDATE preparations SET candidate_plan_approvals=NULL WHERE id=%s',(p['preparation_id'],))
            else:
                v=ledger(f,p)
                if damage=='valid-prefix':v['events']=v['events'][:1];v['revision']=1
                else:v['events'][0]['sha256']='0'*64
                c.execute('UPDATE preparations SET candidate_plan_approvals=%s WHERE id=%s',(Jsonb(v),p['preparation_id']))
    assert snapshot(f,p)==before

@pytest.mark.parametrize('damage',['purpose','actor','fingerprint','receipt-hash','receipt-scope','receipt-id'])
def test_consumption_damage_never_downgrades_p2_or_goal_to_unapproved_legacy(link_fixture,damage):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);key=uuid4().hex
    assert submit(f,p,{**data,'approval_id':item['id']},key).status_code==201;verified(f,p,'P2')
    with f[1].connect() as c:
        if damage.startswith('receipt-'):
            payload=c.execute('SELECT payload FROM synthetic_resource_combination_receipts WHERE request_key=%s',(key,)).fetchone()['payload']
            if damage=='receipt-hash':payload['at']='2000-01-01T00:00:00+00:00'
            elif damage=='receipt-scope':payload['plan_approval']['scope']='OTHER_PURPOSE'
            else:payload['plan_approval']['id']=str(uuid4())
            c.execute('UPDATE synthetic_resource_combination_receipts SET payload=%s WHERE request_key=%s',(Jsonb(payload),key))
        else:
            v=ledger(f,p)
            if damage=='purpose':v['events'][0]['binding']['purpose']='OTHER_PURPOSE'
            elif damage=='actor':v['events'][-1]['actor_id']='fixture-b'
            else:v['events'][-1]['fingerprint']='0'*64
            c.execute('ALTER TABLE preparations DISABLE TRIGGER candidate_plan_approval_prefix')
            c.execute('UPDATE preparations SET candidate_plan_approvals=%s WHERE id=%s',(Jsonb(v),p['preparation_id']))
            c.execute('ALTER TABLE preparations ENABLE TRIGGER candidate_plan_approval_prefix')
    before=snapshot(f,p)
    assert recover(f,p,key).status_code==409 and plan_read(f,p).status_code==409
    assert f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2])).status_code==409
    assert snapshot(f,p)==before and states(f,hs)==['CONFIRMED']*3

@pytest.mark.parametrize('which',['owner-principal','prepare-no-change-update','resource-no-change-update'])
def test_real_row_version_change_without_visible_value_change_invalidates_approval(link_fixture,which):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);before=ledger(f,p)
    with f[1].connect() as c:
        f[1].lock_principal(c,'fixture-a',exclusive=True)
        if which=='owner-principal':c.execute("UPDATE principals SET active=active WHERE id='fixture-a'")
        elif which=='prepare-no-change-update':c.execute("UPDATE preparation_grants SET active=active WHERE principal_id='fixture-a' AND capability='PREPARE'")
        else:c.execute('UPDATE synthetic_resource_grants SET active=active WHERE principal_id=%s AND resource_id=%s',('fixture-a',hs[-1]['resource_id']))
    assert not read(f,p).json()['items'][-1]['current_available']
    assert submit(f,p,{**data,'approval_id':item['id']}).status_code==409 and ledger(f,p)==before and effects(f)==[0]*5

def test_original_read_and_unknown_key_queries_never_persist_source_invalidation(link_fixture):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data)
    with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET capacity=capacity+1 WHERE id=%s',(hs[-1]['resource_id'],))
    before=snapshot(f,p)
    for _ in range(2):
        r=read(f,p);assert r.status_code==200 and not r.json()['items'][-1]['current_available']
        r=f[3].get('/api/preparations/'+p['preparation_id']+'/plan-approval/recovery/'+uuid4().hex,headers=headers(f[2]));assert r.status_code==200 and r.json()['status']=='NOT_OBSERVED'
        assert snapshot(f,p)==before

def test_same_exact_delivery_canonical_member_order_replays_one_consumption(link_fixture):
    f=link_fixture;p,hs,data,_=setup(f);item,_=approved(f,p,data);key=uuid4().hex
    r=submit(f,p,{**data,'approval_id':item['id']},key);assert r.status_code==201
    before=snapshot(f,p)
    r2=submit(f,p,{**data,'members':list(reversed(data['members'])),'approval_id':item['id']},key)
    assert r2.status_code==201 and r2.json()['receipt']==r.json()['receipt'] and snapshot(f,p)==before
