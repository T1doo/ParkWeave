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
import psycopg
from psycopg.conninfo import make_conninfo
from parkweave.store import Store


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--fault-fixtures', action='store_true')
    parser.add_argument('--preparation-fixtures', action='store_true')
    parser.add_argument('--resource-fixtures', action='store_true')
    parser.add_argument('--combination-fixtures', action='store_true')
    args=parser.parse_args()
    root=Path('.runtime');root.mkdir(mode=0o700,exist_ok=True)
    server=pgserver.get_server(root/'smoke-pg',cleanup_mode='stop')
    with psycopg.connect(server.get_uri(),autocommit=True) as c:
        if not c.execute("SELECT 1 FROM pg_database WHERE datname='parkweave'").fetchone():
            c.execute('CREATE DATABASE parkweave')
        if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='parkweave_app'").fetchone():
            c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
    owner=Store(make_conninfo(server.get_uri(),dbname='parkweave'));owner.migrate()
    with owner.connect() as c:
        c.execute(Path('src/parkweave/roles.sql').read_text())
        if args.fault_fixtures:
            c.execute(Path('src/parkweave/roles-fault-fixture.sql').read_text())
        version=c.execute('SELECT version()').fetchone()['version']
    mode='FAULT_INJECTION' if args.fault_fixtures else 'LOCAL'
    env=minimal_environment(os.environ,PARKWEAVE_DSN=owner.dsn,PARKWEAVE_MODE=mode)
    if not (root/'synthetic-sessions.json').exists():
        subprocess.run([sys.executable,'-m','parkweave.cli','seed-synthetic'],env=env,check=True)
    owner.seed(json.loads((root/'synthetic-sessions.json').read_text()))
    if args.preparation_fixtures:
        import secrets
        from parkweave.preparation import seed_synthetic
        sessions=root/'preparation-sessions.json'
        if not sessions.exists():
            sessions.write_text(json.dumps({'prep-specialist-'+id:secrets.token_urlsafe(32) for id in ('fixture-a','fixture-b','fixture-c')}))
            sessions.chmod(0o600)
        seed_synthetic(owner,json.loads(sessions.read_text()))
    if args.resource_fixtures:
        from parkweave.resource_holds import seed_synthetic
        seed_synthetic(owner)
    if args.combination_fixtures:
        from parkweave.resource_combinations import seed_synthetic
        seed_synthetic(owner)
    env['PARKWEAVE_DSN']=make_conninfo(owner.dsn,user='parkweave_app')
    log=(root/'server.log').open('a')
    api=subprocess.Popen([sys.executable,'-m','uvicorn','parkweave.api:configured_app','--factory',
                          '--host','127.0.0.1','--port','8765'],env=env,stdout=log,stderr=log)
    worker=subprocess.Popen([sys.executable,'-m','parkweave.worker'],env=env,stdout=log,stderr=log)
    evidence={'environment':'Linux cloud only','python':sys.version.split()[0],
              'postgresql':version,'api_pid':api.pid,'worker_pid':worker.pid,'port':8765,
              'data':'SYNTHETIC','live_model':'DISABLED','execution_mode':mode}
    (root/'smoke-environment.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence),flush=True)
    def stop(signum, frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try:
        while api.poll() is None and worker.poll() is None:time.sleep(.5)
    except KeyboardInterrupt:pass
    finally:
        for child in (api,worker):
            if child.poll() is None:
                child.terminate();child.wait(timeout=10)
        log.close()


if __name__=='__main__':main()
