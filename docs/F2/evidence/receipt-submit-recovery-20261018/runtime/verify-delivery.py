from pathlib import Path
import hashlib,json,subprocess,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/receipt-submit-recovery-20261018'
def git(*a):return subprocess.check_output(['git',*a],cwd=root,text=True).strip()
source=json.loads((r/'accepted-tests.json').read_text())['source_sha'];head=git('rev-parse','HEAD');assert not git('status','--porcelain')
assert git('branch','--show-current')=='dev/f2-receipt-submit-recovery-20261018'
assert subprocess.run(['git','merge-base','--is-ancestor',source,'HEAD'],cwd=root).returncode==0
paths=['src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md','docs/F2/ReceiptSubmitRecovery-20261018.md'];trees={p:git('rev-parse','HEAD:'+p) for p in paths};assert all(trees[p]==git('rev-parse',source+':'+p) for p in paths)
inputs=json.loads((r/'final-v2-inputs.json').read_text());assert len(inputs)==755 and all(hashlib.sha256((root/p).read_bytes()).hexdigest()==sha for p,sha in inputs.items())
def blobs(ref):
 value={}
 for line in subprocess.check_output(['git','ls-tree','-rz',ref,'--','docs/F2/evidence'],cwd=root).split(b'\0'):
  if not line:continue
  meta,name=line.split(b'\t',1);value[name.decode()]=meta.split()[2].decode()
 return value
current=blobs('HEAD');old=blobs('d5f69a8fe9f0d8860c0325d46a035a7dbbb7f49f');assert all(current[p]==sha for p,sha in old.items())
start=time.monotonic()
for p,sha in old.items():
 path=root/p;assert not path.is_symlink();raw=path.read_bytes();assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==sha,p
assert (root/'.git/codex-index-refresh.lock').exists()
result=dict(delivery_sha=head,tested_source_sha=source,tested_source_is_ancestor=True,tested_trees_unchanged=trees,input_count=755,input_drift=[],inherited_blobs=len(old),inherited_actual_bytes_verified=len(old),inherited_changed=0,inherited_hash_seconds=time.monotonic()-start,clean=True,unknown_lock_preserved=True,scope='Actual local post-commit verification; remote query is separate')
(r/'delivery-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
