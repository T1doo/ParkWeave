"""Explicit additive native storage/ACL installer; import/default are closed.

Consumes existing hardened roles, connection, policy and root approval. No
connection discovery, role/key/policy issuer, broad ACL repair or host start.
"""
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re

import psycopg
from psycopg import sql
from psycopg.pq import TransactionStatus
from pydantic import BaseModel, ConfigDict

from . import native_run_access_preflight as preflight
from . import native_run_access_restricted_host as host
from . import native_run_access_restricted_runtime as runtime
from . import native_run_access_writer as writer
from .store import Denied

SCHEMA='parkweave-native-install-plan/1'
CONNECT_KEYS={'app_connect','app_public_usage','writer_connect','writer_public_usage'}


class Snapshot(BaseModel):
    model_config=ConfigDict(strict=True,extra='forbid')
    catalog: preflight.CatalogSnapshot
    extra_acl: dict[str,bool]
    default_function_acl: list[dict]
    connection_prerequisites: dict[str,bool]


class InstallFailure(RuntimeError):
    def __init__(self,phase,outcome,plan_sha256,rollback_error=None):
        self.phase,self.outcome,self.plan_sha256=phase,outcome,plan_sha256
        self.rollback_error=rollback_error
        super().__init__('native installation '+outcome+' at '+phase+'; preserve claim and inspect original cause; no automatic retry')


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def packaged_statements():
    """Fully consume only the reviewed nine statements, including dollar bodies."""
    pattern=re.compile(r'\s*(?:ALTER TABLE (\w+) ADD COLUMN (\w+) jsonb;|'
        r'CREATE FUNCTION (\w+)\(\) RETURNS trigger\s+LANGUAGE plpgsql AS \$\$(.*?)\$\$;|'
        r'CREATE TRIGGER (\w+) BEFORE (INSERT OR UPDATE(?: OR DELETE)?) ON (\w+)\s+'
        r'FOR EACH ROW EXECUTE FUNCTION (\w+)\(\);)',re.S)
    result={}
    for filename in preflight.FILES:
        text=Path(__file__).with_name(filename).read_text()
        text=re.sub(r'(?m)^--[^\n]*(?:\n|$)','',text);offset=0
        while text[offset:].strip():
            match=pattern.match(text,offset)
            if match is None:raise Denied('packaged installation SQL has unknown or unconsumed statement')
            table,column,function,body,trigger,events,relation,target=match.groups()
            statement=match.group(0).strip()
            if table:
                key='ADD_COLUMN:public.'+table+'.'+column
                if table+'.'+column not in preflight.COLUMNS:raise Denied('unknown packaged column')
                statement=statement.replace('ALTER TABLE '+table,'ALTER TABLE public.'+table,1)
            elif function:
                key='CREATE_FUNCTION:public.'+function+'()'
                if function not in preflight.FUNCTIONS:raise Denied('unknown packaged function')
                statement=statement.replace('CREATE FUNCTION '+function,'CREATE FUNCTION public.'+function,1)
            else:
                key='CREATE_TRIGGER:public.'+relation+'.'+trigger
                expected=preflight.TRIGGERS.get(trigger)
                if expected is None or (relation,target)!=(expected[0],expected[1]):raise Denied('unknown packaged trigger')
                statement=statement.replace(' ON '+relation,' ON public.'+relation,1).replace('FUNCTION '+target,'FUNCTION public.'+target,1)
            if key in result:raise Denied('duplicate packaged installation statement')
            result[key]=statement;offset=match.end()
    expected={'ADD_COLUMN:public.'+name for name in preflight.COLUMNS}
    expected|={'CREATE_FUNCTION:public.'+name+'()' for name in preflight.FUNCTIONS}
    expected|={'CREATE_TRIGGER:public.'+table+'.'+name for name,(table,_,_) in preflight.TRIGGERS.items()}
    if set(result)!=expected:raise Denied('complete packaged nine-object contract required')
    return result


def _spec_layout(spec,layout):
    spec=preflight.InstallationSpec.model_validate(spec);layout=host._runtime_layout(layout)
    host.installed_launch_request(spec,layout)
    if spec.parent_lock_column!='revision' or any(owner!=spec.installer_role for owner in spec.object_owners.values()):
        raise Denied('existing installer ownership and reviewed revision lock column required')
    return spec,layout


