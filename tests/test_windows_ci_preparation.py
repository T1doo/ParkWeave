"""CI plan safety/guard and mocked wire/orchestration, never native Windows PASS."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch
import pytest

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'scripts/windows_ci'
def module(name):
    spec=importlib.util.spec_from_file_location('ci_'+name,DIRECTORY/(name+'.py'));result=importlib.util.module_from_spec(spec)
    sys.path.insert(0,str(DIRECTORY))
    try:spec.loader.exec_module(result)
    finally:sys.path.remove(str(DIRECTORY))
    return result

@pytest.mark.parametrize('file,args',[('server_candidate_probe',['--fixture-dir','uncreated']),('native_suite',['--report','uncreated/report.json'])])
def test_ci_python_guards_refuse_linux_without_writes(tmp_path,file,args):
    if os.name=='nt':pytest.skip('Linux guard oracle only; native Server execution separate')
    p=subprocess.run([sys.executable,str(DIRECTORY/(file+'.py')),*args],cwd=tmp_path,capture_output=True,text=True)
    assert p.returncode==2 and 'NOT_RUN: native Server2025' in p.stdout
    assert list(tmp_path.iterdir())==[]

@pytest.mark.parametrize('product,build,accepted',[(1,26100,False),(3,20348,False),(3,26100,True),(2,26100,True)])
def test_server_guard_checks_actual_product_type_and_build(product,build,accepted):
    m=module('server_candidate_probe')
    with patch.object(m.os,'name','nt'),patch.object(m.sys,'version_info',(3,12,10)),patch.object(m.sys,'getwindowsversion',lambda:SimpleNamespace(product_type=product,build=build),create=True):
        if accepted:m.require_server()
        else:
            with pytest.raises(RuntimeError):m.require_server()

def test_ci_workflow_scope_is_narrow_read_only_and_unpublished():
    text=(ROOT/'.github/workflows/windows-server-engineering.yml').read_text()
    assert 'branches: [dev/f1-foundation]' in text and 'contents: read' in text and 'runs-on: windows-2025' in text
    assert 'persist-credentials: false' in text and 'timeout-minutes: 25' in text and 'if: always()' in text
    for prohibited in ('secrets.','actions/cache','upload-artifact','pull_request_target','workflow_dispatch:'):
        assert prohibited not in text

def test_ci_scripts_only_new_cluster_no_service_uac_policy_mutation():
    text=(DIRECTORY/'Engineering.ps1').read_text()
    assert "'--auth-host=trust'" in text and '-h 127.0.0.1' in text and 'parkweave-server-ci-' in text
    assert 'Get-OwnedState' in text and 'Get-ItemProperty' in text and 'EnableLUA' in text
    for prohibited in ('Set-ExecutionPolicy','Set-ItemProperty','Start-Service','Stop-Service','Remove-Item','netsh','Invoke-Expression','PGPASSWORD','root password'):
        assert prohibited not in text
    assert 'no version spoof' in (DIRECTORY/'server_candidate_probe.py').read_text()
    guard=(ROOT/'scripts/windows/file_candidate_probe.py').read_text();assert "platform.release()!='11'" in guard

def test_chromedriver_commands_loopback_json_and_error_rejection():
    m=module('browser_smoke');driver=m.LocalDriver(54321);requests=[]
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'value':{'error':'unknown error'}}).encode()
    class Opener:
        def open(self,request,timeout):requests.append(request);return Response()
    driver.opener=Opener()
    with pytest.raises(RuntimeError):driver.call('/session','POST',{'fixture':'SYNTHETIC'})
    assert requests[0].full_url=='http://127.0.0.1:54321/session' and json.loads(requests[0].data)=={'fixture':'SYNTHETIC'}

def test_browser_process_requires_explicit_native_binding():
    m=module('browser_smoke')
    if os.name!='nt':
        with pytest.raises(RuntimeError,match='NOT_RUN'):m.run_browser(ROOT,'synthetic')
    source=(DIRECTORY/'browser_smoke.py').read_text()
    assert '--headless=new' in source and '--disable-background-networking' in source
    assert '--no-sandbox' not in source and '--disable-web-security' not in source
    assert 'env=minimal_environment(os.environ)' in source
    fake={'PATH':'SYNTHETIC-path','SystemRoot':'SYNTHETIC-root','GITHUB_TOKEN':'SYNTHETIC','PARKWEAVE_DSN':'SYNTHETIC','PARKWEAVE_INTERN_API_TOKEN':'SYNTHETIC'}
    assert m.minimal_environment(fake)=={'PATH':'SYNTHETIC-path','SystemRoot':'SYNTHETIC-root'}

def test_suite_keeps_independent_checks_after_setup_failure(tmp_path,monkeypatch):
    m=module('native_suite');m.REPO=tmp_path;m.require_server=lambda:None
    monkeypatch.setattr(m.sys,'executable',str(tmp_path/'.venv-windows/Scripts/python.exe'))
    monkeypatch.setattr(m.sys,'argv',['native_suite','--report',str(tmp_path/'summary.json')])
    monkeypatch.setattr(m.os,'environ',{'PARKWEAVE_OWNER_DSN':'SYNTHETIC','PARKWEAVE_DSN':'SYNTHETIC','PARKWEAVE_TEST_OWNER_DSN':'SYNTHETIC'})
    commands=[]
    def run(command,**kwargs):
        commands.append(command)
        if 'Setup.ps1' in ' '.join(command):
            assert kwargs['timeout']==120
            return SimpleNamespace(returncode=1,stdout='',stderr='')
        if 'scripts/run_acceptance.py' in command:
            assert kwargs['timeout']==600
            Path(command[-1]).write_text(json.dumps({'engineering_total_counts':{'PASS':1,'FAIL':0,'SKIP':0},'whole_AT_EX':'NOT_RUN'}));return SimpleNamespace(returncode=0,stdout='',stderr='')
        if 'scripts/windows/file_candidate_probe.py' in command:return SimpleNamespace(returncode=1,stdout='NOT_RUN: explicit native Windows11',stderr='')
        return SimpleNamespace(returncode=1,stdout='',stderr='')
    monkeypatch.setattr(m.subprocess,'run',run)
    assert m.main()==1
    result=json.loads((tmp_path/'summary.json').read_text());names=[r['case'] for r in result['cases']]
    assert 'full_engineering_regression' in names and 'Win11_guard_refuses_Server' in names and 'separate_Server_candidate_oracles' in names
    assert result['production_R4']=='DISABLED' and result['whole_AT_EX']=='NOT_RUN'

def test_blocker_record_does_not_invent_http_code_or_permissions():
    result=json.loads((ROOT/'docs/F1/evidence/eng012-actions-blocker.json').read_text())
    assert result['exit_code']==1 and result['numeric_http_status'] is None
    assert result['workflow_write_permission']=='NOT_TESTED' and result['identity_or_route_changed'] is False
    assert '/actions/runs?' in result['target_api'] and result['complete_non_sensitive_stderr'].endswith(': Forbidden\n')
