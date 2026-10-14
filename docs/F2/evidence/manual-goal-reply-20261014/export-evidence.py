from pathlib import Path
import json,hashlib,re
raw=Path('.runtime/manual-goal-reply-20261014');out=Path('docs/F2/evidence/manual-goal-reply-20261014');out.mkdir(parents=True,exist_ok=True);index=[]
for p in sorted(raw.rglob('*')):
 if not p.is_file() or '__pycache__' in p.parts or p.name in ('archive-review.json','final-handoff.json') or p.suffix not in ('.json','.log','.xml','.exit','.tsv','.py','.js'):continue
 data=p.read_bytes();export=data
 if p.suffix in ('.log','.xml'):export=re.sub(r'(template_consumption = )[^\n]*',r'\1[REDACTED_SYNTHETIC_FIXTURE_SESSION_REPR]',data.decode()).encode()
 target=out/p.relative_to(raw);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(export)
 index.append(dict(file=str(p.relative_to(raw)),raw_sha256=hashlib.sha256(data).hexdigest(),export_sha256=hashlib.sha256(export).hexdigest(),bytes=len(export),raw_bytes=len(data),redacted=data!=export))
(out/'export-index.json').write_text(json.dumps(index,indent=2)+'\n');print({'files':len(index)})
