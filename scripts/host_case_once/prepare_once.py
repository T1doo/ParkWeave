"""Separate pending once-only preparation probe; never launches a controller."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import sys
import traceback
import types

# -I -S cannot discover checkout packages. Load this exact adjacent reviewed file.
_spec=importlib.util.spec_from_file_location('prepare_bootstrap',Path(__file__).with_name('bootstrap.py'))
b=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(b)
BRANCH='refs/heads/dev/f2-prepare-only-security-once-20261013'
APPROVAL_FILE='scripts/host_case_once/prepare_approval.json'
APPROVAL_REF='USER_CONFIRMED_PREPARE_ONLY_ONCE_20261013'
CLAIM='/tmp/parkweave-prepare-only-once-20261013.claim'
for code,stage,case in [('B_PREP_FLAGS','GATE','GATE'),('B_PREP_PROBE','RUNTIME','PROTECTED_RUNTIME'),
                        ('B_PREP_OUTPUT','RUNTIME','PROTECTED_RUNTIME'),('B_PREP_CLEANUP','ROOT','FILES_REMOVED'),
                        ('B_PREP_TIMER','ROOT','PROTECTED_RUNTIME')]:
    b._checks('BOOTSTRAP',stage,(case,),code)

# Fixed program, no controller, sockets, identities, database or model invocation.
PROBE="""import sys,json,os
sys.path[:]=IMPORTS
assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
assert 'sitecustomize' not in sys.modules
import sysconfig,fastapi,uvicorn,psycopg,pydantic,httpx
for module in (sysconfig,fastapi,uvicorn,psycopg,pydantic,httpx):
 assert os.path.commonpath([module.__file__,ENVIRONMENT])==ENVIRONMENT
