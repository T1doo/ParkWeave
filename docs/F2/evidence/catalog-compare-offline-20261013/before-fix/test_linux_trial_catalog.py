"""Offline trial-shape catalog regression; no server, credentials or OS changes.

The function ACL model is intentionally limited to EXECUTE on one builtin.
PostgreSQL 16 NULL function ACL means owner/PUBLIC default EXECUTE, not no ACL.
https://www.postgresql.org/docs/16/ddl-priv.html
"""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import psycopg
import pytest
from pydantic import ValidationError
from psycopg import sql

from parkweave import native_run_access_preflight as preflight
from parkweave import native_run_access_restricted_runtime as runtime
from test_native_run_access_preflight import synthetic_catalog,synthetic_spec

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_database(monkeypatch):
    def forbidden(*a,**kw):pytest.fail('physical database use forbidden in offline catalog test')
    monkeypatch.setattr(psycopg,'connect',forbidden)
    monkeypatch.setattr(psycopg.Connection,'connect',forbidden)


def trial_inputs():
    catalog=synthetic_catalog();spec=synthetic_spec(catalog)
    roles={'synthetic_installer':'pwci_owner','synthetic_app':'pwci_app','synthetic_writer':'pwci_writer'}
    catalog['roles']={roles[k]:v for k,v in catalog['roles'].items()}
    catalog['roles']['pwci_owner'].update(superuser=True,createdb=True,createrole=True,replication=True,bypass_rls=True)
    for table in catalog['tables'].values():table.update(owner='pwci_owner',acl=[])
    for functions in catalog['functions'].values():
        for function in functions:function['owner']='pwci_owner'
    database=dict(name='fixture_'+'a'*32,host='/tmp/parkweave-trial-'+'b'*32+'/pg/socket',port=55439,
                  session_user='pwci_owner',current_user='pwci_owner')
    catalog['database'].update(database)
    spec.update(installer_role='pwci_owner',object_owners={k:'pwci_owner' for k in preflight.TABLES},
                protected_location='/tmp/parkweave-trial-'+'b'*32,api_uid=101,writer_uid=102,
                policy_source_ref='ROOT_APPROVED_THIS_ONE_JOB',key_source_ref='THIS_JOB_WRITER_PRIVATE_FILE_AND_SEALED_FD',
                host_pin_source_ref='THIS_ROOT_HOST_OBSERVATION')
    spec['policy'].update(database_name=database['name'],database_host=database['host'],database_port=database['port'],
                          application_role='pwci_app',writer_role='pwci_writer',owner_id='fixture-a',
                          approver_id='prep-specialist-fixture-a',beneficiary_id='executor-a',
                          generations={'principals':[{'id':'fixture-a','generation':'7'}],
                                       'capabilities':[{'principal_id':'fixture-a','capability':'READ','generation':'8'}],
                                       'preparation':[{'principal_id':'fixture-a','capability':'PREPARE','generation':'9'}]})
    spec['policy']['source']['owner_id']='fixture-a'
    return preflight.InstallationSpec.model_validate(spec),preflight.CatalogSnapshot.model_validate(catalog).model_dump()


def setup_block(check_id):
    """Execute the actual existing block against DI objects, not a copied SQL recipe."""
    tree=ast.parse((ROOT/'scripts/linux_trial/worker.py').read_text())
    setup=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='setup')
    blocks=[n for n in setup.body if isinstance(n,ast.With) and any(
        isinstance(item.context_expr,ast.Call) and isinstance(item.context_expr.func,ast.Attribute)
        and item.context_expr.func.attr=='check' and item.context_expr.args
        and isinstance(item.context_expr.args[0],ast.Constant) and item.context_expr.args[0].value==check_id
        for item in n.items)]
    assert len(blocks)==1
    return compile(ast.Module(body=deepcopy(blocks),type_ignores=[]),'actual_worker_setup_'+check_id,'exec')


class Observation:
    def __init__(self):self.current=None
    def check(self,name):self.current=name;return self
    def __enter__(self):return self
    def __exit__(self,*args):return False


class BuiltinFunctionACL:
    def __init__(self):
        self.public_execute=True  # pg_proc.proacl NULL => built-in function defaults.
        self.direct=set();self.operations=[]
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,statement):
        text=statement.as_string() if isinstance(statement,sql.Composable) else statement
        if 'pg_control_system()' not in text:return self
        self.operations.append(text)
        if text=='REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC':self.public_execute=False
        elif text=='GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO pwci_writer':self.direct.add('pwci_writer')
        else:pytest.fail('unexpected control-system ACL operation')
        return self
    def can_execute(self,role):return role=='pwci_owner' or self.public_execute or role in self.direct


