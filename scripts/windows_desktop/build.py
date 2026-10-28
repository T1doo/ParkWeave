"""Offline real AMD64 PE compilation with explicit official locked inputs.

No downloads, Windows execution, runtime installation or publication.
"""
import argparse
from hashlib import sha256
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import tarfile
import zipfile

SDK_SHA='5ea526bbd728adda0da4d31219267e96460494a427e4894c4e09d9f320f4b9aa'
LOADER_SHA='2f965e10aed3b356a408978a0e6d74eb86e3e722dd008fa9ad39f68884479e85'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zig',type=Path,required=True)
    p.add_argument('--zig-archive',type=Path,required=True)
    p.add_argument('--sdk',type=Path,required=True)
    p.add_argument('--python-asset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bootstrap-root',type=Path,required=True)
    args=p.parse_args()
    build_script_sha256=sha256(Path(__file__).read_bytes()).hexdigest()
    root=Path(__file__).resolve().parents[2]
    lock=json.loads((root/'scripts/windows_portable/runtime-assets.json').read_text())
    python=next(x for x in lock['assets'] if x['kind']=='python')
    raw=args.sdk.read_bytes()
    if sha256(raw).hexdigest()!=SDK_SHA:raise ValueError('OFFICIAL_SDK_HASH_REQUIRED')
    if sha256(args.python_asset.read_bytes()).hexdigest()!=python['sha256']:raise ValueError('ORIGINAL_PYTHON_ASSET_REQUIRED')
    compiler_distribution='02aa270f183da276e5b5920b1dac44a63f1a49e55050ebde3aecc9eb82f93239'
    def digest(path):
        import hashlib
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    if digest(args.zig_archive)!=compiler_distribution:raise ValueError('OFFICIAL_COMPILER_DISTRIBUTION_REQUIRED')
    import hashlib
    compiler_root=args.zig.parent
    expected=set()
    with tarfile.open(args.zig_archive) as archive:
        for member in archive:
            name=Path(member.name)
            if name.parts[0]!='zig-x86_64-linux-0.15.2' or '..' in name.parts or name.is_absolute():raise ValueError('COMPILER_ARCHIVE_LAYOUT')
            if member.isdir():continue
            if not member.isfile():raise ValueError('COMPILER_ARCHIVE_OBJECT')
            relative=Path(*name.parts[1:]);path=compiler_root/relative;expected.add(relative.as_posix())
            if path.is_symlink() or path.resolve()!=path.absolute():raise ValueError('COMPILER_TREE_ALIAS')
            with archive.extractfile(member) as stream:locked=hashlib.file_digest(stream,'sha256').hexdigest()
            if digest(path)!=locked:raise ValueError('COMPILER_TREE_DRIFT')
    actual={p.relative_to(compiler_root).as_posix() for p in compiler_root.rglob('*') if p.is_file()}
    if actual!=expected:raise ValueError('COMPILER_TREE_EXTRA_OR_MISSING')
    compiler_sha=digest(args.zig)
    version=subprocess.check_output([str(args.zig),'version'],text=True).strip()
    if version!='0.15.2':raise ValueError('LOCKED_ZIG_VERSION_REQUIRED')
    args.output.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='parkweave-desktop-compile-') as temp:
        work=Path(temp)
        with zipfile.ZipFile(args.sdk) as z:
            sdk_header=z.read('build/native/include/WebView2.h')
            (work/'WebView2.h').write_bytes(sdk_header)
            loader=z.read('build/native/x64/WebView2Loader.dll');license=z.read('LICENSE.txt')
        compatibility_header=Path(__file__).with_name('EventToken.h').read_bytes()
        namespace_header=Path(__file__).with_name('namespace_guard.h').read_bytes()
        (work/'EventToken.h').write_bytes(compatibility_header)
        (work/'namespace_guard.h').write_bytes(namespace_header)
        # Preserve the official SDK ABI. MinGW does not emit uuidof metadata
        # from MIDL_INTERFACE; generate typed IID constants from that same SDK.
        iids='template<class T>const GUID& interfaceID();\n'
        for guid,name in re.findall(r'MIDL_INTERFACE\("([0-9a-fA-F-]+)"\)\s*(\w+)\s*:',sdk_header.decode()):
            a,b,c,d,e=guid.split('-');tail=d+e
            iids+='template<>inline const GUID& interfaceID<'+name+'>(){static const GUID id={0x'+a+',0x'+b+',0x'+c+',{'+','.join('0x'+tail[i:i+2] for i in range(0,16,2))+'}};return id;}\n'
        (work/'sdk_iids.h').write_text(iids)
        if sha256(loader).hexdigest()!=LOADER_SHA:raise ValueError('OFFICIAL_LOADER_HASH_REQUIRED')
        with zipfile.ZipFile(args.python_asset) as z:pythonw=sha256(z.read('pythonw.exe')).hexdigest()
        from scripts.windows_portable.payload import verify_directory
        manifest=verify_directory(args.bootstrap_root)
        pins={n:r for n,r in manifest['files'].items() if n!='static-dll-audit.json'}
        header='#define WEBVIEW_LOADER_SHA256 "'+LOADER_SHA+'"\n#define PYTHONW_SHA256 "'+pythonw+'"\n'
        header+='struct BootstrapPin {const wchar_t* name;const char* digest;};\nstatic const BootstrapPin BOOTSTRAP_PINS[]={\n'
        header+=''.join('{L'+json.dumps(n.replace('/','\\'))+','+json.dumps(row['sha256'])+'},\n' for n,row in sorted(pins.items()))+'};\n'
        (work/'desktop_pins.h').write_text(header)
        source=Path(__file__).with_name('host.cpp')
        source_raw=source.read_bytes();snapshot=work/'host.cpp';snapshot.write_bytes(source_raw)
        command=[str(args.zig),'c++','-target','x86_64-windows-gnu','-std=c++17','-O2','-fms-extensions',
            '-g0','-s','-municode','-Wl,--subsystem,windows','-static','-I',str(work),str(snapshot),'-o',str(work/'ParkWeave.exe'),
            '-luser32','-lgdi32','-lshell32','-lole32','-ladvapi32','-lwintrust','-lcrypt32','-lbcrypt','-lcomdlg32','-luuid']
        environment={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','TMPDIR':str(work),
            'ZIG_LIB_DIR':str(compiler_root/'lib'),'ZIG_GLOBAL_CACHE_DIR':str(args.output.parent/'zig-global-cache'),
            'ZIG_LOCAL_CACHE_DIR':str(args.output.parent/'zig-local-cache')}
        subprocess.run(command,check=True,timeout=240,env=environment)
        (args.output/'ParkWeave.exe').write_bytes((work/'ParkWeave.exe').read_bytes())
    (args.output/'WebView2Loader.dll').write_bytes(loader)
    (args.output/'WebView2-SDK-LICENSE.txt').write_bytes(license)
    notices='ParkWeave desktop compiler/runtime notices; upstream texts retained unchanged.\n'
    for name in ('LICENSE','lib/libcxx/LICENSE.TXT','lib/libcxxabi/LICENSE.TXT','lib/libunwind/LICENSE.TXT','lib/libc/mingw/COPYING'):
        notices+='\n===== Zig0.15.2/'+name+' =====\n'+(compiler_root/name).read_text()+'\n'
    (args.output/'Desktop-Runtime-NOTICES.txt').write_text(notices)
    record=dict(schema='parkweave-desktop-build/1',host_source_sha256=sha256(source_raw).hexdigest(),
        build_script_sha256=build_script_sha256,
        compiler='Zig0.15.2 x86_64-windows-gnu',compiler_distribution_sha256=compiler_distribution,
        compiler_binary_sha256=compiler_sha,compiler_archive_and_binary_verified=True,
        compiler_tree_files_verified=len(expected),compiler_environment='explicit,no inherited compiler search variables',
        bootstrap_files=pins,bootstrap_header_sha256=sha256(header.encode()).hexdigest(),
        compatibility_header_sha256=sha256(compatibility_header).hexdigest(),
        namespace_policy_sha256=sha256(namespace_header).hexdigest(),
        sdk='Microsoft.Web.WebView2/1.0.3537.50',sdk_sha256=SDK_SHA,pythonw_sha256=pythonw,
        native_windows_execution=False,desktop_product_acceptance=False,
        files={n:dict(bytes=(args.output/n).stat().st_size,sha256=sha256((args.output/n).read_bytes()).hexdigest())
               for n in ('ParkWeave.exe','WebView2Loader.dll','WebView2-SDK-LICENSE.txt','Desktop-Runtime-NOTICES.txt')})
    (args.output/'desktop-build.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
