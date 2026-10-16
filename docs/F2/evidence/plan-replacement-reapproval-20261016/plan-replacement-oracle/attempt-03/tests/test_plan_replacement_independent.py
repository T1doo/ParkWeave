"""Independent design fixture proof; does not claim replacement delivery implemented."""
from copy import deepcopy
from uuid import UUID,uuid4
import hashlib,json,os
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


@pytest.fixture
def replacement_case(capability_resource_catalog,tmp_path):
 expected=os.environ.get('PLAN_REPLACEMENT_TEST_SOURCE_ROOT')
 if expected:
  import importlib
  for name in ('case_resource_delivery','service_plan_approval','case_resources','plan_replacement_compatibility','resource_plan_binding','api'):
   module=importlib.import_module('parkweave.'+name)
   assert Path(module.__file__).resolve().parent==Path(expected).resolve()
 a=capability_resource_catalog;f=a['f'];oldpairs=bind_all(a)
 out=next(p for p in Path(__file__).resolve().parents if (p/'pyproject.toml').exists())/'.runtime/plan-replacement-oracle/artifacts'
 out.mkdir(parents=True,exist_ok=True)
 private=out/('redaction-'+uuid4().hex+'.private.json')
 with os.fdopen(os.open(private,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'w') as h:json.dump(sorted(set(f[2].values())),h)
 checker=pf.ServiceReleasePreflight(a['catalog'],ConsumerRepository(tmp_path/'independent-preflight.consumer.candidate.sqlite3'),enabled_for_isolated_tests=True)
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
 bridge=enable(f,p,enabled_for_source_reapproval_tests=True,enabled_for_plan_replacement_tests=True,plan_replacement_preflight=checker)
 hs,b=bundle(f);d=quoted(f,p,b);item,_=approved(f,p,d)
 result=submit(f,p,{**d,'approval_id':item['id']});assert result.status_code==201,result.text
 verified(f,p,'P2');dr=dispatch(f,offer(f,p)[0].json(),'ACCEPT').json();verified(f,p,'P3')
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
 comparisons=[]
 for (r,i),(nr,ni) in zip(oldpairs,newpairs):
  q=checker.preview(f[2]['fixture-a'],UUID(p['preparation_id']),original_release_id=r['release_id'],original_instance_id=i['instance_id'],target_instance_id=ni['instance_id'])
  assert q['classification']=='NEEDS_RECHECK', {k:q[k] for k in ('classification','contract_classification','blocking_reasons','current_case_blocking_reasons')};assert q['classification']=='NEEDS_RECHECK' and q['contract_classification']=='COMPATIBLE'
  assert q['target_current_available'] and not q['original_source_current_available'] and q['can_record']
  comparisons.append(q)
 # Original reviewed-material proof binds the actual catalog row generation.
 # Refresh it explicitly after all admitted/retired catalog writes, before adoption.
 for action,actor in [('REOPEN','fixture-a'),('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')]:
  response=command(f,p,action,actor,reason='SYNTHETIC original material review after known release replacement')
  assert response.status_code==200,response.text
  p=response.json()
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
 return dict(a=a,f=f,p=p,old=oldstored,new=new,oldreceipt=result.json(),checker=checker,bridge=bridge,oldpairs=oldpairs,newpairs=newpairs,old_dispatch=dr)


def new_quote(x):
 from test_resource_bundles import bundle
 from test_case_resource_delivery import quoted
 f,p=x['f'],x['p'];verified(f,p,'P1');hs,b=bundle(f)
 request={**b,'expected_link_revision':1,'expected_previous_plan_id':x['old']['id']}
 return hs,quoted(f,p,request)


def test_independent_explicit_new_approval_and_original_verify_six_goals(replacement_case):
 from test_plan_source_reapproval import approved
 from test_case_resource_delivery import submit,recover,effects
 from test_resource_bundles import states
 from test_service_plan_approval import ledger
 from test_case_goal_results import get
 from test_case_lifecycle import read as localread,act as localact
 x=replacement_case;f,p=x['f'],x['p'];old=deepcopy(x['oldreceipt']);oldledger=deepcopy(ledger(f,p))
 hs,data=new_quote(x);before=effects(f)
 assert submit(f,p,data).status_code==409 and effects(f)==before
 assert submit(f,p,{**data,'approval_id':old['receipt']['plan_approval']['id']}).status_code==409 and effects(f)==before
 item,_=approved(f,p,data);assert item['purpose']=='CASE_RESOURCE_PLAN_REPLACEMENT'
 key=uuid4().hex;body={**data,'approval_id':item['id']};r=submit(f,p,body,key);assert r.status_code==201,r.text
 result=r.json();assert result['independent_check']['status']=='CURRENT'
 assert effects(f)==[2,6,2,2,2] and states(f,hs)==['CONFIRMED']*3
 assert ledger(f,p)['events'][:3]==oldledger['events'] and ledger(f,p)['revision']==6
 verified(f,p,'P2')
 from test_service_dispatches import offer,command as dispatch
 from test_executor_receipts import act as receipt
 q=f[3].get('/api/service-dispatches/'+x['old_dispatch']['dispatch_id'],headers=headers(f[2],'prep-specialist-fixture-a'));assert q.status_code==200,q.text
 q=q.json();r=offer(f,p,revision=q['revision'],recovery_receipt_step_id=q['recovery_receipt_step_id'])[0];assert r.status_code==201,r.text
 accepted=dispatch(f,r.json(),'ACCEPT');assert accepted.status_code==200,accepted.text
 verified(f,p,'P3')
 sr=f[3].get('/api/executor-receipts/'+accepted.json()['receipt_step_id'],headers=headers(f[2],'executor-a')).json()
 sr=receipt(f,sr,'SUBMIT');assert sr.status_code==200,sr.text
 sr=receipt(f,sr.json(),'ACKNOWLEDGE');assert sr.status_code==200,sr.text
 verified(f,p,'P4')
 assert localact(f,p,localread(f,p).json(),'REVALIDATE').status_code==200
 verified(f,p,'P5');g=get(f,p);assert g.status_code==200,g.text
 raw=next(q for q in Path(__file__).resolve().parents if (q/'pyproject.toml').exists())/'.runtime/plan-replacement-oracle/artifacts'
 (raw/('goal-results-'+uuid4().hex+'.json')).write_text(json.dumps(g.json(),indent=2)+'\n')
 assert g.json()['state']=='LOCAL_OUTPUTS_VERIFIED' and len(g.json()['results'])==6
 assert all(row['state']=='LOCAL_OUTPUT_VERIFIED' for row in g.json()['results']) and not g.json()['case_goal_completed']
 work=f[3].get('/api/cases/worklist',headers=headers(f[2]),params={'limit':1});assert work.status_code==200,work.text
 w=work.json();assert w['read_only'] and w['recorded_states_only']
 hit=next(row for row in w['items'] if row['case_id']==p['case_id'])
 assert hit['preparation_id']==p['preparation_id'] and hit['run_id']==p['run_id'] and not hit['case_goal_completed'] and not hit['evidence_verified']
 cold=recover(f,p,key);assert cold.status_code==200,cold.text
 assert cold.json()['receipt']==result['receipt'] and cold.json()['independent_check']['status']=='CURRENT'
 assert submit(f,p,body,key).json()['receipt']==result['receipt'] and effects(f)==[2,6,2,2,2]
 for field,value in [('reason',body['reason']+' changed'),('expected_previous_plan_id',str(uuid4())),('expected_link_revision',2),('approval_id',str(uuid4()))]:
  r=submit(f,p,{**body,field:value},key);assert r.status_code==409,r.text
  assert effects(f)==[2,6,2,2,2]
 historic=recover(f,p,old['delivery_binding']['request_key']);assert historic.status_code==200,historic.text
 assert historic.json()['receipt']==old['receipt'] and historic.json()['independent_check']['status']=='NEEDS_RECHECK'
 assert states(f,old['combination']['members'])==['CONFIRMED']*3


@pytest.mark.parametrize('user',['fixture-b','fixture-c','prep-specialist-fixture-a','executor-a'])
def test_independent_other_current_identity_denies_quote_propose_commit_and_private_reads(replacement_case,user):
 from test_case_resource_delivery import preview,submit,recover,effects
 from test_service_plan_approval import propose,read
 x=replacement_case;f,p=x['f'],x['p'];hs,data=new_quote(x);before=effects(f)
 for r in (preview(f,p,{k:data[k] for k in ('members','expected_link_revision','expected_previous_plan_id')},user),propose(f,p,data,revision=3,user=user),submit(f,p,data,user=user),recover(f,p,x['oldreceipt']['delivery_binding']['request_key'],user),read(f,p,user)):
  assert r.status_code==403 and 'recorded_preflight' not in r.text
 assert effects(f)==before


@pytest.mark.parametrize('bad',['wrong_previous','same_previous','old_link','strip_previous','strip_both','old_approval','changed_reason'])
def test_independent_replacement_mode_cannot_downgrade_or_reuse_original_approval(replacement_case,bad):
 from test_case_resource_delivery import submit,effects
 from test_plan_source_reapproval import approved
 from test_resource_bundles import states
 x=replacement_case;f,p=x['f'],x['p'];hs,data=new_quote(x);item,_=approved(f,p,data);body={**data,'approval_id':item['id']};before=effects(f)
 if bad=='wrong_previous':body['expected_previous_plan_id']=str(uuid4())
 elif bad=='same_previous':body['expected_previous_plan_id']=x['new']['plan_id']
 elif bad=='old_link':body['expected_link_revision']=2
 elif bad=='strip_previous':body.pop('expected_previous_plan_id')
 elif bad=='strip_both':body.pop('expected_previous_plan_id');body.pop('expected_link_revision')
 elif bad=='old_approval':body['approval_id']=x['oldreceipt']['receipt']['plan_approval']['id']
 elif bad=='changed_reason':body['reason']='SYNTHETIC unapproved changed commit reason'
 r=submit(f,p,body);assert r.status_code in (409,422),r.text
 assert effects(f)==before and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('cap',['READ','EXECUTE','HOLD','PREPARE','authority_aba'])
def test_independent_new_approved_replacement_checks_live_authority_and_aba(replacement_case,cap):
 from test_plan_source_reapproval import approved
 from test_case_resource_delivery import submit,effects,recover
 from test_resource_bundles import states
 x=replacement_case;f,p=x['f'],x['p'];hs,data=new_quote(x);item,_=approved(f,p,data);before=effects(f)
 with f[1].connect() as c:
  f[1].lock_principal(c,'fixture-a',exclusive=True)
  if cap=='HOLD':c.execute("UPDATE synthetic_resource_grants SET active=false WHERE principal_id='fixture-a' AND capability='HOLD'")
  elif cap=='PREPARE':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id='fixture-a' AND capability='PREPARE'")
  elif cap=='authority_aba':c.execute("UPDATE capability_grants SET revision=revision+2 WHERE principal_id='fixture-a' AND capability='EXECUTE'")
  else:c.execute('UPDATE capability_grants SET active=false WHERE principal_id=%s AND capability=%s',('fixture-a',cap))
 r=submit(f,p,{**data,'approval_id':item['id']});assert r.status_code in (403,409),r.text
 assert effects(f)==before and states(f,hs)==['HELD']*3
 if cap=='READ':assert recover(f,p,x['oldreceipt']['delivery_binding']['request_key']).status_code==403


@pytest.mark.parametrize('table',['synthetic_resource_combination_receipts','resource_case_claims','case_resource_links'])
def test_independent_atomic_replacement_fault_rolls_back_new_effects_and_consumption(replacement_case,table):
 import psycopg
 from test_plan_source_reapproval import approved
 from test_case_resource_delivery import submit,effects
 from test_service_plan_approval import ledger
 from test_resource_bundles import states
 x=replacement_case;f,p=x['f'],x['p'];hs,data=new_quote(x);item,_=approved(f,p,data);before=effects(f);oldledger=deepcopy(ledger(f,p))
 with f[1].connect() as c:
  c.execute("CREATE FUNCTION replacement_independent_fault() RETURNS trigger LANGUAGE plpgsql AS $$BEGIN RAISE EXCEPTION 'synthetic replacement independent fault';END$$")
  c.execute('CREATE TRIGGER replacement_independent_fault BEFORE INSERT ON '+table+' FOR EACH ROW EXECUTE FUNCTION replacement_independent_fault()')
 with pytest.raises(psycopg.Error):submit(f,p,{**data,'approval_id':item['id']})
 assert effects(f)==before and ledger(f,p)==oldledger and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('fault',['withdraw_target','catalog_aba','plan_lock_later'])
def test_independent_new_approval_does_not_survive_later_source_or_plan_change(replacement_case,fault):
 from test_plan_source_reapproval import approved
 from test_case_resource_delivery import submit,effects
 from test_resource_bundles import states
 from parkweave import service_capability_catalog as cat
 x=replacement_case;f,p=x['f'],x['p'];hs,data=new_quote(x);item,_=approved(f,p,data);before=effects(f)
 if fault=='withdraw_target':
  with x['a']['catalog'].connection() as c:revision=cat.proof(cat.row(c,'park-a'))['revision']
  x['a']['catalog'].withdraw_release('park-a',uuid4().hex,x['newpairs'][1][0]['release_id'],revision,'SYNTHETIC explicit current selected coordination target withdrawal')
 elif fault=='catalog_aba':
  for _ in range(2):
   with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET namespace=namespace WHERE park_id='park-a' AND service_id='synthetic-material-preparation' AND version=1")
 else:
  from test_service_plan_manual_lock import lock
  r=lock(f,p,'P1');assert r.status_code==200,r.text
 r=submit(f,p,{**data,'approval_id':item['id']});assert r.status_code==409,r.text
 assert effects(f)==before and states(f,hs)==['HELD']*3


def test_independent_only_explicit_new_flag_enables_replacement_scope(replacement_case):
 from test_service_plan_approval import enable
 from test_case_resource_delivery import preview,effects
 from test_resource_bundles import bundle,states
 x=replacement_case;f,p=x['f'],x['p'];verified(f,p,'P1');hs,b=bundle(f);before=effects(f)
 enable(f,p,enabled_for_source_reapproval_tests=True)
 r=preview(f,p,{**b,'expected_link_revision':1,'expected_previous_plan_id':x['old']['id']})
 assert r.status_code==403,r.text
 assert effects(f)==before and states(f,hs)==['HELD']*3


@pytest.mark.parametrize('kind',['breaking_contract','unknown_registry'])
def test_independent_actual_saved_snapshots_finite_compare_rejects_unknown_or_breaking_contract(replacement_case,kind):
 """Pure contract fault probe over actual adopted snapshot, not a legal source mutation."""
 from parkweave import service_release_preflight as pf
 x=replacement_case;f,p=x['f'],x['p']
 with f[1].connect() as c:parent=c.execute('SELECT * FROM preparations WHERE id=%s',(p['preparation_id'],)).fetchone()
 record=sc.find(parent,x['new']['candidate_consumption']['candidate_id'])
 old,oi=x['oldpairs'][1];new,ni=deepcopy(x['newpairs'][1]);oldsource=x['checker']._historical_source(old);newsource=x['checker']._historical_source(new)
 frozen=deepcopy(record['frozen_registry'])
 if kind=='breaking_contract':new['resource_requirements']=[{'synthetic':'unsupported finite changed resource contract'}]
 else:frozen['steps'][0]['revision']+=1
 verdict=pf.compare_v1(parent['service_case_plan'],old,oi,new,ni,oldsource,newsource,frozen)
 assert verdict['classification']=='BREAKING_REJECTED'
 assert ('REGISTERED_SERVICE_CONTRACT_CHANGED' if kind=='breaking_contract' else 'REGISTERED_ACTION_PROFILE_CHANGED') in verdict['blocking_reasons']


def test_independent_later_explicit_owner_note_keeps_consumed_replacement_receipt_historical(replacement_case):
 from test_plan_source_reapproval import approved
 from test_case_resource_delivery import submit,recover,effects
 from test_service_plan_approval import ledger
 x=replacement_case;f,p=x['f'],x['p'];hs,data=new_quote(x);item,_=approved(f,p,data);key=uuid4().hex
 r=submit(f,p,{**data,'approval_id':item['id']},key);assert r.status_code==201,r.text
 receipt=deepcopy(r.json()['receipt']);oldledger=deepcopy(ledger(f,p));before=effects(f)
 path='/api/preparations/'+p['preparation_id']+'/plan-source-conflicts'
 read=f[3].get(path,headers=headers(f[2]));assert read.status_code==200,read.text
 body={**read.json()['action_requests']['EDIT_NOTE'],'text':'SYNTHETIC explicit owner coordination note after replacement approval consumption','reason':'SYNTHETIC original owner retains later manual content'}
 changed=f[3].post(path+'/commands',headers=headers(f[2],key=uuid4().hex),json=body);assert changed.status_code==200,changed.text
 cold=recover(f,p,key);assert cold.status_code==200,cold.text
 assert cold.json()['receipt']==receipt and cold.json()['independent_check']['status']=='NEEDS_RECHECK'
 assert effects(f)==before and ledger(f,p)==oldledger
