from pathlib import Path
import subprocess,json
root=Path('/workspace/ParkWeave');r=root/'.runtime/assigned-demo-chain-20261018'
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
def refs(text):return {ref:sha for sha,ref in [line.split() for line in text.splitlines()]}
before=refs((r/'pre-push-remote.txt').read_text());text=git('ls-remote','--heads','origin');(r/'post-push-remote.txt').write_text(text+'\n');after=refs(text)
target='refs/heads/'+git('branch','--show-current');changed=[k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)]
assert changed==[target] and after[target]==git('rev-parse','HEAD')
assert after['refs/heads/main']==before['refs/heads/main']=='31e7acb7e53bb1ab6465b9daae59de28757f7583'
assert not git('status','--porcelain')
result=dict(delivery_sha=git('rev-parse','HEAD'),remote_sha=after[target],ahead_behind=git('rev-list','--left-right','--count','HEAD...'+after[target]),head_count_before=len(before),head_count_after=len(after),changed_refs=changed,other_refs_unchanged=True,main_unchanged=True,clean=True,unknown_lock_preserved=(root/'.git/codex-index-refresh.lock').exists())
(r/'remote-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
