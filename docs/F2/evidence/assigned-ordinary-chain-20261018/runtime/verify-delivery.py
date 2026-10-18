from pathlib import Path
import subprocess,json,hashlib
root=Path('/workspace/ParkWeave');r=root/'.runtime/assigned-demo-chain-20261018';source='d0045f14699857f8cd4ba254505abe9fa0fc982e'
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
assert git('branch','--show-current')=='dev/f2-demo-original-page-intake-20261017'
assert not git('status','--porcelain')
assert subprocess.run(['git','merge-base','--is-ancestor',source,'HEAD'],cwd=root).returncode==0
for name in ['src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md']:
    assert git('rev-parse','HEAD:'+name)==git('rev-parse',source+':'+name),name
old={line.split('\t',1)[1]:line.split('\t',1)[0] for line in (root/'.runtime/assigned-demo-chain-20261018/inherited-evidence-blobs.txt').read_text().splitlines()}
current={line.split('\t',1)[1]:line.split('\t',1)[0] for line in git('ls-tree','-r','HEAD','--','docs/F2/evidence').splitlines()}
changed=[p for p,h in old.items() if current.get(p)!=h];assert len(old)==29674 and not changed
inputs=json.loads((r/'final-inputs.json').read_text());drift=[p for p,h in inputs.items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h];assert not drift
remote=git('ls-remote','--heads','origin');(r/'pre-push-remote.txt').write_text(remote+'\n');refs={ref:sha for sha,ref in [line.split() for line in remote.splitlines()]};branch=git('branch','--show-current');sha=refs['refs/heads/'+branch]
assert sha=='0567ba3abea00e5cb2eb64ce3b46d04750dffb91'
assert refs['refs/heads/main']=='31e7acb7e53bb1ab6465b9daae59de28757f7583'
result=dict(delivery_sha=git('rev-parse','HEAD'),source_sha=source,source_tree=git('rev-parse','HEAD:src'),source_test_script_contract_trees_unchanged=True,input_count=len(inputs),input_drift=drift,inherited_evidence_count=len(old),inherited_evidence_changed=changed,pre_push_remote_sha=sha,local_ahead_behind=git('rev-list','--left-right','--count','HEAD...'+sha),clean=True,unknown_lock_preserved=(root/'.git/codex-index-refresh.lock').exists())
(r/'delivery-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
