#requires -Version 5.1
param([string]$Python = 'python')
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    Write-Error 'NOT_RUN: Windows file candidate probe requires native Windows11 x64.'
    exit 1
}
$Repo = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$Runtime = Join-Path $Repo '.runtime'
if (-not (Test-Path -LiteralPath $Runtime -PathType Container)) {
    Write-Error 'NOT_RUN: prepare the existing private Park runtime first; this probe will not change its ACL.'
    exit 1
}
$Probe = Join-Path $Runtime ('windows-file-candidate-' + [Guid]::NewGuid().ToString())
# Exclusive new fixture directory. No supplied existing root or ACL repair option.
New-Item -ItemType Directory -Path $Probe -ErrorAction Stop | Out-Null
function Protect-NewFixture([string]$Path, [bool]$Directory) {
    $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    if ($Directory) { $acl = New-Object System.Security.AccessControl.DirectorySecurity }
    else { $acl = New-Object System.Security.AccessControl.FileSecurity }
    $acl.SetOwner($sid)
    $acl.SetAccessRuleProtection($true, $false)
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
}
try {
    Protect-NewFixture $Probe $true
    $Marker = Join-Path $Probe 'SYNTHETIC-CANDIDATE-ONLY.txt'
    [IO.File]::WriteAllText($Marker, 'ParkWeave self-authored fixture; no API activation.', (New-Object Text.UTF8Encoding($false)))
    Protect-NewFixture $Marker $false
    & $Python (Join-Path $PSScriptRoot 'file_candidate_probe.py') --fixture-dir $Probe
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output 'Candidate probe finished. Inspect its private report; this does not activate the API or complete native F1 acceptance.'
} catch {
    Write-Error ('Windows candidate probe failed: ' + $_.Exception.GetType().Name + '. New fixture preserved; no existing ACL repaired.')
    exit 1
}
# Preserve this unique synthetic directory for review; never delete broad user paths.
