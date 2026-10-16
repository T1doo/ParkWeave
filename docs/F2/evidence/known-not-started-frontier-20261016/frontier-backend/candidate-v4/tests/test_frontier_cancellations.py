"""Original cancellation policies with captured tracked business generations."""
pytest_plugins=['frontier_fixture_support']
from copy import deepcopy
from uuid import uuid4
import json
import pytest
from frontier_fixture_support import frontier_case
from test_case_resources import link_fixture
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
 observed={'policy':policy,'scope':'ACTUAL_OWNED_PG_ASGI_CAPTURED_FRONTIER_CANCELLATION'}
 output=x['out']/('cancellation-'+policy+'-'+uuid4().hex+'.json')
 def record(stage,value):
  observed[stage]=value;output.write_text(json.dumps(observed,indent=2,default=str)+'\n')
 if policy=='before_accept':
  module=first;stale=x['old_cancel_body'];record('stale_get',x['old_cancel_view']);fresh,view=cancellation_body(module,x);record('fresh_get',view);assert view['can_cancel'],view
 elif policy=='before_receipt':
  module=before;d=accept(x);stale,view=cancellation_body(module,x);record('stale_get',view);assert not view['can_cancel'] and view['blockers']==['ORDINARY_MANUAL_CASE_REQUIRED'],view
  verified(f,p,'P3');fresh,view=cancellation_body(module,x);record('fresh_get',view);assert not view['can_cancel'] and view['blockers']==['ORDINARY_MANUAL_CASE_REQUIRED'],view
 else:
  module=recon;d=accept(x);verified(f,p,'P3');row=receipt_submit(x,d)
  stale,view=cancellation_body(module,x,'REQUEST_CANCEL');record('stale_get',view);assert not view['can_request'] and view['blockers']==['ORDINARY_MANUAL_CASE_REQUIRED'],view
  r=f[3].post('/api/executor-receipts/'+d['receipt_step_id']+'/commands',headers=headers(f[2],key=uuid4().hex),json=dict(action='ACKNOWLEDGE',expected_revision=row['step']['revision'],receipt_sha256=row['current_receipt']['source_sha256'],reason='SYNTHETIC explicit manual acknowledgement',expected_business_frontier=row['business_frontier']));assert r.status_code==200,r.text
  verified(f,p,'P4');fresh,view=cancellation_body(module,x,'REQUEST_CANCEL');record('fresh_get',view);assert not view['can_request'] and view['blockers']==['ORDINARY_MANUAL_CASE_REQUIRED'],view
 assert stale['expected_business_frontier']!=fresh['expected_business_frontier']
 before_state=checkpoint(x);late_key=uuid4().hex;r=module.post(f,p,stale,late_key)
 record('stale_refusal',{'status':r.status_code,'reply':r.json(),'no_effect':checkpoint(x)==before_state})
 assert r.status_code==409 and r.json()['detail']==DETAIL,r.text
 assert checkpoint(x)==before_state
 assert module.recover(f,p,late_key).json()['status']=='NOT_OBSERVED'
 missing={k:v for k,v in fresh.items() if k!='expected_business_frontier'}
 r=module.post(f,p,missing,uuid4().hex)
 record('missing_fence_refusal',{'status':r.status_code,'reply':r.json(),'no_effect':checkpoint(x)==before_state})
 assert r.status_code==409 and r.json()['detail']==DETAIL,r.text
 assert checkpoint(x)==before_state
 key=uuid4().hex;r=module.post(f,p,fresh,key)
 record('fresh_submission',{'status':r.status_code,'reply':r.json(),'no_effect':checkpoint(x)==before_state})
 if policy!='before_accept':
  assert r.status_code==409 and 'ORDINARY_MANUAL_CASE_REQUIRED' in r.json()['detail'],r.text
  assert checkpoint(x)==before_state
  assert module.recover(f,p,key).json()['status']=='NOT_OBSERVED'
  cold=recover(f,p,delivery_key);assert cold.status_code==200,cold.text;assert cold.json()['receipt']==delivery_receipt['receipt']
  return
 assert r.status_code==200,r.text
 original=r.json();assert module.post(f,p,fresh,key).json()==original
 saved=[(key,fresh,original)]
 for k,body,original in saved:
  r=module.recover(f,p,k);assert r.status_code==200,r.text;assert r.json()['event']==original['event']
  r=module.post(f,p,body,k);assert r.status_code==200,r.text;assert r.json()==original
  current_fence=module.get(f,p).json()['business_frontier'];assert current_fence!=body['expected_business_frontier']
  r=module.post(f,p,{**body,'expected_business_frontier':current_fence},k);assert r.status_code==409,r.text
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


def test_frontier_cancellation_legacy_accept_and_create_raw_null_cannot_reconstruct_exact_original_lineage(link_fixture):
 # Controlled owned-PG corruption, not an API cancellation authorization.
 f=link_fixture;p,d=before.accepted(f)
 good=before.get(f,p);assert good.status_code==200 and good.json()['can_cancel'],good.text
 with f[1].connect() as c:
  c.execute("UPDATE service_dispatch_events SET payload=payload||'{\"expected_business_frontier\":null}'::jsonb WHERE dispatch_id=%s AND action='ACCEPT'",(d['dispatch_id'],))
  c.execute("UPDATE service_receipt_events SET payload=payload||'{\"expected_business_frontier\":null}'::jsonb WHERE step_id=%s AND action='CREATE'",(d['receipt_step_id'],))
 bad=before.get(f,p);assert bad.status_code==200,bad.text
 assert not bad.json()['can_cancel']
 assert 'EXACT_MANUAL_ACCEPTANCE_AND_CREATE_PROOF_REQUIRED' in bad.json()['blockers']


@pytest.mark.parametrize('value',[None,False,0,[],{}, {'generation':None}])
def test_frontier_history_present_field_requires_exact_valid_object(value):
 from parkweave.business_frontier_types import historical_fields
 with pytest.raises(ValueError):historical_fields({'expected_business_frontier':value})
 assert historical_fields({})=={}
