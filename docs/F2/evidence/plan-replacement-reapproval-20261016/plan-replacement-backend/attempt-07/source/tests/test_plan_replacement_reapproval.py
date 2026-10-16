"""Independent design fixture proof; does not claim replacement delivery implemented."""
from copy import deepcopy
from uuid import UUID,uuid4
import hashlib,json
from pathlib import Path
import pytest
from parkweave import service_case_steps as steps,service_selection_candidates as sc,bounded_planning as bp
from parkweave import service_release_preflight as pf
from parkweave.template_consumer import ConsumerRepository
from parkweave.service_capability_contract import hash_instance
from test_preparation import preparation_fixture,headers,command
from test_executor_receipts import receipt_fixture,ready
from test_service_capability_catalog_actual import capability_catalog,capability_resource_catalog,register,material_instance,coordination_instance
from test_service_selection_candidates import planner
from test_independent_selection_integration import adoption
from test_service_case_steps import verified
from test_new_enterprise_local_chain import ALL_GOALS
from test_request_intents import save
from test_template_upgrade import publication


def generate(a,p,revision=0):
 f=a['f'];store=f[0];store._isolated_service_capability_catalog=a['catalog']
 with a['catalog'].connection() as c:
  actor,parent=bp._context(store,c,f[2]['fixture-a'],UUID(p['preparation_id']))
  q=sc.current(store,c,actor,parent,a['catalog'])
 data=sc.Capture(expected_preparation_revision=q['preparation_revision'],expected_source_sha256=q['source_sha256'],expected_capability_catalog_sha256=q['capability_catalog_sha256'])
 v=sc.generate(store,f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,data,catalog=a['catalog'],planner=planner([],mode='all'))
 d=adoption(v).model_copy(update={'expected_plan_revision':revision})
 return steps.adopt(store,f[2]['fixture-a'],UUID(p['preparation_id']),uuid4().hex,d)


def bind_all(a,revision=1):
 values=[]
 for service in ('synthetic-material-preparation','synthetic-resource-coordination','synthetic-local-record-recheck'):
  r=register(a,service=service)['release']
  i=material_instance(r) if service=='synthetic-material-preparation' else coordination_instance(r)
  if service=='synthetic-local-record-recheck':i['instance_id']='park-a-recheck-instance'
  i['config_revision']=revision;i['config_sha256']=hash_instance(i)
  a['catalog'].bind_instance('park-a',uuid4().hex,i);values.append((r,i))
 return values


from test_resource_bundles import bundle,states
from test_case_resource_delivery import quoted,submit,effects,recover,preview
from test_plan_source_reapproval import approved
from test_service_dispatches import offer,command as dispatch
from test_executor_receipts import act as receipt
from test_case_lifecycle import read as localread,act as localact