def _grant_statement(spec,row):
    label,action,table,column=row
    if row not in runtime.required_privileges('revision') or label!='writer' or action not in ('SELECT','INSERT','UPDATE','EXECUTE'):raise Denied('unsupported installation privilege')
    if action=='EXECUTE':
        if table!='pg_control_system()' or column is not None:raise Denied('unknown system function')
        return sql.SQL('GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO {}').format(sql.Identifier(spec.policy.writer_role)).as_string()
    target=sql.Identifier('public',table)
    return (sql.SQL('GRANT '+action+' ({}) ON {} TO {}').format(sql.Identifier(column),target,sql.Identifier(spec.policy.writer_role)) if column else
            sql.SQL('GRANT '+action+' ON {} TO {}').format(target,sql.Identifier(spec.policy.writer_role))).as_string()


def prepare(spec,layout,snapshot):
    """Pure supplied snapshot comparison; this result never authorizes apply."""
    spec,layout=_spec_layout(spec,layout);snapshot=Snapshot.model_validate(snapshot)
    catalog=snapshot.catalog;data=catalog.model_dump()
    # The old collector intentionally omits privileges for columns not yet
    # present. These exact newly added columns need explicit approved grants.
    for row in runtime.required_privileges('revision'):
        if row[3] and row[2]+'.'+row[3] in preflight.COLUMNS and row[2]+'.'+row[3] not in data['columns']:
            data['privileges'].setdefault(preflight._privilege_key(*row),False)
    report=preflight.analyze(spec.model_dump(),data)
    if (report['status'] not in ('PASS','APPROVAL_REQUIRED') or
            (catalog.database.session_user,catalog.database.current_user)!=(spec.installer_role,spec.installer_role) or
            set(snapshot.extra_acl)!=runtime.EXTRA_CHECKS or any(v is not False for v in snapshot.extra_acl.values()) or
            snapshot.default_function_acl or set(snapshot.connection_prerequisites)!=CONNECT_KEYS or
            any(v is not True for v in snapshot.connection_prerequisites.values())):
        raise Denied('known hardened installation snapshot required; no broad ACL repair')
    known_acls=[set(),{spec.installer_role+'=X/'+spec.installer_role},
                {spec.installer_role+'=X/'+spec.installer_role,'=X/'+spec.installer_role}]
    for rows in catalog.functions.values():
        for function in rows:
            if set(function.acl) not in known_acls or len(function.acl)!=len(set(function.acl)):
                raise Denied('unknown existing native function ACL')
    packaged=packaged_statements();steps=[];permitted_checks=set()
    for change in report['changes']:
        action,obj=change['action'],change['object']
        if action in ('ADD_COLUMN','CREATE_FUNCTION','CREATE_TRIGGER'):
            key=action+':'+obj
            if key not in packaged:raise Denied('unknown additive installation object')
            steps.append(dict(kind=action,object=obj,sql=packaged[key]))
            prefix={'ADD_COLUMN':'column.','CREATE_FUNCTION':'function.','CREATE_TRIGGER':'trigger.'}[action]
            name=obj.removeprefix('public.')
            if action=='CREATE_FUNCTION':name=name.removesuffix('()')
            if action=='CREATE_TRIGGER':name=name.split('.')[-1]
            permitted_checks.add(prefix+name)
        elif action!='REVIEW_REQUIRED_PERMISSION':raise Denied('unsupported installation change')
    for row in runtime.required_privileges('revision'):
        key=preflight._privilege_key(*row);value=data['privileges'].get(key)
        if type(value) is not bool:raise Denied('complete current writer privilege observations required')
        if row[1]=='LOCK_UPDATE':
            if value is False and catalog.privileges.get('writer:UPDATE:preparations:revision') is not False:
                raise Denied('inconsistent parent lock privilege snapshot')
            permitted_checks.add('privilege.'+key);continue
        if value is False:
            steps.append(dict(kind='GRANT_PERMISSION',object=key,sql=_grant_statement(spec,row)))
            permitted_checks.add('privilege.'+key)
    if any(check['status']!='PASS' and check['check'] not in permitted_checks for check in report['checks']):
        raise Denied('installation needs unsupported configuration or authority decision')
    # Keep original package order: columns, functions and their dependent triggers.
    order={name:index for index,name in enumerate(packaged)}
    steps.sort(key=lambda step:(1,step['object']) if step['kind']=='GRANT_PERMISSION' else
               (0,order[step['kind']+':'+step['object']]))
    return dict(schema_version=SCHEMA,spec_sha256=writer._sha(spec.model_dump()),
        layout_sha256=writer._sha(layout.model_dump(by_alias=True)),
        before_sha256=writer._sha(snapshot.model_dump()),storage_source_sha256=preflight.expected_storage()[1],
        steps=steps,installation_authorized=False,activation_enabled=False)


