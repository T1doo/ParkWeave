from pathlib import Path
import hashlib,json,subprocess
root=Path('/workspace/ParkWeave');r=root/'.runtime/dispatch-accept-recovery-20261018'
def git(*a):return subprocess.check_output(['git',*a],cwd=root,text=True).strip()
a=json.loads((r/'accepted-tests.json').read_text());source=a['source_sha'];head=git('rev-parse','HEAD')
assert git('branch','--show-current')=='dev/f2-demo-original-page-intake-20261017'
assert subprocess.run(['git','merge-base','--is-ancestor',source,'HEAD'],cwd=root).returncode==0
paths=['src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md']
trees={p:git('rev-parse','HEAD:'+p) for p in paths}
assert all(trees[p]==git('rev-parse',source+':'+p) for p in paths)
inputs=json.loads((r/'final-focused-A-inputs.json').read_text())
current_paths=sorted(set(git('ls-files','src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md').splitlines()+git('ls-files','--others','--exclude-standard','src','tests','scripts').splitlines()))
assert sorted(inputs)==current_paths and len(inputs)==745
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==sha for p,sha in inputs.items())
old={}
for line in (r/'inherited-evidence-blobs.txt').read_text().splitlines():
    meta,name=line.split('\t',1);old[name]=meta.split()[2]
auth=json.loads((r/'identifier-correction-integration.json').read_text())
def blob(p):
    data=(root/p).read_bytes();return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
changed=[p for p,sha in old.items() if blob(p)!=sha]
assert len(old)==29851 and sorted(changed)==sorted(auth['authorized_identifier_correction_changed']) and len(changed)==20
result=dict(delivery_sha=head,tested_source_sha=source,tested_source_is_ancestor=True,tested_trees_unchanged=trees,verified_input_count=len(inputs),input_drift=[],inherited_evidence_count=len(old),inherited_unchanged=len(old)-len(changed),inherited_only_authorized_identifier_correction=changed,unknown_lock_preserved=(root/'.git/codex-index-refresh.lock').exists(),clean=not git('status','--porcelain'),scope='Final source/docs local delivery check; remote verified separately after push')
assert result['unknown_lock_preserved'] and result['clean']
(r/'delivery-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
