#requires -Version 5.1
param([string[]]$SystemDlls=@('vcruntime140.dll','msvcp140.dll','ApiSetSchema.dll'))
$ErrorActionPreference='Stop'
# Metadata only, stdout only. The existing coordinator owns the outer time
# budget and any E:\Software report file. No setters, Add-Type, child process,
# LoadLibrary, installation, account, credential or product start occurs here.
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or
    ![Environment]::Is64BitProcess) {throw 'NATIVE_64BIT_WINDOWS_METADATA_REQUIRED'}
if (!$SystemDlls -or $SystemDlls.Count -gt 64) {throw 'BOUNDED_SYSTEM_NAMES_REQUIRED'}
$names=@()
foreach ($name in $SystemDlls) {
    if ($name -notmatch '^[A-Za-z0-9_-]+\.dll$' -or $name -match '^(api|ext)-ms-') {
        throw 'DLL_BASENAME_ONLY_NO_VIRTUAL_API_SET_FILES'
    }
    if ($names -contains $name.ToLowerInvariant()) {throw 'UNIQUE_SYSTEM_NAMES_REQUIRED'}
    $names+=$name.ToLowerInvariant()
}
$system=[Environment]::GetFolderPath([Environment+SpecialFolder]::System)
if (![IO.Path]::IsPathRooted($system)) {throw 'ACTUAL_SYSTEM_DIRECTORY_REQUIRED'}
$cv=Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion'
$osArch=$null;$processArch=$null
try {
    $osArch=[Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString()
    $processArch=[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString()
} catch {} # Unknown remains explicit; environment architecture strings are not authority.
$files=@()
foreach ($name in $names) {
    $path=Join-Path $system $name
    $row=[ordered]@{name=$name;path=$path;status='UNKNOWN';size=$null;sha256=$null;
        pe_machine=$null;file_version=$null;signature_status='NOT_COLLECTED_CACHE_ONLY_WITNESS_REQUIRED';signer_subject=$null;
        signer_issuer=$null;signer_thumbprint=$null;identity='NOT_COLLECTED';error_type=$null}
    $stream=$null;$hash=$null
    try {
        $before=Get-Item -LiteralPath $path -Force
        if ($before.PSIsContainer -or ($before.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'ORDINARY_EXISTING_SYSTEM_FILE_REQUIRED'
        }
        $stream=[IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read)
        if ($stream.Length -lt 64 -or $stream.Length -gt 134217728) {throw 'BOUNDED_PE_REQUIRED'}
        $row.size=$stream.Length
        $hash=[Security.Cryptography.SHA256]::Create()
        $row.sha256=[BitConverter]::ToString($hash.ComputeHash($stream)).Replace('-','').ToLowerInvariant()
        $stream.Position=0;$header=New-Object byte[] 64
        if ($stream.Read($header,0,64) -ne 64 -or $header[0] -ne 77 -or $header[1] -ne 90) {
            throw 'PE_DOS_HEADER_REQUIRED'
        }
        $offset=[BitConverter]::ToUInt32($header,60)
        if ($offset -gt ($stream.Length - 6)) {throw 'PE_HEADER_BOUNDS'}
        $stream.Position=$offset;$pe=New-Object byte[] 6
        if ($stream.Read($pe,0,6) -ne 6 -or $pe[0] -ne 80 -or $pe[1] -ne 69 -or
            $pe[2] -ne 0 -or $pe[3] -ne 0) {throw 'PE_SIGNATURE_REQUIRED'}
        $row.pe_machine=('0x{0:x4}' -f [BitConverter]::ToUInt16($pe,4))
        $row.file_version=[Diagnostics.FileVersionInfo]::GetVersionInfo($path).FileVersion
        # Get-AuthenticodeSignature can retrieve chain/revocation information
        # and update OS caches. This minimal offline collector does not call it;
        # the original cache-only native witness remains a separate requirement.
        $after=Get-Item -LiteralPath $path -Force
        if ($before.Length -ne $after.Length -or $before.LastWriteTimeUtc -ne $after.LastWriteTimeUtc -or
            ($after.Attributes -band [IO.FileAttributes]::ReparsePoint)) {throw 'FILE_CHANGED_DURING_METADATA'}
        $row.status='OBSERVED_METADATA_ONLY'
    } catch {
        $row.error_type=$_.Exception.GetType().Name
    } finally {
        if ($null -ne $hash) {$hash.Dispose()}
        if ($null -ne $stream) {$stream.Dispose()}
    }
    $files+=[pscustomobject]$row
}
[ordered]@{schema='parkweave-windows-loader-target/1';captured_utc=[DateTime]::UtcNow.ToString('o');
    os=[ordered]@{nt_major=$cv.CurrentMajorVersionNumber;nt_minor=$cv.CurrentMinorVersionNumber;
        build=[int]$cv.CurrentBuildNumber;ubr=$cv.UBR;edition_id=$cv.EditionID;installation_type=$cv.InstallationType};
    architecture=[ordered]@{os_64bit=[Environment]::Is64BitOperatingSystem;process_64bit=[Environment]::Is64BitProcess;
        os_architecture=$osArch;process_architecture=$processArch;native_machine=$null;process_machine=$null};
    system_directory=$system;system_files=$files;api_set_mapping='NOT_COLLECTED';
    target_export_tables='NOT_COLLECTED';loaded_origins='NOT_RUN';
    observation_scope='COOPERATIVE_METADATA_SNAPSHOT_NOT_HELD_NATIVE_IDENTITY';
    response_is_native_witness=$false;activation_allowed=$false;usable_product=$false} |
    ConvertTo-Json -Depth 8
