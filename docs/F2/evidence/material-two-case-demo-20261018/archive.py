from pathlib import Path
import hashlib,json,shutil
R=Path.cwd();D=R/'.runtime/material-two-case-demo-20261018';A=R/'docs/F2/evidence/material-two-case-demo-20261018'
assert not A.exists();A.mkdir(parents=True)
# Root-only exact credential check. Values and raw hashes never enter reports.
private=Path('/tmp/parkweave-material-demo-fsnwe42i/sessions.json')
sessions=list(json.loads(private.read_text()).values())
protected=[s.encode() for s in sessions]+[hashlib.sha256(s.encode()).hexdigest().encode() for s in sessions]
def sha(b):return hashlib.sha256(b).hexdigest()
def unique_pairs(values):
    out={}
    for k,v in values:
        assert k not in out
        out[k]=v
    return out
entries=[]
for p in sorted(D.rglob('*')):
    if not p.is_file():continue
    assert not p.is_symlink()
    raw=p.read_bytes();raw.decode('utf-8')
    assert not any(s in raw for s in protected),'credential export refused; value withheld'
    if p.suffix=='.json':
        json.loads(raw,object_pairs_hook=unique_pairs,parse_constant=lambda s:(_ for _ in ()).throw(ValueError(s)))
    target=A/p.relative_to(D);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    assert target.read_bytes()==raw
    entries.append(dict(raw_path=str(p),public_path=target.relative_to(R).as_posix(),bytes=len(raw),raw_sha256=sha(raw),public_sha256=sha(target.read_bytes()),redactions=0))
ind=A/'independent/pw-static-24f6db1-9rHAFq/independent-final-review.json'
assert sha(ind.read_bytes())=='b57efa4435c47e3182a0cbae749664a4e749ade0c8a1f3a3c2dc17bf7fd095e9'
manifest=dict(material_write_source_commit='ee4d69adb3d39ad4abcdd7e4e84e6733c2add765',restart_source_commit='24f6db12490b7ba7f01099d311af97e926eeddd0',raw_public_pairs=len(entries),strict_json_checked=True,exact_current_plain_session_and_raw_token_hash_matches=0,redactions=0,raw_bytes_preserved=True,independent_business_tests_executed=0,independent_stable_sha256=sha(ind.read_bytes()),excluded='All private database/state/sessions/creation/PG/application logs retained only in original owned /tmp directory. Public synthetic TXT copies are separately tracked deliverables.',entries=entries)
(A/'archive-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in manifest.items() if k!='entries'}))
