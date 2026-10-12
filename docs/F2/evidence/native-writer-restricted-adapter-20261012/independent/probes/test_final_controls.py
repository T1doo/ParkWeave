"""Valid import observations and scoped SQL-text control, all pure DI."""
from copy import deepcopy
from types import SimpleNamespace
import pytest
from parkweave import native_run_access_restricted_host as host
from parkweave import native_run_access_restricted_runtime as runtime
from parkweave.store import Denied
from test_native_run_access_restricted_adapter import adapter_inputs


@pytest.mark.parametrize('bad',['path','file','package_path','origin'])
def test_valid_import_environment_then_unapproved_observation_is_refused(bad):
    _,_,data,_=adapter_inputs();layout=host.RuntimeLayout.model_validate(data)
    path=layout.source_root+'/parkweave/store.py'
    modules={'SYNTHETIC_VALID_MODULE':SimpleNamespace(__file__=path,__spec__=SimpleNamespace(origin=path),__path__=[layout.source_root+'/parkweave'])}
    paths=[layout.source_root,*layout.import_paths]
    host._imports_check(layout,paths=paths,modules=modules,isolated=1,no_site=1)
    modules=deepcopy(modules);paths=list(paths);outside='/synthetic/unapproved/module.py'
    if bad=='path':paths.append('/synthetic/unapproved')
    elif bad=='file':modules['SYNTHETIC_VALID_MODULE'].__file__=outside
    elif bad=='package_path':modules['SYNTHETIC_VALID_MODULE'].__path__=['/synthetic/unapproved']
    else:modules['SYNTHETIC_VALID_MODULE'].__spec__.origin=outside
    with pytest.raises(Denied):host._imports_check(layout,paths=paths,modules=modules,isolated=1,no_site=1)


def test_catalog_scope_checks_distinguish_ownership_from_trusted_system_routines():
    statements=[]
    class Reader:
        def execute(self,sql,params):statements.append((' '.join(sql.split()),params));return self
        def fetchone(self):return {name:False for name in runtime.EXTRA_CHECKS}
    runtime._additional_acl(Reader(),['synthetic_app','synthetic_writer'])
    sql,params=statements[0]
    assert sql.count('%s')==len(params)
    ownership=sql.split(' database_extra,',1)[1].split(' ownership,',1)[0]
    table=sql.split(' ownership,',1)[1].split(' table_extra,',1)[0]
    routine=sql.split(' other_schema_write,',1)[1].split(' routine_extra,',1)[0]
    assert 'has_schema_privilege' in ownership and "'CREATE'" in ownership
    assert "n.nspname NOT IN" not in ownership and "n.nspname='public'" not in ownership
    assert "n.nspname='public'" not in table and "n.nspname<>'public'" in table
    assert "n.nspname='public'" not in routine
    assert "n.nspname NOT IN ('pg_catalog','information_schema')" in routine
    assert 'has_function_privilege' in routine and 'p.prosecdef' in routine
