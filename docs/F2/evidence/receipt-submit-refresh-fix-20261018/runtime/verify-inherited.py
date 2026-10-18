from pathlib import Path
import hashlib,json,subprocess,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/receipt-submit-refresh-fix-20261018';base='b3f64488cbcce8b29a8152509e3b2dac59d6aa84'
def blobs(ref):
 values={}
 for line in subprocess.check_output(['git','ls-tree','-rz',ref,'--','docs/F2/evidence'],cwd=root).split(b'\0'):
  if line:
   meta,name=line.split(b'\t',1);values[name.decode()]=meta.split()[2].decode()
 return values
before=blobs(base);now=blobs('HEAD');assert all(now.get(p)==sha for p,sha in before.items());started=time.monotonic()
for p,sha in before.items():
 f=root/p;assert not f.is_symlink();data=f.read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==sha,p
result=dict(baseline_sha=base,inherited_git_blobs=len(before),actual_byte_hashes_verified=len(before),inherited_changes=0,seconds=time.monotonic()-started,unknown_lock_preserved=(root/'.git/codex-index-refresh.lock').exists())
(r/'inherited-evidence-proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
