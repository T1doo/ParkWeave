"""Root-sealed-input helpers for one approved new target; no public secret output."""
from datetime import datetime,timedelta,timezone
import hashlib,json,os,re,sys,traceback
from pathlib import Path
from uuid import UUID,uuid4

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from fastapi.testclient import TestClient
from parkweave import preparation as prep,native_run_access as native
from parkweave import native_run_access_activation as activation,native_run_access_writer as writer
from parkweave import native_run_access_preflight as preflight,native_run_access_restricted_host as host
from parkweave import native_run_access_restricted_runtime as runtime,case_fact_clarifications as facts
from parkweave.case_fact_clarifications import capture_fixture_cluster
from parkweave.case_cancellation_business_binding import BusinessBinding,required_privileges
from parkweave.api import create_app
from parkweave.store import Store,digest,Denied
from scripts.linux_trial.bootstrap import SetupObservation,setup_diagnostic
from scripts.linux_trial.worker import sealed_input,h,api


def checked_owner(owner):
    proof=owner._case_fact_fixture_receipt
    if (type(proof) is not facts.FixtureDatabaseEvidence or
        facts._fixture_databases.get(proof.nonce) is not proof or
        facts._fixture_clusters.get(proof.cluster.nonce) is not proof.cluster):
        raise Denied('original issued creation proof required')
    with owner.connect() as c:
        identity=facts._migration_identity(c);facts._same_cluster(proof.cluster,identity)
        if (identity['database_name'],identity['database_oid'],identity['owner_name'],identity['session_name'])!=(
            proof.database_name,proof.database_oid,proof.cluster.owner,proof.cluster.owner):
            raise Denied('exact original owned database required')
    return proof


