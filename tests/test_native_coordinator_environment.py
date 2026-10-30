"""Real Linux PowerShell/process environment checks, not Windows acceptance."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from parkweave import process_env
from scripts.windows_ci import native_business_window as window

ROOT=Path(__file__).resolve().parents[1]
HELPER=ROOT/'scripts/windows_ci/native_coordinator_environment.ps1'


def test_windows_case_aliases_and_empty_ambient_configuration():
    source={'Path':'safe-path','SYSTEMROOT':'safe-root','SystemRoot':'safe-root',
        'TEMP':'','LANG':'','pGunknown':'not-forwarded','PGPASSWORD':'','PYTHONPATH':'not-forwarded',
        'GITHUB_TOKEN':'not-forwarded','HOME':'not-forwarded'}
    result=process_env.windows_environment(source)
    assert result=={'PATH':'safe-path','SystemRoot':'safe-root','TEMP':'','LANG':''}
    assert source['pGunknown']=='not-forwarded'
    with pytest.raises(ValueError,match='AMBIGUOUS_OS_ENVIRONMENT'):
        process_env.windows_environment({'PATH':'one','Path':'two'})
    with pytest.raises(ValueError,match='AMBIGUOUS_PROJECT_ENVIRONMENT'):
        process_env.windows_environment({},PARKWEAVE_MODE='LOCAL',parkweave_mode='other')
    assert process_env.windows_environment({'PATH':'parent'},Path='private')['PATH']=='private'


def test_platform_dispatch_keeps_posix_case_semantics(monkeypatch):
    source={'PATH':'one','Path':'two','SYSTEMROOT':'root','SystemRoot':'root'}
    monkeypatch.setattr(process_env,'os',SimpleNamespace(name='nt'))
    with pytest.raises(ValueError):process_env.minimal_environment(source)
    assert process_env.minimal_environment({'SYSTEMROOT':'root'})=={'SystemRoot':'root'}
    monkeypatch.setattr(process_env,'os',SimpleNamespace(name='posix'))
    assert process_env.minimal_environment(source)=={'PATH':'one','SYSTEMROOT':'root','SystemRoot':'root'}


def test_stage_deadlines_share_start_and_context_never_refreshes(monkeypatch):
    now=[1000.0]
    monkeypatch.setattr(window.time,'monotonic',lambda:now[0])
    monkeypatch.setenv('PARKWEAVE_TRIAL_START_MONOTONIC','995.000000000')
    value=SimpleNamespace(work_seconds=900,cleanup_seconds=60,expires_utc=time.time()+4000)
    first=window._trial_work_deadline(value);assert first==1895
    now[0]+=120
    assert window._trial_work_deadline(value)==first
    context=window.current_context()
    monkeypatch.setenv('RUNNER_TRACKING_ID','synthetic-marker')
    assert window.current_context()!=context
    now[0]=1895
    with pytest.raises(window.WindowRefused):window._trial_work_deadline(value)


@pytest.mark.parametrize('start',['','NaN','inf','1e30','2000','-1'])
def test_invalid_stage_clock_metadata_never_becomes_authority(monkeypatch,start):
    monkeypatch.setattr(window.time,'monotonic',lambda:1000.0)
    monkeypatch.setenv('PARKWEAVE_TRIAL_START_MONOTONIC',start)
    with pytest.raises(window.WindowRefused):
        window._trial_work_deadline(SimpleNamespace(work_seconds=900,cleanup_seconds=60,expires_utc=time.time()+4000))


@pytest.fixture
def powershell(tmp_path):
    executable=os.environ.get('PARKWEAVE_TEST_PWSH') or shutil.which('pwsh')
    if not executable:pytest.skip('explicit portable PowerShell CLI unavailable; never use Windows fallback')
    env=process_env.minimal_environment(os.environ)
    for key,name in [('XDG_CACHE_HOME','cache'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','data')]:
        env[key]=str(tmp_path/name)
    def run(code,extra=None):
        path=tmp_path/'probe.ps1';path.write_text(code)
        result=subprocess.run([executable,'-NoLogo','-NoProfile','-NonInteractive','-File',str(path)],
            env={**env,**(extra or {})},text=True,capture_output=True,timeout=30)
        assert result.returncode==0,(result.stdout,result.stderr)
        return result.stdout
    return run


def ps_literal(value):return "'"+str(value).replace("'","''")+"'"


def test_actual_powershell_whitelist_case_collision_and_source_consistency(powershell):
    output=powershell(f"""
