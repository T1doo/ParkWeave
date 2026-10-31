param([Parameter(Mandatory=$true)][string]$CandidateDirectory,
      [Parameter(Mandatory=$true)][string]$CandidateArchive,
      [switch]$ExtractApprovedArchive)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or
    $env:RUNNER_OS -ne 'Windows' -or $env:GITHUB_REPOSITORY -ne 'T1doo/ParkWeave') {
    throw 'DISPOSABLE_HOSTED_WINDOWS_REQUIRED'
}
# The null fixed source record refuses before candidate IO or execution.
$record=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'native_business_window.json') -Raw | ConvertFrom-Json
if ($null -eq $record) {throw 'WINDOW_UNBOUND'}
. (Join-Path $PSScriptRoot 'native_coordinator_environment.ps1')
# Child-only allowlist: no ambient PG*, tokens, proxies or Python settings.
# Parent Process/User/Machine state stays untouched. Source no-PG checks stay.
$coordinatorEnvironment=Get-ParkWeaveCoordinatorEnvironment
foreach ($name in $script:ParkWeaveCoordinatorContextNames) {
    if ($name -eq 'PARKWEAVE_TRIAL_START_MONOTONIC') {continue}
    if ([string]::IsNullOrEmpty($coordinatorEnvironment[$name])) {throw 'COORDINATOR_CONTEXT_REQUIRED'}
}
if ([string]::IsNullOrEmpty($coordinatorEnvironment['SystemRoot']) -or
    $record.work_seconds -ne 900 -or $record.cleanup_seconds -ne 60) {throw 'COORDINATOR_BUDGET_REQUIRED'}
$started=[Environment]::TickCount64/1000.0
$coordinatorEnvironment['PARKWEAVE_TRIAL_START_MONOTONIC']=$started.ToString('F9',[Globalization.CultureInfo]::InvariantCulture)
$cleanupEnd=$started+[Math]::Min(960,($record.expires_utc-[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000.0))
$cache=Join-Path $env:RUNNER_TOOL_CACHE 'Python'
$python=@(Get-ChildItem -LiteralPath $cache -Directory | Where-Object {
    $_.Name -match '^3\.12\.\d+$' -and
    (Test-Path -LiteralPath (Join-Path $_.FullName 'x64\python.exe') -PathType Leaf)
} | Sort-Object -Property {[Version]$_.Name} -Descending | Select-Object -First 1)
if ($python.Count -ne 1) {throw 'EXISTING_RUNNER_PYTHON312_X64_REQUIRED'}
$bootstrap=Join-Path $python[0].FullName 'x64\python.exe'
$entry=Join-Path $PSScriptRoot 'native_business_entry.py'
function Invoke-OriginalCoordinator {
    param([string[]]$StageArguments)
    $info=New-ParkWeaveCoordinatorStartInfo -Executable $bootstrap -WorkingDirectory (Split-Path (Split-Path $PSScriptRoot)) `
        -ArgumentValues (@('-I','-B','-S',$entry)+$StageArguments) -EnvironmentValues $coordinatorEnvironment
    return Invoke-ParkWeaveCoordinator -StartInfo $info -CleanupEnd $cleanupEnd
}
if ((Invoke-OriginalCoordinator -StageArguments @('--check-window')) -ne 0) {throw 'SOURCE_WINDOW_REFUSED'}
$temp=[IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\')+'\'
foreach ($path in @($CandidateDirectory,$CandidateArchive)) {
    if ($path -notmatch '^[A-Za-z]:\\' -or
        -not [IO.Path]::GetFullPath($path).StartsWith($temp,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'ORIGINAL_STAGED_RUNNER_TEMP_PATH_REQUIRED'
    }
    if ($path -eq $CandidateDirectory -and $ExtractApprovedArchive) {
        if (Test-Path -LiteralPath $path) {throw 'EXCLUSIVE_CANDIDATE_EXTRACTION_REQUIRED'}
        $item=Get-Item -LiteralPath ([IO.Path]::GetDirectoryName($path)) -Force
    } else {$item=Get-Item -LiteralPath $path -Force}
    while ($null -ne $item) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {throw 'REPARSE_STAGE_REFUSED'}
        $item=if ($item.PSIsContainer) {$item.Parent} else {$item.Directory}
    }
}
if ($ExtractApprovedArchive) {
    if ((Invoke-OriginalCoordinator -StageArguments @('--extract-only','--payload',$CandidateDirectory,'--candidate-zip',$CandidateArchive)) -ne 0) {
        throw 'CANDIDATE_EXTRACTION_UNKNOWN_NO_RETRY'
    }
}
# The trusted coordinator itself verifies and holds EVERY candidate file and
# ancestor, then imports pinned vendor code. Only the original native process
# implementation later starts the staged, held private product interpreter.
if ((Invoke-OriginalCoordinator -StageArguments @('--execute','--payload',$CandidateDirectory,'--candidate-zip',$CandidateArchive)) -ne 0) {
    throw 'NATIVE_TRIAL_UNKNOWN_NO_RETRY'
}
# No transfer, retry, path deletion, account creation or production activation.
