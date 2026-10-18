from pathlib import Path
import hashlib,json,subprocess,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/original-collaboration-dom-20261018';base='e3be7e4de10fce1ff4fc988ffb878ec12694c660'
def blobs(ref):
    values={}
    for line in subprocess.check_output(['git','ls-tree','-rz',ref,'--','docs/F2/evidence'],cwd=root).split(b'\0'):
        if line:
            meta,name=line.split(b'\t',1);values[name.decode()]=meta.split()[2].decode()
    return values
before=blobs(base);now=blobs('HEAD');assert all(now.get(name)==sha for name,sha in before.items());start=time.monotonic()
for name,sha in before.items():
    p=root/name;assert not p.is_symlink();data=p.read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==sha,name
result=dict(baseline_sha=base,inherited_git_blobs=len(before),actual_byte_hashes_verified=len(before),changes=0,elapsed_seconds=time.monotonic()-start,unknown_lock_preserved=(root/'.git/codex-index-refresh.lock').exists())
(r/'inherited-evidence-proof.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
