"""Predeclared independent actual-PG/ASGI candidates; not executed until frozen.

Fixture is new frontier_fixture_support; original replacement_case is never used.
No browser or native-network credit is claimed by this module.
"""
from copy import deepcopy
from uuid import uuid4
import pytest,psycopg
from frontier_fixture_support import (frontier_case,capability_resource_catalog,capability_catalog,receipt_fixture,preparation_fixture)
from frontier_oracle_support import (verify_imports,qualification,quote,commit,tail,
 snapshot,offer_body,offer_post,record,verified,submit,recover,effects,approved,
 ledger,stored,headers)
from test_resource_bundles import states
from test_service_plan_approval import propose,read as approval_read
from test_case_resource_delivery import preview

@pytest.fixture(autouse=True)
def actual_source_identity():
 verify_imports()


def test_frontier_independent_explicit_approval_actual_five_verify_six_goals_and_cold_get(frontier_case):
 x=frontier_case;f,p=x['f'],x['p'];initial=snapshot(f,p);old=deepcopy(x['old']);oldledger=deepcopy(ledger(f,p))
 assert [s['coordination_state'] for s in old['steps']]==['VERIFIED','VERIFIED','PENDING','PENDING','PENDING']
 assert initial['marker']['epoch']==0 and initial['marker']['ever_started'] is False and not any(initial['counts'].values())
 hs,data=quote(x);before=effects(f)
 assert submit(f,p,data).status_code==409 and effects(f)==before
 item,_=approved(f,p,data);q=qualification(item)
 assert q['previous_plan_id']==old['id'] and q['preparation_id']==p['preparation_id']
 assert item['purpose']=='CASE_RESOURCE_PLAN_REPLACEMENT'
 key=uuid4().hex;body={**data,'approval_id':item['id']};r=submit(f,p,body,key);assert r.status_code==201,r.text
 result=r.json();assert states(f,hs)==['CONFIRMED']*3 and effects(f)==[2,6,2,2,2]
 assert snapshot(f,p)==initial
 assert ledger(f,p)['events'][:3]==oldledger['events']
 tail(x);after=snapshot(f,p);assert after['marker']['epoch']>0 and after['marker']['ever_started'] is True
 assert all(v>0 for v in after['counts'].values())
 r=recover(f,p,key);assert r.status_code==200,r.text
 assert r.json()['receipt']==result['receipt'] and r.json()['independent_check']['status']=='CURRENT'
 assert submit(f,p,body,key).json()['receipt']==result['receipt']
 assert effects(f)==[2,6,2,2,2]
 r=approval_read(f,p);assert r.status_code==200,r.text
 assert next(v for v in r.json()['items'] if v['id']==item['id'])['state']=='CONSUMED'
 r=recover(f,p,x['oldreceipt']['delivery_binding']['request_key']);assert r.status_code==200,r.text
 assert r.json()['receipt']==x['oldreceipt']['receipt']
 assert stored(f,p)['history'][0]=={k:v for k,v in old.items() if k!='history'}
 record('positive-current-history',dict(before=initial,after=after,qualification=q,receipt=result['receipt']))


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_frontier_independent_other_owner_tenant_and_role_cannot_obtain_approval_or_delivery(frontier_case,user):
 x=frontier_case;f,p=x['f'],x['p'];hs,data=quote(x);before=effects(f);snap=snapshot(f,p)
 for r in (preview(f,p,{k:data[k] for k in ('members','expected_link_revision','expected_previous_plan_id','replacement_frontier_profile')},user),
           propose(f,p,data,revision=3,user=user),submit(f,p,data,user=user),
           recover(f,p,x['oldreceipt']['delivery_binding']['request_key'],user)):
  assert r.status_code==403,r.text
 assert effects(f)==before and snapshot(f,p)==snap and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('capability',['READ','EXECUTE','PREPARE','HOLD'])
