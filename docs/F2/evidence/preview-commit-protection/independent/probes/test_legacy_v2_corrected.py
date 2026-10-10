"""Own HTTP/PG/SQLite barriers, history provenance and scoped WAL observation."""
from pathlib import Path
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from queue import Queue
from uuid import UUID,uuid4
import importlib.util,sys,hashlib,json,sqlite3,time
import pytest
from psycopg.types.json import Jsonb
from conftest import pg,fixture
from test_isolated_execution_preview import preparation_fixture,setup,body,execute,read,snapshot
from test_new_enterprise_local_chain import actual_http
from test_service_plan_approval import enable
from test_catalog_approval_coordination import publish
from parkweave import isolated_execution_preview as ep,catalog_publication as catalogs
from parkweave.api import create_app
PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-preview-commit-protection-fixed-review')
@pytest.fixture
def actual(preparation_fixture):
 f=preparation_fixture
 with actual_http(create_app(f[0])) as (client,requests):yield f[:3]+(client,),requests

def note(name,record):(PRIVATE_EVIDENCE/(name+'-safe.json')).write_text(json.dumps(record,indent=2)+'\n')
def semantics(x):
 assert x['source_atomicity'] is False and x['source_consistency']=='COOPERATIVE_GUARDS_WITH_SNAPSHOT_COMPARISON'
 assert {row['source_state'] for row in x['history']} <= {'SNAPSHOT_MATCH','STALE'}

def test_late_reader_cannot_introduce_commit_wait(actual,tmp_path,monkeypatch):
 f,_=actual;p,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f);entered,release=Event(),Event();checks=[];guard=e._guard
 def last_guard(*args):
  guard(*args);checks.append(1)
  if len(checks)==3:entered.set();assert release.wait(8)
 monkeypatch.setattr(e,'_guard',last_guard)
 with ThreadPoolExecutor(1) as pool:
  future=pool.submit(execute,f,p,b)
  try:
   assert entered.wait(6)
   with sqlite3.connect(e.path,timeout=0) as reader:
    with pytest.raises(sqlite3.OperationalError,match='locked'):reader.execute('SELECT count(*) FROM previews').fetchone()
   assert not future.done()
  finally:release.set()
  r=future.result(15)
 assert r.status_code==201;semantics(r.json());assert r.json()['history'][0]['source_state']=='SNAPSHOT_MATCH' and snapshot(f)==before
 note('late-reader',dict(last_guard_passed=True,separate_late_reader_select='LOCKED',post=201,reader_cannot_insert_commit_wait=True,source_state='SNAPSHOT_MATCH',source_atomicity=False,formal_public_values_unchanged=True))

def test_reader_timeout_then_original_key_get_only_then_explicit_attempt(actual,tmp_path):
 f,requests=actual;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f)
 blocker=sqlite3.connect(e.path);blocker.execute('BEGIN');blocker.execute('SELECT count(*) FROM previews').fetchone();start=time.monotonic()
 try:r=execute(f,p,b,key)
 finally:blocker.rollback();blocker.close()
 elapsed=time.monotonic()-start;assert r.status_code==503 and elapsed>=2.8 and elapsed<8
 requests.clear();restored=read(f,p,key);assert restored.status_code==200 and restored.json()['status']=='NOT_OBSERVED' and {r['method'] for r in requests}=={'GET'}
 assert snapshot(f)==before
 r=execute(f,p,b,key);assert r.status_code==201;semantics(r.json());assert len(read(f,p).json()['history'])==1 and snapshot(f)==before
 note('reader-timeout',dict(timeout_http=503,wait_seconds=elapsed,recovery='NOT_OBSERVED',recovery_methods=['GET'],explicit_same_key_after_get=201,preview_rows=1,formal_public_values_unchanged=True))