def _replacement_fixture(capability_resource_catalog,tmp_path,*,old_complete=True):
 a=capability_resource_catalog;f=a['f']
 import os
 private=os.environ.get('PARKWEAVE_REPLACEMENT_PRIVATE_DIR')
 if private:
  directory=Path(private);directory.mkdir(parents=True,exist_ok=True)
  fd=os.open(directory/('fixture-'+uuid4().hex+'.private.json'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'w') as output:output.write(json.dumps(sorted(f[2].values()))+'\n')
 oldpairs=bind_all(a)
 p=ready(f);r=save(f,p,goals=ALL_GOALS);assert r.status_code==200
 p={**p,'revision':r.json()['revision']}
 p=command(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC independent six-goal review').json()
 p=command(f,p,'CONFIRM',reason='SYNTHETIC independent six-goal confirm').json()
 old=generate(a,p);verified(f,p,'P1')
 from test_resource_bundles import bundle
 from test_case_resource_delivery import quoted,submit
 from test_plan_source_reapproval import approved
 from test_service_plan_approval import enable
 from test_service_dispatches import offer,command as dispatch
 from test_executor_receipts import act as receipt
 from test_case_lifecycle import read as localread,act as localact
 checker=pf.ServiceReleasePreflight(a['catalog'],ConsumerRepository(tmp_path/'candidate-initial-preflight.consumer.candidate.sqlite3'),enabled_for_isolated_tests=True)
 enable(f,p,enabled_for_source_reapproval_tests=True,enabled_for_plan_replacement_tests=True,plan_replacement_preflight=checker)
 hs,b=bundle(f);old_holds=deepcopy(hs);d=quoted(f,p,b);item,_=approved(f,p,d)
 result=submit(f,p,{**d,'approval_id':item['id']});assert result.status_code==201,result.text
 verified(f,p,'P2');dr=None
 if old_complete:
  dr=dispatch(f,offer(f,p)[0].json(),'ACCEPT').json();verified(f,p,'P3')
  sr=f[3].get('/api/executor-receipts/'+dr['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
  sr=receipt(f,sr,'SUBMIT').json();sr=receipt(f,sr,'ACKNOWLEDGE').json();verified(f,p,'P4')
  lr=localact(f,p,localread(f,p).json(),'REVALIDATE');assert lr.status_code==200,lr.text
  verified(f,p,'P5')
 with f[1].connect() as c:oldstored=deepcopy(c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['service_case_plan'])
 a['published']=publication(a,goals=a['published']['snapshot']['definition']['required_goals'],source='1',name='SYNTHETIC independent compatible title-only full replacement')
 newpairs=bind_all(a,2)
 from parkweave import service_capability_catalog as cat
 for r,i in oldpairs:
  with a['catalog'].connection() as c:revision=cat.proof(cat.row(c,'park-a'))['revision']
  a['catalog'].withdraw_release('park-a',uuid4().hex,r['release_id'],revision,'SYNTHETIC explicit superseded release retirement preserves Case history')
 checker=pf.ServiceReleasePreflight(a['catalog'],ConsumerRepository(tmp_path/'independent-preflight.consumer.candidate.sqlite3'),enabled_for_isolated_tests=True)
 comparisons=[]
 for (r,i),(nr,ni) in zip(oldpairs,newpairs):
  q=checker.preview(f[2]['fixture-a'],UUID(p['preparation_id']),original_release_id=r['release_id'],original_instance_id=i['instance_id'],target_instance_id=ni['instance_id'])
  expected='NEEDS_RECHECK' if old_complete else 'UNKNOWN'
  assert q['classification']==expected, {k:q[k] for k in ('classification','contract_classification','blocking_reasons','current_case_blocking_reasons')}
  assert q['contract_classification']=='COMPATIBLE'
  assert q['target_current_available'] and not q['original_source_current_available'] and q['can_record'] is old_complete
  comparisons.append(q)
 # Original catalog row epoch changed: obtain a fresh original material review.
 for action,actor in (('REOPEN','fixture-a'),('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')):
  refreshed=command(f,p,action,actor,reason='SYNTHETIC explicit current catalog material review '+action)
  assert refreshed.status_code==200,refreshed.text;p=refreshed.json()
 new=generate(a,p,oldstored['revision'])
 assert old['plan_id']!=new['plan_id'] and new['revision']==1
 assert new['required_goals']==ALL_GOALS and len(new['steps'])==5
 # Original replacement flattens prior history=[] rather than retaining nested history.
 expected_old=deepcopy(oldstored);expected_old.pop('history',None)
 assert new['history']==[expected_old]
 assert {s['id'] for s in old['steps']}.isdisjoint(s['id'] for s in new['steps'])
 with f[1].connect() as c:
  parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
  proofs=steps._recovery_proofs(parent)
  oldrecord=sc.find(parent,old['candidate_consumption']['candidate_id']);newrecord=sc.find(parent,new['candidate_consumption']['candidate_id'])
 assert oldrecord['document']['catalog_snapshot']!=newrecord['document']['catalog_snapshot']
 src=Path(steps.__file__).resolve();assert src==Path(__file__).resolve().parents[1]/'src/parkweave/service_case_steps.py'

 return dict(f=f,p=p,oldstored=oldstored,new=new,old=old,old_holds=old_holds,result=result,dr=dr,comparisons=comparisons)
def test_actual_six_goal_full_replacement_new_approval_atomic_delivery_and_later_note_cold_get(capability_resource_catalog,tmp_path):
 r=_replacement_fixture(capability_resource_catalog,tmp_path)
 f,p,oldstored,new,old,old_holds,result,dr=(r[k] for k in ('f','p','oldstored','new','old','old_holds','result','dr'))
 # Fresh Approval and original transaction on the actual new plan.
 verified(f,p,'P1')
 hs,b=bundle(f)
 data=quoted(f,p,{**b,'expected_link_revision':1,'expected_previous_plan_id':oldstored['id']})
 from test_case_resource_delivery import effects,recover
 before=effects(f);assert submit(f,p,data).status_code==409 and effects(f)==before
 item,view=approved(f,p,data)
 assert item['purpose']=='CASE_RESOURCE_PLAN_REPLACEMENT'
 assert item['context']['plan_replacement']['previous_plan_id']==oldstored['id']
 assert len(item['context']['plan_replacement']['compatibility']['pairs'])==3
 key=uuid4().hex;actual={**data,'approval_id':item['id']}
 value=submit(f,p,actual,key);assert value.status_code==201,value.text
 assert value.json()['independent_check']['status']=='CURRENT'
 assert value.json()['link']['revision']==2 and effects(f)==[2,6,2,2,2]
 verified(f,p,'P2')
 cold=recover(f,p,key);assert cold.status_code==200,cold.text
 assert cold.json()['receipt']==value.json()['receipt'] and cold.json()['independent_check']['status']=='CURRENT'
 assert submit(f,p,actual,key).json()['receipt']==value.json()['receipt']

 # Original preparation generation changed; explicit same-executor reoffer
 # and new receipt generation preserve the old accepted offer/receipt history.
 from test_service_dispatches import read as dispatch_read
 previous=dispatch_read(f,dr).json()
 rr=offer(f,p,revision=previous['revision'],recovery_receipt_step_id=previous['recovery_receipt_step_id'])[0]
 assert rr.status_code==201,rr.text
 dr2=dispatch(f,rr.json(),'ACCEPT');assert dr2.status_code==200,dr2.text;dr2=dr2.json()
 verified(f,p,'P3')
 sr2=f[3].get('/api/executor-receipts/'+dr2['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
 sr2=receipt(f,sr2,'SUBMIT').json();sr2=receipt(f,sr2,'ACKNOWLEDGE').json();verified(f,p,'P4')
 lr=localact(f,p,localread(f,p).json(),'REVALIDATE');assert lr.status_code==200,lr.text
 verified(f,p,'P5')
 goals=f[3].get('/api/preparations/'+p['preparation_id']+'/goal-results',headers=headers(f[2]))
 assert goals.status_code==200,goals.text
 assert goals.json()['state']=='LOCAL_OUTPUTS_VERIFIED' and len(goals.json()['results'])==6
 worklist=f[3].get('/api/cases/worklist',headers=headers(f[2]));assert worklist.status_code==200,worklist.text
 from test_resource_bundles import states
 assert states(f,hs)==['CONFIRMED']*3 and states(f,old_holds)==['CONFIRMED']*3
 prior=recover(f,p,result.json()['delivery_binding']['request_key']);assert prior.status_code==200,prior.text
 assert prior.json()['receipt']==result.json()['receipt'] and prior.json()['independent_check']['status']=='NEEDS_RECHECK'

 # A legal later human note cannot erase the already consumed original fact.
 from test_plan_source_conflicts import edit
 note=edit(f,p,'SYNTHETIC explicit later owner coordination note')
 after_note=recover(f,p,key);assert after_note.status_code==200,after_note.text
 assert after_note.json()['receipt']==value.json()['receipt']
 assert after_note.json()['independent_check']['status'] in ('CURRENT','NEEDS_RECHECK')
 approval_read=f[3].get('/api/preparations/'+p['preparation_id']+'/plan-approval',headers=headers(f[2]))
 assert approval_read.status_code==200,approval_read.text


def test_incomplete_original_business_chain_is_unknown_and_cannot_replacement_quote(capability_resource_catalog,tmp_path):
 r=_replacement_fixture(capability_resource_catalog,tmp_path,old_complete=False);f,p=r['f'],r['p']
 assert all(q['classification']=='UNKNOWN' and q['can_record'] is False for q in r['comparisons'])
 assert [s['coordination_state'] for s in r['oldstored']['steps']]==['VERIFIED','VERIFIED','PENDING','PENDING','PENDING']
 verified(f,p,'P1');hs,b=bundle(f);before=effects(f)
 with f[1].connect() as c:original=c.execute('SELECT candidate_plan_approvals FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['candidate_plan_approvals']
 response=preview(f,p,{**b,'expected_link_revision':1,'expected_previous_plan_id':r['oldstored']['id']})
 assert response.status_code==409,response.text
 assert 'complete verified five-step' in response.json()['detail']
 assert effects(f)==before and states(f,hs)==['HELD']*3
 with f[1].connect() as c:assert c.execute('SELECT candidate_plan_approvals FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()['candidate_plan_approvals']==original


@pytest.mark.parametrize('fault',['executor_revoke','old_resource_cancel'])
def test_previously_verified_but_now_unavailable_source_cannot_replacement_quote(capability_resource_catalog,tmp_path,fault):
 r=_replacement_fixture(capability_resource_catalog,tmp_path);f,p=r['f'],r['p']
 assert all(q['classification']=='NEEDS_RECHECK' for q in r['comparisons'])
 verified(f,p,'P1');hs,b=bundle(f)
 if fault=='executor_revoke':
  with f[1].connect() as c:c.execute("UPDATE capability_grants SET active=false WHERE principal_id='executor-a' AND capability='READ'")
 else:
  from test_resource_bundles import cancel
  cancel(f,r['result'].json()['combination']['id'])
 before=effects(f)
 response=preview(f,p,{**b,'expected_link_revision':1,'expected_previous_plan_id':r['oldstored']['id']})
 assert response.status_code==409,response.text
 if fault=='executor_revoke':
  # The original P1/catalog gate can reject first. Independently exercise the
  # new live-known guard against the same actual PG source, without an HTTP
  # shortcut or pretending its early original denial was a successful quote.
  assert response.json()['detail'] in ('CURRENT_PLAN_P1_REQUIRED','original current known replacement source graph required')
  from parkweave.plan_replacement_compatibility import compare
  from parkweave.store import Conflict
  with f[0].connect() as c:
   actor,parent=steps._context(f[0],c,f[2]['fixture-a'],UUID(p['preparation_id']))
   previous=next(plan for plan in parent['service_case_plan']['history'] if plan['id']==r['oldstored']['id'])
   with pytest.raises(Conflict,match='original current known replacement source graph required'):
    compare(f[0],c,actor,parent,previous,parent['service_case_plan'])
 else:
  assert 'current known replacement source graph' in response.json()['detail']
 assert effects(f)==before and states(f,hs)==['HELD']*3
