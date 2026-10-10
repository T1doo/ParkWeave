"""Original synthetic qualification is fixture setup; no preview-time repair."""
from pathlib import Path
from uuid import uuid4
import json,sqlite3
import pytest
from conftest import pg,fixture
from test_dispatch_execution_preview import receipt_fixture,preparation_fixture,setup,read,execute,body,snapshot,p1_execute,p2_execute
from test_new_enterprise_local_chain import actual_http
from test_preparation import headers
from parkweave import dispatch_execution_preview as dp,isolated_execution_preview as ep,service_dispatches as sd,dispatch_notices as notices,preparation as prep
from parkweave.api import create_app
from parkweave.store import digest
PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-p3-dispatch-execution-preview-review')
@pytest.fixture
def actual(receipt_fixture):
 f=receipt_fixture
 with actual_http(create_app(f[0])) as (client,requests):yield f[:3]+(client,),requests

def note(name,data):(PRIVATE_EVIDENCE/(name+'-safe.json')).write_text(json.dumps(data,indent=2)+'\n')

@pytest.mark.parametrize('decision',['ACCEPT','DECLINE'])
def test_independent_offer_decision_actor_outbox_and_step_relations(actual,tmp_path,monkeypatch,decision):
 f,requests=actual;p,p1,p2,e=setup(f,tmp_path);assert p1_execute(f,p).status_code==p2_execute(f,p).status_code==201;old1=p1.path.read_bytes();old2=p2.path.read_bytes();before=snapshot(f);calls=[];connections=[];token_actors=[]
 for module,name in [(sd,'offer'),(sd,'command'),(notices,'enqueue')]:
  original=getattr(module,name)
  def observed(*args,_name=name,_original=original,**kw):
   proxy=args[0] if _name=='enqueue' else args[0].connection;c=proxy._raw;connections.append(c);assert c.execute('SHOW search_path').fetchone()['search_path']=='pg_temp'
   assert {v['relname'] for v in c.execute("SELECT relname FROM pg_class WHERE relnamespace=pg_my_temp_schema() AND relkind='r'")}==set(dp.TABLES)
   if _name!='enqueue':token_actors.append(c.execute('SELECT id FROM principals WHERE token_hash=%s',(digest(args[1]),)).fetchone()['id'])
   calls.append(_name);return _original(*args,**kw)
  monkeypatch.setattr(module,name,observed)
 key=uuid4().hex;r=execute(f,p,body(f,p,decision),key);assert r.status_code==201;d=r.json()['result'];a=d['artifact'];assert calls==['offer','enqueue','command','enqueue'];assert all(c.closed for c in connections);monkeypatch.undo()
 events=a['dispatch_events'];offer=a['offers'][0];owner=a['p1']['owner_id'];reviewer=a['p1']['reviewer_id'];executor=a['executor_id']
 assert token_actors==[reviewer,executor] and [z['action'] for z in events]==['OFFER',decision] and [z['revision'] for z in events]==[1,2]
 assert [z['actor_id'] for z in events]==[reviewer,executor] and all(z['dispatch_id']==offer['dispatch_id'] and z['offer_id']==offer['id'] for z in events)
 assert offer['executor_id']==executor and offer['state']==('ACCEPTED' if decision=='ACCEPT' else 'DECLINED') and a['p3_state']==offer['state']
 expected={(events[0]['id'],owner),(events[0]['id'],executor),(events[1]['id'],owner),(events[1]['id'],reviewer)};assert {(o['event_id'],o['recipient_id']) for o in a['outbox']}==expected and len(a['outbox'])==4
 assert all(o['state']=='PENDING' and o['consumed_at'] is None for o in a['outbox']) and a['notices']==[]
 if decision=='ACCEPT':
  step=a['steps'][0];created=a['receipt_events'][0];assert len(a['steps'])==len(a['receipt_events'])==1 and step['state']=='AWAITING_RECEIPT' and step['current_receipt_id'] is None
  assert step['id']==offer['receipt_step_id']==created['step_id'] and step['case_id']==a['p1']['case_id']!=p['case_id'] and step['run_id']==a['p1']['run_id']!=p['run_id']
  assert step['executor_id']==created['actor_id']==executor and created['action']=='CREATE'
 else:assert a['steps']==a['receipt_events']==[] and offer['receipt_step_id'] is None and d['coverage_state']=='PARTIAL_PREVIEW'
 assert d['required_goals']==['LOCAL_CASE_RECORD_RECHECK','外部正式成果'] and d['not_previewed']==['P4','P5'] and d['state']=='SUCCEEDED' and d['formal_writes']==0 and not d['new_grants'] and not d['case_goal_completed']
 assert snapshot(f)==before and p1.path.read_bytes()==old1 and p2.path.read_bytes()==old2
 assert f[3].get('/api/service-dispatches/'+offer['dispatch_id'],headers=headers(f[2])).status_code==403
 data=e.path.read_bytes();dp.DispatchExecutionPreview(f[0],e.root,enabled_for_synthetic_preview=True).attach_store(f[0]);requests.clear();cold=read(f,p,key);assert cold.json()['result']==d and {z['method'] for z in requests}=={'GET'} and e.path.read_bytes()==data and snapshot(f)==before
 note('relational-'+decision.lower(),dict(actual_http=True,actual_original_calls=calls,pg_temp_tables=27,connections_closed=True,offer_uses_simulated_reviewer_token=True,decision_uses_simulated_executor_own_token=True,event_revisions=[1,2],outbox_exact_recipient_pairs=4,outbox_state='PENDING',outbox_not_consumed=True,receipt_steps=1 if decision=='ACCEPT' else 0,current_receipt_absent=True,decision_state=offer['state'],full_goals_retained=2,not_executed=['P4','P5'],all_public_values_unchanged=True,p1_and_p2_sqlite_bytes_unchanged=True,formal_dispatch_uuid_read=403,cold_original_key_get_only=True,fixture_qualification_before_preview_only=True))

