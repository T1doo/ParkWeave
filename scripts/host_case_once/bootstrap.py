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
import types
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

# Closed labels: no exception text/type/hash, path, argv or stderr is projected.
CHECKS={}
def _checks(source,stage,cases,names):
    for name in names.split():CHECKS[name]=(source,stage,tuple(cases))
_checks('BOOTSTRAP','GATE',('GATE',),'B_GATE B_CLAIM')
_checks('BOOTSTRAP','ROOT',('PROTECTED_RUNTIME',),'B_ROOT B_PRIVATE_DIR')
_checks('BOOTSTRAP','SOURCE',('PROTECTED_RUNTIME',),'B_SOURCE_DIR B_SOURCE_ENUM B_SOURCE_COPY B_SOURCE_PROTECT')
_checks('BOOTSTRAP','RUNTIME',('PROTECTED_RUNTIME',),'B_ENV_DIR B_INTERPRETER_CHECK B_INTERPRETER_COPY B_STDLIB_COPY B_SITE_DIR')
_checks('BOOTSTRAP','DEPENDENCIES',('PROTECTED_RUNTIME',),'B_EMPTY_NETRC B_DEP_IMPORT B_HOST_TARGET B_WHEEL_DIR B_LOCK B_DOWNLOAD B_WHEEL_VERIFY B_INSTALL B_ENV_PROTECT B_CONTEXT')
_checks('BOOTSTRAP','CONTROLLER',('PROTECTED_RUNTIME',),'B_CONTEXT_IMPORT B_CONTEXT_PID B_SEAL B_STDERR_OPEN B_LAUNCH B_WAIT B_TIMEOUT_TERM B_TIMEOUT_KILL B_OUTPUT_JSON B_OUTPUT_SCHEMA B_SOURCE_MATCH B_EXIT')
_checks('BOOTSTRAP','PRIVATE_LOG',('GATE','PROTECTED_RUNTIME'),'B_PRIVATE_LOG')
_checks('CONTROLLER','GATE',('GATE',),'C_CONTEXT C_PARENT C_ROOT')
_checks('CONTROLLER','IDENTITIES',('REAL_IDENTITIES',),'C_IDENTITIES')
_checks('CONTROLLER','PG_SETUP',('FRESH_CLUSTER','SETUP','BUSINESS_ACL'),'C_PG')
_checks('CONTROLLER','HOST',('PROTECTED_RUNTIME','HOST_CHANNELS','API_PRIVATE_BOUNDARY','ACTUAL_ROLE_ACL','EXPLICIT_BIND'),'C_HOST')
_checks('CONTROLLER','BUSINESS',('REQUEST_APPROVE','NATIVE_ACTIVATION','BUSINESS_BIND','CASE_CANCEL','ORIGINAL_KEY_RECOVERY','HISTORY_RETAINED','LATE_WRITE_REFUSED'),'C_ACCEPTANCE')
_checks('CONTROLLER','CLEANUP',('OWNED_STOP',),'C_CLOSE C_FALLBACK_STOP C_WRITER_STOP C_SETUP_CLOSE C_PG_STOP C_CHILDREN C_CLEANUP')
_checks('CONTROLLER','CLEANUP',('DATABASE_REMOVED',),'C_DROP')
_checks('CONTROLLER','CLEANUP',('IDENTITIES_REMOVED',),'C_IDENTITY_CHECK C_SECRET_RECLAIM C_USER_DELETE C_GROUP_DELETE')
_checks('CONTROLLER','CLEANUP',('FILES_REMOVED',),'C_FILES_REMOVE')
_checks('CONTROLLER','PRIVATE_LOG',CASES,'C_PRIVATE_LOG')
_REVIEWED_CODES={}


def register_source(source,codes):
    if source not in ('BOOTSTRAP','CONTROLLER'):raise ValueError('CLOSED_SOURCE_REQUIRED')
    def add(code):
        _REVIEWED_CODES[id(code)]=(code,source,frozenset(line for _,_,line in code.co_lines() if line is not None))
        for child in code.co_consts:
            if isinstance(child,types.CodeType):add(child)
    for code in codes:add(code)


