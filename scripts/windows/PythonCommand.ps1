# Resolve one application path before passing it to the call operator.
function Resolve-ParkWeavePython {
    param([Parameter(Mandatory=$true)][string]$Python)
    $candidates=@(Get-Command -Name $Python -CommandType Application -All -ErrorAction Stop)
    foreach ($candidate in $candidates) {
        if ($candidate.Source -isnot [string]) { throw 'Python command source must be one path.' }
        $path=$candidate.Source
        # Windows execution aliases are launch stubs, not the required interpreter.
        if ($path -match '(?i)[\\/]Microsoft[\\/]WindowsApps[\\/]') { continue }
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { continue }
        $file=Get-Item -LiteralPath $path -Force -ErrorAction Stop
        if ($file.Length -eq 0) { continue }
        return $file.FullName
    }
    throw 'No real Python executable found; WindowsApps aliases are not accepted.'
}
