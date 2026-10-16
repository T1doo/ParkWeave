"""Original PG parent-lock waits with proper role GETs; no gate or SQL-result patch."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from time import monotonic,sleep
from uuid import uuid4
import pytest
from p3_closure_fixture_support import (closure_case,capability_resource_catalog,capability_catalog,
 receipt_fixture,preparation_fixture,dispatch_read,REVIEWER)
from p3_closure_oracle_support import verify_imports,record,snapshot,qualify_old,check_qualification,headers
from parkweave.store import Conflict

@pytest.fixture(autouse=True)
def actual_import_identity():verify_imports()


def wait_for_parent_queue(c,excluded,timeout=0.9):
 deadline=monotonic()+timeout
 while monotonic()<deadline:
  c.execute('SELECT pg_stat_clear_snapshot()')
  rows=c.execute("""SELECT pid,query,pg_blocking_pids(pid) blockers FROM pg_stat_activity
   WHERE datname=current_database() AND pid<>pg_backend_pid() AND cardinality(pg_blocking_pids(pid))>0
    AND query ILIKE '%%FROM preparations%%' AND query ILIKE '%%FOR UPDATE%%' ORDER BY pid""").fetchall()
  values=[dict(row) for row in rows if row['pid'] not in excluded]
  if values:return values
  sleep(0.01)
 raise AssertionError('original request was not observed waiting on preparation parent within original lock budget')


@pytest.mark.parametrize('closure_case',[{'stop_after':'offered'}],indirect=True)
@pytest.mark.parametrize('first',['ACCEPT','WITHDRAW'])
def test_p3_closure_original_parent_wait_accept_withdraw_both_orders(closure_case,first):
 t=closure_case;f,p=t['f'],t['p'];dispatch=t['dispatch']
 accepted_view=dispatch_read(f,dispatch,'executor-a');withdraw_view=dispatch_read(f,dispatch,REVIEWER)
 assert accepted_view['business_frontier']==withdraw_view['business_frontier']
 before=snapshot(t);requests={}
 for action,actor,view in (('ACCEPT','executor-a',accepted_view),('WITHDRAW',REVIEWER,withdraw_view)):
  requests[action]=dict(actor=actor,key=uuid4().hex,body=dict(action=action,expected_revision=view['revision'],
   reason='SYNTHETIC independent explicit original '+action,expected_business_frontier=deepcopy(view['business_frontier'])))
 def send(action):
  request=requests[action]
  return f[3].post('/api/service-dispatches/'+dispatch['dispatch_id']+'/commands',
   headers=headers(f[2],request['actor'],request['key']),json=request['body'])
 other='WITHDRAW' if first=='ACCEPT' else 'ACCEPT';waits={}
 # The observed owner lock is the same original parent row; no test DDL, trigger,
 # capability, role, command return, or query result is substituted.
 with ThreadPoolExecutor(max_workers=2) as pool:
  with f[1].connect() as gate:
   gate.execute('SELECT id FROM preparations WHERE id=%s FOR UPDATE',(p['preparation_id'],))
   gate_pid=gate.info.backend_pid
   winner=pool.submit(send,first)
   waits[first]=wait_for_parent_queue(gate,set())
   first_pids={row['pid'] for row in waits[first]}
   loser=pool.submit(send,other)
   waits[other]=wait_for_parent_queue(gate,first_pids)
   gate.commit()
  win=winner.result(timeout=10);lose=loser.result(timeout=10)
 after=snapshot(t)
 record('original-parent-wait-'+first.lower(),dict(scope='ACTUAL_ORIGINAL_TESTCLIENT_ASGI_OWNED_PG_QUEUED_PARENT_LOCK',
  intended_first=first,observed_waits=waits,gate_backend_pid=gate_pid,statuses={first:win.status_code,other:lose.status_code},
  captured_fence=accepted_view['business_frontier'],before=before,after=after,loser_response=lose.json()))
 assert win.status_code==200,win.text
 assert lose.status_code==409,lose.text
 # A bounded-lock/deadlock409 does not satisfy stale-intent refusal.
 assert 'captured original business frontier changed' in lose.text,lose.text
 assert win.json()['event']['action']==first
 assert len(after['tables']['service_dispatch_events'])==2
 assert [r['row']['action'] for r in sorted(after['tables']['service_dispatch_events'],key=lambda row:row['row']['revision'])]==['OFFER',first]
 if first=='ACCEPT':
  assert len(after['tables']['service_receipt_steps'])==1 and len(after['tables']['service_receipt_events'])==1
  assert after['tables']['service_step_receipts']==[]
  with pytest.raises(Conflict):qualify_old(t)
 else:
  assert all(after['tables'][name]==[] for name in ('service_receipt_steps','service_step_receipts','service_receipt_events','case_local_lifecycles','case_local_events'))
  check_qualification(qualify_old(t),t,'WITHDRAWN')
 assert after['tables']['case_resource_links']==before['tables']['case_resource_links']
 assert after['tables']['synthetic_resource_holds']==before['tables']['synthetic_resource_holds']
