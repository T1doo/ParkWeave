# Resolve one application path before passing it to the call operator.
param([switch]$ParkWeaveDoctorTrace)
if ($ParkWeaveDoctorTrace) { [Console]::Error.WriteLine('PW_STAGE:PS_RESOLVER_FILE_ENTERED'); [Console]::Error.Flush() }
function Resolve-ParkWeavePython {
    param([Parameter(Mandatory=$true)][string]$Python, [switch]$TraceStages)
    if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_GET_COMMAND_BEGIN'); [Console]::Error.Flush() }
    $candidates=@(Get-Command -Name $Python -CommandType Application -All -ErrorAction Stop)
    if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_GET_COMMAND_RETURNED'); [Console]::Error.Flush() }
    foreach ($candidate in $candidates) {
        if ($candidate.Source -isnot [string]) { throw 'Python command source must be one path.' }
        $path=$candidate.Source
        # Windows execution aliases are launch stubs, not the required interpreter.
        if ($path -match '(?i)[\\/]Microsoft[\\/]WindowsApps[\\/]') { continue }
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_TEST_PATH_READY'); [Console]::Error.Flush() }
        $file=Get-Item -LiteralPath $path -Force -ErrorAction Stop
        if ($TraceStages) { [Console]::Error.WriteLine('PW_STAGE:PS_GET_ITEM_RETURNED'); [Console]::Error.Flush() }
        if ($file.Length -eq 0) { continue }
        return $file.FullName
    }
    throw 'No real Python executable found; WindowsApps aliases are not accepted.'
}
if ($ParkWeaveDoctorTrace) { [Console]::Error.WriteLine('PW_STAGE:PS_RESOLVER_FILE_READY'); [Console]::Error.Flush() }
