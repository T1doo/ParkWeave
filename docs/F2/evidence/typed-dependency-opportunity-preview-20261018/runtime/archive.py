from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,shutil,subprocess,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');raw=root/'.runtime/typed-dependency-opportunity-preview-20261018';public=root/'docs/F2/evidence/typed-dependency-opportunity-preview-20261018'
public.mkdir(exist_ok=False)
sha=lambda data:hashlib.sha256(data).hexdigest()
pairs=[]
private_values=[]
def tokens(value):
 if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{43}',value):private_values.append(value)
 elif isinstance(value,dict):
  for item in value.values():tokens(item)
 elif isinstance(value,list):
  for item in value:tokens(item)
for path in (raw/'independent').rglob('fixture-token-values.private.json'):tokens(json.loads(path.read_text()))
# Overlapping lookaheads retain tokens after pytest's truncated fixture-key repr.
credential=re.compile(r"(?=(?:fixture-[abc]|executor-[ab]|unassigned)'\s*:\s*'([^']*)')")
def copy(path,relative):
 data=path.read_bytes();out=data;replacements=0
 try:
  text=data.decode('utf-8')
  for token in set(private_values):
   count=text.count(token);replacements+=count
   if count:text=text.replace(token,'SYNTHETIC_SESSION_REDACTED')
  spans=sorted(set((m.start(1),m.end(1)) for m in credential.finditer(text) if m.group(1)))
  # Only synthetic credential-looking values and pytest truncations in fixture reprs.
  spans=[(a,b) for a,b in spans if re.fullmatch(r'[A-Za-z0-9_-]{30,}',text[a:b]) or '...' in text[a:b]]
  for a,b in reversed(spans):text=text[:a]+'SYNTHETIC_SESSION_REDACTED'+text[b:];replacements+=1
  out=text.encode()
 except UnicodeDecodeError:pass
 dest=public/relative;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(out)
 pairs.append(dict(raw=str(path.relative_to(root)),public=str(dest.relative_to(root)),raw_sha256=sha(data),public_sha256=sha(out),bytes=len(out),synthetic_session_redactions=replacements))
for name in ['baseline.json','baseline-remote.txt','protected-originals.json','module-source-validation.json','prepush-check.json','prepush-remote.txt','prepush-remote.stderr','failure-ledger.json','counting-verification.json','redaction-dryrun.json','inherited-evidence-before.json','run-window.py','archive.py']:
 copy(raw/name,Path('runtime')/name)
for folder in ['development','frozen-85dfd1a2']:
 for path in sorted((raw/folder).rglob('*')):
  if path.is_file():copy(path,Path('runtime')/path.relative_to(raw))
ind=raw/'independent';review=Path((ind/'active-review-path.txt').read_text().strip())
# Independent explicitly prepares a bounded publication list; no mirror/PG data/private config.
listed=json.loads((review/'publication-files.json').read_text())
for relative in listed:
 path=review/relative
 assert path.is_file() and path.resolve().is_relative_to(review.resolve()) and '.private.' not in path.name and not any(part in ('mirror','data','pytest-temp') for part in Path(relative).parts)
 copy(path,Path('independent')/relative)
manifest=dict(frozen_sha='85dfd1a2c4fa9d4c17ca992949661cf969088525',created_utc=datetime.now(timezone.utc).isoformat(),pairs=pairs,redactions=sum(r['synthetic_session_redactions'] for r in pairs),raw_retained=True,excluded='private tokens/config, mirror trees, PostgreSQL data; no browser artifacts')
(public/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n')
errors=[]
for r in pairs:
 data=(root/r['public']).read_bytes()
 if sha(data)!=r['public_sha256'] or sha((root/r['raw']).read_bytes())!=r['raw_sha256']:errors.append(r['public'])
 path=Path(r['public'])
 if path.suffix=='.json':json.loads(data)
 elif path.suffix=='.jsonl':
  for line in data.decode().splitlines():json.loads(line)
 elif path.suffix=='.xml':ET.fromstring(data)
assert not errors,errors
check=dict(pairs=len(pairs),unchanged_pairs=sum(r['raw_sha256']==r['public_sha256'] for r in pairs),redacted_pairs=sum(r['raw_sha256']!=r['public_sha256'] for r in pairs),synthetic_session_redactions=manifest['redactions'],hash_mismatches=errors,structured_files_parsed=True)
(public/'archive-validation.json').write_text(json.dumps(check,indent=2)+'\n');print(json.dumps(check))
