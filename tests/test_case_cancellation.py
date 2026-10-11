"""Ordinary owner Case cancellation: real owned PG and in-process ASGI only."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import UUID, uuid4
import json, threading, time
import psycopg, pytest
from parkweave import case_cancellation as cc, preparation as prep, service_dispatches as sd, executor_receipts as er
from parkweave.store import Store, Conflict
from test_preparation import preparation_fixture, headers, command as material_command, filled
from test_executor_receipts import receipt_fixture, ready, create as legacy_create
from test_case_resources import link_fixture, group, post as bind, get as link_read
from test_service_dispatches import offer, command as dispatch_command, read as dispatch_read
from test_resource_combinations import cancel as release_group
from test_isolated_run_access import access_fixture
from test_receipt_execution_preview import receipt_preview_fixture


def get(f,p,user='fixture-a'):
 return f[3].get('/api/preparations/'+p['preparation_id']+'/case-cancellation',headers=headers(f[2],user))

def body(f,p):
 x=get(f,p);assert x.status_code==200,x.text;x=x.json()
 return dict(case_id=x['case_id'],expected_preparation_revision=x['preparation_revision'],
   expected_lifecycle_revision=x['lifecycle_revision'],expected_source_sha256=x['source_sha256'],
   confirm_cancel=True,reason='SYNTHETIC owner no longer needs this request')

def post(f,p,data=None,key=None,user='fixture-a'):
 return f[3].post('/api/preparations/'+p['preparation_id']+'/case-cancellation',headers=headers(f[2],user,key or uuid4().hex),json=data or body(f,p))

def recover(f,p,key,user='fixture-a'):
 return f[3].get('/api/preparations/'+p['preparation_id']+'/case-cancellation/recovery/'+key,headers=headers(f[2],user))

def snapshot(f):
 tables=('runs','operations','cases','preparations','preparation_evidence','preparation_events','case_local_lifecycles','case_local_events','controlled_plans','controlled_plan_events','service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps','service_step_receipts','service_receipt_events','case_resource_links','resource_case_claims','synthetic_resource_holds','synthetic_resource_combinations','synthetic_resource_combination_receipts')
 with f[1].connect() as c:
  return {t:sorted(c.execute('SELECT row_to_json(x) r FROM '+t+' x').fetchall(),key=lambda x:json.dumps(x,sort_keys=True,default=str)) for t in tables}


@pytest.mark.parametrize('state',['UNASSIGNED','OFFERED','DECLINED','WITHDRAWN'])
def test_allowed_lineages_replay_cold_get_and_original_success_kept(link_fixture,state):
 f=link_fixture;p=ready(f)
 if state!='UNASSIGNED':
  d=offer(f,p)[0].json()
  if state!='OFFERED':d=dispatch_command(f,d,'DECLINE' if state=='DECLINED' else 'WITHDRAW').json()
 original=snapshot(f);data=body(f,p);key=uuid4().hex;r=post(f,p,data,key);assert r.status_code==200,r.text
 assert post(f,p,data,key).json()==r.json()
 assert post(f,p,{**data,'reason':'changed'},key).status_code==409
 current=get(f,p).json();assert current['case_state']=='CANCELLED' and not current['can_cancel']
 after=snapshot(f)
 assert all(after[t]==original[t] for t in original if t not in ('cases','case_local_lifecycles','case_local_events'))
 # A response dropped after commit is recovered only by GET with the original key.
 proof=recover(f,p,key);assert proof.status_code==200,proof.text
 assert {k:proof.json()[k] for k in r.json()}==r.json()
 cold=cc.recover(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key)
 assert cold['event_id']==r.json()['event_id'] and snapshot(f)==after
 assert recover(f,p,uuid4().hex).json()['status']=='NOT_OBSERVED'
 if state!='UNASSIGNED':
  hist=dispatch_read(f,d,'executor-a').json();assert hist['case_cancelled'] and not hist['can_accept']
  assert hist['current_offer']['state']==state and not hist['can_reoffer']
  for action,user in [('ACCEPT','executor-a'),('DECLINE','executor-a'),('WITHDRAW','prep-specialist-fixture-a')]:
   assert dispatch_command(f,d,action,user).status_code==409
  assert offer(f,p,revision=d['revision'])[0].status_code==409
 assert snapshot(f)==after


@pytest.mark.parametrize('bad',['accept','historical_accept','receipt','closed','isolated','unverified','run_not_success','receipt_corrupt'])
def test_explicit_unsupported_origins_and_history_refused(receipt_fixture,bad):
 f=receipt_fixture;p=ready(f)
 if bad in ('accept','historical_accept'):
  d=offer(f,p)[0].json();assert dispatch_command(f,d,'ACCEPT').status_code==200
  if bad=='historical_accept':
   p=material_command(f,p,'REOPEN',reason='SYNTHETIC changed input').json()
   p=material_command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC changed input checked').json()
   p=material_command(f,p,'CONFIRM',reason='SYNTHETIC changed input confirmed').json()
   d=offer(f,p,revision=2,recovery_receipt_step_id=dispatch_read(f,d).json()['receipt_step_id'])[0].json()
   assert d['current_offer']['state']=='OFFERED'
 elif bad=='receipt':assert legacy_create(f,p)[0].status_code==201
 elif bad=='closed':
  with f[1].connect() as c:c.execute("INSERT INTO case_local_lifecycles(preparation_id,case_id,revision,cycle,state,verified_snapshot,verified_sha256) VALUES(%s,%s,1,1,'LOCAL_RECORD_CLOSED','{}',repeat('0',64))",(p['preparation_id'],p['case_id']))
 else:
  with f[1].connect() as c:
   if bad=='isolated':c.execute("UPDATE runs SET input=input||'{\"isolated_execution\":true}'::jsonb WHERE id=%s",(p['run_id'],))
   elif bad=='unverified':c.execute("UPDATE operations SET state='PREPARED' WHERE run_id=%s",(p['run_id'],))
   elif bad=='run_not_success':c.execute("UPDATE runs SET state='RUNNING' WHERE id=%s",(p['run_id'],))
   else:c.execute("UPDATE operations SET receipt=jsonb_set(receipt,'{source}','\"ISOLATED\"') WHERE run_id=%s",(p['run_id'],))
 data=body(f,p);before=snapshot(f);assert get(f,p).json()['blockers']
 assert post(f,p,data).status_code==409 and snapshot(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a','unassigned'])
def test_cancel_owner_and_tenant_scope_before_private_read(receipt_fixture,user):
 f=receipt_fixture;p=ready(f);data=body(f,p);key=uuid4().hex;before=snapshot(f)
 for r in (get(f,p,user),post(f,p,data,key,user),recover(f,p,key,user)):
  assert r.status_code==403,r.text;assert 'SYNTHETIC owner no longer' not in r.text
 assert snapshot(f)==before


@pytest.mark.parametrize('cap',['READ','PREPARE','EXECUTE','INACTIVE'])
def test_revoked_cancel_and_recovery_authority(receipt_fixture,cap):
 f=receipt_fixture;p=ready(f);data=body(f,p);key=uuid4().hex;assert post(f,p,data,key).status_code==200
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True)
  if cap=='INACTIVE':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
  elif cap=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
  else:c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
 before=snapshot(f);assert post(f,p,data,key).status_code==403
 assert recover(f,p,key).status_code==(200 if cap=='EXECUTE' else 403)
 assert snapshot(f)==before


@pytest.mark.parametrize('field,value',[('reason',' '),('confirm_cancel',False),('confirm_cancel',1),('expected_preparation_revision',True)])
def test_explicit_reason_and_confirmation_validated(receipt_fixture,field,value):
 f=receipt_fixture;p=ready(f);data=body(f,p);before=snapshot(f)
 assert post(f,p,{**data,field:value}).status_code==422 and snapshot(f)==before


@pytest.mark.parametrize('change',['material','case','version','key_other_case'])
def test_exact_source_and_key_scope(receipt_fixture,change):
 f=receipt_fixture;p=ready(f);data=body(f,p);key=uuid4().hex
 if change=='material':assert material_command(f,p,'REOPEN',reason='SYNTHETIC update').status_code==200
 elif change=='case':data['case_id']=str(uuid4())
 elif change=='version':data['expected_preparation_revision']+=1
 else:
  assert post(f,p,data,key).status_code==200;p=ready(f);data=body(f,p)
 before=snapshot(f);assert post(f,p,data,key).status_code==409 and snapshot(f)==before


def test_event_failure_rolls_back_every_change(receipt_fixture):
 f=receipt_fixture;p=ready(f);data=body(f,p);before=snapshot(f)
 with f[1].connect() as c:
  c.execute("CREATE FUNCTION fail_cancel_event() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN IF NEW.action='CANCEL_BEFORE_ACCEPT' THEN RAISE EXCEPTION 'SYNTHETIC cancellation event fault'; END IF; RETURN NEW; END$$")
  c.execute('CREATE TRIGGER fail_cancel_event BEFORE INSERT ON case_local_events FOR EACH ROW EXECUTE FUNCTION fail_cancel_event()')
 with pytest.raises(psycopg.errors.RaiseException,match='SYNTHETIC cancellation event fault'):
  cc.cancel(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,cc.Cancel.model_validate(data))
 assert snapshot(f)==before


@pytest.mark.parametrize('same',[True,False])
def test_same_and_different_key_concurrent_cancel_one_event(receipt_fixture,same):
 f=receipt_fixture;p=ready(f);data=body(f,p);k=uuid4().hex
 def run(i):
  try:return cc.cancel(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),k if same else str(i),cc.Cancel.model_validate(data))
  except Conflict:return 'CONFLICT'
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
 if same:assert results[0]==results[1]
 else:assert results.count('CONFLICT')==1
 with f[1].connect() as c:assert c.execute("SELECT count(*) n FROM case_local_events WHERE action='CANCEL_BEFORE_ACCEPT'").fetchone()['n']==1


def wait_for_pg_lock(f,fragment):
 deadline=time.monotonic()+3
 while time.monotonic()<deadline:
  with f[1].connect() as c:
   rows=c.execute("SELECT pid,wait_event,query FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND position(%s in query)>0",(fragment,)).fetchall()
  if rows:return rows
  time.sleep(.02)
 raise AssertionError('actual PG lock wait not observed: '+fragment)


@pytest.mark.parametrize('writer',['accept','material','offer','plan','link'])
def test_cancel_first_real_pg_wait_blocks_all_competitors(link_fixture,writer):
 f=link_fixture;p=ready(f);d=offer(f,p)[0].json() if writer=='accept' else None
 g=group(f) if writer=='link' else None;data=body(f,p);results=[]
 def cancel():results.append(('cancel',post(f,p,data).status_code))
 def write():
  if writer=='accept':r=dispatch_command(f,d,'ACCEPT')
  elif writer=='material':r=material_command(f,p,'ADD_EVIDENCE',slot='need_summary',text='SYNTHETIC late',source_kind='USER_STATEMENT',source_label='late')
  elif writer=='offer':r=offer(f,p)[0]
  elif writer=='link':r=bind(f,p,g)
  else:
   from parkweave.controlled_plans import TEMPLATE_SHA
   r=f[3].post('/api/preparations/'+p['preparation_id']+'/controlled-plan',headers=headers(f[2],key=uuid4().hex),json=dict(template_sha256=TEMPLATE_SHA,expected_preparation_revision=p['revision'],required_goals=['LOCAL_SYNTHETIC_COORDINATION_RECORDS']))
  results.append((writer,r.status_code))
 with f[1].connect() as block:
  block.execute('SELECT * FROM cases WHERE id=%s FOR UPDATE',(p['case_id'],))
  t=threading.Thread(target=cancel);t.start();wait_for_pg_lock(f,'SELECT * FROM cases WHERE id=')
  w=threading.Thread(target=write);w.start();wait_for_pg_lock(f,'FROM preparations WHERE id=')
 t.join(5);w.join(5);assert not t.is_alive() and not w.is_alive()
 assert sorted(results)==sorted([('cancel',200),(writer,409)])


def test_accept_first_cancel_waits_then_rejects(receipt_fixture,monkeypatch):
 f=receipt_fixture;p=ready(f);d=offer(f,p)[0].json();data=body(f,p);entered=threading.Event();release=threading.Event();results=[]
 original=er._insert_step
 def paused(*args,**kwargs):
  entered.set();assert release.wait(4);return original(*args,**kwargs)
 monkeypatch.setattr(er,'_insert_step',paused)
 t=threading.Thread(target=lambda:results.append(('accept',dispatch_command(f,d,'ACCEPT').status_code)));t.start();assert entered.wait(3)
 w=threading.Thread(target=lambda:results.append(('cancel',post(f,p,data).status_code)));w.start()
 try:wait_for_pg_lock(f,'FROM preparations WHERE id=')
 finally:release.set()
 t.join(5);w.join(5);assert sorted(results)==[('accept',200),('cancel',409)]
 assert get(f,p).json()['case_state']!='CANCELLED'


def test_cancel_retains_resource_capacity_and_independent_release(link_fixture):
 from parkweave import resource_combinations as rc, resource_holds as rh
 f=link_fixture;p=ready(f);g=group(f);assert bind(f,p,g).status_code==201
 before=snapshot(f);assert post(f,p).status_code==200
 assert snapshot(f)['synthetic_resource_holds']==before['synthetic_resource_holds']
 with f[1].connect() as c:
  for m in g['members']:
   h=c.execute('SELECT * FROM synthetic_resource_holds WHERE id=%s',(m['id'],)).fetchone()
   assert h['state']=='CONFIRMED' and rh._peak(c,h['resource_id'],h['starts_at'],h['ends_at'],rh._now(c))>=h['quantity']
 assert link_read(f,p).status_code==200
 assert release_group(f,g['id']).status_code==200
 assert get(f,p).json()['case_state']=='CANCELLED'


@pytest.mark.parametrize('action,user',[(a,'fixture-a' if a in ('ADD_EVIDENCE','CONFIRM','REOPEN') else 'prep-specialist-fixture-a') for a in prep.PreparationCommand.model_fields['action'].annotation.__args__])
def test_all_material_commands_frozen_before_replay(receipt_fixture,action,user):
 f=receipt_fixture;p=ready(f);assert post(f,p).status_code==200;before=snapshot(f)
 extra=dict(slot='need_summary',text='SYNTHETIC blocked',source_kind='USER_STATEMENT',source_label='blocked') if action=='ADD_EVIDENCE' else dict(reason='SYNTHETIC blocked')
 assert material_command(f,p,action,user,**extra).status_code==409 and snapshot(f)==before


@pytest.mark.parametrize('endpoint',[
 'request-intent','readiness','material-draft','planning-preview','fact-clarifications/declare',
 'fact-clarifications/confirm','fact-bundle/commands','opportunities/commands','material-objections',
 'service-case-plan','service-case-plan/commands','controlled-plan','controlled-plan/commands',
 'local-case/commands','resource-link','resource-delivery'])
def test_all_case_business_write_families_reject_cancelled_before_other_prerequisites(link_fixture,endpoint):
 from parkweave.controlled_plans import TEMPLATE_SHA
 f=link_fixture;p=ready(f);assert post(f,p).status_code==200;before=snapshot(f);rev=p['revision'];sha='0'*64;uid=str(uuid4())
 payloads={
  'request-intent':dict(expected_preparation_revision=rev,request_text='SYNTHETIC request',required_goals=[]),
  'readiness':dict(expected_preparation_revision=rev,expected_source_sha256=sha),
  'planning-preview':dict(expected_preparation_revision=rev,expected_source_sha256=sha),
  'material-draft':dict(expected_preparation_revision=rev,expected_source_sha256=sha,expected_reviewer_id='prep-specialist-fixture-a',confirm_material_share=True),
  'fact-clarifications/declare':dict(expected_preparation_revision=rev,profile='LOCAL_SERVICE_PREPARATION_FACTS_V1',purpose='SERVICE_PREPARATION',reason='SYNTHETIC'),
  'fact-clarifications/confirm':dict(expected_preparation_revision=rev,expected_clarification_revision=1,expected_source_sha256=sha,choices=[dict(field=a,assertion_id=str(uuid4()),expected_assertion_revision=1,expected_assertion_fingerprint=sha) for a in ('region','employees','service_need')],reason='SYNTHETIC'),
  'fact-bundle/commands':dict(action='WITHDRAW',expected_preparation_revision=rev,expected_bundle_revision=0,expected_source_sha256=sha,source_id=uid,reason='SYNTHETIC'),
  'opportunities/commands':dict(action='REFRESH',expected_revision=0,expected_source_sha256=sha,reason='SYNTHETIC'),
  'material-objections':dict(action='RAISE',expected_preparation_revision=rev,expected_version=0,binding_sha256=sha,reason='SYNTHETIC'),
  'service-case-plan':dict(expected_preparation_revision=rev,expected_request_revision=1,expected_source_sha256=sha,required_goals=['LOCAL_MATERIAL_PREPARATION'],reason='SYNTHETIC'),
  'service-case-plan/commands':dict(action='BEGIN',step_id=uid,expected_revision=1,reason='SYNTHETIC'),
  'controlled-plan':dict(template_sha256=TEMPLATE_SHA,expected_preparation_revision=rev,required_goals=['LOCAL_SYNTHETIC_COORDINATION_RECORDS']),
  'controlled-plan/commands':dict(action='CHECK_STEP',step='P1',expected_revision=1,expected_source_sha256=sha,reason='SYNTHETIC'),
  'local-case/commands':dict(action='REOPEN',expected_revision=1,expected_cycle=1,reason='SYNTHETIC'),
  'resource-link':dict(combination_id=uid,expected_preparation_revision=rev,expected_link_revision=0,reason='SYNTHETIC'),
  'resource-delivery':dict(members=[dict(hold_id=str(uuid4()),expected_revision=1) for _ in range(3)],expected_preparation_revision=rev,expected_plan_revision=1,expected_source_sha256=sha,valid_until='2026-10-11T12:00:00Z',reason='SYNTHETIC')}
 r=f[3].post('/api/preparations/'+p['preparation_id']+'/'+endpoint,headers=headers(f[2],key=uuid4().hex),json=payloads[endpoint])
 assert r.status_code==409,r.text;assert 'Case cancelled' in r.text and snapshot(f)==before


def test_legacy_receipt_create_guard_and_executor_receipt_parent_bypass(link_fixture):
 from test_executor_receipts import act as receipt_act
 f=link_fixture;p=ready(f);assert post(f,p).status_code==200;before=snapshot(f)
 assert legacy_create(f,p)[0].status_code==409 and snapshot(f)==before
 # Owner-only corruption injection models an otherwise unreachable historical
 # receipt alongside cancellation. The executor _parent path must still freeze.
 with f[1].connect() as c:
  parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
  step=er._insert_step(c,parent,'executor-a')
 row=f[3].get('/api/executor-receipts/'+str(step['id']),headers=headers(f[2],'executor-a')).json();before=snapshot(f)
 assert receipt_act(f,row,'SUBMIT').status_code==409 and snapshot(f)==before


@pytest.mark.parametrize('kind',['controlled','registered'])
def test_historical_plan_get_does_not_persist_implicit_invalidation(link_fixture,kind):
 f=link_fixture;p=ready(f)
 if kind=='controlled':
  from test_controlled_plans import create,check
  assert create(f,p).status_code==201;assert check(f,p,'P1').status_code==200
 else:
  from test_request_intents import save
  from test_service_case_steps import adopt,command
  p=save(f,p,goals=['LOCAL_MATERIAL_PREPARATION']).json()
  assert adopt(f,p).status_code==201
  p=material_command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC checked').json()
  p=material_command(f,p,'CONFIRM',reason='SYNTHETIC confirmed').json()
  assert command(f,p,'P1').status_code==200
 assert post(f,p).status_code==200
 # Uncoordinated fixture source change would normally record GET invalidation.
 with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=source||'{\"revision\":\"changed\"}'::jsonb")
 before=snapshot(f)
 endpoints=['','/readiness','/material-draft','/fact-clarifications','/controlled-plan','/service-case-plan','/service-case-plan/command-recovery','/planning-preview','/local-case','/case-path','/goal-results']
 for path in endpoints:
  r=f[3].get('/api/preparations/'+p['preparation_id']+path,headers=headers(f[2]));assert r.status_code==200,(path,r.text)
  assert snapshot(f)==before,path
 if kind=='registered':
  r=f[3].get('/api/preparations/'+p['preparation_id']+'/service-case-plan',headers=headers(f[2],'prep-specialist-fixture-a'))
  assert r.status_code==200,r.text
  assert all(not step['allowed_actions'] for step in r.json()['steps'])


def test_old_notice_consumption_and_open_recheck_cancelled_case(receipt_fixture):
 from parkweave import dispatch_notices as dn
 from test_dispatch_notices import drain,inbox,act
 f=receipt_fixture;p=ready(f);d=offer(f,p)[0].json()
 # Deliver one historical offer before cancellation, leave the owner outbox old.
 assert dn.consume(f[0]);assert post(f,p).status_code==200;drain(f)
 with f[1].connect() as c:
  delivered=c.execute('SELECT * FROM dispatch_notices').fetchall()
  assert len(delivered)==1 and c.execute("SELECT count(*) n FROM dispatch_notice_outbox WHERE state='SUPPRESSED'").fetchone()['n']==1
 item=inbox(f,delivered[0]['recipient_id']).json()['items'][0]
 assert item['case_cancelled'] and item['historical'] and not item['actionable']
 opened=act(f,delivered[0]['recipient_id'],item,'OPEN');assert opened.status_code==200
 assert opened.json()['notice']['case_cancelled'] and not opened.json()['notice']['actionable']
 assert dispatch_read(f,d,'executor-a').json()['can_accept'] is False
 assert dispatch_command(f,d,'ACCEPT').status_code==409


@pytest.mark.parametrize('writer',['material','offer','plan','link'])
def test_writer_first_real_pg_wait_cancel_rechecks_committed_sources(link_fixture,writer,monkeypatch):
 f=link_fixture;p=ready(f);g=group(f) if writer=='link' else None;data=body(f,p)
 entered=threading.Event();release=threading.Event();results=[];original=prep.case_write_guard;once=[]
 def pause(c,parent):
  original(c,parent)
  if not once:
   once.append(True);entered.set();assert release.wait(4)
 monkeypatch.setattr(prep,'case_write_guard',pause)
 def write():
  if writer=='material':r=material_command(f,p,'ADD_EVIDENCE',slot='need_summary',text='SYNTHETIC changed first',source_kind='USER_STATEMENT',source_label='first')
  elif writer=='offer':r=offer(f,p)[0]
  elif writer=='link':r=bind(f,p,g)
  else:
   from test_controlled_plans import create
   r=create(f,p)
  results.append((writer,r.status_code))
 t=threading.Thread(target=write);t.start();assert entered.wait(3)
 w=threading.Thread(target=lambda:results.append(('cancel',post(f,p,data).status_code)));w.start()
 try:wait_for_pg_lock(f,'FROM preparations WHERE id=')
 finally:release.set()
 t.join(5);w.join(5);assert not t.is_alive() and not w.is_alive()
 assert sorted(results)==sorted([(writer,200 if writer=='material' else 201),('cancel',409 if writer in ('material','offer') else 200)])
 if writer in ('material','offer'):assert post(f,p).status_code==200


def test_cancelled_handoff_and_material_reuse_bypasses_rejected(link_fixture):
 f=link_fixture;p=ready(f);source=ready(f);d=offer(f,p)[0].json();assert post(f,p).status_code==200;before=snapshot(f)
 handoff=dict(expected_preparation_revision=p['revision'],expected_dispatch_revision=d['revision'],predecessor_offer_id=d['current_offer']['id'],predecessor_receipt_step_id=str(uuid4()),expected_receipt_revision=1,executor_id='unassigned',reason='SYNTHETIC late handoff')
 r=f[3].post('/api/service-dispatches/'+d['dispatch_id']+'/reassign',headers=headers(f[2],'prep-specialist-fixture-a',uuid4().hex),json=handoff)
 assert r.status_code==409 and 'Case cancelled' in r.text and snapshot(f)==before
 reuse=dict(expected_target_revision=p['revision'],source_preparation_id=source['preparation_id'],expected_source_preparation_revision=source['revision'],source_evidence_id=str(uuid4()),expected_source_evidence_version=1,expected_source_evidence_sha256='0'*64,expected_source_snapshot_sha256=source['snapshot_sha256'],purpose='SAME_SERVICE_MATERIAL_OUTLINE',reason='SYNTHETIC late reuse')
 r=f[3].post('/api/preparations/'+p['preparation_id']+'/material-reuse',headers=headers(f[2],key=uuid4().hex),json=reuse)
 assert r.status_code==409 and 'Case cancelled' in r.text and snapshot(f)==before


def test_cancel_migration_requires_actual_creation_ticket_and_existing_rights_unchanged(receipt_fixture):
 from pathlib import Path
 f=receipt_fixture;p=ready(f);assert post(f,p).status_code==200;before=snapshot(f)
 sql=Path('src/parkweave/migration-030.sql').read_text()
 with pytest.raises(psycopg.errors.RaiseException,match='creation ticket required'):
  with f[1].connect() as c:c.execute(sql)
 with f[1].connect() as c:
  grants=c.execute("SELECT grantee,table_name,privilege_type FROM information_schema.role_table_grants WHERE grantee='parkweave_app' ORDER BY table_name,privilege_type").fetchall()
  f[1]._case_fact_fixture_receipt.authorize_migration(c);c.execute(sql)
  assert c.execute("SELECT grantee,table_name,privilege_type FROM information_schema.role_table_grants WHERE grantee='parkweave_app' ORDER BY table_name,privilege_type").fetchall()==grants
 assert snapshot(f)==before
 with pytest.raises(psycopg.errors.InsufficientPrivilege):
  with f[0].connect() as c:c.execute("DELETE FROM case_local_events WHERE action='CANCEL_BEFORE_ACCEPT'")
 with f[1].connect() as c:c.execute('INSERT INTO schema_version VALUES(31)')
 with pytest.raises(Conflict,match='newer than this code'):f[1].migrate()


@pytest.mark.parametrize('damage',['case','local_state','local_revision'])
def test_original_key_post_and_get_require_same_committed_state(receipt_fixture,damage):
 f=receipt_fixture;p=ready(f);data=body(f,p);key=uuid4().hex;assert post(f,p,data,key).status_code==200
 with f[1].connect() as c:
  if damage=='case':c.execute("UPDATE cases SET state='NEEDS_INPUT' WHERE id=%s",(p['case_id'],))
  elif damage=='local_state':c.execute("UPDATE case_local_lifecycles SET state='REOPENED' WHERE preparation_id=%s",(p['preparation_id'],))
  else:c.execute('UPDATE case_local_lifecycles SET revision=revision+1 WHERE preparation_id=%s',(p['preparation_id'],))
 before=snapshot(f)
 assert post(f,p,data,key).status_code==recover(f,p,key).status_code==409
 assert snapshot(f)==before


@pytest.mark.parametrize('level',[1,2,3])
def test_cancelled_preview_history_reads_pure_and_late_execution_rejected(receipt_fixture,tmp_path,level):
 from test_isolated_execution_preview import setup as p1_setup,execute as p1_execute,read as p1_read,body as p1_body
 from test_resource_execution_preview import setup as p2_setup,execute as p2_execute,read as p2_read,body as p2_body
 from test_dispatch_execution_preview import setup as p3_setup,execute as p3_execute,read as p3_read,body as p3_body
 f=receipt_fixture
 if level==1:
  p,p1=p1_setup(f,tmp_path);engines=[p1];steps=[(p1_execute,p1_read,p1_body)]
 elif level==2:
  p,p1,p2=p2_setup(f,tmp_path);engines=[p1,p2];steps=[(p1_execute,p1_read,p1_body),(p2_execute,p2_read,p2_body)]
 else:
  p,p1,p2,p3=p3_setup(f,tmp_path);engines=[p1,p2,p3];steps=[(p1_execute,p1_read,p1_body),(p2_execute,p2_read,p2_body),(p3_execute,p3_read,p3_body)]
 original=[]
 for execute,read,make_body in steps:
  b=make_body(f,p);key=uuid4().hex;r=execute(f,p,b,key);assert r.status_code==201,r.text
  original.append((read,b,key,r.json()['result']))
 assert post(f,p).status_code==200
 before=snapshot(f);files=[engine.path.read_bytes() for engine in engines]
 for (execute,_,_), (read,b,key,result) in zip(steps,original):
  r=read(f,p,key);assert r.status_code==200,r.text
  assert r.json()['result']==result and r.json()['execution_available'] is False and r.json()['case_cancelled']
  r=execute(f,p,b);assert r.status_code==409 and 'Case cancelled' in r.text
 assert snapshot(f)==before and [engine.path.read_bytes() for engine in engines]==files


def test_cancelled_receipt_preview_history_read_and_execute_guard(receipt_preview_fixture):
 from test_isolated_execution_preview import execute as p1_execute
 from test_resource_execution_preview import execute as p2_execute
 from test_dispatch_execution_preview import execute as p3_execute
 from test_receipt_execution_preview import execute,read,body as preview_body
 f,p,p1,p2,p3,p4,_=receipt_preview_fixture
 for run in (p1_execute,p2_execute,p3_execute):
  r=run(f,p);assert r.status_code==201,r.text
 b=preview_body(f,p);key=uuid4().hex;r=execute(f,p,b,key);assert r.status_code==201,r.text;result=r.json()['result']
 assert post(f,p).status_code==200
 before=snapshot(f);files=[engine.path.read_bytes() for engine in (p1,p2,p3,p4)]
 r=read(f,p,key);assert r.status_code==200,r.text
 assert r.json()['result']==result and not r.json()['execution_available']
 r=execute(f,p,b);assert r.status_code==409 and 'Case cancelled' in r.text
 assert snapshot(f)==before and [engine.path.read_bytes() for engine in (p1,p2,p3,p4)]==files
