"""Owned Linux synthetic lifecycle oracle; no proof exists in the restart phase."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

import httpx
import psutil
import psycopg
import playwright
from psycopg.conninfo import make_conninfo
from parkweave.process_env import minimal_environment
from parkweave.store import Store

REPO=Path(__file__).resolve().parents[1]


def child_environment(**overrides):
    # Explicit source and installed package paths; never inherited PYTHONPATH.
    sites=list(dict.fromkeys(str(Path(m.__file__).resolve().parent.parent)
                             for m in (psycopg,psutil,playwright)))
    return minimal_environment(os.environ,PYTHONPATH=os.pathsep.join(
        [str(REPO/'src'),str(REPO/'tests'),*sites]),**overrides)


def snapshot(owner):
    """Canonical logical bytes, including current identities; exclude denial audit."""
    with owner.connect() as c:
        c.execute('SET TRANSACTION READ ONLY')
        names=[r['tablename'] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename<>'authorization_audit' ORDER BY tablename").fetchall()]
        result={}
        for name in names:
            rows=c.execute(psycopg.sql.SQL('SELECT row_to_json(x) AS row FROM {} x').format(psycopg.sql.Identifier(name))).fetchall()
            logical=sorted(json.dumps(r['row'],sort_keys=True,ensure_ascii=False,default=str) for r in rows)
            result[name]=hashlib.sha256(json.dumps(logical,ensure_ascii=False).encode()).hexdigest()
        return result


def wait(predicate,seconds=15):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        value=predicate()
        if value:return value
        time.sleep(.05)
    raise AssertionError('bounded owned lifecycle observation timed out')


def stop(child):
    if child.poll() is None:child.terminate()
    child.wait(10)  # No escalation or unknown process cleanup.


def run_phase(root,phase):
    assert sys.platform=='linux' and phase in ('initial','restart')
    assert ctypes.CDLL(None,use_errno=True).prctl(36,1,0,0,0)==0
    root=Path(root).resolve();out=root/phase;out.mkdir(mode=0o700)
    seen={os.getpid():{'pid':os.getpid(),'created':psutil.Process().create_time(),'name':'phase-issuer' if phase=='initial' else 'new-phase'}}
    watching=threading.Event()
    def watch():
        while not watching.wait(.02):
            for p in psutil.Process().children(recursive=True):
                try:seen[p.pid]={'pid':p.pid,'created':p.create_time(),'name':p.name()}
                except psutil.NoSuchProcess:pass
    thread=threading.Thread(target=watch);thread.start()
    server=None;api=None;worker=None;log=None
    note={'phase':phase,'actual_linux':True,'migrate_calls':0,'seed_calls':0,'proof_transport':False}
    try:
        import pgserver
        data=root/'data';server=pgserver.get_server(data,cleanup_mode='stop')
        note['pg_pid']=int((data/'postmaster.pid').read_text().splitlines()[0])
        if phase=='initial':
            from parkweave.case_fact_clarifications import capture_fixture_cluster
            cluster=capture_fixture_cluster(server.get_uri(),data)
            with psycopg.connect(server.get_uri(),autocommit=True) as c:
                c.execute('CREATE DATABASE parkweave')
                c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
            owner=Store(make_conninfo(server.get_uri(),dbname='parkweave'))
            with owner.connect() as c:owner._case_fact_fixture_receipt=cluster.record_created_database(c)
            owner.migrate();note['migrate_calls']=1
            with owner.connect() as c:c.execute((REPO/'src/parkweave/roles.sql').read_text())
            env=child_environment(PARKWEAVE_DSN=owner.dsn)
            subprocess.run([sys.executable,'-m','parkweave.cli','seed-synthetic'],cwd=root,env=env,check=True,stdout=subprocess.DEVNULL,timeout=10)
            note['seed_calls']=1
        else:
            owner=Store(make_conninfo(server.get_uri(),dbname='parkweave'))
            from parkweave import case_fact_clarifications as facts
            assert len(facts._fixture_clusters)==len(facts._fixture_databases)==0
            note['fixture_registry_empty']=True
        session_path=root/'.runtime/synthetic-sessions.json';tokens=json.loads(session_path.read_text())
        note['session_file_sha256']=hashlib.sha256(session_path.read_bytes()).hexdigest()
        note['sessions_mode']=oct(session_path.stat().st_mode&0o777)
        with owner.connect() as c:
            note['database']=c.execute('SELECT (pg_control_system()).system_identifier::text AS system_identifier,(SELECT oid FROM pg_database WHERE datname=current_database()) AS oid,pg_postmaster_start_time()::text AS started').fetchone()
        with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        env=child_environment(PARKWEAVE_DSN=make_conninfo(owner.dsn,user='parkweave_app'),PARKWEAVE_MODE='LOCAL')
        log=(out/'service-private.log').open('w')
        api=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port)],env=env,cwd=REPO,stdout=log,stderr=log)
        note['api_pid']=api.pid
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=3) as client:
            def healthy():
                assert api.poll() is None
                try:
                    r=client.get('/health')
                    return r.status_code==200 and r.json()['process_id']==api.pid and r.json()['schema']==28
                except httpx.TransportError:return False
            wait(healthy)
            worker=subprocess.Popen([sys.executable,'-m','parkweave.worker'],env=env,cwd=REPO,stdout=log,stderr=log)
            note['worker_pid']=worker.pid
            auth={'Authorization':'Bearer '+tokens['fixture-a']}
            if phase=='initial':
                r=client.post('/api/runs',headers={**auth,'Idempotency-Key':'SYNTHETIC-original-create'},json={'goal':'SYNTHETIC normal lifecycle original case'})
                assert r.status_code==202,r.text;run_id=r.json()['run_id']
                def completed():
                    assert worker.poll() is None
                    x=client.get('/api/runs/'+run_id,headers=auth).json()
                    return x if x.get('state')=='SUCCEEDED' else False
                original=wait(completed)
                def drained():
                    with owner.connect() as c:
                        return c.execute("SELECT NOT EXISTS(SELECT 1 FROM outbox WHERE consumed_at IS NULL) AND NOT EXISTS(SELECT 1 FROM dispatch_notice_outbox WHERE state='PENDING') AS done").fetchone()['done']
                wait(drained)
                (root/'original-private.json').write_text(json.dumps({'run_id':run_id,'view':original}))
            else:
                original_data=json.loads((root/'original-private.json').read_text());run_id=original_data['run_id'];original=original_data['view']
            before=snapshot(owner)
            r=client.get('/api/runs',headers=auth);assert r.status_code==200,r.text;directory=r.json()
            assert len(directory['items'])==1 and directory['items'][0]['run_id']==run_id
            read=client.get('/api/runs/'+run_id,headers=auth);assert read.status_code==200 and read.json()==original
            assert original['case']['state']=='NEEDS_INPUT' and original['success_scope']=='LOCAL_CASE_CREATED'
            assert original['case']['external_acceptance']=='NOT_SUBMITTED' and original['case']['offline_fulfillment']=='NO_EVIDENCE'
            note['directory_get_status']=r.status_code;note['run_get_status']=read.status_code
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox'])
                try:
                    widths=[390] if phase=='initial' else [320,390,1200]
                    note['viewports']=widths;requests=[];errors=[];responses=[]
                    for width in widths:
                        context=browser.new_context(viewport={'width':width,'height':1000});page=context.new_page()
                        page.on('pageerror',lambda e:errors.append(str(e)))
                        page.on('request',lambda r:requests.append({'method':r.method,'path':r.url.split(str(port),1)[-1]}))
                        page.on('response',lambda r:responses.append({'status':r.status,'path':r.url.split(str(port),1)[-1]}))
                        try:
                            page.goto(f'http://127.0.0.1:{port}/');assert page.locator('#token').input_value()==''
                            page.locator('#token').fill(tokens['fixture-a']);page.locator('[data-tab="collaboration"]').click()
                            page.locator('#record-directory-read').click();page.locator('#record-directory-items button').wait_for()
                            page.locator('#record-directory-items button').click()
                            page.locator('details.engineering-record > summary').click()
                            try:wait(lambda:'LOCAL_CASE_CREATED' in page.locator('#result').inner_text())
                            except AssertionError:
                                (out/'page-failure-private.json').write_text(json.dumps({'result':page.locator('#result').inner_text(),'feedback':page.locator('#page-feedback').inner_text(),'directory_status':page.locator('#record-directory-status').inner_text(),'errors':errors,'requests':requests,'responses':responses},ensure_ascii=False,indent=2))
                                raise
                            assert json.loads(page.locator('#result').inner_text())==original
                            assert page.locator('#record-directory-items').inner_text()==''
                            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                            assert page.evaluate('Object.keys(localStorage).length===0&&Object.keys(sessionStorage).length===0')
                            page.locator('.collaboration-controls').screenshot(path=str(out/f'cold-record-{width}.png'))
                        finally:context.close()
                    assert not errors and all(x['method']=='GET' for x in requests)
                    note['page_requests_only_get']=True;note['page_errors']=errors
                finally:browser.close()
            for user in ['fixture-b','fixture-c']:
                h={'Authorization':'Bearer '+tokens[user]}
                assert client.get('/api/runs',headers=h).json()['items']==[]
                assert client.get('/api/runs/'+run_id,headers=h).status_code==403
            # P4/P5 proof paths remain disabled on this ordinary cold Store/API.
            from uuid import uuid4
            for path in ['receipt-execution-history','lifecycle-execution-preview']:
                assert client.get('/api/preparations/'+str(uuid4())+'/'+path,headers=auth).status_code==403
            note['business_permissions_logical_hashes']=snapshot(owner)
            assert note['business_permissions_logical_hashes']==before
            with owner.connect() as c:note['denial_audit_count']=c.execute('SELECT count(*) n FROM authorization_audit').fetchone()['n']
            note['normal_worker_alive']=worker.poll() is None
            note['original_view_sha256']=hashlib.sha256(json.dumps(original,sort_keys=True).encode()).hexdigest()
            note['decision']='PASS'
    finally:
        if worker is not None:stop(worker)
        if api is not None:stop(api)
        if log is not None:log.close()
        if server is not None:server.cleanup()
        watching.set();thread.join(3)
        assert not thread.is_alive()
        while True:
            try:
                pid,_=os.waitpid(-1,os.WNOHANG)
                if not pid:break
            except ChildProcessError:break
        (out/'owned-instances-private.json').write_text(json.dumps(list(seen.values()),indent=2))
        (out/'phase-safe.json').write_text(json.dumps(note,indent=2)+'\n')


if __name__=='__main__':run_phase(sys.argv[1],sys.argv[2])
