# Pure binding/control helpers. Server entry guards remain in Engineering.ps1.
# Local tests replace ONLY Invoke-ClusterCommand with an explicit SYNTHETIC double.
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Get-OwnedCluster {
    param([string]$Root,[string]$RunnerTemp,[string]$Bin)
    if (!$Root -or !$RunnerTemp -or !$Bin) { throw 'Explicit owned cluster binding required.' }
    $rootPath=[IO.Path]::GetFullPath($Root)
    $tempPath=[IO.Path]::GetFullPath($RunnerTemp).TrimEnd([IO.Path]::DirectorySeparatorChar)
    $leaf=Split-Path $rootPath -Leaf
    $guid=[Guid]::Empty
    if ((Split-Path $rootPath -Parent) -ne $tempPath -or !$leaf.StartsWith('parkweave-server-ci-') -or
        ![Guid]::TryParseExact($leaf.Substring('parkweave-server-ci-'.Length),'D',[ref]$guid)) {
        throw 'Owned cluster root refused.'
    }
    $statePath=Join-Path $rootPath 'cluster-state.json'
    foreach ($path in @($rootPath,$statePath,(Join-Path $rootPath 'data'))) {
        if (Test-Path -LiteralPath $path) {
            if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Owned cluster reparse path refused.' }
        }
    }
    $state=Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    $names=@($state.PSObject.Properties.Name | Sort-Object)
    if (($names -join ',') -ne 'bin,data,port,project,scope' -or $state.project -ne 'ParkWeave' -or
        $state.scope -ne 'SYNTHETIC_SERVER_ENGINEERING' -or $state.data -ne (Join-Path $rootPath 'data') -or
        $state.bin -ne $Bin -or $state.port -isnot [long] -or $state.port -lt 1024 -or $state.port -gt 65535) {
        throw 'Owned cluster state refused.'
    }
    return $state
}
function Invoke-ClusterCommand {
    param([string]$Exe,[string[]]$Arguments)
    & $Exe @Arguments | Out-Null
    return $LASTEXITCODE
}
function Stop-OwnedCluster {
    param([string]$Root,[string]$RunnerTemp,[string]$Bin)
    $state=Get-OwnedCluster -Root $Root -RunnerTemp $RunnerTemp -Bin $Bin
    $ctl=Join-Path $state.bin 'pg_ctl.exe'
    $status=Invoke-ClusterCommand $ctl @('-D',$state.data,'status')
    if ($status -eq 3) { return @{status='NOT_RUNNING';exit_code=3} }
    if ($status -ne 0) { throw 'Unknown cluster status; stop refused.' }
    $exit=Invoke-ClusterCommand $ctl @('-D',$state.data,'-m','fast','-w','-t','30','stop')
    if ($exit -ne 0) { throw 'Owned cluster stop failed; no fallback.' }
    return @{status='STOPPED';exit_code=0}
}
function Start-OwnedCluster {
    param([string]$Root,[string]$RunnerTemp,[string]$Bin)
    $state=Get-OwnedCluster -Root $Root -RunnerTemp $RunnerTemp -Bin $Bin
    $exit=Invoke-ClusterCommand (Join-Path $state.bin 'pg_ctl.exe') @('-D',$state.data,'-l',(Join-Path $Root 'postgres.log'),'-o',"-h 127.0.0.1 -p $($state.port)",'-w','-t','30','start')
    if ($exit -eq 0) { return @{status='STARTED';exit_code=0} }
    # A failed/timed-out pg_ctl may have started a process. Re-validate binding;
    # preserve primary failure even when cleanup refuses an unknown status.
    try { $cleanup=Stop-OwnedCluster -Root $Root -RunnerTemp $RunnerTemp -Bin $Bin }
    catch { $cleanup=@{status='REFUSED_OR_FAILED';category=$_.Exception.GetType().Name} }
    return @{status='START_FAILED';exit_code=$exit;cleanup=$cleanup}
}
Export-ModuleMember -Function Get-OwnedCluster,Start-OwnedCluster,Stop-OwnedCluster
