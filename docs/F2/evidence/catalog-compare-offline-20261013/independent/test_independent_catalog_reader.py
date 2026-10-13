"""Actual reader DI: effective privilege results are synthetic, never PG proof."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from parkweave import native_run_access_preflight as preflight
from test_linux_trial_catalog import trial_inputs

class Cursor:
    def __init__(self,app,writer,missing_app=False,fail_app=False):
        self.app=app;self.writer=writer;self.missing_app=missing_app;self.fail_app=fail_app
        self.calls=[];self.rows=[];self.row=None
    def execute(self,query,args=None):
        self.calls.append((query,args));self.row=None;self.rows=[]
        if 'FROM pg_catalog.pg_roles r WHERE r.rolname=%s' in query:
            role=args[-1]
            if role=='pwci_app' and self.missing_app:return self
            self.row=dict(superuser=role=='pwci_owner',createdb=False,createrole=False,
                replication=False,bypass_rls=False,dangerous_membership=False,
                owner_membership=False,writer_membership=False)
        elif 'has_function_privilege' in query:
            assert query=="SELECT pg_catalog.has_function_privilege(%s,'pg_catalog.pg_control_system()','EXECUTE') ok"
            assert args in [('pwci_app',),('pwci_writer',)]
            if args==('pwci_app',) and self.fail_app:raise RuntimeError('SYNTHETIC_PRIVILEGE_QUERY_FAILURE')
            self.row={'ok':self.app if args==('pwci_app',) else self.writer}
        elif 'has_schema_privilege' in query:self.row={'ok':args==('pwci_owner',)}
        elif query.lstrip().startswith('SELECT') and any(marker in query for marker in
            ('FROM pg_catalog.pg_class','FROM pg_catalog.pg_attribute','FROM pg_catalog.pg_proc','FROM pg_catalog.pg_trigger')):pass
        else:raise AssertionError('UNMODELED_QUERY')
        return self
    def fetchone(self):return deepcopy(self.row)
    def fetchall(self):return deepcopy(self.rows)

def read(app,writer,**kw):
    spec,catalog=trial_inputs();c=Cursor(app,writer,**kw)
    db=catalog['database'];connection=SimpleNamespace(cursor=lambda **kwargs:c,
        info=SimpleNamespace(host=db['host'],port=db['port']))
    identity=dict(database_name=db['name'],database_oid=db['oid'],system_identifier=db['system_identifier'],
        owner_name='pwci_owner',session_name='pwci_owner',current_name='pwci_owner')
    result=preflight._read_catalog(connection,spec,identity)
    return spec,catalog,result,c

@pytest.mark.parametrize('app,writer,status',[(False,True,'PASS'),(True,True,'REFUSED'),
    (False,False,'APPROVAL_REQUIRED'),(True,False,'REFUSED')])
def test_real_reader_checks_both_named_roles_and_preserves_effective_results(app,writer,status):
    spec,catalog,result,c=read(app,writer)
    assert result['privileges']['app:control_system_execute'] is app
    assert result['privileges']['writer:EXECUTE:pg_control_system():'] is writer
    checks=[args for query,args in c.calls if 'has_function_privilege' in query]
    assert checks==[('pwci_writer',),('pwci_app',)]
    # All other catalog facts are explicit DI fixtures, not actual PG observations.
    for key in ('app:control_system_execute','writer:EXECUTE:pg_control_system():'):
        catalog['privileges'][key]=result['privileges'][key]
    report=preflight.analyze(spec.model_dump(),preflight.CatalogSnapshot.model_validate(catalog).model_dump())
    assert report['status']==status
    if app:assert any(x['check']=='forbidden.app:control_system_execute' and x['status']=='REFUSED' for x in report['checks'])
    assert not report['installation_authorized'] and not report['activation_enabled'] and not report['production_connected']

def test_real_reader_absent_app_role_does_not_synthesize_denial_or_pass():
    spec,catalog,result,c=read(False,True,missing_app=True)
    assert 'app:control_system_execute' not in result['privileges']
    assert [args for query,args in c.calls if 'has_function_privilege' in query]==[('pwci_writer',)]
    del catalog['privileges']['app:control_system_execute']
    report=preflight.analyze(spec.model_dump(),catalog)
    assert report['status']=='NOT_CONNECTED'

def test_real_reader_propagates_app_privilege_query_exception():
    with pytest.raises(RuntimeError,match='SYNTHETIC_PRIVILEGE_QUERY_FAILURE'):
        read(False,True,fail_app=True)
