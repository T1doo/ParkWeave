#requires -Version 7.0
param([ValidateSet('Prepare','Test','Lifecycle','Validation','Publish','Stop')][string]$Action, [string]$Python='python')
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
. (Join-Path $PSScriptRoot '..\windows\PythonCommand.ps1')
$BasePython=Resolve-ParkWeavePython -Python $Python
Import-Module (Join-Path $PSScriptRoot 'ClusterControl.psm1') -Force
Import-Module (Join-Path $PSScriptRoot 'NativeCommand.psm1')
Import-Module (Join-Path $PSScriptRoot 'BudgetControl.psm1')
$JobBudget=$null
if ($Action -in @('Prepare','Lifecycle','Validation')) {
    $JobBudget=New-ParkWeaveJobBudget -Started $env:PARKWEAVE_CI_JOB_STARTED
}
function Invoke-Checked([string]$Exe,[string[]]$Arguments,[string]$Phase,[int]$TimeoutSeconds,[switch]$Capture) {
    if ($null -ne $JobBudget) { $TimeoutSeconds=Get-ParkWeaveWorkTimeout $JobBudget $TimeoutSeconds }
    $result=@{exit_code=125;timed_out=$false;cleanup='OWNED_TREE_STOP_UNCONFIRMED'}
    try {
        $result=Invoke-BoundedNative $BasePython $Exe $Arguments $Phase $TimeoutSeconds $TraceRoot -Capture:$Capture
    } finally {
        if ($Phase -in @('native_lifecycle','native_validation')) {
            # Persist the outer Job result after its tree cleanup, even if the
            # Python checkpoint claimed PASS or the helper threw before return.
            $stageName=if ($Phase -eq 'native_lifecycle') { 'lifecycle' } else { 'validation' }
            $cluster=(Split-Path $env:PARKWEAVE_CI_ROOT -Leaf).Substring('parkweave-server-ci-'.Length)
            $record=@{schema=1;diagnostic_binding=@{run_id=$env:GITHUB_RUN_ID;run_attempt=$env:GITHUB_RUN_ATTEMPT;head_sha=$env:GITHUB_SHA;cluster_id=$cluster};exit_code=[long]$result.exit_code;timed_out=[bool]$result.timed_out;cleanup=[string]$result.cleanup}
            $destination=Join-Path $env:PARKWEAVE_CI_ROOT ($stageName+'-command.json')
            $temporary=Join-Path $env:PARKWEAVE_CI_ROOT ('.command-'+[Guid]::NewGuid().ToString()+'.tmp')
            try {
                $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $temporary -Encoding utf8
                [IO.File]::Move($temporary,$destination,$true)
            } finally {
                if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
            }
        }
    }
    if ($Phase -eq 'summary_publish' -and $result.PSObject.Properties.Name -contains 'stdout') {
        Write-BoundedPublication $result.stdout
    }
    if ($result.exit_code -ne 0) {
        Write-Host "::error title=ParkWeave CI phase::$Phase FAILED exit=$($result.exit_code) timeout=$($result.timed_out) cleanup=$($result.cleanup)"
        throw 'Native engineering phase failed; private output retained, no fallback or policy change.'
    }
    if ($Capture) { return $result.stdout }
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
    if (!$env:RUNNER_TEMP) { throw 'Explicit runner temp required; no discovery.' }
    $TraceRoot=Join-Path $env:RUNNER_TEMP ('parkweave-native-trace-'+[Guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $TraceRoot -ErrorAction Stop | Out-Null
    Protect-NewDirectory $TraceRoot
    if ($Action -eq 'Prepare') {
        Invoke-Checked $BasePython @('-c',"import sys,struct;assert sys.platform=='win32' and sys.version_info[:2]==(3,12) and struct.calcsize('P')==8") 'python_guard' 30
        if (!$env:PGBIN -or !(Test-Path (Join-Path $env:PGBIN 'initdb.exe')) -or !$env:RUNNER_TEMP -or !$env:GITHUB_ENV) {
            throw 'Explicit runner PGBIN/RUNNER_TEMP/GITHUB_ENV required; no discovery or downloads.'
        }
        $pg=Join-Path $env:PGBIN 'postgres.exe'
        $version=Invoke-Checked $pg @('--version') 'postgres_version' 15 -Capture
        if ($version -notmatch '^postgres \(PostgreSQL\) 17\.') { throw 'Native PG17 required.' }
        $root=Join-Path $env:RUNNER_TEMP ('parkweave-server-ci-'+[Guid]::NewGuid().ToString())
        New-Item -ItemType Directory -Path $root -ErrorAction Stop | Out-Null
        Protect-NewDirectory $root
        $port=Invoke-Checked $BasePython @('-c',"import socket;s=socket.socket();s.bind(('127.0.0.1',0));print(s.getsockname()[1]);s.close()") 'allocate_port' 15 -Capture
        if ([int]$port -lt 1024) { throw 'Loopback port allocation failed.' }
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
        Invoke-Checked (Join-Path $env:PGBIN 'initdb.exe') @('-D',$state.data,'-U','park_ci_owner','--auth-local=trust','--auth-host=trust','--encoding=UTF8','--locale=C') 'initdb' 120
        # Start failure may include owned status/stop recovery (up to 145s).
        # Admit it only when all those existing bounded paths fit before cutoff.
        if ((Get-ParkWeaveWorkTimeout $JobBudget 145) -lt 145) { throw 'NOT_RUN: TOTAL_BUDGET_EXHAUSTED' }
        $started=Start-OwnedCluster -Root $root -RunnerTemp $env:RUNNER_TEMP -Bin $env:PGBIN -Python $BasePython -LogDirectory $TraceRoot
        if ($started.status -ne 'STARTED') { $started | ConvertTo-Json -Depth 4; throw 'Owned PG start failed; primary failure preserved.' }
        $psql=Join-Path $env:PGBIN 'psql.exe'
        Invoke-Checked $psql @('-h','127.0.0.1','-p',"$port",'-U','park_ci_owner','-d','postgres','-v','ON_ERROR_STOP=1','-c','CREATE ROLE parkweave_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE') 'create_role' 30
        Invoke-Checked $psql @('-h','127.0.0.1','-p',"$port",'-U','park_ci_owner','-d','postgres','-v','ON_ERROR_STOP=1','-c','CREATE DATABASE parkweave') 'create_database' 30
        if (Test-Path -LiteralPath '.venv-windows') { throw 'Existing managed environment protected; fresh checkout required.' }
        Invoke-Checked $BasePython @('-m','venv','.venv-windows') 'venv' 60
        $managed=Join-Path $Repo '.venv-windows\Scripts\python.exe'
        Invoke-Checked $managed @('-m','pip','install','--no-cache-dir','-r','requirements-windows-candidate.txt') 'pip_dependencies' 240
        Invoke-Checked $managed @('-m','pip','install','--no-cache-dir','--no-deps','-e','.') 'pip_project' 120
        $uac=(Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System' -Name EnableLUA).EnableLUA
        $identity=[System.Security.Principal.WindowsPrincipal]::new([System.Security.Principal.WindowsIdentity]::GetCurrent())
        $pythonVersion=Invoke-Checked $managed @('--version') 'python_version' 15 -Capture
        $metadata=@{scope='WINDOWS_SERVER_ENGINEERING_NOT_WIN11';caption=$OS.Caption;build=$OS.BuildNumber;administrator=$identity.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);uac_enable_lua=$uac;postgres_binary=$version;python=$pythonVersion;image_version=$env:ImageVersion;real_model_calls=0;win11_acceptance='NOT_RUN'}
        $metadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'environment.json') -Encoding utf8
        $metadata | ConvertTo-Json
    } elseif ($Action -eq 'Test') {
        $state=Get-OwnedState
        $managed=Join-Path $Repo '.venv-windows\Scripts\python.exe'
        Invoke-Checked $managed @('scripts/windows_ci/native_suite.py','--report',(Join-Path $env:PARKWEAVE_CI_ROOT 'engineering.json')) 'native_suite' 900
    } elseif ($Action -in @('Lifecycle','Validation')) {
        $state=Get-OwnedState
        $managed=Join-Path $Repo '.venv-windows\Scripts\python.exe'
        $stage=if ($Action -eq 'Lifecycle') { 'lifecycle' } else { 'validation' }
        $phase=if ($Action -eq 'Lifecycle') { 'native_lifecycle' } else { 'native_validation' }
        $limit=if ($Action -eq 'Lifecycle') { 300 } else { 1300 }
        $arguments=@('scripts/windows_ci/native_suite.py','--report',(Join-Path $env:PARKWEAVE_CI_ROOT 'engineering.json'),'--stage',$stage,'--job-test-deadline',[string]$JobBudget.python_deadline_unix,'--job-test-uptime',[string]$JobBudget.python_deadline_uptime)
        $arguments+=@('--regression-shards','docs/F2/evidence/eng057-job-shards.json')
        # Each action may fail; the workflow always runs the next independent
        # stage and final publication/Stop. Neither phase gets a fresh 900s.
        Invoke-Checked $managed $arguments $phase $limit
    } elseif ($Action -eq 'Publish') {
        Invoke-Checked $BasePython @('scripts/windows_ci/publish_summary.py') 'summary_publish' 15 -Capture | Out-Null
    } else {
        $appStopFailed=$false
        # A timed-out suite may not have reached its finally. Reuse the existing
        # lifecycle stop oracle; it verifies recorded PID/cwd/command/start time.
        if (Test-Path -LiteralPath '.runtime/windows-processes.json') {
            try {
                $managed=Join-Path $Repo '.venv-windows\Scripts\python.exe'
                Invoke-Checked $managed @('scripts/windows/lifecycle.py','stop') 'app_stop' 60
            } catch { $appStopFailed=$true }
        }
        if (!$env:PARKWEAVE_CI_ROOT) {
            Write-Output 'NOT_RUN: no published owned cluster; no service touched.'
            if ($appStopFailed) { throw 'Owned app cleanup failed; no process discovery or fallback.' }
            exit 0
        }
        $state=Get-OwnedState
        Stop-OwnedCluster -Root $env:PARKWEAVE_CI_ROOT -RunnerTemp $env:RUNNER_TEMP -Bin $env:PGBIN -Python $BasePython -LogDirectory $TraceRoot | ConvertTo-Json
        if ($appStopFailed) { throw 'Owned app cleanup failed; PG cleanup still attempted.' }
    }
} finally { Pop-Location }
