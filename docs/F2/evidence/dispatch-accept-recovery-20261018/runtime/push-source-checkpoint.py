from pathlib import Path
import json,os,subprocess,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/dispatch-accept-recovery-20261018';sha='bfb16026a5bcfcdca101a69f357157d5f1c4a490';branch='dev/f2-demo-original-page-intake-20261017'
def git(*a):return subprocess.check_output(['git',*a],cwd=root,text=True).strip()
assert git('rev-parse','HEAD')==sha and git('branch','--show-current')==branch and not git('status','--porcelain')
assert json.load(open(r/'repair-probes-result.json'))['exit_code']==0
assert git('remote','get-url','origin')=='https://github.com/T1doo/ParkWeave.git'
env={k:v for k,v in os.environ.items() if not k.startswith('GIT_TRACE') and k not in ('GIT_CURL_VERBOSE','GH_DEBUG')};env['GIT_TERMINAL_PROMPT']='0';prefix=['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential']
p=subprocess.run(prefix+['ls-remote','--heads','origin'],cwd=root,env=env,capture_output=True,text=True,timeout=45);(r/'checkpoint-before-remote.txt').write_text(p.stdout);(r/'checkpoint-before-remote.stderr').write_text(p.stderr);assert p.returncode==0
before={ref:s for s,ref in (line.split() for line in p.stdout.splitlines())};assert before['refs/heads/'+branch]=='25d2b524cbc0fa80fda9eed4b86b64b1cf647984'
argv=prefix+['push','origin','HEAD:refs/heads/'+branch];started=time.time();p=subprocess.run(argv,cwd=root,env=env,capture_output=True,text=True,timeout=120);(r/'checkpoint-push.stdout').write_text(p.stdout);(r/'checkpoint-push.stderr').write_text(p.stderr)
(r/'checkpoint-push-result.json').write_text(json.dumps(dict(sha=sha,exit_code=p.returncode,argv=argv,elapsed_seconds=time.time()-started,kind='SOURCE_REVIEW_CHECKPOINT',full_regression='in progress; one observed failure; NOT accepted',force=False,main_targeted=False),indent=2)+'\n');assert p.returncode==0
p=subprocess.run(prefix+['ls-remote','--heads','origin'],cwd=root,env=env,capture_output=True,text=True,timeout=45);(r/'checkpoint-after-remote.txt').write_text(p.stdout);(r/'checkpoint-after-remote.stderr').write_text(p.stderr);assert p.returncode==0
after={ref:s for s,ref in (line.split() for line in p.stdout.splitlines())};changed=[ref for ref in sorted(before.keys()|after.keys()) if before.get(ref)!=after.get(ref)];assert after['refs/heads/'+branch]==sha and changed==['refs/heads/'+branch];assert after['refs/heads/main']==before['refs/heads/main']=='31e7acb7e53bb1ab6465b9daae59de28757f7583'
result=dict(sha=sha,target_branch=branch,head_count=len(after),changed_refs=changed,main_unchanged=True,other_refs_unchanged=True,ahead_behind=git('rev-list','--left-right','--count','HEAD...'+sha),full_regression_accepted=False,kind='SOURCE_REVIEW_CHECKPOINT_ONLY');(r/'checkpoint-remote-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