def apply_actual_acl():
    acl=BuiltinFunctionACL();observation=Observation()
    exec(setup_block('ROLE_CREATE'),dict(owner=SimpleNamespace(connect=lambda:acl),observation=observation,
        sql=sql,runtime=runtime,db='fixture_'+'a'*32,
        config={'passwords':{'pwci_app':'SYNTHETIC_ONLY','pwci_writer':'SYNTHETIC_ONLY'}}))
    return acl


def compare(spec,catalog):
    observation=Observation();namespace=dict(observation=observation,preflight=preflight,spec=spec,catalog=catalog)
    try:exec(setup_block('CATALOG_COMPARE'),namespace)
    finally:assert observation.current=='CATALOG_COMPARE'
    return namespace['report']


def test_trial_acl_closes_public_execute_before_preserving_writer_grant():
    acl=apply_actual_acl()
    assert acl.can_execute('pwci_writer') and acl.can_execute('pwci_owner')
    assert not acl.can_execute('pwci_app')
    assert not acl.can_execute('unrelated_role')
    assert acl.operations==['REVOKE EXECUTE ON FUNCTION pg_catalog.pg_control_system() FROM PUBLIC',
                            'GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO pwci_writer']


def test_actual_trial_acl_produces_safe_typed_catalog_comparison():
    spec,catalog=trial_inputs();acl=apply_actual_acl()
    catalog['privileges']['app:control_system_execute']=acl.can_execute('pwci_app')
    catalog['privileges']['writer:EXECUTE:pg_control_system():']=acl.can_execute('pwci_writer')
    catalog=preflight.CatalogSnapshot.model_validate(catalog).model_dump()
    report=compare(preflight.InstallationSpec.model_validate(spec.model_dump()),catalog)
    assert report['status']=='PASS' and report['changes']==[]
    assert report['installation_authorized'] is report['activation_enabled'] is report['production_connected'] is False


def test_pre_fix_public_default_is_refused_after_production_model_roundtrip():
    spec,catalog=trial_inputs();acl=BuiltinFunctionACL()
    acl.execute('GRANT EXECUTE ON FUNCTION pg_catalog.pg_control_system() TO pwci_writer')
    catalog['privileges']['app:control_system_execute']=acl.can_execute('pwci_app')
    catalog=preflight.CatalogSnapshot.model_validate(catalog).model_dump()
    report=preflight.analyze(spec.model_dump(),catalog)
    assert report['status']=='REFUSED' and report['changes']==[]
    assert [r['check'] for r in report['checks'] if r['status']!='PASS']==['forbidden.app:control_system_execute']
    with pytest.raises(AssertionError,match='ACTUAL_INSTALLED_CATALOG_NOT_PASS'):compare(spec,catalog)


def test_worker_compare_distinguishes_analyzer_exception_from_nonpass_and_changes():
    spec,catalog=trial_inputs()
    assert compare(spec,catalog)['status']=='PASS'
    missing=deepcopy(catalog);del missing['columns']['runs.native_run_access_protocol']
    missing=preflight.CatalogSnapshot.model_validate(missing).model_dump()
    report=preflight.analyze(spec.model_dump(),missing)
    assert report['status']=='APPROVAL_REQUIRED' and len(report['changes'])==1
    with pytest.raises(AssertionError,match='ACTUAL_INSTALLED_CATALOG_NOT_PASS'):compare(spec,missing)
    # Accepted opaque Python dict values can raise during policy JSON hashing.
    # The real worker builds generations from text fields, not this synthetic object.
    invalid=spec.model_dump();invalid['policy']['generations']={'synthetic_non_json':object()}
    invalid=preflight.InstallationSpec.model_validate(invalid)
    with pytest.raises(TypeError):compare(invalid,catalog)


def test_catalog_row_and_acl_order_do_not_change_comparison_outcome():
    spec,catalog=trial_inputs()
    for field in ('tables','columns','functions','triggers','roles','privileges'):
        catalog[field]=dict(reversed(list(catalog[field].items())))
    for row in catalog['tables'].values():row['acl']=['pwci_app=r/pwci_owner','pwci_owner=arwdDxt/pwci_owner']
    first=compare(spec,catalog)
    for row in catalog['tables'].values():row['acl'].reverse()
    assert compare(spec,catalog)['status']==first['status']=='PASS'


@pytest.mark.parametrize('field,value',[('identity',None),('identity',b'\0'),('generated',None),('nullable',0)])
def test_bad_column_types_fail_before_catalog_compare(field,value):
    _,catalog=trial_inputs();catalog['columns']['runs.native_run_access_protocol'][field]=value
    with pytest.raises(ValidationError):preflight.CatalogSnapshot.model_validate(catalog)
