"""Fresh retained Linux SYNTHETIC demo using the original ordinary P1-P5 APIs.

setup creates only a new private cluster; serve never initializes or repairs one.
No production DSN, Native writer, Approval or V4 provider is accepted.
"""
import argparse
from contextlib import contextmanager
from dataclasses import asdict
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from scripts import material_only_demo as lifecycle
from scripts.linux_fixture_server import stop_children
from parkweave.store import Store,Denied,digest
from parkweave.process_env import minimal_environment
from parkweave import resource_holds as resources,resource_combinations as combinations

PREFIX='parkweave-ordinary-demo-'
SCHEMA='parkweave-ordinary-synthetic-demo/2'
IDS=dict(enterprise='ordinary-demo-enterprise',specialist='ordinary-demo-specialist',executor='ordinary-demo-executor')
PARK='synthetic-ordinary-park';ORG='synthetic-ordinary-org'
# Fixed demo configuration only; these are not production grants or logins.
SCOPES={
    'primary':dict(label='第一合成企业 / 第一合成园区',park_id=PARK,org_id=ORG,ids=IDS,
        sessions={actor:actor for actor in IDS},source_id='ORDINARY_LOCAL_DEMO_V1',
        resources=[dict(id=str(resources.RESOURCE_ID),name='合成协作空间'),
                   dict(id=str(combinations.SECOND_RESOURCE_ID),name='合成研讨设备')]),
    'secondary':dict(label='第二合成企业 / 第二合成园区',park_id='synthetic-ordinary-second-park',
        org_id='synthetic-ordinary-second-org',
        ids={actor:'ordinary-demo-second-'+actor for actor in IDS},
        sessions={actor:'second_'+actor for actor in IDS},source_id='ORDINARY_LOCAL_DEMO_SECOND_SCOPE_V1',
        resources=[dict(id='e6120954-2e0b-4ad3-857f-ed6cc7501651',name='第二园区合成协作空间'),
                   dict(id='34ed95d8-1f15-4a47-9118-eb21c7ae5610',name='第二园区合成研讨设备')]),
}
_last_owned_state=None
SQL_RIGHTS={
    **lifecycle.SQL_RIGHTS,
    'SELECT':lifecycle.SQL_RIGHTS['SELECT']+('synthetic_resources','synthetic_resource_grants'),
    'SELECT,INSERT,UPDATE':lifecycle.SQL_RIGHTS['SELECT,INSERT,UPDATE']+('cases',),
    'SELECT,INSERT':('preparation_evidence','preparation_events','synthetic_resource_holds',
        'synthetic_resource_receipts','synthetic_resource_combinations','synthetic_resource_combination_members',
        'synthetic_resource_combination_receipts','resource_case_claims','case_resource_links',
        'service_dispatches','service_dispatch_offers','service_dispatch_events','service_receipt_steps',
        'service_step_receipts','service_receipt_events','case_local_lifecycles','case_local_events',
        'dispatch_notices'),
    'SELECT,INSERT,UPDATE(state,consumed_at)':('dispatch_notice_outbox',),
    'UPDATE(state)':('synthetic_resource_holds','synthetic_resource_combinations'),
    'UPDATE(revision,current_offer_id)':('service_dispatches',),
    'UPDATE(state,receipt_step_id)':('service_dispatch_offers',),
    'UPDATE(state,revision,current_receipt_id)':('service_receipt_steps',),
    'UPDATE(revision,cycle,state,verified_snapshot,verified_sha256)':('case_local_lifecycles',),
    'UPDATE(seen_at,read_at)':('dispatch_notices',),
}