def test_frontier_independent_current_revocation_invalidates_approved_commit(frontier_case,capability):
 x=frontier_case;f,p=x['f'],x['p'];hs,data=quote(x);item,_=approved(f,p,data);before=effects(f);oldledger=deepcopy(ledger(f,p));snap=snapshot(f,p)
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True)
  if capability=='HOLD':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
  elif capability=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
  else:c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',capability))
 r=submit(f,p,{**data,'approval_id':item['id']});assert r.status_code in (403,409),r.text
 assert effects(f)==before and ledger(f,p)==oldledger and snapshot(f,p)==snap and states(f,hs)==['HELD']*3
 if capability=='READ':assert recover(f,p,x['oldreceipt']['delivery_binding']['request_key']).status_code==403


@pytest.mark.parametrize('field',['missing','generation','preparation_id','plan_id','plan_revision','epoch'])
def test_frontier_independent_missing_or_wrong_explicit_business_fence_refuses_offer(frontier_case,field):
 x=frontier_case;f,p=x['f'],x['p'];commit(x);verified(f,p,'P2');body=offer_body(x)
 if field=='missing':body.pop('expected_business_frontier')
 elif field in ('generation','preparation_id','plan_id'):body['expected_business_frontier'][field]=str(uuid4())
 else:body['expected_business_frontier'][field]+=1
 before=snapshot(f,p);r=offer_post(x,body);assert r.status_code==409,r.text
 assert snapshot(f,p)==before


def test_frontier_independent_issued_protocol_missing_is_not_known_empty(frontier_case):
 x=frontier_case;f,p=x['f'],x['p'];hs,data=quote(x);before=effects(f);protocol=f[0]._known_not_started_frontier
 try:
  f[0]._known_not_started_frontier=None
  r=preview(f,p,{k:data[k] for k in ('members','expected_link_revision','expected_previous_plan_id','replacement_frontier_profile')})
  assert r.status_code==403,r.text
 finally:f[0]._known_not_started_frontier=protocol
 assert effects(f)==before and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('column',['candidate_frontier_birth','candidate_business_frontier'])
def test_frontier_independent_marker_cannot_be_removed_then_reborn(frontier_case,column):
 x=frontier_case;f,p=x['f'],x['p'];before=snapshot(f,p)
 with pytest.raises(psycopg.Error):
  with f[1].connect() as c:c.execute('UPDATE preparations SET '+column+'=NULL WHERE id=%s',(p['preparation_id'],))
 assert snapshot(f,p)==before
 _,data=quote(x);item,_=approved(f,p,data);qualification(item)


@pytest.mark.parametrize('table',['synthetic_resource_combination_receipts','resource_case_claims','case_resource_links'])
def test_frontier_independent_real_pg_delivery_failure_rolls_back_all_original_effects(frontier_case,table):
 x=frontier_case;f,p=x['f'],x['p'];hs,data=quote(x);item,_=approved(f,p,data);before=effects(f);oldledger=deepcopy(ledger(f,p));snap=snapshot(f,p)
 with f[1].connect() as c:
  c.execute("CREATE FUNCTION frontier_independent_fault() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'SYNTHETIC frontier independent rollback';END$$")
  c.execute('CREATE TRIGGER frontier_independent_fault BEFORE INSERT ON '+table+' FOR EACH ROW EXECUTE FUNCTION frontier_independent_fault()')
 with pytest.raises(psycopg.Error):submit(f,p,{**data,'approval_id':item['id']})
 assert effects(f)==before and ledger(f,p)==oldledger and snapshot(f,p)==snap and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('profile',['missing','unknown'])
def test_frontier_independent_no_profile_downgrade_can_turn_incomplete_old_tail_into_completed(frontier_case,profile):
 x=frontier_case;f,p=x['f'],x['p'];hs,data=quote(x);body={k:data[k] for k in ('members','expected_link_revision','expected_previous_plan_id')}
 if profile=='unknown':body['replacement_frontier_profile']='UNKNOWN'
 before=effects(f);snap=snapshot(f,p);r=preview(f,p,body)
 assert r.status_code==(409 if profile=='missing' else 422),r.text
 assert effects(f)==before and snapshot(f,p)==snap and states(f,hs)==['HELD']*3