def installation_request(controller,plan):
    if type(controller) is not host.LinuxHost or type(controller.layout) is not host.InstalledRuntimeLayout:
        raise Denied('exact existing-installation host required')
    spec,layout=_spec_layout(controller.spec,controller.layout)
    if (type(plan) is not dict or set(plan)!={'schema_version','spec_sha256','layout_sha256','before_sha256','storage_source_sha256','steps','installation_authorized','activation_enabled'} or
            plan.get('schema_version')!=SCHEMA or type(plan.get('before_sha256')) is not str or
            not re.fullmatch('[a-f0-9]{64}',plan['before_sha256']) or
            plan['installation_authorized'] is not False or plan['activation_enabled'] is not False or
            plan.get('spec_sha256')!=writer._sha(spec.model_dump()) or
            plan.get('layout_sha256')!=writer._sha(layout.model_dump(by_alias=True)) or
            plan.get('storage_source_sha256')!=preflight.expected_storage()[1]):
        raise Denied('exact reviewed installation plan required')
    return dict(action='INSTALL_NATIVE_STORAGE_AND_EXACT_ACL',plan_sha256=writer._sha(plan),
        spec_sha256=plan['spec_sha256'],layout_sha256=plan['layout_sha256'],
        before_sha256=plan['before_sha256'],storage_source_sha256=plan['storage_source_sha256'],
        valid_from=spec.policy.valid_from,valid_until=spec.policy.valid_until,
        locks=sorted(preflight.TABLES),isolation='READ COMMITTED',
        output=layout.installation_path,cleanup='NO_AUTOMATIC_RETRY_REVOKE_DROP_OR_HOST_START')


def _authorize(controller,plan,authorization):
    request=installation_request(controller,plan);layout=controller.layout
    if (type(authorization) is not str or authorization!=layout.trial_root+'/host/install-approval.json' or
            not host._supported_linux_runtime() or os.geteuid()!=0):
        raise Denied('explicit protected root installation approval required before private reads or SQL')
    _live_interval(controller.spec)
    key=host._protected_bytes(layout.approval_key_path,0,private=True)
    host.verified_record(json.loads(host._protected_bytes(authorization,0,private=True)),key,request)
    host._identities_check(layout);host._code_check(layout);host._dependencies_check(layout)
    receipt=writer._canonical(dict(payload=host.installed_receipt_payload(controller.spec,layout),
        hmac_sha256=hmac.new(key,writer._canonical(host.installed_receipt_payload(controller.spec,layout)).encode(),'sha256').hexdigest())).encode()
    if _sha(receipt)!=layout.creation_receipt_sha256:raise Denied('predeclared installed receipt digest required')
    return receipt


def _live_interval(spec):
    if not datetime.fromisoformat(spec.policy.valid_from)<=datetime.now(timezone.utc)<datetime.fromisoformat(spec.policy.valid_until):
        raise Denied('original installation policy interval required; no renewal')


def _connection_check(connection,spec):
    p=spec.policy
    if (type(connection) is not psycopg.Connection or connection.closed or connection.autocommit is not True or
            connection.info.transaction_status!=TransactionStatus.IDLE or
            (connection.info.host,connection.info.port,connection.info.dbname,connection.info.user)!=
            (p.database_host,p.database_port,p.database_name,spec.installer_role)):
        raise Denied('existing exact idle autocommit installer connection required; never opens one')


def _identity(connection,spec):
    value=runtime._identity(connection.cursor(row_factory=psycopg.rows.dict_row));p=spec.policy
    if ((value['session_name'],value['current_name'])!=(spec.installer_role,spec.installer_role) or
            (value['database_name'],value['database_oid'],value['system_identifier'])!=
            (p.database_name,p.database_oid,p.system_identifier)):
        raise Denied('actual original installer and physical database required')
    return value


