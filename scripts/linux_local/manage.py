"""Offline Linux synthetic candidate installer/launcher; no system installation.

Python 3.12, Git and glibc x86_64 are explicit existing prerequisites. Source
and wheels are verified before use. The original local_product CLI alone creates
identities/database and starts/stops the service. No repair or automatic setup.
"""
import argparse
from contextlib import contextmanager
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import stat
import subprocess
import sys


class Refused(RuntimeError):pass

def need(ok,code):
    if not ok:raise Refused(code)

def read(path,limit=8*1024*1024):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        info=os.fstat(fd);need(stat.S_ISREG(info.st_mode) and info.st_size<=limit,'FILE_REQUIRED')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(limit+1)
        need(len(raw)<=limit,'FILE_LIMIT');return raw
    finally:os.close(fd)

def save(root,name,value):
    raw=(json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
    temporary=root/(name+'.next')
    with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,root/name)
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)

def private(root):
    s=root.stat(follow_symlinks=False)
    need(root.is_absolute() and root.resolve()==root and stat.S_ISDIR(s.st_mode)
         and s.st_uid==os.geteuid() and not s.st_mode&0o077,'PRIVATE_ROOT_REQUIRED')

@contextmanager
def locked(root):
    private(root)
    fd=os.open(root/'.manager.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==os.geteuid() and not s.st_mode&0o077,'PRIVATE_LOCK_REQUIRED')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);yield fd
    finally:os.close(fd)

def manifest(media):
    value=json.loads(read(media/'candidate.json',65536))
    need(value.get('schema')=='parkweave-linux-offline-candidate/1'
         and value.get('usable_product') is False and value.get('scope')=='LINUX_SYNTHETIC_ONLY','CANDIDATE_REQUIRED')
    for name,row in value['files'].items():
        need(type(name) is str and not name.startswith('/') and '..' not in name.split('/') and '\\' not in name,'RELATIVE_FILE_REQUIRED')
        p=media/name;need(p.resolve()==p.absolute(),'UNALIASED_PAYLOAD_REQUIRED')
        raw=read(p,128*1024*1024)
        need(len(raw)==row['bytes'] and sha256(raw).hexdigest()==row['sha256'],'PAYLOAD_HASH_MISMATCH')
    return value

def prerequisite():
    need(sys.platform=='linux' and os.geteuid()!=0 and sys.version_info[:2]==(3,12)
         and platform.machine()=='x86_64','EXISTING_NONROOT_LINUX_X64_PY312_REQUIRED')
    libc=os.confstr('CS_GNU_LIBC_VERSION')
    need(libc and libc.startswith('glibc ') and tuple(map(int,libc.split()[1].split('.')[:2]))>=(2,34),'GLIBC_2_34_REQUIRED')
    need(shutil.which('git') is not None,'EXISTING_GIT_REQUIRED')

def environment():
    value=dict(os.environ)
    for name in ('PYTHONPATH','PYTHONHOME','PYTHONSTARTUP'):value.pop(name,None)
    value['PYTHONDONTWRITEBYTECODE']='1';return value

def inventory(root):
    result={}
    for parent,dirs,files in os.walk(root,followlinks=False):
        for leaf in dirs+files:
            path=Path(parent)/leaf;s=path.lstat();name=path.relative_to(root).as_posix()
            need(s.st_uid==os.geteuid(),'APPLICATION_OWNER_CHANGED')
            if stat.S_ISLNK(s.st_mode):row=['link',os.readlink(path)]
            elif stat.S_ISDIR(s.st_mode):row=['directory',stat.S_IMODE(s.st_mode)]
            else:
                need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'APPLICATION_OBJECT_CHANGED')
                row=['file',stat.S_IMODE(s.st_mode),s.st_size,sha256(read(path,128*1024*1024)).hexdigest()]
            result[name]=row
    return result

