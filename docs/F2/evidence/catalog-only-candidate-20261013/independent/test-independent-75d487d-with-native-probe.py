"""Pure independent boundary probes; no real PG, subprocess, or /tmp writes."""
import ast
from copy import deepcopy
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
import psycopg
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

@pytest.mark.parametrize('invalid',[False,True])
def test_bootstrap_imported_probe_output_and_bad_result_remain_private(monkeypatch,tmp_path,capsys,invalid):
    monkeypatch.setattr(boot,'gate',lambda *a:SHA)
    monkeypatch.setattr(boot,'open',lambda *a,**kw:io.StringIO(),raising=False)
    monkeypatch.setattr(boot.tempfile,'mkdtemp',lambda **kw:str(tmp_path))
    monkeypatch.setattr(boot.subprocess,'run',lambda *a,**kw:None)
    monkeypatch.setattr(sys,'path',list(sys.path))
    def run(root,sha):
        print('SYNTHETIC_PRIVATE_PROBE_STDOUT')
        print('SYNTHETIC_PRIVATE_PROBE_STDERR',file=sys.stderr)
        value=boot.initial(sha)
        value['cases']={k:'PASS' for k in boot.CASES}
        if invalid:value['comparisons']['after']['status']='SYNTHETIC_PRIVATE_BAD_RESULT'
        return value
    monkeypatch.setattr(probe,'run',run)
    assert boot.bootstrap(SHA)==(1 if invalid else 0)
    captured=capsys.readouterr()
    assert captured.err=='' and 'SYNTHETIC_PRIVATE' not in captured.out
    value=json.loads(captured.out)
    assert (tmp_path/'probe.log').read_text()=='SYNTHETIC_PRIVATE_PROBE_STDOUT\nSYNTHETIC_PRIVATE_PROBE_STDERR\n'
    if invalid:assert value['cases']['PG16_START']=='FAIL' and value['cases']['CLEANUP']=='UNKNOWN'

@pytest.mark.parametrize('bad',['host','port','recovery','wrong_sqlstate'])
def test_role_call_refuses_wrong_transport_or_unconfirmed_denial(monkeypatch,bad):
    policy=SimpleNamespace(database_host='/synthetic-socket',database_port=55441,
        database_name='fixture_'+'a'*32,database_oid=4242,system_identifier='1234')
    events=[]
    class WrongSQLState(psycopg.errors.InsufficientPrivilege):sqlstate='XX000'
    class Transaction:
        def __enter__(self):events.append('begin')
        def __exit__(self,typ,value,tb):events.append('rollback' if typ else 'commit');return False
    class Session:
        info=SimpleNamespace(host='/wrong' if bad=='host' else policy.database_host,
            port=1 if bad=='port' else policy.database_port)
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def transaction(self):return Transaction()
        def execute(self,q):
            events.append(q)
            if q.startswith('SELECT current_user'):
                self.row=dict(actual=probe.APP,session=probe.APP,database=policy.database_name,oid=4242,superuser=False)
            elif q==probe.FUNCTION_QUERY:
                raise (WrongSQLState if bad=='wrong_sqlstate' else psycopg.errors.InsufficientPrivilege)('SYNTHETIC_PRIVATE_DENIAL')
            elif q=='SELECT 1 value':
                assert events[-2]=='rollback'
                self.row={'value':0}
            else:raise AssertionError('UNEXPECTED_QUERY')
            return self
        def fetchone(self):return self.row
    monkeypatch.setattr(psycopg,'connect',lambda *a,**kw:Session())
    with pytest.raises((AssertionError,psycopg.errors.InsufficientPrivilege)):
        probe.role_call('dbname=synthetic',probe.APP,SimpleNamespace(policy=policy),False)
    if bad in ('host','port'):assert probe.FUNCTION_QUERY not in events
    if bad=='wrong_sqlstate':assert 'SELECT 1 value' not in events

