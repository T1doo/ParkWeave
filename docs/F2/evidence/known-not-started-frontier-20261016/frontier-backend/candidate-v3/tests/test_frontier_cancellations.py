"""Original cancellation policies with captured tracked business generations."""
pytest_plugins=['frontier_fixture_support']
from copy import deepcopy
from uuid import uuid4
import pytest
from frontier_fixture_support import frontier_case
from test_preparation import headers
from test_case_resource_delivery import quoted,submit,recover,effects
from test_plan_source_reapproval import approved
from test_resource_bundles import bundle
from test_service_case_steps import verified
import test_case_cancellation as first
import test_case_cancellation_before_receipt as before
import test_case_cancellation_reconciliation as recon
from parkweave.store import Denied

DETAIL='captured original business frontier changed; fresh original GET required'


def checkpoint(x):
 f=x['f'];p=x['p']
 with f[1].connect() as c:
  return dict(preparation=deepcopy(c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()),
   case=deepcopy(c.execute('SELECT * FROM cases WHERE id=%s',(p['case_id'],)).fetchone()),
   effects=effects(f),local=[dict(r) for r in c.execute('SELECT * FROM case_local_events WHERE preparation_id=%s ORDER BY revision',(p['preparation_id'],)).fetchall()])


def commit(x):
 f,p=x['f'],x['p'];hs,b=bundle(f)
 data=quoted(f,p,{**b,'expected_link_revision':1,'expected_previous_plan_id':x['old']['id'],'replacement_frontier_profile':'KNOWN_NOT_STARTED_V1'})
 item,_=approved(f,p,data);key=uuid4().hex
 r=submit(f,p,{**data,'approval_id':item['id']},key);assert r.status_code==201,r.text
 verified(f,p,'P2');return key,r.json()


def accept(x):
 f,p=x['f'],x['p']
 current=f[3].get('/api/service-dispatches/catalog',params={'preparation_id':p['preparation_id']},headers=headers(f[2],'prep-specialist-fixture-a'));assert current.status_code==200,current.text
 body={**x['old_offer_body'],'expected_business_frontier':current.json()['business_frontier']}
 r=f[3].post('/api/preparations/'+p['preparation_id']+'/dispatch',headers=headers(f[2],'prep-specialist-fixture-a',uuid4().hex),json=body);assert r.status_code==201,r.text
 d=r.json();r=f[3].post('/api/service-dispatches/'+d['dispatch_id']+'/commands',headers=headers(f[2],'executor-a',uuid4().hex),json=dict(action='ACCEPT',expected_revision=d['revision'],reason='SYNTHETIC tracked original accept',expected_business_frontier=d['business_frontier']));assert r.status_code==200,r.text
 return r.json()


def receipt_submit(x,d):
 f=x['f'];rid=d['receipt_step_id'];r=f[3].get('/api/executor-receipts/'+rid,headers=headers(f[2],'executor-a'));assert r.status_code==200,r.text
 v=r.json();body=dict(action='SUBMIT',expected_revision=v['step']['revision'],text='SYNTHETIC manual frontier cancellation receipt',source_kind='SYNTHETIC',source_label='SYNTHETIC manual',expected_business_frontier=v['business_frontier'])
 r=f[3].post('/api/executor-receipts/'+rid+'/commands',headers=headers(f[2],'executor-a',uuid4().hex),json=body);assert r.status_code==200,r.text
 return r.json()


def cancellation_body(module,x,action=None):
 f,p=x['f'],x['p'];r=module.get(f,p);assert r.status_code==200,r.text
 view=r.json();b=module.body(f,p,action) if action else module.body(f,p)
 b['expected_business_frontier']=deepcopy(view['business_frontier'])
 return b,view