def runtime(root,value):
    app=root/'application';need(not app.exists(),'APPLICATION_ALREADY_PRESENT')
    app.mkdir(mode=0o700)
    source=app/'source';venv=app/'venv';media=root/'media';env=environment()
    with (root/'runtime-install.log').open('ab') as log:
        commands=[['git','-c','core.hooksPath=/dev/null','clone','--branch',value['branch'],str(media/'source.bundle'),str(source)],
            [sys.executable,'-I','-B','-m','venv',str(venv)],
            [str(venv/'bin/python'),'-B','-m','pip','--isolated','install','--no-index','--find-links',str(media/'wheelhouse'),
             '--require-hashes','--no-compile','-r',str(media/'requirements.lock')],
            [str(venv/'bin/python'),'-B','-m','pip','--isolated','install','--no-index','--no-build-isolation','--no-deps','--no-compile','-e',str(source)],
            [str(venv/'bin/python'),'-B','-m','pip','--isolated','check']]
        for command in commands:
            subprocess.run(command,env=env,stdout=log,stderr=log,check=True,timeout=120)
            if command is commands[0]:
                actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,env=env,text=True).strip()
                need(actual==value['source_commit'],'SOURCE_ID_MISMATCH')
    save(root,'application-inventory.json',inventory(app))

def state(root):
    value=json.loads(read(root/'installation.json',8192))
    need(value.get('schema')=='parkweave-linux-user-installation/1','INSTALLATION_REQUIRED')
    return value

def selection(root,record):
    path=Path(record.get('state_dir') or '')
    need(path.is_absolute() and path.parent==root/'data' and path.name.startswith('pw-'),'ORIGINAL_DATA_REQUIRED')
    private(path);return path