def install_business(owner,config,spec):
    checked_owner(owner)
    binding=BusinessBinding.from_spec(spec,business_role='pwci_case',trial_root=config['root'])
    with owner.connect() as c:
        c.execute(sql.SQL('CREATE ROLE pwci_case LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(sql.Literal(config['passwords']['pwci_case'])))
        c.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO pwci_case').format(sql.Identifier(config['database'])))
        c.execute('GRANT USAGE ON SCHEMA public TO pwci_case')
        for row in required_privileges():
            columns=row['columns'];parts=[]
            if columns is not None:parts.append(sql.SQL(',').join(map(sql.Identifier,columns)))
            parts.append(sql.Identifier(row['table']))
            c.execute(sql.SQL('GRANT '+row['action']+(' ({})' if columns is not None else '')+' ON public.{} TO pwci_case').format(*parts))
        extra=runtime._additional_acl(c,['pwci_case','pwci_case'])
        if set(extra)!=runtime.EXTRA_CHECKS or any(v is not False for v in extra.values()):raise Denied('business role extra authority refused')
        actual=c.execute("""SELECT t.relname,a.attname,
            has_column_privilege('pwci_case',t.oid,a.attnum,'SELECT') sel,
            has_column_privilege('pwci_case',t.oid,a.attnum,'INSERT') ins,
            has_column_privilege('pwci_case',t.oid,a.attnum,'UPDATE') upd
            FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace JOIN pg_attribute a ON a.attrelid=t.oid
            WHERE n.nspname='public' AND t.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped""").fetchall()
        for r in actual:
            for action,field in [('SELECT','sel'),('INSERT','ins'),('UPDATE','upd')]:
                expected=any(x['action']==action and x['table']==r['relname'] and
                    (x['columns'] is None or r['attname'] in x['columns']) for x in required_privileges())
                if r[field] is not expected:raise Denied('exact business column write rights required')
        for row in required_privileges():
            if row['columns'] is None:
                ok=c.execute('SELECT has_table_privilege(%s,%s,%s) ok',('pwci_case','public.'+row['table'],row['action'])).fetchone()['ok']
                if ok is not True:raise Denied('required business table read missing')
            else:
                for col in row['columns']:
                    if c.execute('SELECT has_column_privilege(%s,%s,%s,%s) ok',('pwci_case','public.'+row['table'],col,row['action'])).fetchone()['ok'] is not True:
                        raise Denied('required business column permission missing')
    result=make_conninfo(host=binding.database_host,port=binding.database_port,dbname=binding.database_name,
        user=binding.business_role,password=config['passwords']['pwci_case'])
    binding.check_private_dsn(result)
    denied_control_positive(result)
    return result


def denied_control_positive(dsn):
    with psycopg.connect(dsn,row_factory=dict_row,connect_timeout=2,
            options='-c statement_timeout=5000') as c:
        try:c.execute('SELECT system_identifier FROM pg_catalog.pg_control_system()')
        except psycopg.errors.InsufficientPrivilege as e:
            if e.sqlstate!='42501':raise
            c.rollback()
            if c.execute('SELECT 1 value').fetchone()!=dict(value=1):raise AssertionError('BUSINESS_POSITIVE_CONTROL')
        else:raise Denied('business control-system privilege refused')

def setup(config,owned,observation=None):
    observation=observation if observation is not None else SetupObservation()
    # This real PG OS owner satisfies the original receipt's data-directory UID check.
    with observation.check('PG_OWNER'):
        if os.geteuid()!=config['pg_uid']:raise PermissionError('ACTUAL_PG_OWNER_REQUIRED')
    with observation.check('DATABASE_NAME'):
        data=Path(config['data']);maintenance=config['owner_maintenance_dsn'];db=config['database']
        if not re.fullmatch('fixture_[a-f0-9]{32}',db):raise ValueError('NEW_UUID_DATABASE_REQUIRED')
    with observation.check('CLUSTER_PROOF'):
        proof=capture_fixture_cluster(maintenance,data);owned['cluster']=proof
    owned['database_attempted']=True
    with observation.check('DATABASE_CREATE'),psycopg.connect(maintenance,autocommit=True) as c:
        c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(db)))
    with observation.check('DATABASE_RECEIPT'):
        owner=Store(make_conninfo(maintenance,dbname=db))
        owned['store']=owner
        with owner.connect() as c:owner._case_fact_fixture_receipt=proof.record_created_database(c)
    with observation.check('MIGRATION'):owner.migrate()
    tokens=config['tokens']
    # Only a fixed synthetic initial state inside this newly proven empty database.
    with observation.check('SEED'):
        owner.seed({k:tokens[k] for k in ('fixture-a','fixture-b','fixture-c')})
        prep.seed_synthetic(owner,tokens)
    with observation.check('ACTORS'),owner.connect() as c:
        for actor in ('executor-a','unassigned'):
            c.execute('INSERT INTO principals VALUES(%s,%s,%s,%s,%s,true)',
                      (actor,digest(tokens[actor]),'park-a','org-a','service_executor'))
            c.execute('INSERT INTO capability_grants(principal_id,capability,park_id,org_id) VALUES(%s,%s,%s,%s)',
                      (actor,'READ','park-a','org-a'))
    with observation.check('RUN_CREATE'),TestClient(create_app(owner)) as client:
        run=observation.response(client.post('/api/runs',headers=h(tokens,key='ci-setup-run'),json={'goal':'SYNTHETIC资料准备'}),202)['run_id']
        with observation.check('RUN_FINISH'):owner.finish(owner.claim('ci-synthetic-only'))
        with observation.check('PREPARATION_CREATE'):
            row=observation.response(client.post('/api/preparations',headers=h(tokens,key='ci-setup-preparation'),json=dict(
                run_id=run,service_id=prep.SERVICE,service_version=1,reviewer_id='prep-specialist-fixture-a')),201)
        for slot in ('need_summary','material_outline'):
            with observation.check('EVIDENCE_NEED_SUMMARY' if slot=='need_summary' else 'EVIDENCE_MATERIAL_OUTLINE'):
                row=observation.response(client.post('/api/preparations/'+row['preparation_id']+'/commands',headers=h(tokens,key='ci-setup-'+slot),
                    json=dict(action='ADD_EVIDENCE',expected_revision=row['revision'],slot=slot,text='SYNTHETIC '+slot,
                        source_kind='DOCUMENT_EXCERPT',source_label='SYNTHETIC trial v1')),200)
        for action,actor in [('REVIEW','prep-specialist-fixture-a'),('CONFIRM','fixture-a')]:
            with observation.check(action):
                row=observation.response(client.post('/api/preparations/'+row['preparation_id']+'/commands',headers=h(tokens,actor,'ci-setup-'+action),
                    json=dict(action=action,expected_revision=row['revision'],reason='SYNTHETIC explicit '+action)),200)
    with observation.check('NATIVE_STORAGE'):native.install_owned_test_storage(owner,owner._case_fact_fixture_receipt)
    with observation.check('ACTIVATION_STORAGE'):activation.install_owned_test_activation_storage(owner,owner._case_fact_fixture_receipt)
    with observation.check('SOURCE_SNAPSHOT'),owner.connect() as c:
        bridge=native.NativeRunAccess(owner)
        r=c.execute('SELECT * FROM runs WHERE id=%s',(run,)).fetchone()
        source=bridge._source(c,r,bridge._parent(c,r))
        identity=writer._public_database(c)
        system=c.execute('SELECT system_identifier::text value FROM pg_control_system()').fetchone()['value']
        generations=activation._generations(c,'fixture-a','executor-a','prep-specialist-fixture-a')
    with observation.check('POLICY'):
        now=datetime.now(timezone.utc)
        policy=writer.WriterPolicy(environment='PRODUCTION',policy_id=str(uuid4()),revision=1,
            owner_id='fixture-a',approver_id='prep-specialist-fixture-a',beneficiary_id='executor-a',
            approver_actions=['APPROVE','REJECT','REVOKE'],valid_from=now.isoformat(),valid_until=(now+timedelta(minutes=15)).isoformat(),
            source=writer.Source.model_validate(writer._source(source)),generations=generations,
            database_name=db,database_oid=identity['database_oid'],system_identifier=system,
            database_host=identity['database_host'],database_port=identity['database_port'],
            application_role='pwci_app',writer_role='pwci_writer')
    with observation.check('ROLE_CREATE'),owner.connect() as c:
        with observation.check('ROLE_CREATE'):
            for role in ('pwci_app','pwci_writer'):
                # SQL password text stays in a private local connection, never argv or logs.
                c.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}').format(
                    sql.Identifier(role),sql.Literal(config['passwords'][role])))
        with observation.check('DATABASE_ACL'):
            c.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(db)))
            for name in ('postgres','template0','template1'):
                c.execute(sql.SQL('REVOKE CONNECT,TEMPORARY ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
            c.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO pwci_app,pwci_writer').format(sql.Identifier(db)))
        with observation.check('SCHEMA_ACL'):
            c.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
            c.execute('GRANT USAGE ON SCHEMA public TO pwci_app,pwci_writer')
        with observation.check('APP_ACL'):
            c.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO pwci_app')
            c.execute('GRANT INSERT ON authorization_audit TO pwci_app')
        with observation.check('WRITER_ACL'):
            # Function NULL ACL includes PUBLIC EXECUTE. A writer GRANT alone
            # retains it, contradicting the existing app-control denial check.
            # This transaction belongs only to the freshly proven UUID database.
            c.execute('REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC')
            for label,action,table,column in runtime.required_privileges('revision'):
                if action=='LOCK_UPDATE':continue
                if action=='EXECUTE':c.execute('GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO pwci_writer');continue
                c.execute(sql.SQL('GRANT '+action+(' ({})' if column else '')+' ON {} TO pwci_writer').format(
                    *([sql.Identifier(column)] if column else []),sql.Identifier(table)))
    with observation.check('SPEC'):
        spec=preflight.InstallationSpec(policy=policy,installer_role='pwci_owner',
            object_owners={t:'pwci_owner' for t in preflight.TABLES},permission_strategy='DIRECT_DML',parent_lock_column='revision',
            protected_location=config['root'],api_uid=config['api_uid'],writer_uid=config['writer_uid'],transport='LINUX_UNIX',
            policy_source_ref='ROOT_APPROVED_THIS_ONE_JOB',key_source_ref='THIS_JOB_WRITER_PRIVATE_FILE_AND_SEALED_FD',
            host_pin_source_ref='THIS_ROOT_HOST_OBSERVATION')
    # Original issued owner collector is still checked inside this owner process.
    with observation.check('CATALOG_COLLECT'),owner.connect() as c:
        catalog=preflight.collect_owned_catalog(c,owner._case_fact_fixture_receipt,spec)
    with observation.check('CATALOG_COMPARE'):
        report=preflight.analyze(spec.model_dump(),catalog)
        if report['status']!='PASS' or report['changes']:raise AssertionError('ACTUAL_INSTALLED_CATALOG_NOT_PASS')
    with observation.check('RESULT'):
        app_dsn=make_conninfo(host=policy.database_host,port=policy.database_port,dbname=db,user='pwci_app',password=config['passwords']['pwci_app'])
        writer_dsn=make_conninfo(host=policy.database_host,port=policy.database_port,dbname=db,user='pwci_writer',password=config['passwords']['pwci_writer'])
        denied_control_positive(app_dsn)
        result=dict(spec=spec.model_dump(),parent=row,app_dsn=app_dsn,writer_dsn=writer_dsn,
                    creation=dict(action='ORIGINAL_NEW_OWNED_DATABASE',database_name=db,database_oid=policy.database_oid,
                        system_identifier=system,owner='pwci_owner',trial_root=config['root'],
                        absent_from_initial_databases=True,initial_databases=['postgres','template0','template1']))
        result['business_dsn']=install_business(owner,config,spec)
        return result


SNAPSHOT_TABLES=('runs','operations','cases','preparations','preparation_evidence','preparation_events',
    'case_local_lifecycles','case_local_events','run_assignments','service_dispatches','service_dispatch_offers',
    'service_dispatch_events','service_receipt_steps','case_resource_links','resource_case_claims',
    'synthetic_resource_holds','synthetic_resource_combinations','synthetic_resource_combination_receipts')


def drop_owned(config,owned):
    if not owned.get('database_attempted'):return
    owner=owned.get('store')
    if owner is None:raise Denied('unconfirmed creation is not removable')
    proof=checked_owner(owner)
    with psycopg.connect(config['owner_maintenance_dsn'],autocommit=True,row_factory=dict_row,
            options='-c lock_timeout=1000 -c statement_timeout=5000') as c:
        identity=facts._migration_identity(c);facts._same_cluster(proof.cluster,identity)
        if identity['database_name']!='postgres' or identity['session_name']!=proof.cluster.owner:
            raise Denied('original maintenance owner required')
        row=c.execute('SELECT oid,pg_get_userbyid(datdba) owner FROM pg_database WHERE datname=%s',
            (proof.database_name,)).fetchone()
        if row!=dict(oid=proof.database_oid,owner=proof.cluster.owner):raise Denied('original created database instance required')
        c.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(proof.database_name)))
        names={r['datname'] for r in c.execute('SELECT datname FROM pg_database').fetchall()}
        if names!=set(dict(proof.cluster.initial_databases)):raise Denied('unexpected database retained; do not remove')
    owned['database_attempted']=False


