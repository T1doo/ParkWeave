pytest_plugins=['frontier_fixture_support']
from copy import deepcopy
from uuid import uuid4
from frontier_fixture_support import frontier_case
from test_preparation import headers
from test_case_resource_delivery import quoted,submit,recover,effects,preview
from test_plan_source_reapproval import approved
from test_resource_bundles import bundle
from test_service_case_steps import verified


def test_frontier_new_approval_original_tail_and_historical_fact(frontier_case):
 r=frontier_case;f,p=r['f'],r['p'];hs,b=bundle(f)
 data=quoted(f,p,{**b,'expected_link_revision':1,'expected_previous_plan_id':r['old']['id'],'replacement_frontier_profile':'KNOWN_NOT_STARTED_V1'})
 item,_=approved(f,p,data);assert item['context']['plan_replacement']['compatibility']['schema']==2
 key=uuid4().hex;actual={**data,'approval_id':item['id']};value=submit(f,p,actual,key);assert value.status_code==201,value.text
 verified(f,p,'P2')
 late=f[3].post('/api/preparations/'+p['preparation_id']+'/dispatch',headers=headers(f[2],'prep-specialist-fixture-a',uuid4().hex),json=r['old_offer_body'])
 assert late.status_code==409,late.text
 dispatch=f[3].get('/api/preparations/'+p['preparation_id']+'/dispatch',headers=headers(f[2],'prep-specialist-fixture-a')).json()
 body={**r['old_offer_body'],'reason':'SYNTHETIC explicit new-plan offer','expected_business_frontier':dispatch['business_frontier']}
 response=f[3].post('/api/preparations/'+p['preparation_id']+'/dispatch',headers=headers(f[2],'prep-specialist-fixture-a',uuid4().hex),json=body);assert response.status_code==201,response.text
 dispatch=response.json();body=dict(action='ACCEPT',expected_revision=dispatch['revision'],reason='SYNTHETIC original acceptance',expected_business_frontier=dispatch['business_frontier'])
 response=f[3].post('/api/service-dispatches/'+dispatch['dispatch_id']+'/commands',headers=headers(f[2],'executor-a',uuid4().hex),json=body);assert response.status_code==200,response.text
 dispatch=response.json();verified(f,p,'P3')
 receipt=f[3].get('/api/executor-receipts/'+dispatch['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
 body=dict(action='SUBMIT',expected_revision=receipt['step']['revision'],text='SYNTHETIC original frontier receipt',source_kind='SYNTHETIC',source_label='SYNTHETIC manual source',expected_business_frontier=receipt['business_frontier'])
 response=f[3].post('/api/executor-receipts/'+dispatch['receipt_step_id']+'/commands',headers=headers(f[2],'executor-a',uuid4().hex),json=body);assert response.status_code==200,response.text
 receipt=response.json();body=dict(action='ACKNOWLEDGE',expected_revision=receipt['step']['revision'],receipt_sha256=receipt['current_receipt']['source_sha256'],reason='SYNTHETIC original owner acknowledge',expected_business_frontier=receipt['business_frontier'])
 response=f[3].post('/api/executor-receipts/'+dispatch['receipt_step_id']+'/commands',headers=headers(f[2],key=uuid4().hex),json=body);assert response.status_code==200,response.text
 verified(f,p,'P4')
 from test_case_lifecycle import read,act
 local=read(f,p).json();body=dict(action='REVALIDATE',expected_revision=local['revision'],expected_cycle=local['cycle'],reason='SYNTHETIC original frontier revalidation',expected_snapshot_sha256=local['current_snapshot_sha256'],expected_business_frontier=local['business_frontier'])
 response=f[3].post('/api/preparations/'+p['preparation_id']+'/local-case/commands',headers=headers(f[2],key=uuid4().hex),json=body);assert response.status_code==200,response.text
 verified(f,p,'P5')
 goals=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]));assert goals.status_code==200,goals.text
 assert goals.json()['state']=='LOCAL_OUTPUTS_VERIFIED'
 cold=recover(f,p,key);assert cold.status_code==200,cold.text;assert cold.json()['receipt']==value.json()['receipt']
 assert submit(f,p,actual,key).json()['receipt']==value.json()['receipt']
