"""Actual PG/API goal results; existing workflow remains the only business writer."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4
import json,pytest
from psycopg.types.json import Jsonb
from parkweave import case_goal_results as results,service_case_steps as plans
from parkweave.store import Store
from test_service_case_steps import link_fixture,setup,adopt,verified,command,read,GOALS
from test_case_resources import group,post as link
from test_service_dispatches import offer,command as dispatch_act,REVIEWER
from test_executor_receipts import receipt_fixture,act as receipt_act
from test_preparation import preparation_fixture,headers,command as prep_act,read as prep_read
from test_request_intents import save
from test_case_lifecycle import read as local_read,act as local_act

TABLES=('preparations','preparation_events','preparation_evidence','fact_assertions','cases','runs','principals','capability_grants','field_grants','preparation_grants','action_grants','run_assignments','case_resource_links','resource_case_claims','synthetic_resources','synthetic_resource_grants','synthetic_resource_holds','synthetic_resource_combinations','synthetic_resource_combination_members','synthetic_resource_combination_receipts','service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps','service_step_receipts','service_receipt_events','case_local_lifecycles','case_local_events','controlled_plans','controlled_plan_events')
def snapshot(f):
 with f[1].connect() as c:return {t:c.execute('SELECT * FROM '+t+' ORDER BY to_jsonb('+t+')::text').fetchall() for t in TABLES}
def get(f,p,user='fixture-a'):return f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2],user))
def start(f,goals=None):
 p=setup(f,GOALS[0])
 if goals is not None:
  p=save(f,p,goals=goals).json();p=prep_act(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC actual goal review').json();p=prep_act(f,p,'CONFIRM',reason='SYNTHETIC actual goal confirmation').json()
 assert adopt(f,p).status_code==201
 return p

def complete(f,goals=None,local=False):
 p=start(f,goals or GOALS[:4]+([GOALS[4]] if local else []));verified(f,p,'P1');g=group(f);assert link(f,p,g).status_code==201;verified(f,p,'P2')
 d=dispatch_act(f,offer(f,p)[0].json(),'ACCEPT').json();verified(f,p,'P3');s=f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
 s=receipt_act(f,s,'SUBMIT',text='SYNTHETIC PRIVATE_GOAL_RECEIPT_1').json();s=receipt_act(f,s,'REQUEST_CHANGES').json();s=receipt_act(f,s,'SUBMIT',text='SYNTHETIC PRIVATE_GOAL_RECEIPT_2').json();s=receipt_act(f,s,'ACKNOWLEDGE').json();verified(f,p,'P4')
 if local:assert local_act(f,p,local_read(f,p).json(),'REVALIDATE').status_code==200;verified(f,p,'P5')
 return p,g,d,s

def test_actual_multi_goal_output_proofs_full_original_workflow_read_only_cold_store(link_fixture):
 f=link_fixture;p,g,d,s=complete(f,local=True);before=snapshot(f);r=get(f,p);assert r.status_code==200,r.text;x=r.json()
 assert x['state']=='LOCAL_OUTPUTS_VERIFIED' and len(x['results'])==5 and all(z['state']=='LOCAL_OUTPUT_VERIFIED' for z in x['results']);out={z['adapter_id']:z['actual_output'] for z in x['results']}
 assert out['P1']['materials']==[{ 'slot':m['slot'],'evidence_id':m['id'],'version':m['version'],'source_sha256':m['source_sha256']} for m in prep_read(f,p).json()['current_materials']]
 assert out['P2']['combination_id']==g['id'] and len(out['P2']['members'])==2
 assert out['P3']['offer_id']==d['current_offer']['id'] and out['P3']['receipt_step_id']==d['receipt_step_id']
 assert out['P4']['receipt_id']==s['current_receipt']['id'] and out['P4']['receipt_version']==2 and out['P4']['kind']=='MANUAL_SYNTHETIC_TEXT_ACKNOWLEDGEMENT' and out['P4']['execution_id'] is None
 assert out['P5']['local_record_state']=='READY' and out['P5']['revalidation_event_id']
 assert not x['case_goal_completed'] and x['read_only'] and not x['automatically_verified'];raw=json.dumps(x);assert 'PRIVATE_GOAL_RECEIPT' not in raw and 'PRIVATE_CASE_STEP' not in raw and 'source_snapshot' not in raw and 'verified_sources' not in raw
 assert snapshot(f)==before
 assert results.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']))==x and snapshot(f)==before
 with ThreadPoolExecutor(4) as pool:xs=list(pool.map(lambda _:get(f,p).json(),range(4)))
 assert all(v==x for v in xs) and snapshot(f)==before

def test_output_exists_does_not_bypass_original_owner_verify(link_fixture):
 f=link_fixture;p=start(f);before=snapshot(f);x=get(f,p).json();assert x['results'][0]['state']=='AWAITING_OWNER_VERIFICATION' and x['results'][0]['actual_output'] and x['results'][0]['historical_verification'] is None;assert snapshot(f)==before
 verified(f,p,'P1');assert get(f,p).json()['results'][0]['state']=='LOCAL_OUTPUT_VERIFIED'

@pytest.mark.parametrize('user',['fixture-b','fixture-c',REVIEWER,'executor-a','executor-b','unassigned'])
def test_no_new_role_or_cross_tenant_result_scope(link_fixture,user):
 f=link_fixture;p=start(f);before=snapshot(f)
 assert get(f,p,user).status_code==403;assert snapshot(f)==before

@pytest.mark.parametrize('which',['READ','PREPARE','ACTIVE','ROLE'])
def test_current_result_authority_fails_closed(link_fixture,which):
 f=link_fixture;p=start(f)
 with f[1].connect() as c:
  if which=='READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
  elif which=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
  elif which=='ACTIVE':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
  else:c.execute("UPDATE principals SET role='resource_admin' WHERE id='fixture-a'")
 before=snapshot(f);assert get(f,p).status_code==403;assert snapshot(f)==before

def test_read_after_execute_revoke_does_not_hide_history_or_publish_current_result(link_fixture):
 f=link_fixture;p=start(f);verified(f,p,'P1')
 with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
 before=snapshot(f);x=get(f,p).json();assert x['results'][0]['state']=='NEEDS_RECHECK' and not x['results'][0]['historical_verification']['current'] and x['results'][0]['actual_output'] is None;assert snapshot(f)==before

def test_new_unsupported_request_is_preserved_and_old_plan_not_current(link_fixture):
 f=link_fixture;p=start(f);verified(f,p,'P1');assert save(f,p,goals=['LOCAL_MATERIAL_PREPARATION','REAL_EXTERNAL_FULFILLMENT'],text='SYNTHETIC <img src=x onerror=evil()> new goal').status_code==200
 before=snapshot(f);x=get(f,p).json();assert [z['state'] for z in x['results']]==['NEEDS_NEW_PLAN','UNSUPPORTED'];assert x['adopted_goals']==['LOCAL_MATERIAL_PREPARATION'];assert all(z['actual_output'] is None for z in x['results']);assert snapshot(f)==before

@pytest.mark.parametrize('damage',['text','review-actor','review-case','confirm-actor','confirm-sha','review-missing','verify-missing','verify-fingerprint','verify-actor','verify-sources','objection'])
def test_partial_proof_damage_or_unresolved_feedback_never_becomes_result(link_fixture,damage):
 f=link_fixture;p=start(f);verified(f,p,'P1')
 with f[1].connect() as c:
  if damage=='text':c.execute('UPDATE preparation_evidence SET text=text||%s WHERE preparation_id=%s',('SYNTHETIC corrupted bytes',p['preparation_id']))
  elif damage=='review-actor':c.execute("UPDATE preparation_events SET actor_id='fixture-a' WHERE preparation_id=%s AND action='REVIEW'",(p['preparation_id'],))
  elif damage=='review-case':c.execute("UPDATE preparation_events SET payload=jsonb_set(payload,'{case_id}',to_jsonb(%s::text)) WHERE preparation_id=%s AND action='REVIEW'",(str(uuid4()),p['preparation_id']))
  elif damage=='confirm-actor':c.execute("UPDATE preparation_events SET actor_id=%s WHERE preparation_id=%s AND action='CONFIRM'",(REVIEWER,p['preparation_id']))
  elif damage=='confirm-sha':c.execute("UPDATE preparation_events SET payload=jsonb_set(payload,'{snapshot_sha256}',to_jsonb(%s::text)) WHERE preparation_id=%s AND action='CONFIRM'",('0'*64,p['preparation_id']))
  elif damage=='review-missing':c.execute("DELETE FROM preparation_events WHERE preparation_id=%s AND action='REVIEW'",(p['preparation_id'],))
  elif damage.startswith('verify-'):
   plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'];event=plan['events'][-1]
   if damage=='verify-missing':event.update(action='BEGIN',sources=None,source_sha256=None)
   elif damage=='verify-fingerprint':event['fingerprint']='0'*64
   elif damage=='verify-actor':event['actor_id']=REVIEWER
   else:event['sources']={'SYNTHETIC':'forged output'}
   c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
 if damage=='objection':
  from test_material_objections import get as objection_read,post as objection_write,body as objection_body
  v=objection_read(f,p).json();r=objection_write(f,p,objection_body(v));assert r.status_code==200,r.text
 before=snapshot(f);r=get(f,p);assert r.status_code==200,r.text;x=r.json();assert x['results'][0]['state']!='LOCAL_OUTPUT_VERIFIED' and x['state']!='LOCAL_OUTPUTS_VERIFIED';assert snapshot(f)==before

@pytest.mark.parametrize('damage',['empty','revision-bool','duplicate-step','dependencies','event-id','event-revision','plan-id'])
def test_invalid_structural_plan_proof_rejected_without_writes(link_fixture,damage):
 f=link_fixture;p=start(f);verified(f,p,'P1')
 with f[1].connect() as c:
  plan=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']
  if damage=='empty':plan['events']=[];plan['revision']=0
  elif damage=='revision-bool':plan['revision']=True
  elif damage=='duplicate-step':plan['steps'].append(deepcopy(plan['steps'][0]))
  elif damage=='dependencies':plan['steps'][0]['depends_on']=['P4']
  elif damage=='event-id':plan['events'][1]['id']=plan['events'][0]['id']
  elif damage=='event-revision':plan['events'][1]['revision']=1
  else:plan['events'][1]['plan_id']=str(uuid4())
  c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(plan),p['preparation_id']))
 before=snapshot(f);assert get(f,p).status_code==409;assert snapshot(f)==before

@pytest.mark.parametrize('damage',['cancelled','resource-read','resource-ended','receipt-text','receipt-ack','accept-event'])
def test_current_business_source_damage_keeps_history_and_blocks_result(link_fixture,damage):
 f=link_fixture;p,g,d,s=complete(f)
 with f[1].connect() as c:
  if damage=='cancelled':c.execute("UPDATE synthetic_resource_combinations SET state='CANCELLED' WHERE id=%s",(g['id'],))
  elif damage=='resource-read':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='READ'")
  elif damage=='resource-ended':c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '2 minutes',ends_at=clock_timestamp()-interval '1 minute' WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],))
  elif damage=='receipt-text':c.execute('UPDATE service_step_receipts SET text=text||%s WHERE id=%s',('SYNTHETIC corrupt',s['current_receipt']['id']))
  elif damage=='receipt-ack':c.execute("UPDATE service_receipt_events SET actor_id='executor-a' WHERE step_id=%s AND action='ACKNOWLEDGE'",(d['receipt_step_id'],))
  else:c.execute("UPDATE service_dispatch_events SET actor_id='fixture-a' WHERE offer_id=%s AND action='ACCEPT'",(d['current_offer']['id'],))
 before=snapshot(f);x=get(f,p).json();assert x['state']=='UNVERIFIED';assert x['results'][-1]['state']!='LOCAL_OUTPUT_VERIFIED' and x['results'][-1]['actual_output'] is None;assert x['results'][-1]['historical_verification'] and not x['results'][-1]['historical_verification']['current'];assert snapshot(f)==before

def test_request_without_plan_or_explicit_goals_stays_unknown(link_fixture):
 f=link_fixture;p=setup(f,GOALS[0]);before=snapshot(f);x=get(f,p).json();assert x['results'][0]['state']=='NOT_ADOPTED' and not x['case_goal_completed'];assert snapshot(f)==before
 assert save(f,p,goals=[]).status_code==200;before=snapshot(f);x=get(f,p).json();assert x['state']=='UNKNOWN' and x['results']==[] and snapshot(f)==before

@pytest.mark.parametrize('damage',['actor','cycle','snapshot','payload'])
def test_actual_local_revalidation_requires_original_current_event_proof(link_fixture,damage):
 f=link_fixture;p,g,d,s=complete(f,local=True)
 with f[1].connect() as c:
  if damage=='actor':c.execute("UPDATE case_local_events SET actor_id=%s WHERE preparation_id=%s AND action='REVALIDATE'",(REVIEWER,p['preparation_id']))
  elif damage=='cycle':c.execute("UPDATE case_local_events SET cycle=cycle+1 WHERE preparation_id=%s AND action='REVALIDATE'",(p['preparation_id'],))
  elif damage=='snapshot':c.execute("UPDATE case_local_events SET snapshot=%s WHERE preparation_id=%s AND action='REVALIDATE'",(Jsonb({'SYNTHETIC':'damaged proof'}),p['preparation_id']))
  else:c.execute("UPDATE case_local_events SET payload=jsonb_set(payload,'{verified_snapshot_sha256}',to_jsonb(%s::text)) WHERE preparation_id=%s AND action='REVALIDATE'",('0'*64,p['preparation_id']))
 before=snapshot(f);x=get(f,p).json();assert x['results'][-1]['state']=='NEEDS_RECHECK' and x['results'][-1]['actual_output'] is None and x['results'][-1]['historical_verification'];assert snapshot(f)==before

def test_resource_window_expiry_during_actual_last_source_row_lock_wait(link_fixture):
 import time
 f=link_fixture;p,g,d,s=complete(f,local=True)
 with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '1 minute',ends_at=clock_timestamp()+interval '2 seconds' WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],))
 for a in ('P2','P3','P4'):verified(f,p,a)
 assert local_act(f,p,local_read(f,p).json(),'REVALIDATE').status_code==200;verified(f,p,'P5');assert get(f,p).json()['state']=='LOCAL_OUTPUTS_VERIFIED';before=snapshot(f)
 with f[1].connect() as block,ThreadPoolExecutor(1) as pool:
  block.execute('SELECT preparation_id FROM case_local_lifecycles WHERE preparation_id=%s FOR UPDATE',(p['preparation_id'],));pending=pool.submit(get,f,p)
  deadline=time.monotonic()+1
  while time.monotonic()<deadline:
   block.execute('SELECT pg_stat_clear_snapshot()')
   waiting=block.execute("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%FROM case_local_lifecycles%%') AS waiting").fetchone()['waiting']
   if waiting:break
   time.sleep(.01)
  assert waiting,'actual goal read did not reach the last source row lock'
  block.execute("SELECT pg_sleep(greatest(0,extract(epoch from (max(ends_at)-clock_timestamp())))+.03) FROM synthetic_resource_holds WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],));block.commit();r=pending.result(5)
 assert r.status_code==200,r.text;x=r.json();assert x['state']=='UNVERIFIED' and x['results'][1]['actual_output'] is None and 'RESOURCE_WINDOW_ENDED' in x['results'][1]['issues'];assert snapshot(f)==before
