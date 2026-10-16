"""Actual owned PG and TestClient ASGI: no native HTTP/browser claim."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
from uuid import uuid4
import pytest
from frontier_fixture_support import (frontier_case,capability_resource_catalog,
 capability_catalog,receipt_fixture,preparation_fixture)
from frontier_oracle_support import (verify_imports,commit,verified,offer_body,
 offer_post,snapshot,record,headers,effects,ledger)
from test_service_dispatches import command as dispatch_command

@pytest.fixture(autouse=True)
def verify_actual_candidate_imports():verify_imports()


def awaiting_receipt(x):
 f,p=x['f'],x['p'];result=commit(x);verified(f,p,'P2')
 r=offer_post(x,offer_body(x));assert r.status_code==201,r.text;row=r.json()
 r=dispatch_command(f,row,'ACCEPT',expected_business_frontier=row['business_frontier']);assert r.status_code==200,r.text
 dispatch=r.json();verified(f,p,'P3')
 r=f[3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(f[2],'executor-a'));assert r.status_code==200,r.text
 return result,dispatch,r.json()


def test_frontier_actual_p4_two_transactions_same_captured_fence_one_success_one_conflict(frontier_case):
 x=frontier_case;f,p=x['f'],x['p'];result,dispatch,row=awaiting_receipt(x)
 body=dict(action='SUBMIT',expected_revision=row['step']['revision'],
  text='SYNTHETIC independent concurrent original P4 receipt',source_kind='SYNTHETIC',
  source_label='SYNTHETIC original manual receipt concurrency probe',
  expected_business_frontier=deepcopy(row['business_frontier']))
 keys=[uuid4().hex,uuid4().hex];barrier=Barrier(2);before=snapshot(f,p)
 resource_before=effects(f);approval_before=deepcopy(ledger(f,p))
 def send(key):
  barrier.wait(timeout=5)
  return f[3].post('/api/executor-receipts/'+dispatch['receipt_step_id']+'/commands',
   headers=headers(f[2],'executor-a',key),json=deepcopy(body))
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(send,key) for key in keys]
  responses=[future.result(timeout=20) for future in futures]
 statuses=sorted(r.status_code for r in responses)
 record('p4-concurrent-original-same-fence',dict(scope='ACTUAL_ASGI_HTTP_OWNED_PG_TWO_CONCURRENT_REQUEST_TRANSACTIONS',
  statuses=statuses,captured_fence=body['expected_business_frontier'],before=before,
  after=snapshot(f,p),errors=[r.json() for r in responses if r.status_code!=200]))
 assert statuses==[200,409],[r.status_code for r in responses]
 success=next(r.json() for r in responses if r.status_code==200)
 assert success['step']['state']=='RECEIPT_RECORDED' and success['step']['revision']==row['step']['revision']+1
 after=snapshot(f,p)
 assert after['counts']['service_step_receipts']==before['counts']['service_step_receipts']+1
 assert after['counts']['service_receipt_events']==before['counts']['service_receipt_events']+1
 assert all(after['counts'][t]==before['counts'][t] for t in before['counts'] if t not in ('service_step_receipts','service_receipt_events'))
 assert after['marker']['epoch']>before['marker']['epoch'] and effects(f)==resource_before and ledger(f,p)==approval_before
 with f[1].connect() as c:
  rows=c.execute('SELECT request_key FROM service_receipt_events WHERE step_id=%s AND action=%s',
   (dispatch['receipt_step_id'],'SUBMIT')).fetchall()
 assert len(rows)==1 and rows[0]['request_key'] in keys
 r=f[3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(f[2],'executor-a'))
 assert r.status_code==200,r.text
 assert r.json()['current_receipt']==success['current_receipt']
 assert len(r.json()['receipt_history'])==1 and len(r.json()['history'])==2
