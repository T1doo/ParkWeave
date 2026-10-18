from pathlib import Path
import hashlib,json,subprocess
root=Path('/workspace/ParkWeave');r=root/'.runtime/resource-approval-host-read-20261018'
def git(*a):return subprocess.check_output(['git',*a],cwd=root,text=True).strip()
source=json.loads((r/'accepted-tests.json').read_text())['source_sha'];head=git('rev-parse','HEAD');assert not git('status','--porcelain')
assert git('branch','--show-current')=='dev/f2-resource-approval-host-read-20261018'
assert subprocess.run(['git','merge-base','--is-ancestor',source,'HEAD'],cwd=root).returncode==0
paths=['src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md'];trees={p:git('rev-parse','HEAD:'+p) for p in paths};assert all(trees[p]==git('rev-parse',source+':'+p) for p in paths)
inputs=json.loads((r/'final-inputs.json').read_text());assert len(inputs)==749 and all(hashlib.sha256((root/p).read_bytes()).hexdigest()==sha for p,sha in inputs.items())
current={}
for line in git('ls-tree','-r','HEAD','--','docs/F2/evidence').splitlines():
 meta,name=line.split('\t',1);current[name]=meta.split()[2]
old={}
for line in (r/'inherited-evidence-blobs.txt').read_text().splitlines():
 meta,name=line.split('\t',1);old[name]=meta.split()[2]
assert len(old)==30651 and all(current[p]==sha for p,sha in old.items())
assert (root/'.git/codex-index-refresh.lock').exists()
result=dict(delivery_sha=head,tested_source_sha=source,tested_source_is_ancestor=True,tested_trees_unchanged=trees,input_count=749,input_drift=[],inherited_blobs=30651,inherited_changed=0,clean=True,unknown_lock_preserved=True,scope='Actual local post-commit verification; remote query is separate')
(r/'delivery-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
