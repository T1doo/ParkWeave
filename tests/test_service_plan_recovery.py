"""Original key historical recovery: owned PG/API, no command replay or observation writes."""
import json,time
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave import service_case_steps as plans
from test_service_case_steps import preparation_fixture,receipt_fixture,link_fixture,setup,adopt,adopt_body,command,read,step,verified,accepted,GOALS
from test_preparation import headers
from test_case_goal_results import snapshot,complete,local_act,local_read
from test_request_intents import save

def recover(f,p,key=None,user='fixture-a'):
 return f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan/command-recovery',headers=headers(f[2],user,key))

def original(f,action):
 p=setup(f,GOALS[0]);key=str(uuid4())
 if action=='ADOPT':data=adopt_body(f,p);response=adopt(f,p,data,key);return p,key,response,data
 row=adopt(f,p).json()
 if action=='RETRY':assert command(f,p,'P1','REPORT_FAILURE',row=row).status_code==200;row=read(f,p).json()
 data=dict(action=action,step_id=step(row,'P1')['id'],expected_revision=row['revision'],reason='SYNTHETIC PRIVATE_ORIGINAL_PLAN_REASON',expected_source_sha256=step(row,'P1')['source_sha256'] if action=='VERIFY' else None)
 response=f[3].post('/api/preparations/'+p['preparation_id']+'/service-case-plan/commands',headers=headers(f[2],key=key),json=data)
 return p,key,response,data

@pytest.mark.parametrize('action',['ADOPT','BEGIN','REPORT_FAILURE','RETRY','VERIFY'])
def test_original_five_actions_exact_event_read_only_repeated_cold_store_and_idempotency(link_fixture,action):
 f=link_fixture;p,key,response,data=original(f,action);assert response.status_code in (200,201)
 receipt=response.json()['command_receipt'];before=snapshot(f)
 for _ in range(3):
  r=recover(f,p,key);assert r.status_code==200;x=r.json();assert x['status']=='COMMITTED' and x['event']['id']==receipt['id'] and x['event']['actor_ref']==receipt['actor_ref'];assert x['event']['expected_revision']==receipt['expected_revision'];assert x['historical_only'] and x['read_only'] and not x['automatically_replayed'] and not x['case_goal_completed'];assert x['current']['read_only'] and not x['current']['can_adopt'];assert all(not s['allowed_actions'] and s['verified_sources'] is None and s['source_sha256'] is None for s in x['current']['steps']);assert 'PRIVATE_' not in json.dumps(x) and snapshot(f)==before
 with ThreadPoolExecutor(4) as pool:results=list(pool.map(lambda _:recover(f,p,key),range(4)))
 assert all(r.status_code==200 and r.json()['event']['id']==receipt['id'] for r in results) and snapshot(f)==before
 from parkweave.store import Store
 cold=plans.recover(Store(f[0].dsn),f[2]['fixture-a'],__import__('uuid').UUID(p['preparation_id']),key);assert cold==x and snapshot(f)==before
 path='/api/preparations/'+p['preparation_id']+'/service-case-plan'+('' if action=='ADOPT' else '/commands')
 replay=f[3].post(path,headers=headers(f[2],key=key),json=data);assert replay.status_code in (200,201) and replay.json()['command_receipt']==receipt and snapshot(f)==before
 changed=f[3].post(path,headers=headers(f[2],key=key),json={**data,'reason':'SYNTHETIC changed body'});assert changed.status_code==409 and snapshot(f)==before

def test_no_request_not_observed_and_other_case_key_never_mean_failure(link_fixture):
 f=link_fixture;p,key,response,_=original(f,'ADOPT');p2=setup(f,GOALS[0]);before=snapshot(f)
 assert recover(f,p).json()['status']=='NO_REQUEST' and recover(f,p,str(uuid4())).json()['status']=='NOT_OBSERVED'
 assert recover(f,p2,key).status_code==409 and snapshot(f)==before

@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a','executor-b'])
def test_another_actor_key_does_not_grant_original_recovery(link_fixture,user):
 f=link_fixture;p,key,_,_=original(f,'VERIFY');before=snapshot(f);r=recover(f,p,key,user);assert r.status_code==403 and 'PRIVATE_' not in r.text and key not in r.text and snapshot(f)==before

@pytest.mark.parametrize('cap',['READ','PREPARE','EXECUTE','ACTIVE','ROLE'])
def test_current_original_authority_required_before_historical_key(link_fixture,cap):
 f=link_fixture;p,key,_,_=original(f,'VERIFY')
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True)
  if cap=='ACTIVE':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
  elif cap=='ROLE':c.execute("UPDATE principals SET role='service_executor' WHERE id='fixture-a'")
  elif cap=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
  else:c.execute("UPDATE capability_grants SET active=false,revision=revision+1 WHERE principal_id='fixture-a' AND capability=%s",(cap,))
 before=snapshot(f);assert recover(f,p,key).status_code==403 and snapshot(f)==before
 if cap=='EXECUTE':assert recover(f,p).status_code==200 and recover(f,p).json()['status']=='NO_REQUEST' and snapshot(f)==before

