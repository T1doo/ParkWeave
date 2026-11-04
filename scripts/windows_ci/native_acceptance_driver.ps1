param([Parameter(Mandatory=$true)][string]$CandidateUri)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted' -or
    $env:RUNNER_OS -ne 'Windows' -or $env:GITHUB_REPOSITORY -ne 'T1doo/ParkWeave') {
    throw 'DISPOSABLE_HOSTED_WINDOWS_REQUIRED'
}
# No new Python install, credential, execution-policy override or user PC.
$cache=Join-Path $env:RUNNER_TOOL_CACHE 'Python'
$python=@(Get-ChildItem -LiteralPath $cache -Directory |
    Where-Object {$_.Name -match '^3\.12\.\d+$' -and
        (Test-Path -LiteralPath (Join-Path $_.FullName 'x64\python.exe') -PathType Leaf)} |
    Sort-Object -Property {[Version]$_.Name} -Descending | Select-Object -First 1)
if ($python.Count -ne 1) {throw 'EXISTING_PYTHON312_X64_REQUIRED'}
$bootstrap=Join-Path $python[0].FullName 'x64\python.exe'
$entry=Join-Path $PSScriptRoot 'native_acceptance_entry.py'
# Only source metadata reads until the source-bound window passes. JSON null
# currently refuses here; no download/temp directory or native action follows.
$record=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'native_acceptance_window.json') -Raw | ConvertFrom-Json
if ($null -eq $record) {throw 'WINDOW_UNBOUND'}
$parent=(& git rev-parse 'HEAD^').Trim()
if ($LASTEXITCODE -ne 0 -or $parent -ne $record.reviewed_parent) {throw 'REVIEWED_PARENT_REQUIRED'}
$allowed=@('scripts/windows_ci/native_acceptance_window.json','.github/workflows/native-local-acceptance-once.yml')
$changed=@(& git diff --name-only 'HEAD^' HEAD)
if ($LASTEXITCODE -ne 0 -or @($changed | Where-Object {$_ -notin $allowed}).Count -gt 0) {
    throw 'EXECUTABLE_SOURCE_CHANGED'
}
if (@(& git status --porcelain=v1).Count -gt 0) {throw 'CLEAN_SOURCE_REQUIRED'}
& $bootstrap -I -B $entry --check-window
if ($LASTEXITCODE -ne 0) {throw 'SOURCE_BOUND_WINDOW_REQUIRED'}
$uri=[Uri]$CandidateUri
if ($uri.AbsoluteUri -notmatch '^https://github\.com/T1doo/ParkWeave/releases/download/[A-Za-z0-9._-]+/Windows-runtime-candidate-5a048dbef9da\.zip$') {
    throw 'EXPLICIT_ORIGINAL_PUBLIC_CANDIDATE_REQUIRED'
}
$temp=Get-Item -LiteralPath $env:RUNNER_TEMP
if (!$temp.PSIsContainer -or ($temp.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'LOCAL_RUNNER_TEMP_REQUIRED'
}
$root=Join-Path $temp.FullName ('parkweave-native-stage-'+[Guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $root -ErrorAction Stop | Out-Null
$candidate=Join-Path $root 'candidate.zip'
$handler=[Net.Http.HttpClientHandler]::new();$handler.AllowAutoRedirect=$false;$handler.UseDefaultCredentials=$false
$client=[Net.Http.HttpClient]::new($handler);$cancel=[Threading.CancellationTokenSource]::new(60000)
$response=$null;$output=$null;$inputStream=$null
try {
    for ($hop=0;$hop -lt 4;$hop++) {
        if ($uri.Scheme -ne 'https' -or $uri.Port -ne 443 -or $uri.UserInfo -or
            $uri.Host -notin @('github.com','release-assets.githubusercontent.com','objects.githubusercontent.com')) {
            throw 'REDIRECT_ORIGIN_REFUSED'
        }
        $request=[Net.Http.HttpRequestMessage]::new([Net.Http.HttpMethod]::Get,$uri)
        try {$response=$client.SendAsync($request,[Net.Http.HttpCompletionOption]::ResponseHeadersRead,$cancel.Token).GetAwaiter().GetResult()}
        finally {$request.Dispose()}
        $status=[int]$response.StatusCode
        if ($status -eq 200) {break}
        if ($status -notin @(301,302,303,307,308) -or !$response.Headers.Location) {
            throw 'DOWNLOAD_REFUSED_NO_RETRY'
        }
        $uri=[Uri]::new($uri,$response.Headers.Location);$response.Dispose();$response=$null
    }
    if ($null -eq $response -or [int]$response.StatusCode -ne 200) {throw 'REDIRECT_LIMIT'}
    $inputStream=$response.Content.ReadAsStreamAsync($cancel.Token).GetAwaiter().GetResult()
    $output=[IO.File]::Open($candidate,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    $buffer=[byte[]]::new(65536);$total=0L
    while ($true) {
        $count=$inputStream.ReadAsync($buffer,0,[Math]::Min($buffer.Length,51637701-$total),$cancel.Token).GetAwaiter().GetResult()
        if ($count -eq 0) {break}
        $total+=$count
        if ($total -gt 51637700) {throw 'CANDIDATE_SIZE_REFUSED'}
        $output.Write($buffer,0,$count)
    }
    if ($total -ne 51637700) {throw 'CANDIDATE_SIZE_REFUSED'}
} catch {throw 'BOUND_CANDIDATE_TRANSFER_REFUSED_NO_RETRY'}
finally {
    if ($null -ne $output) {$output.Dispose()}
    if ($null -ne $inputStream) {$inputStream.Dispose()}
    if ($null -ne $response) {$response.Dispose()}
    $cancel.Dispose();$client.Dispose();$handler.Dispose()
}
$stream=[IO.File]::Open($candidate,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
$archive=$null
try {
    $hash=[Security.Cryptography.SHA256]::Create()
    try {$digest=[Convert]::ToHexString($hash.ComputeHash($stream)).ToLowerInvariant()}
    finally {$hash.Dispose()}
    if ($digest -ne '58486d0c92833d2358a9c0198c082065ebf3bd91cd1b76364132555ff7dbbbaf') {throw 'ORIGINAL_CANDIDATE_HASH_REQUIRED'}
    $stream.Position=0;Add-Type -AssemblyName System.IO.Compression
    $archive=[IO.Compression.ZipArchive]::new($stream,[IO.Compression.ZipArchiveMode]::Read,$true)
    if ($archive.Entries.Count -ne 3012) {throw 'CANDIDATE_MEMBERS_REFUSED'}
    $bytes=0L
    foreach ($member in $archive.Entries) {
        $name=$member.FullName;$bytes+=$member.Length
        if (!$name -or $name.Contains('\') -or $name.Contains(':') -or $name.StartsWith('/') -or $name.EndsWith('/') -or
            @($name.Split('/') | Where-Object {$_ -in @('','.', '..')}).Count -gt 0 -or $bytes -gt 192MB) {
            throw 'CANDIDATE_LAYOUT_REFUSED'
        }
    }
    $payload=Join-Path $root 'payload';New-Item -ItemType Directory -Path $payload -ErrorAction Stop | Out-Null
    foreach ($member in $archive.Entries) {
        $path=Join-Path $payload $member.FullName
        [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($path)) | Out-Null
        $source=$member.Open()
        try {
            $destination=[IO.File]::Open($path,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
            try {$source.CopyTo($destination)} finally {$destination.Dispose()}
        } finally {$source.Dispose()}
    }
} finally {if ($null -ne $archive) {$archive.Dispose()};$stream.Dispose()}
& (Join-Path $payload 'runtime/python/python.exe') -I -B $entry --execute --payload $payload --candidate-zip $candidate
if ($LASTEXITCODE -ne 0) {throw 'NATIVE_OBSERVATION_UNKNOWN_NO_RETRY'}
# No path-based recursive cleanup, public artifact upload, system repair or
# automatic re-execution. Staging/empty marker survive until runner disposal.
