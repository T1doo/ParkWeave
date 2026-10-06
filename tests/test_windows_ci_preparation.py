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
    assert 'persist-credentials: false' in text and 'timeout-minutes: 25' in text and 'timeout-minutes: 2\n' in text
    assert 'actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065' in text
    assert "python-version: '3.12'" in text and "architecture: 'x64'" in text
    assert text.index('Select Python 3.12 x64') < text.index('Independent controlled Job measurement without owner helpers')
    assert text.count('runs-on:')==1 and text.count('      - name:')==4
    assert 'group: parkweave-server-engineering-${{ github.ref }}' in text and 'cancel-in-progress: false' in text
    executable='\n'.join(line for line in text.splitlines() if not line.strip().startswith('#'))
    for prohibited in ('Engineering.ps1','SetOwner','Set-Acl','pip','descriptor_readonly_probe','native_failure_oracles'):
        assert prohibited not in executable
    assert "$os.Caption -notmatch 'Windows Server 2025' -or $os.ProductType -eq 1" in executable
    assert 'python -m scripts.windows_ci.controlled_job_measurement --run-controlled' in executable
    for prohibited in ('secrets.','actions/cache','upload-artifact','pull_request_target','workflow_dispatch:'):
        assert prohibited not in text

def test_ci_scripts_only_new_cluster_no_service_uac_policy_mutation():
    text=(DIRECTORY/'Engineering.ps1').read_text()+(DIRECTORY/'ClusterControl.psm1').read_text()
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
    monkeypatch.setattr(m.os,'environ',{'PARKWEAVE_OWNER_DSN':'host=127.0.0.1 dbname=parkweave user=park_ci_owner','PARKWEAVE_DSN':'host=127.0.0.1 dbname=parkweave user=parkweave_app','PARKWEAVE_TEST_OWNER_DSN':'host=127.0.0.1 dbname=postgres user=park_ci_owner'})
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
    monkeypatch.setattr(m,'run_owned_job',lambda command,**kwargs:run(command,**kwargs))
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


@pytest.mark.parametrize('state',[
    {'project':'ParkWeave','model':'DISABLED','port':8765,'processes':[]},
    {'project':'ParkWeave','model':'DISABLED','port':8765,'processes':[{'pid':11,'identity_matches':True},{'pid':22,'identity_matches':False}]},
    {'project':'ParkWeave','model':'DISABLED','port':8765,'processes':[{'pid':11,'identity_matches':True},{'pid':11,'identity_matches':True}]},
    {'project':'foreign','model':'DISABLED','port':8765,'processes':[{'pid':11,'identity_matches':True},{'pid':22,'identity_matches':True}]},
    None,
])
def test_status_exit_success_cannot_prove_missing_foreign_or_malformed_services(state):
    m=module('native_suite');assert not m.owned_status(json.dumps(state))
    assert m.owned_status(json.dumps({'project':'ParkWeave','model':'DISABLED','port':8765,'processes':[{'pid':11,'identity_matches':True},{'pid':22,'identity_matches':True}]}))
    assert not m.owned_status('SYNTHETIC unreadable status')


