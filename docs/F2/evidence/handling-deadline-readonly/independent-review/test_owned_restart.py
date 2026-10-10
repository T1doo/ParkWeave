"""Dedicated independent PG and actual fresh API PID; no shared fixture restart."""
from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
import os,json,socket,subprocess,sys,time
import pytest,psycopg,httpx
from playwright.sync_api import sync_playwright
import conftest
from parkweave import case_fact_clarifications as facts
from parkweave.process_env import minimal_environment
from test_preparation import preparation_fixture,filled,headers
from test_deadline_independent import attach,snapshot,get,open_page
from test_new_enterprise_local_chain import actual_http
from parkweave.api import create_app

OUT=Path('/workspace/ParkWeave/.runtime/independent-handling-deadline-review/restart')
@pytest.fixture
def own_restart_fixture(tmp_path):
    import pgserver
    data=tmp_path/'independent-deadline-owned-pg';server=pgserver.get_server(data,cleanup_mode='stop')
    server._case_fact_fixture_cluster=facts.capture_fixture_cluster(server.get_uri(),data.resolve())
    with psycopg.connect(server.get_uri(),autocommit=True) as c:c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
    generator=conftest.fixture.__wrapped__(server,None)
    try:
        f=preparation_fixture.__wrapped__(next(generator));yield f,server
    finally:
        generator.close();server.cleanup();assert not (data/'postmaster.pid').exists()

def test_independent_own_pg_restart_invalidates_old_registry_new_pid_unknown(own_restart_fixture):
    from pgserver._commands import pg_ctl
    f,server=own_restart_fixture;p=filled(f);registry=attach(f,p);original=snapshot(f)
    with f[1].connect() as c:before=facts._migration_identity(c)
    old_pid=server.get_pid()
    with actual_http(create_app(f[0])) as (client,requests):
        hf=(f[0],f[1],f[2],client);assert get(hf,p).json()['state']=='SYNTHETIC_CALCULATED'
        pg_ctl(['-w','-m','fast','stop'],pgdata=server.pgdata,user=server.system_user,timeout=10,env=minimal_environment(os.environ));assert not (server.pgdata/'postmaster.pid').exists()
        server.ensure_postgres_running()
        with f[1].connect() as c:after=facts._migration_identity(c)
        assert server.get_pid()!=old_pid and after['postmaster_start']!=before['postmaster_start']
        assert all(before[k]==after[k] for k in ('system_identifier','database_oid','database_name','data_directory','owner_name'))
        denied=get(hf,p);assert denied.status_code==403 and 'independent-source' not in denied.text
    assert snapshot(f)==original and registry.pid==os.getpid()
    with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'actual-api.log').open('w') as output:
        proc=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--log-level','warning','--no-access-log'],env=minimal_environment(os.environ,PARKWEAVE_DSN=f[0].dsn,PARKWEAVE_MODE='LOCAL',PYTHONDONTWRITEBYTECODE='1'),stdout=output,stderr=subprocess.STDOUT)
        try:
            base='http://127.0.0.1:'+str(port)
            with httpx.Client(base_url=base,timeout=5) as api:
                end=time.monotonic()+10
                while time.monotonic()<end:
                    try:
                        health=api.get('/health')
                        if health.status_code==200:break
                    except httpx.HTTPError:pass
                    assert proc.poll() is None;time.sleep(.02)
                else:pytest.fail('owned new API readiness deadline')
                assert health.json()['process_id']==proc.pid and proc.pid!=os.getpid()
                path='/api/preparations/'+p['preparation_id']+'/handling-deadline';x=api.get(path,headers=headers(f[2]));assert x.status_code==200 and x.json()['issues']==['DEADLINE_SOURCE_DISABLED'] and x.json()['deadline_utc'] is None
                assert api.get(path,headers=headers(f[2],'fixture-b')).status_code==403
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox']);ctx=browser.new_context(viewport={'width':320,'height':1000});page=ctx.new_page();methods=[];page.on('request',lambda r:methods.append(r.method))
                try:
                    page.goto(base);assert page.locator('#token').input_value()=='';page.locator('#token').fill(f[2]['fixture-a']);page.locator('#token').dispatch_event('change');page.locator('[data-tab="collaboration"]').click();page.evaluate('(id)=>loadPreparation(id,{role:"enterprise_operator"})',p['preparation_id']);page.wait_for_function('()=>preparationView!==null');page.locator('#handling-deadline-read').click();page.wait_for_function('()=>deadlineView?.state==="UNKNOWN"')
                    assert page.evaluate('deadlineView.deadline_utc===null&&localStorage.length===0') and 'PRIVATE_ORACLE_CLOCK' not in page.content() and set(methods)=={'GET'}
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth');page.screenshot(path=str(OUT/'cold-default-320.png'),full_page=True)
                finally:ctx.close();browser.close()
            assert snapshot(f)==original
            (OUT/'restart-evidence.json').write_text(json.dumps(dict(actual_pg_restart=True,old_pg_pid=old_pid,new_pg_pid=server.get_pid(),postmaster_start_changed=True,system_identifier_and_database_oid_unchanged=True,old_registry_http_status=403,new_api_pid=proc.pid,new_api_default_unknown=True,cold_chromium_get_only=True,business_and_permissions_rows_unchanged=True,fixture_capability_not_reissued=True),indent=2)+'\n')
        finally:
            proc.terminate()
            try:proc.wait(10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(5);raise
