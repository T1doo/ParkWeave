from pathlib import Path
import hashlib,json,re,subprocess,shutil
root=Path('/workspace/ParkWeave');r=root/'.runtime/preparation-read-write-timing';dest=root/'docs/F2/evidence/preparation-read-write-timing-20261017'
assert not dest.exists()
assert json.loads((r/'final-result.json').read_text())['unique']==284
for name in ['resource-red','resource-green','final']:
 invocation=r/(name+'-invocation.json')
 if not invocation.exists():continue
 base=Path(json.loads(invocation.read_text())['basetemp'])
 if not base.is_dir():continue
 for src in sorted(base.rglob('*')):
  if not src.is_file() or src.suffix not in ('.json','.xml','.log','.png','.stdout','.stderr'):continue
  rel=src.relative_to(base)
  if any(part=='data' or part.startswith('parkweave-pg') for part in rel.parts):continue
  target=r/'retained-tmp'/name/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
for directory in ['service-plan-cold-recovery/browser','case-goal-results/browser','template-plan-continuity-20261013']:
 original=root/'.runtime'/directory
 if not original.is_dir():continue
 started=json.loads((r/'final-invocation.json').read_text())['started']
 for src in original.rglob('*'):
  if src.is_file() and src.suffix in ('.png','.json','.log') and src.stat().st_mtime>=started:
   target=r/'retained-other-runtime'/directory/src.relative_to(original);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
paths=[]
for p in sorted(r.rglob('*')):
 if not p.is_file() or p.suffix not in ('.json','.xml','.log','.py','.html','.stdout','.stderr','.png','.txt'):continue
 if p.relative_to(r).parts[0].startswith('recovery-check-') or p.name=='inherited-evidence-blobs.txt':continue
 paths.append(p)
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
known=set(pattern.findall(subprocess.check_output(['git','ls-files','-z'])+(r/'pre-freeze-remote.txt').read_bytes()))
records=[]
for p in paths:
 raw=p.read_bytes();relative=Path('runtime')/p.relative_to(r);public=dest/relative;public.parent.mkdir(parents=True,exist_ok=True);redactions=[0]
 def redact(match):
  if match.group(0) in known:return match.group(0)
  redactions[0]+=1;return b'REDACTED_TEMPORARY_SESSION_CANDIDATE'
 data=raw if p.suffix=='.png' else pattern.sub(redact,raw)
 public.write_bytes(data);records.append(dict(raw_path=str(p),public_path=str(relative),raw_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(raw),public_bytes=len(data),redactions=redactions[0]))
manifest=dict(source_sha='25c64f1dd4bb2ca9a79be88650d3a1b410c4bef5',records=records,redactions=sum(x['redactions'] for x in records),redaction_rule='bounded 43-character URL-safe temporary synthetic session candidates, excluding known tracked paths and remote ref identifiers; PNG untouched, password controls masked by browser',excluded_test_window='green-v1 retained as failure/provenance evidence only; no immutable window proof',private_only=['recovery-check-20261017 process snapshot, source snapshot and raw tar archive; original logs retained under raw paths','inherited-evidence-blobs.txt: all29065 original evidence blobs; reconstructed from175918d4 and verified before delivery'],limits='Only generated or still available diagnostics copied. No database data directories, real source records, credentials, assignments or real model calls.')
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(pairs=len(records),redactions=manifest['redactions'])))
