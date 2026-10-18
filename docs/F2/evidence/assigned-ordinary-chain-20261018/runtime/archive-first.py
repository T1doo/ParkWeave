from pathlib import Path
import hashlib,json,re,subprocess,shutil
root=Path('/workspace/ParkWeave');r=root/'.runtime/assigned-demo-chain-20261018'
dest=root/'docs/F2/evidence/assigned-ordinary-chain-20261018';assert not dest.exists()
final=json.loads((r/'final-result.json').read_text())
assert final['unique']==31 and final['testcases']==31 and not any(final[k] for k in ['failures','errors','skipped','input_drift'])
for label in ['development-v1','development-v2','development-v3','final']:
    call=json.loads((r/(label+'-invocation.json')).read_text());base=Path(call['basetemp'])
    if not base.is_dir():continue
    for p in sorted(base.rglob('*')):
        if not p.is_file() or p.suffix not in ('.json','.xml','.log','.png','.stdout','.stderr'):continue
        rel=p.relative_to(base)
        if any(part=='data' or part.startswith('parkweave-pg') for part in rel.parts):continue
        target=r/'retained-tmp'/label/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
known=set(pattern.findall(subprocess.check_output(['git','ls-files','-z'],cwd=root)))
records=[]
for p in sorted(r.rglob('*')):
    if not p.is_file() or p.suffix not in ('.json','.jsonl','.xml','.log','.py','.js','.md','.stdout','.stderr','.png','.txt'):continue
    if p.name=='inherited-evidence-blobs.txt':continue
    rel=Path('runtime')/p.relative_to(r);public=dest/rel;public.parent.mkdir(parents=True,exist_ok=True);raw=p.read_bytes();redactions=[0]
    def redact(m):
        if m.group() in known:return m.group()
        redactions[0]+=1;return b'REDACTED_TEMPORARY_SESSION_CANDIDATE'
    data=raw if p.suffix in ('.png','.py','.js') else pattern.sub(redact,raw)
    public.write_bytes(data);records.append(dict(raw_path=str(p),public_path=str(rel),raw_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(raw),public_bytes=len(data),redactions=redactions[0]))
manifest=dict(source_sha=final['source_sha'],records=records,redactions=sum(x['redactions'] for x in records),redaction_rule='bounded43 URL-safe synthetic temporary session candidates, excluding tracked path identifiers; static source and PNG untouched',limits=['No PG data directories exported','Fixture initial existing preparation/materials/exactRun executor assignment are separate from ordinary runtime','Only final31 source window accepted; development failures/pass retained without aggregation','Prior72c296 and independent31 remain qualified at that earlier SHA; no transfer to new tests SHA'])
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(pairs=len(records),redactions=manifest['redactions'])))
