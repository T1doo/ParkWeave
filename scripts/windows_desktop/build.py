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


COMPILERS = {
    '02aa270f183da276e5b5920b1dac44a63f1a49e55050ebde3aecc9eb82f93239': ('zig-x86_64-linux-0.15.2','tar'),
    '3a0ed1e8799a2f8ce2a6e6290a9ff22e6906f8227865911fb7ddedc3cc14cb0c': ('zig-x86_64-windows-0.15.2','zip'),
}


def file_digest(path):
    import hashlib
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify_compiler(archive_path,compiler_root):
    # Exact official distributions; never trust an adjacent self-written hash.
    import hashlib,stat
    checksum=file_digest(archive_path)
    if checksum not in COMPILERS:raise ValueError('OFFICIAL_COMPILER_DISTRIBUTION_REQUIRED')
    stem,kind=COMPILERS[checksum];expected=set();folded=set()
    def verify(name,stream):
        from pathlib import PurePosixPath
        path=PurePosixPath(name)
        if '\\' in name or ':' in name or path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0]!=stem or len(path.parts)<2:
            raise ValueError('COMPILER_ARCHIVE_LAYOUT')
        relative=Path(*path.parts[1:]);key=relative.as_posix()
        if key.casefold() in folded:raise ValueError('COMPILER_ARCHIVE_DUPLICATE')
        folded.add(key.casefold());expected.add(key);target=compiler_root/relative
        if target.is_symlink() or target.resolve()!=target.absolute():raise ValueError('COMPILER_TREE_ALIAS')
        if file_digest(target)!=hashlib.file_digest(stream,'sha256').hexdigest():raise ValueError('COMPILER_TREE_DRIFT')
    if kind=='zip':
        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                if member.is_dir():continue
                mode=stat.S_IFMT(member.external_attr>>16)
                if mode not in (0,stat.S_IFREG):raise ValueError('COMPILER_ARCHIVE_OBJECT')
                with archive.open(member) as stream:verify(member.filename,stream)
    else:
        with tarfile.open(archive_path) as archive:
            for member in archive:
                if member.isdir():continue
                if not member.isfile():raise ValueError('COMPILER_ARCHIVE_OBJECT')
                with archive.extractfile(member) as stream:verify(member.name,stream)
    actual={p.relative_to(compiler_root).as_posix() for p in compiler_root.rglob('*') if p.is_file()}
    if actual!=expected:raise ValueError('COMPILER_TREE_EXTRA_OR_MISSING')
    return checksum,expected


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--zig',type=Path,required=True)
    p.add_argument('--zig-archive',type=Path,required=True)
    p.add_argument('--sdk',type=Path,required=True)
    p.add_argument('--python-asset',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--bootstrap-root',type=Path,required=True)
    p.add_argument('--ui-driver-output',type=Path)
    args=p.parse_args()
    for name in ('zig','zig_archive','sdk','python_asset','output','bootstrap_root','ui_driver_output'):
        value=getattr(args,name)
        if value is not None:setattr(args,name,value.absolute())
    build_script_sha256=sha256(Path(__file__).read_bytes()).hexdigest()
    root=Path(__file__).resolve().parents[2]
    lock=json.loads((root/'scripts/windows_portable/runtime-assets.json').read_text())
    python=next(x for x in lock['assets'] if x['kind']=='python')
    raw=args.sdk.read_bytes()
    if sha256(raw).hexdigest()!=SDK_SHA:raise ValueError('OFFICIAL_SDK_HASH_REQUIRED')
    if sha256(args.python_asset.read_bytes()).hexdigest()!=python['sha256']:raise ValueError('ORIGINAL_PYTHON_ASSET_REQUIRED')
    compiler_root=args.zig.parent
    compiler_distribution,expected=verify_compiler(args.zig_archive,compiler_root)
    compiler_sha=file_digest(args.zig)
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
        settings_header=Path(__file__).with_name('webview_settings.h').read_bytes()
        (work/'EventToken.h').write_bytes(compatibility_header)
        (work/'namespace_guard.h').write_bytes(namespace_header)
        (work/'webview_settings.h').write_bytes(settings_header)
        startup_policy=Path(__file__).with_name('startup_policy.h').read_bytes()
        (work/'startup_policy.h').write_bytes(startup_policy)
        # Preserve the official SDK ABI. MinGW does not emit uuidof metadata
        # from MIDL_INTERFACE; generate typed IID constants from that same SDK.
        iids='template<class T>const GUID& interfaceID();\n'
        for guid,name in re.findall(r'MIDL_INTERFACE\("([0-9a-fA-F-]+)"\)\s*(\w+)\s*:',sdk_header.decode()):
            a,b,c,d,e=guid.split('-');tail=d+e
            iids+='template<>inline const GUID& interfaceID<'+name+'>(){static const GUID id={0x'+a+',0x'+b+',0x'+c+',{'+','.join('0x'+tail[i:i+2] for i in range(0,16,2))+'}};return id;}\n'
        (work/'sdk_iids.h').write_text(iids)
        if sha256(loader).hexdigest()!=LOADER_SHA:raise ValueError('OFFICIAL_LOADER_HASH_REQUIRED')
        with zipfile.ZipFile(args.python_asset) as z:python_exe=sha256(z.read('python.exe')).hexdigest()
        from scripts.windows_portable.payload import verify_directory
        manifest=verify_directory(args.bootstrap_root)
        pins={n:r for n,r in manifest['files'].items() if n!='static-dll-audit.json'}
        header='#define WEBVIEW_LOADER_SHA256 "'+LOADER_SHA+'"\n#define PYTHON_SHA256 "'+python_exe+'"\n'
        header+='struct BootstrapPin {const wchar_t* name;const char* digest;};\nstatic const BootstrapPin BOOTSTRAP_PINS[]={\n'
        header+=''.join('{L'+json.dumps(n.replace('/','\\'))+','+json.dumps(row['sha256'])+'},\n' for n,row in sorted(pins.items()))+'};\n'
        (work/'desktop_pins.h').write_text(header)
        icon_raw=(root/'src/parkweave/assets/parkweave.ico').read_bytes()
        if icon_raw[:4]!=b'\x00\x00\x01\x00':raise ValueError('WINDOWS_ICON_REQUIRED')
        (work/'parkweave.ico').write_bytes(icon_raw)
        (work/'app-icon.rc').write_text('1 ICON "parkweave.ico"\n',encoding='ascii')
        from scripts.windows_desktop.startup_document import render
        startup_html=render(root)
        if ')PWSTARTUP"' in startup_html:raise ValueError('STARTUP_LITERAL_BOUNDARY')
        (work/'startup_html.h').write_text('static const char STARTUP_HTML[]=u8R"PWSTARTUP('+startup_html+')PWSTARTUP";\n',encoding='utf-8')
        source=Path(__file__).with_name('host.cpp')
        source_raw=source.read_bytes();snapshot=work/'host.cpp';snapshot.write_bytes(source_raw)
        command=[str(args.zig),'c++','-target','x86_64-windows-gnu','-std=c++17','-O2','-fms-extensions',
            '-g0','-s','-municode','-Wl,--subsystem,windows','-static','-I',str(work),str(snapshot),str(work/'app-icon.res'),'-o',str(work/'ParkWeave.exe'),
            '-luser32','-lgdi32','-lshell32','-lole32','-ladvapi32','-lwintrust','-lcrypt32','-lbcrypt','-lcomdlg32','-luuid']
        environment={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','TMPDIR':str(work),
            'ZIG_LIB_DIR':str(compiler_root/'lib'),'ZIG_GLOBAL_CACHE_DIR':str(args.output.parent/'zig-global-cache'),
            'ZIG_LOCAL_CACHE_DIR':str(args.output.parent/'zig-local-cache')}
        if os.name=='nt':
            system_root=os.environ['SystemRoot']
            environment.update(PATH=str(Path(system_root)/'System32'),SystemRoot=system_root,TEMP=str(work),TMP=str(work))
        subprocess.run([str(args.zig),'rc','/fo',str(work/'app-icon.res'),str(work/'app-icon.rc')],cwd=work,check=True,timeout=60,env=environment)
        subprocess.run(command,check=True,timeout=240,env=environment)
        (args.output/'ParkWeave.exe').write_bytes((work/'ParkWeave.exe').read_bytes())
        ui_driver=None
        if args.ui_driver_output is not None:
            driver_source=Path(__file__).with_name('trial_ui_driver.cpp').read_bytes()
            (work/'trial_ui_driver.cpp').write_bytes(driver_source)
            driver_command=[str(args.zig),'c++','-target','x86_64-windows-gnu','-std=c++17','-O2','-g0','-s','-static',
                str(work/'trial_ui_driver.cpp'),'-o',str(work/'trial-ui-driver.exe'),
                '-lole32','-loleaut32','-luuid','-luser32','-lgdi32','-lwindowscodecs','-lbcrypt']
            subprocess.run(driver_command,check=True,timeout=120,env=environment)
            driver=(work/'trial-ui-driver.exe').read_bytes()
            args.ui_driver_output.parent.mkdir(parents=True,exist_ok=True)
            with args.ui_driver_output.open('xb') as stream:stream.write(driver)
            ui_driver=dict(source_sha256=sha256(driver_source).hexdigest(),bytes=len(driver),sha256=sha256(driver).hexdigest(),
                native_execution=False,scope='CI_ONLY_UIA_PRIVATE_PIPE_DRIVER_NOT_A_PRODUCT_ENTRY')
    (args.output/'WebView2Loader.dll').write_bytes(loader)
    (args.output/'WebView2-SDK-LICENSE.txt').write_bytes(license)
    notices='ParkWeave desktop compiler/runtime notices; upstream texts retained unchanged.\n'
    for name in ('LICENSE','lib/libcxx/LICENSE.TXT','lib/libcxxabi/LICENSE.TXT','lib/libunwind/LICENSE.TXT','lib/libc/mingw/COPYING'):
        notices+='\n===== Zig0.15.2/'+name+' =====\n'+(compiler_root/name).read_text()+'\n'
    (args.output/'Desktop-Runtime-NOTICES.txt').write_text(notices)
    record=dict(schema='parkweave-desktop-build/1',host_source_sha256=sha256(source_raw).hexdigest(),
        startup_document_sha256=sha256(startup_html.encode('utf-8')).hexdigest(),startup_policy_sha256=sha256(startup_policy).hexdigest(),
        build_script_sha256=build_script_sha256,icon_sha256=sha256(icon_raw).hexdigest(),
        compiler='Zig0.15.2 x86_64-windows-gnu',compiler_distribution_sha256=compiler_distribution,
        compiler_binary_sha256=compiler_sha,compiler_archive_and_binary_verified=True,
        compiler_tree_files_verified=len(expected),compiler_environment='explicit,no inherited compiler search variables',
        bootstrap_files=pins,bootstrap_header_sha256=sha256(header.encode()).hexdigest(),
        compatibility_header_sha256=sha256(compatibility_header).hexdigest(),
        namespace_policy_sha256=sha256(namespace_header).hexdigest(),
        settings_policy_sha256=sha256(settings_header).hexdigest(),
        sdk='Microsoft.Web.WebView2/1.0.3537.50',sdk_sha256=SDK_SHA,python_sha256=python_exe,
        native_windows_execution=False,desktop_product_acceptance=False,ui_driver=ui_driver,
        files={n:dict(bytes=(args.output/n).stat().st_size,sha256=sha256((args.output/n).read_bytes()).hexdigest())
               for n in ('ParkWeave.exe','WebView2Loader.dll','WebView2-SDK-LICENSE.txt','Desktop-Runtime-NOTICES.txt')})
    (args.output/'desktop-build.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