def setup_session(config):
    owned={};observation=SetupObservation()
    try:
        result=setup(config,owned,observation)
        frame=dict(outcome='PASS',result=result)
    except BaseException:
        raw=traceback.format_exc();traceback.print_exc()
        frame=dict(outcome='FAIL',trace_sha256=hashlib.sha256(raw.encode()).hexdigest())
    print(writer._canonical(frame),flush=True)
    for raw in sys.stdin.buffer:
        if len(raw)>524288:raise ValueError('BOUNDED_OWNER_FRAME_REQUIRED')
        message=json.loads(raw)
        if message==dict(operation='SNAPSHOT'):
            owner=owned['store'];checked_owner(owner)
            with owner.connect() as c:
                result={t:c.execute('SELECT row_to_json(t) value FROM '+t+' t ORDER BY row_to_json(t)::text').fetchall() for t in SNAPSHOT_TABLES}
        elif message==dict(operation='DROP'):
            try:drop_owned(config,owned);result=dict(dropped=True)
            except BaseException:traceback.print_exc();result=dict(dropped=False)
        elif message==dict(operation='CLOSE'):break
        else:raise ValueError('EXPLICIT_OWNER_OPERATION_REQUIRED')
        print(writer._canonical(dict(result=result)),flush=True)


class BusinessStore(Store):
    def __init__(self,dsn,binding):
        binding.check_private_dsn(dsn);super().__init__(dsn);self.binding=binding

    def connect(self):
        c=super().connect();b=self.binding
        try:
            row=c.execute("""SELECT d.datname db,d.oid oid,session_user session,current_user role,
                pg_get_userbyid(d.datdba) owner FROM pg_database d WHERE d.datname=current_database()""").fetchone()
            if (row!=dict(db=b.database_name,oid=b.database_oid,session=b.business_role,role=b.business_role,owner=b.installer_role) or
                    (c.info.host,c.info.port)!=(b.database_host,b.database_port)):
                raise Denied('exact business session/database required')
            c.rollback()
            return c
        except BaseException:c.close();raise


