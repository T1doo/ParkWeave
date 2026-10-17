from pathlib import Path
import hashlib,json,re,subprocess
root=Path('/workspace/ParkWeave');r=root/'.runtime/demo-original-page-intake';dest=root/'docs/F2/evidence/demo-original-page-intake-20261017';m=json.loads((dest/'manifest.json').read_text());old={x['raw_path']:x for x in m['records']}
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])');known=set(pattern.findall(subprocess.check_output(['git','ls-files','-z'])+(r/'preflight-remote.stdout').read_bytes()))
for p in sorted(r.rglob('*')):
 if not p.is_file() or p.is_relative_to(r/'export-v1') or p.name in ('inherited-evidence-blobs.txt','delivery-whitespace.log') or p.suffix not in ('.json','.xml','.log','.py','.stdout','.stderr','.png'):continue
 raw=p.read_bytes()
 if str(p) in old:
  assert hashlib.sha256(raw).hexdigest()==old[str(p)]['raw_sha256'];continue
 count=0
 def redact(match):
  global count
  if match.group(0) in known:return match.group(0)
  count+=1;return b'REDACTED_TEMPORARY_SESSION_CANDIDATE'
 data=raw if p.suffix=='.png' else pattern.sub(redact,raw);relative=Path('runtime')/p.relative_to(r);out=dest/relative;assert not out.exists();out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
 m['records'].append(dict(raw_path=str(p),public_path=str(relative),raw_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(raw),public_bytes=len(data),redactions=count))
m['records'].sort(key=lambda x:x['public_path']);m['redactions']=sum(x['redactions'] for x in m['records']);m['delivery_checks']='Final validation metadata and push receipt can be outside raw/public pairs to avoid recursive archives; private original records retained.'
(dest/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(dict(pairs=len(m['records']),redactions=m['redactions']))
