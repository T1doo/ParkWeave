"""Pure launch/runtime observation and catalog-predicate scope probes."""
from pathlib import Path
import os,sys
from types import SimpleNamespace
import pytest
from parkweave import native_run_access_restricted_host as host
from parkweave import native_run_access_restricted_runtime as runtime
from parkweave.store import Denied
from test_native_run_access_restricted_adapter import adapter_inputs


def test_launch_blocks_automatic_site_code_before_private_fd_consumption():
    _,_,layout,_=adapter_inputs()
    args=host.launch_arguments(layout,999)['args']
    assert '-S' in args, 'isolated -I still permits automatic global site/.pth code before private ticket verification'


def test_runtime_refuses_unapproved_import_path_and_preloaded_source(monkeypatch):
    spec,_,data,private=adapter_inputs();layout=host.RuntimeLayout.model_validate(data)
    authorization=host._RuntimeAuthorization(host._ISSUER,dict(spec=spec,layout=data,private=private,host_pid=999,host_started='SYNTHETIC_START'))
    monkeypatch.setattr(host,'_identities_check',lambda *a:None)
    monkeypatch.setattr(host,'_code_check',lambda *a:None)
    monkeypatch.setattr(host,'_process',lambda pid:dict(pid=999,uid=0,started='SYNTHETIC_START'))
    monkeypatch.setattr(os,'geteuid',lambda:layout.writer_uid)
    monkeypatch.setattr(os,'getegid',lambda:layout.ipc_gid)
    monkeypatch.setattr(os,'getgroups',lambda:[])
    monkeypatch.setattr(os,'getppid',lambda:999)
    outside='/synthetic/unprotected-import-root'
    monkeypatch.setattr(sys,'path',[layout.source_root,*layout.dependency_roots,outside])
    monkeypatch.setitem(sys.modules,'SYNTHETIC_UNAPPROVED_MODULE',SimpleNamespace(__file__=outside+'/module.py'))
    with pytest.raises(Denied):authorization.check()


@pytest.mark.parametrize('boundary',['system_schema_create','nonpublic_write','nonpublic_dangerous_routine'])
def test_catalog_query_does_not_filter_unsafe_authority_out_of_observation(boundary):
    # This is query-predicate coverage, NOT actual PostgreSQL privilege execution.
    class Projection:
        def execute(self,sql,params):self.sql=' '.join(sql.split());return self
        def fetchone(self):
            result={name:False for name in runtime.EXTRA_CHECKS}
            if boundary=='system_schema_create':
                hidden="n.nspname NOT IN ('pg_catalog','information_schema')" in self.sql
                result['ownership']=not hidden
            elif boundary=='nonpublic_write':
                section=self.sql.split(' ownership,',1)[1].split(' table_extra,',1)[0]
                result['table_extra']="n.nspname='public'" not in section
            else:
                section=self.sql.split(' column_extra,',1)[1].split(' routine_extra,',1)[0]
                result['routine_extra']="n.nspname='public'" not in section
            return result
    reader=Projection()
    observation=runtime._additional_acl(reader,['synthetic_app','synthetic_writer'])
    assert any(observation.values()), {'boundary':boundary,'projection':'unsafe namespace authority is filtered out','scope':'metadata query text only; no PG'}