@pytest.mark.parametrize('phase',['before_commit','after_commit'])
def test_failure_commit_boundary_get_recovers_exact_or_nothing(actual,tmp_path,monkeypatch,phase):
 f,requests=actual;p,e=setup(f,tmp_path);b=body(f,p);key=uuid4().hex;before=snapshot(f);calls=[];original=e._guard if phase=='before_commit' else ep.planning._proposal
 def fault(*args):
  value=original(*args);calls.append(1)
  if len(calls)==3:raise ep.Unavailable('SYNTHETIC independent bounded commit-stage fault')
  return value
 if phase=='before_commit':monkeypatch.setattr(e,'_guard',fault)
 else:monkeypatch.setattr(ep.planning,'_proposal',fault)
 assert execute(f,p,b,key).status_code==503
 with sqlite3.connect(e.path) as db:rows=db.execute('SELECT document,proof FROM previews').fetchall()
 if phase=='before_commit':monkeypatch.setattr(e,'_guard',original);assert rows==[]
 else:monkeypatch.setattr(ep.planning,'_proposal',original);assert len(rows)==1
 cold=ep.IsolatedExecutionPreview(f[0],e.root,enabled_for_synthetic_preview=True);cold.attach_store(f[0]);data=e.path.read_bytes();requests.clear();r=read(f,p,key);assert r.status_code==200;semantics(r.json())
 assert r.json()['status']==('NOT_OBSERVED' if phase=='before_commit' else 'COMMITTED')
 if phase=='after_commit':assert ep.prep.canonical(r.json()['result'])==rows[0][0]
 assert {r['method'] for r in requests}=={'GET'} and e.path.read_bytes()==data and snapshot(f)==before
 if phase=='before_commit':assert execute(f,p,b,key).status_code==201 and len(read(f,p).json()['history'])==1
 note('fault-'+phase,dict(http=503,persisted_rows_at_fault=len(rows),cold_recovery='NOT_OBSERVED' if phase=='before_commit' else 'COMMITTED',cold_methods=['GET'],exact_body_and_proof_retained=phase=='after_commit',explicit_retry_only=phase=='before_commit',formal_public_values_unchanged=True))

def test_noncooperative_change_at_actual_commit_return_is_snapshot_stale(actual,tmp_path,monkeypatch):
 f,_=actual;p,e=setup(f,tmp_path);b=body(f,p);before=snapshot(f);guard=e._guard;checks=[]
 def change_at_last_guard(*args):
  guard(*args);checks.append(1)
  if len(checks)==3:
   with f[1].connect() as c:c.execute("UPDATE preparation_catalog SET source=%s WHERE park_id='park-a' AND service_id=%s AND version=1",(Jsonb({'kind':'SYNTHETIC','id':'independent-late-source','revision':'2'}),ep.prep.SERVICE))
 monkeypatch.setattr(e,'_guard',change_at_last_guard);r=execute(f,p,b);assert r.status_code==201;semantics(r.json());assert r.json()['history'][0]['source_state']=='STALE' and r.json()['current_source_sha256']!=r.json()['result']['binding']['source_sha256']
 after=snapshot(f);assert {k:v for k,v in before.items() if k!='preparation_catalog'}=={k:v for k,v in after.items() if k!='preparation_catalog'}
 note('noncooperative-late-source',dict(owner_direct_source_change=True,post=201,source_state='STALE',source_atomicity=False,all_other_public_values_unchanged=True,not_atomic_all_sources=True))

def test_cooperative_catalog_writer_waits_until_failed_preview_rollback(actual,tmp_path,monkeypatch):
 f,_=actual;p,e=setup(f,tmp_path);bridge=enable(f,p);protocol=catalogs.IsolatedCatalogPublication(bridge,enabled_for_isolated_tests=True);b=body(f,p);before=snapshot(f);entered,release=Event(),Event();guards=[];guard=e._guard;pids=Queue();lock=catalogs.lock
 def final_fault(*args):
  guard(*args);guards.append(1)
  if len(guards)==3:entered.set();assert release.wait(8);raise ep.Unavailable('SYNTHETIC rollback after last guard')
 def observed_lock(c,key,exclusive=False):
  if exclusive:pids.put(c.execute('SELECT pg_backend_pid() pid').fetchone()['pid'])
  return lock(c,key,exclusive)
 monkeypatch.setattr(e,'_guard',final_fault);monkeypatch.setattr(catalogs,'lock',observed_lock)
 with ThreadPoolExecutor(2) as pool:
  preview=pool.submit(execute,f,p,b)
  try:
   assert entered.wait(6);writer=pool.submit(publish,protocol,p);pid=pids.get(timeout=5);until=time.monotonic()+4;waiting=False
   while time.monotonic()<until:
    with f[1].connect() as c:waiting=bool(c.execute("SELECT 1 FROM pg_locks WHERE pid=%s AND locktype='advisory' AND NOT granted",(pid,)).fetchone())
    if waiting:break
    time.sleep(.02)
   assert waiting and not writer.done()
  finally:release.set()
  r=preview.result(15);event=writer.result(15)
 assert r.status_code==503 and event['revision']==2
 with sqlite3.connect(e.path) as db:assert db.execute('SELECT count(*) FROM previews').fetchone()[0]==0
 after=snapshot(f);assert {k:v for k,v in before.items() if k!='preparation_catalog'}=={k:v for k,v in after.items() if k!='preparation_catalog'}
 note('cooperative-writer-rollback',dict(actual_pg_advisory_not_granted=True,publisher_waited_before_preview_rollback=True,preview=503,preview_rows=0,publish_revision_after_release=2,all_other_public_values_unchanged=True))

