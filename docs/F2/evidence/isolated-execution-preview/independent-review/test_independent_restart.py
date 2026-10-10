"""Actual owned PG stop/start and different API processes, original GET only."""
from pathlib import Path
from contextlib import contextmanager
import os,socket,subprocess,sys,tempfile,time,json
import pytest,psycopg,httpx
from playwright.sync_api import sync_playwright
import conftest
from parkweave import case_fact_clarifications as facts
from parkweave.api import create_app
from parkweave.process_env import minimal_environment
from test_preparation import preparation_fixture,headers
from test_isolated_execution_preview import setup,snapshot
from test_isolated_execution_preview_browser import open_page,lost,recovered

PRIVATE_EVIDENCE=Path('/workspace/ParkWeave/.runtime/independent-isolated-execution-preview-v2-review')
@pytest.fixture
def independent_cluster(tmp_path):
 import pgserver
 data=tmp_path/'independent-own-restart-pg'/'data';data.parent.mkdir(mode=0o700)
 pg=pgserver.get_server(data,cleanup_mode='stop');pg._case_fact_fixture_cluster=facts.capture_fixture_cluster(pg.get_uri(),data.resolve())
 with psycopg.connect(pg.get_uri(),autocommit=True) as c:c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
 generator=conftest.fixture.__wrapped__(pg,None)
 try:yield preparation_fixture.__wrapped__(next(generator)),pg
 finally:
  generator.close();pg.cleanup();assert not (data/'postmaster.pid').exists()

def test_owned_actual_pg_and_api_restart_keeps_old_complete_proof_get_only(independent_cluster,tmp_path):
 f,pg=independent_cluster;p,e=setup(f,tmp_path,goals=['LOCAL_CASE_RECORD_RECHECK','SYNTHETIC original restart target'])
 factory=tmp_path/'independent_preview_factory.py';factory.write_text('import os\nfrom parkweave.api import create_app\nfrom parkweave.store import Store\nfrom parkweave.isolated_execution_preview import IsolatedExecutionPreview\ndef app():\n s=Store(os.environ["PARKWEAVE_DSN"])\n IsolatedExecutionPreview(s,os.environ["PARKWEAVE_PREVIEW_ROOT"],enabled_for_synthetic_preview=True).attach_store(s)\n return create_app(s)\n')
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 base=f'http://127.0.0.1:{port}';env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_PREVIEW_ROOT=str(e.root),PYTHONPATH=os.pathsep.join([str(tmp_path),str(Path.cwd()/'src')]),PYTHONDONTWRITEBYTECODE='1')
 active=None;pids=[]
 def identity():
  with f[1].connect() as c:return c.execute("SELECT current_database() name,oid::text oid,(SELECT system_identifier::text FROM pg_control_system()) system_identifier,pg_postmaster_start_time() started FROM pg_database WHERE datname=current_database()").fetchone()
 with (PRIVATE_EVIDENCE/'independent-owned-restart-api.log').open('w') as log:
  def start(default=False):
   target='parkweave.api:configured_app' if default else 'independent_preview_factory:app'
   proc=subprocess.Popen([sys.executable,'-m','uvicorn',target,'--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],env=env,stdout=log,stderr=log);pids.append(proc.pid);deadline=time.monotonic()+12
   with httpx.Client(timeout=.5) as client:
    while proc.poll() is None and time.monotonic()<deadline:
     try:
      r=client.get(base+'/health')
      if r.status_code==200 and r.json()['process_id']==proc.pid:return proc
     except httpx.HTTPError:pass
     time.sleep(.05)
   if proc.poll() is None:proc.terminate();proc.wait(5)
   raise AssertionError('independent owned API startup deadline')
  try:
   active=start()
   with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);context=browser.new_context();page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(type(e).__name__))
    try:
     page.goto(base);open_page(page,f,p);storage,post=lost(page,f,p);original=post['result'];before=snapshot(f);bytes_before=e.path.read_bytes();old_identity=identity();old_pg_pid=pg.get_pid()
     active.terminate();active.wait(5);active=None
     from pgserver._commands import pg_ctl
     pg_ctl(['-w','-m','fast','stop'],pgdata=pg.pgdata,user=pg.system_user,timeout=10,env=minimal_environment(os.environ));assert not (pg.pgdata/'postmaster.pid').exists();pg.ensure_postgres_running()
     new_identity=identity();assert pg.get_pid()!=old_pg_pid and old_identity['started']!=new_identity['started']
     assert all(old_identity[k]==new_identity[k] for k in ('name','oid','system_identifier')) and snapshot(f)==before and e.path.read_bytes()==bytes_before
     active=start(default=True)
     endpoint=base+'/api/preparations/'+p['preparation_id']+'/execution-preview'
     with httpx.Client() as client:
      assert client.get(endpoint,headers=headers(f[2])).status_code==403
      assert client.post(endpoint,headers=headers(f[2],key=post['key']),json=post['body']).status_code==403
     active.terminate();active.wait(5);active=None
     active=start();assert len(set(pids))==3
     requests=[];page.on('request',lambda r:requests.append(r.method));page.reload();open_page(page,f,p);recovered(page)
     assert page.evaluate('executionPreviewView.result')==original and page.evaluate('executionPreviewView.history[0].source_state')=='CURRENT'
     assert set(requests)=={'GET'} and page.evaluate('JSON.stringify({...localStorage})')==storage and snapshot(f)==before and e.path.read_bytes()==bytes_before and not errors
     (PRIVATE_EVIDENCE/'owned-pg-api-restart-safe.json').write_text(json.dumps(dict(api_pids=pids,old_pg_pid=old_pg_pid,new_pg_pid=pg.get_pid(),postmaster_start_changed=True,system_identifier_and_database_oid_retained=True,explicit_same_namespace_v2_configuration=True,default_new_process_get_and_post=403,original_key_cold_page_get_only=True,artifact_and_complete_goal_proof_unchanged=True,sqlite_bytes_unchanged=True,formal_public_values_unchanged=True,no_permission_reissued=True,model_calls=0),indent=2)+'\n')
    finally:context.close();browser.close()
  finally:
   if active is not None and active.poll() is None:active.terminate();active.wait(5)
