from pathlib import Path
import json,os,subprocess,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/resource-approval-host-read-20261018';branch='dev/f2-resource-approval-host-read-20261018'
def git(*a):return subprocess.check_output(['git',*a],cwd=root,text=True).strip()
a=json.loads((r/'accepted-tests.json').read_text());source=a['source_sha'];head=git('rev-parse','HEAD')
assert git('branch','--show-current')==branch and not git('status','--porcelain')
assert subprocess.run(['git','merge-base','--is-ancestor',source,'HEAD'],cwd=root).returncode==0
for name in ('src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md'):assert git('rev-parse','HEAD:'+name)==git('rev-parse',source+':'+name),name
assert git('remote','get-url','origin')=='https://github.com/T1doo/ParkWeave.git'
env={k:v for k,v in os.environ.items() if not k.startswith('GIT_TRACE') and k not in ('GIT_CURL_VERBOSE','GH_DEBUG')};env['GIT_TERMINAL_PROMPT']='0';prefix=['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential']
p=subprocess.run(prefix+['ls-remote','--heads','origin'],cwd=root,env=env,capture_output=True,text=True,timeout=45);(r/'pre-push-remote.txt').write_text(p.stdout);(r/'pre-push-remote.stderr').write_text(p.stderr);assert p.returncode==0
refs={ref:sha for sha,ref in (line.split() for line in p.stdout.splitlines())};assert 'refs/heads/'+branch not in refs
initial={ref:sha for sha,ref in (line.split() for line in (r/'initial-remote.txt').read_text().splitlines())};assert refs==initial
assert refs['refs/heads/main']=='31e7acb7e53bb1ab6465b9daae59de28757f7583' and refs['refs/heads/dev/f2-demo-original-page-intake-20261017']=='2e3cc3023c42fcbacae1e8bef5a34e8061644d82'
argv=prefix+['push','origin','HEAD:refs/heads/'+branch];start=time.time()
try:
 p=subprocess.run(argv,cwd=root,env=env,capture_output=True,text=True,timeout=120);out,err,status,code=p.stdout,p.stderr,'PROCESS_COMPLETED',p.returncode
except subprocess.TimeoutExpired as exc:
 out,err=exc.stdout or b'',exc.stderr or b'';out=out.decode(errors='replace') if isinstance(out,bytes) else out;err=err.decode(errors='replace') if isinstance(err,bytes) else err;status,code='UNCERTAIN_TIMEOUT',None
(r/'push.stdout').write_text(out);(r/'push.stderr').write_text(err)
result=dict(delivery_sha=head,tested_source_sha=source,branch=branch,status=status,exit_code=code,elapsed_seconds=time.time()-start,argv=argv,force=False,main_targeted=False,new_credentials=False,credential_path='existing per-command gh auth git-credential; no persisted config')
(r/'push-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(code if code is not None else 2)
