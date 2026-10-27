"""Actual HTTP/ASGI/owned PG CaseStep business flow, never ordinary authority."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib,json,os
from pathlib import Path
from uuid import UUID,uuid4
import pytest
from fastapi.testclient import TestClient
from parkweave import case_step_assignments as cs, service_dispatches as sd, executor_receipts as er
from parkweave.api import create_app,configured_app
from parkweave.store import Store,Denied
from test_executor_receipts import receipt_fixture,act
from test_preparation import preparation_fixture,create,add,command as prep_command,headers
from test_service_dispatches import offer,command as decision
from test_new_enterprise_local_chain import actual_http
from service_release_acceptance_support import authority_snapshot

REVIEWER='prep-specialist-fixture-a'
OUT=Path(os.environ.get('PARKWEAVE_CASE_STEP_EVIDENCE','.runtime/case-step-assignment-20261018/development'))
def record(name,value):
 OUT.mkdir(parents=True,exist_ok=True);(OUT/(name+'-'+uuid4().hex[:8]+'.json')).write_text(json.dumps(value,indent=2,default=str)+'\n')
def ok(r,status=200):assert r.status_code==status,r.text;return r.json()
def dependency(f,**kw):
 return cs.IsolatedCaseStepAssignments(f[0],f[1],f[1]._case_fact_fixture_receipt,owner_id='fixture-a',reviewer_id=REVIEWER,executor_ids=('executor-a',),enabled_for_isolated_tests=True,**kw)
@pytest.fixture
def scoped(receipt_fixture):
 f=receipt_fixture;provider=dependency(f);before=authority_snapshot(f[1])
 with actual_http(create_app(f[0],case_step_assignments=provider)) as (api,traffic):
  yield (*f[:3],api),provider,before,traffic

def prepared(f,label='A'):
 p,_,_=create(f,goal='PRIVATE_REQUEST_'+label)
 p=ok(add(f,p,text='PRIVATE_MATERIAL_'+label));p=ok(add(f,p,'material_outline','PRIVATE_OUTLINE_'+label))
 p=ok(prep_command(f,p,'REVIEW',REVIEWER,reason='SYNTHETIC independent review '+label))
 return ok(prep_command(f,p,'CONFIRM',reason='SYNTHETIC owner confirms '+label))
def submit(f,p):
 d=ok(offer(f,p)[0],201);before=d;key=uuid4().hex;d=ok(decision(f,d,'ACCEPT',key=key))
 r=ok(f[3].get('/api/executor-receipts/'+d['receipt_step_id'],headers=headers(f[2],'executor-a')))
 return d,r,before,key

def test_new_case_step_actual_receipt_ack_and_default_app_still_denies(scoped):
 f,provider,baseline,traffic=scoped;p=prepared(f);d,r,before,key=submit(f,p)
 assert d['current_offer']['state']=='ACCEPTED' and d['assignment_contract']==cs.CONTRACT
 assert not d['run_access_granted'] and not r['run_access_granted']
 assert ok(f[3].get('/api/service-dispatches',headers=headers(f[2],'executor-a')))['items'][0]['id']==d['dispatch_id']
 assert ok(f[3].get('/api/executor-receipts',headers=headers(f[2],'executor-a')))['items'][0]['id']==r['step']['id']
 # Minimal actual projections omit the full private request/material, not just a UI label.
 own=ok(f[3].get('/api/service-dispatches/'+d['dispatch_id'],headers=headers(f[2],'executor-a')))
 assert all(v not in json.dumps([own,r]) for v in ['PRIVATE_REQUEST_A','PRIVATE_MATERIAL_A','PRIVATE_OUTLINE_A'])
 assert 'owner_id' not in r['step'] and r['step']['goal']==cs.TITLE
 r=ok(act(f,r,'SUBMIT',text='SYNTHETIC actual task output'),200)
 assert r['current_receipt']['source_sha256']==hashlib.sha256(b'SYNTHETIC actual task output').hexdigest()
 r=ok(act(f,r,'ACKNOWLEDGE'));assert r['step']['state']=='LOCAL_ACKNOWLEDGED' and not r['case_goal_completed']
 assert authority_snapshot(f[1])==baseline
 with f[0].connect() as c:
  assert c.execute('SELECT current_user name').fetchone()['name']=='parkweave_app'
  assert not c.execute("SELECT has_table_privilege(current_user,'run_assignments','INSERT') allowed").fetchone()['allowed']
 assert ok(f[3].get('/api/runs/'+p['run_id'],headers=headers(f[2],'executor-a')),403)
 with TestClient(create_app(f[0])) as default:
  for path in ['/api/preparations/'+p['preparation_id']+'/dispatch','/api/executor-receipts/'+r['step']['id']]:ok(default.get(path,headers=headers(f[2],'executor-a')),403)
  ok(default.get('/api/preparations/'+p['preparation_id']+'/dispatch',headers=headers(f[2],REVIEWER)),403)
 expected=ok(f[3].get('/api/executor-receipts/'+r['step']['id'],headers=headers(f[2],'executor-a')))
 with TestClient(create_app(f[0],case_step_assignments=provider)) as cold:
  assert ok(cold.get('/api/executor-receipts/'+r['step']['id'],headers=headers(f[2],'executor-a')))==expected
 assert authority_snapshot(f[1])==baseline
 record('actual-new-case',dict(preparation=p,dispatch=d,receipt=r,original_accepted=before,acceptance_key=key,traffic=traffic,authority_unchanged=True,ordinary_Run_denied=True,new_business_writes_through_HTTP_only=True))

@pytest.mark.parametrize('actor',['fixture-a','fixture-b','fixture-c','executor-a','unassigned','prep-specialist-fixture-b'])
def test_only_current_responsible_specialist_can_offer(scoped,actor):
 f,_,baseline,_=scoped;p=prepared(f)
 assert offer(f,p,user=actor)[0].status_code==403
 with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM service_dispatches').fetchone()['n']==0
 assert authority_snapshot(f[1])==baseline

def test_wrong_target_case_and_privacy_scope(scoped):
 f,_,_,_=scoped;p=prepared(f)
 assert offer(f,p,executor='unassigned')[0].status_code==403
 d,r,*_=submit(f,p)
 for actor in ('unassigned','executor-b','executor-c','prep-specialist-fixture-b'):
  ok(f[3].get('/api/service-dispatches/'+d['dispatch_id'],headers=headers(f[2],actor)),403)
  ok(f[3].get('/api/executor-receipts/'+r['step']['id'],headers=headers(f[2],actor)),403)
 p2=prepared(f,'B');assert p2['case_id']!=p['case_id']
 assert ok(f[3].get('/api/preparations/'+p2['preparation_id']+'/dispatch',headers=headers(f[2],'executor-a')),403)

@pytest.mark.parametrize('change',['executor_READ','owner_EXECUTE','reviewer_REVIEW','material','catalog','expired'])
def test_current_change_denies_old_step_without_resurrection(scoped,monkeypatch,change):
 f,_,_,_=scoped;p=prepared(f);d,r,*_=submit(f,p)
 if change=='expired':
  now=cs._now;monkeypatch.setattr(cs,'_now',lambda c:now(c)+timedelta(seconds=301))
 else:
  with f[1].connect() as c:
   if change=='executor_READ':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
   elif change=='owner_EXECUTE':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='fixture-a' AND capability='EXECUTE'")
   elif change=='reviewer_REVIEW':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(REVIEWER,))
   elif change=='material':c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],))
   else:c.execute("UPDATE preparation_catalog SET name=name||' updated' WHERE park_id='park-a'")
 assert act(f,r,'SUBMIT').status_code==403
 if change in ('executor_READ','owner_EXECUTE','reviewer_REVIEW'):
  with f[1].connect() as c:
   if change=='reviewer_REVIEW':c.execute("UPDATE preparation_grants SET active=true WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(REVIEWER,))
   else:c.execute("UPDATE capability_grants SET active=true WHERE principal_id=%s AND capability=%s",('executor-a' if change=='executor_READ' else 'fixture-a','READ' if change=='executor_READ' else 'EXECUTE'))
  assert act(f,r,'SUBMIT').status_code==403
 with f[1].connect() as c:assert not c.execute('SELECT 1 FROM service_step_receipts').fetchone()

@pytest.mark.parametrize('change',['executor_revoke','material','expired'])
def test_withdraw_is_not_locked_by_the_access_it_terminates(scoped,monkeypatch,change):
 f,_,_,_=scoped;p=prepared(f);d,r,*_=submit(f,p)
 if change=='expired':
  now=cs._now;monkeypatch.setattr(cs,'_now',lambda c:now(c)+timedelta(seconds=301))
 else:
  with f[1].connect() as c:
   if change=='executor_revoke':c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
   else:c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],))
 x=ok(decision(f,d,'WITHDRAW'));assert x['current_offer']['state']=='WITHDRAWN'
 owner=ok(f[3].get('/api/executor-receipts/'+r['step']['id'],headers=headers(f[2])))
 assert owner['is_current_step'] is False
 assert ok(f[3].get('/api/executor-receipts',headers=headers(f[2])))['items'][0]['id']==r['step']['id']
 assert act(f,r,'SUBMIT').status_code==403
 assert offer(f,p,revision=x['revision'])[0].status_code in (403,409)
 with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n']==1

@pytest.mark.parametrize('active',[True,False])
def test_no_legacy_assignment_fallback_even_after_marker_expiry(scoped,monkeypatch,active):
 f,_,_,_=scoped;p=prepared(f);d=ok(offer(f,p)[0],201)
 # Only a deliberate negative-fixture mutation; never used in the positive path.
 f[1].assign_status('executor-a',UUID(p['run_id']),active=active)
 now=cs._now;monkeypatch.setattr(cs,'_now',lambda c:now(c)+timedelta(seconds=301))
 assert decision(f,d,'ACCEPT').status_code==403
 with TestClient(create_app(f[0])) as legacy:
  other=(*f[:3],legacy);assert decision(other,d,'ACCEPT').status_code==403
  ok(legacy.get('/api/service-dispatches/'+d['dispatch_id'],headers=headers(f[2],'executor-a')),403)
 with f[1].connect() as c:assert not c.execute('SELECT 1 FROM service_receipt_steps').fetchone()

def test_one_offer_deadline_replay_and_concurrent_accept_have_one_effect(scoped):
 f,_,baseline,_=scoped;p=prepared(f);key=uuid4().hex;d=ok(offer(f,p,key=key)[0],201)
 replay=ok(offer(f,p,key=key)[0],201);assert replay['assignment_valid_until']==d['assignment_valid_until']
 k=uuid4().hex
 with ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(lambda _:decision(f,d,'ACCEPT',key=k),range(2)))
 assert [r.status_code for r in rows]==[200,200]
 assert rows[0].json()['receipt_step_id']==rows[1].json()['receipt_step_id']
 assert authority_snapshot(f[1])==baseline
 with f[1].connect() as c:
  assert c.execute('SELECT count(*) n FROM service_receipt_steps').fetchone()['n']==1
  assert c.execute("SELECT count(*) n FROM service_dispatch_events WHERE action='ACCEPT'").fetchone()['n']==1

def test_explicit_dependency_only_fresh_start_and_no_provider_mix(scoped,monkeypatch):
 f,provider,_,_=scoped
 with pytest.raises(Denied):cs.IsolatedCaseStepAssignments(f[0],f[1],None,owner_id='fixture-a',reviewer_id=REVIEWER,executor_ids=('executor-a',),enabled_for_isolated_tests=True)
 with pytest.raises(Denied):create_app(f[0],case_step_assignments=object())
 with pytest.raises(Denied):create_app(f[0],case_step_assignments=provider,formal_source_reader=object())
 p=prepared(f)
 with pytest.raises(Denied):dependency(f)
 monkeypatch.setenv('PARKWEAVE_DSN',f[0].dsn)
 for k in ('PARKWEAVE_RUNTIME_READ_CONFIG','PARKWEAVE_RUNTIME_WRITE_CONFIG','PARKWEAVE_RESOURCE_APPROVAL_READ_CONFIG','PARKWEAVE_SERVICE_PROFILE','PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG','PARKWEAVE_FORMAL_PREPARATION_READ_CONFIG'):monkeypatch.delenv(k,raising=False)
 with TestClient(configured_app()) as ordinary:
  assert offer((*f[:3],ordinary),p)[0].status_code==403

def test_original_accept_and_submit_recovery_bind_exact_events(scoped):
 f,_,baseline,_=scoped;p=prepared(f);d,r,before,key=submit(f,p)
 query=dict(preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=p['run_id'],offer_id=before['current_offer']['id'],expected_revision=before['revision'],preparation_revision=p['revision'])
 x=ok(f[3].get('/api/service-dispatches/'+d['dispatch_id']+'/accept-recovery',params=query,headers=headers(f[2],'executor-a',key)));assert x['status']=='COMMITTED'
 original=r;key=uuid4().hex;r=ok(act(f,r,'SUBMIT',key=key));query.pop('offer_id');query.update(expected_revision=original['step']['revision'])
 path='/api/executor-receipts/'+r['step']['id']+'/submit-recovery'
 x=ok(f[3].get(path,params=query,headers=headers(f[2],'executor-a',key)));assert x['status']=='COMMITTED' and x['event']['receipt_sha256']==r['current_receipt']['source_sha256']
 query['case_id']=str(uuid4());assert f[3].get(path,params=query,headers=headers(f[2],'executor-a',key)).status_code==403
 assert authority_snapshot(f[1])==baseline


def test_decline_is_terminal_committed_and_cannot_renew(scoped):
 f,_,_,_=scoped;p=prepared(f);d=ok(offer(f,p)[0],201)
 x=ok(decision(f,d,'DECLINE'));assert x['current_offer']['state']=='DECLINED'
 assert offer(f,p,revision=x['revision'])[0].status_code==409
 ok(f[3].get('/api/service-dispatches/'+d['dispatch_id'],headers=headers(f[2],'executor-a')),403)
 with f[1].connect() as c:assert c.execute("SELECT count(*) n FROM service_dispatch_events WHERE action='DECLINE'").fetchone()['n']==1


@pytest.mark.parametrize('flow',['ACK','DECLINE','WITHDRAW_REVOKED'])
def test_original_html_forms_complete_case_step_without_run_grant(scoped,flow):
 import queue,subprocess,threading
 f,_,baseline,_=scoped;p=prepared(f,'HTML');OUT.mkdir(parents=True,exist_ok=True);name='case-step-html-'+uuid4().hex[:8]
 errors=OUT/(name+'.stderr');lines=[];messages=queue.Queue()
 with errors.open('w') as err:
  proc=subprocess.Popen(['node','tests/case_step_assignment_real_html.js'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
  def consume():
   for line in proc.stdout:messages.put(line)
   messages.put(None)
  threading.Thread(target=consume,daemon=True).start()
  proc.stdin.write(json.dumps(dict(base=str(f[3].base_url).rstrip('/'),preparation_id=p['preparation_id'],flow=flow,tokens=dict(owner=f[2]['fixture-a'],reviewer=f[2][REVIEWER],executor=f[2]['executor-a'])))+'\n');proc.stdin.flush()
  try:
   while True:
    line=messages.get(timeout=60)
    if line is None:break
    lines.append(line);item=json.loads(line)
    if item.get('control')=='revoke_executor':
     with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
     proc.stdin.write('{}\n');proc.stdin.flush()
    elif item.get('control')=='assert_final':
     if flow!='WITHDRAW_REVOKED':assert authority_snapshot(f[1])==baseline
     with f[1].connect() as c:
      assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
      if flow=='ACK':assert c.execute('SELECT state FROM service_receipt_steps').fetchone()['state']=='LOCAL_ACKNOWLEDGED'
      else:assert c.execute('SELECT state FROM service_dispatch_offers').fetchone()['state']==('DECLINED' if flow=='DECLINE' else 'WITHDRAWN')
     proc.stdin.write('{}\n');proc.stdin.flush()
   code=proc.wait(timeout=5)
  finally:
   if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
   (OUT/(name+'.jsonl')).write_text(''.join(lines))
 assert code==0,errors.read_text()
 result=json.loads(lines[-1]);assert result['checks']>=4 and sum(c['method']=='POST' for c in result['calls'])==({'ACK':4,'DECLINE':2,'WITHDRAW_REVOKED':3}[flow])


def test_event_failure_rolls_back_receipt_handoff(scoped,monkeypatch):
 f,_,baseline,_=scoped;p=prepared(f);d=ok(offer(f,p)[0],201);original=er._event
 def fail(*args,**kw):
  original(*args,**kw);raise RuntimeError('SYNTHETIC event failure after insert')
 monkeypatch.setattr(er,'_event',fail)
 assert decision(f,d,'ACCEPT').status_code==500
 with f[1].connect() as c:
  assert not c.execute('SELECT 1 FROM service_receipt_steps').fetchone()
  assert not c.execute('SELECT 1 FROM service_receipt_events').fetchone()
  assert c.execute('SELECT state FROM service_dispatch_offers').fetchone()['state']=='OFFERED'
 assert authority_snapshot(f[1])==baseline


def test_actual_parent_lock_wait_crosses_original_offer_deadline(receipt_fixture):
 import time
 f=receipt_fixture;provider=dependency(f,offer_seconds=2)
 with actual_http(create_app(f[0],case_step_assignments=provider)) as (api,_):
  f=(*f[:3],api);p=prepared(f);d=ok(offer(f,p)[0],201)
  with f[1].connect() as lock:
   lock.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
   with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(decision,f,d,'ACCEPT');observed=False
    for _ in range(30):
     with f[1].connect() as observe:
      observed=bool(observe.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM preparations%' LIMIT 1").fetchone())
     if observed:break
     time.sleep(.02)
    assert observed,'owned request did not enter the expected parent lock wait'
    time.sleep(2.05);lock.commit();r=future.result(timeout=10)
  assert r.status_code==403
  with f[1].connect() as c:
   assert not c.execute('SELECT 1 FROM service_receipt_steps').fetchone()
   assert c.execute('SELECT state FROM service_dispatch_offers').fetchone()['state']=='OFFERED'
  record('actual-lock-expiry',dict(owned_lock_wait_observed=observed,status=r.status_code,deadline_unchanged=d['assignment_valid_until'],accepted_steps=0))


def test_malformed_marker_is_quarantined_for_both_services(scoped):
 from psycopg.types.json import Jsonb
 f,_,_,_=scoped;p=prepared(f);d=ok(offer(f,p)[0],201)
 with f[1].connect() as c:
  c.execute("UPDATE service_dispatch_events SET payload=jsonb_set(payload,ARRAY[%s],%s) WHERE action='OFFER'",(cs.MARKER,Jsonb({'binding':[], 'valid_until':'bad'})))
 assert decision(f,d,'ACCEPT').status_code==403
 with TestClient(create_app(f[0])) as ordinary:
  assert decision((*f[:3],ordinary),d,'ACCEPT').status_code==403


def test_final_post_write_deadline_check_rolls_back(scoped,monkeypatch):
 f,_,_,_=scoped;p=prepared(f);d=ok(offer(f,p)[0],201);event=sd._event;now=cs._now
 def cross(c,p,root,offer,key,fp,action,*a,**kw):
  x=event(c,p,root,offer,key,fp,action,*a,**kw)
  if action=='ACCEPT':monkeypatch.setattr(cs,'_now',lambda c:now(c)+timedelta(seconds=301))
  return x
 monkeypatch.setattr(sd,'_event',cross)
 assert decision(f,d,'ACCEPT').status_code==403
 with f[1].connect() as c:
  assert not c.execute('SELECT 1 FROM service_receipt_steps').fetchone()
  assert c.execute('SELECT state FROM service_dispatch_offers').fetchone()['state']=='OFFERED'


@pytest.mark.parametrize('broken',['offer_coordinate','marker_boolean'])
def test_damaged_original_offer_proof_denies_live_and_owner_history(scoped,broken):
 from psycopg.types.json import Jsonb
 f,_,_,_=scoped;p=prepared(f);d=ok(offer(f,p)[0],201)
 with f[1].connect() as c:
  row=c.execute("SELECT id,payload FROM service_dispatch_events WHERE action='OFFER'").fetchone();payload=row['payload']
  if broken=='offer_coordinate':payload['dispatch_id']=str(uuid4())
  else:payload[cs.MARKER]['binding']['service_version']=True
  c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s',(Jsonb(payload),row['id']))
 assert decision(f,d,'ACCEPT').status_code==403
 for actor in ('executor-a','fixture-a',REVIEWER):
  ok(f[3].get('/api/service-dispatches/'+d['dispatch_id'],headers=headers(f[2],actor)),403)


def test_missing_recovery_key_still_requires_original_coordinates(scoped):
 f,_,_,_=scoped;p=prepared(f);d,r,before,_=submit(f,p)
 query=dict(preparation_id=p['preparation_id'],case_id=p['case_id'],run_id=p['run_id'],offer_id=before['current_offer']['id'],expected_revision=1,preparation_revision=p['revision'])
 path='/api/service-dispatches/'+d['dispatch_id']+'/accept-recovery';h=headers(f[2],'executor-a',uuid4().hex)
 assert ok(f[3].get(path,params=query,headers=h))['status']=='NOT_OBSERVED'
 query['expected_revision']=2;ok(f[3].get(path,params=query,headers=h),409)
 query.pop('offer_id');query['expected_revision']=r['step']['revision']+1
 ok(f[3].get('/api/executor-receipts/'+r['step']['id']+'/submit-recovery',params=query,headers=h),409)
