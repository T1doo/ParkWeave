"""Independent relationship and failure oracles over original synthetic fixture."""
from pathlib import Path
from uuid import uuid4
import json,sqlite3
import pytest
from conftest import pg,fixture
from test_receipt_execution_preview import receipt_preview_fixture,access_fixture,receipt_fixture,preparation_fixture,body,execute,read,snapshot,p1_execute,p2_execute,p3_execute
from test_new_enterprise_local_chain import actual_http
from test_preparation import headers
from parkweave import receipt_execution_preview as p4,isolated_local_execution as local,executor_receipts as er,isolated_execution_preview as ep,preparation as prep
from parkweave.api import create_app
from parkweave.store import digest,Denied,Store
PRIVATE=Path('/workspace/ParkWeave/.runtime/independent-p4-receipt-execution-preview-review')
def note(name,data):(PRIVATE/(name+'-safe.json')).write_text(json.dumps(data,indent=2)+'\n')
@pytest.fixture
def actual(receipt_preview_fixture):
 f,p,p1,p2,p3,e,a=receipt_preview_fixture
 with actual_http(create_app(f[0])) as (client,requests):yield (f[:3]+(client,),p,p1,p2,p3,e,a),requests

def schema(f):
 with f[1].connect() as c:
  return {name:c.execute(query).fetchall() for name,query in dict(columns="SELECT table_name,column_name,data_type,is_nullable,column_default FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position",indexes="SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname",grants="SELECT grantee,table_name,privilege_type FROM information_schema.table_privileges WHERE table_schema='public' ORDER BY grantee,table_name,privilege_type").items()}

@pytest.mark.parametrize('decision',['ACKNOWLEDGE','REQUEST_CHANGES'])
def test_original_generate_submit_and_review_relationships_and_formal_schema(actual,monkeypatch,decision):
 (f,p,p1,p2,p3,e,a),requests=actual
 assert p1_execute(f,p).status_code==p2_execute(f,p).status_code==p3_execute(f,p).status_code==201
 old=[v.path.read_bytes() for v in (p1,p2,p3)];before=snapshot(f);columns=schema(f);calls=[];raw=[];generated=local.IsolatedLocalExecutor.generate;command=er.command
 def generate(adapter,store,c,row,parent):
  raw.append(c._raw);assert c._raw.execute('SHOW search_path').fetchone()['search_path']=='pg_temp'
  assert {r['relname'] for r in c._raw.execute("SELECT relname FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")}==set(p4.TABLES)
  indexes=c._raw.execute("SELECT indexdef FROM pg_indexes WHERE tablename='run_assignments' AND schemaname LIKE 'pg_temp_%'").fetchall();assert any('UNIQUE' in z['indexdef'] and '(principal_id, run_id)' in z['indexdef'] for z in indexes)
  for query in ('SELECT 1','SELECT * FROM public.service_step_receipts','COMMIT','SELECT * FROM principals'):
   with pytest.raises(Denied):c.execute(query)
  text,meta=generated(adapter,store,c,row,parent);assert text==prep.canonical(meta['report']);calls.append('generate');return text,meta
 def cmd(store,token,id,key,data):
  result=command(store,token,id,key,data);calls.append('SUBMIT' if type(data) is local.ExecuteLocal else data.action)
  return result
 monkeypatch.setattr(local.IsolatedLocalExecutor,'generate',generate);monkeypatch.setattr(er,'command',cmd)
 key=uuid4().hex;r=execute(f,p,body(f,p,decision),key);assert r.status_code==201;doc=r.json()['result'];art=doc['artifact'];assert calls==['generate','SUBMIT',decision] and all(c.closed for c in raw);monkeypatch.undo()
 receipt=art['p4_receipts'][0];step=art['p4_steps'][0];events=art['p4_events'];report=receipt['adapter_execution']['report'];b=report['binding']
 assert step['current_receipt_id']==receipt['id'] and step['id']==receipt['step_id']==b['step_id']==art['steps'][0]['id']==art['offers'][0]['receipt_step_id']
 assert receipt['source_sha256']==digest(receipt['text']) and receipt['text']==prep.canonical(report) and [x['action'] for x in events]==['CREATE','SUBMIT',decision]
 assert [x['revision'] for x in events]==[1,2,3] and [x['actor_id'] for x in events]==[art['executor_id'],art['executor_id'],art['p1']['owner_id']]
 assert b['case_id']==step['case_id']==art['p1']['case_id']!=p['case_id'] and b['run_id']==step['run_id']==art['p1']['run_id']!=p['run_id']
 assert b['offer_id']==art['offers'][0]['id'] and b['executor_id']==art['executor_id'] and isinstance(b['managed_access'],dict)
 assert [x['action'] for x in art['access_events']]==['REQUEST','APPROVE'] and len({report['execution_id']})==1
 assert report['checks']==['CURRENT_ACCEPTED_HANDOFF','CURRENT_PREPARATION_BINDING','CURRENT_MANAGED_EXECUTOR_LEASE'] and report['effect']=='LOCAL_SYNTHETIC_HANDOFF_REPORT_CREATED' and report['case_goal_completed'] is False
 assert step['state']==('LOCAL_ACKNOWLEDGED' if decision=='ACKNOWLEDGE' else 'CHANGES_REQUESTED') and art['local_current_at_execution'] is (decision=='ACKNOWLEDGE')
 assert doc['required_goals']==['LOCAL_CASE_RECORD_RECHECK','外部正式成果'] and doc['not_previewed']==['P5'] and doc['coverage_state']=='PARTIAL_PREVIEW' and not doc['case_goal_completed']
 assert len(art['outbox'])==4 and all(o['state']=='PENDING' and o['consumed_at'] is None for o in art['outbox']) and not art['notices']
 assert snapshot(f)==before and schema(f)==columns and [v.path.read_bytes() for v in (p1,p2,p3)]==old
 # Cold objects are rebuilt under the same actual process-issued bridge; only GET.
 data=e.path.read_bytes();s=Store(f[0].dsn);a[2].attach_store(s);f[0]._isolated_local_execution.attach_store(s);p4.ReceiptExecutionPreview(s,e.root,enabled_for_synthetic_preview=True).attach_store(s)
 with actual_http(create_app(s)) as (client,reads):
  q=client.get('/api/preparations/'+p['preparation_id']+'/receipt-execution-preview/recovery/'+key,headers=headers(f[2]));assert q.status_code==200 and q.json()['result']==doc and {z['method'] for z in reads}=={'GET'}
 assert e.path.read_bytes()==data and snapshot(f)==before and schema(f)==columns
 note('relations-'+decision,dict(actual_http=True,original_generate_submit_review_calls=calls,shadow_tables=28,shadow_unique_assignment_index=True,pg_temp_only=True,raw_connections_closed=True,report_receipt_events_binding=True,decision=decision,pending_outbox=4,notices=0,formal_business_values_and_schema_privileges_unchanged=True,previous_three_sqlite_bytes_unchanged=True,cold_same_issued_process_get_only=True,source_atomicity=False))

