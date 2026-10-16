"""New explicit closure profile: actual PG/ASGI candidates, never old zero proof."""
from copy import deepcopy
from uuid import uuid4
import pytest,psycopg
from psycopg.types.json import Jsonb
from p3_closure_fixture_support import (closure_case,capability_resource_catalog,capability_catalog,
 receipt_fixture,preparation_fixture,offer_current,dispatch_read,REVIEWER)
from p3_closure_oracle_support import (verify_imports,record,snapshot,qualify_old,check_qualification,
 quote,commit,new_business_tail,current_offer_body,post_offer,headers,PROFILE,TABLES)
from test_service_dispatches import command as dispatch_command
from test_case_resource_delivery import preview,submit,recover,effects
from test_service_plan_approval import ledger,propose,read as approval_read
from test_service_case_steps import verified
from parkweave.store import Conflict

@pytest.fixture(autouse=True)
def actual_import_identity():verify_imports()


@pytest.mark.parametrize('closure_case',[{'action':action,'cycles':cycles} for action in ('WITHDRAW','DECLINE') for cycles in (1,3)],indirect=True)
def test_p3_closure_actual_mode_history_new_approval_original_tail_and_readonly_cold_receipts(closure_case):
 t=closure_case;f,p=t['f'],t['p'];before=snapshot(t);oldreceipt=deepcopy(t['oldreceipt']);oldledger=deepcopy(ledger(f,p))
 result=commit(t);q=result['qualification'];assert q['epoch']>0 and q['ever_started'] is True
 assert effects(f)==[2,6,2,2,2] and ledger(f,p)['events'][:3]==oldledger['events']
 new_business_tail(t);after=snapshot(t)
 assert after['parent']['candidate_business_frontier']['epoch']>q['epoch']
 assert len(after['tables']['service_receipt_steps'])==1 and len(after['tables']['service_step_receipts'])==1
 # Old closure prefix events remain literal historical rows after new REOFFER/ACCEPT.
 oldevents=before['tables']['service_dispatch_events']
 assert all(e in after['tables']['service_dispatch_events'] for e in oldevents)
 for key,receipt in ((result['key'],result['result']['receipt']),
                     (oldreceipt['delivery_binding']['request_key'],oldreceipt['receipt'])):
  r=recover(f,p,key);assert r.status_code==200,r.text;assert r.json()['receipt']==receipt
 r=approval_read(f,p);assert r.status_code==200,r.text
 assert next(row for row in r.json()['items'] if row['id']==result['item']['id'])['state']=='CONSUMED'
 assert snapshot(t)==after,'cold GET changed original business state/history'
 assert submit(f,p,result['body'],result['key']).json()['receipt']==result['result']['receipt']
 for field,value in [('reason',result['body']['reason']+' changed'),('replacement_frontier_profile',None),
                     ('expected_previous_plan_id',str(uuid4())),('expected_link_revision',2)]:
  r=submit(f,p,{**result['body'],field:value},result['key']);assert r.status_code==409,r.text
 assert snapshot(t)==after and effects(f)==[2,6,2,2,2]
 record('closed-profile-full-chain',dict(mode=q['closure_state'],qualification=q,
  old_event_count=len(oldevents),new_event_count=len(after['tables']['service_dispatch_events']),
  old_receipt=oldreceipt['receipt'],new_receipt=result['result']['receipt'],cold_get_did_not_write=True))


@pytest.mark.parametrize('closure_case',[{'stop_after':'offered'}],indirect=True)
def test_p3_closure_offered_requires_explicit_current_authorized_withdraw(closure_case):
 t=closure_case;f,p=t['f'],t['p'];before=snapshot(t)
 with pytest.raises(Conflict):qualify_old(t)
 assert snapshot(t)==before
 row=dispatch_read(f,t['dispatch'],REVIEWER)
 r=dispatch_command(f,row,'WITHDRAW',expected_business_frontier=row['business_frontier']);assert r.status_code==200,r.text
 q=check_qualification(qualify_old(t),t,'WITHDRAWN')
 assert q['epoch']>before['parent']['candidate_business_frontier']['epoch']
 record('offered-explicit-withdraw',dict(before_state='OFFERED',qualification=q))


@pytest.mark.parametrize('closure_case',[{'stop_after':'old_p2'}],indirect=True)
def test_p3_closure_no_dispatch_history_cannot_claim_closed_profile(closure_case):
 t=closure_case;before=snapshot(t);assert before['parent']['candidate_business_frontier']['epoch']==0
 with pytest.raises(Conflict):qualify_old(t)
 assert snapshot(t)==before