@pytest.mark.parametrize('platform',['posix','nt'])
def test_suite_marks_exit_zero_status_identity_failure_and_keeps_other_phases(tmp_path,monkeypatch,platform):
    m=module('native_suite');m.REPO=tmp_path;m.require_server=lambda:None
    monkeypatch.setattr(m,'os',SimpleNamespace(name=platform,environ=m.os.environ))
    binding={'run_id':'1','run_attempt':'1','head_sha':'a'*40,'cluster_id':'synthetic'}
    monkeypatch.setattr(m,'current_binding',lambda *args:dict(binding))
    runtime=tmp_path/'.runtime';runtime.mkdir();(runtime/'synthetic-sessions.json').write_text(json.dumps({'fixture-a':'SYNTHETIC-token'}));(runtime/'windows-config.json').write_text('{}')
    monkeypatch.setattr(m.sys,'executable',str(tmp_path/'.venv-windows/Scripts/python.exe'))
    monkeypatch.setattr(m.sys,'argv',['native_suite','--report',str(tmp_path/'summary.json')])
    monkeypatch.setattr(m.os,'environ',{'PARKWEAVE_OWNER_DSN':'host=127.0.0.1 dbname=parkweave user=park_ci_owner','PARKWEAVE_DSN':'host=127.0.0.1 dbname=parkweave user=parkweave_app','PARKWEAVE_TEST_OWNER_DSN':'host=127.0.0.1 dbname=postgres user=park_ci_owner'})
    setup_count=0
    def run(command,**kwargs):
        nonlocal setup_count
        if any(str(x).endswith('Setup.ps1') for x in command):
            setup_count+=1
            return SimpleNamespace(returncode=0 if setup_count==1 else 1,stdout='',stderr='existing configuration protected')
        if any(str(x).endswith('Status.ps1') for x in command):return SimpleNamespace(returncode=0,stdout=json.dumps({'project':'ParkWeave','port':8765,'model':'DISABLED','processes':[{'pid':1,'identity_matches':False},{'pid':2,'identity_matches':True}]}),stderr='')
        if 'scripts/run_acceptance.py' in command:
            Path(command[-1]).write_text(json.dumps({'engineering_total_counts':{'PASS':1,'FAIL':0,'SKIP':0},'whole_AT_EX':'NOT_RUN','source_binding':{'state':'AVAILABLE','head_sha':binding['head_sha']}}))
        if 'scripts/windows/file_candidate_probe.py' in command:return SimpleNamespace(returncode=1,stdout='NOT_RUN: explicit native Windows11',stderr='')
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    class Response:
        def __init__(self,request):self.request=request
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'run_id':'SYNTHETIC-run'} if self.request.method=='POST' else {'state':'SUCCEEDED','case':{'id':'SYNTHETIC-case','state':'NEEDS_INPUT','external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE'}}).encode()
    class Opener:
        def open(self,request,timeout):return Response(request)
    monkeypatch.setattr(m,'run_owned_job',lambda command,**kwargs:run(command,**kwargs))
    monkeypatch.setattr(m.subprocess,'run',run);monkeypatch.setattr(m.urllib.request,'build_opener',lambda *args:Opener())
    monkeypatch.setitem(sys.modules,'browser_smoke',SimpleNamespace(run_browser=lambda *args:{'scope':'SYNTHETIC-MOCK'}))
    assert m.main()==1
    rows=json.loads((tmp_path/'summary.json').read_text())['cases'];status=next(x for x in rows if x['case']=='Status_native')
    assert status=={'case':'Status_native','status':'FAIL','exit_code':0,'reason':'OWNED_STATUS_NOT_CONFIRMED'}
    assert all(x['status']=='PASS' for x in rows if x['case']!='Status_native')


def test_case_rendering_oracle_requires_actual_goal_and_rejects_script_node():
    m=module('browser_smoke')
    class Driver:
        def __init__(self,bad):self.bad=bad
        def execute(self,script):return self.bad
    actual={'case':{'goal':m.INJECTION_GOAL}}
    m.verify_case_rendering(Driver(False),actual,json.dumps(actual))
    for record,text,bad in [(actual,'unrelated UI',False),({'case':{'goal':'different'}},json.dumps(actual),False),(actual,json.dumps(actual),True)]:
        with pytest.raises(AssertionError):m.verify_case_rendering(Driver(bad),record,text)


def test_cleanup_summary_uses_structured_categories_never_raw_exception_notes():
    m=module('native_suite');exc=RuntimeError('SYNTHETIC-private-message');exc.add_note('SYNTHETIC-private-note');exc.parkweave_owned_browser_cleanup=('TimeoutExpired','PermissionError')
    row=m.exception_row('lifecycle_exception',exc);assert row['category']=='RuntimeError' and row['owned_browser_cleanup_failures']==['TimeoutExpired','PermissionError']
    assert 'SYNTHETIC-private' not in json.dumps(row)
