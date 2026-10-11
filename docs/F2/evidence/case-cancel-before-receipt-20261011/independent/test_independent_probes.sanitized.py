"""Independent counterexamples in a fresh owned fixture; no original test edits."""
import importlib.util,json,os
from pathlib import Path
from uuid import UUID,uuid4
import pytest
from psycopg.types.json import Jsonb
from parkweave.store import Store,digest
from test_preparation import preparation_fixture,headers,command as material
from test_executor_receipts import receipt_fixture,ready
from test_service_dispatches import offer,command as decide
from test_pending_receipt_handoff import body_for,post as reassign
from test_worker_gateway import runtime,auth,worker,enqueue,oracle
import test_case_cancellation_before_receipt as new
import test_case_cancellation as old

ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/case-cancel-before-receipt/independent-review'
spec=importlib.util.spec_from_file_location('_case_cancel_independent_original_conftest',ROOT/'tests/conftest.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
pg=base.pg
fixture=base.fixture

def observe(name,data):
 stage=os.environ.get('PARKWEAVE_INDEPENDENT_OBSERVATION_STAGE')
 target=OUT/stage if stage else OUT
 target.mkdir(exist_ok=True)
 (target/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str)+'\n')

@pytest.mark.parametrize('kind',['handoff','new_material'])
def test_stripped_later_accept_and_create_extras_cannot_become_initial_proof(receipt_fixture,kind):
 f=receipt_fixture;p,d=new.accepted(f)
 if kind=='handoff':
  f[1].assign_status('unassigned',UUID(p['run_id']),active=True)
  pending=reassign(f,d,body_for(f,p,d));assert pending.status_code==201,pending.text
  result=decide(f,pending.json(),'ACCEPT');assert result.status_code==200,result.text;d=result.json()
 else:
  original=d['receipt_step_id'];p=material(f,p,'REOPEN',reason='SYNTHETIC independent new material').json()
  p=material(f,p,'REVIEW','prep-specialist-fixture-a',reason='SYNTHETIC review').json()
  p=material(f,p,'CONFIRM',reason='SYNTHETIC confirm').json()
  pending=offer(f,p,revision=d['revision'],recovery_receipt_step_id=original)[0];assert pending.status_code==201,pending.text
  result=decide(f,pending.json(),'ACCEPT');assert result.status_code==200,result.text;d=result.json()
 accept_base={'dispatch_id','offer_id','receipt_step_id','revision','action','state','actor_id','executor_id','reason'}
 create_base={'step_id','revision','state','action','actor_id','scope','dispatch_id','offer_id','reason'}
 with f[1].connect() as c:
  a=c.execute("SELECT id,payload FROM service_dispatch_events WHERE offer_id=%s AND action='ACCEPT'",(d['current_offer']['id'],)).fetchone()
  b=c.execute("SELECT id,payload FROM service_receipt_events WHERE step_id=%s AND action='CREATE'",(d['receipt_step_id'],)).fetchone()
  offered=c.execute("SELECT payload FROM service_dispatch_events WHERE offer_id=%s AND action='REOFFER'",(d['current_offer']['id'],)).fetchone()
  assert a['payload'].keys()-accept_base and b['payload'].keys()-create_base and offered
  c.execute('UPDATE service_dispatch_events SET payload=%s WHERE id=%s',(Jsonb({k:v for k,v in a['payload'].items() if k in accept_base}),a['id']))
  c.execute('UPDATE service_receipt_events SET payload=%s WHERE id=%s',(Jsonb({k:v for k,v in b['payload'].items() if k in create_base}),b['id']))
 before=old.snapshot(f);preview=new.get(f,p);assert preview.status_code==200,preview.text
 cancelled=new.post(f,p)
 observe('stripped-'+kind,{'preview_can_cancel':preview.json()['can_cancel'],'blockers':preview.json()['blockers'],'post_status':cancelled.status_code,'post_result':cancelled.json(),'original_offered_payload':offered['payload']})
 assert (preview.json()['can_cancel'],cancelled.status_code)==(False,409)
 assert old.snapshot(f)==before