def test_real_legacy_5c25_created_v2_cold_read_without_migration(actual,tmp_path):
 f,requests=actual;p,unused=setup(f,tmp_path,goals=['LOCAL_CASE_RECORD_RECHECK','SYNTHETIC old full target'])
 path=PRIVATE_EVIDENCE/'legacy_5c25_isolated_execution_preview.py';name='parkweave._independent_legacy_5c25'
 spec=importlib.util.spec_from_file_location(name,path);legacy=importlib.util.module_from_spec(spec);sys.modules[name]=legacy;spec.loader.exec_module(legacy)
 assert legacy.VERSION==ep.VERSION==2 and legacy.EXECUTION_CONTRACT_SHA256==ep.EXECUTION_CONTRACT_SHA256
 old=legacy.IsolatedExecutionPreview(f[0],(tmp_path/'actual-legacy-v2').resolve(),enabled_for_synthetic_preview=True);old.attach_store(f[0]);before=snapshot(f);key=uuid4().hex;created=old.execute(f[0],f[2]['fixture-a'],UUID(p['preparation_id']),key,legacy.Execute(**body(f,p)));document=created['result']
 with sqlite3.connect(old.path) as db:row=db.execute('SELECT document,proof FROM previews').fetchone()
 data=old.path.read_bytes();cold=ep.IsolatedExecutionPreview(f[0],old.root,enabled_for_synthetic_preview=True);cold.attach_store(f[0]);requests.clear();restored=read(f,p,key);assert restored.status_code==200 and restored.json()['result']==document;semantics(restored.json());assert restored.json()['history'][0]['source_state']=='SNAPSHOT_MATCH'
 with sqlite3.connect(old.path) as db:assert db.execute('SELECT document,proof FROM previews').fetchone()==row
 assert old.path.read_bytes()==data and snapshot(f)==before and {r['method'] for r in requests}=={'GET'}
 note('legacy-5c25-cold-v2',dict(original_module_sha='5c25aa08c7ab499764bc2aa145dd932ee8a2a417',module_file_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),old_class_created_actual_sqlite_v2_artifact=True,same_current_owned_pg_fixture=True,execution_contract_hash_equal=True,old_document_and_independent_proof_exact=True,whole_sqlite_file_bytes_unchanged=True,no_migration_or_permissions_reissued=True,cold_key_recovery='COMMITTED',cold_network=['GET'],source_state='SNAPSHOT_MATCH',source_atomicity=False,formal_public_values_unchanged=True))

def test_wal_mode_observation_does_not_extend_rollback_reader_exclusion(actual,tmp_path,monkeypatch):
 f,_=actual;p,e=setup(f,tmp_path)
 with sqlite3.connect(e.path) as db:assert db.execute('PRAGMA journal_mode=WAL').fetchone()[0]=='wal'
 assert not (e.root/'preview.sqlite3-wal').exists() and not (e.root/'preview.sqlite3-shm').exists()
 before=snapshot(f);b=body(f,p);entered,release=Event(),Event();checks=[];guard=e._guard
 def pause(*args):
  guard(*args);checks.append(1)
  if len(checks)==3:entered.set();assert release.wait(8)
 monkeypatch.setattr(e,'_guard',pause)
 with ThreadPoolExecutor(1) as pool:
  future=pool.submit(execute,f,p,b);reader=None
  try:
   assert entered.wait(6);reader=sqlite3.connect(e.path,timeout=0);assert reader.execute('PRAGMA journal_mode').fetchone()[0]=='wal';reader.execute('BEGIN');old_count=reader.execute('SELECT count(*) FROM previews').fetchone()[0];assert old_count==0
   release.set();r=future.result(15);assert r.status_code==201 and reader.execute('SELECT count(*) FROM previews').fetchone()[0]==0
  finally:
   release.set()
   if reader:reader.rollback();reader.close()
 semantics(r.json());assert snapshot(f)==before
 note('wal-observation',dict(classification='BOUNDARY_OBSERVATION_NOT_ROLLBACK_MODE_ACCEPTANCE',private_owner_changed_only_journal_mode=True,wal_late_reader_select_allowed=True,wal_commit_not_blocked_by_reader=True,post=201,source_atomicity=False,formal_public_values_unchanged=True,rollback_mode_reader_exclusion_not_claimed_for_wal=True))
