"""Pure independent boundary probes; no real PG, subprocess, or /tmp writes."""
import ast
from copy import deepcopy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from scripts.catalog_only import bootstrap as boot,probe

ROOT=Path('/workspace/ParkWeave')
SHA='a'*40

def test_bootstrap_private_log_failure_still_has_closed_public_result(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(boot,'gate',lambda *a:SHA)
    monkeypatch.setattr(boot,'open',lambda *a,**kw:io.StringIO(),raising=False)
    monkeypatch.setattr(boot.tempfile,'mkdtemp',lambda **kw:str(tmp_path))
    def fail_dependency(*a,**kw):raise RuntimeError('SYNTHETIC_PRIVATE_DEPENDENCY_FAILURE')
    monkeypatch.setattr(boot.subprocess,'run',fail_dependency)
    original=Path.write_text
    def fail_log(path,*a,**kw):
        if path.name=='bootstrap-failure.log':raise OSError('SYNTHETIC_PRIVATE_LOG_WRITE_FAILURE')
        return original(path,*a,**kw)
    monkeypatch.setattr(Path,'write_text',fail_log)
    assert boot.bootstrap(SHA)==1
    captured=capsys.readouterr();assert captured.err==''
    output=json.loads(captured.out)
    assert output['cases']['DEPENDENCIES']=='FAIL'
    assert 'SYNTHETIC_PRIVATE' not in captured.out

@pytest.mark.parametrize('code',[-9,1])
def test_cleanup_abnormal_postmaster_exit_never_deletes_or_reports_pass(code):
    tree=ast.parse((ROOT/'scripts/catalog_only/probe.py').read_text())
    run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    outer=next(n for n in run.body if isinstance(n,ast.Try))
    cleanup=next(n for n in outer.finalbody if isinstance(n,ast.Try))
    # Compile the actual cleanup block in a wrapper because it can return early.
    function=ast.FunctionDef(name='cleanup_only',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),
        body=[deepcopy(cleanup),ast.Return(value=ast.Name(id='output',ctx=ast.Load()))],decorator_list=[])
    module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
    deleted=[];output=boot.initial(SHA)
    class Log:
        def write_text(self,*a,**kw):pass
    class Root:
        def __truediv__(self,name):return Log()
    cluster=SimpleNamespace(is_symlink=lambda:False,stat=lambda:SimpleNamespace(st_uid=1001))
    namespace=dict(output=output,pg=SimpleNamespace(poll=lambda:code),cluster=cluster,root=Root(),created=True,
        initdb_started=True,initdb_complete=True,previous_handlers={},public_summary=boot.public_summary,
        os=SimpleNamespace(geteuid=lambda:1001),shutil=SimpleNamespace(rmtree=lambda p:deleted.append(p)),
        signal=SimpleNamespace(signal=lambda *a:None),subprocess=boot.subprocess,traceback=boot.traceback)
    exec(compile(module,'actual_catalog_cleanup','exec'),namespace)
    result=namespace['cleanup_only']()
    assert result['cases']['CLEANUP'] in ('FAIL','UNKNOWN')
    assert deleted==[]