@pytest.mark.parametrize('role',[probe.APP,probe.WRITER])
def test_actual_role_connection_preserves_explicit_private_libpq_options(monkeypatch,role):
    tree=ast.parse((ROOT/'scripts/catalog_only/probe.py').read_text())
    run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    maintenance=next(n for n in ast.walk(run) if isinstance(n,ast.Assign) and
        any(isinstance(t,ast.Name) and t.id=='maintenance' for t in n.targets))
    socket=Path('/synthetic/socket');passfile=Path('/synthetic/empty.pgpass')
    dsn=eval(compile(ast.Expression(maintenance.value),'actual_maintenance_dsn','eval'),
        dict(make_conninfo=psycopg.conninfo.make_conninfo,socket=socket,passfile=passfile,OWNER=probe.OWNER))
    owner_dsn=psycopg.conninfo.make_conninfo(dsn,dbname='fixture_'+'a'*32)
    policy=SimpleNamespace(database_host=str(socket),database_port=55441,
        database_name='fixture_'+'a'*32,database_oid=4242,system_identifier='1234')
    seen=[]
    class Session:
        info=SimpleNamespace(host=str(socket),port=55441)
        def __enter__(self):return self
        def __exit__(self,*a):return False
        def transaction(self):return self
        def execute(self,q):
            self.row=(dict(actual=role,session=role,database=policy.database_name,oid=4242,superuser=False)
                if q.startswith('SELECT current_user') else {'value':'1234'})
            return self
        def fetchone(self):return self.row
    def connect(actual,**kwargs):
        parsed=psycopg.conninfo.conninfo_to_dict(actual);seen.append(parsed)
        assert parsed['user']==role and parsed['dbname']==policy.database_name
        assert parsed['passfile']==str(passfile)
        assert parsed['sslmode']==parsed['gssencmode']=='disable'
        assert not set(parsed)&{'password','service','sslkey','sslcert','hostaddr'}
        return Session()
    monkeypatch.setattr(psycopg,'connect',connect)
    probe.role_call(owner_dsn,role,SimpleNamespace(policy=policy),True)
    assert len(seen)==1

def test_actual_empty_passfile_creation_is_exclusive_without_existing_file_read():
    tree=ast.parse((ROOT/'scripts/catalog_only/probe.py').read_text())
    run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
    outer=next(n for n in run.body if isinstance(n,ast.Try));body=outer.body
    index=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and
        any(isinstance(t,ast.Name) and t.id=='passfile' for t in n.targets))
    calls=[]
    fakeos=SimpleNamespace(O_WRONLY=os.O_WRONLY,O_CREAT=os.O_CREAT,O_EXCL=os.O_EXCL,
        open=lambda *a:(calls.append(('open',a)) or 73),close=lambda fd:calls.append(('close',fd)))
    exec(compile(ast.Module(body=deepcopy(body[index:index+3]),type_ignores=[]),'actual_empty_passfile_creation','exec'),
        dict(root=Path('/synthetic'),os=fakeos))
    assert calls==[('open',(Path('/synthetic/empty.pgpass'),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)),('close',73)]

def test_native_probe_output_cannot_bypass_private_output_boundary(monkeypatch,tmp_path,capsys):
    monkeypatch.setattr(boot,'gate',lambda *a:SHA)
    monkeypatch.setattr(boot,'open',lambda *a,**kw:io.StringIO(),raising=False)
    monkeypatch.setattr(boot.tempfile,'mkdtemp',lambda **kw:str(tmp_path))
    monkeypatch.setattr(boot.subprocess,'run',lambda *a,**kw:None)
    monkeypatch.setattr(sys,'path',list(sys.path))
    def run(root,sha):
        os.write(1,b'SYNTHETIC_NATIVE_PRIVATE_STDOUT\n')
        os.write(2,b'SYNTHETIC_NATIVE_PRIVATE_STDERR\n')
        value=boot.initial(sha);value['cases']={k:'PASS' for k in boot.CASES};return value
    monkeypatch.setattr(probe,'run',run)
    public=tmp_path/'external-fd-capture.log'
    with public.open('wb') as capture:
        saved=[os.dup(1),os.dup(2)]
        try:
            os.dup2(capture.fileno(),1);os.dup2(capture.fileno(),2)
            assert boot.bootstrap(SHA)==0
        finally:
            for fd,previous in zip((1,2),saved):os.dup2(previous,fd);os.close(previous)
    assert public.read_bytes()==b''
    captured=capsys.readouterr();assert captured.err=='' and 'SYNTHETIC_NATIVE_PRIVATE' not in captured.out
    assert 'SYNTHETIC_NATIVE_PRIVATE_STDOUT' in (tmp_path/'probe.log').read_text()
    assert 'SYNTHETIC_NATIVE_PRIVATE_STDERR' in (tmp_path/'probe.log').read_text()
