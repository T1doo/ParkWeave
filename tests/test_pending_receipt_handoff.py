"""Real owned PG/in-process ASGI pending manual handoff; no new production authority."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4
import pytest
import psycopg
from parkweave import service_dispatches as sd, executor_receipts as er
from parkweave.store import Store, Conflict, Denied
from test_preparation import preparation_fixture, headers, command as prep_command
from test_executor_receipts import receipt_fixture, ready, act as receipt_act, create as legacy_create
from test_service_dispatches import offer, command as decide, REVIEWER

TABLES=('service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps',
        'service_step_receipts','service_receipt_events','dispatch_notice_outbox','dispatch_notices')
AUTHORITY=('principals','capability_grants','field_grants','action_grants','run_assignments',
           'preparation_grants','synthetic_resource_grants')

def snapshot(f,tables=TABLES):
 with f[1].connect() as c:return {t:c.execute('SELECT * FROM '+t+' ORDER BY 1').fetchall() for t in tables}

def accepted(f):
 parent=ready(f)
 # Existing fixture principal/READ role; original setup assigns only this owned synthetic Run.
 f[1].assign_status('unassigned',UUID(parent['run_id']),active=True)
 r,_,_=offer(f,parent);row=decide(f,r.json(),'ACCEPT').json()
 return parent,row

def catalog(f,parent):
 r=f[3].get('/api/service-dispatches/catalog?preparation_id='+parent['preparation_id'],headers=headers(f[2],REVIEWER))
 assert r.status_code==200;return r.json()

def body_for(f,parent,row,target='unassigned'):
 p=catalog(f,parent)['reassignment_predecessor'];assert p
 return dict(expected_preparation_revision=parent['revision'],expected_dispatch_revision=row['revision'],
             predecessor_offer_id=p['predecessor_offer_id'],predecessor_receipt_step_id=p['predecessor_receipt_step_id'],
             expected_receipt_revision=p['predecessor_receipt_revision'],executor_id=target,
             reason='SYNTHETIC explicit manual responsibility handoff')

def post(f,row,body,key=None,user=REVIEWER):
 return f[3].post('/api/service-dispatches/'+row['dispatch_id']+'/reassign',headers=headers(f[2],user,key or uuid4().hex),json=body)

def recover(f,row,key,user=REVIEWER):
 return f[3].get('/api/service-dispatches/'+row['dispatch_id']+'/reassignment-recovery/'+key,headers=headers(f[2],user))

def step(f,id,user='fixture-a'):
 r=f[3].get('/api/executor-receipts/'+str(id),headers=headers(f[2],user));assert r.status_code==200;return r.json()

def test_actual_handoff_new_accept_receipt_owner_ack_and_immutable_predecessor(receipt_fixture):
 f=receipt_fixture;parent,row=accepted(f);old_id=row['receipt_step_id'];old=snapshot(f);authority=snapshot(f,AUTHORITY)
 b=body_for(f,parent,row);key=uuid4().hex;r=post(f,row,b,key);assert r.status_code==201;r=r.json()
 assert r['current_offer']['executor_id']=='unassigned' and r['current_offer']['state']=='OFFERED' and r['current_receipt_step_id'] is None
 assert step(f,old_id)['record_mode']=='HISTORICAL_GENERATION'
 assert receipt_act(f,step(f,old_id),'SUBMIT').status_code==409
 assert legacy_create(f,parent)[0].status_code==409
 rr=recover(f,row,key);assert rr.status_code==200 and rr.headers['cache-control']=='no-store'
 assert rr.json()['status']=='COMMITTED' and rr.json()['event']==r['event'] and rr.json()['historical_only']
 assert post(f,row,b,key).json()['event']==r['event']
 done=decide(f,r,'ACCEPT').json();new_id=done['receipt_step_id'];assert new_id!=old_id
 new=step(f,new_id,'unassigned');assert new['receipt_history']==[] and new['step']['state']=='AWAITING_RECEIPT'
 assert f[3].get('/api/executor-receipts/'+new_id,headers=headers(f[2],'executor-a')).status_code==403
 new=receipt_act(f,new,'SUBMIT','unassigned',text='SYNTHETIC actual new party report').json()
 final=receipt_act(f,new,'ACKNOWLEDGE').json();assert final['step']['state']=='LOCAL_ACKNOWLEDGED'
 assert final['current_receipt']['actor_id']=='unassigned' and not final['case_goal_completed']
 now=snapshot(f)
 for table in ('service_receipt_steps','service_receipt_events','service_dispatch_offers','service_dispatch_events'):
  for original in old[table]:assert original in now[table]
 assert snapshot(f,AUTHORITY)==authority
 assert recover(f,row,key).json()['event']==r['event']
 # A new app/Store reads the persistent event without adopting a trust/permission cache.
 with f[1].connect() as c: assert c.execute('SELECT state FROM cases WHERE id=%s',(UUID(parent['case_id']),)).fetchone()['state']=='NEEDS_INPUT'
 assert sd.recover_reassignment(Store(f[0].dsn),f[2][REVIEWER],UUID(row['dispatch_id']),key)['status']=='COMMITTED'

@pytest.mark.parametrize('decision',['DECLINE','WITHDRAW'])
def test_new_party_rejection_does_not_restore_old_writes_and_can_explicitly_handoff_again(receipt_fixture,decision):
 f=receipt_fixture;parent,row=accepted(f);old_id=row['receipt_step_id'];body=body_for(f,parent,row)
 pending=post(f,row,body).json();closed=decide(f,pending,decision).json()
 assert receipt_act(f,step(f,old_id),'SUBMIT').status_code==409
 pending=post(f,closed,body_for(f,parent,closed)).json();done=decide(f,pending,'ACCEPT').json()
 assert done['receipt_step_id']!=old_id and step(f,old_id)['record_mode']=='HISTORICAL_GENERATION'


def test_multiple_handoffs_back_to_original_party_use_distinct_receipt_generations(receipt_fixture):
 f=receipt_fixture;parent,row=accepted(f);ids=[row['receipt_step_id']]
 for target in ('unassigned','executor-a','unassigned'):
  row=post(f,row,body_for(f,parent,row,target)).json();row=decide(f,row,'ACCEPT').json();ids.append(row['receipt_step_id'])
 assert len(set(ids))==4
 for id in ids[:-1]:assert step(f,id)['record_mode']=='HISTORICAL_GENERATION'
 assert step(f,ids[-1])['record_mode']=='CURRENT_GENERATION'

@pytest.mark.parametrize('user',['fixture-a','fixture-b','fixture-c','executor-a','unassigned','prep-specialist-fixture-b'])
def test_wrong_role_scope_or_current_reviewer_cannot_reassign_or_recover(receipt_fixture,user):
 f=receipt_fixture;parent,row=accepted(f);b=body_for(f,parent,row);before=snapshot(f)
 assert post(f,row,b,user=user).status_code==403
 assert recover(f,row,uuid4().hex,user).status_code==403
 assert snapshot(f)==before

@pytest.mark.parametrize('change',['target_assignment','target_read','target_inactive','target_role','target_org','reviewer_grant','reviewer_read','owner_execute'])
def test_current_authority_refusal_before_new_handoff_and_replay(receipt_fixture,change):
 f=receipt_fixture;parent,row=accepted(f);b=body_for(f,parent,row);key=uuid4().hex;assert post(f,row,b,key).status_code==201
 target='unassigned' if change.startswith('target') else REVIEWER if change.startswith('reviewer') else 'fixture-a'
 with f[1].connect() as c:
  f[1].lock_principal(c,target,exclusive=True)
  if change=='target_assignment':c.execute('UPDATE run_assignments SET active=false WHERE principal_id=%s',(target,))
  elif change=='reviewer_grant':c.execute('UPDATE preparation_grants SET active=false WHERE principal_id=%s',(target,))
  elif change in ('target_read','reviewer_read','owner_execute'):c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',(target,'EXECUTE' if change=='owner_execute' else 'READ'))
  else:c.execute('UPDATE principals SET '+{'target_inactive':'active=false','target_role':"role='resource_admin'",'target_org':"org_id='org-b'"}[change]+' WHERE id=%s',(target,))
 before=snapshot(f);assert post(f,row,b,key).status_code==403 and snapshot(f)==before

@pytest.mark.parametrize('field,value',[('executor_id','executor-a'),('executor_id','executor-b'),('predecessor_offer_id','00000000-0000-0000-0000-000000000000'),('predecessor_receipt_step_id','00000000-0000-0000-0000-000000000000'),('expected_dispatch_revision',1),('expected_preparation_revision',1),('expected_receipt_revision',2)])
def test_exact_predecessor_and_versions_required(receipt_fixture,field,value):
 f=receipt_fixture;parent,row=accepted(f);b=body_for(f,parent,row);b[field]=value;before=snapshot(f)
 assert post(f,row,b).status_code in (403,409) and snapshot(f)==before

@pytest.mark.parametrize('state',['RECEIPT_RECORDED','CHANGES_REQUESTED','LOCAL_ACKNOWLEDGED','AWAITING_RECEIPT'])
def test_any_submitted_receipt_or_reopened_history_prevents_handoff(receipt_fixture,state):
 f=receipt_fixture;parent,row=accepted(f);b=body_for(f,parent,row);current=receipt_act(f,step(f,row['receipt_step_id']),'SUBMIT').json()
 if state=='CHANGES_REQUESTED':current=receipt_act(f,current,'REQUEST_CHANGES').json()
 elif state=='LOCAL_ACKNOWLEDGED':current=receipt_act(f,current,'ACKNOWLEDGE').json()
 elif state=='AWAITING_RECEIPT':current=receipt_act(f,current,'REOPEN').json()
 b['expected_receipt_revision']=current['step']['revision'];before=snapshot(f)
 assert not catalog(f,parent)['can_reassign'];assert post(f,row,b).status_code==409 and snapshot(f)==before


def test_stale_material_and_old_schema_disabled_without_writes(receipt_fixture):
 f=receipt_fixture;parent,row=accepted(f);b=body_for(f,parent,row)
 with f[1].connect() as c:c.execute('DELETE FROM schema_version WHERE version=29')
 before=snapshot(f);assert post(f,row,b).status_code==409 and not catalog(f,parent)['can_reassign'] and snapshot(f)==before
 with f[1].connect() as c:c.execute('INSERT INTO schema_version VALUES(29)')
 assert prep_command(f,parent,'REOPEN',reason='SYNTHETIC new material planning').status_code==200
 before=snapshot(f);assert post(f,row,b).status_code==409 and snapshot(f)==before


def test_old_executor_revocation_does_not_require_new_grant_to_replace_pending_party(receipt_fixture):
 f=receipt_fixture;parent,row=accepted(f);b=body_for(f,parent,row)
 f[1].assign_status('executor-a',UUID(parent['run_id']),active=False)
 authority=snapshot(f,AUTHORITY);pending=post(f,row,b).json();done=decide(f,pending,'ACCEPT').json()
 assert done['current_offer']['executor_id']=='unassigned' and snapshot(f,AUTHORITY)==authority
 assert f[3].get('/api/executor-receipts/'+row['receipt_step_id'],headers=headers(f[2],'executor-a')).status_code==403


def test_changed_key_body_and_cross_case_recovery_rejected_without_mutation(receipt_fixture):
 f=receipt_fixture;parent,row=accepted(f);b=body_for(f,parent,row);key=uuid4().hex;assert post(f,row,b,key).status_code==201
 before=snapshot(f);assert post(f,row,{**b,'reason':'SYNTHETIC different'},key).status_code==409
 unknown=recover(f,row,uuid4().hex).json();assert unknown['status']=='NOT_OBSERVED' and unknown['event'] is None
 other_parent,other=accepted(f);before=snapshot(f);assert recover(f,other,key).status_code==409 and snapshot(f)==before

@pytest.mark.parametrize('same_key',[False,True])
def test_concurrent_reassignment_creates_one_offer_and_one_outbox_event(receipt_fixture,same_key):
 f=receipt_fixture;parent,row=accepted(f);b=sd.Reassign(**body_for(f,parent,row));shared=uuid4().hex;before=snapshot(f)
 def send(i):
  try:return sd.reassign(f[0],f[2][REVIEWER],UUID(row['dispatch_id']),shared if same_key else uuid4().hex,b)['event']
  except Conflict:return None
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(send,range(2)))
 assert sum(x is not None for x in results)==(2 if same_key else 1)
 now=snapshot(f)
 for t in ('service_dispatch_offers','service_dispatch_events'):assert len(now[t])==len(before[t])+1
 added=[x for x in now['dispatch_notice_outbox'] if x not in before['dispatch_notice_outbox']]
 assert len(added)==2 and len({x['event_id'] for x in added})==1
 assert {x['recipient_id'] for x in added}=={'fixture-a','unassigned'}
 assert now['service_receipt_steps']==before['service_receipt_steps']

@pytest.mark.parametrize('first',['submit','handoff'])
def test_submit_vs_handoff_serialized_at_parent_lock(receipt_fixture,first):
 f=receipt_fixture;parent,row=accepted(f);b=sd.Reassign(**body_for(f,parent,row));old_id=UUID(row['receipt_step_id'])
 receipt=er.Command(action='SUBMIT',expected_revision=1,text='SYNTHETIC concurrent report',source_kind='SYNTHETIC',source_label='SYNTHETIC')
 if first=='submit':
  er.command(f[0],f[2]['executor-a'],old_id,uuid4().hex,receipt)
  with pytest.raises(Conflict):sd.reassign(f[0],f[2][REVIEWER],UUID(row['dispatch_id']),uuid4().hex,b)
 else:
  sd.reassign(f[0],f[2][REVIEWER],UUID(row['dispatch_id']),uuid4().hex,b)
  with pytest.raises(Conflict):er.command(f[0],f[2]['executor-a'],old_id,uuid4().hex,receipt)


def test_actual_parallel_submit_and_handoff_have_exactly_one_committed_outcome(receipt_fixture):
 f=receipt_fixture;parent,row=accepted(f);body=sd.Reassign(**body_for(f,parent,row))
 receipt=er.Command(action='SUBMIT',expected_revision=1,text='SYNTHETIC racing report',source_kind='SYNTHETIC',source_label='SYNTHETIC')
 from threading import Barrier
 start=Barrier(2)
 def run(which):
  start.wait(timeout=5)
  try:
   if which=='submit':er.command(f[0],f[2]['executor-a'],UUID(row['receipt_step_id']),uuid4().hex,receipt)
   else:sd.reassign(f[0],f[2][REVIEWER],UUID(row['dispatch_id']),uuid4().hex,body)
   return which
  except Conflict:return None
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,['submit','handoff']))
 assert sum(x is not None for x in results)==1
 current=sd.read(f[0],f[2][REVIEWER],UUID(row['dispatch_id']))
 if 'submit' in results:assert current['current_offer']['state']=='ACCEPTED' and len(step(f,row['receipt_step_id'])['receipt_history'])==1
 else:assert current['current_offer']['state']=='OFFERED' and step(f,row['receipt_step_id'])['receipt_history']==[]


def test_event_failure_rolls_back_offer_root_invalidation_and_outbox(receipt_fixture):
 f=receipt_fixture;parent,row=accepted(f);b=sd.Reassign(**body_for(f,parent,row));before=snapshot(f)
 with f[1].connect() as c:c.execute('REVOKE INSERT ON service_dispatch_events FROM parkweave_app')
 with pytest.raises(psycopg.errors.InsufficientPrivilege):sd.reassign(f[0],f[2][REVIEWER],UUID(row['dispatch_id']),uuid4().hex,b)
 assert snapshot(f)==before


def test_migration29_repeat_preserves_rows_and_enforces_unique_receipt_per_offer(receipt_fixture):
 f=receipt_fixture;parent,row=accepted(f);before=snapshot(f);f[1].migrate();assert snapshot(f)==before
 from pathlib import Path
 with f[1].connect() as c:
  f[1]._case_fact_fixture_receipt.authorize_migration(c);c.execute('DELETE FROM schema_version WHERE version IN (30,31,32)');c.execute(Path('src/parkweave/migration-029.sql').read_text());c.rollback()
 assert snapshot(f)==before
 pending=post(f,row,body_for(f,parent,row)).json()
 with pytest.raises(psycopg.errors.UniqueViolation):
  with f[1].connect() as c:c.execute("UPDATE service_dispatch_offers SET state='ACCEPTED',receipt_step_id=%s WHERE id=%s",(UUID(row['receipt_step_id']),UUID(pending['current_offer']['id'])))
 assert f[3].get('/api/service-dispatches/'+row['dispatch_id'],headers=headers(f[2],REVIEWER)).json()['current_offer']['state']=='OFFERED'


def test_no_handoff_marker_cannot_use_removed_material_generation_unique_constraint(receipt_fixture):
 f=receipt_fixture;parent,row=accepted(f);pending=post(f,row,body_for(f,parent,row)).json()
 with f[1].connect() as c:c.execute("UPDATE service_dispatch_events SET payload=payload-'handoff_kind' WHERE offer_id=%s",(UUID(pending['current_offer']['id']),))
 before=snapshot(f);assert decide(f,pending,'ACCEPT').status_code==409 and snapshot(f)==before


@pytest.mark.parametrize('field,kind',[('predecessor_receipt_revision','bool'),('previous_preparation_revision','float'),('accepted_preparation_revision','float')])
def test_json_lineage_revision_type_is_exact_and_refused_before_accept(receipt_fixture,field,kind):
 from psycopg.types.json import Jsonb
 f=receipt_fixture;parent,row=accepted(f);pending=post(f,row,body_for(f,parent,row)).json()
 with f[1].connect() as c:
  event=c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action='REOFFER'",(UUID(pending['current_offer']['id']),)).fetchone()['payload']
  assert type(event[field]) is int
  if kind=='bool':assert event[field]==1
  event[field]=True if kind=='bool' else float(event[field])
  c.execute("UPDATE service_dispatch_events SET payload=%s WHERE offer_id=%s AND action='REOFFER'",(Jsonb(event),UUID(pending['current_offer']['id'])))
  actual=c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action='REOFFER'",(UUID(pending['current_offer']['id']),)).fetchone()['payload'][field]
  assert type(actual) is (bool if kind=='bool' else float)
 before=snapshot(f);assert decide(f,pending,'ACCEPT').status_code==409 and snapshot(f)==before


def test_json_original_acceptance_revision_type_cannot_prove_pending_predecessor(receipt_fixture):
 from psycopg.types.json import Jsonb
 f=receipt_fixture;parent,row=accepted(f);body=body_for(f,parent,row)
 with f[1].connect() as c:
  event=c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action='ACCEPT'",(UUID(row['current_offer']['id']),)).fetchone()['payload']
  assert type(event['revision']) is int;event['revision']=float(event['revision'])
  c.execute("UPDATE service_dispatch_events SET payload=%s WHERE offer_id=%s AND action='ACCEPT'",(Jsonb(event),UUID(row['current_offer']['id'])))
  assert type(c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action='ACCEPT'",(UUID(row['current_offer']['id']),)).fetchone()['payload']['revision']) is float
 before=snapshot(f);assert not catalog(f,parent)['can_reassign'];assert post(f,row,body).status_code==409 and snapshot(f)==before

@pytest.mark.parametrize('attribute',['_isolated_run_access','_isolated_dispatch_execution_preview','_isolated_receipt_execution_preview'])
def test_isolated_adapter_paths_do_not_enable_handoff(receipt_fixture,attribute):
 f=receipt_fixture;parent,row=accepted(f);b=sd.Reassign(**body_for(f,parent,row));setattr(f[0],attribute,object())
 try:
  with f[1].connect() as c:assert not sd._handoff_enabled(f[0],c)
 finally:delattr(f[0],attribute)
