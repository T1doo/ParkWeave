"""PowerShell resolution regressions; Linux fixtures are not native Windows evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from parkweave.process_env import minimal_environment

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('case', ['multiple', 'alias_first', 'spaces', 'aliases_only', 'source_array', 'missing_zero'])
def test_python_resolver_returns_one_real_application_path(tmp_path, case):
    if os.name == 'nt':
        pytest.skip('Linux executable-link fixture; Server exercises the real Windows resolver')
    pwsh = ROOT / '.cache/powershell/bin/pwsh'
    if not pwsh.exists():
        pytest.skip('portable PowerShell unavailable; resolver regression NOT_RUN')
    first = tmp_path / 'Python with spaces' / 'python-resolution-fixture'
    second = tmp_path / 'other Python' / first.name
    alias = tmp_path / 'Microsoft/WindowsApps/python.exe'
    for path in (first, second, alias):
        path.parent.mkdir(parents=True, exist_ok=True)
    first.symlink_to(sys.executable)
    second.symlink_to(sys.executable)
    alias.write_text('SYNTHETIC WindowsApps launch stub')
    script = tmp_path / 'resolve.ps1'
    script.write_text(r'''
param($Resolver,$First,$Second,$Alias,$Case)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
. $Resolver
function Check($ok,$label) { if (!$ok) { throw "SYNTHETIC oracle failed: $label" } }
if ($Case -eq 'multiple' -or $Case -eq 'spaces') {
    $name=if ($Case -eq 'multiple') { [IO.Path]::GetFileName($First) } else { $First }
    if ($Case -eq 'multiple') {
        $sources=@(Get-Command $name -CommandType Application -All).Source
        Check ($sources.Count -eq 2) 'actual multiple ApplicationInfo objects'
        # Reproduce the failed conversion without executing the joined program name.
        $joined=[string]$sources
        Check ($joined.Contains($First) -and $joined.Contains($Second)) 'old joined path failure'
    }
} else {
    $script:fixtureSources=switch ($Case) {
        'alias_first' { @($Alias,$First) }
        'aliases_only' { @($Alias) }
        'source_array' { ,@($First,$Second) }
        'missing_zero' { @((Join-Path ([IO.Path]::GetDirectoryName($First)) 'missing'),(Join-Path ([IO.Path]::GetDirectoryName($First)) 'zero'),$First) }
    }
    if ($Case -eq 'missing_zero') { [IO.File]::WriteAllText($script:fixtureSources[1],'') }
    function Get-Command {
        param($Name,$CommandType,[switch]$All,$ErrorAction)
        Check ($CommandType -eq 'Application' -and $All) 'application enumeration only'
        if ($Case -eq 'source_array') { [pscustomobject]@{Source=@($First,$Second)};return }
        foreach($source in $script:fixtureSources) { [pscustomobject]@{Source=$source} }
    }
    $name='SYNTHETIC-python'
}
if ($Case -eq 'aliases_only' -or $Case -eq 'source_array') {
    $refused=$false
    try { Resolve-ParkWeavePython $name | Out-Null } catch { $refused=$true }
    Check $refused 'invalid interpreter refused'
} else {
    $resolved=@(Resolve-ParkWeavePython $name)
    Check ($resolved.Count -eq 1 -and $resolved[0] -eq $First) 'one exact path with spaces retained'
    # Exercise the same call operator and independent argument passing as Prepare.
    $arguments=@('-c','import sys,struct,json;assert sys.version_info[:2]==(3,12) and struct.calcsize("P")==8;print(json.dumps(sys.argv[1:]))','SYNTHETIC argument with spaces')
    $result=& $resolved[0] @arguments
    Check ($LASTEXITCODE -eq 0) 'real selected Python3.12 x64 executes'
    Check (@($result | ConvertFrom-Json)[0] -eq 'SYNTHETIC argument with spaces') 'independent argument preserved'
    & $resolved[0] -c 'import sys;assert sys.version_info[:2]==(3,11)' 2>$null
    Check ($LASTEXITCODE -ne 0) 'wrong version fails closed'
}
@{case=$Case;status='PASS';native_Windows='NOT_RUN'}|ConvertTo-Json -Compress
''')
    env = minimal_environment(
        os.environ,
        PATH=os.pathsep.join((str(first.parent), str(second.parent), os.environ.get('PATH', ''))),
        XDG_CACHE_HOME=str(tmp_path / 'cache'),
        XDG_CONFIG_HOME=str(tmp_path / 'config'),
        XDG_DATA_HOME=str(tmp_path / 'data'),
    )
    result = subprocess.run(
        [str(pwsh), '-NoProfile', '-NonInteractive', '-File', str(script),
         str(ROOT / 'scripts/windows/PythonCommand.ps1'), str(first), str(second), str(alias), case],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['status'] == 'PASS'
