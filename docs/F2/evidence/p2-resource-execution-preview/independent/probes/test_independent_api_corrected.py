"""Independent relational and boundary oracles through owned actual HTTP/PG."""
from pathlib import Path
from uuid import UUID,uuid4
from datetime import timedelta
import json,sqlite3
import pytest
from conftest import pg,fixture
from test_resource_execution_preview import preparation_fixture,setup,read,execute,body,snapshot
from test_isolated_execution_preview import execute as p1_execute
from test_new_enterprise_local_chain import actual_http
from test_preparation import headers
from parkweave import resource_execution_preview as rp,isolated_execution_preview as ep,resource_holds as rh,resource_combinations as rc,case_resources as cr,bounded_planning as planning
from parkweave.api import create_app
PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-p2-resource-execution-preview-review')
@pytest.fixture
def actual(preparation_fixture):
 f=preparation_fixture
 with actual_http(create_app(f[0])) as (client,requests):yield f[:3]+(client,),requests

def note(name,data):(PRIVATE_EVIDENCE/(name+'-safe.json')).write_text(json.dumps(data,indent=2)+'\n')

def test_independent_complete_relational_graph_and_closed_original_calls(actual,tmp_path,monkeypatch):
 f,requests=actual;p,p1,e=setup(f,tmp_path,goals=['LOCAL_CASE_RESOURCE_ASSOCIATION','SYNTHETIC separate mandatory goal']);assert p1_execute(f,p).status_code==201;old=p1.path.read_bytes();before=snapshot(f);calls=[];connections=[]
 for mod,name in [(rh,'preview'),(rh,'create'),(rc,'confirm'),(cr,'bind')]:
  orig=getattr(mod,name)
  def seen(store,*args,_orig=orig,_name=name,**kw):
   raw=store.connection._raw;connections.append(raw);assert raw.execute('SHOW search_path').fetchone()['search_path']=='pg_temp';calls.append(_name);return _orig(store,*args,**kw)
  monkeypatch.setattr(mod,name,seen)
 key=uuid4().hex;r=execute(f,p,key=key);assert r.status_code==201;d=r.json()['result'];a=d['artifact'];holds=a['holds'];gid=a['combination']['id'];link=a['links'][0];claim=a['claims'][0]
 assert calls==['preview','create','preview','create','confirm','bind'] and all(c.closed for c in connections)
 assert len(holds)==len(a['receipts'])==2 and all(h['state']=='CONFIRMED' and h['quantity']==1 for h in holds)
 assert {v['resource_id'] for v in holds}.isdisjoint({str(i) for i in rp.RESOURCES}) and len({v['resource_id'] for v in holds})==2
 assert {v['hold_id'] for v in a['receipts']}=={v['id'] for v in holds}
 assert {h['id'] for h in a['combination']['members']}=={h['id'] for h in holds} and all(h['combination_id']==gid for h in a['combination']['members']) and link['combination_id']==claim['combination_id']==gid
 assert link['case_id']==claim['case_id']==a['p1']['case_id']!=p['case_id'] and link['preparation_sha256']==a['p1']['snapshot_sha256']
 assert all(v['occupied_peak']==0 for v in a['prechecks']) and d['required_goals']==['LOCAL_CASE_RESOURCE_ASSOCIATION','SYNTHETIC separate mandatory goal'] and d['not_previewed']==['P3','P4','P5']
 assert d['state']=='SUCCEEDED' and d['formal_writes']==0 and snapshot(f)==before and p1.path.read_bytes()==old
 for hold in holds:
  rr=f[3].get('/api/synthetic-resources/'+hold['resource_id']+'/holds',headers=headers(f[2]));assert rr.status_code==403
 assert f[3].post('/api/preparations/'+p['preparation_id']+'/resource-link',headers=headers(f[2],key=uuid4().hex),json=dict(combination_id=gid,expected_preparation_revision=p['revision'],expected_link_revision=0,reason='SYNTHETIC independent consumption rejection')).status_code==403
 requests.clear();data=e.path.read_bytes();rp.ResourceExecutionPreview(f[0],e.root,enabled_for_synthetic_preview=True).attach_store(f[0]);cold=read(f,p,key);assert cold.json()['result']==d and {q['method'] for q in requests}=={'GET'} and e.path.read_bytes()==data and snapshot(f)==before
 note('relational-graph',dict(actual_http=True,real_original_command_sequence=calls,temp_connections_closed=True,fresh_resource_uuid_count=2,held_quantity=1,receipts_hold_ids_exact=True,combination_link_claim_join=True,p1_snapshot_anchor_matches=True,formal_uuid_consumption=403,old_p1_sqlite_bytes_unchanged=True,all_public_values_unchanged=True,original_key_cold_get_only=True,complete_goals_retained=2))

