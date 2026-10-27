#requires -Version 5.1
param([string]$Python = 'python')
. (Join-Path $PSScriptRoot 'Common.ps1')
Invoke-ParkWeave -Action 'test' -Python $Python
