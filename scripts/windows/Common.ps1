# Shared native launcher. No execution-policy changes or credential persistence.
param([switch]$ParkWeaveDoctorTrace)
if ($ParkWeaveDoctorTrace) { [Console]::Error.WriteLine('PW_STAGE:PS_COMMON_ENTERED'); [Console]::Error.Flush() }
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($ParkWeaveDoctorTrace) {
    [Console]::Error.WriteLine('PW_STAGE:PS_RESOLVER_PATH_BEGIN'); [Console]::Error.Flush()
    $ResolverScript = Join-Path $PSScriptRoot 'PythonCommand.ps1'
    [Console]::Error.WriteLine('PW_STAGE:PS_RESOLVER_PATH_READY'); [Console]::Error.Flush()
    . $ResolverScript -ParkWeaveDoctorTrace
    [Console]::Error.WriteLine('PW_STAGE:PS_RESOLVER_SOURCE_READY'); [Console]::Error.Flush()
} else {
    . (Join-Path $PSScriptRoot 'PythonCommand.ps1')
}
function Invoke-ParkWeave {
    param([string]$Action, [string]$Python = 'python', [switch]$TraceStages)
    if ($TraceStages -and $Action -ne 'doctor') { throw 'Stage tracing is limited to Doctor.' }
    if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_INVOKE_ENTERED'); [Console]::Error.Flush() }
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw 'NOT_RUN: requires native Windows. WSL/Linux does not count.'
    }
    $Repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    if (!(Test-Path (Join-Path $Repo 'pyproject.toml'))) { throw 'ParkWeave repository missing.' }
    if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_REPO_READY'); [Console]::Error.Flush() }
    $ManagedPython = Join-Path $Repo '.venv-windows\Scripts\python.exe'
    if ($Action -ne 'setup' -and (Test-Path $ManagedPython)) { $Python = $ManagedPython }
    if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_MANAGED_PATH_READY'); [Console]::Error.Flush() }
    $Executable = Resolve-ParkWeavePython -Python $Python -TraceStages:$TraceStages
    if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_PYTHON_RESOLVED'); [Console]::Error.Flush() }
    Push-Location $Repo
    try {
        if ($TraceStages) {
            [Console]::Error.WriteLine('PW_STAGE:PS_LIFECYCLE_BEGIN'); [Console]::Error.Flush()
            & $Executable (Join-Path $PSScriptRoot 'lifecycle.py') $Action --trace-stages
            [Console]::Error.WriteLine('PW_STAGE:PS_LIFECYCLE_RETURNED'); [Console]::Error.Flush()
        } else {
            & $Executable (Join-Path $PSScriptRoot 'lifecycle.py') $Action
        }
        if ($LASTEXITCODE -ne 0) { throw "ParkWeave $Action failed. Read the safe error; existing data remains." }
    } finally { Pop-Location }
}