def test_original_specialist_and_executor_recovery_current_assignment_required(link_fixture):
 f=link_fixture;p=setup(f,GOALS[2]);row=adopt(f,p).json();key=str(uuid4());r=command(f,p,'P1','BEGIN',row=row,user='prep-specialist-fixture-a',key=key);assert r.status_code==200;before=snapshot(f);x=recover(f,p,key,'prep-specialist-fixture-a');assert x.status_code==200 and x.json()['event']['action']=='BEGIN' and snapshot(f)==before
 with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
 before=snapshot(f);assert recover(f,p,key,'prep-specialist-fixture-a').status_code==403 and snapshot(f)==before
 with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=true WHERE principal_id='prep-specialist-fixture-a' AND capability='REVIEW_ASSIGNED'")
 g,d=accepted(f,p);row=read(f,p).json();key2=str(uuid4());r=command(f,p,'P3','BEGIN',row=row,user='executor-a',key=key2);assert r.status_code==200;before=snapshot(f);assert recover(f,p,key2,'executor-a').status_code==200 and snapshot(f)==before
 with f[1].connect() as c:c.execute("UPDATE run_assignments SET active=false WHERE principal_id='executor-a' AND run_id=%s",(p['run_id'],))
 before=snapshot(f);assert recover(f,p,key2,'executor-a').status_code==403 and snapshot(f)==before

def test_original_executor_key_cannot_read_after_current_offer_actor_changes(link_fixture):
 f=link_fixture;p=setup(f,GOALS[2]);assert adopt(f,p).status_code==201;_,d=accepted(f,p);key=str(uuid4());assert command(f,p,'P3','BEGIN',user='executor-a',key=key).status_code==200
 # Fault only changes a synthetic existing offer source; no new assignment/grant.
 with f[1].connect() as c:c.execute("UPDATE service_dispatch_offers SET executor_id='executor-b' WHERE id=%s",(d['current_offer']['id'],))
 before=snapshot(f);r=recover(f,p,key,'executor-a');assert r.status_code==403 and 'executor-b' not in r.text and key not in r.text and snapshot(f)==before

def test_request_replacement_preserves_old_plan_event_without_observation_write(link_fixture):
 f=link_fixture;p,key,r,data=original(f,'VERIFY');old=r.json();assert save(f,p,goals=[GOALS[0],GOALS[1]],text='SYNTHETIC changed current request').status_code==200
 before=snapshot(f);x=recover(f,p,key).json();assert x['event']['current_plan'] and x['current']['state']=='BLOCKED' and snapshot(f)==before
 body=adopt_body(f,{**p,'revision':x['current']['preparation_revision']});body['expected_plan_revision']=old['revision'];r=adopt(f,p,body);assert r.status_code==201
 before=snapshot(f);x=recover(f,p,key).json();assert not x['event']['current_plan'] and x['event']['plan_id']==old['plan_id'] and x['current']['plan_id']!=old['plan_id'];assert x['current']['history']==[{'id':old['plan_id'],'revision':old['revision']}] and snapshot(f)==before
 # Reconstruct the first ADOPT proof even after replacement.
 old_key=old['events'][0]['request_key'];assert recover(f,p,old_key).json()['event']['expected_revision']==0 and snapshot(f)==before

@pytest.mark.parametrize('damage',['fingerprint','reason','revision','source','step','duplicate','adopt-binding','coordination-type'])
def test_damaged_original_proof_rejected_without_downgrade_or_effect(link_fixture,damage):
 f=link_fixture;p,key,_,_=original(f,'VERIFY')
 with f[1].connect() as c:
  row=c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'];e=row['events'][-1]
  if damage=='fingerprint':e['fingerprint']='0'*64
  elif damage=='reason':e['reason']='SYNTHETIC altered reason'
  elif damage=='revision':e['revision']=True
  elif damage=='source':e['sources']={'SYNTHETIC':'forged'}
  elif damage=='step':e['step_id']=str(uuid4())
  elif damage=='duplicate':row['events'].append(deepcopy(e));row['revision']+=1
  elif damage=='adopt-binding':row['adoption_preview']['case_id']=str(uuid4())
  else:e['coordination_only']=0
  c.execute('UPDATE preparations SET service_case_plan=%s WHERE id=%s',(Jsonb(row),p['preparation_id']))
 before=snapshot(f);assert recover(f,p,key).status_code==409 and recover(f,p).status_code==409 and snapshot(f)==before