def test_receipt_row_without_submit_event_or_current_pointer_refuses(receipt_fixture):
 f=receipt_fixture;p,d=new.accepted(f);text='SYNTHETIC independent historical receipt'
 with f[1].connect() as c:
  c.execute("INSERT INTO service_step_receipts(id,step_id,version,text,source_kind,source_label,source_sha256,actor_id) VALUES(%s,%s,1,%s,'SYNTHETIC','SYNTHETIC isolated corruption probe',%s,'executor-a')",(uuid4(),d['receipt_step_id'],text,digest(text)))
 before=old.snapshot(f);x=new.get(f,p).json();assert 'HISTORICAL_RECEIPT_SUBMISSION_NOT_SUPPORTED' in x['blockers']
 assert new.post(f,p).status_code==409 and old.snapshot(f)==before

@pytest.mark.parametrize('action',['SUBMIT','ACKNOWLEDGE','REQUEST_CHANGES','REOPEN'])
def test_historical_noncreate_event_refuses_even_without_receipt_row(receipt_fixture,action):
 f=receipt_fixture;p,d=new.accepted(f)
 with f[1].connect() as c:
  c.execute("INSERT INTO service_receipt_events(id,step_id,actor_id,request_key,fingerprint,revision,action,payload) VALUES(%s,%s,'executor-a',%s,repeat('0',64),2,%s,'{}')",(uuid4(),d['receipt_step_id'],uuid4().hex,action))
 before=old.snapshot(f);x=new.get(f,p).json();assert 'HISTORICAL_RECEIPT_SUBMISSION_NOT_SUPPORTED' in x['blockers']
 assert new.post(f,p).status_code==409 and old.snapshot(f)==before


def test_original_accept_post_key_cannot_replay_business_after_cancel(receipt_fixture):
 f=receipt_fixture;p=ready(f);offered=offer(f,p)[0].json();key=uuid4().hex
 accepted=decide(f,offered,'ACCEPT',key=key);assert accepted.status_code==200,accepted.text
 assert new.post(f,p).status_code==200
 before=old.snapshot(f);r=decide(f,offered,'ACCEPT',key=key)
 assert r.status_code==409 and 'Case cancelled' in r.text and old.snapshot(f)==before


def test_inactive_managed_origin_is_rejected_by_plain_cold_store(receipt_fixture):
 f=receipt_fixture;p,d=new.accepted(f)
 with f[1].connect() as c:
  c.execute('ALTER TABLE run_assignments ADD COLUMN managed_access jsonb')
  c.execute("UPDATE run_assignments SET active=false,managed_access='{}' WHERE run_id=%s",(p['run_id'],))
 before=old.snapshot(f);x=new.cr.read(Store(f[0].dsn),f[2]['fixture-a'],UUID(p['preparation_id']))
 assert not x['can_cancel'] and 'ISOLATED_RUN_ACCESS_NOT_SUPPORTED' in x['blockers']
 assert new.post(f,p).status_code==409 and old.snapshot(f)==before

@pytest.mark.parametrize('user',['fixture-b','fixture-c'])
def test_cross_scope_worker_result_with_persistent_state_observation(runtime,user):
 api,owner,tokens,env=runtime;run=enqueue(runtime,'case.create')
 with owner.connect() as c:
  c.execute('INSERT INTO run_assignments VALUES(%s,%s,%s,%s,true)',(user,run,'park-a','org-a'))
 assert api.get('/api/runs/'+run,headers=auth(tokens,user)).status_code==403
 assert api.post('/api/runs/'+run+'/cancel',headers=auth(tokens,user)).status_code==403
 result=worker(runtime)
 with owner.connect() as c:
  count=c.execute('SELECT count(*) n FROM cases').fetchone()['n']
 data={'user':user,'worker_returncode':result.returncode,'worker_stdout':result.stdout,'worker_stderr':result.stderr,'persistent_run_operation':oracle(owner,run),'case_count':count}
 observe('cross-scope-worker-'+user,data)
 assert count==1,data