def reviewed_source(code):
    entry=_REVIEWED_CODES.get(id(code))
    return entry[1] if entry is not None and entry[0] is code else None


def reviewed_line(code,line):
    entry=_REVIEWED_CODES.get(id(code))
    return entry is not None and entry[0] is code and type(line) is int and 0<line<=10000 and line in entry[2]


class Diagnostic:
    def __init__(self,items):self.items=items;self.active=None;self.line=0
    def checkpoint(self,check_id,case=None):
        source,stage,cases=CHECKS[check_id]
        case=cases[0] if case is None else case
        if case not in cases:raise ValueError('CLOSED_CHECK_CASE_REQUIRED')
        self.active=dict(case=case,substage=stage,check_id=check_id,source=source,line=0)
        frame=sys._getframe(1)
        self.line=frame.f_lineno if reviewed_source(frame.f_code)==source and reviewed_line(frame.f_code,frame.f_lineno) else 0
    def capture(self,case=None):
        if self.active is None:raise ValueError('CHECKPOINT_REQUIRED')
        value=dict(self.active);source=value['source']
        if case is not None:
            if case not in CHECKS[value['check_id']][2]:raise ValueError('CLOSED_CHECK_CASE_REQUIRED')
            value['case']=case
        line=self.line;tb=sys.exc_info()[2]
        while tb is not None:
            if reviewed_source(tb.tb_frame.f_code)==source and reviewed_line(tb.tb_frame.f_code,tb.tb_lineno):line=tb.tb_lineno
            tb=tb.tb_next
        value['line']=line
        if len(self.items)<32:self.items.append(value)
        return value


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
        if (type(d) is not dict or set(d)!={'case','substage','check_id','source','line'} or
                type(d['check_id']) is not str or d['check_id'] not in CHECKS or
                type(d['case']) is not str or d['case'] not in CHECKS[d['check_id']][2] or
                (d['source'],d['substage'])!=CHECKS[d['check_id']][:2] or
                type(d['line']) is not int or not 0<=d['line']<=10000):
            raise ValueError('CLOSED_HOST_CASE_DIAGNOSTIC_REQUIRED')
    return json.loads(json.dumps(value))


def git(checkout,*args):
    # Read Git as the existing checkout owner; never change safe.directory/config.
    s=checkout.stat()
    if s.st_uid<=0:raise PermissionError('NONROOT_CHECKOUT_OWNER_REQUIRED')
    return subprocess.check_output(['/usr/bin/git',*args],cwd=checkout,env={'LANG':'C.UTF-8'},
        user=s.st_uid,group=s.st_gid,extra_groups=[],stderr=subprocess.PIPE,timeout=5).decode().strip()


