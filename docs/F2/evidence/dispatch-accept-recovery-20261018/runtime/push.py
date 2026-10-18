from pathlib import Path
import json,os,subprocess,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/dispatch-accept-recovery-20261018';branch='dev/f2-demo-original-page-intake-20261017'
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
assert git('branch','--show-current')==branch and not git('status','--porcelain')
source=json.load(open(r/'accepted-tests.json'))['source_sha']
for name in ['src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md']:assert git('rev-parse','HEAD:'+name)==git('rev-parse',source+':'+name),name
assert git('remote','get-url','origin')=='https://github.com/T1doo/ParkWeave.git'
env={k:v for k,v in os.environ.items() if not k.startswith('GIT_TRACE') and k not in ('GIT_CURL_VERBOSE','GH_DEBUG')};env['GIT_TERMINAL_PROMPT']='0'
prefix=['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential']
pre=subprocess.run(prefix+['ls-remote','--heads','origin'],cwd=root,env=env,capture_output=True,text=True,timeout=45)
(r/'pre-push-remote.txt').write_text(pre.stdout);(r/'pre-push-remote.stderr').write_text(pre.stderr);assert pre.returncode==0
refs={ref:sha for sha,ref in (line.split() for line in pre.stdout.splitlines())};assert refs['refs/heads/'+branch]=='bfb16026a5bcfcdca101a69f357157d5f1c4a490'
assert subprocess.run(['git','merge-base','--is-ancestor',refs['refs/heads/'+branch],'HEAD'],cwd=root).returncode==0
argv=prefix+['push','origin','HEAD:refs/heads/'+branch];started=time.time();sha=git('rev-parse','HEAD')
try:
 p=subprocess.run(argv,cwd=root,env=env,capture_output=True,text=True,timeout=120);out,err=p.stdout,p.stderr;status='PROCESS_COMPLETED';code=p.returncode
except subprocess.TimeoutExpired as exc:
 out=exc.stdout or b'';err=exc.stderr or b'';out=out.decode(errors='replace') if isinstance(out,bytes) else out;err=err.decode(errors='replace') if isinstance(err,bytes) else err;status='UNCERTAIN_TIMEOUT';code=None
(r/'push.stdout').write_text(out);(r/'push.stderr').write_text(err)
result=dict(delivery_sha=sha,source_sha=source,argv=argv,branch=branch,status=status,exit_code=code,elapsed_seconds=time.time()-started,credential_path='existing per-command gh auth git-credential; no persisted config or new credentials',force=False,main_targeted=False)
(r/'push-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if code is not None:raise SystemExit(code)
raise SystemExit(2)