@pytest.mark.parametrize('policy',['before_accept','before_receipt','reconciliation'])
def test_frontier_cancellation_original_policy_captured_fence_rejects_late_and_preserves_replay(frontier_case,policy):
 x=frontier_case;f,p=x['f'],x['p'];delivery_key,delivery_receipt=commit(x)
 if policy=='before_accept':
  module=first;stale=x['old_cancel_body'];fresh,view=cancellation_body(module,x);assert view['can_cancel'],view
 elif policy=='before_receipt':
  module=before;d=accept(x);stale,view=cancellation_body(module,x);assert not view['can_cancel'] and 'ORDINARY_MANUAL_CASE_REQUIRED' in view['blockers'],view
  verified(f,p,'P3');fresh,view=cancellation_body(module,x);assert not view['can_cancel'] and 'ORDINARY_MANUAL_CASE_REQUIRED' in view['blockers'],view
 else:
  module=recon;d=accept(x);verified(f,p,'P3');row=receipt_submit(x,d)
  stale,view=cancellation_body(module,x,'REQUEST_CANCEL');assert not view['can_request'] and 'ORDINARY_MANUAL_CASE_REQUIRED' in view['blockers'],view
  r=f[3].post('/api/executor-receipts/'+d['receipt_step_id']+'/commands',headers=headers(f[2],key=uuid4().hex),json=dict(action='ACKNOWLEDGE',expected_revision=row['step']['revision'],receipt_sha256=row['current_receipt']['source_sha256'],reason='SYNTHETIC explicit manual acknowledgement',expected_business_frontier=row['business_frontier']));assert r.status_code==200,r.text
  verified(f,p,'P4');fresh,view=cancellation_body(module,x,'REQUEST_CANCEL');assert not view['can_request'] and 'ORDINARY_MANUAL_CASE_REQUIRED' in view['blockers'],view
 assert stale['expected_business_frontier']!=fresh['expected_business_frontier']
 before_state=checkpoint(x);late_key=uuid4().hex;r=module.post(f,p,stale,late_key)
 assert r.status_code==409 and r.json()['detail']==DETAIL,r.text
 assert checkpoint(x)==before_state
 assert module.recover(f,p,late_key).json()['status']=='NOT_OBSERVED'
 missing={k:v for k,v in fresh.items() if k!='expected_business_frontier'}
 r=module.post(f,p,missing,uuid4().hex)
 assert r.status_code==409 and r.json()['detail']==DETAIL,r.text
 assert checkpoint(x)==before_state
 key=uuid4().hex;r=module.post(f,p,fresh,key)
 if policy!='before_accept':
  assert r.status_code==409 and 'ORDINARY_MANUAL_CASE_REQUIRED' in r.json()['detail'],r.text
  assert checkpoint(x)==before_state
  assert module.recover(f,p,key).json()['status']=='NOT_OBSERVED'
  cold=recover(f,p,delivery_key);assert cold.status_code==200,cold.text;assert cold.json()['receipt']==delivery_receipt['receipt']
  return
 assert r.status_code==200,r.text
 original=r.json();assert module.post(f,p,fresh,key).json()==original
 saved=[(key,fresh,original)]
 if policy=='reconciliation':
  for action in ('RECONCILE','CONFIRM_CANCEL'):
   body,view=cancellation_body(module,x,action);assert not view['blockers'],view
   k=uuid4().hex;r=module.post(f,p,body,k);assert r.status_code==200,r.text;saved.append((k,body,r.json()))
 for k,body,original in saved:
  r=module.recover(f,p,k);assert r.status_code==200,r.text;assert r.json()['event']==original['event']
  r=module.post(f,p,body,k);assert r.status_code==200,r.text;assert r.json()==original
  observed=module.get(f,p).json()['business_frontier'];assert observed!=body['expected_business_frontier']
  r=module.post(f,p,{**body,'expected_business_frontier':observed},k);assert r.status_code==409,r.text
  r=module.post(f,p,{**body,'reason':'SYNTHETIC changed samekey'},k);assert r.status_code==409,r.text
 cold=recover(f,p,delivery_key);assert cold.status_code==200,cold.text;assert cold.json()['receipt']==delivery_receipt['receipt']
 # Controlled owner inheritance fault: current child is rejected, as is the
 # sticky relhassubclass left by CREATE/DROP; no claim about arbitrary owner DDL.
 with f[1].connect() as c:c.execute('CREATE TABLE frontier_effect_child () INHERITS(service_receipt_steps)')
 with f[0].connect() as c:
  with pytest.raises(Denied,match='noninherited'):x['protocol'].check(c)
 with f[1].connect() as c:c.execute('DROP TABLE frontier_effect_child')
 with f[0].connect() as c:
  with pytest.raises(Denied,match='noninherited'):x['protocol'].check(c)