assert sysconfig.get_config_vars()
assert 'sitecustomize' not in sys.modules
print('PREPARE_IMPORTS_PASS')
"""


def deadline(signum,frame):raise TimeoutError('PREPARATION_DEADLINE')


def probe(context,root):
    # repr inserts only internally generated new-root paths, never executable input.
    program='IMPORTS='+repr(context['imports'])+'\nENVIRONMENT='+repr(context['environment'])+'\n'+PROBE
    with (root/'private/import-stderr.log').open('wb') as err:
        child=subprocess.run([context['environment']+'/bin/python3.12','-I','-S','-B','-c',program],
            env={'LANG':'C.UTF-8'},cwd='/',stdout=subprocess.PIPE,stderr=err,timeout=30,check=True)
    return child.stdout


def remove_owned(root,identity):
    s=root.lstat()
    if (not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022 or
            (s.st_dev,s.st_ino)!=identity or root.parent!=Path('/tmp') or
            not root.name.startswith('parkweave-prepare-')):
        raise PermissionError('OWNED_PREPARATION_ROOT_REQUIRED')
    if not shutil.rmtree.avoids_symlink_attacks:raise PermissionError('FD_SAFE_REMOVAL_REQUIRED')
    shutil.rmtree(root)
    if root.exists() or root.is_symlink():raise OSError('OWNED_REMOVAL_REQUIRED')


def owned_directory(s,identity,mode):
    permissions=stat.S_IMODE(s.st_mode)
    if (not stat.S_ISDIR(s.st_mode) or s.st_uid!=0 or permissions&~mode or permissions&0o700!=0o700 or
            (s.st_dev,s.st_ino)!=identity):
        raise PermissionError('OWNED_PRIVATE_DIRECTORY_REQUIRED')


def failure_log(root,identity,private_identity,raw):
    # Open verified directory instances, never follow a conflicting/replaced path.
    rootfd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    privatefd=None;logfd=None
    try:
        owned_directory(os.fstat(rootfd),identity,0o711)
        privatefd=os.open('private',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=rootfd)
        owned_directory(os.fstat(privatefd),private_identity,0o700)
        logfd=os.open('prepare-failure.log',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,
            0o600,dir_fd=privatefd)
        while raw:
            count=os.write(logfd,raw)
            if count<=0:raise OSError('PRIVATE_LOG_WRITE_REQUIRED')
            raw=raw[count:]
    finally:
        try:
            if logfd is not None:os.close(logfd)
        finally:
            try:
                if privatefd is not None:os.close(privatefd)
            finally:os.close(rootfd)


def run(sha):
    value=b.initial(sha);diag=b.Diagnostic(value['diagnostics']);root=None
    old_handler=None;timer_started=False;log_ready=False
    try:
        diag.checkpoint('B_PREP_FLAGS')
        if not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
            raise PermissionError('ISOLATED_NO_SITE_NO_BYTECODE_REQUIRED')
        diag.checkpoint('B_GATE')
        checkout=Path.cwd()
        source_sha=b.gate(checkout,sha,os.environ,approval_file=APPROVAL_FILE,branch=BRANCH,approval_ref=APPROVAL_REF)
        value['source_sha']=source_sha
        # Gate may spawn read-only Git; no timer, claim, directory or effectful child before approval.
        old_handler=signal.signal(signal.SIGALRM,deadline);signal.alarm(480);timer_started=True
        diag.checkpoint('B_CLAIM')
        fd=os.open(CLAIM,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:os.write(fd,(source_sha+'\n').encode())
        finally:os.close(fd)
        value['cases']['GATE']='PASS'
        diag.checkpoint('B_ROOT')
        root=Path('/tmp/parkweave-prepare-'+b.uuid4().hex);root.mkdir(mode=0o711)
        s=root.lstat();identity=(s.st_dev,s.st_ino)
        owned_directory(s,identity,0o711)
        diag.checkpoint('B_PRIVATE_DIR');(root/'private').mkdir(mode=0o700)
        s=(root/'private').lstat();private_identity=(s.st_dev,s.st_ino)
        owned_directory(s,private_identity,0o700)
        owned_directory(root.lstat(),identity,0o711)
        log_ready=True # Only after both exclusive creations and instance checks.
        value['phase']='PROTECTED_RUNTIME'
        context=b.prepare(checkout,source_sha,root,diag)
        diag.checkpoint('B_PREP_PROBE');stdout=probe(context,root)
        diag.checkpoint('B_PREP_OUTPUT')
        if stdout!=b'PREPARE_IMPORTS_PASS\n':raise ValueError('CLOSED_IMPORT_RESULT_REQUIRED')
        value['cases']['PROTECTED_RUNTIME']='PASS'
        diag.checkpoint('B_PREP_CLEANUP');signal.alarm(60)
        remove_owned(root,identity)
        value['cases']['FILES_REMOVED']='PASS';value['cleanup']=True;value['phase']='COMPLETE'
    except BaseException:
        failed=diag.capture();value['cases'][failed['case']]='FAIL'
        value['error']='TIMEOUT' if isinstance(sys.exc_info()[1],TimeoutError) else 'FAILURE'
        value['phase']='GATE' if failed['case']=='GATE' else 'PROTECTED_RUNTIME'
        if timer_started:signal.alarm(60)
        try:
            diag.checkpoint('B_PRIVATE_LOG',case='GATE' if failed['case']=='GATE' else 'PROTECTED_RUNTIME')
            if not log_ready:raise OSError('NO_OWNED_PRIVATE_ROOT')
            failure_log(root,identity,private_identity,traceback.format_exc().encode())
            value['failure_logs']='SAVED'
        except BaseException:
            diag.capture();value['failure_logs']='UNAVAILABLE'
        # Failure preserves the owned T and private logs until this fresh VM dies.
        # No false cleanup receipt, no deletion of claim, no retry in this VM.
    finally:
        if timer_started:
            try:
                diag.checkpoint('B_PREP_TIMER')
                signal.alarm(0);signal.signal(signal.SIGALRM,old_handler)
            except BaseException:
                diag.capture();value['error']='FAILURE';value['cases']['PROTECTED_RUNTIME']='FAIL'
                value['phase']='PROTECTED_RUNTIME';value['failure_logs']='UNAVAILABLE'
    print(json.dumps(b.public_summary(value),sort_keys=True))
    return 0 if value['error']=='NONE' and value['cleanup'] else 1


b.register_source('BOOTSTRAP',[v.__code__ for v in tuple(globals().values())
    if isinstance(v,types.FunctionType) and v.__module__==__name__])
if __name__=='__main__':raise SystemExit(run(sys.argv[1] if len(sys.argv)==2 else ''))
