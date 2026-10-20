#requires -Version 5.1
param([string]$Python = 'python', [switch]$TraceStages)
if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_DOCTOR_ENTERED'); [Console]::Error.Flush() }
. (Join-Path $PSScriptRoot 'Common.ps1')
if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_COMMON_READY'); [Console]::Error.Flush() }
Invoke-ParkWeave -Action 'doctor' -Python $Python -TraceStages:$TraceStages
