"""Native-only self-authored fixture probe. Never called by application lifecycle.
Changes ACL/data ONLY on fresh child fixtures under PS-created unique private marker.
Does not auto-activate API, retry failures with weaker flags or enable privileges.
"""
import argparse
import ctypes
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'src'))
from parkweave.process_env import minimal_environment
from parkweave.store import Denied
from parkweave.windows_files import read_windows_candidate,root_parts,private_acl
from parkweave.windows_handles import WinAPI

DATA=b'SYNTHETIC Windows candidate fixture, not park data.'
FID=str(uuid.uuid4())
RESOURCE={'id':FID,'size':len(DATA),'sha256':hashlib.sha256(DATA).hexdigest()}


def acl_new(path,directory,*,unsafe=False):
    # Only called immediately after our exclusive fixture create, never user paths.
    code="$p=$env:PARKWEAVE_PROBE_ITEM;$s=[System.Security.Principal.WindowsIdentity]::GetCurrent().User;"
    code+="$a=New-Object System.Security.AccessControl."+('DirectorySecurity;' if directory else 'FileSecurity;')
    code+="$a.SetOwner($s);$a.SetAccessRuleProtection($true,$false);$r=New-Object System.Security.AccessControl.FileSystemAccessRule($s,'FullControl','Allow');$a.AddAccessRule($r);"
    if unsafe:code+="$e=New-Object System.Security.Principal.SecurityIdentifier('S-1-1-0');$r=New-Object System.Security.AccessControl.FileSystemAccessRule($e,'Read','Allow');$a.AddAccessRule($r);"
    code+="Set-Acl -LiteralPath $p -AclObject $a"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',code],
        env=minimal_environment(os.environ,PARKWEAVE_PROBE_ITEM=str(path)),capture_output=True,timeout=15)
    if result.returncode:raise RuntimeError('fixture ACL preparation failed')


def fixture(base,label,*,bad_root=False,bad_files=False,bad_file=False):
    root=base/label;root.mkdir();acl_new(root,True,unsafe=bad_root)
    files=root/'files';files.mkdir();acl_new(files,True,unsafe=bad_files)
    target=files/(FID+'.txt')
    with target.open('xb') as f:f.write(DATA)
    acl_new(target,False,unsafe=bad_file)
    return root,target


def rejected(call):
    try:call()
    except Denied:return
    raise AssertionError('candidate unexpectedly accepted adversarial fixture')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--fixture-dir',required=True,type=Path);args=parser.parse_args()
    if os.name!='nt' or platform.release()!='11' or sys.version_info[:2]!=(3,12) or ctypes.sizeof(ctypes.c_void_p)!=8:
        print('NOT_RUN: explicit native Windows11 / Python3.12 x64 required. No fixture changed.');return 1
    base=args.fixture_dir
    if not base.is_absolute() or base.parent!=REPO/'.runtime' or not base.name.startswith('windows-file-candidate-'):
        print('REFUSED: unique script-created fixture required');return 1
    try:uuid.UUID(base.name.removeprefix('windows-file-candidate-'))
    except ValueError:return 1
    api=WinAPI()
    # Read-only handle verification before any child fixture writes. Existing root
    # must be private; retain every ancestor handle through the entire probe.
    from parkweave.windows_files import metadata
    with ExitStack() as stack:
        def hold(h):stack.callback(api.close,h);return h
        drive,parts=root_parts(str(base));parent=hold(api.open_drive(drive))
        volume=api.info(parent).volume
        for part in parts:
            parent=hold(api.open_relative(parent,part,False));metadata(api.info(parent),True,volume)
        private_acl(api.security(parent),api.user_sid())
        marker=hold(api.open_relative(parent,'SYNTHETIC-CANDIDATE-ONLY.txt',True))
        marker_info=api.info(marker);metadata(marker_info,False,volume)
        private_acl(api.security(marker),api.user_sid())
        expected=b'ParkWeave self-authored fixture; no API activation.'
        if marker_info.size!=len(expected) or api.read(marker,len(expected)+1)!=expected:return 1
        return run_probe(base,api)


