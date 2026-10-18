from pathlib import Path
import json,os,subprocess,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/dispatch-accept-recovery-20261018';branch='dev/f2-demo-original-page-intake-20261017'
env={k:v for k,v in os.environ.items() if not k.startswith('GIT_TRACE') and k not in ('GIT_CURL_VERBOSE','GH_DEBUG')};env['GIT_TERMINAL_PROMPT']='0'
p=subprocess.run(['git','-c','credential.helper=','-c','credential.helper=!gh auth git-credential','ls-remote','--heads','origin'],cwd=root,env=env,capture_output=True,text=True,timeout=45)
(r/'post-push-remote.txt').write_text(p.stdout);(r/'post-push-remote.stderr').write_text(p.stderr);assert p.returncode==0
old={ref:sha for sha,ref in (line.split() for line in (r/'pre-push-remote.txt').read_text().splitlines())};new={ref:sha for sha,ref in (line.split() for line in p.stdout.splitlines())};sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
changed=[dict(ref=ref,before=old.get(ref),after=new.get(ref)) for ref in sorted(old.keys()|new.keys()) if old.get(ref)!=new.get(ref)]
assert new['refs/heads/'+branch]==sha and [x['ref'] for x in changed]==['refs/heads/'+branch]
assert new['refs/heads/main']==old['refs/heads/main']=='31e7acb7e53bb1ab6465b9daae59de28757f7583'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
result=dict(delivery_sha=sha,source_sha=json.load(open(r/'accepted-tests.json'))['source_sha'],changed_refs=changed,head_count_before=len(old),head_count_after=len(new),main_unchanged=True,other_refs_unchanged=True,actual_local_remote_ahead_behind=subprocess.check_output(['git','rev-list','--left-right','--count','HEAD...'+new['refs/heads/'+branch]],cwd=root,text=True).strip(),clean=True,unknown_lock_preserved=(root/'.git/codex-index-refresh.lock').exists(),time=time.time())
(r/'remote-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
