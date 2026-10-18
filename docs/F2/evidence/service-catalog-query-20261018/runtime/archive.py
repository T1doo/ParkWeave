from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');raw=root/'.runtime/service-catalog-query-20261018';pub=root/'docs/F2/evidence/service-catalog-query-20261018'
pub.mkdir(exist_ok=False)
sha=lambda b:hashlib.sha256(b).hexdigest()
review=Path((raw/'independent/active-review-path.txt').read_text().strip())
listed=json.loads((review/'publication-files.json').read_text())
upstream_rows=json.loads((review/'publication-redaction-map.json').read_text())
upstream={str(review/row['public']):row for row in upstream_rows}
for row in upstream_rows:
 assert sha((review/row['raw']).read_bytes())==row['raw_sha256']
 assert sha((review/row['public']).read_bytes())==row['public_sha256']
secrets=set();fragments=set()
def collect(value):
 if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{43}',value):secrets.add(value)
 elif isinstance(value,dict):
  for item in value.values():collect(item)
 elif isinstance(value,list):
  for item in value:collect(item)
for path in (raw/'independent').rglob('fixture-token-values.private.json'):collect(json.loads(path.read_text()))
pattern=re.compile(r"(?=(?:fixture-[abc]|executor-[ab]|unassigned)'\s*:\s*'([^']*)')")
inputs=[]
names=['baseline.json','baseline-remote.txt','baseline-remote.stderr','protected-originals.json','module-source-validation.json','module-source-validation-351735ef.json','prepush-check.json','prepush-remote.txt','prepush-remote.stderr','failure-ledger.json','counting-verification.json','counting-verification-351735ef.json','cross-window-verification.json','inherited-evidence-before.json','run-window.py','verify-baseline.py','verify-baseline.stdout','verify-baseline.stderr','verify-window.py','projection-refinement.json','archive-controller-note.json','archive-attempt-2.stdout','archive-attempt-2.stderr','archive-attempt-3.stdout','archive-attempt-3.stderr','archive.py']
for name in names:inputs.append((raw/name,Path('runtime')/name))
for folder in ['development','frozen-351735ef','frozen-9fd652a2']:
 for path in sorted((raw/folder).rglob('*')):
  if path.is_file():inputs.append((path,Path('runtime')/path.relative_to(raw)))
for relative in listed:
 path=review/relative
 assert path.is_file() and path.resolve().is_relative_to(review.resolve()) and '.private.' not in path.name and not any(p in ('mirror','data','pytest-temp') for p in Path(relative).parts)
 inputs.append((path,Path('independent')/relative))
assert len(inputs)==len(set(str(rel) for path,rel in inputs))
for path,rel in inputs:
 for m in pattern.finditer(path.read_text()):
  if re.fullmatch(r'[A-Za-z0-9_-]{43}',m[1]):secrets.add(m[1])
  for piece in re.split(r'[^A-Za-z0-9_-]+',m[1]):
   if len(piece)>=16 and piece not in ('ep-specialist-fixture-a','SYNTHETIC_SESSION_REDACTED','SYNTHETIC_SESSION_FRAGMENT_REDACTED'):fragments.add(piece)
pairs=[]
for path,rel in inputs:
 prepared=path;mapping=upstream.get(str(path));data=path.read_bytes();text=data.decode();redactions=0
 if mapping:
  path=review/mapping['raw'];redactions=mapping['full_value_replacements']+mapping['actual_fixture_key_prefix_replacements']
  data=path.read_bytes()
 if not mapping:
  for secret in sorted(secrets):
   redactions+=text.count(secret);text=text.replace(secret,'SYNTHETIC_SESSION_REDACTED')
  spans={(m.start(1),m.end(1)) for m in pattern.finditer(text) if m[1] not in ('SYNTHETIC_SESSION_REDACTED','SYNTHETIC_SESSION_FRAGMENT_REDACTED') and (re.fullmatch(r'[A-Za-z0-9_-]{30,}',m[1]) or '...' in m[1])}
  for start,end in sorted(spans,reverse=True):text=text[:start]+'SYNTHETIC_SESSION_REDACTED'+text[end:];redactions+=1
 out=prepared.read_bytes() if mapping else text.encode();target=pub/rel;target.parent.mkdir(exist_ok=True,parents=True);target.write_bytes(out)
 if mapping:assert sha(out)==mapping['public_sha256']
 pairs.append(dict(raw=str(path.relative_to(root)),public=str(target.relative_to(root)),raw_sha256=sha(data),public_sha256=sha(out),public_bytes=len(out),synthetic_session_redactions=redactions,prepared_public=str(prepared.relative_to(root)) if mapping else None))
manifest=dict(frozen_sha='9fd652a29dfbf642fa0f4a49547bf3553417bd74',created_utc=datetime.now(timezone.utc).isoformat(),pairs=pairs,raw_retained=True,excluded='Private session/config, mirror trees, PostgreSQL data; no browser artifacts.')
(pub/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
for row in pairs:
 path=root/row['public'];data=path.read_bytes()
 assert sha(data)==row['public_sha256'] and sha((root/row['raw']).read_bytes())==row['raw_sha256']
 if path.suffix=='.json':json.loads(data)
 elif path.suffix=='.jsonl':
  for line in data.decode().splitlines():json.loads(line)
 elif path.suffix=='.xml':ET.fromstring(data)
check=dict(pairs=len(pairs),unchanged_pairs=sum(r['raw_sha256']==r['public_sha256'] for r in pairs),redacted_pairs=sum(r['raw_sha256']!=r['public_sha256'] for r in pairs),synthetic_session_redactions=sum(r['synthetic_session_redactions'] for r in pairs),paired_public_targets_unique=True,hash_mismatches=[],structured_files_parsed=True)
(pub/'archive-validation.json').write_text(json.dumps(check,indent=2)+'\n')
findings=[];scanned=0
for path in pub.rglob('*'):
 if path.is_file():
  scanned+=1;text=path.read_text()
  if any(v in text or v[:16] in text for v in secrets) or any(v in text for v in fragments):findings.append(str(path.relative_to(pub)))
assert not findings,findings
(pub/'confidentiality-validation.json').write_text(json.dumps(dict(known_synthetic_session_values=len(secrets),known_fragments_at_least_16=len(fragments),full_and_16_character_prefix_matches=findings,excluded_deterministic_fixture_role_fragment='ep-specialist-fixture-a',excluded_public_redaction_markers=['SYNTHETIC_SESSION_REDACTED','SYNTHETIC_SESSION_FRAGMENT_REDACTED'],files_scanned_before_this_metadata=scanned,raw_preserved=True),indent=2)+'\n')
print(json.dumps(check))
