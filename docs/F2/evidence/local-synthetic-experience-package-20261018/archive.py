from pathlib import Path
import hashlib,json,shutil
R=Path.cwd();D=R/'.runtime/local-synthetic-experience-package-20261018';A=R/'docs/F2/evidence/local-synthetic-experience-package-20261018'
assert not A.exists();A.mkdir(parents=True)
def sha(b):return hashlib.sha256(b).hexdigest()
def pairs(values):
    result={}
    for key,value in values:
        assert key not in result,'duplicate JSON key'
        result[key]=value
    return result
entries=[]
for p in sorted(D.rglob('*')):
    if not p.is_file() or p.suffix=='.zip':continue
    assert not p.is_symlink()
    relative=p.relative_to(D);raw=p.read_bytes();raw.decode('utf-8')
    if p.suffix=='.json':
        json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda s:(_ for _ in ()).throw(ValueError(s)))
    target=A/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    assert target.read_bytes()==raw
    entries.append(dict(raw_path=str(p),public_path=target.relative_to(R).as_posix(),bytes=len(raw),raw_sha256=sha(raw),public_sha256=sha(target.read_bytes()),redactions=0))
ind=A/'independent/pw-ind-experience-33bf2ef-okagab9l/independent-final-review.json'
assert sha(ind.read_bytes())=='1efa827e45aa9edb078fc2c02eb300b4f6b05fa563158fb7e15112a89e2e23ee'
manifest=dict(source_commit='33bf2efa125e5d3b7b59e30b3ea153b9d58a113a',raw_public_pairs=len(entries),redactions=0,strict_json_checked=True,raw_bytes_preserved=True,independent_stable_sha256=sha(ind.read_bytes()),excluded_zip_artifacts='Preliminary/repeat ZIPs retained in local runtime; final ZIP is separately tracked in deliverables with its full checksum.',entries=entries)
(A/'archive-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='entries'}))
