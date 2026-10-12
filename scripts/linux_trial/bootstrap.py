"""Approved fresh GitHub VM only. No trial secrets reach its public stdout/stderr."""
import hashlib
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

BRANCH = 'refs/heads/dev/f2-restricted-linux-trial-20261012'
CASES = ('PROTECTED_RUNTIME','FRESH_CLUSTER','REAL_IDENTITIES','HOST_CHANNELS',
         'API_PRIVATE_BOUNDARY','EXPLICIT_BIND','ACTUAL_ROLE_ACL','EVENT_ROLLBACK',
         'REAL_PARENT_LOCK','REQUEST_APPROVE','ACTIVATION_ROLLBACK','LOST_RESPONSE_GET',
         'COLD_REBIND','LEASE_EXPIRY','CHANGED_SOURCE_REVOKE','NO_RENEWAL','OWNED_STOP')
PHASES = ('PREFLIGHT','PROTECTED_RUNTIME','IDENTITIES','PG_START','PG_SETUP','HOST_START',
          'ACCEPTANCE','CLEANUP','COMPLETE')
ERRORS = ('NONE','CHECK_FAILED','OS_REFUSED','TIMEOUT','ADAPTER_DENIED','INTERNAL_ERROR')


def public_summary(value):
    """Closed projection, never arbitrary error text, paths, credentials or repr."""
    if not isinstance(value,dict) or set(value)!={'source_sha','phase','error','cases','cleanup'}:
        raise ValueError('SUMMARY_CONTRACT')
    if (not isinstance(value['source_sha'],str) or not re.fullmatch('[0-9a-f]{40}',value['source_sha']) or
            value['phase'] not in PHASES or value['error'] not in ERRORS or
            type(value['cleanup']) is not bool or set(value['cases'])!=set(CASES) or
            any(v not in ('PASS','FAIL','NOT_RUN') for v in value['cases'].values())):
        raise ValueError('SUMMARY_CONTRACT')
    return dict(suite='ACTUAL_ISOLATED_RESTRICTED_LINUX_TRIAL',**value,
                paid_services=0,artifact_uploads=0,cache_uploads=0,production_deployment=False)


