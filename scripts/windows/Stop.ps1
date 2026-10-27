#requires -Version 5.1
param([string]$Python = 'python')
. (Microsoft.PowerShell.Management\Join-Path $PSScriptRoot 'Common.ps1')
Invoke-ParkWeave -Action 'stop' -Python $Python
