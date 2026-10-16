pytest_plugins=['p3_closure_fixture_support']
from uuid import uuid4
from copy import deepcopy
import pytest,json
from p3_closure_fixture_support import closure_case,dispatch_read
from test_resource_bundles import bundle
from test_case_resource_delivery import quoted,submit,recover
from test_plan_source_reapproval import approved
from test_service_case_steps import verified
from test_frontier_cancellations import accept,receipt_submit
from test_preparation import headers

@pytest.mark.parametrize('closure_case',['WITHDRAW','DECLINE'],indirect=True)
def test_closure_explicit_approval_native_anchor_and_original_tail(closure_case):
 t=closure_case;f,p=t['f'],t['p'];hs,b=bundle(f)
 data=quoted(f,p,{**b,'expected_link_revision':1,'expected_previous_plan_id':t['old']['id'],'replacement_frontier_profile':'P3_NEVER_ACCEPTED_CLOSED_V1'})
 item,_=approved(f,p,data);q=item['context']['plan_replacement']['compatibility']['qualification']
 assert q['schema']==1 and q['epoch']==6 and q['closure_state']=={'WITHDRAW':'WITHDRAWN','DECLINE':'DECLINED'}[t['closure_action']]
 key=uuid4().hex;r=submit(f,p,{**data,'approval_id':item['id']},key);assert r.status_code==201,r.text;original=r.json()
 verified(f,p,'P2')
 # Fresh original OFFER retains old dispatch revision and all old rows.
 from p3_closure_fixture_support import offer_current
 d,_=offer_current(t)
 from test_service_dispatches import command
 r=command(f,d,'ACCEPT',expected_business_frontier=d['business_frontier']);assert r.status_code==200,r.text;d=r.json();verified(f,p,'P3')
 row=receipt_submit(t,d)
 r=f[3].post('/api/executor-receipts/'+d['receipt_step_id']+'/commands',headers=headers(f[2],key=uuid4().hex),json=dict(action='ACKNOWLEDGE',expected_revision=row['step']['revision'],receipt_sha256=row['current_receipt']['source_sha256'],reason='SYNTHETIC explicit closure receipt acknowledgement',expected_business_frontier=row['business_frontier']));assert r.status_code==200,r.text
 verified(f,p,'P4')
 from test_case_lifecycle import read
 view=read(f,p).json();r=f[3].post('/api/preparations/'+p['preparation_id']+'/local-case/commands',headers=headers(f[2],key=uuid4().hex),json=dict(action='REVALIDATE',expected_revision=view['revision'],expected_cycle=view['cycle'],reason='SYNTHETIC explicit closure original revalidation',expected_snapshot_sha256=view['current_snapshot_sha256'],expected_business_frontier=view['business_frontier']));assert r.status_code==200,r.text
 verified(f,p,'P5')
 goals=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]));assert goals.status_code==200,goals.text;assert goals.json()['state']=='LOCAL_OUTPUTS_VERIFIED'
 cold=recover(f,p,key);assert cold.status_code==200,cold.text;assert cold.json()['receipt']==original['receipt']
 assert submit(f,p,{**data,'approval_id':item['id']},key).json()['receipt']==original['receipt']
 with f[1].connect() as c:
  parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
  assert parent['candidate_business_frontier']['epoch']>q['epoch']
  assert parent['candidate_p3_closure_consumptions'][0]['qualification']==q
 (t['out']/('core-'+t['closure_action']+'.json')).write_text(json.dumps(dict(qualification=q,goals=goals.json(),cold=cold.json()),indent=2)+'\n')
