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
from contextlib import contextmanager
from uuid import uuid4

BRANCH = 'refs/heads/dev/f2-restricted-linux-trial-20261012'
CASES = ('PROTECTED_RUNTIME','FRESH_CLUSTER','REAL_IDENTITIES','HOST_CHANNELS',
         'API_PRIVATE_BOUNDARY','EXPLICIT_BIND','ACTUAL_ROLE_ACL','EVENT_ROLLBACK',
         'REAL_PARENT_LOCK','REQUEST_APPROVE','ACTIVATION_ROLLBACK','LOST_RESPONSE_GET',
         'COLD_REBIND','LEASE_EXPIRY','CHANGED_SOURCE_REVOKE','NO_RENEWAL','OWNED_STOP')
PHASES = ('PREFLIGHT','PROTECTED_RUNTIME','IDENTITIES','PG_START','PG_SETUP','HOST_START',
          'ACCEPTANCE','CLEANUP','COMPLETE')
ERRORS = ('NONE','CHECK_FAILED','OS_REFUSED','TIMEOUT','ADAPTER_DENIED','INTERNAL_ERROR')
SETUP_CHECKS = dict(HELPER_ENTRY='INPUT',HELPER_FRAME='TRANSPORT',SEALED_INPUT='INPUT',
    PG_OWNER='INPUT',DATABASE_NAME='INPUT',CLUSTER_PROOF='OWNERSHIP',DATABASE_CREATE='OWNERSHIP',
    DATABASE_RECEIPT='OWNERSHIP',MIGRATION='MIGRATION',SEED='SYNTHETIC',ACTORS='SYNTHETIC',
    RUN_CREATE='SYNTHETIC',RUN_FINISH='SYNTHETIC',PREPARATION_CREATE='SYNTHETIC',
    EVIDENCE_NEED_SUMMARY='SYNTHETIC',EVIDENCE_MATERIAL_OUTLINE='SYNTHETIC',REVIEW='SYNTHETIC',
    CONFIRM='SYNTHETIC',NATIVE_STORAGE='STORAGE',ACTIVATION_STORAGE='STORAGE',SOURCE_SNAPSHOT='POLICY',
    POLICY='POLICY',ROLE_CREATE='ACL',DATABASE_ACL='ACL',SCHEMA_ACL='ACL',APP_ACL='ACL',
    WRITER_ACL='ACL',SPEC='POLICY',CATALOG_COLLECT='CATALOG',CATALOG_COMPARE='CATALOG',RESULT='OUTPUT')
# 0 means no allowlisted HTTP observation. Never publish an arbitrary status.
SETUP_HTTP_CODES = (0,200,201,202,400,401,403,404,409,422,500,502,503)


def setup_diagnostic(value):
    if (type(value) is not dict or set(value)!={'substage','check_id','status_code'} or
            type(value['check_id']) is not str or value['check_id'] not in SETUP_CHECKS or
            type(value['substage']) is not str or value['substage']!=SETUP_CHECKS[value['check_id']] or
            type(value['status_code']) is not int or value['status_code'] not in SETUP_HTTP_CODES or
            value['status_code'] and value['check_id'] not in ('RUN_CREATE','PREPARATION_CREATE',
                'EVIDENCE_NEED_SUMMARY','EVIDENCE_MATERIAL_OUTLINE','REVIEW','CONFIRM')):
        raise ValueError('SETUP_DIAGNOSTIC_CONTRACT')
    return {k:value[k] for k in ('substage','check_id','status_code')}


class SetupObservation:
    """A fixed check ID is recorded before the operation; exceptions stay private."""
    def __init__(self):self.value=dict(substage='INPUT',check_id='HELPER_ENTRY',status_code=0)

    @contextmanager
    def check(self,check_id):
        self.value=setup_diagnostic(dict(substage=SETUP_CHECKS[check_id],check_id=check_id,status_code=0))
        yield

    def response(self,response,expected):
        status=response.status_code
        self.value['status_code']=status if type(status) is int and status in SETUP_HTTP_CODES else 0
        if type(status) is not int or status!=expected:raise AssertionError('SYNTHETIC_SETUP_STATUS')
        return response.json()


def setup_frame(raw,returncode):
    """Private success payload never enters the public projection; failure has none."""
    if type(raw) is not bytes or len(raw)>524288 or type(returncode) is not int:
        raise ValueError('SETUP_FRAME_CONTRACT')
    def unique(pairs):
        if len(pairs)!=len({k for k,v in pairs}):raise ValueError('SETUP_FRAME_CONTRACT')
        return dict(pairs)
    try:frame=json.loads(raw.decode('utf-8'),object_pairs_hook=unique)
    except (ValueError,TypeError):raise ValueError('SETUP_FRAME_CONTRACT') from None
    if type(frame) is not dict or frame.get('outcome') not in ('PASS','FAIL'):
        raise ValueError('SETUP_FRAME_CONTRACT')
    success=frame['outcome']=='PASS'
    if (set(frame)!=({'outcome','diagnostic','result'} if success else {'outcome','diagnostic'}) or
            returncode!=(0 if success else 1)):
        raise ValueError('SETUP_FRAME_CONTRACT')
    diagnostic=setup_diagnostic(frame['diagnostic'])
    if success and (diagnostic['check_id']!='RESULT' or type(frame['result']) is not dict):
        raise ValueError('SETUP_FRAME_CONTRACT')
    return frame['outcome'],diagnostic,frame.get('result')


def public_summary(value):
    """Closed projection, never arbitrary error text, paths, credentials or repr."""
    required={'source_sha','phase','error','cases','cleanup'}
    if type(value) is not dict or set(value) not in (required,required|{'setup_diagnostic'}):
        raise ValueError('SUMMARY_CONTRACT')
    if (not isinstance(value['source_sha'],str) or not re.fullmatch('[0-9a-f]{40}',value['source_sha']) or
            value['phase'] not in PHASES or value['error'] not in ERRORS or
            type(value['cleanup']) is not bool or type(value['cases']) is not dict or set(value['cases'])!=set(CASES) or
            any(v not in ('PASS','FAIL','NOT_RUN') for v in value['cases'].values())):
        raise ValueError('SUMMARY_CONTRACT')
    result=dict(value)
    if 'setup_diagnostic' in result and result['setup_diagnostic'] is not None:
        result['setup_diagnostic']=setup_diagnostic(result['setup_diagnostic'])
    return dict(suite='ACTUAL_ISOLATED_RESTRICTED_LINUX_TRIAL',**result,
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
    value=dict(source_sha=sha,phase='PREFLIGHT',error='NONE',cases={c:'NOT_RUN' for c in CASES},cleanup=True,setup_diagnostic=None)
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
        # Keep the safe fallback intact until every child field is validated.
        output=public_summary(candidate)
        value={k:candidate[k] for k in value}
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