def run_probe(base,api):
    results=[]
    def test(label,call):
        try:call();results.append({'case':label,'status':'PASS'})
        except Exception as exc:results.append({'case':label,'status':'FAIL','category':type(exc).__name__,**({'safe_reason':str(exc)} if isinstance(exc,Denied) else {})})
    # First positive oracle must pass before adversarial Denied is meaningful.
    root,target=fixture(base,'safe')
    def positive():assert read_windows_candidate(str(root),RESOURCE)==DATA
    test('safe_handle_read',positive)
    if results[-1]['status']=='PASS':
        for label,options in [('unsafe_root',{'bad_root':True}),('unsafe_files',{'bad_files':True}),('unsafe_file',{'bad_file':True})]:
            bad,_=fixture(base,label,**options)
            test(label,lambda bad=bad:rejected(lambda:read_windows_candidate(str(bad),RESOURCE)))
        def integrity():rejected(lambda:read_windows_candidate(str(root),RESOURCE|{'sha256':'0'*64}))
        test('integrity_mismatch',integrity)
        def ids():
            for value in (FID+':stream','..\\outside',str(target)):
                rejected(lambda value=value:read_windows_candidate(str(root),RESOURCE|{'id':value}))
        test('ids_ads_path_traversal',ids)
        hard,hardfile=fixture(base,'hardlink');os.link(hardfile,base/'synthetic-hardlink.txt')
        test('hardlink_refused',lambda:rejected(lambda:read_windows_candidate(str(hard),RESOURCE)))
        # Junction needs no symlink privilege; only fresh fixture aliases.
        alias=base/'junction'
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
            "New-Item -ItemType Junction -Path $env:PARKWEAVE_PROBE_ALIAS -Target $env:PARKWEAVE_PROBE_TARGET -ErrorAction Stop | Out-Null"],
            env=minimal_environment(os.environ,PARKWEAVE_PROBE_ALIAS=str(alias),PARKWEAVE_PROBE_TARGET=str(root)),capture_output=True,timeout=15)
        if result.returncode:results.append({'case':'ancestor_junction','status':'NOT_RUN','category':'JUNCTION_CREATION_UNAVAILABLE'})
        else:test('ancestor_junction',lambda:rejected(lambda:read_windows_candidate(str(alias),RESOURCE)))
        def sharing():
            drive,parts=root_parts(str(root))
            with ExitStack() as stack:
                def hold(h):stack.callback(api.close,h);return h
                parent=hold(api.open_drive(drive))
                for part in parts:parent=hold(api.open_relative(parent,part,False))
                directory=hold(api.open_relative(parent,'files',False));item=hold(api.open_relative(directory,FID+'.txt',True))
                # Existing ACL snapshot before and after attempted mutation stays identical.
                before=api.security(item)
                try:os.rename(target,target.with_name('renamed.txt'))
                except OSError:pass
                else:raise AssertionError('rename of held file unexpectedly permitted')
                try:
                    with target.open('ab') as f:f.write(b'UNEXPECTED')
                except OSError:pass
                else:raise AssertionError('writer against held file unexpectedly permitted')
                assert api.security(item)==before
                private_acl(before,api.user_sid())
        test('held_file_blocks_write_and_rename',sharing)
        # File symlink privilege is optional, report NOT_RUN instead of bypass/elevation.
        linked,linkedfile=fixture(base,'symlink');linkedfile.unlink()
        try:os.symlink(target,linkedfile)
        except OSError:results.append({'case':'file_symlink','status':'NOT_RUN','category':'SYMLINK_PRIVILEGE_UNAVAILABLE'})
        else:test('file_symlink',lambda:rejected(lambda:read_windows_candidate(str(linked),RESOURCE)))
    else:results.append({'case':'remaining_native_oracles','status':'NOT_RUN','category':'POSITIVE_ORACLE_FAILED_NO_FALLBACK'})
    report={'project':'ParkWeave','scope':'UNACTIVATED_READ_ONLY_CANDIDATE','fixture':'SELF_AUTHORED_SYNTHETIC',
            'windows':platform.version(),'python':platform.python_version(),'architecture':platform.machine(),
            'cases':results,'whole_F1_AT_EX':'NOT_RUN','api_file_backend':'DISABLED','real_model_calls':0}
    with (base/'candidate-report.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    acl_new(base/'candidate-report.json',False)
    print(json.dumps({'candidate_cases':{s:sum(r['status']==s for r in results) for s in ('PASS','FAIL','NOT_RUN')},'whole_F1_AT_EX':'NOT_RUN','api_file_backend':'DISABLED'}))
    return 0 if all(r['status']=='PASS' for r in results) else 1

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        print('Windows candidate probe refused: '+type(exc).__name__+'; no existing ACL repair or fallback.',file=sys.stderr)
        raise SystemExit(1)
