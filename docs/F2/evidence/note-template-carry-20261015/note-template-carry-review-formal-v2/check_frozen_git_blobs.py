from pathlib import Path
import hashlib,json,subprocess,time
r=Path('/workspace/ParkWeave');out=Path(__file__).resolve().parent;sha='f686adafe3cec9b2820c10fada51ef2f57a559a6';begin=time.monotonic()
f=json.loads((r/'.runtime/note-template-carry-root/freeze-v3.json').read_text());assert f['source_sha']==sha
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()==sha
rows=subprocess.check_output(['git','ls-tree','-rz','--full-tree',sha],cwd=r).split(b'\0');items=[]
for row in rows:
 if not row:continue
 info,path=row.split(b'\t',1);mode,kind,oid=info.split();assert kind==b'blob'
 items.append((path.decode(),oid.decode()))
assert set(p for p,_ in items)==set(f['all_tracked_sha256'])
data=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(oid for _,oid in items)+'\n').encode(),cwd=r)
pos=0;git_drift=[];worktree_drift=[]
for path,oid in items:
 e=data.index(b'\n',pos);parts=data[pos:e].split();assert parts[0].decode()==oid and parts[1]==b'blob';size=int(parts[2]);start=e+1;raw=data[start:start+size];assert data[start+size:start+size+1]==b'\n';pos=start+size+1
 if hashlib.sha256(raw).hexdigest()!=f['all_tracked_sha256'][path]:git_drift.append(path)
 if hashlib.sha256((r/path).read_bytes()).hexdigest()!=f['all_tracked_sha256'][path]:worktree_drift.append(path)
assert pos==len(data)
record=dict(status='PASS' if not git_drift and not worktree_drift else 'FAIL',source_sha=sha,all_tracked_paths=len(items),source_paths=len(f['source_paths']),git_blob_drift=git_drift,worktree_drift=worktree_drift,elapsed_seconds=time.monotonic()-begin,no_Git_or_source_writes=True)
(out/'frozen-Git-blob-proof.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));assert record['status']=='PASS'
