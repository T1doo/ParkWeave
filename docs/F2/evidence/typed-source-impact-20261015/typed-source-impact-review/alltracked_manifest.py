from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/typed-source-impact-review'
SHA='a5d9da251c223e3a64e20d3d47987d5b58fcdb6f'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==SHA
rows=subprocess.check_output(['git','ls-tree','-rz','--full-tree',SHA],cwd=ROOT).split(b'\0')
files={};mismatch=[];total=0
for raw in rows:
    if not raw:continue
    meta,path=raw.split(b'\t',1);mode,kind,oid=meta.decode().split();path=path.decode();assert kind=='blob',path
    data=(ROOT/path).read_bytes();total+=len(data)
    files[path]={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'git_blob':oid}
    if hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()!=oid:mismatch.append(path)
result={'source_sha':SHA,'all_git_tracked':len(files),'bytes':total,'frozen_git_blob_mismatches':mismatch,'files':files}
(OUT/('alltracked-a5d9da25-'+sys.argv[1]+'.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='files'}))
