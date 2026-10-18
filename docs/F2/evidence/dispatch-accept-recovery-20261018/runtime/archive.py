from pathlib import Path
import ast,hashlib,json,re,subprocess,shutil
root=Path('/workspace/ParkWeave');r=root/'.runtime/dispatch-accept-recovery-20261018'
dest=root/'docs/F2/evidence/dispatch-accept-recovery-20261018';assert not dest.exists()
accepted=json.loads((r/'accepted-tests.json').read_text())
for label in accepted['labels']:
    result=json.loads((r/(label+'-result.json')).read_text())
    assert result['source_sha']==accepted['source_sha'] and result['exit_code']==0 and not any(result[k] for k in ['failures','errors','skipped','input_drift'])
for call_path in sorted(r.glob('*-invocation.json')):
    call=json.loads(call_path.read_text());base=Path(call['basetemp']);label=call_path.name.removesuffix('-invocation.json')
    if not base.is_dir():continue
    for p in sorted(base.rglob('*')):
        if not p.is_file() or p.suffix not in ('.json','.jsonl','.xml','.log','.png','.stdout','.stderr'):continue
        rel=p.relative_to(base)
        if any(part=='data' or part.startswith('parkweave-pg') for part in rel.parts):continue
        target=r/'retained-tmp'/label/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
pattern=re.compile(rb'(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{43}(?![A-Za-z0-9_-])')
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=root)
known=set(pattern.findall(tracked));identifiers=set()
for name in tracked.decode().split('\0'):
    if not name.endswith('.py') or not name.startswith(('src/','tests/','scripts/')):continue
    for node in ast.walk(ast.parse((root/name).read_text())):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and pattern.fullmatch(node.name.encode()):identifiers.add(node.name)
known.update(s.encode() for s in identifiers)
records=[]
for p in sorted(r.rglob('*')):
    if not p.is_file() or p.suffix not in ('.json','.jsonl','.xml','.log','.py','.js','.html','.md','.stdout','.stderr','.png','.txt'):continue
    if p.name in ('inherited-evidence-blobs.txt','visible-process-inventory.json'):continue
    rel=Path('runtime')/p.relative_to(r);public=dest/rel;public.parent.mkdir(parents=True,exist_ok=True);raw=p.read_bytes();redactions=[0]
    def redact(m):
        if m.group() in known:return m.group()
        redactions[0]+=1;return b'REDACTED_TEMPORARY_SESSION_CANDIDATE'
    data=raw if p.suffix in ('.png','.py','.js','.html') else pattern.sub(redact,raw)
    public.write_bytes(data)
    entry=dict(raw_path=str(p),public_path=str(rel),raw_sha256=hashlib.sha256(raw).hexdigest(),public_sha256=hashlib.sha256(data).hexdigest(),raw_bytes=len(raw),public_bytes=len(data),redactions=redactions[0])
    if p.name=='demo-pack.json' and raw==b'x'*65537:
        assert re.fullmatch(r'runtime/retained-tmp/(final-A|final-v2-A)/test_bounded_files_mode_and_ex0/demo-pack.json',str(rel))
        entry.update(artifact_kind='INTENTIONAL_INVALID_OVERSIZE_JSON_INPUT',origin_test='tests/test_local_synthetic_demo.py::test_bounded_files_mode_and_existing_catalog_required[oversize]',source='tests/test_local_synthetic_demo.py:256')
    records.append(entry)
manifest=dict(source_sha=accepted['source_sha'],records=records,redactions=sum(x['redactions'] for x in records),source_proven_identifier_allowlist=sorted(identifiers),redaction_rule='43-character URL-safe synthetic session candidates, excluding tracked path identifiers and AST-proven source identifiers; static source and PNG untouched',limits=['No PG data directories exported','Private full process argv inventory retained privately with SHA in process-observation.json; not exported','Ordinary positive path starts with explicit owned synthetic existing preparation/Run assignment/OFFER fixture before server start','Only named accepted-tests windows count; development/main first attempt failures remain failures','Independent77 overlaps final161, never add','No Windows/formal AT/real business/model evidence'])
(dest/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(pairs=len(records),redactions=manifest['redactions'])))
