"""Local clock and orchestration boundaries; no Windows or PostgreSQL execution."""
import os
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import pytest
from test_windows_ci_preparation import module

ROOT=Path(__file__).resolve().parents[1]


def test_portable_job_clock_shares_prepare_and_stage_cutoff(tmp_path):
    pwsh=ROOT/'.cache/powershell/bin/pwsh'
    if not pwsh.exists():pytest.skip('portable PowerShell unavailable')
    script=tmp_path/'budget.ps1'
    script.write_text(r'''
param($ModulePath)
$ErrorActionPreference='Stop'
Import-Module $ModulePath
function Check($value) { if (!$value) { throw 'Synthetic budget assertion failed' } }
$prepare=New-ParkWeaveJobBudget '1700000000' 1700000030 '500000' 530000
Check ($prepare.deadline_unix -eq 1700001300 -and $prepare.python_deadline_unix -eq 1700001290)
Check ((Get-ParkWeaveWorkTimeout $prepare 240) -eq 240)
$validation=New-ParkWeaveJobBudget '1700000000' 1700001250 '500000' 1750000
Check ((Get-ParkWeaveWorkTimeout $validation 1300) -le 49)
Check ($validation.deadline_unix -eq $prepare.deadline_unix)
foreach($bad in @('', '1', '1700000001x')) {
 $refused=$false;try {New-ParkWeaveJobBudget $bad 1700000030|Out-Null}catch{$refused=$true};Check $refused
}
$refused=$false;try {New-ParkWeaveJobBudget '1700000100' 1700000030|Out-Null}catch{$refused=$true};Check $refused
$expired=New-ParkWeaveJobBudget '1700000000' 1700001300 '500000' 1800000
$rollback=New-ParkWeaveJobBudget '1700000000' 1700000100 '500000' 1800000
Check ($rollback.remaining -le 0)
$refused=$false;try {Get-ParkWeaveWorkTimeout $expired 600|Out-Null}catch{$refused=$true};Check $refused
'PASS: pure clock, zero process/PG commands'
''')
    from parkweave.process_env import minimal_environment
    env=minimal_environment(os.environ,XDG_CACHE_HOME=str(tmp_path/'cache'),XDG_CONFIG_HOME=str(tmp_path/'config'),XDG_DATA_HOME=str(tmp_path/'data'))
    proc=subprocess.run([str(pwsh),'-NoProfile','-NonInteractive','-File',str(script),str(ROOT/'scripts/windows_ci/BudgetControl.psm1')],env=env,capture_output=True,text=True,timeout=15)
    assert proc.returncode==0,proc.stderr
    assert 'PASS: pure clock' in proc.stdout


def test_workflow_keeps_one_job_and_25_minutes_with_independent_followups():
    text=(ROOT/'.github/workflows/windows-server-engineering.yml').read_text()
    assert text.count('runs-on:')==1 and text.count('timeout-minutes: 25')==1
    assert 'UtcNow.ToUnixTimeSeconds()-30' in text
    actions=['Anchor existing','Checkout without','Select Python','-Action Prepare','-Action Lifecycle','-Action Validation','-Action Publish','-Action Stop']
    positions=[text.index(s) for s in actions]
    assert positions==sorted(positions)
    for name in ('Validation','Publish','Stop'):
        section=text[:text.index('-Action '+name)].rsplit('      - name:',1)[-1]
        assert 'if: always()' in section
    assert 'contents: read' in text and 'checks: write' not in text
    entry=(ROOT/'scripts/windows_ci/Engineering.ps1').read_text()
    assert "'native_suite' 900" in entry
    assert "'native_lifecycle'" in entry and "'native_validation'" in entry
    assert "'summary_publish' 15 -Capture" in entry
    assert 'Get-ParkWeaveWorkTimeout $JobBudget $TimeoutSeconds' in entry