$ErrorActionPreference='Stop'
. {ps_literal(HELPER)}
$source=[Collections.Generic.Dictionary[string,string]]::new([StringComparer]::Ordinal)
$source['Path']='safe-path';$source['SYSTEMROOT']='safe-root';$source['SystemRoot']='safe-root'
$source['LANG']='';$source['PGUNRECOGNIZED']='not-forwarded';$source['pgpassword']=''
$source['PYTHONPATH']='not-forwarded';$source['GITHUB_TOKEN']='not-forwarded'
$before=$source.Count;$clean=Get-ParkWeaveCoordinatorEnvironment -Source $source
if ($source.Count -ne $before -or $clean.Count -ne 3 -or $clean['PATH'] -cne 'safe-path') {{throw 'FILTER_FAILED'}}
$source['Path']='conflict';$source['PATH']='other'
$refused=$false
try {{Get-ParkWeaveCoordinatorEnvironment -Source $source | Out-Null}} catch {{$refused=$true}}
if (-not $refused) {{throw 'CASE_CONFLICT_NOT_REFUSED'}}
@{{os=$script:ParkWeaveCoordinatorOsNames;context=$script:ParkWeaveCoordinatorContextNames}} | ConvertTo-Json -Compress
""")
    result=json.loads(output)
    assert set(result['os'])==set(process_env.WINDOWS_OS_ENV_NAMES)
    assert set(result['context'])==set(window.CONTEXT_NAMES)
    assert not any(name.upper().startswith('PG') for name in result['os']+result['context'])


def test_actual_powershell_python_and_role_descendants_drop_ambient_settings(powershell,tmp_path):
    # These are environment-only processes, not fake PG/API/native observations.
    leaf=tmp_path/'leaf.py';leaf.write_text('import os,json; print(json.dumps(dict(keys=sorted(os.environ),role=os.environ.get("PARKWEAVE_ROLE"))))')
    probe=tmp_path/'coordinator.py';probe.write_text(f'''
import hashlib,json,os,subprocess,sys,time
sys.path.insert(0,{str(ROOT/'src')!r})
from parkweave.process_env import minimal_environment
assert os.environ['SystemRoot']=='SYNTHETIC_ENV_ONLY_ROOT'
assert hashlib.sha256(os.environ['PATH'].encode()).hexdigest().upper()==sys.argv.pop()
before=dict(os.environ);rows=[]
for role in ('pg','api','worker'):
    env=minimal_environment(os.environ,PARKWEAVE_ROLE=role)
    r=subprocess.run([sys.executable,'-I','-B','-S',{str(leaf)!r}],env=env,capture_output=True,text=True,check=True,timeout=5)
    rows.append(json.loads(r.stdout))
assert dict(os.environ)==before
print(json.dumps(dict(keys=sorted(os.environ),args=sys.argv[1:],clock_elapsed=time.monotonic()-float(os.environ['PARKWEAVE_TRIAL_START_MONOTONIC']),roles=rows)))
''')
    arguments=['a space','quote"literal','$(must-not-run)','中文','']
    args=','.join(ps_literal(x) for x in ['-I','-B','-S',probe,*arguments])
    output=powershell(f"""
$ErrorActionPreference='Stop'
. {ps_literal(HELPER)}
$before=[Environment]::GetEnvironmentVariables('Process')
$clean=Get-ParkWeaveCoordinatorEnvironment
$start=[Environment]::TickCount64/1000.0
$clean['PARKWEAVE_TRIAL_START_MONOTONIC']=$start.ToString('F9',[Globalization.CultureInfo]::InvariantCulture)
$pathDigest=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.Encoding]::UTF8.GetBytes($before['PATH'])))
$info=New-ParkWeaveCoordinatorStartInfo -Executable {ps_literal(sys.executable)} -WorkingDirectory {ps_literal(tmp_path)} -ArgumentValues (@({args})+@($pathDigest)) -EnvironmentValues $clean
$code=Invoke-ParkWeaveCoordinator -StartInfo $info -CleanupEnd ($start+15)
if ($code -ne 0 -or $script:ParkWeaveUnknownCoordinators.Count -ne 0) {{throw 'CHILD_EXIT_FAILED'}}
$after=[Environment]::GetEnvironmentVariables('Process')
if ($before.Count -ne $after.Count) {{throw 'PARENT_CHANGED'}}
foreach ($key in $before.Keys) {{if ($after[$key] -cne $before[$key]) {{throw 'PARENT_CHANGED'}}}}
""",{'PGUNKNOWN':'never-forward','pgpassword':'','PgServiceFile':'never-forward',
        'PYTHONPATH':'never-forward','GITHUB_TOKEN':'never-forward','HTTPS_PROXY':'never-forward',
        'RUNNER_TRACKING_ID':'synthetic-marker','sYsTeMrOoT':'SYNTHETIC_ENV_ONLY_ROOT',
        'WINDIR':'SYNTHETIC_ENV_ONLY_ROOT','COMSPEC':'SYNTHETIC_ENV_ONLY_SHELL',
        'PATHEXT':'.EXE','TEMP':str(tmp_path),'TMP':str(tmp_path)})
    value=json.loads(output)
    assert value['args']==arguments and 0<=value['clock_elapsed']<15
    assert 'RUNNER_TRACKING_ID' in value['keys']
    assert {'PATH','SystemRoot','WINDIR','COMSPEC','PATHEXT','TEMP','TMP'}<=set(value['keys'])
    for keys in [value['keys'],*(row['keys'] for row in value['roles'])]:
        assert not any(key.upper().startswith('PG') for key in keys)
        assert not {'GITHUB_TOKEN','PYTHONPATH','HTTPS_PROXY','HOME','USERPROFILE'}&set(keys)
    assert {row['role'] for row in value['roles']}=={'pg','api','worker'}
    assert all('RUNNER_TRACKING_ID' not in row['keys'] for row in value['roles'])


def test_actual_powershell_exit_code_timeout_and_owned_unknown_retention(powershell,tmp_path):
    output=powershell(f"""
