from pathlib import Path
import hashlib,json,subprocess,time
R=Path.cwd();D=R/'.runtime/material-two-case-demo-20261018';S='4fa85aac3b8961b35846800597208096c3a2e934';start=time.monotonic()
def tree(ref):
 result={}
 for line in subprocess.check_output(['git','ls-tree','-rz',ref,'--','docs/F2/evidence']).split(b'\0'):
  if line:
   meta,p=line.split(b'\t',1);result[p.decode()]=meta.split()[2].decode()
 return result
before=tree(S);now=tree('HEAD');assert len(before)==33554 and all(now.get(p)==oid for p,oid in before.items())
for p,oid in before.items():
 f=R/p;assert not f.is_symlink();b=f.read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==oid,p
result=dict(baseline_sha=S,inherited_blobs=len(before),actual_git_blob_bytes_verified=len(before),changed=0,unknown_lock_preserved=(R/'.git/codex-index-refresh.lock').exists(),elapsed_seconds=time.monotonic()-start)
(D/'inherited-evidence-proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