def source_binding():
    """Content binding works from an installed source tree without Git metadata."""
    paths=[]
    for p in (ROOT/'src/parkweave').rglob('*'):
        if '__pycache__' in p.parts:continue
        if p.is_symlink():raise Denied('regular demo source files required')
        if p.is_file():paths.append(p)
    paths += [Path(__file__),ROOT/'scripts/material_only_demo.py',ROOT/'scripts/linux_fixture_server.py']
    files={str(p.relative_to(ROOT)):sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    return dict(sha256=digest(json.dumps(files,sort_keys=True,separators=(',',':'))),files=files)


def private_state(value):
    p=Path(value).absolute()
    if (sys.platform!='linux' or p.resolve()!=p or p.parent!=Path('/tmp') or
            not p.name.startswith(PREFIX) or not p.is_dir() or
            p.stat().st_uid!=os.geteuid() or p.stat().st_mode&0o077):
        raise Denied('owned private ordinary demo directory required')
    for name in ('data','socket','logs','state.json','sessions.json','entry.lock','creation-observation.json'):
        child=p/name
        if child.is_symlink() or child.exists() and (child.stat().st_uid!=os.geteuid() or child.stat().st_mode&0o077):
            raise Denied('private owned ordinary demo files required')
        if child.exists() and ((name in ('data','socket','logs'))!=child.is_dir() or
                name not in ('data','socket','logs') and (not child.is_file() or child.stat().st_size>131072)):
            raise Denied('bounded regular ordinary demo files required')
    return p


@contextmanager
def locked(value):
    p=private_state(value)
    with (p/'entry.lock').open('r+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield p


def authority(c):
    result=lifecycle.authority(c)
    role=c.execute("SELECT oid,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls,rolcanlogin FROM pg_roles WHERE rolname='parkweave_app'").fetchone()
    if (not role or any(role[k] for k in ('rolsuper','rolcreatedb','rolcreaterole','rolreplication','rolbypassrls')) or not role['rolcanlogin']):
        raise Denied('original restricted demo app role required')
    sql=dict(role=role,
        database=c.execute('SELECT datdba,datacl::text[] acl FROM pg_database WHERE datname=current_database()').fetchone(),
        schema=c.execute("SELECT nspowner,nspacl::text[] acl FROM pg_namespace WHERE nspname='public'").fetchone(),
        members=c.execute('SELECT roleid,admin_option FROM pg_auth_members WHERE member=%s ORDER BY roleid',(role['oid'],)).fetchall(),
        tables=c.execute("SELECT relname,relowner,relacl::text[] acl FROM pg_class WHERE relnamespace='public'::regnamespace AND relkind IN ('r','v','m','S','f','p') ORDER BY relname").fetchall(),
        columns=c.execute("SELECT c.relname,a.attname,a.attacl::text[] acl FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid WHERE c.relnamespace='public'::regnamespace AND a.attnum>0 AND NOT a.attisdropped AND a.attacl IS NOT NULL ORDER BY c.relname,a.attname").fetchall())
    if sql['members'] or sql['database']['datdba']==role['oid'] or any(t['relowner']==role['oid'] for t in sql['tables']):
        raise Denied('demo app cannot be an owner or inherit another role')
    ddl=c.execute("SELECT has_database_privilege('parkweave_app',current_database(),'CREATE') OR has_database_privilege('parkweave_app',current_database(),'TEMP') OR has_schema_privilege('parkweave_app','public','CREATE') allowed").fetchone()
    if ddl['allowed']:raise Denied('demo app cannot create schemas or temporary/public objects')
    result['sql_sha256']=digest(json.dumps(sql,sort_keys=True,default=str,separators=(',',':')))
    return result


def initialize(owner,tokens):
    """Fixed synthetic initial data, called only after this process created the DB."""
    from parkweave.case_fact_clarifications import FixtureDatabaseEvidence
    receipt=getattr(owner,'_case_fact_fixture_receipt',None)
    if type(receipt) is not FixtureDatabaseEvidence:
        raise Denied('live owned synthetic creation receipt required before demo initialization')
    with owner.connect() as c:
        receipt.authorize_migration(c)
        for scope in SCOPES.values():
            ids=scope['ids'];park=scope['park_id'];org=scope['org_id']
            for actor,role,caps in (('enterprise','enterprise_operator',('READ','EXECUTE')),
                    ('specialist','park_specialist',('READ',)),('executor','service_executor',('READ',))):
                session=tokens[scope['sessions'][actor]]
                c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',(ids[actor],digest(session),park,org,role))
                for cap in caps:c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s)',(ids[actor],cap,park,org))
            c.execute("INSERT INTO action_grants(principal_id,action,park_id,org_id) VALUES(%s,'case.create',%s,%s)",(ids['enterprise'],park,org))
            for actor,cap in (('enterprise','PREPARE'),('specialist','REVIEW_ASSIGNED')):
                c.execute('INSERT INTO preparation_grants(principal_id,park_id,org_id,capability) VALUES(%s,%s,%s,%s)',(ids[actor],park,org,cap))
            source=dict(kind='SYNTHETIC',id=scope['source_id'],revision='1',statement=scope['label']+'；合成演示配置，不是正式目录、批准或外部履约。')
            c.execute("INSERT INTO preparation_catalog VALUES(%s,'synthetic-material-preparation',1,%s,%s,'SYNTHETIC','NOT_EVALUATED')",(park,scope['label']+'普通资料服务（合成）',Jsonb(source)))
            for resource in scope['resources']:
                c.execute("INSERT INTO synthetic_resources VALUES(%s,%s,%s,1,2,300,clock_timestamp()-interval '1 day',clock_timestamp()+interval '30 days',true,'UTC','SYNTHETIC','LOCAL_AUTHORITY',%s)",(resource['id'],park,resource['name'],Jsonb(source)))
                for cap in ('READ','HOLD'):c.execute('INSERT INTO synthetic_resource_grants VALUES(%s,%s,%s,%s,%s,true)',(ids['enterprise'],resource['id'],park,org,cap))
        c.execute('REVOKE ALL ON DATABASE parkweave FROM PUBLIC')
        c.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
        c.execute('GRANT CONNECT ON DATABASE parkweave TO parkweave_app')
        c.execute('GRANT USAGE ON SCHEMA public TO parkweave_app')
        for rights,tables in SQL_RIGHTS.items():c.execute('GRANT '+rights+' ON '+','.join(tables)+' TO parkweave_app')


def setup():
    global _last_owned_state
    if sys.platform!='linux' or os.geteuid()==0:raise Denied('existing unprivileged Linux environment required')
    p=Path(tempfile.mkdtemp(prefix=PREFIX,dir='/tmp'));_last_owned_state=p
    print(json.dumps(dict(setup_state_dir=str(p),scope='ORDINARY_SYNTHETIC',state_retained=True)),flush=True)
    for name in ('logs','socket','downloads'):(p/name).mkdir(mode=0o700)
    (p/'entry.lock').touch(mode=0o600)
    with (p/'logs/initdb.log').open('x') as log:
        subprocess.run([lifecycle.pg_bin('initdb'),'-D',str(p/'data'),'-U','postgres',
            '--auth-local=trust','--auth-host=reject','--encoding=UTF8','--no-locale'],
            stdout=log,stderr=log,check=True,timeout=30,env=minimal_environment(os.environ))
    with locked(p),lifecycle.postgres(p):
        from parkweave.case_fact_clarifications import capture_fixture_cluster
        cluster=capture_fixture_cluster(lifecycle.dsn(p,maintenance=True),p/'data')
        with psycopg.connect(lifecycle.dsn(p,maintenance=True),autocommit=True) as c:
            c.execute('CREATE DATABASE parkweave')
            c.execute('CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
        owner=Store(lifecycle.dsn(p))
        with owner.connect() as c:receipt=cluster.record_created_database(c)
        owner._case_fact_fixture_receipt=receipt
        lifecycle.dump(p/'creation-observation.json',asdict(receipt))
        owner.migrate()
        tokens={key:secrets.token_urlsafe(32) for scope in SCOPES.values() for key in scope['sessions'].values()}
        initialize(owner,tokens)
        with owner.connect() as c:
            identity=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()
            oid=c.execute('SELECT oid::bigint FROM pg_database WHERE datname=current_database()').fetchone()['oid']
            snapshot=authority(c)
            assert snapshot['counts']==dict(principals=6,capability_grants=8,action_grants=2,
                preparation_grants=4,preparation_catalog=2,run_assignments=0,field_grants=0,
                synthetic_resources=4,synthetic_resource_grants=8)
            assert all(c.execute('SELECT count(*) n FROM '+t).fetchone()['n']==0 for t in
                ('runs','cases','preparations','synthetic_resource_holds','service_dispatches','service_receipt_steps','case_local_events'))
        lifecycle.dump(p/'sessions.json',tokens)
        lifecycle.dump(p/'state.json',dict(schema=SCHEMA,source=source_binding(),system_identifier=identity['system_identifier'],
            database_oid=oid,schema_version=32,authority=snapshot,ids=IDS,scopes=SCOPES,sessions_sha256=sha256((p/'sessions.json').read_bytes()).hexdigest(),session_expiry='NONE_MANUAL_REVOCATION_REQUIRED'))
    return p


def check_port(port):
    if not 1024<=port<=65535:raise Denied('unprivileged loopback port required')
    with socket.socket() as probe:probe.bind(('127.0.0.1',port))


def serve(value,port):
    global _last_owned_state
    check_port(port)
    with locked(value) as p:
        _last_owned_state=p
        if (p/'stop-unconfirmed').exists():raise Denied('previous owned stop unconfirmed; state retained')
        marker=json.loads((p/'state.json').read_text())
        if (marker.get('schema')!=SCHEMA or marker.get('source')!=source_binding() or marker.get('ids')!=IDS or
                marker.get('scopes')!=SCOPES or
                marker['sessions_sha256']!=sha256((p/'sessions.json').read_bytes()).hexdigest()):
            raise Denied('ordinary demo source/state binding changed')
        with lifecycle.postgres(p) as pg:
            with psycopg.connect(lifecycle.dsn(p),row_factory=dict_row) as c:
                c.execute('SET TRANSACTION READ ONLY')
                identity=c.execute('SELECT system_identifier::text FROM pg_control_system()').fetchone()
                oid=c.execute('SELECT oid::bigint FROM pg_database WHERE datname=current_database()').fetchone()['oid']
                version=c.execute('SELECT max(version) v FROM schema_version').fetchone()['v']
                if (identity['system_identifier']!=marker['system_identifier'] or oid!=marker['database_oid'] or
                        version!=32 or authority(c)!=marker['authority']):
                    raise Denied('retained ordinary demo database/authority changed; no repair')
            env=minimal_environment(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONDONTWRITEBYTECODE='1',
                PARKWEAVE_DSN=lifecycle.dsn(p,application=True),PARKWEAVE_MODE='LOCAL',
                PARKWEAVE_CASE_STEP_MODE='CURRENT_PREPARATION')
            children=[]
            with (p/'logs/application.log').open('a') as log:
                try:
                    for command in (['uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port',str(port),'--no-access-log'],['parkweave.worker']):
                        children.append(subprocess.Popen([sys.executable,'-B','-m',*command],cwd=ROOT,env=env,stdout=log,stderr=log))
                    deadline=time.monotonic()+20
                    while time.monotonic()<deadline:
                        if any(child.poll() is not None for child in children):raise RuntimeError('owned API/worker exited; inspect private logs')
                        try:
                            with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=.3) as response:health=json.load(response)
                            if health.get('process_id')==children[0].pid and health.get('schema')==32 and health.get('data')=='SYNTHETIC' and health.get('execution_mode')=='LOCAL':break
                        except (OSError,ValueError):pass
                        time.sleep(.1)
                    else:raise RuntimeError('owned ordinary API readiness timeout')
                    print(json.dumps(dict(url=f'http://127.0.0.1:{port}',api_pid=children[0].pid,worker_pid=children[1].pid,
                        postgres_pid=pg.pid,state_dir=str(p),sessions_file=str(p/'sessions.json'),scope='ORDINARY_SYNTHETIC',
                        mode='CURRENT_PREPARATION',models='DISABLED',run_assignment_created=False,
                        available_scopes=[dict(id=id,label=scope['label'],session_keys=scope['sessions']) for id,scope in SCOPES.items()])),flush=True)
                    while all(child.poll() is None for child in children):time.sleep(.25)
                    raise RuntimeError('owned API/worker exited')
                finally:
                    try:stop_children(children)
                    except BaseException:
                        (p/'stop-unconfirmed').touch(exist_ok=True)
                        raise


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('setup','serve'));parser.add_argument('--state-dir');parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if (args.command=='serve')!=bool(args.state_dir):parser.error('serve requires existing --state-dir; setup creates only a fresh private directory')
    signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        if args.command=='setup':print(json.dumps(dict(state_dir=str(setup()),session_expiry='NONE_MANUAL_REVOCATION_REQUIRED')),flush=True)
        else:serve(args.state_dir,args.port)
    except KeyboardInterrupt:return 130 if args.command=='setup' else 0
    except Exception as error:
        if _last_owned_state is not None:
            import traceback
            with (_last_owned_state/'failure.log').open('a') as stream:stream.write(traceback.format_exc())
        print('ORDINARY_SYNTHETIC_DEMO_BLOCKED: '+type(error).__name__+'; private state retained; no automatic retry',file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