$ErrorActionPreference='Stop'
. {ps_literal(HELPER)}
$clean=Get-ParkWeaveCoordinatorEnvironment
$start=[Environment]::TickCount64/1000.0
$info=New-ParkWeaveCoordinatorStartInfo -Executable {ps_literal(sys.executable)} -WorkingDirectory {ps_literal(tmp_path)} -ArgumentValues @('-I','-B','-S','-c','raise SystemExit(7)') -EnvironmentValues $clean
if ((Invoke-ParkWeaveCoordinator -StartInfo $info -CleanupEnd ($start+10)) -ne 7) {{throw 'EXIT_CODE_LOST'}}
$info=New-ParkWeaveCoordinatorStartInfo -Executable {ps_literal(sys.executable)} -WorkingDirectory {ps_literal(tmp_path)} -ArgumentValues @('-I','-B','-S','-c','import time; time.sleep(.5)') -EnvironmentValues $clean
$end=([Environment]::TickCount64/1000.0)+.1
$refused=$false
try {{Invoke-ParkWeaveCoordinator -StartInfo $info -CleanupEnd $end | Out-Null}} catch {{$refused=$true}}
if (-not $refused -or $script:ParkWeaveUnknownCoordinators.Count -ne 1) {{throw 'UNKNOWN_NOT_RETAINED'}}
# Test-only: wait the original harmless child to its natural exit, then dispose
# that same held Process. Production never retries, looks up PID or kills it.
$original=$script:ParkWeaveUnknownCoordinators[0]
if (-not $original.WaitForExit(5000) -or $original.ExitCode -ne 0) {{throw 'TEST_CHILD_DID_NOT_EXIT'}}
$original.Dispose()
'OWNED_ENVIRONMENT_ONLY_EXIT_CHECKED'
""")
    assert output.strip()=='OWNED_ENVIRONMENT_ONLY_EXIT_CHECKED'


def test_actual_powershell_parser_and_null_driver_gate(powershell,tmp_path):
    copy=tmp_path/'native_business_driver.ps1';copy.write_bytes((ROOT/'scripts/windows_ci/native_business_driver.ps1').read_bytes())
    (tmp_path/'native_business_window.json').write_text('null\n')
    output=powershell(f"""
$ErrorActionPreference='Stop'
foreach ($path in @({ps_literal(copy)},{ps_literal(HELPER)})) {{
    $tokens=$null;$errors=$null
    [Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors) | Out-Null
    if ($errors.Count) {{throw 'PARSE_FAILED'}}
}}
$refused=$false
try {{& {ps_literal(copy)} -CandidateDirectory 'not-opened' -CandidateArchive 'not-opened'}} catch {{
    if ($_.Exception.Message -cne 'WINDOW_UNBOUND') {{throw 'WRONG_NULL_GATE'}}
    $refused=$true
}}
if (-not $refused) {{throw 'NULL_NOT_REFUSED'}}
'NULL_REFUSED_BEFORE_HELPER_OR_CHILD'
""",{'GITHUB_ACTIONS':'true','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Windows','GITHUB_REPOSITORY':'T1doo/ParkWeave','PGUNKNOWN':'never-forward'})
    assert output.strip()=='NULL_REFUSED_BEFORE_HELPER_OR_CHILD'
