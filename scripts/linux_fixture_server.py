from parkweave.process_env import minimal_environment
"""Opt-in Linux test harness; never a Windows installer or production launcher."""
from pathlib import Path
import json
import argparse
import os
import signal
import subprocess
import sys
import time
import pgserver
import tempfile
import shutil
from contextlib import contextmanager
import psycopg
from psycopg.conninfo import make_conninfo
from parkweave.store import Store, Denied

REPO=Path(__file__).resolve().parents[1]


class DemoStopUnconfirmed(RuntimeError):
    pass


def stop_children(children):
    """Try every exact child even if an earlier stop cannot be confirmed."""
    failures=[]
    for child in children:
        try:
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill();child.wait(timeout=5)
        except (OSError,subprocess.TimeoutExpired,KeyboardInterrupt):
            try:stopped=child.poll() is not None
            except OSError:stopped=False
            if not stopped:failures.append(child.pid)
    if failures:
        raise DemoStopUnconfirmed('Owned demo child stop unconfirmed; private temporary directory retained')


@contextmanager
def demo_database(fresh=False):
    """A fresh temporary demo is issued real in-process creation evidence.

    Existing persistent state is never renamed, reset or retroactively given
    creation evidence. Only an already schema-25/26 demo may use the old path.
    """
    if sys.platform != "linux":raise Denied("Linux synthetic demo only; Windows installed adapter remains blocked")
    base=Path(tempfile.mkdtemp(prefix="parkweave-demo-")) if fresh else None
    root=base/".runtime" if fresh else Path(".runtime").resolve()
    data=base/"data" if fresh else root/"smoke-pg"
    server=None
    preserve=False
    try:
        if fresh:root.mkdir(mode=0o700)
        elif not (data/"PG_VERSION").is_file():
            raise Denied("No existing schema-25 demo; use --fresh-fixture for a new temporary demo")
        server=pgserver.get_server(data,cleanup_mode="stop")
        if fresh:
            from parkweave.case_fact_clarifications import capture_fixture_cluster
            cluster=capture_fixture_cluster(server.get_uri(),data.resolve())
            with psycopg.connect(server.get_uri(),autocommit=True) as c:
                c.execute("CREATE DATABASE parkweave")
                c.execute("CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE")
            owner=Store(make_conninfo(server.get_uri(),dbname="parkweave"))
            with owner.connect() as c:
                owner._case_fact_fixture_receipt=cluster.record_created_database(c)
        else:
            with psycopg.connect(server.get_uri()) as c:
                if not c.execute("SELECT 1 FROM pg_database WHERE datname='parkweave'").fetchone():
                    raise Denied("Existing demo has no parkweave database; use --fresh-fixture without altering it")
                if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='parkweave_app'").fetchone():
                    raise Denied("Existing demo app role missing; no automatic identity repair")
            owner=Store(make_conninfo(server.get_uri(),dbname="parkweave"))
            with owner.connect() as c:
                table=c.execute("SELECT to_regclass('public.schema_version') t").fetchone()["t"]
                version=c.execute("SELECT max(version) v FROM schema_version").fetchone()["v"] if table else None
                if version not in (25,26):
                    raise Denied("Existing demo migration has no creation receipt; preserve it and use --fresh-fixture")
        if fresh or version==26:owner.migrate()
        yield root,owner
    except DemoStopUnconfirmed:
        preserve=True
        raise
    finally:
        if server is not None:server.cleanup()
        if base is not None and not preserve:
            if (data/"postmaster.pid").exists():
                raise RuntimeError("Owned demo stop not confirmed; temporary directory retained")
            shutil.rmtree(base)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fault-fixtures', action='store_true')
    parser.add_argument('--preparation-fixtures', action='store_true')
    parser.add_argument('--resource-fixtures', action='store_true')
    parser.add_argument('--combination-fixtures', action='store_true')
    parser.add_argument('--receipt-fixtures', action='store_true')
    parser.add_argument("--fresh-fixture",action="store_true",help="new temporary synthetic demo; preserves existing .runtime and removes only this demo on exit")
    parser.add_argument("--port",type=int,default=8765)
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error("port must be 1024..65535")
    def stop(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    with demo_database(args.fresh_fixture) as (root,owner):
        serve(root,owner,args)


def serve(root,owner,args):
    with owner.connect() as c:
        c.execute((REPO/'src/parkweave/roles.sql').read_text())
        if args.fault_fixtures:
            c.execute((REPO/'src/parkweave/roles-fault-fixture.sql').read_text())
        version=c.execute('SELECT version()').fetchone()['version']
    mode='FAULT_INJECTION' if args.fault_fixtures else 'LOCAL'
    env=minimal_environment(os.environ,PARKWEAVE_DSN=owner.dsn,PARKWEAVE_MODE=mode,PYTHONPATH=str(REPO/"src"))
    if not (root/'synthetic-sessions.json').exists():
        subprocess.run([sys.executable,'-m','parkweave.cli','seed-synthetic'],env=env,check=True,cwd=root.parent)
    owner.seed(json.loads((root/'synthetic-sessions.json').read_text()))
    if args.preparation_fixtures:
        import secrets
        from parkweave.preparation import seed_synthetic
        sessions=root/'preparation-sessions.json'
        if not sessions.exists():
            sessions.write_text(json.dumps({'prep-specialist-'+id:secrets.token_urlsafe(32) for id in ('fixture-a','fixture-b','fixture-c')}))
            sessions.chmod(0o600)
        seed_synthetic(owner,json.loads(sessions.read_text()))
    if args.receipt_fixtures:
        # Explicit synthetic fixture owner setup; never repair a revoked identity/grant.
        import secrets
        from parkweave.store import digest
        sessions=root/'receipt-sessions.json'
        if not sessions.exists():
            sessions.write_text(json.dumps({'receipt-executor-'+id:secrets.token_urlsafe(32) for id in ('fixture-a','fixture-b','fixture-c')}))
            sessions.chmod(0o600)
        with owner.connect() as c:
            for id,token in json.loads(sessions.read_text()).items():
                parent=c.execute('SELECT park_id,org_id FROM principals WHERE id=%s',(id.removeprefix('receipt-executor-'),)).fetchone()
                c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true) ON CONFLICT DO NOTHING',(id,digest(token),parent['park_id'],parent['org_id'],'service_executor'))
                c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING',(id,'READ',parent['park_id'],parent['org_id']))
    if args.resource_fixtures:
        from parkweave.resource_holds import seed_synthetic
        seed_synthetic(owner)
    if args.combination_fixtures:
        from parkweave.resource_combinations import seed_synthetic
        seed_synthetic(owner)
    env['PARKWEAVE_DSN']=make_conninfo(owner.dsn,user='parkweave_app')
    children=[]
    with (root/'server.log').open('a') as log:
        try:
            api=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory',
                                  '--host','127.0.0.1','--port',str(args.port)],env=env,stdout=log,stderr=log,cwd=REPO)
            children.append(api)
            worker=subprocess.Popen([sys.executable,'-m','parkweave.worker'],env=env,stdout=log,stderr=log,cwd=REPO)
            children.append(worker)
            from http.client import HTTPConnection
            deadline=time.monotonic()+15
            while True:
                if any(child.poll() is not None for child in children):
                    raise RuntimeError('Owned demo process exited before readiness; inspect private server.log')
                connection=HTTPConnection('127.0.0.1',args.port,timeout=.5)
                try:
                    connection.request('GET','/health')
                    response=connection.getresponse()
                    health=json.loads(response.read()) if response.status==200 else None
                    if health and health.get('process_id')==api.pid and health.get('schema') in (25,26) and health.get('data')=='SYNTHETIC' and health.get('execution_mode')==mode:
                        break
                except (OSError,ValueError):pass
                finally:connection.close()
                if time.monotonic()>deadline:raise RuntimeError('Owned demo did not become ready; inspect private server.log')
                time.sleep(.1)
            evidence={'environment':'Linux cloud only','python':sys.version.split()[0],
                      'postgresql':version,'api_pid':api.pid,'worker_pid':worker.pid,'port':args.port,
                      'runtime_directory':str(root),'temporary_fixture':args.fresh_fixture,
                      'data':'SYNTHETIC','live_model':'DISABLED','execution_mode':mode}
            (root/'smoke-environment.json').write_text(json.dumps(evidence,indent=2)+'\n')
            print(json.dumps(evidence),flush=True)
            while all(child.poll() is None for child in children):time.sleep(.5)
            raise RuntimeError('Owned demo process exited; inspect private server.log')
        except KeyboardInterrupt:pass
        finally:
            stop_children(children)


if __name__=='__main__':main()
