"""Exact source-bound candidate build on one hosted Linux runner; never Windows.

Null approval refuses before Git/temp/network/build actions. Official locked
public assets only; no credential/alternate URL/retry/cache adoption. The final
ZIP must equal the independently reviewed hash before workflow artifact upload.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from scripts.windows_ci.native_business_window import _record,_read,need,RECORD,WORKFLOW


def source_window():
    window,raw=_record()
    expected=dict(GITHUB_ACTIONS='true',RUNNER_ENVIRONMENT='github-hosted',RUNNER_OS='Linux',
        GITHUB_REPOSITORY=window.repository,GITHUB_REF=window.ref,GITHUB_JOB='candidate-build',
        GITHUB_EVENT_NAME='push',GITHUB_RUN_ATTEMPT='1',GITHUB_RUN_NUMBER=str(window.run_number),
        NATIVE_PUBLIC='true',GITHUB_WORKFLOW_REF=window.repository+'/'+WORKFLOW+'@'+window.ref)
    need(all(os.environ.get(k)==v for k,v in expected.items()) and os.name=='posix' and sys.platform=='linux'
        and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
        and re.fullmatch('[1-9][0-9]{0,19}',os.environ.get('GITHUB_RUN_ID',''))
        and (window.run_id is None or os.environ['GITHUB_RUN_ID']==window.run_id)
        and not any(k.upper().startswith('PG') for k in os.environ)
        and os.environ.get('GITHUB_SHA')==os.environ.get('GITHUB_WORKFLOW_SHA')
        and re.fullmatch('[a-f0-9]{40}',os.environ.get('GITHUB_SHA','')))
    deadline=min(time.monotonic()+330,time.monotonic()+window.expires_utc-time.time()-window.work_seconds-window.cleanup_seconds)
    need(deadline>time.monotonic())
    def git(*args):
        return subprocess.check_output(['git','--no-optional-locks',*args],cwd=ROOT,timeout=10)
    need(ROOT==Path(os.environ['GITHUB_WORKSPACE']).resolve(strict=True)
        and git('rev-parse','HEAD').decode().strip()==os.environ['GITHUB_SHA']
        and git('rev-parse','HEAD^').decode().strip()==window.reviewed_parent
        and not git('status','--porcelain=v1')
        and set(git('diff','--name-only','HEAD^','HEAD').decode().splitlines())<={RECORD,WORKFLOW}
        and git('show','HEAD:'+RECORD)==raw
        and sha256(_read(ROOT/WORKFLOW,65536)).hexdigest()==window.workflow_sha256)
    temp=Path(os.environ['RUNNER_TEMP']);need(temp.is_absolute() and not temp.is_symlink())
    return window,temp/('parkweave-candidate-build-'+os.environ['GITHUB_RUN_ID']),deadline


def download(row,destination,deadline):
    need(type(row) is dict and type(row['bytes']) is int and 0<row['bytes']<=512*1024*1024
        and re.fullmatch('[a-f0-9]{64}',row['sha256']))
    url=urllib.parse.urlsplit(row['url'])
    need(url.scheme=='https' and url.hostname in ('www.python.org','get.enterprisedb.com',
        'files.pythonhosted.org','ziglang.org','api.nuget.org') and not url.username and not url.password)
    need(time.monotonic()<deadline and not destination.exists())
    destination.parent.mkdir(parents=True,exist_ok=True)
    digest=sha256();total=0
    # Default urllib honors existing proxy/CA policy. Never retry or use a mirror.
    with urllib.request.urlopen(row['url'],timeout=min(15,deadline-time.monotonic())) as response:
        need(urllib.parse.urlsplit(response.geturl()).hostname==url.hostname and response.status==200)
        with destination.open('xb') as stream:
            while True:
                need(time.monotonic()<deadline)
                part=response.read(min(1024*1024,row['bytes']+1-total))
                if not part:break
                total+=len(part);need(total<=row['bytes']);stream.write(part);digest.update(part)
    need(total==row['bytes'] and digest.hexdigest()==row['sha256'])


def extract_compiler(archive,destination):
    with tarfile.open(archive,'r:xz') as stream:
        members=stream.getmembers();need(0<len(members)<=30000)
        names=set()
        for item in members:
            parts=Path(item.name).parts
            need(parts and parts[0]=='zig-x86_64-linux-0.15.2' and not Path(item.name).is_absolute()
                and '..' not in parts and item.name not in names and (item.isfile() or item.isdir()))
            names.add(item.name)
        stream.extractall(destination,members=members,filter='data')


def build(window,work,deadline):
    need(not work.exists());work.mkdir(mode=0o700)
    source=work/'source'
    subprocess.run(['git','worktree','add','--detach',str(source),window.reviewed_parent],cwd=ROOT,
        check=True,capture_output=True,timeout=10)
    # All executable builders and locks come from the reviewed parent, not an
    # input download or an approval-commit code change.
    runtime=json.loads((source/'scripts/windows_portable/runtime-assets.json').read_bytes())
    tools=json.loads((source/'scripts/windows_ci/native_candidate_tools.json').read_bytes())
    need(runtime['schema']=='parkweave-windows-runtime-assets/1'
        and tools['schema']=='parkweave-native-candidate-tools/1')
    assets=work/'assets'
    for row in runtime['assets']+tools['assets']:
        name=Path(row['file']);need(not name.is_absolute() and '..' not in name.parts)
        download(row,assets/name,deadline)
    compiler=work/'compiler';compiler.mkdir()
    extract_compiler(assets/'zig-x86_64-linux-0.15.2.tar.xz',compiler)
    code="import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module(sys.argv.pop(1),run_name='__main__')"
    def run(module,*args):
        need(time.monotonic()<deadline)
        command=[sys.executable,'-I','-B','-S','-c',code,str(source),module,*map(str,args)]
        result=subprocess.run(command,cwd=source,capture_output=True,timeout=max(.001,deadline-time.monotonic()))
        (work/(module.rsplit('.',1)[-1]+'-'+str(len(list(work.glob('*.log'))))+'.log')).write_bytes(result.stdout+result.stderr)
        need(result.returncode==0)
    base=('--source',window.reviewed_parent,'--assets',assets,'--lock',source/'scripts/windows_portable/runtime-assets.json')
    run('scripts.windows_portable.build',*base,'--output',work/'bootstrap.zip')
    bootstrap=work/'bootstrap';bootstrap.mkdir()
    with zipfile.ZipFile(work/'bootstrap.zip') as stream:
        for name in stream.namelist():
            need(not Path(name).is_absolute() and '..' not in Path(name).parts)
        stream.extractall(bootstrap)
    run('scripts.windows_desktop.build','--zig',compiler/'zig-x86_64-linux-0.15.2/zig',
        '--zig-archive',assets/'zig-x86_64-linux-0.15.2.tar.xz',
        '--sdk',assets/'microsoft.web.webview2.1.0.3537.50.nupkg',
        '--python-asset',assets/'python-3.12.10-embed-amd64.zip',
        '--bootstrap-root',bootstrap,'--output',work/'desktop')
    artifact=work/'artifact';artifact.mkdir()
    archive=artifact/'candidate.zip'
    run('scripts.windows_portable.build',*base,'--desktop-assets',work/'desktop','--output',archive)
    need(time.monotonic()<deadline and archive.stat().st_size==window.archive_bytes
        and sha256(archive.read_bytes()).hexdigest()==window.archive_sha256)
    with zipfile.ZipFile(archive) as stream:raw=stream.read('payload-manifest.json')
    need(sha256(raw).hexdigest()==window.manifest_sha256
        and json.loads(raw)['source_commit']==window.reviewed_parent)
    return artifact


def main():
    try:
        window,work,deadline=source_window()
        artifact=build(window,work,deadline)
        # Output is consumed only by the same-run pinned artifact action.
        with open(os.environ['GITHUB_OUTPUT'],'a') as stream:stream.write('artifact='+str(artifact)+'\n')
        print(json.dumps(dict(candidate='EXACT_APPROVED_BYTES',native_windows_executed=False)))
        return 0
    except BaseException as error:
        print(json.dumps(dict(candidate='NOT_BUILT_OR_UNKNOWN',error_type=type(error).__name__)))
        return 2


if __name__=='__main__':raise SystemExit(main())