@pytest.mark.parametrize('phase,cap',[('native_lifecycle',300),('native_validation',1300)])
def test_staged_helpers_refuse_clock_reset_or_over_budget_before_launch(tmp_path,monkeypatch,phase,cap):
    native=module('native_command')
    monkeypatch.setattr(native.time,'time',lambda:1700001250)
    monkeypatch.setattr(native,'uptime_milliseconds',lambda:1750000)
    monkeypatch.setenv('PARKWEAVE_CI_JOB_UPTIME','500000')
    monkeypatch.delenv('PARKWEAVE_CI_JOB_STARTED',raising=False)
    with pytest.raises(ValueError):native.execute(sys.executable,['-c','pass'],phase,1,tmp_path)
    monkeypatch.setenv('PARKWEAVE_CI_JOB_STARTED','1700000000')
    with pytest.raises(ValueError):native.execute(sys.executable,['-c','pass'],phase,51,tmp_path)
    monkeypatch.setenv('PARKWEAVE_CI_JOB_STARTED','1700001260')
    with pytest.raises(ValueError):native.execute(sys.executable,['-c','pass'],phase,1,tmp_path)
    assert not list(tmp_path.iterdir())
    assert native.LIMITS[phase]==cap and native.LIMITS['native_suite']==900


@pytest.mark.parametrize('phase',['native_lifecycle','native_validation'])
def test_staged_helpers_keep_owned_job_exit_and_cleanup(tmp_path,monkeypatch,phase):
    native=module('native_command');monkeypatch.setenv('PARKWEAVE_CI_JOB_STARTED','1700000000')
    monkeypatch.setattr(native.time,'time',lambda:1700000030)
    monkeypatch.setattr(native,'uptime_milliseconds',lambda:530000)
    monkeypatch.setenv('PARKWEAVE_CI_JOB_UPTIME','500000')
    # Only replace this module's OS name; retain real pathlib platform behavior.
    monkeypatch.setattr(native,'os',SimpleNamespace(name='nt',environ=os.environ))
    calls=[]
    def run(args,**kw):
        calls.append(kw['timeout'])
        return SimpleNamespace(returncode=17,cleanup='OWNED_TREE_STOP_UNCONFIRMED')
    monkeypatch.setattr(native,'run_owned_job',run)
    result=native.execute(sys.executable,['-c','pass'],phase,40,tmp_path)
    assert calls==[40] and result['exit_code']==17
    assert result['cleanup']=='OWNED_TREE_STOP_UNCONFIRMED'


@pytest.mark.parametrize('phase,captured',[('summary_publish',True),('python_guard',False)])
def test_only_publisher_retains_bounded_safe_stdout_on_failure(tmp_path,phase,captured):
    native=module('native_command')
    text=json.dumps(module('publish_summary').base('SUMMARY_MISSING'))+'\n::notice title=ParkWeave safe diagnostics::{"kind":"publication","state":"ANNOTATIONS_UNAVAILABLE"}\n'
    result=native.execute(sys.executable,['-c','import sys;sys.stdout.write('+repr(text)+');raise SystemExit(1)'],phase,5,tmp_path,capture=True)
    assert result['exit_code']==1
    assert ('stdout' in result)==captured
    if captured: assert result['stdout']==text.rstrip('\n')