def approved_context(env,uid,sha):
    return (uid==0 and re.fullmatch('[a-f0-9]{40}',sha or '') is not None and
        all(env.get(k)==v for k,v in dict(TRIAL_REPOSITORY='T1doo/ParkWeave',TRIAL_REF=BRANCH,
            TRIAL_EVENT='push',TRIAL_ATTEMPT='1',TRIAL_NUMBER='1',
            RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux').items()))


def protected_copy(source,target):
    """New copies only; dereference trusted input links, reject links in output."""
    if target.exists():raise ValueError('NEW_OUTPUT_REQUIRED')
    if source.is_dir():shutil.copytree(source,target,symlinks=False,ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo'))
    else:target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    for p in [target,*target.rglob('*')] if target.is_dir() else [target]:
        s=p.lstat()
        if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise ValueError('REGULAR_COPY_REQUIRED')
        os.chown(p,0,0);os.chmod(p,0o755 if stat.S_ISDIR(s.st_mode) or p==target and not target.is_dir() else 0o644)


def bootstrap(sha):
    value=dict(source_sha=sha,phase='PREFLIGHT',error='NONE',cases={c:'NOT_RUN' for c in CASES},cleanup=True)
    private=None
    try:
        if not approved_context(os.environ,os.geteuid(),sha):raise PermissionError('APPROVED_NEW_VM_CONTEXT_REQUIRED')
        checkout=Path.cwd()
        actual=subprocess.check_output(['/usr/bin/git','rev-parse','HEAD'],cwd=checkout,text=True).strip()
        if actual!=sha:raise ValueError('EXACT_CHECKOUT_REQUIRED')
        # No child receives inherited job/environment secrets. All tool output is private.
        root=Path('/tmp/parkweave-trial-'+uuid4().hex);root.mkdir(mode=0o711)
        private=root/'private';private.mkdir(mode=0o700)
        value['phase']='PROTECTED_RUNTIME'
        source=root/'source';source.mkdir(mode=0o755)
        names=subprocess.check_output(['/usr/bin/git','ls-tree','-r','--name-only',sha,'src/parkweave','scripts/linux_trial'],cwd=checkout,text=True).splitlines()
        for name in names:
            target=source/(name.removeprefix('src/') if name.startswith('src/') else name)
            target.parent.mkdir(parents=True,exist_ok=True)
            raw=subprocess.check_output(['/usr/bin/git','show',sha+':'+name],cwd=checkout)
            target.write_bytes(raw);os.chmod(target,0o644)
        for path in [source,*source.rglob('*')]:
            if path.is_dir():os.chmod(path,0o755)
        env=root/'environment';(env/'bin').mkdir(parents=True,mode=0o755);(env/'lib').mkdir(mode=0o755)
        original=Path('/usr/bin/python3.12')
        s=original.lstat()
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=0 or s.st_mode&0o022:raise PermissionError('OFFICIAL_REGULAR_INTERPRETER_REQUIRED')
        protected_copy(original,env/'bin/python3.12')
        protected_copy(Path('/usr/lib/python3.12'),env/'lib/python3.12')
        site=env/'lib/python3.12/site-packages';site.mkdir(mode=0o755)
        packages=['fastapi==0.142.2','uvicorn==0.54.0','psycopg[binary]==3.3.6',
                  'pydantic==2.13.5','httpx==0.28.1','pytest==9.1.1','setuptools==80.9.0']
        with (private/'dependency-tool.log').open('wb') as log:
            subprocess.run(['/usr/bin/python3.12','-m','pip','install','--no-cache-dir','--only-binary=:all:',
                '--target',str(site),*packages],stdout=log,stderr=log,env={'LANG':'C.UTF-8','PATH':'/usr/bin:/bin'},timeout=240,check=True)
        for p in env.rglob('*'):
            s=p.lstat()
            if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):raise PermissionError('PROTECTED_COPY_HAS_LINK')
            os.chown(p,0,0);os.chmod(p,0o755 if stat.S_ISDIR(s.st_mode) else 0o644)
        os.chmod(env/'bin/python3.12',0o755)
        imports=[str(source),str(env/'lib/python3.12'),str(env/'lib/python3.12/lib-dynload'),str(site)]
        context=dict(root=str(root),source_sha=sha,source=str(source),environment=str(env),imports=imports,
                     approval='USER_CONFIRMED_ONE_FREE_GITHUB_VM_2026-10-12T12:49:49Z')
        (private/'context.json').write_text(json.dumps(context));os.chmod(private/'context.json',0o600)
        entry='import sys;sys.path[:]='+repr(imports)+';from scripts.linux_trial.controller import main;raise SystemExit(main())'
        # Popen controller is root; SDK directly owns writer child under this root process.
        process=subprocess.Popen([str(env/'bin/python3.12'),'-I','-S','-B','-c',entry,str(private/'context.json')],
            env={'LANG':'C.UTF-8'},cwd='/',stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        value['cleanup']=False
        try:stdout,stderr=process.communicate(timeout=1000)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:stdout,stderr=process.communicate(timeout=20)
            except subprocess.TimeoutExpired:process.kill();stdout,stderr=process.communicate(timeout=5)
            (private/'controller-stderr.log').write_bytes(stderr)
            raise
        (private/'controller-stderr.log').write_bytes(stderr)
        candidate=json.loads(stdout)
        if set(candidate)!=set(value) or candidate['source_sha']!=sha:raise ValueError('EXACT_PUBLIC_SUMMARY_REQUIRED')
        value={k:candidate[k] for k in ('source_sha','phase','error','cases','cleanup')}
        output=public_summary(value)
        print(json.dumps(output,sort_keys=True))
        return 0 if process.returncode==0 and all(v=='PASS' for v in value['cases'].values()) else 1
    except BaseException as exc:
        if private is not None:
            (private/'bootstrap-failure.log').write_text(traceback.format_exc())
            os.chmod(private/'bootstrap-failure.log',0o600)
        value['error']='OS_REFUSED' if isinstance(exc,PermissionError) else 'TIMEOUT' if isinstance(exc,subprocess.TimeoutExpired) else 'CHECK_FAILED' if isinstance(exc,(AssertionError,ValueError)) else 'INTERNAL_ERROR'
        value['cases']['PROTECTED_RUNTIME']='FAIL'
        if not re.fullmatch('[a-f0-9]{40}',sha or ''):value['source_sha']='0'*40
        print(json.dumps(public_summary(value),sort_keys=True));return 1


if __name__=='__main__':
    raise SystemExit(bootstrap(sys.argv[1] if len(sys.argv)==2 else ''))
