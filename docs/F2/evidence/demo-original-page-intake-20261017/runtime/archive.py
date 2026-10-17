from pathlib import Path
import hashlib,json,re,subprocess
root=Path('/workspace/ParkWeave');r=root/'.runtime/demo-original-page-intake';dest=root/'docs/F2/evidence/demo-original-page-intake-20261017'
assert not dest.exists()
paths=sorted(p for p in r.rglob('*') if p.is_file() and p.name!='inherited-evidence-blobs.txt' and not p.is_relative_to(r/'export-v1') and p.suffix in ('.json','.xml','.log','.py','.stdout','.stderr','.png'))
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
known_inputs=subprocess.check_output(['git','ls-files','-z'])+(r/'preflight-remote.stdout').read_bytes()
known=set(pattern.findall(known_inputs))
records=[]
for p in paths:
 raw=p.read_bytes();relative=Path('runtime')/p.relative_to(r);public=dest/relative;public.parent.mkdir(parents=True,exist_ok=True)
 count=0
 def redact(match):
  global count
  if match.group(0) in known:return match.group(0)
  count+=1;return b'REDACTED_TEMPORARY_SESSION_CANDIDATE'
 data=raw if p.suffix=='.png' else pattern.sub(redact,raw)
 public.write_bytes(data);records.append(dict(raw_path=str(p),public_path=str(relative),raw_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(raw),public_bytes=len(data),redactions=count))
inherited=r/'inherited-evidence-blobs.txt'
manifest=dict(source_sha='9c50ff798fd4c6a78f1756aba75cffac2a8d137a',records=records,redaction_rule='bounded 43-character URL-safe session candidates in text, excluding known tracked paths and preflight ref names; PNG password control masked; raw originals private',redactions=sum(x['redactions'] for x in records),omitted=[dict(raw_path=str(inherited),sha256=hashlib.sha256(inherited.read_bytes()).hexdigest(),count=len(inherited.read_text().splitlines()),reason='large prior evidence Git-blob map retained privately; reconstruct from 897fc694 docs/F2/evidence tree, validate every inherited blob before delivery')],earlier_tmp='pytest-owned retention removed early development tmp directories before archival; every pytest log/XML/exact failed test copy/input manifest retained; only available later tmp diagnostics archived')
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(pairs=len(records),redactions=manifest['redactions'])))