def test_portable_publication_sink_keeps_exact_utf8_lf_boundary(tmp_path,monkeypatch):
    pwsh=ROOT/'.cache/powershell/bin/pwsh'
    if not pwsh.exists():pytest.skip('portable PowerShell unavailable')
    from parkweave.process_env import minimal_environment
    env=minimal_environment(os.environ,XDG_CACHE_HOME=str(tmp_path/'cache'),XDG_CONFIG_HOME=str(tmp_path/'config'),XDG_DATA_HOME=str(tmp_path/'data'))
    publisher=module('publish_summary')
    prefix='::notice title=ParkWeave safe diagnostics::'
    # Exactly 2048 bytes per command including LF, 16384 bytes for eight.
    empty=publisher.annotation_command({'kind':'case','padding':''})
    command=publisher.annotation_command({'kind':'case','padding':'x'*(2047-len(empty))})
    text=json.dumps(publisher.base('SUMMARY_MISSING'))+'\n'+'\n'.join([command]*8)
    native=module('native_command')
    # Explicit synthetic formatter at its own maximum; the sink preserves
    # the helper's byte-validated full batch without Windows newline changes.
    import importlib
    formatter=importlib.import_module('publish_summary')
    monkeypatch.setattr(formatter,'annotation_commands',lambda public:([command]*8,True))
    result=native.execute(sys.executable,['-c','import sys;sys.stdout.write('+repr(text+'\n')+')'],'summary_publish',5,tmp_path,capture=True)
    script=tmp_path/'sink.ps1';script.write_text('param($ModulePath,$TextFile)\nImport-Module $ModulePath\nWrite-BoundedPublication ([IO.File]::ReadAllText($TextFile))\n')
    content=tmp_path/'public.txt';content.write_text(result['stdout'])
    proc=subprocess.run([str(pwsh),'-NoProfile','-NonInteractive','-File',str(script),str(ROOT/'scripts/windows_ci/NativeCommand.psm1'),str(content)],env=env,capture_output=True,timeout=15)
    assert proc.returncode==0,proc.stderr
    assert proc.stdout==(text+'\n').encode('utf-8') and b'\r' not in proc.stdout
    annotations=proc.stdout.splitlines()[1:]
    assert sum(len(line)+1 for line in annotations)==publisher.MAX_ANNOTATION_TOTAL_BYTES
    assert all(len(line)+1==publisher.MAX_ANNOTATION_BYTES for line in annotations)


@pytest.mark.parametrize('fragment',['{', 'valid_json_without_annotations', 'missing_terminal_lf', 'timeout_fragment'])
def test_partial_publisher_output_is_fixed_unavailable_and_failure(tmp_path,fragment):
    native=module('native_command');publisher=module('publish_summary')
    text=json.dumps(publisher.base('SUMMARY_MISSING'))
    if fragment=='{': text='{'
    if fragment=='missing_terminal_lf':text+='\n::notice title=ParkWeave safe diagnostics::{"kind":"publication","state":"ANNOTATIONS_UNAVAILABLE"}'
    command='import sys;sys.stdout.write('+repr(text)+');sys.stdout.flush()'
    timeout=5
    if fragment=='timeout_fragment':command+=';import time;time.sleep(2)';timeout=.05
    result=native.execute(sys.executable,['-c',command],'summary_publish',timeout,tmp_path,capture=True)
    assert result['exit_code']!=0
    assert result['stdout']==native.unavailable_publication()
    assert 'ANNOTATIONS_UNAVAILABLE' in result['stdout']


def test_capture_refuses_whole_line_short_write_against_regenerated_batch(monkeypatch):
    import importlib
    native=module('native_command');formatter=importlib.import_module('publish_summary')
    public=formatter.base('SUMMARY_MISSING');line=formatter.annotation_command({'kind':'publication','state':'ANNOTATIONS_UNAVAILABLE'})
    monkeypatch.setattr(formatter,'annotation_commands',lambda public:([line,line],True))
    with pytest.raises(ValueError):native.publication_capture((json.dumps(public)+'\n'+line+'\n').encode())


def test_publisher_oversize_preserves_original_nonzero_exit(tmp_path):
    native=module('native_command')
    result=native.execute(sys.executable,['-c',"import sys;sys.stdout.write('x'*100000);raise SystemExit(17)"],'summary_publish',5,tmp_path,capture=True)
    assert result['exit_code']==17 and result['error_category']=='CaptureLimitExceeded'
    assert result['stdout']==native.unavailable_publication()


def test_shared_uptime_refuses_new_budget_when_wall_clock_rolls_back(tmp_path,monkeypatch):
    native=module('native_command')
    monkeypatch.setenv('PARKWEAVE_CI_JOB_STARTED','1700000000')
    monkeypatch.setenv('PARKWEAVE_CI_JOB_UPTIME','500000')
    monkeypatch.setattr(native.time,'time',lambda:1700000100)
    monkeypatch.setattr(native,'uptime_milliseconds',lambda:1800000)
    with pytest.raises(ValueError):native.execute(sys.executable,['-c','pass'],'native_validation',1,tmp_path)
    assert not list(tmp_path.iterdir())
