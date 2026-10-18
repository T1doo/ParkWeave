"""Original notice queue/HTTP under the same explicit CaseStep scope."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import json,os,queue,subprocess,threading,time
from pathlib import Path
from uuid import UUID,uuid4
import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from parkweave import dispatch_notices as dn,case_step_assignments as cs
from parkweave.api import create_app
from test_case_step_assignments import scoped,prepared,ok,dependency,REVIEWER
from test_executor_receipts import receipt_fixture
from test_preparation import preparation_fixture,headers
from test_service_dispatches import offer,command as decision
from test_new_enterprise_local_chain import actual_http
from service_release_acceptance_support import authority_snapshot

OUT=Path(os.environ.get('PARKWEAVE_CASE_STEP_NOTICE_EVIDENCE','.runtime/case-step-notices-20261018/development'))
def inbox(f,user='executor-a'):return f[3].get('/api/dispatch-notices',headers=headers(f[2],user))
def read(f,x,user='executor-a'):return f[3].get('/api/dispatch-notices/'+x['event_id'],headers=headers(f[2],user))
def act(f,x,action,user='executor-a'):return f[3].post('/api/dispatch-notices/'+x['event_id']+'/commands',headers=headers(f[2],user),json=dict(action=action,expected_revision=x['revision']))
def drain(f,scope=None):
 for _ in range(30):
  if not dn.consume(f[0],case_step_assignments=scope):return
 raise AssertionError('notice drain exceeded finite fixture bound')
def offer_notice(scoped):
 f,scope,baseline,_=scoped;p=prepared(f,'NOTICE');d=ok(offer(f,p,reason='PRIVATE_NOTICE_REASON')[0],201);drain(f,scope);x=ok(inbox(f))['items'][0];return f,scope,baseline,p,d,x

def test_original_queue_open_read_duplicate_consume_and_cold_boundary(scoped):
 f,scope,baseline,_=scoped;p=prepared(f);d=ok(offer(f,p)[0],201)
 drain(f)
 with f[1].connect() as c:assert {r['state'] for r in c.execute('SELECT state FROM dispatch_notice_outbox')}=={'PENDING'}
 with ThreadPoolExecutor(max_workers=3) as pool:list(pool.map(lambda _:dn.consume(f[0],case_step_assignments=scope),range(6)))
 drain(f,scope);x=ok(inbox(f))['items'][0]
 assert x['assignment_contract']==cs.CONTRACT and not x['run_access_granted'] and x['actionable'] and not x['historical']
 assert not any(s in inbox(f).text for s in ('PRIVATE_REQUEST','PRIVATE_MATERIAL','PRIVATE_NOTICE_REASON'))
 ok(act(f,x,'MARK_READ'),409);opened=ok(act(f,x,'OPEN'))['notice'];assert opened['open_requested_at'] and not opened['read_at']
 marked=ok(act(f,x,'MARK_READ'))['notice'];assert marked['read_at']
 assert ok(act(f,x,'MARK_READ'))['notice']==marked==ok(act(f,x,'OPEN'))['notice']
 d=ok(decision(f,d,'ACCEPT'));drain(f);drain(f,scope)
 assert not ok(read(f,x))['notice']['actionable'] and ok(read(f,x))['notice']['historical']
 assert len(ok(inbox(f,'fixture-a'))['items'])==2 and len(ok(inbox(f,REVIEWER))['items'])==1
 with f[1].connect() as c:
  assert c.execute('SELECT count(*) n FROM dispatch_notices').fetchone()['n']==4
  assert not c.execute("SELECT 1 FROM dispatch_notice_outbox WHERE state='PENDING'").fetchone()
 with TestClient(create_app(f[0])) as api:
  other=(*f[:3],api);assert ok(inbox(other))['items']==[];ok(read(other,x),403)
 assert authority_snapshot(f[1])==baseline

@pytest.mark.parametrize('actor',['fixture-b','fixture-c','executor-b','unassigned',REVIEWER])
def test_actual_nonrecipient_cannot_open_or_mark(scoped,actor):
 f,_,_,_,_,x=offer_notice(scoped)
 for response in (read(f,x,actor),act(f,x,'OPEN',actor),act(f,x,'MARK_READ',actor)):ok(response,403)

@pytest.mark.parametrize('change',['revoke','restore_generation','material','expired','withdraw','decline'])
def test_delivered_notice_rechecks_current_scope_and_preserves_owner_history(scoped,monkeypatch,change):
 f,scope,_,p,d,x=offer_notice(scoped)
 if change in ('withdraw','decline'):ok(decision(f,d,change.upper()));drain(f,scope)
 elif change=='expired':
  now=cs._now;monkeypatch.setattr(cs,'_now',lambda c:now(c)+timedelta(seconds=301))
 else:
  with f[1].connect() as c:
   if change=='material':c.execute('UPDATE preparations SET revision=revision+1 WHERE id=%s',(p['preparation_id'],))
   else:
    c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
    if change=='restore_generation':c.execute("UPDATE capability_grants SET active=true WHERE principal_id='executor-a' AND capability='READ'")
 for response in (read(f,x),act(f,x,'OPEN'),act(f,x,'MARK_READ')):ok(response,403)
 r=inbox(f);assert r.status_code==403 or r.json()['items']==[]
 owner=ok(inbox(f,'fixture-a'))['items'];old=next(i for i in owner if i['event_id']==x['event_id']);assert old['historical'] and not old['actionable']
 ok(act(f,x,'OPEN','fixture-a'));ok(act(f,x,'MARK_READ','fixture-a'))
 with f[1].connect() as c:assert not c.execute("SELECT read_at FROM dispatch_notices WHERE recipient_id='executor-a'").fetchone()['read_at']

def test_revoked_before_delivery_suppression_does_not_resurrect(scoped):
 f,scope,_,_=scoped;p=prepared(f);d=ok(offer(f,p)[0],201)
 with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
 drain(f,scope)
 with f[1].connect() as c:
  assert c.execute("SELECT state FROM dispatch_notice_outbox WHERE recipient_id='executor-a'").fetchone()['state']=='SUPPRESSED'
  c.execute("UPDATE capability_grants SET active=true WHERE principal_id='executor-a' AND capability='READ'")
 drain(f,scope);assert ok(inbox(f))['items']==[]

@pytest.mark.parametrize('action',['OFFER','ACCEPT','DECLINE','WITHDRAW'])
def test_damaged_original_event_cannot_be_a_notice_proof(scoped,action):
 f,scope,_,p,d,x=offer_notice(scoped)
 if action!='OFFER':ok(decision(f,d,action));drain(f,scope)
 owner=next(i for i in ok(inbox(f,'fixture-a'))['items'] if i['action']==action)
 with f[1].connect() as c:
  row=c.execute('SELECT payload FROM service_dispatch_events WHERE id=%s',(owner['event_id'],)).fetchone();payload=row['payload'];payload['dispatch_id']=str(uuid4());c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s',(Jsonb(payload),owner['event_id']))
 for response in (read(f,owner,'fixture-a'),act(f,owner,'OPEN','fixture-a'),act(f,owner,'MARK_READ','fixture-a')):ok(response,403)


def test_unknown_issuer_and_malformed_markers_stay_pending(scoped):
 f,scope,_,_=scoped;p=prepared(f);ok(offer(f,p)[0],201)
 with f[1].connect() as c:
  row=c.execute("SELECT id,payload FROM service_dispatch_events WHERE action='OFFER'").fetchone();payload=row['payload'];payload[cs.MARKER]['binding']['contract_id']=str(uuid4());c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s',(Jsonb(payload),row['id']))
 drain(f);drain(f,scope)
 with f[1].connect() as c:
  assert not c.execute('SELECT 1 FROM dispatch_notices').fetchone()
  assert {r['state'] for r in c.execute('SELECT state FROM dispatch_notice_outbox')}=={'PENDING'}


def test_mark_read_wait_crossing_first_deadline_rolls_back(receipt_fixture):
 f=receipt_fixture;scope=dependency(f,offer_seconds=2)
 with actual_http(create_app(f[0],case_step_assignments=scope)) as (api,_):
  f=(*f[:3],api);p=prepared(f);ok(offer(f,p)[0],201);drain(f,scope);x=ok(inbox(f))['items'][0];ok(act(f,x,'OPEN'))
  with f[1].connect() as lock:
   lock.execute("SELECT * FROM dispatch_notices WHERE recipient_id='executor-a' FOR UPDATE")
   with ThreadPoolExecutor(max_workers=1) as pool:
    future=pool.submit(act,f,x,'MARK_READ');seen=False
    for _ in range(30):
     with f[1].connect() as c:seen=bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM dispatch_notices%' LIMIT 1").fetchone())
     if seen:break
     time.sleep(.02)
    assert seen;time.sleep(2.05);lock.commit();r=future.result(timeout=10)
  ok(r,403)
  with f[1].connect() as c:assert c.execute("SELECT read_at FROM dispatch_notices WHERE recipient_id='executor-a'").fetchone()['read_at'] is None

@pytest.mark.parametrize('flow',['NORMAL','LATE_LIST','LATE_OPEN','LATE_MARK','LATE_403'])
def test_original_page_list_notice_open_and_read_with_late_results(scoped,flow):
 f,scope,baseline,_=scoped;p=prepared(f,'HTML_NOTICE');OUT.mkdir(parents=True,exist_ok=True);name=flow+'-'+uuid4().hex[:8];lines=[];messages=queue.Queue()
 with (OUT/(name+'.stderr')).open('w') as error:
  proc=subprocess.Popen(['node','tests/case_step_notice_real_html.js'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=error,text=True,bufsize=1)
  def consume():
   for line in proc.stdout:messages.put(line)
   messages.put(None)
  threading.Thread(target=consume,daemon=True).start()
  proc.stdin.write(json.dumps(dict(base=str(f[3].base_url).rstrip('/'),preparation_id=p['preparation_id'],flow=flow,tokens=dict(owner=f[2]['fixture-a'],reviewer=f[2][REVIEWER],executor=f[2]['executor-a'],other=f[2]['fixture-b'])))+'\n');proc.stdin.flush()
  try:
   while True:
    line=messages.get(timeout=60)
    if line is None:break
    lines.append(line);item=json.loads(line)
    if item.get('control')=='drain':drain(f,scope)
    elif item.get('control')=='revoke':
     with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
    elif item.get('control')=='assert_final':
     if flow!='LATE_403':assert authority_snapshot(f[1])==baseline
     with f[1].connect() as c:
      assert not c.execute('SELECT 1 FROM run_assignments').fetchone()
      assert not c.execute('SELECT 1 FROM service_receipt_steps').fetchone()
      row=c.execute("SELECT * FROM dispatch_notices WHERE recipient_id='executor-a'").fetchone()
      assert bool(row['read_at'])==(flow in ('NORMAL','LATE_MARK'))
    if item.get('control'):proc.stdin.write('{}\n');proc.stdin.flush()
   code=proc.wait(timeout=5)
  finally:
   if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
   (OUT/(name+'.jsonl')).write_text(''.join(lines))
 assert code==0,(OUT/(name+'.stderr')).read_text()
 assert json.loads(lines[-1])['checks']>=4


def test_corrupt_owned_proof_is_not_terminally_suppressed(scoped):
 f,scope,_,_=scoped;p=prepared(f);ok(offer(f,p)[0],201)
 with f[1].connect() as c:
  c.execute("UPDATE service_dispatch_events SET payload=jsonb_set(payload,'{dispatch_id}',%s) WHERE action='OFFER'",(Jsonb(str(uuid4())),))
 drain(f);drain(f,scope)
 with f[1].connect() as c:assert {r['state'] for r in c.execute('SELECT state FROM dispatch_notice_outbox')}=={'PENDING'}


def test_legacy_and_scoped_consumers_do_not_steal_each_others_queue(scoped,monkeypatch):
 f,scope,_,_=scoped;p=prepared(f);ok(offer(f,p)[0],201);monkeypatch.setattr(dn,'SCAN_LIMIT',1)
 with TestClient(create_app(f[0])) as legacy:
  other=(*f[:3],legacy);old,_,_=offer(other);ok(old,201)
  drain(f,scope)
  with f[1].connect() as c:
   rows=c.execute('SELECT d.preparation_id,o.state FROM dispatch_notice_outbox o JOIN service_dispatch_events e ON e.id=o.event_id JOIN service_dispatches d ON d.id=e.dispatch_id').fetchall()
   assert all(r['state']==('DELIVERED' if str(r['preparation_id'])==p['preparation_id'] else 'PENDING') for r in rows)
  drain(f)
  assert len(ok(inbox(f))['items'])==1 and len(ok(inbox(other))['items'])==1
  with f[1].connect() as c:assert c.execute('SELECT count(*) n FROM dispatch_notices').fetchone()['n']==4


def test_current_revoke_after_open_before_last_mark_read_check_rolls_back(scoped):
 f,scope,_,_,_,x=offer_notice(scoped);ok(act(f,x,'OPEN'))
 with f[1].connect() as lock:
  lock.execute("SELECT * FROM dispatch_notices WHERE recipient_id='executor-a' FOR UPDATE")
  with ThreadPoolExecutor(max_workers=1) as pool:
   future=pool.submit(act,f,x,'MARK_READ');seen=False
   for _ in range(30):
    with f[1].connect() as c:seen=bool(c.execute("SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'SELECT * FROM dispatch_notices%' LIMIT 1").fetchone())
    if seen:break
    time.sleep(.02)
   assert seen
   # Deliberate concurrent negative-fixture mutation, never a production writer.
   lock.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
   lock.commit();r=future.result(timeout=10)
 ok(r,403)
 with f[1].connect() as c:assert c.execute("SELECT read_at FROM dispatch_notices WHERE recipient_id='executor-a'").fetchone()['read_at'] is None


def test_scoped_navigation_cannot_cross_default_or_issuer(scoped,monkeypatch):
 f,scope,_,_,_,_=offer_notice(scoped);monkeypatch.setattr(dn,'LIST_RETURN_LIMIT',1);nav=dn.Navigation()
 x=dn.list_items(f[0],f[2]['fixture-a'],navigation=nav,case_step_assignments=scope);assert x['next_cursor']
 with pytest.raises(cs.Denied):dn.list_items(f[0],f[2]['fixture-a'],cursor=x['next_cursor'],navigation=nav)
 original=scope.contract_id;scope.contract_id=str(uuid4())
 try:
  with pytest.raises(cs.Denied):dn.list_items(f[0],f[2]['fixture-a'],cursor=x['next_cursor'],navigation=nav,case_step_assignments=scope)
 finally:scope.contract_id=original