def test_read_waits_for_original_uncommitted_write_then_no_duplicate_event(link_fixture,monkeypatch):
 import threading
 f=link_fixture;p=setup(f,GOALS[0]);row=adopt(f,p).json();key=str(uuid4());held=threading.Event();release=threading.Event();save_real=plans._save
 def save_wait(c,parent,plan):save_real(c,parent,plan);held.set();assert release.wait(5)
 monkeypatch.setattr(plans,'_save',save_wait)
 with ThreadPoolExecutor(2) as pool:
  write=pool.submit(command,f,p,'P1','BEGIN',row=row,key=key);assert held.wait(5);read_pending=pool.submit(recover,f,p,key)
  time.sleep(.05);assert not read_pending.done();release.set();posted=write.result(5);r=read_pending.result(5)
 assert posted.status_code==200 and r.status_code==200 and r.json()['status']=='COMMITTED';before=snapshot(f);assert recover(f,p,key).json()['event']['id']==posted.json()['command_receipt']['id'] and snapshot(f)==before
 with f[1].connect() as c:assert len(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan']['events'])==2

def test_actual_resource_expiry_during_last_lifecycle_lock_wait_is_read_only(link_fixture):
 f=link_fixture;p,g,d,s=complete(f,local=True)
 with f[1].connect() as c:c.execute("UPDATE synthetic_resource_holds SET starts_at=clock_timestamp()-interval '1 minute',ends_at=clock_timestamp()+interval '2 seconds' WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],))
 for adapter in ('P2','P3','P4'):verified(f,p,adapter)
 assert local_act(f,p,local_read(f,p).json(),'REVALIDATE').status_code==200;row=verified(f,p,'P5');key=row['command_receipt']['request_key'];before=snapshot(f)
 with f[1].connect() as block,ThreadPoolExecutor(1) as pool:
  block.execute('SELECT preparation_id FROM case_local_lifecycles WHERE preparation_id=%s FOR UPDATE',(p['preparation_id'],));pending=pool.submit(recover,f,p,key);deadline=time.monotonic()+1;waiting=False
  while time.monotonic()<deadline:
   block.execute('SELECT pg_stat_clear_snapshot()');waiting=block.execute("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%FROM case_local_lifecycles%%') waiting").fetchone()['waiting']
   if waiting:break
   time.sleep(.01)
  assert waiting;block.execute("SELECT pg_sleep(greatest(0,extract(epoch from (max(ends_at)-clock_timestamp())))+.03) FROM synthetic_resource_holds WHERE id IN (SELECT hold_id FROM synthetic_resource_combination_members WHERE combination_id=%s)",(g['id'],));block.commit();r=pending.result(5)
 assert r.status_code==200 and r.json()['event']['action']=='VERIFY';current=r.json()['current'];assert step(current,'P2')['actual_business_state']=='LINK_NEEDS_RECHECK' and step(current,'P2')['state']!='VERIFIED' and step(current,'P5')['state']!='VERIFIED' and snapshot(f)==before

from test_isolated_run_access import access_fixture,act as access_act

def test_actual_managed_run_deadline_expires_while_recovery_waits_on_parent(access_fixture):
 from datetime import datetime,timedelta,timezone
 from parkweave import resource_combinations as rc
 from test_preparation import command as prep_act
 from test_case_resources import group,post as link
 from test_service_dispatches import offer,command as dispatch_act,REVIEWER
 a=access_fixture;f,p,bridge,_,_=a;bridge.clock=lambda:datetime.now(timezone.utc);rc.seed_synthetic(f[1]);now=bridge.clock();access_act(a,'REQUEST',requested_validity=dict(valid_from=now.isoformat(),valid_until=(now+timedelta(minutes=10)).isoformat(),timezone='UTC'));access_act(a,'APPROVE')
 r=save(f,p,goals=[GOALS[2]],text='SYNTHETIC managed original plan');assert r.status_code==200;p={**p,'revision':r.json()['revision']};p=prep_act(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC review').json();p=prep_act(f,p,'CONFIRM',reason='SYNTHETIC confirm').json();assert adopt(f,p).status_code==201;verified(f,p,'P1');g=group(f);assert link(f,p,g).status_code==201;verified(f,p,'P2');d=offer(f,p)[0];assert d.status_code==201;assert dispatch_act(f,d.json(),'ACCEPT').status_code==200
 key=str(uuid4());r=command(f,p,'P3','BEGIN',user='executor-a',key=key);assert r.status_code==200 and recover(f,p,key,'executor-a').status_code==200
 access_act(a,'REVOKE');now=bridge.clock();end=now+timedelta(seconds=2);access_act(a,'REQUEST',requested_validity=dict(valid_from=now.isoformat(),valid_until=end.isoformat(),timezone='UTC'));access_act(a,'APPROVE');before=snapshot(f)
 with f[1].connect() as block,ThreadPoolExecutor(1) as pool:
  block.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],));pending=pool.submit(recover,f,p,key,'executor-a');deadline=time.monotonic()+1;waiting=False
  while time.monotonic()<deadline:
   block.execute('SELECT pg_stat_clear_snapshot()');waiting=block.execute("SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query ILIKE '%%FROM preparations%%FOR UPDATE%%') waiting").fetchone()['waiting']
   if waiting:break
   time.sleep(.01)
  assert waiting;block.execute('SELECT pg_sleep(greatest(0,extract(epoch from (%s::timestamptz-clock_timestamp())))+.03)',(end,));block.commit();r=pending.result(5)
 assert r.status_code==403 and key not in r.text and snapshot(f)==before
