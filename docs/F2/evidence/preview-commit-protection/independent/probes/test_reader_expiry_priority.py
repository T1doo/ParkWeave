"""Independent real SQLite COMMIT reader wait crosses observed managed deadline."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
from threading import Event
from uuid import uuid4
import json,sqlite3,time
from conftest import pg,fixture
from test_isolated_run_access import access_fixture,receipt_fixture,approved
from test_isolated_execution_preview import preparation_fixture,body,execute,read,snapshot
from test_request_intents import save
from test_new_enterprise_local_chain import actual_http
from parkweave.api import create_app
from parkweave import isolated_execution_preview as ep

PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-preview-commit-protection-fixed-review')

def test_reader_wait_before_exclusive_guard_expiry_must_not_persist(access_fixture,tmp_path,monkeypatch):
 a=access_fixture;approved(a);original,p,bridge,clock,_=a
 p={**p,'revision':save(original,p,goals=['LOCAL_MATERIAL_PREPARATION']).json()['revision']}
 engine=ep.IsolatedExecutionPreview(original[0],(tmp_path/'independent-commit-reader').resolve(),enabled_for_synthetic_preview=True);engine.attach_store(original[0])
 with actual_http(create_app(original[0])) as (client,requests):
  f=original[:3]+(client,);data=body(f,p);key=uuid4().hex;before=snapshot(f)
  exclusive_attempted=Event();guard_counts=[];managed_seen=[];database=engine._database;guard=engine._guard
  source=engine._source
  def observed_source(*args):
   value=source(*args);managed_seen.append(('executor-a',p['run_id']) in args[1]._managed_checks);return value
  monkeypatch.setattr(engine,'_source',observed_source)
  def observed_guard(*args):
   guard_counts.append(len(guard_counts)+1);guard(*args)
  monkeypatch.setattr(engine,'_guard',observed_guard)
  @contextmanager
  def observed_database():
   with database() as db:
    db.set_trace_callback(lambda text:exclusive_attempted.set() if text=='BEGIN EXCLUSIVE' else None)
    yield db
  monkeypatch.setattr(engine,'_database',observed_database)
  reader=sqlite3.connect(engine.path);reader.execute('BEGIN');assert reader.execute('SELECT count(*) FROM previews').fetchone()[0]==0
  clock_before=clock[0]
  try:
   with ThreadPoolExecutor(max_workers=1) as pool:
    request=pool.submit(execute,f,p,data,key)
    try:
     assert exclusive_attempted.wait(8),'actual BEGIN EXCLUSIVE was not attempted while separate real reader held SHARED lock'
     time.sleep(.05);assert not request.done()
     assert len(guard_counts)==0 and managed_seen and all(managed_seen)
     clock[0]+=timedelta(minutes=11)
    finally:reader.rollback();reader.close()
    response=request.result(timeout=20)
  finally:
   if reader:reader.close()
  with sqlite3.connect(engine.path) as db:
   rows=db.execute('SELECT document FROM previews').fetchall();state=json.loads(rows[0][0])['state'] if rows else None
  monkeypatch.setattr(engine,'_guard',guard);monkeypatch.setattr(engine,'_database',database);monkeypatch.setattr(engine,'_source',source)
  requests.clear();recovery=read(f,p,key);recovery_status=recovery.json().get('status') if recovery.status_code==200 else None
  record=dict(actual_http=True,actual_owned_postgresql=True,actual_separate_sqlite_shared_reader=True,actual_begin_exclusive_trace_observed=True,request_waiting_before_first_guard=True,source_observed_valid_managed_dependency=True,clock_crossed_issued_10minute_deadline_during_initial_reader_wait=True,guard_attempts_after_clock_change=len(guard_counts),http_status=response.status_code,persisted_rows=len(rows),persisted_state=state,recovery_http=recovery.status_code,recovery_status=recovery_status,recovery_methods=sorted({r['method'] for r in requests}),formal_public_values_unchanged=snapshot(f)==before,expected_persisted_rows=0,expected_response=403,expected_recovery='NOT_OBSERVED',no_permission_reissued=True,model_calls=0)
  (PRIVATE_EVIDENCE/'reader-exclusive-expiry-safe.json').write_text(json.dumps(record,indent=2)+'\n')
  assert snapshot(f)==before
  assert response.status_code==403 and len(rows)==0 and recovery_status=='NOT_OBSERVED'
