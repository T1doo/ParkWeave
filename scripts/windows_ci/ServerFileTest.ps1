#requires -Version 5.1
param([string]$Python='python')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'NOT_RUN: native Server engineering only.' }
$os=Get-CimInstance Win32_OperatingSystem
if ($os.Caption -notmatch 'Windows Server 2025' -or $os.ProductType -eq 1) { throw 'NOT_RUN: Server2025 only, not Win11.' }
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$runtime=Join-Path $repo '.runtime'
if (!(Test-Path -LiteralPath $runtime -PathType Container)) { throw 'NOT_RUN: existing private lifecycle runtime required; no repair.' }
$probe=Join-Path $runtime ('server-file-engineering-'+[Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $probe -ErrorAction Stop | Out-Null
function Protect-NewFixture([string]$Path,[bool]$Directory) {
    $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
    if ($Directory) { $acl=[System.Security.AccessControl.DirectorySecurity]::new() }
    else { $acl=[System.Security.AccessControl.FileSecurity]::new() }
    $acl.SetOwner($sid);$acl.SetAccessRuleProtection($true,$false)
    $rule=[System.Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','Allow')
    $acl.AddAccessRule($rule);Set-Acl -LiteralPath $Path -AclObject $acl
}
Protect-NewFixture $probe $true
$marker=Join-Path $probe 'SERVER-ENGINEERING-ONLY.txt'
[IO.File]::WriteAllText($marker,'ParkWeave SYNTHETIC Server engineering; not Win11 acceptance.',[Text.UTF8Encoding]::new($false))
Protect-NewFixture $marker $false
& $Python (Join-Path $PSScriptRoot 'server_candidate_probe.py') --fixture-dir $probe
if ($LASTEXITCODE -ne 0) { throw 'Server candidate oracle failed/incomplete; production disabled, no weaker fallback.' }