@contextmanager
def stopped(root,record):
    if record['setup']=='NOT_STARTED':yield;return
    need(record['setup']=='COMPLETE','SETUP_NOT_CONFIRMED_KEEP_ALL_FILES')
    path=selection(root,record)
    fd=os.open(path/'.local-installation.lock',os.O_RDWR|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        row=json.loads(read(path/'.local-installation.json',8192))
        need(row['phase'] in ('READY_STOPPED','RELEASE_PENDING') and not (path/'data/postmaster.pid').exists()
             and not (path/'stop-unconfirmed').exists(),'STOP_NOT_CONFIRMED_KEEP_ALL_FILES')
        yield
    finally:os.close(fd)

def cli(root,*args):
    return [str(root/'application/venv/bin/python'),'-B','-m','scripts.local_product',*args]

def execute(args):
    prerequisite()
    if args.command=='install':
        media=Path(__file__).resolve().parent;value=manifest(media)
        root=Path(args.destination).absolute()
        need(root.resolve()==root and root.parent.is_dir(),'UNALIASED_DESTINATION_REQUIRED')
        need(len(os.fsencode(root/'data'/('pw-'+'0'*32)/'socket/.s.PGSQL.5432'))<=107,'SHORTER_USER_DESTINATION_REQUIRED')
        root.mkdir(mode=0o700)  # Exclusive; never adopt an existing directory.
        with locked(root):
            (root/'data').mkdir(mode=0o700);(root/'media').mkdir(mode=0o700)
            record=dict(schema='parkweave-linux-user-installation/1',source_commit=value['source_commit'],software='INSTALLING',setup='NOT_STARTED',state_dir=None)
            save(root,'installation.json',record)
            for name in ('candidate.json',*value['files']):
                target=root/'media'/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
                with target.open('xb') as output:output.write(read(media/name,128*1024*1024))
            need(manifest(root/'media')==value,'COPIED_PAYLOAD_MISMATCH')
            entry=read(root/'media/install.py')
            need(sha256(entry).hexdigest()==value['files']['install.py']['sha256'],'COPIED_ENTRY_MISMATCH')
            with (root/'ParkWeave.py').open('xb') as output:output.write(entry)
            launcher='#!/bin/sh\nexec '+shlex.quote(sys.executable)+' -I -B '+shlex.quote(str(root/'ParkWeave.py'))+' "$@"\n'
            with (root/'ParkWeave').open('x') as output:output.write(launcher)
            (root/'ParkWeave').chmod(0o700)
            runtime(root,value);record['software']='INSTALLED';save(root,'installation.json',record)
        print(json.dumps(dict(installed='LINUX_SYNTHETIC_CANDIDATE',directory=str(root),next_command=str(root/'ParkWeave')+' setup',usable_product=False)));return
    root=Path(__file__).absolute().parent
    with locked(root) as lock:
        record=state(root);value=manifest(root/'media')
        need(record['source_commit']==value['source_commit'],'ORIGINAL_SOURCE_REQUIRED')
        if args.command=='status':
            print(json.dumps(dict(scope='LINUX_SYNTHETIC_ONLY',software=record['software'],setup=record['setup'],source_commit=record['source_commit'],usable_product=False)));return
        if args.command=='restore':
            need(record['software']=='UNINSTALLED','CONFIRMED_UNINSTALL_REQUIRED')
            with stopped(root,record):
                record['software']='INSTALLING';save(root,'installation.json',record)
                runtime(root,value);record['software']='INSTALLED';save(root,'installation.json',record)
            print(json.dumps(dict(software='INSTALLED',data_preserved=True,next_command='start' if record['setup']=='COMPLETE' else 'setup')));return
        need(record['software']=='INSTALLED','INSTALLED_RUNTIME_REQUIRED')
        if args.command=='uninstall':
            with stopped(root,record):
                need(inventory(root/'application')==json.loads(read(root/'application-inventory.json')),'APPLICATION_CHANGED_KEEP_ALL_FILES')
                need(shutil.rmtree.avoids_symlink_attacks,'SAFE_DIRECTORY_REMOVAL_REQUIRED')
                record['software']='UNINSTALLING';save(root,'installation.json',record)
                shutil.rmtree(root/'application')
                record['software']='UNINSTALLED';save(root,'installation.json',record)
            print(json.dumps(dict(software='UNINSTALLED',data_preserved=True,offline_restore_supported=True)));return
        if args.command=='setup':
            need(record['setup']=='NOT_STARTED' and not any((root/'data').iterdir()),'SETUP_ALREADY_ATTEMPTED_NO_RETRY')
            record['setup']='PENDING';save(root,'installation.json',record)
            child=subprocess.Popen(cli(root,'install','--parent',str(root/'data')),
                cwd=root/'application/source',env=environment(),stdout=subprocess.PIPE)
            try:output,_=child.communicate()  # Human password input has no kill timer.
            except KeyboardInterrupt:
                # Terminal Ctrl+C also reaches the original CLI, which owns PG
                # cleanup. Wait boundedly; never SIGKILL it or infer completion.
                try:child.wait(timeout=30)
                except subprocess.TimeoutExpired:raise Refused('SETUP_CHILD_EXIT_UNKNOWN_NO_RETRY') from None
                raise
            need(child.returncode==0 and len(output)<=65536,'SETUP_NOT_CONFIRMED_KEEP_STATE')
            receipts=[json.loads(line) for line in output.decode().splitlines() if line.startswith('{')]
            receipt=next((row for row in receipts if row.get('installed')=='LOCAL_SYNTHETIC_MATERIAL_ONLY'),None)
            need(receipt is not None,'SETUP_NOT_CONFIRMED_KEEP_STATE')
            record['state_dir']=receipt['state_dir'];selection(root,record)
            record['setup']='COMPLETE';save(root,'installation.json',record)
            print(json.dumps(dict(setup='COMPLETE_SYNTHETIC',next_command='start',passwords_stored=False)));return
        need(args.command=='start' and record['setup']=='COMPLETE','EXPLICIT_COMPLETE_SETUP_REQUIRED')
        path=selection(root,record)
        os.chdir(root/'application/source')
        # Retain the original manager lock through exec, until the original
        # backend finishes its own PG/worker cleanup. No new process authority.
        os.set_inheritable(lock,True)
        os.execve(cli(root)[0],cli(root,'start','--state-dir',str(path),'--port',str(args.port)),environment())

def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('install','setup','start','status','uninstall','restore'))
    parser.add_argument('--destination',help='install only; new user directory, never an existing root')
    parser.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    if bool(args.destination)!=(args.command=='install'):parser.error('only install requires --destination')
    try:execute(args)
    except KeyboardInterrupt:return 130
    except Exception as error:
        code=error.args[0] if type(error) is Refused else type(error).__name__
        print('PARKWEAVE_LINUX_REFUSED: '+code+'; files and data retained',file=sys.stderr);return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
