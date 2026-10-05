#requires -Version 7.0
param([ValidateSet('Prepare','Test','Stop')][string]$Action, [string]$Python='python')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'NOT_RUN: native Windows Server 2025 engineering only; no Linux/WSL substitute.'
}
$OS=Get-CimInstance Win32_OperatingSystem
if ($OS.Caption -notmatch 'Windows Server 2025' -or $OS.ProductType -eq 1) {
    throw 'NOT_RUN: explicit Windows Server 2025 required; this is not a Win11 harness.'
}
$Repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$BasePython=(Get-Command $Python -CommandType Application -ErrorAction Stop).Source
Import-Module (Join-Path $PSScriptRoot 'ClusterControl.psm1') -Force
function Invoke-Checked([string]$Exe,[string[]]$Arguments) {
    & $Exe @Arguments
    if ($LASTEXITCODE -ne 0) { throw 'Native engineering command failed; preserve fixture, no fallback or policy change.' }
}
function Protect-NewDirectory([string]$Path) {
    $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl=[System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetOwner($sid); $acl.SetAccessRuleProtection($true,$false)
    $rule=[System.Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow')
    $acl.AddAccessRule($rule); Set-Acl -LiteralPath $Path -AclObject $acl
}
function Get-OwnedState {
    if (!$env:PARKWEAVE_CI_ROOT) { throw 'No owned cluster state; do not discover or stop other PostgreSQL instances.' }
    return Get-OwnedCluster -Root $env:PARKWEAVE_CI_ROOT -RunnerTemp $env:RUNNER_TEMP -Bin $env:PGBIN
}
Push-Location $Repo
try {
    if ($Action -eq 'Prepare') {
        Invoke-Checked $BasePython @('-c',"import sys,struct;assert sys.platform=='win32' and sys.version_info[:2]==(3,12) and struct.calcsize('P')==8")
        if (!$env:PGBIN -or !(Test-Path (Join-Path $env:PGBIN 'initdb.exe')) -or !$env:RUNNER_TEMP -or !$env:GITHUB_ENV) {
            throw 'Explicit runner PGBIN/RUNNER_TEMP/GITHUB_ENV required; no discovery or downloads.'
        }
        $pg=Join-Path $env:PGBIN 'postgres.exe'
        $version=& $pg --version
        if ($LASTEXITCODE -ne 0 -or $version -notmatch '^postgres \(PostgreSQL\) 17\.') { throw 'Native PG17 required.' }
        $root=Join-Path $env:RUNNER_TEMP ('parkweave-server-ci-'+[Guid]::NewGuid().ToString())
        New-Item -ItemType Directory -Path $root -ErrorAction Stop | Out-Null
        Protect-NewDirectory $root
        $port=& $BasePython -c "import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1]);s.close()"
        if ($LASTEXITCODE -ne 0 -or [int]$port -lt 1024) { throw 'Loopback port allocation failed.' }
        $state=@{project='ParkWeave';scope='SYNTHETIC_SERVER_ENGINEERING';data=(Join-Path $root 'data');bin=$env:PGBIN;port=[int]$port}
        $state | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'cluster-state.json') -Encoding utf8
        # Publish only explicitly constructed ephemeral config, never inherited secrets.
        $env:PARKWEAVE_CI_ROOT=$root
        "PARKWEAVE_CI_ROOT=$root" | Add-Content -LiteralPath $env:GITHUB_ENV
        $testDsn="host=127.0.0.1 port=$port dbname=postgres user=park_ci_owner"
        $ownerDsn="host=127.0.0.1 port=$port dbname=parkweave user=park_ci_owner"
        $appDsn="host=127.0.0.1 port=$port dbname=parkweave user=parkweave_app"
        "PARKWEAVE_TEST_OWNER_DSN=$testDsn" | Add-Content -LiteralPath $env:GITHUB_ENV
        "PARKWEAVE_OWNER_DSN=$ownerDsn" | Add-Content -LiteralPath $env:GITHUB_ENV
        "PARKWEAVE_DSN=$appDsn" | Add-Content -LiteralPath $env:GITHUB_ENV
        Invoke-Checked (Join-Path $env:PGBIN 'initdb.exe') @('-D',$state.data,'-U','park_ci_owner','--auth-local=trust','--auth-host=trust','--encoding=UTF8','--locale=C')
        $started=Start-OwnedCluster -Root $root -RunnerTemp $env:RUNNER_TEMP -Bin $env:PGBIN
        if ($started.status -ne 'STARTED') { $started | ConvertTo-Json -Depth 4; throw 'Owned PG start failed; primary failure preserved.' }
        $psql=Join-Path $env:PGBIN 'psql.exe'
        Invoke-Checked $psql @('-h','127.0.0.1','-p',"$port",'-U','park_ci_owner','-d','postgres','-v','ON_ERROR_STOP=1','-c','CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE')
        Invoke-Checked $psql @('-h','127.0.0.1','-p',"$port",'-U','park_ci_owner','-d','postgres','-v','ON_ERROR_STOP=1','-c','CREATE DATABASE parkweave')
        if (Test-Path -LiteralPath '.venv-windows') { throw 'Existing managed environment protected; fresh checkout required.' }
        Invoke-Checked $BasePython @('-m','venv','.venv-windows')
        $managed=Join-Path $Repo '.venv-windows\Scripts\python.exe'
        Invoke-Checked $managed @('-m','pip','install','--no-cache-dir','-r','requirements-windows-candidate.txt')
        Invoke-Checked $managed @('-m','pip','install','--no-cache-dir','--no-deps','-e','.')
        $uac=(Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -Name EnableLUA).EnableLUA
        $identity=[System.Security.Principal.WindowsPrincipal]::new([System.Security.Principal.WindowsIdentity]::GetCurrent())
        $metadata=@{scope='WINDOWS_SERVER_ENGINEERING_NOT_WIN11';caption=$OS.Caption;build=$OS.BuildNumber;administrator=$identity.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);uac_enable_lua=$uac;postgres_binary=$version;python=(& $managed --version);image_version=$env:ImageVersion;real_model_calls=0;win11_acceptance='NOT_RUN'}
        $metadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'environment.json') -Encoding utf8
        $metadata | ConvertTo-Json
    } elseif ($Action -eq 'Test') {
        $state=Get-OwnedState
        $managed=Join-Path $Repo '.venv-windows\Scripts\python.exe'
        Invoke-Checked $managed @('scripts/windows_ci/native_suite.py','--report',(Join-Path $env:PARKWEAVE_CI_ROOT 'engineering.json'))
    } else {
        if (!$env:PARKWEAVE_CI_ROOT) { Write-Output 'NOT_RUN: no published owned cluster; no service touched.'; exit 0 }
        $state=Get-OwnedState
        Stop-OwnedCluster -Root $env:PARKWEAVE_CI_ROOT -RunnerTemp $env:RUNNER_TEMP -Bin $env:PGBIN | ConvertTo-Json
    }
} finally { Pop-Location }