def test_literal_partial_failure_then_rule_repair_retains_failed_history(actual,tmp_path):
 f,_=actual;p,p1,e=setup(f,tmp_path);second=sorted(rp.RESOURCES,key=str)[1]
 with f[1].connect() as c:c.execute('UPDATE synthetic_resources SET enabled=false WHERE id=%s',(second,))
 before=snapshot(f);key=uuid4().hex;r=execute(f,p,key=key);assert r.status_code==201;failed=r.json()['result'];a=failed['artifact'];assert failed['state']=='FAILED' and a['p1']['state']=='LOCAL_CONFIRMED' and a['p2_state']=='FAILED'
 assert len(a['holds'])==len(a['receipts'])==1 and a['holds'][0]['state']=='HELD' and a['combination'] is None and a['links']==a['claims']==a['combination_receipts']==[] and snapshot(f)==before
 with f[1].connect() as c:c.execute("UPDATE synthetic_resources SET enabled=true,revision=revision+1,source=jsonb_set(source,'{revision}','\"independent-2\"') WHERE id=%s",(second,))
 before=snapshot(f);fixed=execute(f,p).json()['result'];assert fixed['state']=='SUCCEEDED' and read(f,p,key).json()['result']==failed and read(f,p).json()['history'][0]['source_state']=='STALE' and snapshot(f)==before
 note('literal-partial-repair',dict(actual_http=True,first_attempt='FAILED',actual_retained_partial_holds=1,partial_receipts=1,combination_link_claim_absent=True,explicit_rule_repair=True,new_attempt='SUCCEEDED',old_failed_body_exact=True,old_source_state='STALE',all_public_values_unchanged_by_preview=True))

@pytest.mark.parametrize('mutation',['goal','p1','link','precheck','state'])
def test_single_document_rehash_http_cannot_replace_independent_artifact_proof(actual,tmp_path,mutation):
 f,_=actual;p,_,e=setup(f,tmp_path);key=uuid4().hex;assert execute(f,p,key=key).status_code==201;before=snapshot(f)
 with sqlite3.connect(e.path) as db:row=dict(zip([z[0] for z in db.execute('SELECT * FROM previews').description],db.execute('SELECT * FROM previews').fetchone()))
 doc=json.loads(row['document'])
 if mutation=='goal':doc['required_goals']=[]
 elif mutation=='p1':doc['artifact']['p1']['events']=[]
 elif mutation=='link':doc['artifact']['links'][0]['case_id']=str(uuid4())
 elif mutation=='precheck':doc['artifact']['prechecks'][0]['occupied_peak']=99
 else:doc['state']='FAILED'
 doc['sha256']=ep._sha({k:v for k,v in doc.items() if k!='sha256'})
 with sqlite3.connect(e.path) as db:
  db.execute('DROP TRIGGER immutable_update');db.execute('UPDATE previews SET document=?',(ep.prep.canonical(doc),));db.execute("CREATE TRIGGER immutable_update BEFORE UPDATE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END")
 assert read(f,p).status_code==read(f,p,key).status_code==409 and snapshot(f)==before
 with sqlite3.connect(e.path) as db:assert db.execute('SELECT proof,fingerprint FROM previews').fetchone()==(row['proof'],row['fingerprint'])
 note('single-body-'+mutation,dict(actual_http=True,single_document_changed_with_recomputed_sha=True,independent_proof_and_request_fingerprint_unchanged=True,current_and_original_key_get=409,all_public_values_unchanged=True))

@pytest.mark.parametrize('action_field',['path','role','commands'])
def test_independent_action_registration_closed_and_original_history_still_readable(actual,tmp_path,monkeypatch,action_field):
 f,_=actual;p,_,e=setup(f,tmp_path);key=uuid4().hex;old=execute(f,p,key=key).json()['result'];before=snapshot(f)
 change={'path':'/api/not-the-original-binding','role':'unregistered-role','commands':['UNKNOWN']}[action_field];action={**rp.P2_ACTIONS[0],action_field:change};monkeypatch.setitem(planning.ACTIONS,'P2',[action]);view=read(f,p);assert view.status_code==200 and view.json()['execution_available'] is False
 assert execute(f,p).status_code==409 and read(f,p,key).json()['result']==old and read(f,p,key).json()['history'][0]['source_state']=='STALE' and snapshot(f)==before
 note('registered-'+action_field,dict(actual_http=True,only_registered_action_field_changed=action_field,execution_available=False,new_attempt=409,old_history_body_exact=True,source_state='STALE',all_public_values_unchanged=True))
