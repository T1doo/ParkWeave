from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');raw=root/'.runtime/case-step-notices-20261018';review=raw/'independent';pub=root/'docs/F2/evidence/case-step-notices-20261018'
sha=lambda b:hashlib.sha256(b).hexdigest()
listed=json.loads((review/'publication-files.json').read_text())
upstream_rows=json.loads((review/'raw-public-redaction-map.json').read_text())['files']
upstream={str(review/r['public']):r for r in upstream_rows}
secrets=set();fragments=set()
def collect(v):
 if isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_-]{43}',v):secrets.add(v)
 elif isinstance(v,dict):
  for x in v.values():collect(x)
 elif isinstance(v,list):
  for x in v:collect(x)
for p in review.rglob('fixture-token-values.private.json'):collect(json.loads(p.read_text()))
inputs=[]
for p in sorted(raw.iterdir()):
 if p.is_file() and '.private.' not in p.name and p.name not in ('archive.stdout','archive.stderr','baseline-notice-page.html','html-draft.js'):inputs.append((p,Path('runtime')/p.name))
for name in ['development','frozen-928be187','frozen-1da2e6c2']:
 for p in sorted((raw/name).rglob('*')):
  if p.is_file() and '.private.' not in p.name:inputs.append((p,Path('runtime')/p.relative_to(raw)))
for relative in listed:
 p=review/relative
 assert p.is_file() and p.resolve().is_relative_to(review.resolve()) and '.private.' not in p.name and not any(x in ('mirror','data','pytest-temp') for x in Path(relative).parts)
 inputs.append((p,Path('independent')/relative))
assert len(inputs)==len(set(str(r) for p,r in inputs))
pattern=re.compile(r"(?=(?:fixture-[abc]|executor-[ab]|unassigned)'\s*:\s*'([^']*)')")
for p,rel in inputs:
 if str(p) in upstream:continue
 for m in pattern.finditer(p.read_text()):
  if re.fullmatch(r'[A-Za-z0-9_-]{43}',m[1]):secrets.add(m[1])
  for x in re.split('[^A-Za-z0-9_-]+',m[1]):
   if len(x)>=16 and x not in ('ep-specialist-fixture-a','SYNTHETIC_SESSION_REDACTED','SYNTHETIC_SESSION_FRAGMENT_REDACTED'):fragments.add(x)
pub.mkdir(exist_ok=False)
pairs=[]
for prepared,rel in inputs:
 mapping=upstream.get(str(prepared));path=prepared;data=path.read_bytes();out=data;count=0
 if mapping:
  path=review/mapping['raw'];data=path.read_bytes()
  assert sha(data)==mapping['raw_sha256'] and sha(out)==mapping['public_sha256']
  count=mapping['replacement_count']
 else:
  text=data.decode()
  for secret in sorted(secrets):count+=text.count(secret);text=text.replace(secret,'SYNTHETIC_SESSION_REDACTED')
  spans={(m.start(1),m.end(1)) for m in pattern.finditer(text) if m[1] not in ('SYNTHETIC_SESSION_REDACTED','SYNTHETIC_SESSION_FRAGMENT_REDACTED') and (re.fullmatch(r'[A-Za-z0-9_-]{30,}',m[1]) or '...' in m[1])}
  for start,end in sorted(spans,reverse=True):text=text[:start]+'SYNTHETIC_SESSION_REDACTED'+text[end:];count+=1
  out=text.encode()
 target=pub/rel;target.parent.mkdir(exist_ok=True,parents=True);target.write_bytes(out)
 pairs.append(dict(raw=str(path.relative_to(root)),public=str(target.relative_to(root)),raw_sha256=sha(data),public_sha256=sha(out),public_bytes=len(out),synthetic_session_redactions=count,prepared_public=str(prepared.relative_to(root)) if mapping else None))
for row in pairs:
 p=root/row['public'];data=p.read_bytes();assert sha(data)==row['public_sha256'] and sha((root/row['raw']).read_bytes())==row['raw_sha256']
 if p.suffix=='.json':json.loads(data)
 elif p.suffix=='.jsonl':
  for line in data.decode().splitlines():json.loads(line)
 elif p.suffix=='.xml':ET.fromstring(data)
findings=[]
for p in pub.rglob('*'):
 if p.is_file():
  t=p.read_text()
  if any(v in t or v[:16] in t for v in secrets) or any(v in t for v in fragments):findings.append(str(p.relative_to(pub)))
assert not findings,findings
(pub/'manifest.json').write_text(json.dumps(dict(frozen_sha='1da2e6c28024e3d7f518a2b8d62ce271c5ddb749',created_utc=datetime.now(timezone.utc).isoformat(),pairs=pairs,raw_retained=True,excluded='Private session/config, mirror trees and PostgreSQL data; no browser artifacts.'),indent=2)+'\n')
checks=dict(pairs=len(pairs),unchanged_pairs=sum(r['raw_sha256']==r['public_sha256'] for r in pairs),redacted_pairs=sum(r['raw_sha256']!=r['public_sha256'] for r in pairs),synthetic_session_redactions=sum(r['synthetic_session_redactions'] for r in pairs),paired_public_targets_unique=True,hash_mismatches=[],structured_files_parsed=True,independent_canonical_shadows_copied_byte_for_byte=True)
(pub/'archive-validation.json').write_text(json.dumps(checks,indent=2)+'\n')
(pub/'confidentiality-validation.json').write_text(json.dumps(dict(known_synthetic_session_values=len(secrets),known_fragments_at_least_16=len(fragments),full_and_16_character_prefix_matches=findings,excluded_deterministic_fixture_role_fragment='ep-specialist-fixture-a',excluded_public_redaction_markers=['SYNTHETIC_SESSION_REDACTED','SYNTHETIC_SESSION_FRAGMENT_REDACTED'],raw_preserved=True),indent=2)+'\n')
print(json.dumps(checks))
