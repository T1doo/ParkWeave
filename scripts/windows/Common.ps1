# Shared native launcher. No execution-policy changes or credential persistence.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'PythonCommand.ps1')
function Invoke-ParkWeave {
    param([string]$Action, [string]$Python = 'python')
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'NOT_RUN: requires native Windows. WSL/Linux does not count.'
    }
    $Repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    if (!(Test-Path (Join-Path $Repo 'pyproject.toml'))) { throw 'ParkWeave repository missing.' }
    $ManagedPython = Join-Path $Repo '.venv-windows\Scripts\python.exe'
    if ($Action -ne 'setup' -and (Test-Path $ManagedPython)) { $Python = $ManagedPython }
    $Executable = Resolve-ParkWeavePython -Python $Python
    Push-Location $Repo
    try {
        & $Executable (Join-Path $PSScriptRoot 'lifecycle.py') $Action
        if ($LASTEXITCODE -ne 0) { throw "ParkWeave $Action failed. Read the safe error; existing data remains." }
    } finally { Pop-Location }
}
