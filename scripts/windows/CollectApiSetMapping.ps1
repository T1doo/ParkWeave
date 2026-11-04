#requires -Version 5.1
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-f0-9]{64}$')][string]$ExpectedSha256,
    [Parameter(Mandatory=$true)][string[]]$Contracts
)
$ErrorActionPreference='Stop'
# Read one existing System32 data file, stdout only. No code loading, signing
# query, Add-Type, child process, setter, account, credential or product start.
# The coordinator owns the external time budget and E:\Software output file.
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or
    ![Environment]::Is64BitProcess) {throw '64BIT_WINDOWS_METADATA_REQUIRED'}
if (!$Contracts -or $Contracts.Count -gt 64) {throw 'BOUNDED_CONTRACT_LIST_REQUIRED'}
$requested=@{}
foreach ($name in $Contracts) {
    $key=$name.ToLowerInvariant()
    if ($key.EndsWith('.dll')) {$key=$key.Substring(0,$key.Length-4)}
    if ($key -notmatch '^(api|ext)-ms-[a-z0-9]+(-[a-z0-9]+)*$' -or $requested.ContainsKey($key)) {
        throw 'UNIQUE_CONTRACT_BASENAMES_REQUIRED'
    }
    $requested[$key]=$true
}
$path=Join-Path ([Environment]::GetFolderPath([Environment+SpecialFolder]::System)) 'ApiSetSchema.dll'
$before=Get-Item -LiteralPath $path -Force
if ($before.PSIsContainer -or ($before.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'ORDINARY_SYSTEM_SCHEMA_REQUIRED'
}
$stream=$null;$hash=$null
try {
    $stream=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
    if ($stream.Length -lt 64 -or $stream.Length -gt 4194304) {throw 'BOUNDED_SCHEMA_REQUIRED'}
    $script:apiSetData=New-Object byte[] ([int]$stream.Length)
    $read=0
    while ($read -lt $script:apiSetData.Length) {
        $n=$stream.Read($script:apiSetData,$read,$script:apiSetData.Length-$read)
        if ($n -le 0) {throw 'SCHEMA_SHORT_READ'}
        $read+=$n
    }
    if ($stream.ReadByte() -ne -1) {throw 'SCHEMA_GREW'}
    $hash=[Security.Cryptography.SHA256]::Create()
    $observed=[BitConverter]::ToString($hash.ComputeHash($script:apiSetData)).Replace('-','').ToLowerInvariant()
    if ($observed -ne $ExpectedSha256) {throw 'APISET_SCHEMA_HASH_CHANGED'}
    $script:apiSetBase=0;$script:apiSetSize=$script:apiSetData.Length
    function Span([long]$Offset,[long]$Length) {
        if ($Offset -lt 0 -or $Length -lt 0 -or $Offset -gt $script:apiSetSize -or
            $Length -gt ($script:apiSetSize-$Offset)) {throw 'APISET_RANGE_REFUSED'}
    }
    function U32([long]$Offset) {
        Span $Offset 4
        return [BitConverter]::ToUInt32($script:apiSetData,[int]($script:apiSetBase+$Offset))
    }
    if ($script:apiSetData[0] -ne 77 -or $script:apiSetData[1] -ne 90) {throw 'PE_DOS_REQUIRED'}
    $pe=U32 60;Span $pe 24
    if ((U32 $pe) -ne 17744 -or [BitConverter]::ToUInt16($script:apiSetData,$pe+4) -ne 34404) {
        throw 'AMD64_PE_REQUIRED'
    }
    $count=[BitConverter]::ToUInt16($script:apiSetData,$pe+6)
    $optional=[BitConverter]::ToUInt16($script:apiSetData,$pe+20)
    if ($count -lt 1 -or $count -gt 96 -or $optional -lt 240) {throw 'PE_HEADER_REFUSED'}
    Span ($pe+24) $optional
    if ([BitConverter]::ToUInt16($script:apiSetData,$pe+24) -ne 523) {throw 'PE32_PLUS_REQUIRED'}
    $sections=$pe+24+$optional;Span $sections ($count*40)
    $found=@()
    for ($i=0;$i -lt $count;$i++) {
        $section=$sections+$i*40
        $label=[Text.Encoding]::ASCII.GetString($script:apiSetData,$section,8).TrimEnd([char[]]@(0))
        if ($label -eq '.apiset') {$found+=,@((U32 ($section+20)),(U32 ($section+16)))}
    }
    if ($found.Count -ne 1) {throw 'UNIQUE_APISET_SECTION_REQUIRED'}
    $start=[long]$found[0][0];$length=[long]$found[0][1];Span $start $length
    if ($length -lt 28 -or $length -gt 4194304) {throw 'APISET_SECTION_SIZE_REFUSED'}
    $script:apiSetBase=$start;$script:apiSetSize=$length
    $version=U32 0;$size=U32 4;$flags=U32 8;$total=U32 12
    $entries=U32 16;$hashes=U32 20;$factor=U32 24
    if ($version -ne 6 -or $size -lt 28 -or $size -gt $length -or $total -gt 20000 -or
        $factor -lt 1 -or $factor -gt 65535) {throw 'APISET_V6_HEADER_REFUSED'}
    $script:apiSetSize=$size
    if ($total -gt 0) {
        if ($entries -lt 28 -or $hashes -lt 28) {throw 'APISET_TABLE_OFFSET_REFUSED'}
        Span $entries ($total*24);Span $hashes ($total*8)
    }
    $unicode=[Text.UnicodeEncoding]::new($false,$false,$true)
    function TextAt([long]$Offset,[long]$Length) {
        if ($Length -lt 0 -or $Length -gt 1024 -or ($Length%2) -ne 0) {throw 'APISET_TEXT_LENGTH_REFUSED'}
        Span $Offset $Length
        $value=$unicode.GetString($script:apiSetData,[int]($script:apiSetBase+$Offset),[int]$Length).ToLowerInvariant()
        if ($value -notmatch '^[\x20-\x7e]*$') {throw 'APISET_TEXT_REFUSED'}
        return $value
    }
    $allNames=@{};$computed=@();$selected=@();$totalValues=0
    for ($i=0;$i -lt $total;$i++) {
        $entry=$entries+$i*24;$entryFlags=U32 $entry
        $nameOffset=U32 ($entry+4);$nameLength=U32 ($entry+8);$hashedLength=U32 ($entry+12)
        $valueOffset=U32 ($entry+16);$valueCount=U32 ($entry+20)
        $key=TextAt $nameOffset $nameLength
        if (!$key -or $key -notmatch '^(api|ext)-ms-[a-z0-9]+(-[a-z0-9]+)*$' -or
            $allNames.ContainsKey($key) -or $hashedLength -lt 1 -or ($hashedLength%2) -ne 0 -or
            $hashedLength -gt $nameLength -or $valueCount -gt 64) {throw 'APISET_ENTRY_REFUSED'}
        $totalValues+=$valueCount
        if ($totalValues -gt 65536) {throw 'APISET_VALUE_BUDGET_REFUSED'}
        $allNames[$key]=$true
        [uint64]$h=0
        foreach ($ch in (TextAt $nameOffset $hashedLength).ToCharArray()) {
            $h=($h*[uint64]$factor+[uint64][int]$ch) -band [uint64]4294967295
        }
        $computed+=,[uint32]$h
        if ($valueCount -gt 0) {Span $valueOffset ($valueCount*20)}
        $values=@();$aliases=@{}
        for ($j=0;$j -lt $valueCount;$j++) {
            $v=$valueOffset+$j*20;$valueFlags=U32 $v
            $alias=TextAt (U32 ($v+4)) (U32 ($v+8))
            $hostName=TextAt (U32 ($v+12)) (U32 ($v+16))
            if ($aliases.ContainsKey($alias) -or ($alias -and $alias -notmatch '^[a-z0-9_-]+(\.[a-z0-9_-]+)*$') -or
                ($hostName -and $hostName -notmatch '^[a-z0-9_-]+\.dll$')) {throw 'APISET_VALUE_REFUSED'}
            $aliases[$alias]=$true;$values+=[ordered]@{flags=$valueFlags;alias=$alias;host=$hostName}
        }
        if ($requested.ContainsKey($key)) {
            $selected+=[ordered]@{contract=($key+'.dll');flags=$entryFlags;hashed_length=$hashedLength;values=$values}
        }
    }
    $indices=@{};[long]$prior=-1
    for ($i=0;$i -lt $total;$i++) {
        $h=U32 ($hashes+$i*8);$index=U32 ($hashes+$i*8+4)
        if ($h -lt $prior -or $index -ge $total -or $indices.ContainsKey($index) -or $computed[$index] -ne $h) {
            throw 'APISET_HASH_INDEX_REFUSED'
        }
        $indices[$index]=$true;$prior=$h
    }
    $after=Get-Item -LiteralPath $path -Force
    if ($before.Length -ne $after.Length -or $before.LastWriteTimeUtc -ne $after.LastWriteTimeUtc -or
        ($after.Attributes -band [IO.FileAttributes]::ReparsePoint)) {throw 'SCHEMA_METADATA_CHANGED'}
    $missing=@($requested.Keys | Where-Object {!$allNames.ContainsKey($_)} | ForEach-Object {$_+'.dll'})
    [ordered]@{schema='parkweave-api-set-selected-v6/1';captured_utc=[DateTime]::UtcNow.ToString('o');
        file=[ordered]@{path=$path;size=$stream.Length;sha256=$observed;machine='AMD64';identity='NOT_COLLECTED';signature='NOT_COLLECTED'};
        namespace=[ordered]@{version=$version;size=$size;flags=$flags;count=$total;hash_factor=$factor};
        requested=@($Contracts);entries=$selected;missing_contracts=$missing;hash_index_validated=$true;
        observation_scope='FILE_DATA_SNAPSHOT_NOT_LIVE_PEB_OR_HELD_NATIVE_WITNESS';
        response_is_native_witness=$false;activation_allowed=$false;usable_product=$false} | ConvertTo-Json -Depth 10
} finally {
    if ($null -ne $hash) {$hash.Dispose()}
    if ($null -ne $stream) {$stream.Dispose()}
}
