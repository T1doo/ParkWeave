# Trusted source helper. Construct only a child environment; never mutate the
# parent Process/User/Machine environment. No source grant or native operation.
$script:ParkWeaveCoordinatorOsNames=@(
    'COMSPEC','LANG','LC_ALL','PATH','PATHEXT','SystemRoot','TEMP','TMP','TMPDIR','TZ','WINDIR'
)
$script:ParkWeaveCoordinatorContextNames=@(
    'GITHUB_ACTIONS','RUNNER_ENVIRONMENT','RUNNER_OS','NATIVE_PUBLIC','GITHUB_REPOSITORY',
    'GITHUB_REF','GITHUB_JOB','GITHUB_EVENT_NAME','GITHUB_RUN_ATTEMPT','GITHUB_RUN_NUMBER','GITHUB_RUN_ID',
    'GITHUB_SHA','GITHUB_WORKFLOW_SHA','GITHUB_WORKFLOW_REF','GITHUB_WORKSPACE','RUNNER_TEMP','RUNNER_TOOL_CACHE','PSYCOPG_IMPL',
    'RUNNER_TRACKING_ID','PARKWEAVE_TRIAL_START_MONOTONIC'
)
$script:ParkWeaveUnknownCoordinators=[Collections.Generic.List[Diagnostics.Process]]::new()

function Get-ParkWeaveCoordinatorEnvironment {
    param([Collections.IDictionary]$Source=[Environment]::GetEnvironmentVariables('Process'))
    $allowed=[Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($name in $script:ParkWeaveCoordinatorOsNames+$script:ParkWeaveCoordinatorContextNames) {
        $allowed.Add($name,$name)
    }
    $result=[Collections.Generic.Dictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
    foreach ($key in $Source.Keys) {
        if ($key -isnot [string] -or -not $allowed.ContainsKey($key)) {continue}
        $name=$allowed[$key];$value=$Source[$key]
        if ($value -isnot [string] -or $value -match '[\x00-\x1f]') {throw 'INVALID_COORDINATOR_ENVIRONMENT'}
        if ($result.ContainsKey($name) -and $result[$name] -cne $value) {throw 'AMBIGUOUS_COORDINATOR_ENVIRONMENT'}
        $result[$name]=$value
    }
    return ,$result
}

function New-ParkWeaveCoordinatorStartInfo {
    param([string]$Executable,[string[]]$ArgumentValues,[Collections.IDictionary]$EnvironmentValues,[string]$WorkingDirectory)
    if (-not [IO.Path]::IsPathFullyQualified($Executable) -or
        -not [IO.Path]::IsPathFullyQualified($WorkingDirectory) -or
        [string]::IsNullOrEmpty($EnvironmentValues['PATH'])) {throw 'FIXED_COORDINATOR_PATH_REQUIRED'}
    $info=[Diagnostics.ProcessStartInfo]::new()
    $info.FileName=$Executable;$info.WorkingDirectory=$WorkingDirectory;$info.UseShellExecute=$false
    # Inherit console handles. No redirected pipe that can deadlock on output.
    $info.Environment.Clear()
    $checked=Get-ParkWeaveCoordinatorEnvironment -Source $EnvironmentValues
    if ($checked.Count -ne $EnvironmentValues.Count) {throw 'UNREVIEWED_COORDINATOR_ENVIRONMENT'}
    foreach ($key in $checked.Keys) {$info.Environment.Add($key,$checked[$key])}
    foreach ($argument in $ArgumentValues) {[void]$info.ArgumentList.Add($argument)}
    return $info
}

function Invoke-ParkWeaveCoordinator {
    param([Diagnostics.ProcessStartInfo]$StartInfo,[double]$CleanupEnd)
    $remaining=$CleanupEnd-([Environment]::TickCount64/1000.0)
    if (-not [double]::IsFinite($remaining) -or $remaining -le 0 -or $remaining -gt 960) {
        throw 'COORDINATOR_DEADLINE_REFUSED'
    }
    $process=[Diagnostics.Process]::new();$process.StartInfo=$StartInfo
    $exited=$false;$retained=$false
    try {
        if (-not $process.Start()) {throw 'COORDINATOR_START_UNKNOWN_NO_RETRY'}
        $remaining=$CleanupEnd-([Environment]::TickCount64/1000.0)
        if ($remaining -le 0 -or -not $process.WaitForExit([int][Math]::Ceiling($remaining*1000))) {
            throw 'COORDINATOR_EXIT_UNKNOWN_NO_RETRY'
        }
        $code=$process.ExitCode;$exited=$true
        return $code
    } catch {
        if (-not $exited) {[void]$script:ParkWeaveUnknownCoordinators.Add($process);$retained=$true}
        throw 'COORDINATOR_PROCESS_UNKNOWN_NO_RETRY'
    } finally {
        if ($exited) {
            try {$process.Dispose()} catch {
                if (-not $retained) {[void]$script:ParkWeaveUnknownCoordinators.Add($process)}
                throw 'COORDINATOR_CLOSE_UNKNOWN_NO_RETRY'
            }
        }
    }
}
