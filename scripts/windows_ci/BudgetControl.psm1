# One job epoch, never a fresh budget at each phase. Pure local timing only.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function New-ParkWeaveJobBudget {
    param([string]$Started, [double]$NowUnix=([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()/1000.0),
          [string]$StartedUptime=$env:PARKWEAVE_CI_JOB_UPTIME,[long]$NowUptime=[Environment]::TickCount64)
    if ($Started -notmatch '^[1-9][0-9]{9,11}$') { throw 'Explicit job clock required.' }
    $epoch=[long]$Started
    if ($epoch -gt $NowUnix) { throw 'Future job clock refused.' }
    if ($StartedUptime -notmatch '^[0-9]{1,16}$') { throw 'Explicit shared uptime clock required.' }
    $uptime=[long]$StartedUptime
    if ($uptime -gt $NowUptime) { throw 'Future shared uptime clock refused.' }
    return @{deadline_unix=($epoch+1300);python_deadline_unix=($epoch+1290);
             python_deadline_uptime=($uptime+1290000);
             remaining=[Math]::Min(($epoch+1300-$NowUnix),(($uptime+1300000-$NowUptime)/1000.0));clock=[Diagnostics.Stopwatch]::StartNew()}
}
function Get-ParkWeaveWorkTimeout {
    param([hashtable]$Budget,[int]$Maximum)
    if ($Maximum -le 0) { throw 'Positive command limit required.' }
    # Floor and one second scheduling margin. No max(1) when exhausted.
    $remaining=[Math]::Floor($Budget.remaining-$Budget.clock.Elapsed.TotalSeconds)-1
    if ($remaining -le 0) { throw 'NOT_RUN: TOTAL_BUDGET_EXHAUSTED' }
    return [int][Math]::Min($Maximum,$remaining)
}
Export-ModuleMember -Function New-ParkWeaveJobBudget,Get-ParkWeaveWorkTimeout
