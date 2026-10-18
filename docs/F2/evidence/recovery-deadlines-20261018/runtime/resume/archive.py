from pathlib import Path
import hashlib,json,re,subprocess,shutil

root=Path('/workspace/ParkWeave')
current=root/'.runtime/ttl-template-resume-20261018'
prior=root/'.runtime/ttl-template-repair-20261017'
dest=root/'docs/F2/evidence/recovery-deadlines-20261018'
assert not dest.exists()
result=json.loads((current/'final-result.json').read_text())
assert result['unique']==296 and not any(result[k] for k in ['failures','errors','skipped','input_drift','missing','extra','unmapped_interrupted_records'])
for name in ['interrupted-failures-serial']:
    call=json.loads((current/(name+'-invocation.json')).read_text())
    base=Path(call['basetemp'])
    if base.is_dir():
        for src in sorted(base.rglob('*')):
            if not src.is_file() or src.suffix not in ('.json','.xml','.log','.png','.stdout','.stderr'):continue
            rel=src.relative_to(base)
            if any(p=='data' or p.startswith('parkweave-pg') for p in rel.parts):continue
            target=current/'retained-tmp'/name/rel
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
for i in range(2):
    call=json.loads((current/f'final-shard-{i}-invocation.json').read_text());base=Path(call['basetemp'])
    assert base.is_dir()
    for src in sorted(base.rglob('*')):
        if not src.is_file() or src.suffix not in ('.json','.xml','.log','.png','.stdout','.stderr'):continue
        rel=src.relative_to(base)
        if any(p=='data' or p.startswith('parkweave-pg') for p in rel.parts):continue
        target=current/'retained-tmp'/f'final-shard-{i}'/rel
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
started=json.loads((current/'final-invocation.json').read_text())['started']
for directory in ['service-plan-cold-recovery/browser','case-goal-results/browser','template-plan-continuity-20261013']:
    base=root/'.runtime'/directory
    if not base.is_dir():continue
    for src in sorted(base.rglob('*')):
        if src.is_file() and src.suffix in ('.png','.json','.log') and src.stat().st_mtime>=started:
            target=current/'retained-other-runtime'/directory/src.relative_to(base)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target)
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
known=set(pattern.findall(subprocess.check_output(['git','ls-files','-z'],cwd=root)+(current/'preflight-remote.txt').read_bytes()))
records=[]
for prefix,base in [('prior-repair',prior),('resume',current)]:
    for src in sorted(base.rglob('*')):
        if not src.is_file() or src.suffix not in ('.json','.jsonl','.xml','.log','.py','.js','.md','.html','.stdout','.stderr','.png','.txt'):continue
        if src.name in ('inherited-evidence-blobs.txt',):continue
        rel=Path('runtime')/prefix/src.relative_to(base);public=dest/rel;public.parent.mkdir(parents=True,exist_ok=True)
        raw=src.read_bytes();count=[0]
        def redact(m):
            if m.group() in known:return m.group()
            count[0]+=1;return b'REDACTED_TEMPORARY_SESSION_CANDIDATE'
        data=raw if src.suffix in ('.png','.py','.js','.html') else pattern.sub(redact,raw)
        public.write_bytes(data)
        records.append(dict(raw_path=str(src),public_path=str(rel),raw_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(raw),public_bytes=len(data),redactions=count[0]))
manifest=dict(source_sha=result['source_sha'],records=records,redactions=sum(r['redactions'] for r in records),redaction_rule='Bounded 43-character URL-safe synthetic temporary session candidates; known tracked paths and remote refs retained; PNG and static code/HTML snapshots untouched (no captured runtime tokens in those sources).',limits=['R2 workspace raw logs retained; original R2 /tmp browser/API and independent mirror files were absent after environment restore.','R2 reproduction PASS means a former defect was observed, not acceptance.','R2 paused 17PASS/10FAIL/3unnamed interrupted records is incomplete and excluded from acceptance.','No PG data directories or unknown process snapshots exported.','Inherited 29301 F2 evidence blobs remain unchanged; private blob map excluded.'])
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(pairs=len(records),redactions=manifest['redactions'])))
