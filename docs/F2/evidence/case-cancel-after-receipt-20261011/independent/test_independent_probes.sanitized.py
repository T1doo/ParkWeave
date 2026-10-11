"""Independent reconciliation counterexamples, with an owned isolated fixture."""
import importlib.util,json,os,subprocess,shutil
from pathlib import Path
from uuid import UUID,uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave import case_cancellation_reconciliation as cr,preparation as prep
from parkweave.store import Store,digest
from test_preparation import preparation_fixture,headers,command as material,create as create_material
from test_executor_receipts import receipt_fixture,act
from test_case_resources import link_fixture,group,post as bind
from test_service_dispatches import offer,command as decide
from test_pending_receipt_handoff import body_for,post as handoff
from test_case_cancellation_before_receipt import accepted,generation
from test_case_lifecycle import built,read as local_read,act as local_act
from test_resource_combinations import cancel
import test_case_cancellation_reconciliation as new
import test_case_cancellation as old

ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/case-cancel-after-receipt/independent-review'
spec=importlib.util.spec_from_file_location('_case_cancel_reconciliation_independent_conftest',ROOT/'tests/conftest.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
pg=base.pg
fixture=base.fixture

def observe(name,data):
 target=OUT/os.environ['PARKWEAVE_INDEPENDENT_OBSERVATION_STAGE'];target.mkdir(exist_ok=True)
 path=target/(name+'.json')
 if path.exists():raise RuntimeError('refuse to overwrite original observation '+name)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+'\n')

@pytest.mark.parametrize('action',['ACKNOWLEDGE','REQUEST_CHANGES','REOPEN'])
@pytest.mark.parametrize('damage',['actor','fingerprint','typed_payload'])
def test_enterprise_receipt_decision_exact_proof(receipt_fixture,action,damage):
 f=receipt_fixture;p,d,row=new.submitted(f)
 r=act(f,row,action);assert r.status_code==200,r.text
 with f[1].connect() as c:
  e=c.execute('SELECT * FROM service_receipt_events WHERE action=%s',(action,)).fetchone()
  if damage=='actor':c.execute("UPDATE service_receipt_events SET actor_id='executor-a' WHERE id=%s",(e['id'],))
  elif damage=='fingerprint':c.execute("UPDATE service_receipt_events SET fingerprint=repeat('0',64) WHERE id=%s",(e['id'],))
  else:
   payload=e['payload'];payload['revision']=float(payload['revision'])
   c.execute('UPDATE service_receipt_events SET payload=%s WHERE id=%s',(Jsonb(payload),e['id']))
 before=old.snapshot(f);preview=new.get(f,p);assert preview.status_code==200,preview.text
 result=new.post(f,p)
 observe('decision-'+action+'-'+damage,{'blockers':preview.json()['blockers'],'can_request':preview.json()['can_request'],'post_status':result.status_code})
 assert not preview.json()['can_request'] and result.status_code==409
 assert old.snapshot(f)==before

def test_latest_unresolved_assessment_cannot_finalize_earlier_known_receipt(receipt_fixture):
 f=receipt_fixture;p,d,row=new.submitted(f)
 assert new.post(f,p).status_code==200
 known=new.post(f,p,new.body(f,p,'RECONCILE'));assert known.status_code==200,known.text
 known_id=known.json()['event_id'];assert new.get(f,p).json()['can_confirm']
 unresolved=new.post(f,p,new.body(f,p,'RECONCILE','UNRESOLVED'));assert unresolved.status_code==200,unresolved.text
 x=new.get(f,p).json();assert x['case_state']=='RECONCILING' and not x['can_confirm']
 data=new.body(f,p,'CONFIRM_CANCEL');data['reconciliation_event_id']=known_id
 before=old.snapshot(f);r=new.post(f,p,data)
 observe('latest-assessment-required',{'prior_known_event_id':known_id,'latest_event_id':x['reconciliation_event_id'],'can_confirm':x['can_confirm'],'stale_known_confirm_status':r.status_code})
 assert r.status_code==409 and old.snapshot(f)==before