def business_session(config):
    expected={'api_uid','api_gid','ipc_gid','spec','business_binding','business_dsn','tokens'}
    if set(config)!=expected or (os.geteuid(),os.getegid())!=(config['api_uid'],config['api_gid']) or config['ipc_gid'] not in os.getgroups():
        raise Denied('exact business API input/identity required')
    b=BusinessBinding.model_validate(config['business_binding']);b.check_spec(config['spec'])
    store=BusinessStore(config['business_dsn'],b)
    with TestClient(create_app(store)) as client:
        def request(method,path,*,key=None,body=None):
            r=client.request(method,path,headers=h(config['tokens'],b.source.owner_id,key),
                **({'json':body} if body is not None else {}))
            return dict(status=r.status_code,body=r.json())
        for raw in sys.stdin.buffer:
            if len(raw)>524288:raise ValueError('BOUNDED_BUSINESS_FRAME_REQUIRED')
            value=json.loads(raw);op=value.get('operation')
            if op=='READ' and set(value)=={'operation'}:result=request('GET',b.read_path())
            elif op in ('CANCEL_DROP','CHANGED_KEY') and set(value)=={'operation','key','body'}:
                b.recovery_path(value['key']);b.check_cancel_request(b.source.preparation_id,value['body'])
                response=request('POST',b.read_path(),key=value['key'],body=value['body'])
                # Exactly one original POST; its response intentionally discarded.
                result=dict(sent_once=True) if op=='CANCEL_DROP' else response
            elif op=='RECOVER' and set(value)=={'operation','key'}:
                result=request('GET',b.recovery_path(value['key']))
            elif op=='LATE_MATERIAL' and set(value)=={'operation'}:
                result=request('POST','/api/preparations/'+b.source.preparation_id+'/commands',key='ci-late-material',
                    body=dict(action='REOPEN',expected_revision=b.source.preparation_revision,reason='SYNTHETIC late material write'))
            elif op=='IDENTITY' and set(value)=={'operation'}:
                with store.connect() as c:
                    result=c.execute("SELECT session_user session,current_user role,has_function_privilege(current_user,'pg_control_system()','EXECUTE') control").fetchone()
            elif value==dict(operation='CLOSE'):break
            else:raise ValueError('EXPLICIT_BOUND_BUSINESS_OPERATION_REQUIRED')
            print(writer._canonical(dict(result=result)),flush=True)


def main():
    if len(sys.argv)!=3 or sys.argv[1] not in ('SETUP','API','BUSINESS'):raise ValueError('EXPLICIT_PRIVATE_HELPER_REQUIRED')
    config=sealed_input(int(sys.argv[2]))
    if sys.argv[1]=='SETUP':setup_session(config)
    elif sys.argv[1]=='API':api(config)
    else:business_session(config)
    return 0


if __name__=='__main__':raise SystemExit(main())