def _baseline_check(connection,spec):
    # The reused reader selects max(version). Refuse unknown executable table
    # structures before that data read, including inherited/foreign children.
    c=connection.cursor(row_factory=psycopg.rows.dict_row)
    known=c.execute("""SELECT r.oid FROM pg_catalog.pg_class r
        JOIN pg_catalog.pg_namespace n ON n.oid=r.relnamespace
        JOIN pg_catalog.pg_attribute a ON a.attrelid=r.oid
        WHERE n.nspname='public' AND r.relname='schema_version'
        AND r.relkind='r' AND pg_catalog.pg_get_userbyid(r.relowner)=%s
        AND NOT r.relrowsecurity AND NOT r.relforcerowsecurity
        AND NOT r.relhasrules AND NOT r.relispartition
        AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_rewrite w WHERE w.ev_class=r.oid)
        AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_inherits i
            WHERE i.inhparent=r.oid OR i.inhrelid=r.oid)
        AND a.attname='version' AND a.attnum>0 AND NOT a.attisdropped
        AND a.atttypid='pg_catalog.int4'::pg_catalog.regtype
        AND a.attidentity='' AND a.attgenerated=''""",(spec.installer_role,)).fetchone()
    if known is None:raise Denied('known plain owned schema_version required before data reads')


def _collect(connection,spec,identity):
    _baseline_check(connection,spec)
    data=preflight._read_catalog(connection,spec,identity);p=spec.policy
    c=connection.cursor(row_factory=psycopg.rows.dict_row)
    data['privileges']['writer:SELECT:schema_version:']=c.execute(
        "SELECT pg_catalog.has_table_privilege(%s,'public.schema_version','SELECT') ok",(p.writer_role,)).fetchone()['ok']
    default_acl=c.execute("""SELECT d.defaclobjtype::text kind,d.defaclnamespace namespace_oid,
        d.defaclacl::text[] acl FROM pg_catalog.pg_default_acl d
        WHERE d.defaclrole=(SELECT oid FROM pg_catalog.pg_roles WHERE rolname=%s)
        AND d.defaclobjtype='f' AND (d.defaclnamespace=0 OR d.defaclnamespace=
        (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname='public'))
        ORDER BY d.defaclnamespace""",(spec.installer_role,)).fetchall()
    prerequisites={}
    for label,role in [('app',p.application_role),('writer',p.writer_role)]:
        row=c.execute("SELECT pg_catalog.has_database_privilege(%s,pg_catalog.current_database(),'CONNECT') connect,pg_catalog.has_schema_privilege(%s,'public','USAGE') usage",(role,role)).fetchone()
        prerequisites[label+'_connect']=row['connect'];prerequisites[label+'_public_usage']=row['usage']
    return Snapshot(catalog=data,extra_acl=runtime._additional_acl(c,[p.application_role,p.writer_role]),
                    default_function_acl=default_acl,connection_prerequisites=prerequisites).model_dump()


def _new_private_output(path,raw):
    host._path_chain(path,{0})
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:host._write_all(fd,raw);os.fsync(fd)
    finally:os.close(fd)


def _controller_snapshot(controller):
    if type(controller) is not host.LinuxHost or type(controller.layout) is not host.InstalledRuntimeLayout:
        raise Denied('exact existing-installation host required')
    return host.LinuxHost(controller.spec.model_dump(),controller.layout.model_dump(by_alias=True))