def test_combined_handoff_material_and_multiple_receipt_versions(receipt_fixture):
 f=receipt_fixture;p,d=accepted(f);f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
 r=handoff(f,d,body_for(f,p,d));assert r.status_code==201,r.text
 r=decide(f,r.json(),'ACCEPT',user='unassigned');assert r.status_code==200,r.text;d=r.json()
 row=act(f,generation(f,d,'unassigned'),'SUBMIT',user='unassigned');assert row.status_code==200,row.text
 row=act(f,row.json(),'REQUEST_CHANGES');assert row.status_code==200,row.text
 row=act(f,row.json(),'SUBMIT',user='unassigned',text='SYNTHETIC independent second version');assert row.status_code==200,row.text
 p=material(f,p,'REOPEN',reason='SYNTHETIC independent new material').json()
 p=material(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC review').json()
 p=material(f,p,'CONFIRM',reason='SYNTHETIC confirm').json()
 pending=offer(f,p,revision=d['revision'],recovery_receipt_step_id=d['receipt_step_id'],executor='unassigned')[0]
 assert pending.status_code==201,pending.text
 r=decide(f,pending.json(),'ACCEPT',user='unassigned');assert r.status_code==200,r.text;d=r.json()
 row=act(f,generation(f,d,'unassigned'),'SUBMIT',user='unassigned');assert row.status_code==200,row.text
 x=new.get(f,p).json();assert x['can_request'] and len(x['receipts'])==3,x
 assert len(x['source']['immutable_source']['manual_lineage']['steps'])==3
 before=old.snapshot(f);keys=[]
 for action in cr.ACTIONS:
  data=new.body(f,p,action);key=uuid4().hex
  if action=='RECONCILE':
   assert len(data['receipts'])==3
   bad={**data,'receipts':data['receipts'][1:]};assert new.post(f,p,bad).status_code==409
  r=new.post(f,p,data,key);assert r.status_code==200,r.text;keys.append((key,data,r.json()['event']))
 after=old.snapshot(f)
 assert all(before[t]==after[t] for t in before if t not in ('cases','case_local_lifecycles','case_local_events'))
 for key,data,event in keys:
  cold=cr.recover(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']),key)
  assert cold['event']==event and cold['current']['case_state']=='CANCELLED'
 observe('combined-generations',{'receipt_count':len(x['receipts']),'step_count':3,'original_keys_recovered':len(keys),'final_state':new.get(f,p).json()['case_state']})

def test_independent_resource_release_preserves_historical_request_recovery(link_fixture):
 f=link_fixture;p,d,row=new.submitted(f);g=group(f);assert bind(f,p,g).status_code==201
 data=new.body(f,p);key=uuid4().hex;r=new.post(f,p,data,key);assert r.status_code==200,r.text
 before=old.snapshot(f);released=cancel(f,g['id']);assert released.status_code==200,released.text
 recovered=new.recover(f,p,key);assert recovered.status_code==200,recovered.text
 assert recovered.json()['event']==r.json()['event'] and recovered.json()['current']['case_state']=='RECONCILING'
 assert new.post(f,p,data,key).json()['event']==r.json()['event']
 with f[1].connect() as c:
  rows=c.execute('SELECT state FROM synthetic_resource_holds WHERE id=ANY(%s)',([UUID(x['id']) for x in g['members']],)).fetchall()
  assert rows and all(x['state']=='RELEASED' for x in rows)
 after=old.snapshot(f)
 assert before['cases']==after['cases'] and before['case_local_events']==after['case_local_events']
 observe('resource-release-and-recovery',{'release_status':released.status_code,'recovery_status':recovered.status_code,'state':recovered.json()['current']['case_state']})

@pytest.mark.parametrize('damage',['actor','fingerprint','payload_revision','snapshot_identity'])
def test_prior_revalidate_original_event_proof_cannot_be_fabricated(link_fixture,damage):
 f=link_fixture;p,g,d,row=built(f)
 result=local_act(f,p,local_read(f,p).json(),'REVALIDATE');assert result.status_code==200,result.text
 with f[1].connect() as c:
  e=c.execute("SELECT * FROM case_local_events WHERE action='REVALIDATE'").fetchone()
  if damage=='actor':c.execute("UPDATE case_local_events SET actor_id='executor-a' WHERE id=%s",(e['id'],))
  elif damage=='fingerprint':c.execute("UPDATE case_local_events SET fingerprint=repeat('0',64) WHERE id=%s",(e['id'],))
  elif damage=='payload_revision':
   payload=e['payload'];payload['revision']=float(payload['revision']);c.execute('UPDATE case_local_events SET payload=%s WHERE id=%s',(Jsonb(payload),e['id']))
  else:
   snap=e['snapshot'];snap['case_id']=str(uuid4());c.execute('UPDATE case_local_events SET snapshot=%s WHERE id=%s',(Jsonb(snap),e['id']))
 before=old.snapshot(f);preview=new.get(f,p);assert preview.status_code==200,preview.text
 result=new.post(f,p);observe('prefix-'+damage,{'blockers':preview.json()['blockers'],'can_request':preview.json()['can_request'],'post_status':result.status_code})
 assert not preview.json()['can_request'] and result.status_code==409 and old.snapshot(f)==before

@pytest.mark.parametrize('field',['case_id','preparation_id','owner_id'])
def test_bad_manual_source_does_not_export_unknown_scope_receipt_text(receipt_fixture,field):
 f=receipt_fixture;p,d,row=new.submitted(f);marker='SYNTHETIC independent inaccessible foreign receipt marker'
 other=None
 if field!='owner_id':other=create_material(f,user='fixture-b')[0]
 with f[1].connect() as c:
  c.execute('UPDATE service_step_receipts SET text=%s,source_sha256=%s',(marker,digest(marker)))
  if field=='owner_id':c.execute("UPDATE service_receipt_steps SET owner_id='fixture-b'")
  else:
   c.execute('UPDATE service_receipt_steps SET '+field+'=%s',(other[field],))
 before=old.snapshot(f);x=new.get(f,p);assert x.status_code==200,x.text
 result=new.post(f,p)
 observe('bad-scope-'+field,{'can_request':x.json()['can_request'],'blockers':x.json()['blockers'],'body_marker_exported':marker in x.text,'post_status':result.status_code})
 assert not x.json()['can_request'] and marker not in x.text and result.status_code==409 and old.snapshot(f)==before

@pytest.mark.parametrize('mode',['eight_handles','ninth_corrupt_set','future_handle','terminal_old_request','known_is_not_confirmation'])
def test_independent_opaque_ui_and_explicit_phase(mode):
 node=shutil.which('node');assert node
 r=subprocess.run([node,str(OUT/'independent_reconciliation_ui.js'),mode],cwd=ROOT,text=True,capture_output=True,timeout=15)
 observe('ui-'+mode,{'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'browser_attempts':0})
 assert r.returncode==0,r.stderr
 data=json.loads(r.stdout);assert data['mode']==mode and data['checks']>0 and data['browser_attempts']==0
