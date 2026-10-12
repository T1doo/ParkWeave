"""Offline installation comparison and original owned-PG catalog reads only.

No connection discovery, production adapter, installer or authority is provided.
Supplied JSON is an unverified snapshot, even when every comparison passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
import psycopg
from psycopg.pq import TransactionStatus

from .native_run_access_writer import WriterPolicy
from .store import Denied

TABLES = ('schema_version', 'principals', 'capability_grants', 'preparation_grants',
          'action_grants', 'field_grants', 'runs', 'operations', 'cases', 'preparations',
          'preparation_evidence', 'case_local_lifecycles', 'run_assignments',
          'authorization_audit')
COLUMNS = {'runs.native_run_access_protocol': 'jsonb',
           'runs.native_run_access_activation': 'jsonb',
           'run_assignments.native_access': 'jsonb'}
TRIGGERS = {'native_run_access_append_only': ('runs', 'guard_native_run_access_protocol', 23),
            'native_activation_append_only': ('runs', 'guard_native_run_access_activation', 23),
            'native_assignment_bound': ('run_assignments', 'guard_native_assignment', 31)}
FUNCTIONS = tuple(value[1] for value in TRIGGERS.values())
FILES = ('native-run-access-storage.sql', 'native-run-access-activation-storage.sql')
ROLE_NAME = r'^[A-Za-z_][A-Za-z0-9_$]{0,62}$'


def _sha(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(value).hexdigest()


def _body_sha(value):
    return _sha(value.replace('\r\n', '\n').strip().encode())


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)


class InstallationSpec(Strict):
    policy: WriterPolicy | None = None
    installer_role: str | None = Field(default=None, pattern=ROLE_NAME)
    object_owners: dict[str, str] = Field(default_factory=dict)
    permission_strategy: Literal['DIRECT_DML', 'NARROW_FUNCTIONS'] | None = None
    parent_lock_column: str | None = Field(default=None, pattern=ROLE_NAME)
    protected_location: str | None = None
    api_uid: int | None = Field(default=None, ge=0)
    writer_uid: int | None = Field(default=None, ge=0)
    transport: Literal['LINUX_UNIX', 'WINDOWS_NATIVE'] | None = None
    policy_source_ref: str | None = None
    key_source_ref: str | None = None
    host_pin_source_ref: str | None = None


class Table(Strict):
    oid: int = Field(gt=0)
    owner: str
    kind: str
    rls: bool
    force_rls: bool
    acl: list[str]


class Column(Strict):
    type: str
    nullable: bool
    default: str | None
    identity: str
    generated: str


class Function(Strict):
    oid: int = Field(gt=0)
    owner: str
    arguments: str
    returns: str
    language: str
    body_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    security_definer: bool
    strict: bool
    leakproof: bool
    volatility: str
    config: list[str] | None
    acl: list[str]


class Trigger(Strict):
    relation_oid: int
    function_oid: int
    type: int
    enabled: str
    internal: bool
    constraint_oid: int
    columns: str
    condition: str | None
    arguments_count: int
    arguments_hex: str
    deferrable: bool
    initially_deferred: bool
    old_table: str | None
    new_table: str | None


class Role(Strict):
    superuser: bool
    createdb: bool
    createrole: bool
    replication: bool
    bypass_rls: bool
    dangerous_membership: bool
    owner_membership: bool
    writer_membership: bool


class Database(Strict):
    name: str
    oid: int
    system_identifier: str | None
    host: str
    port: int
    session_user: str
    current_user: str


class CatalogSnapshot(Strict):
    database: Database
    schema_version: int | None
    tables: dict[str, Table]
    columns: dict[str, Column]
    functions: dict[str, list[Function]]
    triggers: dict[str, list[Trigger]]
    roles: dict[str, Role]
    privileges: dict[str, bool]
    unneeded_writer_permissions: list[Annotated[str, Field(pattern=r'^(INSERT|UPDATE|DELETE):[A-Za-z_][A-Za-z0-9_$]*(\.[A-Za-z_][A-Za-z0-9_$]*)?$')]]


def expected_storage():
    """Exact packaged source bodies, not an operator-provided expected SQL file."""
    bodies, files = {}, {}
    for name in FILES:
        raw = Path(__file__).with_name(name).read_bytes()
        files[name] = _sha(raw)
        for function, body in re.findall(
                r'CREATE FUNCTION (\w+)\(\) RETURNS trigger\s+LANGUAGE plpgsql AS \$\$(.*?)\$\$;',
                raw.decode(), re.S):
            bodies[function] = _body_sha(body)
    if set(bodies) != set(FUNCTIONS):
        raise ValueError('packaged native storage contract unavailable')
    return bodies, files


def required_privileges(parent_lock_column=None):
    # Exact current writer path. audit_denial INSERT belongs to the existing API.
    reads = [table for table in TABLES if table not in ('schema_version', 'authorization_audit', 'field_grants')]
    result = [('writer', 'SELECT', table, None) for table in reads]
    result += [('writer', 'UPDATE', 'runs', column) for column in
               ('native_run_access_protocol', 'native_run_access_activation')]
    result += [('writer', 'INSERT', 'run_assignments', column) for column in
               ('principal_id', 'run_id', 'park_id', 'org_id', 'active', 'native_access')]
    result += [('writer', 'UPDATE', 'run_assignments', column) for column in ('active', 'native_access')]
    result += [('writer', 'LOCK_UPDATE', 'preparations', None),
               ('writer', 'EXECUTE', 'pg_control_system()', None)]
    if parent_lock_column:
        result.append(('writer', 'UPDATE', 'preparations', parent_lock_column))
    return result


def _privilege_key(role, action, table, column=None):
    return ':'.join((role, action, table, *(('' if column is None else column),)))


def analyze(spec=None, snapshot=None):
    report = {'schema': 'parkweave-native-writer-preflight/1', 'mode': 'OFFLINE_UNVERIFIED_SNAPSHOT',
              'installation_authorized': False, 'activation_enabled': False,
              'production_connected': False, 'windows_native': 'NOT_RUN', 'formal_at35': 'NOT_RUN',
              'checks': [], 'changes': [], 'installation_status': 'APPROVAL_REQUIRED'}

    def check(name, status, **details):
        report['checks'].append(dict(check=name, status=status, **details))

    def change(action, object_name, **details):
        report['changes'].append(dict(action=action, object=object_name, approval_required=True,
            executable_sql=None, rollback='MANUAL_REVIEW; never drop existing ledger/history or widen authority', **details))

    try:
        spec = InstallationSpec.model_validate(spec if spec is not None else {})
        catalog = CatalogSnapshot.model_validate(snapshot) if snapshot is not None else None
        bodies, files = expected_storage()
    except (ValidationError, ValueError, TypeError):
        check('input_contract', 'REFUSED', reason='INVALID_TYPED_INPUT_OR_PACKAGED_CONTRACT; values not echoed')
        report['status'] = 'REFUSED'
        return report
    report['storage_source_sha256'] = files
    missing = [name for name in ('policy', 'installer_role', 'permission_strategy', 'protected_location',
               'api_uid', 'writer_uid', 'transport', 'policy_source_ref', 'key_source_ref', 'host_pin_source_ref', 'parent_lock_column')
               if getattr(spec, name) is None or (isinstance(getattr(spec, name), str) and not getattr(spec, name).strip())]
    missing += ['object_owners.' + name for name in TABLES if not spec.object_owners.get(name)]
    check('installation_configuration', 'MISSING_CONFIG' if missing else 'PASS', missing=missing)
    if (set(spec.object_owners) - set(TABLES) or
            any(not re.fullmatch(ROLE_NAME, owner) for owner in spec.object_owners.values())):
        check('object_owner_configuration', 'REFUSED', reason='EXACT_KNOWN_OBJECT_AND_ROLE_NAMES_REQUIRED')
    policy = spec.policy
    if policy:
        report['policy_sha256'] = _sha(policy.model_dump())
        check('production_policy_type', 'PASS' if policy.environment == 'PRODUCTION' else 'REFUSED')
        if not all(re.fullmatch(ROLE_NAME, r) for r in (policy.application_role, policy.writer_role)):
            check('database_roles', 'REFUSED', reason='EXACT_ROLE_NAMES_REQUIRED')
        if any(r.startswith('pg_') for r in (policy.application_role, policy.writer_role)):
            check('database_roles', 'REFUSED', reason='SYSTEM_PREDEFINED_ROLE_IS_NOT_A_RESTRICTED_SERVICE_IDENTITY')
    check('independent_os_identity', 'REFUSED' if spec.api_uid is not None and spec.api_uid == spec.writer_uid else
          ('MISSING_CONFIG' if spec.api_uid is None or spec.writer_uid is None else 'PASS'),
          qualification='DECLARED_ONLY; actual OS isolation/key/pin not verified')
    if spec.transport == 'WINDOWS_NATIVE':
        check('transport', 'APPROVAL_REQUIRED', reason='WINDOWS_NATIVE_NOT_IMPLEMENTED_OR_VERIFIED')
    if spec.permission_strategy == 'NARROW_FUNCTIONS':
        check('permission_strategy', 'APPROVAL_REQUIRED', reason='NARROW_INTERFACE_NOT_IMPLEMENTED_OR_REVIEWED')
    if catalog is None:
        check('database_catalog', 'NOT_CONNECTED', reason='NO_SNAPSHOT; tool never discovers or opens a database')
    else:
        check('baseline_version', 'PASS' if catalog.schema_version == 32 else 'REFUSED',
              expected=32, observed=catalog.schema_version)
        check('catalog_observer_session', 'PASS' if catalog.database.session_user == catalog.database.current_user else 'REFUSED',
              qualification='Observer only; real API/writer session identities remain unverified')
        if policy:
            expected = (policy.database_name, policy.database_oid, policy.system_identifier,
                        policy.database_host, policy.database_port)
            actual = (catalog.database.name, catalog.database.oid, catalog.database.system_identifier,
                      catalog.database.host, catalog.database.port)
            check('exact_database_identity', 'NOT_CONNECTED' if actual[2] is None else
                  ('PASS' if actual == expected else 'REFUSED'),
                  qualification='SNAPSHOT_COMPARISON_ONLY; no live production identity proof')
        for name in TABLES:
            table = catalog.tables.get(name)
            if table is None:
                check('table.' + name, 'REFUSED', reason='BASE_RELATION_MISSING; do not apply additive SQL')
                continue
            wanted = spec.object_owners.get(name)
            check('table.' + name, 'REFUSED' if table.kind != 'r' else 'MISSING_CONFIG' if not wanted else
                  ('PASS' if table.kind == 'r' and table.owner == wanted else 'REFUSED'),
                  owner_sha256=_sha(table.owner), acl_sha256=_sha(table.acl))
            if table.rls or table.force_rls:
                check('rls.' + name, 'APPROVAL_REQUIRED', reason='CURRENT_PYTHON_SCOPE_REQUIRES_SEPARATE_RLS_REVIEW')
        for name, kind in COLUMNS.items():
            column = catalog.columns.get(name)
            if column is None:
                check('column.' + name, 'APPROVAL_REQUIRED', reason='MISSING_ADDITIVE_COLUMN')
                change('ADD_COLUMN', 'public.' + name, type=kind, nullable=True, default=None)
            else:
                expected_column = dict(type=kind, nullable=True, default=None, identity='', generated='')
                fields = [field for field, value in expected_column.items() if getattr(column, field) != value]
                check('column.' + name, 'REFUSED' if fields else 'PASS', mismatch_fields=fields,
                      reason='EXACT_NULLABLE_JSONB_WITHOUT_DEFAULT_IDENTITY_OR_GENERATION')
        for name in FUNCTIONS:
            found = catalog.functions.get(name, [])
            if not found:
                check('function.' + name, 'APPROVAL_REQUIRED', reason='MISSING_ADDITIVE_FUNCTION')
                change('CREATE_FUNCTION', 'public.' + name + '()', expected_body_sha256=bodies[name])
            else:
                function = found[0]
                expected_function = dict(arguments='', returns='trigger', language='plpgsql', body_sha256=bodies[name],
                    security_definer=False, strict=False, leakproof=False, volatility='v', config=None)
                fields = [field for field, value in expected_function.items() if getattr(function, field) != value]
                if len(found) != 1:fields.append('overload_count')
                same = not fields
                if spec.installer_role and function.owner != spec.installer_role:fields.append('owner')
                check('function.' + name, 'REFUSED' if not same else 'MISSING_CONFIG' if not spec.installer_role else
                      ('PASS' if same and function.owner == spec.installer_role else 'REFUSED'),
                      mismatch_fields=fields, expected_body_sha256=bodies[name], body_sha256=function.body_sha256, acl_sha256=_sha(function.acl),
                      reason='EXACT_SIGNATURE_BODY_SECURITY_CONFIG_OWNER; conflict must not be overwritten')
        for name, (table, function, kind) in TRIGGERS.items():
            found = catalog.triggers.get(name, [])
            if not found:
                check('trigger.' + name, 'APPROVAL_REQUIRED', reason='MISSING_ADDITIVE_TRIGGER')
                change('CREATE_TRIGGER', 'public.' + table + '.' + name, function='public.' + function + '()', type=kind)
            else:
                trigger = found[0]
                relation = catalog.tables.get(table)
                routines = catalog.functions.get(function, [])
                expected_trigger = dict(relation_oid=relation.oid if relation else None,
                    function_oid=routines[0].oid if len(routines) == 1 else None, type=kind, enabled='O', internal=False,
                    constraint_oid=0, columns='', condition=None, arguments_count=0, arguments_hex='',
                    deferrable=False, initially_deferred=False, old_table=None, new_table=None)
                fields = [field for field, value in expected_trigger.items() if getattr(trigger, field) != value]
                if len(found) != 1:fields.append('duplicate_count')
                check('trigger.' + name, 'REFUSED' if fields else 'PASS', mismatch_fields=fields,
                      reason='EXACT_RELATION_FUNCTION_OID_AND_TRIGGER_SEMANTICS')
        if policy:
            if spec.installer_role:
                check('installer_role_present', 'PASS' if spec.installer_role in catalog.roles else 'NOT_CONNECTED',
                      qualification='Declared operator catalog entry only; actual installer session/authorization unverified')
                for key in ('installer:schema_create', 'installer:alter_targets'):
                    value = catalog.privileges.get(key)
                    check('privilege.' + key, 'NOT_CONNECTED' if value is None else ('PASS' if value else 'APPROVAL_REQUIRED'))
            for label, name in (('app', policy.application_role), ('writer', policy.writer_role)):
                role = catalog.roles.get(name)
                check('role.' + label, 'APPROVAL_REQUIRED' if role is None else
                      ('REFUSED' if any(role.model_dump().values()) else 'PASS'),
                      reason='EXISTING_RESTRICTED_NONOWNER_ROLE_AND_MEMBERSHIPS; no role creation')
            for label, action, table, column in required_privileges(spec.parent_lock_column):
                key = _privilege_key(label, action, table, column)
                ok = catalog.privileges.get(key)
                check('privilege.' + key, 'NOT_CONNECTED' if ok is None else ('PASS' if ok else 'APPROVAL_REQUIRED'))
                if ok is False:
                    change('REVIEW_REQUIRED_PERMISSION', key, strategy=spec.permission_strategy,
                           note='LOCK_UPDATE requires some technical UPDATE privilege; SELECT alone does not suffice' if action == 'LOCK_UPDATE' else None)
            for key in ('app:assignment_write', 'app:identity_write', 'app:control_system_execute',
                        'app:schema_create', 'writer:schema_create', 'writer:unneeded_write'):
                value = catalog.privileges.get(key)
                if key == 'writer:unneeded_write' and catalog.unneeded_writer_permissions:
                    value = True  # Detailed effective excess cannot be overridden by a summary flag.
                check('forbidden.' + key, 'NOT_CONNECTED' if value is None else ('REFUSED' if value else 'PASS'))
            report['unneeded_writer_permissions'] = catalog.unneeded_writer_permissions
    statuses = {row['status'] for row in report['checks']}
    report['status'] = next((s for s in ('REFUSED', 'MISSING_CONFIG', 'NOT_CONNECTED', 'APPROVAL_REQUIRED') if s in statuses), 'PASS')
    report['minimum_installation_authorization'] = [
        'Trusted actual database/catalog/source and existing restricted identities; offline/owned snapshots are not production proof',
        'Explicit reviewed additive objects and exact effective ACL delta or separately implemented narrow interface, with manual rollback',
        'Protected production launcher/UID separation/policy/key/pin and restart/key lifecycle; no credentials supplied to this tool',
        'Separate authorization for production installation and enablement; Windows native/AT35 remain NOT_RUN',
    ]
    return report


def collect_owned_catalog(connection, proof, spec):
    """Only an already-connected, original issued fixture; no DDL/ticket/locks."""
    from . import case_fact_clarifications as facts
    spec = InstallationSpec.model_validate(spec)
    if (type(proof) is not facts.FixtureDatabaseEvidence or
            facts._fixture_databases.get(proof.nonce) is not proof or
            facts._fixture_clusters.get(proof.cluster.nonce) is not proof.cluster or
            not re.fullmatch(r'fixture_[a-f0-9]{32}', proof.database_name) or
            connection.info.dbname != proof.database_name or
            connection.info.user != proof.cluster.owner or
            connection.info.transaction_status != TransactionStatus.IDLE):
        raise Denied('original issued UUID owned fixture and idle owner connection required before catalog reads')
    with connection.transaction():
        c = connection.cursor(row_factory=psycopg.rows.dict_row)
        c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        c.execute('SET LOCAL search_path=pg_catalog')
        c.execute("SET LOCAL statement_timeout='5s'")
        c.execute("SET LOCAL lock_timeout='1s'")
        identity = facts._migration_identity(connection)
        facts._same_cluster(proof.cluster, identity)
        if (identity['database_oid'] != proof.database_oid or identity['owner_name'] != proof.cluster.owner or
                identity['session_name'] != proof.cluster.owner):
            raise Denied('actual owned fixture identity differs from issued receipt')
        tables = {r.pop('name'): r for r in c.execute("""SELECT r.relname name,r.oid,pg_catalog.pg_get_userbyid(r.relowner) owner,
            r.relkind::text kind,r.relrowsecurity rls,r.relforcerowsecurity force_rls,
            coalesce(pg_catalog.array_to_json(r.relacl),'[]'::json)::jsonb acl
            FROM pg_catalog.pg_class r JOIN pg_catalog.pg_namespace n ON n.oid=r.relnamespace
            WHERE n.nspname='public' AND r.relname=ANY(%s)""", (list(TABLES),)).fetchall()}
        columns = {r.pop('name'): r for r in c.execute("""SELECT r.relname||'.'||a.attname name,
            pg_catalog.format_type(a.atttypid,a.atttypmod) type,NOT a.attnotnull nullable,
            pg_catalog.pg_get_expr(d.adbin,d.adrelid) "default",a.attidentity::text identity,a.attgenerated::text generated
            FROM pg_catalog.pg_attribute a JOIN pg_catalog.pg_class r ON r.oid=a.attrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=r.relnamespace LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
            WHERE n.nspname='public' AND NOT a.attisdropped AND (r.relname||'.'||a.attname)=ANY(%s)""", (list(COLUMNS),)).fetchall()}
        functions = {}
        for row in c.execute("""SELECT p.proname name,p.oid,pg_catalog.pg_get_userbyid(p.proowner) owner,
            pg_catalog.pg_get_function_identity_arguments(p.oid) arguments,pg_catalog.pg_get_function_result(p.oid) returns,
            l.lanname language,p.prosrc body,p.prosecdef security_definer,p.proisstrict strict,p.proleakproof leakproof,
            p.provolatile::text volatility,p.proconfig config,coalesce(pg_catalog.array_to_json(p.proacl),'[]'::json)::jsonb acl
            FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
            JOIN pg_catalog.pg_language l ON l.oid=p.prolang WHERE n.nspname='public' AND p.proname=ANY(%s)""", (list(FUNCTIONS),)).fetchall():
            name = row.pop('name');row['body_sha256'] = _body_sha(row.pop('body'))
            functions.setdefault(name, []).append(row)
        triggers = {}
        for row in c.execute("""SELECT t.tgname name,t.tgrelid relation_oid,t.tgfoid function_oid,t.tgtype type,
            t.tgenabled::text enabled,t.tgisinternal internal,t.tgconstraint constraint_oid,t.tgattr::text columns,
            pg_catalog.pg_get_expr(t.tgqual,t.tgrelid) condition,t.tgnargs arguments_count,pg_catalog.encode(t.tgargs,'hex') arguments_hex,
            t.tgdeferrable deferrable,t.tginitdeferred initially_deferred,t.tgoldtable old_table,t.tgnewtable new_table
            FROM pg_catalog.pg_trigger t JOIN pg_catalog.pg_class r ON r.oid=t.tgrelid
            JOIN pg_catalog.pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname='public' AND t.tgname=ANY(%s)""", (list(TRIGGERS),)).fetchall():
            triggers.setdefault(row.pop('name'), []).append(row)
        policy = spec.policy
        role_names = [spec.installer_role] + ([policy.application_role, policy.writer_role] if policy else [])
        roles = {}
        owners = sorted({r['owner'] for r in tables.values()} | {identity['owner_name']} | {r['owner'] for rows in functions.values() for r in rows})
        for name in filter(None, role_names):
            row = c.execute("""SELECT r.rolsuper superuser,r.rolcreatedb createdb,r.rolcreaterole createrole,
                r.rolreplication replication,r.rolbypassrls bypass_rls,
                EXISTS(SELECT 1 FROM pg_catalog.pg_roles x WHERE
                    (x.rolsuper OR x.rolcreatedb OR x.rolcreaterole OR x.rolreplication OR x.rolbypassrls OR
                     pg_catalog.left(x.rolname,3)='pg_') AND
                    pg_catalog.pg_has_role(r.oid,x.oid,'MEMBER')) dangerous_membership,
                EXISTS(SELECT 1 FROM pg_catalog.pg_roles x WHERE x.rolname=ANY(%s) AND
                    pg_catalog.pg_has_role(r.oid,x.oid,'MEMBER')) owner_membership,
                EXISTS(SELECT 1 FROM pg_catalog.pg_roles x WHERE x.rolname=%s AND x.oid<>r.oid AND
                    pg_catalog.pg_has_role(r.oid,x.oid,'MEMBER')) writer_membership
                FROM pg_catalog.pg_roles r WHERE r.rolname=%s""", (owners, policy.writer_role if policy else None, name)).fetchone()
            if row:roles[name] = row
        privileges = {}
        labels = {'app': policy.application_role, 'writer': policy.writer_role} if policy else {}
        def privilege(label, action, table, column=None):
            role = labels.get(label)
            if role not in roles:return None
            if action == 'EXECUTE':
                return c.execute("SELECT pg_catalog.has_function_privilege(%s,'pg_catalog.pg_control_system()','EXECUTE') ok", (role,)).fetchone()['ok']
            if table not in tables:return None
            oid = tables[table]['oid']
            if action == 'LOCK_UPDATE':
                return c.execute("SELECT pg_catalog.has_any_column_privilege(%s,%s,'UPDATE') ok", (role, oid)).fetchone()['ok']
            if column:
                # Missing additive columns are reported separately, not queried as identifiers.
                exists = c.execute('SELECT 1 FROM pg_catalog.pg_attribute WHERE attrelid=%s AND attname=%s AND NOT attisdropped', (oid, column)).fetchone()
                if not exists:return None
                return c.execute('SELECT pg_catalog.has_column_privilege(%s,%s,%s,%s) ok', (role, oid, column, action)).fetchone()['ok']
            return c.execute('SELECT pg_catalog.has_table_privilege(%s,%s,%s) ok', (role, oid, action)).fetchone()['ok']
        for label, action, table, column in required_privileges(spec.parent_lock_column):
            value = privilege(label, action, table, column)
            if value is not None:privileges[_privilege_key(label, action, table, column)] = value
        def any_write(label, names):
            if labels.get(label) not in roles:return None
            return any(privilege(label, action, table) or c.execute('SELECT pg_catalog.has_any_column_privilege(%s,%s,%s) ok',
                       (labels[label], tables[table]['oid'], action)).fetchone()['ok']
                       for table in names if table in tables for action in ('INSERT', 'UPDATE')) or any(
                       privilege(label, 'DELETE', table) for table in names if table in tables)
        for key, value in (('app:assignment_write', any_write('app', ['run_assignments'])),
                           ('app:identity_write', any_write('app', ['principals', 'capability_grants', 'preparation_grants', 'action_grants', 'field_grants'])),
                           ('app:control_system_execute', privilege('app', 'EXECUTE', 'pg_control_system()'))):
            if value is not None:privileges[key] = value
        excess = []
        if policy and policy.writer_role in roles:
            allowed = {'runs': {'native_run_access_protocol', 'native_run_access_activation'},
                       'run_assignments': {'active', 'native_access'}, 'preparations': {spec.parent_lock_column}}
            for row in c.execute("""SELECT r.relname name,a.attname column,
                    pg_catalog.has_column_privilege(%s,r.oid,a.attnum,'INSERT') insert_ok,
                    pg_catalog.has_column_privilege(%s,r.oid,a.attnum,'UPDATE') update_ok,
                    pg_catalog.has_table_privilege(%s,r.oid,'DELETE') delete_ok
                    FROM pg_catalog.pg_class r JOIN pg_catalog.pg_namespace n ON n.oid=r.relnamespace
                    JOIN pg_catalog.pg_attribute a ON a.attrelid=r.oid
                    WHERE n.nspname='public' AND r.relkind IN ('r','p') AND a.attnum>0 AND NOT a.attisdropped""",
                    (policy.writer_role, policy.writer_role, policy.writer_role)).fetchall():
                table, column = row['name'], row['column']
                if row['update_ok'] and column not in allowed.get(table, set()):excess.append('UPDATE:'+table+'.'+column)
                if row['insert_ok'] and not (table == 'run_assignments' and column in
                        {'principal_id', 'run_id', 'park_id', 'org_id', 'active', 'native_access'}):excess.append('INSERT:'+table+'.'+column)
                if row['delete_ok']:excess.append('DELETE:'+table)
            excess = sorted(set(excess))
            privileges['writer:unneeded_write'] = bool(excess)
        for label, role in labels.items():
            if role in roles:
                privileges[label+':schema_create'] = c.execute("SELECT pg_catalog.has_schema_privilege(%s,'public','CREATE') ok", (role,)).fetchone()['ok']
        if spec.installer_role in roles:
            privileges['installer:schema_create'] = c.execute("SELECT pg_catalog.has_schema_privilege(%s,'public','CREATE') ok", (spec.installer_role,)).fetchone()['ok']
            targets = [tables[t]['owner'] for t in ('runs', 'run_assignments') if t in tables]
            privileges['installer:alter_targets'] = len(targets) == 2 and (roles[spec.installer_role]['superuser'] or all(
                c.execute('SELECT pg_catalog.pg_has_role(%s,%s,\'USAGE\') ok', (spec.installer_role, owner)).fetchone()['ok'] for owner in targets))
        version = c.execute('SELECT max(version) value FROM public.schema_version').fetchone()['value'] if 'schema_version' in tables else None
        snapshot = CatalogSnapshot(database=dict(name=identity['database_name'],oid=identity['database_oid'],
            system_identifier=identity['system_identifier'],host=connection.info.host,port=connection.info.port,
            session_user=identity['session_name'],current_user=identity['current_name']),
            schema_version=version,tables=tables,columns=columns,functions=functions,triggers=triggers,
            roles=roles,privileges=privileges,unneeded_writer_permissions=excess)
        return snapshot.model_dump()


def main(argv=None):
    class Parser(argparse.ArgumentParser):
        def error(self, message):
            self.exit(4, 'REFUSED: unsupported preflight arguments; values not echoed\n')
    parser = Parser(allow_abbrev=False, description='离线安装差异比较；不连接数据库、不安装、不授予权限、不启用。')
    parser.add_argument('--spec', type=Path, help='公开安装对象/来源引用清单；禁止DSN/密钥')
    parser.add_argument('--snapshot', type=Path, help='已获得的元数据快照；始终作为离线未验证输入')
    args = parser.parse_args(argv)
    try:
        spec = json.loads(args.spec.read_text()) if args.spec else None
        snapshot = json.loads(args.snapshot.read_text()) if args.snapshot else None
        report = analyze(spec, snapshot)
    except (OSError, ValueError):
        report = dict(schema='parkweave-native-writer-preflight/1', status='REFUSED',
                      reason='INPUT_UNREADABLE_OR_INVALID_JSON; values not echoed',
                      installation_authorized=False, activation_enabled=False, production_connected=False)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return {'PASS': 0, 'MISSING_CONFIG': 2, 'NOT_CONNECTED': 3, 'REFUSED': 4, 'APPROVAL_REQUIRED': 5}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
