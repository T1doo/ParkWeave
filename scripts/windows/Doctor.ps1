#requires -Version 5.1
param([string]$Python = 'python', [switch]$TraceStages)
if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_DOCTOR_ENTERED'); [Console]::Error.Flush() }
if ($TraceStages) {
    [Console]::Error.WriteLine('PW_STAGE:PS_COMMON_PATH_BEGIN'); [Console]::Error.Flush()
    $CommonScript = Microsoft.PowerShell.Management\Join-Path $PSScriptRoot 'Common.ps1'
    [Console]::Error.WriteLine('PW_STAGE:PS_COMMON_PATH_READY'); [Console]::Error.Flush()
    . $CommonScript -ParkWeaveDoctorTrace
} else {
    . (Microsoft.PowerShell.Management\Join-Path $PSScriptRoot 'Common.ps1')
}
if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_COMMON_READY'); [Console]::Error.Flush() }
Invoke-ParkWeave -Action 'doctor' -Python $Python -TraceStages:$TraceStages