@pytest.mark.parametrize('target',['lease','access','report_checks','receipt_link'])
def test_single_document_rehash_preserves_independent_anchor(actual,target):
 (f,p,_,_,_,e,_),_=actual;key=uuid4().hex;assert execute(f,p,key=key).status_code==201;before=snapshot(f)
 with sqlite3.connect(e.path) as db:db.row_factory=sqlite3.Row;row=dict(db.execute('SELECT * FROM previews').fetchone())
 d=json.loads(row['document']);art=d['artifact']
 if target=='lease':art['p4_receipts'][0]['adapter_execution']['report']['binding']['managed_access']={}
 elif target=='access':art['access_events'][1]['action']='REQUEST'
 elif target=='report_checks':art['p4_receipts'][0]['adapter_execution']['report']['checks']=[]
 else:art['p4_steps'][0]['current_receipt_id']=str(uuid4())
 d['sha256']=ep._sha({k:v for k,v in d.items() if k!='sha256'})
 with sqlite3.connect(e.path) as db:
  db.execute('DROP TRIGGER immutable_update');db.execute('UPDATE previews SET document=?',(prep.canonical(d),));db.execute("CREATE TRIGGER immutable_update BEFORE UPDATE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END")
 assert read(f,p,key).status_code==read(f,p).status_code==409 and snapshot(f)==before
 with sqlite3.connect(e.path) as db:assert db.execute('SELECT proof,fingerprint FROM previews').fetchone()==(row['proof'],row['fingerprint'])
 note('body-'+target,dict(actual_http=True,single_document_recomputed_hash=True,independent_proof_and_request_fingerprint_retained=True,current_and_key_get=409,formal_business_unchanged=True))

@pytest.mark.parametrize('when',['generate','after_commit'])
def test_failure_commit_boundary_recovers_only_original_key(actual,monkeypatch,when):
 (f,p,_,_,_,e,_),_=actual;b=body(f,p);key=uuid4().hex;before=snapshot(f);calls=[];original=e.execute
 if when=='generate':
  def fail(*args,**kw):calls.append('generate_failure');raise ep.Unavailable('SYNTHETIC independent unavailable')
  monkeypatch.setattr(local.IsolatedLocalExecutor,'generate',fail)
 else:
  def fail(*args,**kw):result=original(*args,**kw);calls.append('committed');raise ep.Unavailable('SYNTHETIC independent lost reply')
  monkeypatch.setattr(e,'execute',fail)
 assert execute(f,p,b,key).status_code==503;monkeypatch.undo();data=e.path.read_bytes();requests=[]
 with actual_http(create_app(f[0])) as (client,requests):
  q=client.get('/api/preparations/'+p['preparation_id']+'/receipt-execution-preview/recovery/'+key,headers=headers(f[2]));assert q.status_code==200
  assert q.json()['status']==('NOT_OBSERVED' if when=='generate' else 'COMMITTED') and len(q.json()['history'])==(0 if when=='generate' else 1) and {x['method'] for x in requests}=={'GET'}
 assert e.path.read_bytes()==data and snapshot(f)==before
 note('failure-'+when,dict(actual_http=True,post=503,key_get=q.json()['status'],only_get_after_failure=True,formal_business_unchanged=True,saved_bytes_unchanged_by_get=True))

@pytest.mark.parametrize('gate',['proof','provider'])
def test_current_gate_cold_original_key_no_history_or_repair(actual,gate):
 (f,p,_,_,_,e,a),_=actual;key=uuid4().hex;assert execute(f,p,key=key).status_code==201;data=e.path.read_bytes();before=snapshot(f)
 if gate=='proof':a[2].proof=None
 else:f[0]._isolated_local_execution=None
 q=read(f,p,key);assert q.status_code==403 and 'result' not in q.json() and 'history' not in q.json() and e.path.read_bytes()==data and snapshot(f)==before
 note('cold-gate-'+gate,dict(actual_http=True,status=403,history_not_leaked=True,original_bytes_retained=True,no_proof_or_authority_reissue=True,formal_business_unchanged=True))
