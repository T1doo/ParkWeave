"""Root hash/structure/residual checks; redaction reconstruction is independent."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,xml.etree.ElementTree as ET
root=Path.cwd();archive=root/'docs/F2/evidence/shared-source-cases-20261015'
index=json.loads((archive/'index.json').read_text());seen=set();counts=Counter();redactions=Counter()
private_paths=[root/'.runtime/template-migration-tests-20261014/redaction-values.private.json',root/'.runtime/template-structure-tests-20261015/redaction-values.private.json']
for directory in ('shared-source-cases','shared-source-cases-independent','shared-source-cases-review','shared-source-cases-backend'):
 private_paths.extend((root/'.runtime'/directory).rglob('*redaction*.private.json'))
private=set()
for path in private_paths:
 if path.exists():private.update(json.loads(path.read_text()))
assert all(isinstance(v,str) and re.fullmatch('[A-Za-z0-9_-]{43}',v) for v in private)
scan=re.compile(r'(?=([A-Za-z0-9_-]{43}))')
for entry in index['entries']:
 raw_path=root/entry['raw_path'];out=root/entry['export_path'];assert out.is_relative_to(archive) and out not in seen;seen.add(out)
 raw=raw_path.read_bytes();data=out.read_bytes()
 assert (hashlib.sha256(raw).hexdigest(),len(raw))==(entry['raw_sha256'],entry['raw_bytes'])
 assert (hashlib.sha256(data).hexdigest(),len(data))==(entry['export_sha256'],entry['export_bytes'])
 assert not any(m[1] in private for m in scan.finditer(data.decode('utf-8'))),'known synthetic session residual'
 redactions.update(entry['redactions']);counts['files']+=1;counts['bytes']+=len(data)
 if out.suffix=='.xml':
  a=ET.fromstring(raw);b=ET.fromstring(data)
  def statuses(doc):return Counter((c.get('classname'),c.get('name'),'ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS') for c in doc.iter('testcase'))
  assert statuses(a)==statuses(b);assert [(n.tag,sorted(n.attrib)) for n in a.iter()]==[(n.tag,sorted(n.attrib)) for n in b.iter()];counts['xml']+=1
 elif out.suffix=='.json':json.loads(data);counts['json']+=1
 elif out.suffix=='.jsonl':
  for line in data.splitlines():json.loads(line)
  counts['jsonl']+=1
 elif out.suffix=='.py':compile(data,str(out),'exec');assert raw==data;counts['python']+=1
 elif out.suffix=='.js':assert raw==data;counts['javascript']+=1
report=dict(status='ROOT_HASH_STRUCTURE_RESIDUAL_PASS_INDEPENDENT_REBUILD_PENDING',source_sha=index['source_sha'],counts=dict(counts),redactions=dict(redactions),known_synthetic_session_residuals=0,private_value_format_verified='43 URLSAFE characters; overlapping-position candidate scan',deterministic_redaction_reconstruction='PENDING_INDEPENDENT_AUDIT',private_originals_hashes_sizes_unchanged=True,public_exports_hashes_sizes_exact=True,prepared_legacy_verify_script_executed=False)
(root/'.runtime/shared-source-cases/archive-audit.json').write_text(json.dumps(report,indent=2)+'\n');(archive/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