def inspect(controller,connection):
    """Read an explicit existing target and prepare a delta; never authorizes it."""
    controller=_controller_snapshot(controller);spec,layout=_spec_layout(controller.spec,controller.layout)
    _connection_check(connection,spec);phase='INSPECT_BEGIN';begun=False
    try:
        connection.execute('BEGIN ISOLATION LEVEL READ COMMITTED READ ONLY');begun=True
        connection.execute('SET LOCAL search_path=pg_catalog,public')
        connection.execute("SET LOCAL statement_timeout='5s'");connection.execute("SET LOCAL lock_timeout='1s'")
        phase='INSPECT';identity=_identity(connection,spec)
        _baseline_check(connection,spec)
        # Hold the baseline relation while revalidating and reading its version.
        connection.execute('LOCK TABLE ONLY public.schema_version IN ACCESS SHARE MODE')
        snapshot=_collect(connection,spec,identity)
        plan=prepare(spec,layout,snapshot)
        phase='INSPECT_END';connection.rollback();begun=False
        return dict(snapshot=snapshot,plan=plan,installation_authorized=False,activation_enabled=False)
    except BaseException as error:
        if not begun:raise InstallFailure(phase,'BEGIN_UNKNOWN',None) from error
        if phase=='INSPECT_END':raise InstallFailure(phase,'READ_ONLY_END_UNCONFIRMED',None,error) from error
        try:connection.rollback()
        except BaseException as rollback_error:
            raise InstallFailure(phase,'READ_ONLY_END_UNCONFIRMED',None,rollback_error) from error
        raise InstallFailure(phase,'READ_ONLY_ENDED',None) from error


def install(controller,connection,plan,authorization=None):
    """Apply one root-approved exact delta. No connection/configuration fallback."""
    controller=_controller_snapshot(controller)
    if type(plan) is not dict:raise Denied('exact reviewed installation plan required')
    # The caller may retain/mutate its mapping while authorization or SQL waits.
    # All later authorization, claim, comparison and execution use this copy.
    plan=json.loads(writer._canonical(plan))
    receipt=_authorize(controller,plan,authorization);spec=controller.spec;layout=controller.layout
    _connection_check(connection,spec)
    if Path(layout.installation_path).exists() or Path(layout.installation_path).is_symlink():
        raise Denied('new installed receipt output required; no adoption or overwrite')
    request=installation_request(controller,plan);plan_sha=writer._sha(plan)
    _live_interval(spec)
    _new_private_output(layout.trial_root+'/host/install-claim.json',writer._canonical(request).encode())
    phase='BEGIN';begun=False;committed=False
    try:
        connection.execute('BEGIN ISOLATION LEVEL READ COMMITTED');begun=True
        connection.execute('SET LOCAL search_path=pg_catalog,public')
        connection.execute("SET LOCAL statement_timeout='5s'");connection.execute("SET LOCAL lock_timeout='1s'")
        identity=_identity(connection,spec)
        connection.execute('SELECT pg_catalog.pg_advisory_xact_lock(%s)',(int(plan_sha[:15],16),))
        for name in sorted(preflight.TABLES):
            connection.execute(sql.SQL('LOCK TABLE {} IN ACCESS EXCLUSIVE MODE').format(sql.Identifier('public',name)))
        phase='BEFORE';before=_collect(connection,spec,identity)
        fresh=prepare(spec,layout,before)
        if writer._canonical(fresh)!=writer._canonical(plan):raise Denied('approved installation snapshot or exact delta changed')
        phase='APPLY'
        for step in fresh['steps']:_live_interval(spec);connection.execute(step['sql'])
        phase='AFTER';identity=_identity(connection,spec)
        after=_collect(connection,spec,identity);remaining=prepare(spec,layout,after)
        if remaining['steps']:raise Denied('installation postcondition incomplete')
        _live_interval(spec);phase='COMMIT';connection.commit();committed=True
        phase='PUBLISH';_live_interval(spec);_new_private_output(layout.installation_path,receipt)
        return dict(status='COMMITTED',plan_sha256=plan_sha,before_sha256=plan['before_sha256'],
                    after_sha256=writer._sha(after),installation_receipt_sha256=_sha(receipt),
                    installation_receipt_path=layout.installation_path,host_started=False,activation_enabled=False)
    except BaseException as error:
        if committed:raise InstallFailure(phase,'COMMITTED_OUTPUT_UNCONFIRMED',plan_sha) from error
        if phase=='COMMIT':raise InstallFailure(phase,'COMMIT_UNKNOWN',plan_sha) from error
        if not begun:raise InstallFailure(phase,'BEGIN_UNKNOWN',plan_sha) from error
        try:connection.rollback()
        except BaseException as rollback_error:
            raise InstallFailure(phase,'ROLLBACK_UNCONFIRMED',plan_sha,rollback_error) from error
        raise InstallFailure(phase,'ROLLED_BACK',plan_sha) from error