def gate(checkout,sha,env,*,approval_file=APPROVAL_FILE,branch=BRANCH,approval_ref=APPROVAL_REF):
    path=checkout/approval_file
    if not stat.S_ISREG(path.lstat().st_mode):raise PermissionError('REGULAR_APPROVAL_REQUIRED')
    def unique(pairs):
        if len(pairs)!=len({k for k,_ in pairs}):raise ValueError('DUPLICATE_APPROVAL_KEY')
        return dict(pairs)
    a=json.loads(path.read_text(),object_pairs_hook=unique)
    if (os.geteuid()!=0 or type(sha) is not str or not re.fullmatch('[a-f0-9]{40}',sha) or
            type(a) is not dict or set(a)!={'approved','source_sha','approval_ref'} or
            a['approved'] is not True or a['approval_ref']!=approval_ref or
            type(a['source_sha']) is not str or not re.fullmatch('[a-f0-9]{40}',a['source_sha']) or
            any(env.get(k)!=v for k,v in dict(HOST_CASE_REPOSITORY='T1doo/ParkWeave',HOST_CASE_REF=branch,
                HOST_CASE_EVENT='push',HOST_CASE_NUMBER='1',HOST_CASE_ATTEMPT='1',HOST_CASE_PUBLIC='true',
                RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux').items())):
        raise PermissionError('NEW_EXPLICIT_SECURITY_APPROVAL_REQUIRED')
    if (git(checkout,'rev-parse','HEAD')!=sha or
            git(checkout,'rev-list','--parents','-n','1','HEAD').split()!=[sha,a['source_sha']] or
            git(checkout,'diff','--name-only',a['source_sha'],sha)!=approval_file or
            git(checkout,'status','--porcelain') or
            json.loads(git(checkout,'show',a['source_sha']+':'+approval_file))!=dict(approved=False,source_sha=None,approval_ref=None)):
        raise PermissionError('REVIEWED_PARENT_APPROVAL_ONLY_REQUIRED')
    return a['source_sha']


def prepare(checkout,source_sha,root,diag=None):
    diag=Diagnostic([]) if diag is None else diag
    diag.checkpoint('B_SOURCE_DIR')
    source=root/'source';source.mkdir(mode=0o755)
    diag.checkpoint('B_SOURCE_ENUM')
    names=git(checkout,'ls-tree','-r','--name-only',source_sha,'src/parkweave','scripts/linux_trial','scripts/host_case_once').splitlines()
    if not names or len(names)>512:raise ValueError('BOUNDED_REVIEWED_BUNDLE_REQUIRED')
    diag.checkpoint('B_SOURCE_COPY')
    for name in names:
        if any(x in ('','..','.') for x in name.split('/')):raise ValueError('REVIEWED_BUNDLE_PATH_REQUIRED')
        target=source/(name.removeprefix('src/') if name.startswith('src/') else name)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(subprocess.check_output(['/usr/bin/git','show',source_sha+':'+name],cwd=checkout,
            env={'LANG':'C.UTF-8'},user=checkout.stat().st_uid,group=checkout.stat().st_gid,extra_groups=[],stderr=subprocess.PIPE,timeout=5))
        os.chmod(target,0o644)
    diag.checkpoint('B_SOURCE_PROTECT')
    for p in [source,*source.rglob('*')]:
        if p.is_dir():os.chmod(p,0o755)
    diag.checkpoint('B_ENV_DIR')
    environment=root/'environment';(environment/'bin').mkdir(parents=True);(environment/'lib').mkdir()
    diag.checkpoint('B_INTERPRETER_CHECK')
    original=Path('/usr/bin/python3.12');s=original.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:raise PermissionError('OFFICIAL_INTERPRETER_REQUIRED')
    diag.checkpoint('B_INTERPRETER_COPY')
    protected_copy(original,environment/'bin/python3.12')
    diag.checkpoint('B_STDLIB_COPY')
    protected_copy(Path('/usr/lib/python3.12'),environment/'lib/python3.12',stdlib=True)
    diag.checkpoint('B_SITE_DIR')
    site=environment/'lib/python3.12/site-packages';site.mkdir()
    diag.checkpoint('B_EMPTY_NETRC')
    netrc=root/'private/empty.netrc';fd=os.open(netrc,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    # The reviewed source bundle, not checkout/environment discovery, owns the lock.
    diag.checkpoint('B_DEP_IMPORT')
    sys.path.insert(0,str(source))
    from scripts.host_case_once.dependencies import supported_host,pip_commands,verify
    diag.checkpoint('B_HOST_TARGET')
    supported_host()
    diag.checkpoint('B_WHEEL_DIR')
    locks=source/'scripts/host_case_once';wheels=root/'private/wheels';wheels.mkdir()
    diag.checkpoint('B_LOCK')
    download,install=pip_commands(locks,wheels,site)
    with (root/'private/dependencies.log').open('wb') as log:
        pip_env={'LANG':'C.UTF-8','PATH':'/usr/bin:/bin','NETRC':str(netrc),'PIP_CONFIG_FILE':os.devnull}
        diag.checkpoint('B_DOWNLOAD')
        subprocess.run(download,env=pip_env,stdout=log,stderr=log,timeout=90,check=True)
        diag.checkpoint('B_WHEEL_VERIFY')
        verify(locks,wheels) # Offline exact set/bytes/hash/metadata; reject before install.
        diag.checkpoint('B_INSTALL')
        subprocess.run(install,env=pip_env,stdout=log,stderr=log,timeout=90,check=True)
    diag.checkpoint('B_ENV_PROTECT')
    for p in [environment,*environment.rglob('*')]:
        s=p.lstat()
        if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise PermissionError('PROTECTED_BUNDLE_NO_LINKS_REQUIRED')
        os.chown(p,0,0);os.chmod(p,0o755 if stat.S_ISDIR(s.st_mode) else 0o644)
    os.chmod(environment/'bin/python3.12',0o755)
    diag.checkpoint('B_CONTEXT')
    return dict(root=str(root),source_sha=source_sha,source=str(source),environment=str(environment),
        imports=[str(source),str(environment/'lib/python3.12'),str(environment/'lib/python3.12/lib-dynload'),str(site)],
        approval_ref=APPROVAL_REF)


def protected_copy(source,target,*,stdlib=False):
    if stdlib and (str(source)!='/usr/lib/python3.12' or not sys.flags.isolated or not sys.flags.no_site):
        raise PermissionError('fixed no-site stdlib copy required')
    if target.exists() or target.is_symlink():raise PermissionError('new protected copy required')
    # Check the source before copying: dereferencing a link would lose its evidence.
    for p in [source,*source.parents]:
        s=p.lstat()
        if s.st_uid!=0 or s.st_mode&0o022 or not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
            raise PermissionError('official protected source required')
    def regular_copy(p,q):
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        out=None
        try:
            s=os.fstat(fd)
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:
                raise PermissionError('official regular source required')
            out=os.open(q,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
            while True:
                raw=os.read(fd,65536)
                if not raw:break
                offset=0
                while offset<len(raw):
                    written=os.write(out,raw[offset:])
                    if written<=0:raise OSError('protected copy write failed')
                    offset+=written
        finally:
            if out is not None:os.close(out)
            os.close(fd)
    def copy(p,q):
        s=p.lstat()
        if stdlib and stat.S_ISLNK(s.st_mode):
            if s.st_uid!=0:raise PermissionError('official protected link required')
            link=os.readlink(p)
            if str(p)=='/usr/lib/python3.12/sitecustomize.py' and link=='/etc/python3.12/sitecustomize.py':
                return # -I -S: never read/copy an external site configuration hook.
            if str(p)=='/usr/lib/python3.12/_sysconfigdata__linux_x86_64-linux-gnu.py' and link=='_sysconfigdata__x86_64-linux-gnu.py':
                regular_copy(p.parent/'_sysconfigdata__x86_64-linux-gnu.py',q)
                return # One fixed root-internal regular file; never follow a link chain.
            raise PermissionError('unlisted stdlib link refused')
        if s.st_uid!=0 or s.st_mode&0o022 or not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
            raise PermissionError('official protected source required')
        if stat.S_ISDIR(s.st_mode):
            q.mkdir()
            for child in p.iterdir():
                if child.name=='__pycache__' or child.suffix in ('.pyc','.pyo'):continue
                copy(child,q/child.name)
        else:regular_copy(p,q)
    copy(source,target)
    for p in [target,*target.rglob('*')] if target.is_dir() else [target]:
        s=p.lstat()
        if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise PermissionError('regular protected copy required')
        os.chown(p,0,0);os.chmod(p,0o755 if stat.S_ISDIR(s.st_mode) or p==target and not target.is_dir() else 0o644)


def bootstrap(sha):
    result=initial(sha);root=None;diag=Diagnostic(result['diagnostics'])
    try:
        diag.checkpoint('B_GATE')
        checkout=Path.cwd();source_sha=gate(checkout,sha,os.environ);result['source_sha']=source_sha
        diag.checkpoint('B_CLAIM')
        fd=os.open(CLAIM,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        try:os.write(fd,(source_sha+'\n').encode())
        finally:os.close(fd)
        result['cases']['GATE']='PASS'
        diag.checkpoint('B_ROOT')
        root=Path('/tmp/parkweave-trial-'+uuid4().hex);root.mkdir(mode=0o711)
        diag.checkpoint('B_PRIVATE_DIR')
        (root/'private').mkdir(mode=0o700);result['phase']='PROTECTED_RUNTIME'
        context=prepare(checkout,source_sha,root,diag)
        diag.checkpoint('B_CONTEXT_IMPORT')
        sys.path[:]=context['imports']
        from scripts.linux_trial.controller import sealed
        from parkweave.native_run_access_writer import _pid_started
        diag.checkpoint('B_CONTEXT_PID')
        context.update(bootstrap_pid=os.getpid(),bootstrap_started=_pid_started(os.getpid()))
        diag.checkpoint('B_SEAL')
        fd=sealed(context)
        entry='import sys;sys.path[:]='+repr(context['imports'])+';from scripts.host_case_once.controller import main;raise SystemExit(main())'
        diag.checkpoint('B_STDERR_OPEN')
        with (root/'private/controller-stderr.log').open('wb') as err:
            try:
                diag.checkpoint('B_LAUNCH')
                child=subprocess.Popen([context['environment']+'/bin/python3.12','-I','-S','-B','-c',entry,str(fd)],
                    env={'LANG':'C.UTF-8'},cwd='/',pass_fds=(fd,),close_fds=True,stdout=subprocess.PIPE,stderr=err)
            finally:os.close(fd)
            diag.checkpoint('B_WAIT')
            try:stdout,_=child.communicate(timeout=1000)
            except subprocess.TimeoutExpired:
                diag.checkpoint('B_TIMEOUT_TERM')
                child.terminate()
                try:child.communicate(timeout=90)
                except subprocess.TimeoutExpired:
                    diag.checkpoint('B_TIMEOUT_KILL')
                    child.kill();child.communicate(timeout=5)
                raise
        diag.checkpoint('B_OUTPUT_JSON');decoded=json.loads(stdout)
        diag.checkpoint('B_OUTPUT_SCHEMA');candidate=public_summary(decoded)
        diag.checkpoint('B_SOURCE_MATCH')
        if candidate['source_sha']!=source_sha:raise ValueError('EXACT_CONTROLLER_RESULT_REQUIRED')
        result=candidate;diag.items=result['diagnostics']
        success=result['cleanup'] and result['error']=='NONE' and all(v=='PASS' for v in result['cases'].values())
        diag.checkpoint('B_EXIT')
        if child.returncode!=(0 if success else 1):raise ValueError('CONTROLLER_EXIT_REQUIRED')
    except BaseException:
        failed=diag.capture();result['error']='FAILURE';result['cases'][failed['case']]='FAIL'
        result['phase']='GATE' if failed['case']=='GATE' else 'PROTECTED_RUNTIME'
        try:
            diag.checkpoint('B_PRIVATE_LOG',case=failed['case'])
            if root is None:raise OSError()
            (root/'private/bootstrap-failure.log').write_text(traceback.format_exc());result['failure_logs']='SAVED'
        except BaseException:
            diag.capture();result['failure_logs']='UNAVAILABLE'
    print(json.dumps(public_summary(result),sort_keys=True))
    return 0 if all(v=='PASS' for v in result['cases'].values()) and result['cleanup'] else 1


register_source('BOOTSTRAP',[v.__code__ for v in tuple(globals().values()) if isinstance(v,types.FunctionType) and v.__module__==__name__])

if __name__=='__main__':raise SystemExit(bootstrap(sys.argv[1] if len(sys.argv)==2 else ''))