def test_original_shadow_owner_token_material_add_after_offer_refuses_accept_without_rotation(actual,tmp_path,monkeypatch):
 f,_=actual;p,_,_,e=setup(f,tmp_path);before=snapshot(f);generated=[];original_tokens=dp.secrets.token_urlsafe;original_offer=sd.offer
 def capture(*args,**kw):
  token=original_tokens(*args,**kw);generated.append(token);return token
 def change(store,token,id,key,data):
  offered=original_offer(store,token,id,key,data);c=store.connection._raw;row=c.execute('SELECT owner_id FROM preparations WHERE id=%s',(id,)).fetchone();hashed=c.execute('SELECT token_hash FROM principals WHERE id=%s',(row['owner_id'],)).fetchone()['token_hash']
  owner_token=next(t for t in generated if digest(t)==hashed)
  prep.command(store,owner_token,id,uuid4().hex,prep.PreparationCommand(action='ADD_EVIDENCE',expected_revision=offered['preparation_revision'],slot='need_summary',text='SYNTHETIC independent original-command material version2',source_kind='USER_STATEMENT',source_label='SYNTHETIC original-owner v2'))
  return offered
 monkeypatch.setattr(dp.secrets,'token_urlsafe',capture);monkeypatch.setattr(sd,'offer',change);key=uuid4().hex;r=execute(f,p,key=key);assert r.status_code==201;d=r.json()['result'];a=d['artifact']
 assert d['state']=='FAILED' and a['p3_state']=='FAILED' and [x['action'] for x in a['dispatch_events']]==['OFFER'] and a['offers'][0]['state']=='OFFERED'
 assert a['steps']==a['receipt_events']==[] and len(a['outbox'])==2 and all(x['state']=='PENDING' for x in a['outbox']) and not a['notices'] and snapshot(f)==before
 monkeypatch.undo();new=execute(f,p).json()['result'];assert new['artifact']['p3_state']=='ACCEPTED' and read(f,p,key).json()['result']==d and snapshot(f)==before
 note('material-after-offer',dict(actual_http=True,original_ADD_EVIDENCE_with_original_generated_shadow_owner_token=True,token_rotation=False,new_grants_or_assignment_repair=False,old_state='FAILED',actual_offer_retained=True,accept_not_created=True,receipt_steps=0,outbox_pending=2,explicit_new_attempt='ACCEPTED',old_failed_body_exact=True,all_public_values_unchanged=True,plaintext_tokens_not_recorded=True))

@pytest.mark.parametrize('mutation',['decision','actor','outbox','goals','receipt'])
def test_single_body_rehash_actual_http_refuses_tampered_p3_proof(actual,tmp_path,mutation):
 f,_=actual;p,_,_,e=setup(f,tmp_path);key=uuid4().hex;assert execute(f,p,key=key).status_code==201;before=snapshot(f)
 with sqlite3.connect(e.path) as db:db.row_factory=sqlite3.Row;row=dict(db.execute('SELECT * FROM previews').fetchone())
 d=json.loads(row['document'])
 if mutation=='decision':d['decision']='DECLINE'
 elif mutation=='actor':d['artifact']['dispatch_events'][1]['actor_id']=d['artifact']['p1']['reviewer_id']
 elif mutation=='outbox':d['artifact']['outbox'][0]['state']='DELIVERED'
 elif mutation=='goals':d['required_goals']=[]
 else:d['artifact']['steps'][0]['current_receipt_id']=str(uuid4())
 d['sha256']=ep._sha({k:v for k,v in d.items() if k!='sha256'})
 with sqlite3.connect(e.path) as db:
  db.execute('DROP TRIGGER immutable_update');db.execute('UPDATE previews SET document=?',(prep.canonical(d),));db.execute("CREATE TRIGGER immutable_update BEFORE UPDATE ON previews BEGIN SELECT RAISE(ABORT,'immutable preview'); END")
 assert read(f,p).status_code==read(f,p,key).status_code==409 and snapshot(f)==before
 with sqlite3.connect(e.path) as db:assert db.execute('SELECT proof,fingerprint FROM previews').fetchone()==(row['proof'],row['fingerprint'])
 note('single-body-'+mutation,dict(actual_http=True,body_only_changed_with_recomputed_hash=True,independent_proof_and_original_request_anchor_unchanged=True,current_and_original_key_get=409,all_public_values_unchanged=True))

@pytest.mark.parametrize('party',['reviewer','executor'])
def test_original_current_participant_qualification_before_saved_artifact(actual,tmp_path,party):
 f,_=actual;p,_,_,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;assert execute(f,p,b,key).status_code==201
 with f[1].connect() as c:
  who='prep-specialist-fixture-a' if party=='reviewer' else 'executor-a';f[1].lock_principal(c,who,exclusive=True)
  if party=='reviewer':c.execute("UPDATE preparation_grants SET active=false WHERE principal_id=%s AND capability='REVIEW_ASSIGNED'",(who,))
  else:c.execute('UPDATE run_assignments SET active=false WHERE principal_id=%s AND run_id=%s',(who,p['run_id']))
 before=snapshot(f);stored=e.path.read_bytes();assert read(f,p,key).status_code==execute(f,p,b,key).status_code==403 and e.path.read_bytes()==stored and snapshot(f)==before
 note('qualification-'+party,dict(actual_http=True,existing_original_qualification_revoked_only=True,current_and_replay=403,original_saved_bytes_retained=True,no_grant_or_assignment_repair=True,all_public_values_unchanged_by_preview=True))
