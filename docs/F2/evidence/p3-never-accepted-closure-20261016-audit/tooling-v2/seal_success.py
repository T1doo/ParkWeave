"""Seal one successful independent audit after its process/log have closed."""
from pathlib import Path
import hashlib,json,sys,re,datetime
root=Path('/workspace/ParkWeave');base=root/'.runtime/p3-closure-audit';attempt=sys.argv[1]
if re.fullmatch('[A-Za-z0-9_-]{1,60}',attempt) is None:raise ValueError('bounded attempt required')
run=base/attempt;target=run/'seal.json'
if target.exists():raise ValueError('never overwrite existing audit seal')
result=run/'final-archive-audit.json';v=json.loads(result.read_text())
if v['status']!='PASS' or v['errors']:raise ValueError('only actual complete PASS may be sealed')
log=base/(attempt+'-run.log')
paths=[base/'tooling-v2'/n for n in ('audit_archive.py','primary_gate_audit.py','external_copy_audit.py','external-copy-selection.json','path_minimization.py','seal_success.py')]+[base/'preparation-v6.json',log]+[p for p in run.rglob('*') if p.is_file()]
if any(p.is_symlink() for p in paths):raise ValueError('audit symlink refused')
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
record=dict(status='SEALED_NO_FURTHER_AUDIT_ATTEMPT_WRITES',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha=v['source_sha'],attempt=attempt,seal_self_hash_included=False,files=files)
target.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(seal_path=str(target.relative_to(root)),seal_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),files=len(files))))