@pytest.mark.parametrize('closure_case',[{'stop_after':'closed','action':'DECLINE'}],indirect=True)
def test_p3_closure_real_reoffer_revives_offered_and_requires_new_withdraw_digest(closure_case):
 t=closure_case;f=t['f'];old=check_qualification(qualify_old(t),t,'DECLINED')
 row,_=offer_current(t);assert row['current_offer']['state']=='OFFERED'
 with pytest.raises(Conflict):qualify_old(t)
 row=dispatch_read(f,row,REVIEWER);r=dispatch_command(f,row,'WITHDRAW',expected_business_frontier=row['business_frontier']);assert r.status_code==200,r.text
 new=check_qualification(qualify_old(t),t,'WITHDRAWN')
 assert new['dispatch']['revision']==old['dispatch']['revision']+2
 assert new['dispatch']['history_sha256']!=old['dispatch']['history_sha256'] and new['marker_sha256']!=old['marker_sha256']
 record('real-reoffer-then-explicit-reclosure',dict(old=old,new=new))


def test_p3_closure_new_adopt_p1_pending_p2_original_reoffer_gate_refuses(closure_case):
 t=closure_case;before=snapshot(t);body=current_offer_body(t);r=post_offer(t,body)
 assert r.status_code==409,r.text
 assert snapshot(t)==before
 record('new-plan-p2-pending-original-gate',dict(status=r.status_code,fence=body['expected_business_frontier'],response=r.json()))


@pytest.mark.parametrize('profile',[None,'KNOWN_NOT_STARTED_V1','UNKNOWN'])
def test_p3_closure_profile_never_downgrades_to_zero_or_completed(closure_case,profile):
 t=closure_case;f,p=t['f'],t['p'];_,data=quote(t);body={k:data[k] for k in ('members','expected_link_revision','expected_previous_plan_id')}
 if profile is not None:body['replacement_frontier_profile']=profile
 before=snapshot(t);r=preview(f,p,body)
 assert r.status_code in (403,409,422),r.text
 assert snapshot(t)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_p3_closure_other_identity_cannot_preview_propose_consume_or_read_old_receipt(closure_case,user):
 t=closure_case;f,p=t['f'],t['p'];_,data=quote(t);before=snapshot(t)
 for r in (preview(f,p,{k:data[k] for k in ('members','expected_link_revision','expected_previous_plan_id','replacement_frontier_profile')},user),
           propose(f,p,data,revision=3,user=user),submit(f,p,data,user=user),
           recover(f,p,t['oldreceipt']['delivery_binding']['request_key'],user)):
  assert r.status_code==403,r.text
 assert snapshot(t)==before


@pytest.mark.parametrize('closure_case',[{'stop_after':'closed'}],indirect=True)
@pytest.mark.parametrize('mutation',['delete_event','delete_restore_event','payload_fence_boolean','request_key'])
def test_p3_closure_controlled_owner_history_damage_cannot_be_rehashed_to_closed(closure_case,mutation):
 t=closure_case;f=t['f'];original=check_qualification(qualify_old(t),t,'WITHDRAWN')
 with f[1].connect() as c:
  row=c.execute('SELECT * FROM service_dispatch_events WHERE dispatch_id=%s ORDER BY revision LIMIT 1',(t['dispatch']['dispatch_id'],)).fetchone()
  if mutation in ('delete_event','delete_restore_event'):
   notices=c.execute('SELECT * FROM dispatch_notice_outbox WHERE event_id=%s',(row['id'],)).fetchall()
   c.execute('DELETE FROM dispatch_notice_outbox WHERE event_id=%s',(row['id'],))
   c.execute('DELETE FROM service_dispatch_events WHERE id=%s',(row['id'],))
  elif mutation=='payload_fence_boolean':
   payload=deepcopy(row['payload']);payload['expected_business_frontier']['epoch']=True
   c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s',(Jsonb(payload),row['id']))
  else:c.execute('UPDATE service_dispatch_events SET request_key=%s WHERE id=%s',(uuid4().hex,row['id']))
 if mutation=='delete_restore_event':
  with f[1].connect() as c:
   c.execute('INSERT INTO service_dispatch_events(id,dispatch_id,offer_id,actor_id,request_key,fingerprint,revision,action,payload,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
    tuple(Jsonb(row[k]) if k=='payload' else row[k] for k in ('id','dispatch_id','offer_id','actor_id','request_key','fingerprint','revision','action','payload','created_at')))
   from psycopg.sql import SQL,Identifier,Placeholder
   for notice in notices:
    columns=list(notice);c.execute(SQL('INSERT INTO dispatch_notice_outbox ({}) VALUES ({})').format(
     SQL(',').join(Identifier(k) for k in columns),SQL(',').join(Placeholder() for _ in columns)),tuple(notice[k] for k in columns))
 with pytest.raises(Conflict):qualify_old(t)
 record('controlled-owner-history-'+mutation,dict(scope='OWNER_PG_SQL_FAULT_NOT_PUBLIC_HISTORY_MUTATION',original=original,actual=snapshot(t)))
