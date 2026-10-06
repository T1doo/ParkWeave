"""SYNTHETIC fault doubles on Linux; never native Windows acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
import pytest
from test_windows_ci_preparation import module, ROOT, DIRECTORY

APP='host=127.0.0.1 dbname=parkweave user=parkweave_app'
CONFIG={'PARKWEAVE_DSN':APP,'PARKWEAVE_OWNER_DSN':'SYNTHETIC-owner','PARKWEAVE_TEST_OWNER_DSN':'SYNTHETIC-test-owner'}

@pytest.mark.parametrize('phase,keys', [('setup',{'PARKWEAVE_DSN','PARKWEAVE_OWNER_DSN'}),('doctor',{'PARKWEAVE_DSN'}),('start',{'PARKWEAVE_DSN'}),('status',{'PARKWEAVE_DSN'}),('regression',{'PARKWEAVE_TEST_OWNER_DSN'}),('stop',set()),('file_probe',set()),('guard',set()),('browser',set())])
def test_phase_environment_only_reads_required_configuration(phase,keys):
    m=module('child_environment');reads=[]
    class Config(dict):
        def __getitem__(self,key):reads.append(key);return super().__getitem__(key)
    class Source(dict):
        def __getitem__(self,key):
            assert key=='PATH', 'must not read synthetic hidden credential'
            return super().__getitem__(key)
    source=Source(PATH='synthetic-path',PGPASSWORD='SYNTHETIC',GITHUB_TOKEN='SYNTHETIC',PARKWEAVE_OWNER_DSN='SYNTHETIC')
    env=m.command_environment(source,Config(CONFIG),phase)
    assert set(reads)==keys and set(env)==keys|{'PATH'}

@pytest.mark.parametrize('dsn',[APP.replace('parkweave_app','park_ci_owner'),APP.replace('dbname=parkweave','dbname=postgres'),APP+' service=untrusted',APP+" options='-c role=park_ci_owner'",APP.replace('127.0.0.1','remote.invalid')])
def test_owner_or_indirect_app_binding_refused(dsn):
    m=module('child_environment')
    with pytest.raises(ValueError):m.command_environment({},dict(CONFIG,PARKWEAVE_DSN=dsn),'start')

@pytest.mark.parametrize('delete_failure,exited',[(False,False),(True,False),(False,True)])
def test_browser_timeout_cleanup_order_preserves_primary(delete_failure,exited):
    m=module('browser_smoke');events=[]
    class Profile:
        name='SYNTHETIC-owned-profile'
        def __init__(self,**kw):pass
        def cleanup(self):events.append('profile')
    class Proc:
        def poll(self):return 0 if exited else None
        def terminate(self):events.append('terminate')
        def wait(self,timeout):assert timeout==10;events.append('wait')
    class Driver:
        session='SYNTHETIC-owned-session'
        def __init__(self,port):pass
        def call(self,path,method):
            assert path=='/session/SYNTHETIC-owned-session' and method=='DELETE';events.append('session')
            if delete_failure:raise OSError('SYNTHETIC')
    primary=subprocess.TimeoutExpired('SYNTHETIC-browser',15)
    with patch.object(m.tempfile,'TemporaryDirectory',Profile),patch.object(m.subprocess,'Popen',return_value=Proc()),patch.object(m,'LocalDriver',Driver):
        with pytest.raises(subprocess.TimeoutExpired) as error:
            with m.owned_browser('SYNTHETIC-driver',12345):raise primary
    assert error.value is primary
    assert events==(['session','profile'] if exited else ['session','terminate','wait','profile'])
    if delete_failure:assert 'OSError' in primary.__notes__[0]

def test_api_worker_environment_uses_same_minimal_filter():
    # Verify actual product launch sites and actual filter with synthetic poison.
    source=(ROOT/'scripts/windows/lifecycle.py').read_text()
    assert 'for command in commands:' in source and 'env=app_environment(dsn,os.environ)' in source
    spec=__import__('importlib.util',fromlist=['util'])
    definition=spec.spec_from_file_location('eng013_lifecycle',ROOT/'scripts/windows/lifecycle.py')
    m=spec.module_from_spec(definition);definition.loader.exec_module(m)
    poison={'PATH':os.environ.get('PATH',''),'PARKWEAVE_OWNER_DSN':'SYNTHETIC-owner','PARKWEAVE_TEST_OWNER_DSN':'SYNTHETIC-test-owner','PGPASSWORD':'SYNTHETIC','GITHUB_TOKEN':'SYNTHETIC'}
    with patch.dict(os.environ,poison,clear=True):env=m.app_environment(APP,os.environ)
    assert env['PARKWEAVE_DSN']==APP and not set(poison.keys()-{'PATH'})&env.keys()
    child=subprocess.run([sys.executable,'-c','import os,json;print(json.dumps(sorted(os.environ)))'],env=env,capture_output=True,text=True,check=True)
    assert not set(poison.keys()-{'PATH'})&set(json.loads(child.stdout))

def test_cluster_control_faults_with_no_real_postgres(tmp_path):
    pwsh=ROOT/'.cache/powershell/bin/pwsh'
    if not pwsh.exists():pytest.skip('portable PowerShell unavailable; fault oracle NOT_RUN')
    script=tmp_path/'faults.ps1';script.write_text(r'''
param($ModulePath,$FixtureTemp)
$ErrorActionPreference='Stop'
Import-Module $ModulePath -Force
$m=Get-Module ClusterControl
& $m { $script:commands=[Collections.Generic.List[object]]::new(); $script:exits=[Collections.Generic.Queue[int]]::new()
 function script:Invoke-ClusterCommand { param($Exe,$Arguments) $script:commands.Add(@($Exe,$Arguments)); if (!$script:exits.Count) { throw 'Unexpected synthetic command' }; return $script:exits.Dequeue() }
}
$root=Join-Path $FixtureTemp ('parkweave-server-ci-'+[Guid]::NewGuid().ToString())
$bin=Join-Path $FixtureTemp 'SYNTHETIC-bin'
New-Item -ItemType Directory -Path (Join-Path $root 'data'),$bin | Out-Null
$original=@{bin=$bin;data=(Join-Path $root 'data');port=54329;project='ParkWeave';scope='SYNTHETIC_SERVER_ENGINEERING'}
function Write-State($state) { $state | ConvertTo-Json | Set-Content (Join-Path $root 'cluster-state.json') }
function Reset-Commands($codes) { & $m {param($codes) $script:commands.Clear();$script:exits.Clear();foreach($code in $codes){$script:exits.Enqueue($code)}} $codes }
function Count-Commands { & $m {$script:commands.Count} }
function Check($condition,$label) { if (!$condition) { throw ('Failed synthetic oracle: '+$label) } }
Write-State $original
Reset-Commands @(0)
$r=Start-OwnedCluster $root $FixtureTemp $bin
Check ($r.status -eq 'STARTED' -and (Count-Commands) -eq 1) 'positive start'
foreach($pair in @(@(3,'NOT_RUNNING'),@(0,'STOPPED'),@(2,'REFUSED_OR_FAILED'))) {
 $codes=if($pair[0] -eq 0){@(1,0,0)}else{@(1,$pair[0])};Reset-Commands $codes
 $r=Start-OwnedCluster $root $FixtureTemp $bin
 Check ($r.status -eq 'START_FAILED' -and $r.exit_code -eq 1 -and $r.cleanup.status -eq $pair[1]) 'failed start cleanup'
 Check ((Count-Commands) -eq $codes.Count) 'no blind fallback command'
}
Reset-Commands @(3);$r=Stop-OwnedCluster $root $FixtureTemp $bin
Check ($r.status -eq 'NOT_RUNNING' -and (Count-Commands) -eq 1) 'idempotent stop'
Reset-Commands @(0,1);$refused=$false
try {Stop-OwnedCluster $root $FixtureTemp $bin|Out-Null}catch{$refused=$true}
Check ($refused -and (Count-Commands) -eq 2) 'stop failure no fallback'
foreach($key in @('project','scope','data','bin','port','extra')) {
 $state=$original.Clone();$state[$key]='SYNTHETIC-tamper';Write-State $state;Reset-Commands @();$refused=$false
 try {Stop-OwnedCluster $root $FixtureTemp $bin|Out-Null}catch{$refused=$true}
 Check ($refused -and (Count-Commands) -eq 0) ('tamper '+$key)
}
Write-State $original
Reset-Commands @();$refused=$false
try {Stop-OwnedCluster $FixtureTemp $FixtureTemp $bin|Out-Null}catch{$refused=$true}
Check ($refused -and (Count-Commands) -eq 0) 'outside owned root'
Write-State $original
# Start succeeds, then state changes: Stop must re-read before any command.
Reset-Commands @(0);$r=Start-OwnedCluster $root $FixtureTemp $bin
$state=$original.Clone();$state.data=Join-Path $FixtureTemp 'SYNTHETIC-foreign';Write-State $state
$refused=$false;try{Stop-OwnedCluster $root $FixtureTemp $bin|Out-Null}catch{$refused=$true}
Check ($refused -and (Count-Commands) -eq 1) 'tamper after start'
foreach($port in @(1023,65536,'54329')) {
 $state=$original.Clone();$state.port=$port;Write-State $state;Reset-Commands @();$refused=$false
 try{Get-OwnedCluster $root $FixtureTemp $bin|Out-Null}catch{$refused=$true}
 Check ($refused -and (Count-Commands) -eq 0) 'port type range'
}
@{scope='SYNTHETIC_LOCAL_COMMAND_DOUBLE';real_postgres_commands=0;oracles=17;result='PASS'}|ConvertTo-Json -Compress
''')
    from parkweave.process_env import minimal_environment
    env=minimal_environment(os.environ,XDG_CACHE_HOME=str(tmp_path/'cache'),XDG_CONFIG_HOME=str(tmp_path/'config'),XDG_DATA_HOME=str(tmp_path/'data'))
    result=subprocess.run([str(pwsh),'-NoProfile','-NonInteractive','-File',str(script),str(DIRECTORY/'ClusterControl.psm1'),str(tmp_path)],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['real_postgres_commands']==0

def test_actual_api_and_worker_launch_arguments_have_no_owner_env(tmp_path,monkeypatch):
    import importlib.util
    import psutil
    import urllib.request
    spec=importlib.util.spec_from_file_location('eng013_launch',ROOT/'scripts/windows/lifecycle.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.RUNTIME=tmp_path;m.STATE=tmp_path/'owned-state.json'
    monkeypatch.setattr(m,'load_config',lambda:{'python':'SYNTHETIC-python','port':8765})
    monkeypatch.setattr(m,'check_python',lambda value:None)
    monkeypatch.setattr(m,'check_dsn_scope',lambda value,app:None)
    monkeypatch.setattr(m,'port_available',lambda value:None)
    monkeypatch.setattr(m,'protect_private_root',lambda value:None)
    monkeypatch.setattr(m,'needed_environment',lambda name:APP)
    monkeypatch.setattr(m.os,'environ',{'PATH':'SYNTHETIC','PARKWEAVE_OWNER_DSN':'SYNTHETIC-owner','PARKWEAVE_TEST_OWNER_DSN':'SYNTHETIC-test','PGPASSWORD':'SYNTHETIC','GITHUB_TOKEN':'SYNTHETIC'})
    launches=[]
    class Proc:
        def __init__(self,command,**kwargs):self.pid=700+len(launches);launches.append((command,kwargs['env']))
        def create_time(self):return 1.0
        def poll(self):return None
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return b'{"execution_mode":"LOCAL","model":"MODEL_MOCK","process_id":700}'
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr(psutil,'Popen',Proc);monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    m.start()
    assert len(launches)==2 and 'uvicorn' in launches[0][0] and 'parkweave.worker' in launches[1][0]
    for _,env in launches:assert env=={'PATH':'SYNTHETIC','PARKWEAVE_DSN':APP,'PARKWEAVE_MODE':'LOCAL'}

def test_browser_timeout_stops_owned_services_and_keeps_independent_phases(tmp_path,monkeypatch):
    from types import SimpleNamespace
    import urllib.request
    m=module('native_suite');m.REPO=tmp_path;m.require_server=lambda:None
    # Synthetic parent binding and its verified child report are independent of
    # the injected browser timeout; missing source authority must still fail.
    binding={'run_id':'1','run_attempt':'1','head_sha':'a'*40,'cluster_id':'00000000-0000-0000-0000-000000000001'}
    monkeypatch.setattr(m,'current_binding',lambda *args:dict(binding))
    monkeypatch.setattr(m.sys,'executable',str(tmp_path/'.venv-windows/Scripts/python.exe'))
    monkeypatch.setattr(m.sys,'argv',['native_suite','--report',str(tmp_path/'summary.json')])
    monkeypatch.setattr(m.os,'environ',dict(CONFIG))
    runtime=tmp_path/'.runtime';runtime.mkdir();state=runtime/'windows-processes.json';commands=[];setup_count=0
    def run(command,**kwargs):
        nonlocal setup_count
        joined=' '.join(command);commands.append(joined)
        env=kwargs['env']
        if 'Setup.ps1' in joined:
            setup_count+=1
            if setup_count==2:return SimpleNamespace(returncode=1,stdout='',stderr='existing configuration protected')
            (runtime/'synthetic-sessions.json').write_text('{"fixture-a":"SYNTHETIC"}')
            (runtime/'windows-config.json').write_text('{"scope":"SYNTHETIC"}')
        elif 'Start.ps1' in joined:
            assert 'PARKWEAVE_OWNER_DSN' not in env and 'PARKWEAVE_TEST_OWNER_DSN' not in env
            state.write_text('{"scope":"SYNTHETIC"}')
        elif 'Stop.ps1' in joined:
            assert not any(key.startswith('PARKWEAVE_') for key in env);state.unlink(missing_ok=True)
        elif 'Status.ps1' in joined:
            return SimpleNamespace(returncode=0,stdout=json.dumps({'project':'ParkWeave','model':'DISABLED','port':8765,'processes':[{'pid':700,'identity_matches':True},{'pid':701,'identity_matches':True}]}),stderr='')
        elif 'scripts/run_acceptance.py' in joined:
            assert set(key for key in env if key.startswith('PARKWEAVE_'))=={'PARKWEAVE_TEST_OWNER_DSN'}
            assert command[command.index('--source-head')+1]==binding['head_sha']
            Path(command[command.index('--report')+1]).write_text(json.dumps({'engineering_total_counts':{'PASS':1,'FAIL':0,'SKIP':0},'whole_AT_EX':'NOT_RUN',
                'source_binding':{'state':'AVAILABLE','head_sha':binding['head_sha']}}))
        elif 'file_candidate_probe.py' in joined:return SimpleNamespace(returncode=1,stdout='NOT_RUN: explicit native Windows11',stderr='')
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    class Response:
        def __init__(self,request):self.request=request
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self):return json.dumps({'run_id':'synthetic-run'} if self.request.method=='POST' else {'state':'SUCCEEDED','case':{'id':'synthetic-case','state':'NEEDS_INPUT','external_acceptance':'NOT_SUBMITTED','offline_fulfillment':'NO_EVIDENCE'}}).encode()
    class Opener:
        def open(self,request,**kwargs):return Response(request)
    def timeout(*args):raise subprocess.TimeoutExpired('SYNTHETIC-browser',15)
    monkeypatch.setattr(m.subprocess,'run',run);monkeypatch.setattr(urllib.request,'build_opener',lambda *args:Opener())
    monkeypatch.setitem(sys.modules,'browser_smoke',SimpleNamespace(run_browser=timeout))
    assert m.main()==1
    summary=json.loads((tmp_path/'summary.json').read_text());cases={row['case']:row for row in summary['cases']}
    assert cases['lifecycle_exception']['category']=='TimeoutExpired' and cases['final_Stop_owned_services']['status']=='PASS'
    assert all(cases[key]['status']=='PASS' for key in ('full_engineering_regression','Win11_guard_refuses_Server','separate_Server_candidate_oracles'))
    assert not state.exists() and sum('Stop.ps1' in command for command in commands)==2

@pytest.mark.parametrize('fault',['popen','wait','profile'])
def test_browser_cleanup_fault_is_visible_and_never_hides_primary(fault):
    m=module('browser_smoke');events=[]
    class Profile:
        name='SYNTHETIC-profile'
        def __init__(self,**kwargs):pass
        def cleanup(self):
            events.append('profile')
            if fault=='profile':raise PermissionError('SYNTHETIC')
    class Proc:
        def poll(self):return None
        def terminate(self):events.append('terminate')
        def wait(self,timeout):
            events.append('wait')
            if fault=='wait':raise subprocess.TimeoutExpired('SYNTHETIC-cleanup',10)
    class Driver:
        session=None
        def __init__(self,*args):pass
    def popen(*args,**kwargs):
        if fault=='popen':raise OSError('SYNTHETIC-popen')
        return Proc()
    with patch.object(m.tempfile,'TemporaryDirectory',Profile),patch.object(m.subprocess,'Popen',popen),patch.object(m,'LocalDriver',Driver):
        if fault=='popen':
            with pytest.raises(OSError,match='SYNTHETIC-popen'):
                with m.owned_browser('SYNTHETIC',12345):pytest.fail('not reached')
            assert events==['profile']
        else:
            primary=subprocess.TimeoutExpired('SYNTHETIC-body',15)
            with pytest.raises(subprocess.TimeoutExpired) as error:
                with m.owned_browser('SYNTHETIC',12345):raise primary
            assert error.value is primary and primary.__notes__ and events==['terminate','wait','profile']
            summary=module('native_suite').exception_row('lifecycle_exception',primary)
            assert summary['owned_browser_cleanup_failures']==(['TimeoutExpired'] if fault=='wait' else ['PermissionError'])
            assert 'SYNTHETIC-body' not in json.dumps(summary) and 'SYNTHETIC-cleanup' not in json.dumps(summary)

@pytest.mark.parametrize('fault',['wait','profile'])
def test_successful_browser_body_cleanup_failure_reaches_safe_suite_summary(fault):
    m=module('browser_smoke')
    class Profile:
        name='SYNTHETIC-profile'
        def __init__(self,**kwargs):pass
        def cleanup(self):
            if fault=='profile':raise PermissionError('SYNTHETIC-private-cleanup')
    class Proc:
        def poll(self):return None
        def terminate(self):pass
        def wait(self,timeout):
            if fault=='wait':raise subprocess.TimeoutExpired('SYNTHETIC-private-command',10)
    class Driver:
        session=None
        def __init__(self,*args):pass
    with patch.object(m.tempfile,'TemporaryDirectory',Profile),patch.object(m.subprocess,'Popen',lambda *args,**kwargs:Proc()),patch.object(m,'LocalDriver',Driver):
        with pytest.raises(RuntimeError) as error:
            with m.owned_browser('SYNTHETIC',12345):pass
    summary=module('native_suite').exception_row('lifecycle_exception',error.value)
    assert summary['category']=='RuntimeError' and summary['owned_browser_cleanup_failures']==(['TimeoutExpired'] if fault=='wait' else ['PermissionError'])
    assert 'SYNTHETIC-private' not in json.dumps(summary)
