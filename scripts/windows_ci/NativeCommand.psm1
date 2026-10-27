Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
function Invoke-BoundedNative {
    param([string]$Python,[string]$Exe,[string[]]$Arguments,[string]$Phase,
          [int]$TimeoutSeconds,[string]$LogDirectory,[switch]$Capture)
    if ($Phase -notmatch '^[a-z_]+$') { throw 'Invalid native phase.' }
    Write-Host "::notice title=ParkWeave CI phase::$Phase START deadline=${TimeoutSeconds}s"
    $helper=Join-Path $PSScriptRoot 'native_command.py'
    $options=@($helper,'--exe',$Exe,'--phase',$Phase,'--timeout',"$TimeoutSeconds",'--log-dir',$LogDirectory)
    if ($Capture) { $options+='--capture' }
    # The helper never waits for pipe EOF from a service descendant.
    $raw=& $Python @options -- @Arguments
    if ($LASTEXITCODE -ne 0) {
        Write-Host "::error title=ParkWeave CI phase::$Phase HELPER_FAILED"
        throw 'Native command helper failed; private output retained.'
    }
    $result=$raw | ConvertFrom-Json
    Write-Host "::notice title=ParkWeave CI phase::$Phase END exit=$($result.exit_code) timeout=$($result.timed_out) elapsed=$($result.elapsed_seconds)s cleanup=$($result.cleanup)"
    return $result
}
Export-ModuleMember -Function Invoke-BoundedNative
function Write-BoundedPublication {
    param([string]$Text)
    # Re-emit only the trusted publisher capture with UTF-8/LF. Write-Host
    # would translate a boundary annotation's final LF to CRLF on Windows.
    $bytes=[Text.UTF8Encoding]::new($false,$true).GetBytes($Text+"`n")
    if ($bytes.Length -gt (96*1024+1)) { throw 'Bounded publication capture refused.' }
    [Console]::Out.Flush()
    $sink=[Console]::OpenStandardOutput()
    $sink.Write($bytes,0,$bytes.Length)
    $sink.Flush()
}
Export-ModuleMember -Function Write-BoundedPublication
