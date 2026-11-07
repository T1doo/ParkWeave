import zipfile
import json
import os
import subprocess
import sys
from types import SimpleNamespace
import pytest
from scripts.windows_ci import native_candidate_build as build
from scripts.windows_ci import native_candidate_launch as launch
from scripts.windows_ci.native_business_window import WindowRefused


def test_compiler_platform_is_explicit_and_closed():
    assert build.compiler_layout('nt')==('zig-x86_64-windows-0.15.2.zip','zig-x86_64-windows-0.15.2/zig.exe')
    assert build.compiler_layout('posix')==('zig-x86_64-linux-0.15.2.tar.xz','zig-x86_64-linux-0.15.2/zig')
    with pytest.raises(WindowRefused):build.compiler_layout('unknown')


@pytest.mark.parametrize('name',['../outside','zig-x86_64-windows-0.15.2/../outside','zig-x86_64-windows-0.15.2/name:stream'])
def test_windows_compiler_archive_refuses_path_escape_before_extraction(tmp_path,name):
    archive=tmp_path/'compiler.zip';destination=tmp_path/'out'
    with zipfile.ZipFile(archive,'w') as z:z.writestr(name,b'not executable')
    with pytest.raises(WindowRefused):build.extract_compiler(archive,destination)
    assert not destination.exists()


def test_builder_child_excludes_pg_without_changing_parent_or_proxy_policy(monkeypatch):
    for key in list(os.environ):
        if key.upper().startswith('PG'):monkeypatch.delenv(key)
    monkeypatch.setenv('PGDATA','synthetic-unrelated-database')
    monkeypatch.setenv('PgBin','synthetic-system-binaries')
    monkeypatch.setenv('HTTPS_PROXY','http://synthetic-proxy.invalid:8888')
    monkeypatch.setenv('SSL_CERT_FILE','synthetic-ca.pem')
    before=dict(os.environ)
    result=subprocess.run([sys.executable,'-I','-B','-S','-c',
        "import os,json,sys;print(json.dumps(dict(pg=[k for k in os.environ if k.upper().startswith('PG')],proxy=os.environ['HTTPS_PROXY'],ca=os.environ['SSL_CERT_FILE'],isolated=sys.flags.isolated,no_site=sys.flags.no_site,no_bytecode=sys.dont_write_bytecode)))"],
        env=launch.builder_environment(os.environ),capture_output=True,text=True,check=True)
    assert json.loads(result.stdout)==dict(pg=[],proxy=before['HTTPS_PROXY'],ca='synthetic-ca.pem',isolated=1,no_site=1,no_bytecode=True)
    assert dict(os.environ)==before


def test_direct_builder_still_refuses_ambient_pg_before_git(monkeypatch):
    window=SimpleNamespace(repository='T1doo/ParkWeave',ref='refs/heads/codex/windows-closure-20261105',
        run_number=19,operations=(),run_id=None)
    monkeypatch.setattr(build,'_record',lambda:(window,b''))
    monkeypatch.setenv('PGDATA','synthetic-unrelated-database')
    monkeypatch.setattr(build.subprocess,'check_output',lambda *a,**kw:pytest.fail('Git before admission'))
    with pytest.raises(build.CandidateBuildRefused) as error:build.source_window()
    assert error.value.stage=='AMBIENT_PG_ENVIRONMENT'


def test_launcher_has_one_fixed_child_and_returns_failure_without_retry(monkeypatch):
    calls=[]
    def run(command,**kwargs):
        calls.append((command,kwargs));return SimpleNamespace(returncode=2)
    monkeypatch.setattr(launch.subprocess,'run',run)
    assert launch.main()==2
    assert len(calls)==1
    command,kwargs=calls[0]
    assert command==[sys.executable,'-I','-B','-S',str(launch.Path(launch.__file__).with_name('native_candidate_build.py'))]
    assert not any(k.upper().startswith('PG') for k in kwargs['env'])
    assert kwargs['timeout']==340
