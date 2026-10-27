"""Accepted but never submitted manual Case: owned PostgreSQL and ASGI evidence."""
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID,uuid4
import threading
import psycopg,pytest
from parkweave import case_cancellation_before_receipt as cr,executor_receipts as er,preparation as prep
from parkweave.store import Store,Conflict
from test_preparation import preparation_fixture,headers,command as material
from test_executor_receipts import receipt_fixture,ready,act,create as legacy_create
from test_case_resources import link_fixture,group,post as bind
from test_service_dispatches import offer,command as decide,read as dispatch_read
from test_pending_receipt_handoff import body_for,post as reassign,step
import test_case_cancellation as old

PATH='/case-cancellation-before-receipt'
def get(f,p,user='fixture-a'):
 return f[3].get('/api/preparations/'+p['preparation_id']+PATH,headers=headers(f[2],user))
def body(f,p):
 r=get(f,p);assert r.status_code==200,r.text;x=r.json()
 return dict(case_id=x['case_id'],expected_preparation_revision=x['preparation_revision'],expected_lifecycle_revision=x['lifecycle_revision'],expected_source_sha256=x['source_sha256'],confirm_cancel=True,reason='SYNTHETIC enterprise cancels before any manual receipt')
def post(f,p,data=None,key=None,user='fixture-a'):
 return f[3].post('/api/preparations/'+p['preparation_id']+PATH,headers=headers(f[2],user,key or uuid4().hex),json=data or body(f,p))
def recover(f,p,key,user='fixture-a'):
 return f[3].get('/api/preparations/'+p['preparation_id']+PATH+'/recovery/'+key,headers=headers(f[2],user))
def accepted(f):
 p=ready(f);r=offer(f,p)[0];assert r.status_code==201,r.text
 r=decide(f,r.json(),'ACCEPT');assert r.status_code==200,r.text
 return p,r.json()
def generation(f,d,user='fixture-a'):return step(f,d['receipt_step_id'],user)


