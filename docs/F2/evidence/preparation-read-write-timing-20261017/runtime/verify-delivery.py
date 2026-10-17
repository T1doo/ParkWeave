from pathlib import Path
import subprocess,json,hashlib
root=Path('/workspace/ParkWeave');r=root/'.runtime/preparation-read-write-timing';source='25c64f1dd4bb2ca9a79be88650d3a1b410c4bef5'
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
assert git('branch','--show-current')=='dev/f2-demo-original-page-intake-20261017'
assert not git('status','--porcelain')
assert subprocess.run(['git','merge-base','--is-ancestor',source,'HEAD'],cwd=root).returncode==0
scope=['src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md']
for name in scope:assert git('rev-parse','HEAD:'+name)==git('rev-parse',source+':'+name),name
old={line.split('\t',1)[1]:line.split('\t',1)[0] for line in (r/'inherited-evidence-blobs.txt').read_text().splitlines()}
new={line.split('\t',1)[1]:line.split('\t',1)[0] for line in git('ls-tree','-r','HEAD','--','docs/F2/evidence').splitlines()}
changed=[p for p,h in old.items() if new.get(p)!=h];assert not changed
manifest=json.loads((r/'final-inputs.json').read_text());drift=[p for p,h in manifest.items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h];assert not drift
remote=git('ls-remote','--heads','origin');(r/'pre-push-remote.txt').write_text(remote+'\n');target='refs/heads/'+git('branch','--show-current');sha=next(line.split()[0] for line in remote.splitlines() if line.split()[1]==target)
assert sha=='175918d440bb06d3749cb5fc1de5b79c0a4e9b0f'
result=dict(delivery_sha=git('rev-parse','HEAD'),source_sha=source,source_tree=git('rev-parse','HEAD:src'),source_test_script_contract_git_trees_unchanged=True,input_count=len(manifest),input_drift=drift,inherited_evidence_count=len(old),inherited_evidence_changed=changed,pre_push_remote_sha=sha,local_ahead_behind=git('rev-list','--left-right','--count','HEAD...'+sha),clean=True)
(r/'delivery-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
