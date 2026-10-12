"""Private sealed-input helpers on the approved VM, never a public log producer."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from uuid import UUID,uuid4

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg import sql
from fastapi.testclient import TestClient

from parkweave import preparation as prep,native_run_access as native
from parkweave import native_run_access_activation as activation,native_run_access_writer as writer
from parkweave import native_run_access_preflight as preflight,native_run_access_restricted_host as host
from parkweave import native_run_access_restricted_runtime as runtime
from parkweave.case_fact_clarifications import capture_fixture_cluster
from parkweave.api import create_app
from parkweave.store import Store,digest


def sealed_input(fd):
    s=os.fstat(fd);seals=fcntl.F_SEAL_SEAL|fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK
    if s.st_uid!=0 or not stat.S_ISREG(s.st_mode) or s.st_size>524288 or fcntl.fcntl(fd,fcntl.F_GET_SEALS)&seals!=seals:
        raise PermissionError('ROOT_SEALED_INPUT_REQUIRED')
    raw=os.pread(fd,524289,0);os.close(fd)
    if len(raw)>524288:raise ValueError('BOUNDED_INPUT_REQUIRED')
    return json.loads(raw)


def h(tokens,actor='fixture-a',key=None):
    result={'Authorization':'Bearer '+tokens[actor]}
    if key is not None:result['Idempotency-Key']=key
    return result


def setup(config):
    # This real PG OS owner satisfies the original receipt's data-directory UID check.
    if os.geteuid()!=config['pg_uid']:raise PermissionError('ACTUAL_PG_OWNER_REQUIRED')
    data=Path(config['data']);maintenance=config['owner_maintenance_dsn'];db=config['database']
    if not re.fullmatch('fixture_[a-f0-9]{32}',db):raise ValueError('NEW_UUID_DATABASE_REQUIRED')
    proof=capture_fixture_cluster(maintenance,data)
    with psycopg.connect(maintenance,autocommit=True) as c:
        c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db)))
    owner=Store(make_conninfo(maintenance,dbname=db))
    with owner.connect() as c:owner._case_fact_fixture_receipt=proof.record_created_database(c)
    owner.migrate()
    tokens=config['tokens']
    # Only a fixed synthetic initial state inside this newly proven empty database.
    owner.seed({k:tokens[k] for k in ('fixture-a','fixture-b','fixture-c')})
    prep.seed_synthetic(owner,tokens)
    with owner.connect() as c:
        for actor in ('executor-a','unassigned'):
            c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',
                      (actor,digest(tokens[actor]),'park-a','org-a','service_executor'))
            c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s)',
                      (actor,'READ','park-a','org-a'))
    with TestClient(create_app(owner)) as client:
        def checked(response,status):
            if response.status_code!=status:raise AssertionError('SYNTHETIC_SETUP_STATUS')
            return response.json()
        run=checked(client.post('/api/runs',headers=h(tokens,key='ci-setup-run'),json={'goal':'SYNTHETIC资料准备'}),202)['run_id']
        owner.finish(owner.claim('ci-synthetic-only'))
        row=checked(client.post('/api/preparations',headers=h(tokens,key='ci-setup-preparation'),json=dict(
            run_id=run,service_id=prep.SERVICE,service_version=1,reviewer_id='prep-specialist-fixture-a')),201)
        for slot in ('need_summary','material_outline'):
            row=checked(client.post('/api/preparations/'+row['preparation_id']+'/commands',headers=h(tokens,key='ci-setup-'+slot),
                json=dict(action='ADD_EVIDENCE',expected_revision=row['revision'],slot=slot,text='SYNTHETIC '+slot,
                    source_kind='DOCUMENT_EXCERPT',source_label='SYNTHETIC trial v1')),200)
        for action,actor in [('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')]:
            row=checked(client.post('/api/preparations/'+row['preparation_id']+'/commands',headers=h(tokens,actor,'ci-setup-'+action),
                json=dict(action=action,expected_revision=row['revision'],reason='SYNTHETIC explicit '+action)),200)
    native.install_owned_test_storage(owner,owner._case_fact_fixture_receipt)
    activation.install_owned_test_activation_storage(owner,owner._case_fact_fixture_receipt)
    bridge=native.NativeRunAccess(owner)
    with owner.connect() as c:
        r=c.execute('SELECT * FROM runs WHERE id=%s',(run,)).fetchone()
        source=bridge._source(c,r,bridge._parent(c,r))
        identity=writer._public_database(c)
        system=c.execute('SELECT system_identifier::text value FROM pg_control_system()').fetchone()['value']
        generations=activation._generations(c,'fixture-a','executor-a','prep-specialist-fixture-a')
    now=datetime.now(timezone.utc)
    policy=writer.WriterPolicy(environment='PRODUCTION',policy_id=str(uuid4()),revision=1,
        owner_id='fixture-a',approver_id='prep-specialist-fixture-a',beneficiary_id='executor-a',
        approver_actions=['APPROVE','REJECT','REVOKE'],valid_from=now.isoformat(),valid_until=(now+timedelta(minutes=15)).isoformat(),
        source=writer.Source.model_validate(writer._source(source)),generations=generations,
        database_name=db,database_oid=identity['database_oid'],system_identifier=system,
        database_host=identity['database_host'],database_port=identity['database_port'],
        application_role='pwci_app',writer_role='pwci_writer')
    with owner.connect() as c:
        for role in ('pwci_app','pwci_writer'):
            # SQL password text stays in a private local connection, never argv or logs.
            c.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(
                sql.Identifier(role),sql.Literal(config['passwords'][role])))
        c.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(db)))
        for name in ('postgres','template0','template1'):
            c.execute(sql.SQL('REVOKE CONNECT,TEMPORARY ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
        c.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO pwci_app,pwci_writer').format(sql.Identifier(db)))
        c.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
        c.execute('GRANT USAGE ON SCHEMA public TO pwci_app,pwci_writer')
        c.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO pwci_app')
        c.execute('GRANT INSERT ON authorization_audit TO pwci_app')
        for label,action,table,column in runtime.required_privileges('revision'):
            if action=='LOCK_UPDATE':continue
            if action=='EXECUTE':c.execute('GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO pwci_writer');continue
            c.execute(sql.SQL('GRANT '+action+(' ({})' if column else '')+' ON {} TO pwci_writer').format(
                *([sql.Identifier(column)] if column else []),sql.Identifier(table)))
    spec=preflight.InstallationSpec(policy=policy,installer_role='pwci_owner',
        object_owners={t:'pwci_owner' for t in preflight.TABLES},permission_strategy='DIRECT_DML',parent_lock_column='revision',
        protected_location=config['root'],api_uid=config['api_uid'],writer_uid=config['writer_uid'],transport='LINUX_UNIX',
        policy_source_ref='ROOT_APPROVED_THIS_ONE_JOB',key_source_ref='THIS_JOB_WRITER_PRIVATE_FILE_AND_SEALED_FD',
        host_pin_source_ref='THIS_ROOT_HOST_OBSERVATION')
    # Original issued owner collector is still checked inside this owner process.
    with owner.connect() as c:catalog=preflight.collect_owned_catalog(c,owner._case_fact_fixture_receipt,spec)
    report=preflight.analyze(spec.model_dump(),catalog)
    if report['status']!='PASS' or report['changes']:raise AssertionError('ACTUAL_INSTALLED_CATALOG_NOT_PASS')
    app_dsn=make_conninfo(host=policy.database_host,port=policy.database_port,dbname=db,user='pwci_app',password=config['passwords']['pwci_app'])
    writer_dsn=make_conninfo(host=policy.database_host,port=policy.database_port,dbname=db,user='pwci_writer',password=config['passwords']['pwci_writer'])
    return dict(spec=spec.model_dump(),parent=row,app_dsn=app_dsn,writer_dsn=writer_dsn,
                creation=dict(action='ORIGINAL_NEW_OWNED_DATABASE',database_name=db,database_oid=policy.database_oid,
                    system_identifier=system,owner='pwci_owner',trial_root=config['root'],
                    absent_from_initial_databases=True,initial_databases=['postgres','template0','template1']))


def api(config):
    if (os.geteuid(),os.getegid())!=(config['api_uid'],config['api_gid']) or config['ipc_gid'] not in os.getgroups():
        raise PermissionError('REAL_API_IDENTITY_REQUIRED')
    if set(config)!={'api_uid','api_gid','ipc_gid','app_dsn','tokens','binding_path','binding_sha256','writer_private_path'}:
        raise ValueError('NO_OWNER_OR_WRITER_SECRET_IN_API_INPUT')
    store=Store(config['app_dsn']);client=TestClient(create_app(store));client.__enter__()
    def request(value):
        result=client.request(value['method'],value['path'],headers=h(config['tokens'],value.get('actor','fixture-a'),value.get('key')),
            **({'json':value['body']} if 'body' in value else {}))
        return dict(status=result.status_code,body=result.json())
    try:
        for raw in sys.stdin.buffer:
            if len(raw)>524288:raise ValueError('BOUNDED_PRIVATE_FRAME_REQUIRED')
            value=json.loads(raw)
            if value['operation']=='REQUEST':result=request(value['request'])
            elif value['operation']=='PARALLEL':
                with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(request,value['requests']))
            elif value['operation']=='BIND':
                host.bind_api(store,config['binding_path'],config['binding_sha256']);result={'bound':True}
            elif value['operation']=='IDENTITY':
                blocked=False
                try:
                    with open(config['writer_private_path'],'rb') as private:private.read(1)
                except PermissionError:blocked=True
                with store.connect() as c:
                    row=c.execute("SELECT current_user role,session_user session,has_table_privilege(current_user,'run_assignments','UPDATE') assignment_write,has_table_privilege(current_user,'principals','UPDATE') identity_write").fetchone()
                result=dict(uid=os.geteuid(),gid=os.getegid(),ipc_member=config['ipc_gid'] in os.getgroups(),writer_private_blocked=blocked,role=row)
            elif value['operation']=='RAW_WRITER_DROP':
                import socket
                public=json.loads(Path(config['binding_path']).read_text());sock=socket.socket(socket.AF_UNIX)
                try:
                    sock.connect(public['pin']['command_path'])
                    sock.sendall((writer._canonical(value['frame'])+'\n').encode())
                    # One POST-equivalent frame, deliberately no response read or resend.
                finally:sock.close()
                result={'sent_once':True}
            elif value['operation']=='CLOSE':break
            else:raise ValueError('EXPLICIT_PRIVATE_OPERATION_REQUIRED')
            sys.stdout.write(writer._canonical({'result':result})+'\n');sys.stdout.flush()
    finally:client.__exit__(None,None,None)


def main():
    if len(sys.argv)!=3 or sys.argv[1] not in ('SETUP','API'):raise ValueError('EXPLICIT_HELPER_MODE_REQUIRED')
    config=sealed_input(int(sys.argv[2]))
    if sys.argv[1]=='SETUP':sys.stdout.write(writer._canonical(setup(config)));sys.stdout.flush()
    else:api(config)


if __name__=='__main__':main()
