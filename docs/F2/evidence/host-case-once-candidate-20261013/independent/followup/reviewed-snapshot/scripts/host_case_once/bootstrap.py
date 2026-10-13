"""Pending by default; one new approved VM, no effects before the exact Git gate."""
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import traceback
from uuid import uuid4

BRANCH='refs/heads/dev/f2-host-case-security-once-20261013'
APPROVAL_FILE='scripts/host_case_once/approval.json'
APPROVAL_REF='USER_CONFIRMED_HOST_CASE_SECURITY_ONCE_20261013'
CASES=('GATE','PROTECTED_RUNTIME','REAL_IDENTITIES','FRESH_CLUSTER','SETUP','BUSINESS_ACL',
       'HOST_CHANNELS','API_PRIVATE_BOUNDARY','ACTUAL_ROLE_ACL','EXPLICIT_BIND',
       'REQUEST_APPROVE','NATIVE_ACTIVATION','BUSINESS_BIND','CASE_CANCEL',
       'ORIGINAL_KEY_RECOVERY','HISTORY_RETAINED','LATE_WRITE_REFUSED',
       'OWNED_STOP','DATABASE_REMOVED','FILES_REMOVED','IDENTITIES_REMOVED')
STATES=('PASS','FAIL','UNKNOWN','NOT_RUN')
PHASES=('GATE','PROTECTED_RUNTIME','IDENTITIES','PG_START','PG_SETUP','HOST_START','ACCEPTANCE','CLEANUP','COMPLETE')
ERRORS=('NONE','REFUSED','FAILURE','TIMEOUT','UNKNOWN')
CLAIM='/tmp/parkweave-host-case-security-once-20261013.claim'


def initial(sha):
    return dict(source_sha=sha if type(sha) is str and re.fullmatch('[a-f0-9]{40}',sha) else '0'*40,
        phase='GATE',error='NONE',cases={k:'NOT_RUN' for k in CASES},cleanup=False,
        failure_logs='NOT_NEEDED',diagnostics=[])


def public_summary(value):
    if (type(value) is not dict or set(value)!=set(initial('')) or
            type(value['source_sha']) is not str or not re.fullmatch('[a-f0-9]{40}',value['source_sha']) or
            value['phase'] not in PHASES or value['error'] not in ERRORS or type(value['cleanup']) is not bool or
            type(value['cases']) is not dict or set(value['cases'])!=set(CASES) or
            any(type(v) is not str or v not in STATES for v in value['cases'].values()) or
            value['failure_logs'] not in ('NOT_NEEDED','SAVED','UNAVAILABLE') or
            type(value['diagnostics']) is not list or len(value['diagnostics'])>32):
        raise ValueError('CLOSED_HOST_CASE_RESULT_REQUIRED')
    for d in value['diagnostics']:
        if (type(d) is not dict or set(d)!={'case','line','trace_sha256'} or d['case'] not in CASES or
                type(d['line']) is not int or not 0<=d['line']<=10000 or
                type(d['trace_sha256']) is not str or not re.fullmatch('[a-f0-9]{64}',d['trace_sha256'])):
            raise ValueError('CLOSED_HOST_CASE_DIAGNOSTIC_REQUIRED')
    return json.loads(json.dumps(value))


def git(checkout,*args):
    # Read Git as the existing checkout owner; never change safe.directory/config.
    s=checkout.stat()
    if s.st_uid<=0:raise PermissionError('NONROOT_CHECKOUT_OWNER_REQUIRED')
    return subprocess.check_output(['/usr/bin/git',*args],cwd=checkout,env={'LANG':'C.UTF-8'},
        user=s.st_uid,group=s.st_gid,extra_groups=[],stderr=subprocess.PIPE,timeout=5).decode().strip()


