"""One stdlib-only hosted read-only predicate diagnostic; never imports product.

No old logs, dependency/font fetch, credentials, browser, API or PG invocation.
Public output is fixed booleans, git source and allowlisted file metadata only.
"""
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
PARENT='3f0ca98b6334d6e7a2c2d7c05e8d6dc51f430bdd'
BRANCH='dev/pgdata-inheritance-source-20261026'
PATHS={'.github/workflows/template-hosted-predicate-once.yml','scripts/template_hosted_predicate_once.py','tests/test_template_hosted_predicate_once.py'}
EXPECTED={'GITHUB_REPOSITORY':'T1doo/ParkWeave','GITHUB_REF':'refs/heads/'+BRANCH,'GITHUB_EVENT_NAME':'push','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_NUMBER':'1','RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux','PW_PUBLIC':'true'}
LIMIT=16384


def git(args,deadline):
    left=deadline-time.monotonic()
    if left<=0:raise TimeoutError()
    return subprocess.check_output(['git',*args],cwd=ROOT,timeout=min(3,left),stderr=subprocess.DEVNULL)


def metadata(path):
    try:st=path.lstat()
    except FileNotFoundError:return {'exists':False}
    return {'exists':True,'regular':stat.S_ISREG(st.st_mode),'directory':stat.S_ISDIR(st.st_mode),
            'symlink':stat.S_ISLNK(st.st_mode),'canonical':path.resolve()==path,
            'trusted_owner':st.st_uid in (0,os.geteuid()),'current_user_owner':st.st_uid==os.geteuid(),
            'not_group_or_other_writable':not bool(st.st_mode&0o022),'executable':bool(st.st_mode&0o111),
            'mode':oct(stat.S_IMODE(st.st_mode)),'size':st.st_size}


def inspect(environment,report,deadline):
    checks=report['checks']
    for key,value in EXPECTED.items():checks['host_'+key]=environment.get(key)==value
    checks['no_inherited_business_configuration']=not any(k.startswith('PARKWEAVE_') for k in environment)
    if not all(checks.values()):return
    head=git(['rev-parse','HEAD'],deadline).decode().strip()
    checks['source_sha_matches_event']=bool(re.fullmatch('[0-9a-f]{40}',head)) and head==environment.get('GITHUB_SHA')
    checks['source_branch_matches']=git(['branch','--show-current'],deadline).decode().strip()==BRANCH
    checks['source_worktree_clean']=not git(['status','--porcelain'],deadline)
    checks['source_direct_parent']=git(['rev-parse','HEAD^'],deadline).decode().strip()==PARENT
    checks['source_changed_only_diagnostic']=set(git(['diff','--name-only',PARENT,head],deadline).decode().splitlines())==PATHS
    report['head_sha']=head if re.fullmatch('[0-9a-f]{40}',head) else None
    if not all(checks.values()):return
    for name in ('template_browser_approval.json','template_http_approval.json'):
        raw=(ROOT/'scripts'/name).read_bytes()
        if len(raw)>2048:raise ValueError()
        value=json.loads(raw)
        checks['closed_'+name]=value=={'version':1,'enabled':False,'reviewed_source':None,'invocation':None,'expires_utc':None}
    chrome=metadata(Path('/opt/google/chrome/chrome'));report['chrome']=chrome
    checks['chrome_exists']=chrome['exists']
    for key in ('regular','trusted_owner','not_group_or_other_writable','executable'):
        checks['chrome_'+key]=chrome.get(key,False)
    checks['chrome_not_symlink']=chrome.get('symlink') is False
    fontconfig=metadata(Path('/usr/bin/fc-match'));report['fontconfig']=fontconfig
    checks['fontconfig_is_file']=Path('/usr/bin/fc-match').is_file()
    scratch=metadata(ROOT.parent/'scratch');report['scratch']=scratch
    checks['scratch_fresh_before_prepare']=not scratch['exists']
    cache=metadata(ROOT/'.runtime/approved-noto-run48');report['font_cache_before_staging']=cache
    checks['font_cache_fresh_before_staging']=not cache['exists']
    # Only booleans, no environment value (including public image vars) emitted.
    report['image_comparison']={'os_variable_present':bool(environment.get('ImageOS')),
        'version_variable_present':bool(environment.get('ImageVersion')),
        'same_known_os_as_run49':environment.get('ImageOS')=='ubuntu24',
        'same_known_image_as_run49':environment.get('ImageVersion')=='20261012.334.1'}
    if time.monotonic()>=deadline:raise TimeoutError()


def publish(path,report,*,initial=False):
    raw=(json.dumps(report,sort_keys=True)+'\n').encode()
    if len(raw)>LIMIT:raise ValueError()
    target=path if initial else path.with_name('diagnostic.next.json')
    with target.open('xb') as stream:stream.write(raw)
    if not initial:os.replace(target,path)


def main():
    started=time.monotonic();os.umask(0o077)
    report={'status':'NOT_COMPLETED','scope':'NEW_RUNNER_PREDICATES_NOT_RUN49_ROOT_CAUSE',
            'checks':{},'downloads':0,'business_GET':0,'business_POST':0,'Chrome_PG_API_started':False}
    path=None
    try:
        parent=Path(os.environ['RUNNER_TEMP']);st=parent.lstat()
        if parent.resolve()!=parent or not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid():raise ValueError()
        directory=parent/'template-hosted-predicate';directory.mkdir(mode=0o700,exist_ok=False)
        path=directory/'diagnostic.json';publish(path,report,initial=True)
        inspect(os.environ,report,started+19)
        report['status']='CONDITIONS_SATISFIED' if report['checks'] and all(report['checks'].values()) else 'CONDITIONS_REJECTED'
    except BaseException as error:
        report.update(status='DIAGNOSTIC_ERROR',error_type=type(error).__name__)
    report['elapsed_seconds']=round(time.monotonic()-started,3)
    try:
        if path is not None:publish(path,report)
        for key,value in report['checks'].items():print('CHECK '+key+': '+('PASS' if value else 'FAIL'),flush=True)
        print('DIAGNOSTIC '+report['status'],flush=True)
    except BaseException:return 1
    return 0 if report['status']=='CONDITIONS_SATISFIED' else 1


if __name__=='__main__':raise SystemExit(main())