@pytest.mark.parametrize('history',['accepted','handoff_pending','handoff_declined','handoff_withdrawn','handoff_accepted','multiple_handoffs','material_reaccepted'])
def test_full_manual_lineage_preserved_cancel_replay_and_cold_read(link_fixture,history):
 f=link_fixture;p,d=accepted(f);original_id=d['receipt_step_id']
 if history.startswith('handoff') or history=='multiple_handoffs':
  f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
  r=reassign(f,d,body_for(f,p,d));assert r.status_code==201,r.text;d=r.json()
  if history in ('handoff_declined','handoff_withdrawn'):d=decide(f,d,'DECLINE' if history=='handoff_declined' else 'WITHDRAW').json()
  elif history in ('handoff_accepted','multiple_handoffs'):
   d=decide(f,d,'ACCEPT').json()
   if history=='multiple_handoffs':
    for target in ('executor-a','unassigned'):
     d=reassign(f,d,body_for(f,p,d,target)).json();d=decide(f,d,'ACCEPT').json()
 elif history=='material_reaccepted':
  p=material(f,p,'REOPEN',reason='SYNTHETIC material changed').json()
  p=material(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC new check').json()
  p=material(f,p,'CONFIRM',reason='SYNTHETIC new confirmation').json()
  d=offer(f,p,revision=d['revision'],recovery_receipt_step_id=original_id)[0].json();d=decide(f,d,'ACCEPT').json()
 assert get(f,p).json()['can_cancel'],get(f,p).json()['blockers']
 assert old.post(f,p).status_code==409  # Old slice retains its actual ACCEPT refusal.
 before=old.snapshot(f);data=body(f,p);key=uuid4().hex;r=post(f,p,data,key);assert r.status_code==200,r.text
 assert r.json()['event']['action']==cr.ACTION and r.json()['scope']==cr.SCOPE
 assert post(f,p,data,key).json()==r.json();assert post(f,p,{**data,'reason':'changed'},key).status_code==409
 after=old.snapshot(f)
 assert all(before[t]==after[t] for t in before if t not in ('cases','case_local_lifecycles','case_local_events'))
 assert recover(f,p,key).json()['event']==r.json()['event']
 assert cr.recover(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key)['event']==r.json()['event']
 assert old.recover(f,p,key).status_code==409 and old.post(f,p,data,key).status_code==409
 for s in after['service_receipt_steps']:
  row=step(f,str(s['r']['id']));assert row['case_cancelled'] and not row['can_submit'] and not row['local_execution']['can_execute']
 assert old.snapshot(f)==after
 assert not dispatch_read(f,d,'executor-a').json()['can_accept']
 assert f[3].get('/api/executor-receipts',headers=headers(f[2])).json()['items'][0]['case_cancelled']


@pytest.mark.parametrize('state',['RECEIPT_RECORDED','CHANGES_REQUESTED','LOCAL_ACKNOWLEDGED','AWAITING_RECEIPT','old_generation'])
def test_any_historical_submission_refuses_even_reopen_or_new_empty_generation(receipt_fixture,state):
 f=receipt_fixture;p,d=accepted(f);row=act(f,generation(f,d),'SUBMIT').json()
 if state=='CHANGES_REQUESTED':row=act(f,row,'REQUEST_CHANGES').json()
 elif state=='LOCAL_ACKNOWLEDGED':row=act(f,row,'ACKNOWLEDGE').json()
 elif state=='AWAITING_RECEIPT':row=act(f,row,'REOPEN').json()
 elif state=='old_generation':
  p=material(f,p,'REOPEN',reason='SYNTHETIC new input').json()
  p=material(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC review').json();p=material(f,p,'CONFIRM',reason='SYNTHETIC confirmed').json()
  d=offer(f,p,revision=d['revision'],recovery_receipt_step_id=d['receipt_step_id'])[0].json();d=decide(f,d,'ACCEPT').json()
 before=old.snapshot(f);assert 'HISTORICAL_RECEIPT_SUBMISSION_NOT_SUPPORTED' in get(f,p).json()['blockers']
 assert post(f,p).status_code==409 and old.snapshot(f)==before


@pytest.mark.parametrize('kind',['handoff','new_material'])
@pytest.mark.parametrize('strip_offered',[False,True])
def test_later_generation_cannot_become_initial_by_stripping_lineage(receipt_fixture,kind,strip_offered):
 from psycopg.types.json import Jsonb
 f=receipt_fixture;p,d=accepted(f)
 if kind=='handoff':
  f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
  r=reassign(f,d,body_for(f,p,d));assert r.status_code==201,r.text
 else:
  original=d['receipt_step_id'];p=material(f,p,'REOPEN',reason='SYNTHETIC new material').json()
  p=material(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC review').json()
  p=material(f,p,'CONFIRM',reason='SYNTHETIC confirmation').json()
  r=offer(f,p,revision=d['revision'],recovery_receipt_step_id=original)[0];assert r.status_code==201,r.text
 r=decide(f,r.json(),'ACCEPT');assert r.status_code==200,r.text;d=r.json()
 dispatch_base={'dispatch_id','offer_id','receipt_step_id','revision','action','state','actor_id','executor_id','reason'}
 create_base={'step_id','revision','state','action','actor_id','scope','dispatch_id','offer_id','reason'}
 with f[1].connect() as c:
  for table,identity,actions,keys in [('service_dispatch_events','offer_id',['ACCEPT','REOFFER'] if strip_offered else ['ACCEPT'],dispatch_base),('service_receipt_events','step_id',['CREATE'],create_base)]:
   id=d['current_offer']['id'] if identity=='offer_id' else d['receipt_step_id']
   events=c.execute('SELECT id,payload FROM '+table+' WHERE '+identity+'=%s AND action=ANY(%s)',(id,actions)).fetchall()
   for event in events:
    assert event['payload'].keys()-keys
    c.execute('UPDATE '+table+' SET payload=%s WHERE id=%s',(Jsonb({k:v for k,v in event['payload'].items() if k in keys}),event['id']))
 before=old.snapshot(f);x=get(f,p);assert x.status_code==200 and not x.json()['can_cancel']
 assert 'EXACT_MANUAL_ACCEPTANCE_AND_CREATE_PROOF_REQUIRED' in x.json()['blockers']
 assert post(f,p).status_code==409 and old.snapshot(f)==before


def test_initial_actual_acceptance_after_declined_offer_remains_supported(receipt_fixture):
 f=receipt_fixture;p=ready(f);d=offer(f,p)[0];assert d.status_code==201
 d=decide(f,d.json(),'DECLINE');assert d.status_code==200
 d=offer(f,p,revision=d.json()['revision'])[0];assert d.status_code==201
 d=decide(f,d.json(),'ACCEPT');assert d.status_code==200
 assert get(f,p).json()['can_cancel'] and post(f,p).status_code==200


@pytest.mark.parametrize('damage',['legacy','unaccepted','accept_actor','accept_fingerprint','create_fingerprint','create_payload','step_revision','step_namespace','closed_history','isolated_provider','managed_cold','external','run_proof','handoff_extra','handoff_boolean'])
def test_unproven_or_effectful_origin_explicitly_refused(receipt_fixture,damage):
 from psycopg.types.json import Jsonb
 f=receipt_fixture
 if damage in ('legacy','unaccepted'):
  p=ready(f)
  if damage=='legacy':assert legacy_create(f,p)[0].status_code==201
 else:p,d=accepted(f)
 if damage.startswith('handoff'):
  f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
  d=reassign(f,d,body_for(f,p,d)).json();d=decide(f,d,'ACCEPT').json()
 with f[1].connect() as c:
  if damage=='accept_actor':c.execute("UPDATE service_dispatch_events SET actor_id='fixture-a' WHERE action='ACCEPT'")
  elif damage=='accept_fingerprint':c.execute("UPDATE service_dispatch_events SET fingerprint=repeat('0',64) WHERE action='ACCEPT'")
  elif damage=='create_fingerprint':c.execute("UPDATE service_receipt_events SET fingerprint=repeat('0',64) WHERE action='CREATE'")
  elif damage=='create_payload':c.execute("UPDATE service_receipt_events SET payload=jsonb_set(payload,'{revision}','true') WHERE action='CREATE'")
  elif damage=='step_revision':c.execute('UPDATE service_receipt_steps SET revision=2')
  elif damage=='step_namespace':
   # Owned test corruption only: otherwise the original CHECK refuses this
   # unsupported row before the API can even observe it. Product CHECK stays.
   c.execute('ALTER TABLE service_receipt_steps DROP CONSTRAINT service_receipt_steps_namespace_check')
   c.execute("UPDATE service_receipt_steps SET namespace='PREVIEW_EXECUTION'")
  elif damage=='closed_history':
   c.execute("INSERT INTO case_local_lifecycles(preparation_id,case_id,revision,cycle,state) VALUES(%s,%s,1,1,'REOPENED')",(p['preparation_id'],p['case_id']))
   c.execute("INSERT INTO case_local_events(id,preparation_id,actor_id,request_key,fingerprint,revision,cycle,action,payload) VALUES(%s,%s,'fixture-a','synthetic-close',repeat('0',64),1,1,'CLOSE_LOCAL_RECORD','{}')",(uuid4(),p['preparation_id']))
  elif damage=='isolated_provider':f[0]._isolated_execution_preview=object()
  elif damage=='managed_cold':
   c.execute('ALTER TABLE run_assignments ADD COLUMN managed_access jsonb');c.execute("UPDATE run_assignments SET managed_access='{}' WHERE run_id=%s",(p['run_id'],))
  elif damage=='external':
   c.execute('ALTER TABLE cases DROP CONSTRAINT cases_external_acceptance_check')
   c.execute("UPDATE cases SET external_acceptance='SUBMITTED' WHERE id=%s",(p['case_id'],))
  elif damage=='run_proof':c.execute("UPDATE operations SET state='PREPARED' WHERE run_id=%s",(p['run_id'],))
  elif damage=='handoff_extra':c.execute("UPDATE service_receipt_events SET payload=jsonb_set(payload,'{predecessor_executor_id}','\"wrong\"') WHERE step_id=%s",(d['receipt_step_id'],))
  elif damage=='handoff_boolean':
   for table in ('service_dispatch_events','service_receipt_events'):
    c.execute('UPDATE '+table+" SET payload=jsonb_set(payload,'{predecessor_receipt_revision}','true') WHERE payload ? 'handoff_kind'")
 before=old.snapshot(f);assert not get(f,p).json()['can_cancel']
 assert post(f,p).status_code==409 and old.snapshot(f)==before
 if damage=='managed_cold':assert not cr.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']))['can_cancel']


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a','unassigned'])
def test_current_owner_scope_for_preview_submit_and_key_recovery(receipt_fixture,user):
 f=receipt_fixture;p,d=accepted(f);data=body(f,p);before=old.snapshot(f)
 assert get(f,p,user).status_code==post(f,p,data,user=user).status_code==recover(f,p,uuid4().hex,user).status_code==403
 assert old.snapshot(f)==before


@pytest.mark.parametrize('cap',['READ','PREPARE','EXECUTE','INACTIVE'])
def test_current_revocation_rechecked_for_commit_and_cold_key_read(receipt_fixture,cap):
 f=receipt_fixture;p,d=accepted(f);data=body(f,p);key=uuid4().hex;assert post(f,p,data,key).status_code==200
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True)
  if cap=='INACTIVE':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
  elif cap=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a'")
  else:c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
 before=old.snapshot(f);assert post(f,p,data,key).status_code==403
 assert recover(f,p,key).status_code==(200 if cap=='EXECUTE' else 403)
 assert old.snapshot(f)==before


@pytest.mark.parametrize('same_key,same_body',[(True,True),(True,False),(False,True)])
def test_key_concurrency_commits_exactly_one_event(receipt_fixture,same_key,same_body):
 f=receipt_fixture;p,d=accepted(f);data=body(f,p);key=uuid4().hex
 def run(i):
  try:return cr.cancel(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key if same_key else str(i),cr.Cancel.model_validate({**data,'reason':data['reason'] if same_body else str(i)}))
  except Conflict:return 'CONFLICT'
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
 if same_key and same_body:assert results[0]==results[1]
 else:assert results.count('CONFLICT')==1
 with f[1].connect() as c:assert c.execute("SELECT count(*) n FROM case_local_events WHERE action='CANCEL_BEFORE_RECEIPT'").fetchone()['n']==1


def test_cancel_event_failure_is_full_transaction_rollback(receipt_fixture):
 f=receipt_fixture;p,d=accepted(f);data=body(f,p);before=old.snapshot(f)
 with f[1].connect() as c:
  c.execute("CREATE FUNCTION fail_receipt_cancel() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN IF NEW.action='CANCEL_BEFORE_RECEIPT' THEN RAISE EXCEPTION 'SYNTHETIC cancel fault'; END IF; RETURN NEW; END$$")
  c.execute('CREATE TRIGGER fail_receipt_cancel BEFORE INSERT ON case_local_events FOR EACH ROW EXECUTE FUNCTION fail_receipt_cancel()')
 with pytest.raises(psycopg.errors.RaiseException,match='SYNTHETIC cancel fault'):
  cr.cancel(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,cr.Cancel.model_validate(data))
 assert old.snapshot(f)==before


def competing(f,p,d,writer):
 if writer=='submit':
  row=generation(f,d,'executor-a');return lambda:act(f,row,'SUBMIT')
 if writer in ('accept','handoff'):
  f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
  b=body_for(f,p,d)
  if writer=='handoff':return lambda:reassign(f,d,b)
  pending=reassign(f,d,b);assert pending.status_code==201;d=pending.json()
  return lambda:decide(f,d,'ACCEPT')
 if writer=='material':return lambda:material(f,p,'ADD_EVIDENCE',slot='need_summary',text='SYNTHETIC next',source_kind='USER_STATEMENT',source_label='SYNTHETIC next')
 if writer=='link':
  g=group(f);return lambda:bind(f,p,g)
 from test_request_intents import save
 from test_service_case_steps import adopt,adopt_body
 p=save(f,p,goals=['LOCAL_MATERIAL_PREPARATION']).json()
 data=adopt_body(f,p);return lambda:adopt(f,p,data)


@pytest.mark.parametrize('field',['case_id','expected_preparation_revision','expected_lifecycle_revision','expected_source_sha256'])
def test_exact_owner_preview_all_versions_required(receipt_fixture,field):
 f=receipt_fixture;p,d=accepted(f);data=body(f,p)
 data[field]=str(uuid4()) if field=='case_id' else '0'*64 if field=='expected_source_sha256' else data[field]+1
 before=old.snapshot(f);assert post(f,p,data).status_code==409 and old.snapshot(f)==before


@pytest.mark.parametrize('damage',['case','local_state','local_revision'])
def test_original_key_requires_current_committed_state(receipt_fixture,damage):
 f=receipt_fixture;p,d=accepted(f);data=body(f,p);key=uuid4().hex;assert post(f,p,data,key).status_code==200
 with f[1].connect() as c:
  if damage=='case':c.execute("UPDATE cases SET state='NEEDS_INPUT' WHERE id=%s",(p['case_id'],))
  elif damage=='local_state':c.execute("UPDATE case_local_lifecycles SET state='REOPENED' WHERE preparation_id=%s",(p['preparation_id'],))
  else:c.execute('UPDATE case_local_lifecycles SET revision=revision+1 WHERE preparation_id=%s',(p['preparation_id'],))
 before=old.snapshot(f);assert post(f,p,data,key).status_code==recover(f,p,key).status_code==409
 assert old.snapshot(f)==before


def test_case_rights_do_not_export_or_release_revoked_resource_data(link_fixture):
 from test_resource_combinations import cancel
 f=link_fixture;p,d=accepted(f);g=group(f);assert bind(f,p,g).status_code==201
 with f[1].connect() as c:c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a'")
 x=get(f,p);assert x.status_code==200 and x.json()['can_cancel']
 assert all(set(link)=={'id','revision','sha256'} for link in x.json()['source']['resource_links'])
 before=old.snapshot(f);assert post(f,p).status_code==200;after=old.snapshot(f)
 assert before['synthetic_resource_holds']==after['synthetic_resource_holds']
 assert cancel(f,g['id']).status_code==403 and old.snapshot(f)==after


def test_handoff_and_material_reuse_bypasses_after_cancel(link_fixture):
 f=link_fixture;p,d=accepted(f);f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
 pending=body_for(f,p,d);source=ready(f);assert post(f,p).status_code==200;before=old.snapshot(f)
 assert reassign(f,d,pending).status_code==409
 reuse=dict(expected_target_revision=p['revision'],source_preparation_id=source['preparation_id'],expected_source_preparation_revision=source['revision'],source_evidence_id=str(uuid4()),expected_source_evidence_version=1,expected_source_evidence_sha256='0'*64,expected_source_snapshot_sha256=source['snapshot_sha256'],purpose='SAME_SERVICE_MATERIAL_OUTLINE',reason='SYNTHETIC late reuse')
 r=f[3].post('/api/preparations/'+p['preparation_id']+'/material-reuse',headers=headers(f[2],key=uuid4().hex),json=reuse)
 assert r.status_code==409 and 'Case cancelled' in r.text and old.snapshot(f)==before


@pytest.mark.parametrize('writer',['submit','accept','handoff','material','plan','link'])
def test_cancel_wins_actual_parent_lock_wait_then_every_late_writer_refused(link_fixture,writer):
 f=link_fixture;p,d=accepted(f);write=competing(f,p,d,writer);data=body(f,p);results=[]
 with f[1].connect() as blocker:
  blocker.execute('SELECT * FROM cases WHERE id=%s FOR UPDATE',(p['case_id'],))
  cancel=threading.Thread(target=lambda:results.append(('cancel',post(f,p,data).status_code)));cancel.start();old.wait_for_pg_lock(f,'SELECT * FROM cases WHERE id=')
  other=threading.Thread(target=lambda:results.append((writer,write().status_code)));other.start();old.wait_for_pg_lock(f,'FROM preparations WHERE id=')
 cancel.join(6);other.join(6);assert not cancel.is_alive() and not other.is_alive()
 assert sorted(results)==sorted([('cancel',200),(writer,409)])
 assert get(f,p).json()['case_state']=='CANCELLED'


@pytest.mark.parametrize('writer',['submit','accept','handoff','material','plan','link'])
def test_other_writer_wins_real_lock_wait_then_cancel_rechecks_complete_source(link_fixture,writer,monkeypatch):
 f=link_fixture;p,d=accepted(f);write=competing(f,p,d,writer);data=body(f,p)
 entered=threading.Event();release=threading.Event();results=[];original=prep.case_write_guard;once=[]
 def pause(c,parent):
  original(c,parent)
  if not once:once.append(True);entered.set();assert release.wait(5)
 monkeypatch.setattr(prep,'case_write_guard',pause)
 t=threading.Thread(target=lambda:results.append((writer,write().status_code)));t.start();assert entered.wait(3)
 cancel=threading.Thread(target=lambda:results.append(('cancel',post(f,p,data).status_code)));cancel.start()
 try:old.wait_for_pg_lock(f,'FROM preparations WHERE id=')
 finally:release.set()
 t.join(6);cancel.join(6);assert not t.is_alive() and not cancel.is_alive()
 assert sorted(results)==sorted([(writer,200 if writer in ('submit','accept','material') else 201),('cancel',409)])
 assert get(f,p).json()['case_state']!='CANCELLED'
 assert post(f,p).status_code==(409 if writer=='submit' else 200)


def wrap_old_guards(monkeypatch):
 monkeypatch.setattr(old,'ready',lambda f:accepted(f)[0]);monkeypatch.setattr(old,'post',post)

@pytest.mark.parametrize('endpoint',old.test_all_case_business_write_families_reject_cancelled_before_other_prerequisites.pytestmark[0].args[1])
def test_existing_write_family_frozen_after_actual_accept(link_fixture,monkeypatch,endpoint):
 wrap_old_guards(monkeypatch);old.test_all_case_business_write_families_reject_cancelled_before_other_prerequisites(link_fixture,endpoint)

@pytest.mark.parametrize('action,user',[(a,'fixture-a' if a in ('ADD_EVIDENCE','CONFIRM','REOPEN') else 'prep-specialist-fixture-a') for a in prep.PreparationCommand.model_fields['action'].annotation.__args__])
def test_all_existing_material_commands_frozen_after_actual_accept(receipt_fixture,monkeypatch,action,user):
 wrap_old_guards(monkeypatch);old.test_all_material_commands_frozen_before_replay(receipt_fixture,action,user)

@pytest.mark.parametrize('action',['SUBMIT','ACKNOWLEDGE','REQUEST_CHANGES','REOPEN'])
def test_receipt_parent_bypass_all_commands_and_legacy_create_frozen(receipt_fixture,action):
 f=receipt_fixture;p,d=accepted(f);row=generation(f,d);assert post(f,p).status_code==200;before=old.snapshot(f)
 payload=dict(action=action,expected_revision=row['step']['revision'])
 if action=='SUBMIT':payload.update(text='SYNTHETIC late receipt',source_kind='SYNTHETIC',source_label='SYNTHETIC late')
 else:payload.update(reason='SYNTHETIC late decision',receipt_sha256='0'*64)
 r=f[3].post('/api/executor-receipts/'+row['step']['id']+'/commands',headers=headers(f[2],'executor-a' if action=='SUBMIT' else 'fixture-a',uuid4().hex),json=payload)
 assert r.status_code==409 and legacy_create(f,p)[0].status_code==409
 assert old.snapshot(f)==before


@pytest.mark.parametrize('kind',['controlled','registered'])
def test_cancelled_history_reads_remain_free_of_plan_invalidation(link_fixture,monkeypatch,kind):
 if kind=='registered':
  wrap_old_guards(monkeypatch);old.test_historical_plan_get_does_not_persist_implicit_invalidation(link_fixture,kind);return
 from test_controlled_plans import create,check
 f=link_fixture;p=ready(f);assert create(f,p).status_code==201;assert check(f,p,'P1').status_code==200
 g=group(f);assert bind(f,p,g).status_code==201;assert check(f,p,'P2').status_code==200
 d=offer(f,p)[0];assert d.status_code==201;assert decide(f,d.json(),'ACCEPT').status_code==200
 assert post(f,p).status_code==200
 with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=source||'{\"revision\":\"changed\"}'::jsonb")
 before=old.snapshot(f)
 for path in ['','/readiness','/material-draft','/fact-clarifications','/controlled-plan','/service-case-plan','/service-case-plan/command-recovery','/planning-preview','/local-case','/case-path','/goal-results']:
  r=f[3].get('/api/preparations/'+p['preparation_id']+path,headers=headers(f[2]));assert r.status_code==200,(path,r.text)
  assert old.snapshot(f)==before,path


@pytest.mark.parametrize('event',['accept','create','offered'])
@pytest.mark.parametrize('value',[[],None,7,'invalid'])
def test_nonobject_lineage_payload_fails_closed_with_explicit_blocker(receipt_fixture,event,value):
 from psycopg.types.json import Jsonb
 f=receipt_fixture;p,d=accepted(f)
 if event=='offered':
  f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
  d=reassign(f,d,body_for(f,p,d)).json();d=decide(f,d,'ACCEPT').json()
 table='service_receipt_events' if event=='create' else 'service_dispatch_events'
 with f[1].connect() as c:
  if event=='create':c.execute('UPDATE '+table+' SET payload=%s WHERE step_id=%s',(Jsonb(value),d['receipt_step_id']))
  else:c.execute('UPDATE '+table+" SET payload=%s WHERE offer_id=%s AND action=%s",(Jsonb(value),d['current_offer']['id'],'ACCEPT' if event=='accept' else 'REOFFER'))
 before=old.snapshot(f);assert 'EXACT_MANUAL_ACCEPTANCE_AND_CREATE_PROOF_REQUIRED' in get(f,p).json()['blockers']
 assert post(f,p).status_code==409 and old.snapshot(f)==before


def test_resource_capacity_and_release_keep_original_authority(link_fixture):
 from test_resource_combinations import cancel
 from parkweave import resource_holds as rh
 f=link_fixture;p,d=accepted(f);g=group(f);assert bind(f,p,g).status_code==201
 before=old.snapshot(f);assert post(f,p).status_code==200;after=old.snapshot(f)
 for table in ('service_dispatch_events','service_receipt_events','service_receipt_steps','case_resource_links','resource_case_claims','synthetic_resource_holds'):
  assert before[table]==after[table]
 with f[1].connect() as c:
  for m in g['members']:
   h=c.execute('SELECT * FROM synthetic_resource_holds WHERE id=%s',(m['id'],)).fetchone();assert h['state']=='CONFIRMED'
   assert rh._peak(c,h['resource_id'],h['starts_at'],h['ends_at'],rh._now(c))>=h['quantity']
 assert cancel(f,g['id']).status_code==200 and get(f,p).json()['case_state']=='CANCELLED'


def test_pending_old_notice_rechecked_after_accepted_cancellation(receipt_fixture):
 from parkweave import dispatch_notices as dn
 from test_dispatch_notices import drain,inbox,act as notice_act
 f=receipt_fixture;p,d=accepted(f);assert dn.consume(f[0]);assert post(f,p).status_code==200;drain(f)
 with f[1].connect() as c:rows=c.execute('SELECT * FROM dispatch_notices').fetchall()
 for n in rows:
  item=inbox(f,n['recipient_id']).json()['items'][0];assert item['case_cancelled'] and not item['actionable']
  assert not notice_act(f,n['recipient_id'],item,'OPEN').json()['notice']['actionable']
