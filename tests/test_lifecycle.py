"""Shared safety policies and Linux CLI refusal, NOT native PowerShell execution."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

PATH=Path(__file__).resolve().parents[1]/'scripts/windows/lifecycle.py'
spec=importlib.util.spec_from_file_location('parkweave_lifecycle',PATH)
lifecycle=importlib.util.module_from_spec(spec);spec.loader.exec_module(lifecycle)


def test_native_cli_cannot_run_on_linux(tmp_path):
    if os.name=='nt':pytest.skip('Linux refusal oracle; native lifecycle manual gates separate')
    for action in lifecycle.ACTIONS:
        r=subprocess.run([sys.executable,str(PATH),action],cwd=tmp_path,capture_output=True,text=True,env=lifecycle.minimal_environment(os.environ))
        assert r.returncode==1 and 'NOT_RUN: native Windows required' in r.stderr
        assert list(tmp_path.iterdir())==[]


def test_config_write_is_exclusive_and_no_secret_fields(tmp_path):
    python=tmp_path/'.venv-windows/Scripts/python.exe'
    config=lifecycle.config_template(tmp_path,python)
    lifecycle.validate_config(config,tmp_path)
    path=tmp_path/'config.json';lifecycle.write_exclusive(path,config);original=path.read_bytes()
    with pytest.raises(FileExistsError):lifecycle.write_exclusive(path,{'replace':'bad'})
    assert path.read_bytes()==original and not any('token' in k or 'dsn' in k or 'password' in k for k in config)
    for change in [{'host':'0.0.0.0'},{'database':'Sim2Act'},{'model':'LIVE'},{'data':'REAL'},{'port':80},{'python':'/bin/sh'},{'private_root':str(tmp_path.parent)}, {'extra':'x'}]:
        with pytest.raises(lifecycle.BoundaryError):lifecycle.validate_config(config|change,tmp_path)


class FakeProcess:
    def __init__(self,command,cwd,created=20):self.command,self.directory,self.created=command,cwd,created;self.terminated=False
    def cmdline(self):return self.command
    def cwd(self):return self.directory
    def create_time(self):return self.created
    def terminate(self):self.terminated=True
    def wait(self,timeout):return 0


def test_process_identity_refuses_pid_reuse_foreign_command_and_cwd(tmp_path):
    repo=tmp_path.resolve();command=[str(repo/'.venv-windows/Scripts/python.exe'),'-m','parkweave.worker']
    record={'pid':42,'created':20,'command':command}
    owned=FakeProcess(command,str(repo))
    assert lifecycle.stop_record(record,repo,lambda _:owned)=='STOPPED' and owned.terminated
    for proc,rec in [(FakeProcess(command,str(repo),created=21),record),(FakeProcess(command,str(repo.parent)),record),
                     (FakeProcess(['python','-m','Sim2Act'],str(repo)),record),
                     (FakeProcess(['python','-m','http.server'],str(repo)),record|{'command':['python','-m','http.server']})]:
        assert lifecycle.stop_record(rec,repo,lambda _:proc)=='FOREIGN_REFUSED' and not proc.terminated
    assert lifecycle.stop_record(record,repo,lambda _:(_ for _ in ()).throw(ProcessLookupError()))=='ABSENT'


def test_child_environment_drops_owner_and_model_secrets():
    fake={'PARKWEAVE_OWNER_DSN':'fake-owner','PARKWEAVE_TEST_OWNER_DSN':'fake-test-owner','PARKWEAVE_INTERN_API_TOKEN':'fake-key',
          'INTERN_API_TOKEN':'fake-key2','PARKWEAVE_FILE_ROOT':'outside','PARKWEAVE_MODE':'FAULT_INJECTION','PATH':'fake-path'}
    env=lifecycle.app_environment('fake-app',fake)
    assert env=={'PARKWEAVE_DSN':'fake-app','PARKWEAVE_MODE':'LOCAL','PATH':'fake-path'}
    assert fake['PARKWEAVE_OWNER_DSN']=='fake-owner'  # caller mapping untouched


def test_powershell_wrappers_are_static_native_only_and_do_not_disable_security():
    root=PATH.parent
    for name in ('Doctor','Setup','Start','Status','Stop','Test'):
        s=(root/(name+'.ps1')).read_text()
        assert "-Action '"+name.lower()+"'" in s and 'Common.ps1' in s
    source='\n'.join(p.read_text() for p in root.glob('*.ps1'))
    for prohibited in ('Set-ExecutionPolicy','Bypass','Remove-Item','Stop-Process','netsh','0.0.0.0','Invoke-Expression'):
        assert prohibited not in source
    assert 'Win32NT' in source and 'Push-Location' in source and 'finally' in source


def test_inaccessible_process_is_not_treated_as_absent(tmp_path):
    import psutil
    record={'pid':42,'created':20,'command':[]}
    with pytest.raises(lifecycle.BoundaryError,match='cannot inspect'):
        lifecycle.stop_record(record,tmp_path,lambda _:(_ for _ in ()).throw(psutil.AccessDenied(42)))


def test_positive_api_identity_and_invalid_binding(tmp_path):
    repo=tmp_path.resolve();python=str(repo/'.venv-windows/Scripts/python.exe')
    command=[python,'-m','uvicorn','parkweave.api:configured_app','--factory','--host','127.0.0.1','--port','8765']
    assert lifecycle.trusted_command(command,repo)
    for bad in [command[:-1]+['80'],command[:6]+['0.0.0.0']+command[7:],command+['--reload']]:
        assert not lifecycle.trusted_command(bad,repo)


def test_environment_whitelist_never_reads_or_forwards_unrelated_keys():
    from parkweave.process_env import minimal_environment
    from collections.abc import Mapping
    class SelectiveMapping(Mapping):
        def __getitem__(self,key):
            assert key in ('PATH','TEMP'), 'unrelated environment key was read'
            return {'PATH':'safe-path','TEMP':'safe-temp'}[key]
        def __iter__(self):return iter(('PATH','TEMP','UNRELATED_SECRET'))
        def __len__(self):return 3
        def __contains__(self,key):return key in ('PATH','TEMP','UNRELATED_SECRET')
    assert minimal_environment(SelectiveMapping(),PARKWEAVE_DSN='fake-project')=={'PATH':'safe-path','TEMP':'safe-temp','PARKWEAVE_DSN':'fake-project'}


def test_windows_existing_acl_check_does_not_repair_permissions(tmp_path,monkeypatch):
    root=tmp_path/'existing';root.mkdir()
    calls=[]
    monkeypatch.setattr(lifecycle,'require_windows',lambda:None)
    monkeypatch.setattr(lifecycle.subprocess,'run',lambda command,**kwargs:calls.append((command,kwargs)) or type('R',(),{'returncode':3})())
    with pytest.raises(lifecycle.BoundaryError,match='nothing changed'):lifecycle.protect_private_root(root)
    assert len(calls)==1 and 'Get-Acl' in calls[0][0][-1] and 'Set-Acl' not in calls[0][0][-1]
    assert set(calls[0][1]['env']) <= lifecycle.minimal_environment(os.environ).keys()|{'PARKWEAVE_ACL_ROOT'}


@pytest.mark.parametrize('prior',['empty','incomplete_environment','existing_runtime','existing_configuration'])
def test_first_setup_pause_precedes_all_install_and_database_side_effects(tmp_path,monkeypatch,prior):
    """Linux callable oracle, not execution of native Windows installation."""
    repo=tmp_path/'repo';repo.mkdir();runtime=repo/'.runtime';config=runtime/'windows-config.json'
    if prior=='incomplete_environment':(repo/'.venv-windows').mkdir()
    if prior in ('existing_runtime','existing_configuration'):
        runtime.mkdir();(runtime/'synthetic-sessions.json').write_text('PRIVATE_EXISTING_SESSIONS')
    if prior=='existing_configuration':config.write_text('PRIVATE_EXISTING_CONFIG')
    monkeypatch.setattr(lifecycle,'REPO',repo);monkeypatch.setattr(lifecycle,'RUNTIME',runtime);monkeypatch.setattr(lifecycle,'CONFIG',config)
    before={str(p.relative_to(repo)):p.read_bytes() if p.is_file() else None for p in repo.rglob('*')}
    def forbidden(*args,**kwargs):raise AssertionError('installation/database/environment boundary crossed')
    for name in ('check_python','needed_environment','protect_private_root','write_exclusive','check_dsn_scope'):
        monkeypatch.setattr(lifecycle,name,forbidden)
    monkeypatch.setattr(lifecycle.subprocess,'run',forbidden)
    with pytest.raises(lifecycle.BoundaryError) as refused:lifecycle.setup()
    assert {str(p.relative_to(repo)):p.read_bytes() if p.is_file() else None for p in repo.rglob('*')}==before
    if prior=='existing_configuration':assert 'existing configuration protected' in str(refused.value)
    else:
        import lifecycle_diagnostics as diagnostic
        assert diagnostic.failure(refused.value)['boundary_reason']=='OWNER_MUTATION_PAUSED'
        assert diagnostic.failure(refused.value)['boundary_phase']=='configuration'


def test_fresh_doctor_reports_setup_pause_without_dsn_or_dependency_install(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(lifecycle,'REPO',tmp_path);monkeypatch.setattr(lifecycle,'RUNTIME',tmp_path/'.runtime');monkeypatch.setattr(lifecycle,'CONFIG',tmp_path/'.runtime/config.json')
    monkeypatch.setattr(lifecycle,'check_python',lambda value:None)  # platform/version inspection isolated
    def forbidden(*args,**kwargs):raise AssertionError('fresh Doctor must not need maintenance/DSN/install')
    monkeypatch.setattr(lifecycle,'needed_environment',forbidden);monkeypatch.setattr(lifecycle.subprocess,'run',forbidden)
    monkeypatch.setenv('PARKWEAVE_OWNER_DSN','PRIVATE_PRECHECK_DSN');monkeypatch.setenv('PARKWEAVE_INTERN_API_TOKEN','PRIVATE_PRECHECK_TOKEN')
    lifecycle.doctor();text=capsys.readouterr().out;info=json.loads(text)
    assert info['new_setup']['status']=='BLOCKED' and info['new_setup']['reason']=='OWNER_MUTATION_PAUSED'
    assert info['new_setup']['native_acceptance']=='NOT_ACCEPTED' and info['model']=='DISABLED'
    assert 'PRIVATE_PRECHECK' not in text and list(tmp_path.iterdir())==[]


def test_setup_cli_emits_fixed_pause_and_nonzero_before_side_effects(tmp_path,monkeypatch,capsys):
    import lifecycle_diagnostics as diagnostic
    monkeypatch.setattr(lifecycle,'require_windows',lambda:None)  # mock dispatch only, never native PASS
    monkeypatch.setattr(lifecycle,'CONFIG',tmp_path/'absent.json');monkeypatch.setattr(sys,'argv',['lifecycle.py','setup'])
    def forbidden(*args,**kwargs):raise AssertionError('preflight crossed install boundary')
    monkeypatch.setattr(lifecycle.subprocess,'run',forbidden)
    with pytest.raises(SystemExit) as exit:lifecycle.main()
    assert exit.value.code==1
    output=capsys.readouterr();row=diagnostic.parse(output.out,'setup')
    assert row['boundary_reason']=='OWNER_MUTATION_PAUSED' and row['boundary_phase']=='configuration'
    assert 'New native setup is paused' in output.err and str(tmp_path) not in output.out
    assert list(tmp_path.iterdir())==[]
