"""Original lifecycle receipts and current validity via read-only real PG/API."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from uuid import UUID,uuid4
import json,hashlib,threading,time
import pytest,psycopg
from parkweave import case_lifecycle as lc
from parkweave.store import Store,Conflict
from test_case_lifecycle import built,closed,read,act,counts
from test_case_resources import link_fixture
from test_preparation import preparation_fixture,headers,command as prep_act
from test_executor_receipts import receipt_fixture,ready
from test_resource_combinations import cancel


def recover(f,p,key,user='fixture-a'):
 return f[3].get('/api/preparations/'+p['preparation_id']+'/local-case/recovery/'+key,headers=headers(f[2],user))


def snapshot(f):
 with f[1].connect() as c:
  tables=('preparations','cases','case_local_lifecycles','case_local_events','case_resource_links','resource_case_claims','synthetic_resource_holds','synthetic_resource_combinations','service_dispatches','service_dispatch_events','service_receipt_steps','service_receipt_events','controlled_plans','controlled_plan_events')
  data={t:sorted(c.execute('SELECT row_to_json(x) r FROM '+t+' x').fetchall(),key=lambda x:json.dumps(x,sort_keys=True,default=str)) for t in tables}
 return hashlib.sha256(json.dumps(data,sort_keys=True,default=str).encode()).hexdigest()


@pytest.mark.parametrize('action',['REVALIDATE','CLOSE_LOCAL_RECORD','REOPEN'])
def test_three_original_events_cold_read_only_receipt_and_current_view(link_fixture,action):
 f=link_fixture
 if action=='REOPEN':p,g,d,s,_=closed(f)
 else:
  p,g,d,s=built(f)
  if action=='CLOSE_LOCAL_RECORD':assert act(f,p,read(f,p).json(),'REVALIDATE').status_code==200
 row=read(f,p).json();key=uuid4().hex;r=act(f,p,row,action,key=key);assert r.status_code==200,r.text
 before=snapshot(f);x=recover(f,p,key);assert x.status_code==200,x.text;x=x.json()
 assert x['status']=='COMMITTED' and x['historical_only'] and not x['automatically_replayed']
 assert x['receipt']['event']==r.json()['event'] and x['receipt']['action']==action
 assert x['receipt']['original_expected_revision']==row['revision'] and x['receipt']['original_expected_cycle']==row['cycle']
 assert x['current']['revision']==r.json()['revision'] and not x['current']['case_goal_completed']
 assert x['original_is_current_version'] and x['current']['case_state']!='FULFILLED'
 again=lc.recover(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key)
 assert str(again['receipt']['id'])==x['receipt']['id'] and snapshot(f)==before
 assert recover(f,p,key).json()==x and snapshot(f)==before


@pytest.mark.parametrize('changed',['reopen','materials','cancel','rule','reviewer'])
def test_historical_receipt_never_becomes_current_validity_or_reexecution(link_fixture,changed):
 f=link_fixture;p,g,d,s,_=closed(f);key=uuid4().hex
 if changed=='reopen':
  r=act(f,p,read(f,p).json(),'REOPEN',key=key);original=r.json()['event'];assert r.status_code==200
  assert act(f,p,read(f,p).json(),'REVALIDATE').status_code==200
 else:
  with f[1].connect() as c:key=c.execute("SELECT request_key FROM case_local_events WHERE action='CLOSE_LOCAL_RECORD'").fetchone()['request_key']
  original=recover(f,p,key).json()['receipt']['event']
  if changed=='materials':assert prep_act(f,p,'REOPEN',reason='SYNTHETIC changed materials').status_code==200
  elif changed=='cancel':assert cancel(f,g['id']).status_code==200
  elif changed=='rule':
   with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET revision=revision+1')
  else:
   with f[1].connect() as c:c.execute("UPDATE preparation_grants SET active=false WHERE capability='REVIEW_ASSIGNED'")
 before=snapshot(f);r=recover(f,p,key);assert r.status_code==200,r.text;x=r.json()
 assert x['status']=='COMMITTED' and x['receipt']['event']==original
 if changed=='reopen':assert not x['original_is_current_version'] and x['current']['cycle']==2
 else:assert x['current']['verification_current'] is False
 assert snapshot(f)==before


@pytest.mark.parametrize('cap',['EXECUTE','HOLD','READ','PREPARE','RESOURCE_READ','ACTIVE'])
def test_current_read_authority_precedes_original_receipt_and_write_rights_are_separate(link_fixture,cap):
 f=link_fixture;p,g,d,s,row=closed(f)
 with f[1].connect() as c:
  key=c.execute("SELECT request_key FROM case_local_events WHERE action='CLOSE_LOCAL_RECORD'").fetchone()['request_key']
  if cap in ('EXECUTE','READ'):c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
  elif cap=='ACTIVE':c.execute("UPDATE principals SET active=false WHERE id='fixture-a'")
  elif cap=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
  else:c.execute('UPDATE synthetic_resource_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a','READ' if cap=='RESOURCE_READ' else cap))
 before=snapshot(f);r=recover(f,p,key);assert r.status_code==(200 if cap in ('EXECUTE','HOLD') else 403),r.text
 if cap in ('EXECUTE','HOLD'):
  assert r.json()['status']=='COMMITTED'
  assert not r.json()['current']['can_close_local_record']
 assert snapshot(f)==before


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a','unassigned'])
def test_cross_enterprise_and_role_never_receive_private_original_event(link_fixture,user):
 f=link_fixture;p,g,d,s,row=closed(f)
 with f[1].connect() as c:key=c.execute("SELECT request_key FROM case_local_events WHERE action='CLOSE_LOCAL_RECORD'").fetchone()['request_key']
 before=snapshot(f);r=recover(f,p,key,user);assert r.status_code==403,r.text
 assert 'reason' not in r.text and 'receipt' not in r.text and snapshot(f)==before


@pytest.mark.parametrize('bad',['payload','snapshot','scope','cycle','ledger-revision','fingerprint','reason'])
def test_corrupt_original_proof_is_not_a_committed_recovery_result(link_fixture,bad):
 f=link_fixture;p,g,d,s,row=closed(f)
 with f[1].connect() as c:
  key=c.execute("SELECT request_key FROM case_local_events WHERE action='CLOSE_LOCAL_RECORD'").fetchone()['request_key']
  if bad=='ledger-revision':c.execute('UPDATE case_local_lifecycles SET revision=1')
  elif bad=='fingerprint':c.execute("UPDATE case_local_events SET fingerprint='wrong' WHERE request_key=%s",(key,))
  elif bad=='reason':c.execute("UPDATE case_local_events SET payload=jsonb_set(payload,'{reason}','\"SYNTHETIC changed original body\"') WHERE request_key=%s",(key,))
  elif bad=='snapshot':c.execute("UPDATE case_local_events SET snapshot=jsonb_set(snapshot,'{preparation_revision}','99') WHERE request_key=%s",(key,))
  else:c.execute("UPDATE case_local_events SET payload=jsonb_set(payload,ARRAY[%s],%s::jsonb) WHERE request_key=%s",({'payload':'action','scope':'scope','cycle':'cycle'}[bad],json.dumps('REOPEN' if bad=='payload' else 'wrong' if bad=='scope' else 99),key))
 before=snapshot(f);r=recover(f,p,key);assert r.status_code==409,r.text;assert snapshot(f)==before


def test_unknown_key_and_other_own_case_key_do_not_invent_events(link_fixture):
 f=link_fixture;p,g,d,s,row=closed(f);before=snapshot(f)
 assert recover(f,p,uuid4().hex).json()['status']=='NOT_OBSERVED' and snapshot(f)==before
 with f[1].connect() as c:key=c.execute("SELECT request_key FROM case_local_events WHERE action='CLOSE_LOCAL_RECORD'").fetchone()['request_key']
 p2=ready(f);before=snapshot(f);assert recover(f,p2,key).status_code==409 and snapshot(f)==before
 for t in ('case_local_events',):
  with pytest.raises(psycopg.errors.InsufficientPrivilege):
   with f[0].connect() as c:c.execute('DELETE FROM '+t)


def test_read_waits_for_original_key_then_observes_same_event_without_write(link_fixture):
 f=link_fixture;p,g,d,s=built(f);key=uuid4().hex;row=read(f,p).json();assert act(f,p,row,'REVALIDATE',key=key).status_code==200
 started=threading.Event();result=[]
 def run():started.set();result.append(lc.recover(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key))
 before=snapshot(f)
 with f[1].connect() as c:
  c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',('case-local-key:fixture-a:'+key,));worker=threading.Thread(target=run);worker.start();assert started.wait(2);time.sleep(.15);assert not result
 worker.join(5);assert not worker.is_alive() and result[0]['status']=='COMMITTED' and snapshot(f)==before


def test_parallel_read_and_repeated_post_have_one_original_event(link_fixture):
 f=link_fixture;p,g,d,s=built(f);key=uuid4().hex;row=read(f,p).json();r=act(f,p,row,'REVALIDATE',key=key);assert r.status_code==200
 def run(_):return lc.recover(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key)
 before=snapshot(f)
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(run,range(3)))
 assert all(str(x['receipt']['id'])==str(results[0]['receipt']['id']) for x in results)
 assert act(f,p,row,'REVALIDATE',key=key).status_code==200 and counts(f)==[1,1] and snapshot(f)==before