def gate(checkout,sha,env):
    path=checkout/APPROVAL_FILE
    if not stat.S_ISREG(path.lstat().st_mode):raise PermissionError('REGULAR_APPROVAL_REQUIRED')
    def unique(pairs):
        if len(pairs)!=len({k for k,_ in pairs}):raise ValueError('DUPLICATE_APPROVAL_KEY')
        return dict(pairs)
    a=json.loads(path.read_text(),object_pairs_hook=unique)
    if (os.geteuid()!=0 or type(sha) is not str or not re.fullmatch('[a-f0-9]{40}',sha) or
            type(a) is not dict or set(a)!={'approved','source_sha','approval_ref'} or
            a['approved'] is not True or a['approval_ref']!=APPROVAL_REF or
            type(a['source_sha']) is not str or not re.fullmatch('[a-f0-9]{40}',a['source_sha']) or
            any(env.get(k)!=v for k,v in dict(HOST_CASE_REPOSITORY='T1doo/ParkWeave',HOST_CASE_REF=BRANCH,
                HOST_CASE_EVENT='push',HOST_CASE_NUMBER='1',HOST_CASE_ATTEMPT='1',HOST_CASE_PUBLIC='true',
                RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux').items())):
        raise PermissionError('NEW_EXPLICIT_SECURITY_APPROVAL_REQUIRED')
    if (git(checkout,'rev-parse','HEAD')!=sha or
            git(checkout,'rev-list','--parents','-n','1','HEAD').split()!=[sha,a['source_sha']] or
            git(checkout,'diff','--name-only',a['source_sha'],sha)!=APPROVAL_FILE or
            git(checkout,'status','--porcelain') or
            json.loads(git(checkout,'show',a['source_sha']+':'+APPROVAL_FILE))!=dict(approved=False,source_sha=None,approval_ref=None)):
        raise PermissionError('REVIEWED_PARENT_APPROVAL_ONLY_REQUIRED')
    return a['source_sha']


def prepare(checkout,source_sha,root):
    source=root/'source';source.mkdir(mode=0o755)
    names=git(checkout,'ls-tree','-r','--name-only',source_sha,'src/parkweave','scripts/linux_trial','scripts/host_case_once').splitlines()
    if not names or len(names)>512:raise ValueError('BOUNDED_REVIEWED_BUNDLE_REQUIRED')
    for name in names:
        if any(x in ('','..','.') for x in name.split('/')):raise ValueError('REVIEWED_BUNDLE_PATH_REQUIRED')
        target=source/(name.removeprefix('src/') if name.startswith('src/') else name)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(subprocess.check_output(['/usr/bin/git','show',source_sha+':'+name],cwd=checkout,
            env={'LANG':'C.UTF-8'},user=checkout.stat().st_uid,group=checkout.stat().st_gid,extra_groups=[],timeout=5))
        os.chmod(target,0o644)
    for p in [source,*source.rglob('*')]:
        if p.is_dir():os.chmod(p,0o755)
    environment=root/'environment';(environment/'bin').mkdir(parents=True);(environment/'lib').mkdir()
    original=Path('/usr/bin/python3.12');s=original.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:raise PermissionError('OFFICIAL_INTERPRETER_REQUIRED')
    protected_copy(original,environment/'bin/python3.12')
    protected_copy(Path('/usr/lib/python3.12'),environment/'lib/python3.12')
    site=environment/'lib/python3.12/site-packages';site.mkdir()
    netrc=root/'private/empty.netrc';fd=os.open(netrc,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    with (root/'private/dependencies.log').open('wb') as log:
        subprocess.run(['/usr/bin/python3.12','-I','-m','pip','--isolated','install','--no-input',
            '--keyring-provider=disabled','--disable-pip-version-check','--no-cache-dir','--no-compile','--only-binary=:all:',
            '--target',str(site),'fastapi==0.142.2','uvicorn==0.54.0','psycopg[binary]==3.3.6',
            'pydantic==2.13.5','httpx==0.28.1'],env={'LANG':'C.UTF-8','PATH':'/usr/bin:/bin',
            'NETRC':str(netrc),'PIP_CONFIG_FILE':os.devnull},stdout=log,stderr=log,timeout=180,check=True)
    for p in [environment,*environment.rglob('*')]:
        s=p.lstat()
        if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise PermissionError('PROTECTED_BUNDLE_NO_LINKS_REQUIRED')
        os.chown(p,0,0);os.chmod(p,0o755 if stat.S_ISDIR(s.st_mode) else 0o644)
    os.chmod(environment/'bin/python3.12',0o755)
    return dict(root=str(root),source_sha=source_sha,source=str(source),environment=str(environment),
        imports=[str(source),str(environment/'lib/python3.12'),str(environment/'lib/python3.12/lib-dynload'),str(site)],
        approval_ref=APPROVAL_REF)


def protected_copy(source,target):
    if target.exists() or target.is_symlink():raise PermissionError('new protected copy required')
    # Check the source before copying: dereferencing a link would lose its evidence.
    for p in [source,*source.parents]:
        s=p.lstat()
        if s.st_uid!=0 or s.st_mode&0o022 or not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
            raise PermissionError('official protected source required')
    def copy(p,q):
        s=p.lstat()
        if s.st_uid!=0 or s.st_mode&0o022 or not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
            raise PermissionError('official protected source required')
        if stat.S_ISDIR(s.st_mode):
            q.mkdir()
            for child in p.iterdir():
                if child.name=='__pycache__' or child.suffix in ('.pyc','.pyo'):continue
                copy(child,q/child.name)
        else:shutil.copyfile(p,q)
    copy(source,target)
    for p in [target,*target.rglob('*')] if target.is_dir() else [target]:
        s=p.lstat()
        if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise PermissionError('regular protected copy required')
        os.chown(p,0,0);os.chmod(p,0o755 if stat.S_ISDIR(s.st_mode) or p==target and not target.is_dir() else 0o644)


def bootstrap(sha):
    result=initial(sha);root=None
    try:
        checkout=Path.cwd();source_sha=gate(checkout,sha,os.environ);result['source_sha']=source_sha
        fd=os.open(CLAIM,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:os.write(fd,(source_sha+'\n').encode())
        finally:os.close(fd)
        result['cases']['GATE']='PASS'
        root=Path('/tmp/parkweave-trial-'+uuid4().hex);root.mkdir(mode=0o711)
        (root/'private').mkdir(mode=0o700);result['phase']='PROTECTED_RUNTIME'
        context=prepare(checkout,source_sha,root)
        sys.path[:]=context['imports']
        from scripts.linux_trial.controller import sealed
        from parkweave.native_run_access_writer import _pid_started
        context.update(bootstrap_pid=os.getpid(),bootstrap_started=_pid_started(os.getpid()))
        fd=sealed(context)
        entry='import sys;sys.path[:]='+repr(context['imports'])+';from scripts.host_case_once.controller import main;raise SystemExit(main())'
        with (root/'private/controller-stderr.log').open('wb') as err:
            try:
                child=subprocess.Popen([context['environment']+'/bin/python3.12','-I','-S','-B','-c',entry,str(fd)],
                    env={'LANG':'C.UTF-8'},cwd='/',pass_fds=(fd,),close_fds=True,stdout=subprocess.PIPE,stderr=err)
            finally:os.close(fd)
            try:stdout,_=child.communicate(timeout=1000)
            except subprocess.TimeoutExpired:
                child.terminate()
                try:child.communicate(timeout=90)
                except subprocess.TimeoutExpired:child.kill();child.communicate(timeout=5)
                raise
        candidate=public_summary(json.loads(stdout))
        if candidate['source_sha']!=source_sha:raise ValueError('EXACT_CONTROLLER_RESULT_REQUIRED')
        result=candidate
        success=result['cleanup'] and result['error']=='NONE' and all(v=='PASS' for v in result['cases'].values())
        if child.returncode!=(0 if success else 1):raise ValueError('CONTROLLER_EXIT_REQUIRED')
    except BaseException:
        result['error']='FAILURE';result['cases']['GATE' if root is None else 'PROTECTED_RUNTIME']='FAIL'
        try:
            if root is None:raise OSError()
            (root/'private/bootstrap-failure.log').write_text(traceback.format_exc());result['failure_logs']='SAVED'
        except BaseException:result['failure_logs']='UNAVAILABLE'
    print(json.dumps(public_summary(result),sort_keys=True))
    return 0 if all(v=='PASS' for v in result['cases'].values()) and result['cleanup'] else 1


if __name__=='__main__':raise SystemExit(bootstrap(sys.argv[1] if len(sys.argv)==2 else ''))
