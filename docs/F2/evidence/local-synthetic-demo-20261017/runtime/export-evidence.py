"""Export only closed logs/metadata and selected actual test outputs."""
from pathlib import Path
import hashlib,json,re,shutil,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');r=root/'.runtime/local-synthetic-demo'
closed=json.loads((r/'final-validation.json').read_text());assert closed['exit_code']==0 and not closed['input_drift']
http=json.loads((r/'ordinary-http-validation.json').read_text());assert http['exit_code']==0 and not http['input_drift']
final_cases=list(ET.parse(r/'final-pytest.xml').getroot().iter('testcase'))
assert len(final_cases)==317 and len({(c.attrib['classname'],c.attrib['name']) for c in final_cases})==317
assert not any(c.find(k) is not None for c in final_cases for k in ('failure','error','skipped'))
stage=r/'export-final';stage.mkdir(exist_ok=False)
selected=[]
for p in sorted(r.iterdir()):
 if p.is_file() and p.suffix in ('.json','.xml','.log','.py','.sh','.stdout','.stderr','.transcribed') and p.name!='report-draft.md':
  selected.append((p,Path('runtime')/p.name))
for name in ('final-cwd-v2','final-cwd-v3','legacy-target-cwd'):
 for p in sorted((r/name/'.runtime').rglob('*.json')):
  selected.append((p,Path('artifacts')/name/p.relative_to(r/name/'.runtime')))
inv=json.loads((r/'final-invocation.json').read_text());base=Path(next(x.split('=',1)[1] for x in inv['argv'] if x.startswith('--basetemp=')))
for relative in ('test_ordinary_factory_original0/actual-ordinary-demo-chain.json',
 'test_ordinary_subprocess_chrom0/browser-proof.json',
 'test_ordinary_subprocess_chrom0/demo-selected-1200.png',
 'test_ordinary_subprocess_chrom0/demo-selected-390.png',
 'test_ordinary_subprocess_chrom0/demo-selected-320.png',
 'test_ordinary_subprocess_chrom0/first/ordinary-api.log',
 'test_ordinary_subprocess_chrom0/restart/ordinary-api.log'):
 p=base/relative;assert p.is_file(),str(p);selected.append((p,Path('artifacts/final')/relative))
http_base=Path(http['basetemp'])
for p in sorted(http_base.rglob('*')):
 if p.is_file() and p.name in ('actual-http-full-chain.json','actual-ordinary-demo-chain.json','ordinary-api.log'):
  selected.append((p,Path('artifacts/http')/p.relative_to(http_base)))
assert any(p.name=='actual-http-full-chain.json' for p,_ in selected)
rows=[]
for source,target in selected:
 raw=source.read_bytes();result=raw;redactions=0
 if source.suffix!='.png':
  text=raw.decode('utf-8')
  # Temporary synthetic session strings only. Original private bytes remain.
  patterns=[r"(Bearer )[A-Za-z0-9_-]{40,}",r"((?:'|\")(?:(?:prep-specialist-)?fixture-[abc]|executor-[abc])(?:'|\"):\s*(?:'|\"))[A-Za-z0-9_-]{40,}"]
  for pattern in patterns:
   text,n=re.subn(pattern,lambda m:m.group(1)+'SYNTHETIC_SESSION_REDACTED',text);redactions+=n
  result=text.encode('utf-8')
 destination=stage/target;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(result)
 assert source.read_bytes()==raw
 rows.append(dict(raw_path=str(source),public_path=target.as_posix(),raw_sha256=hashlib.sha256(raw).hexdigest(),
  public_sha256=hashlib.sha256(result).hexdigest(),raw_bytes=len(raw),public_bytes=len(result),temporary_synthetic_session_redactions=redactions))
for row in rows:
 assert hashlib.sha256(Path(row['raw_path']).read_bytes()).hexdigest()==row['raw_sha256']
 assert hashlib.sha256((stage/row['public_path']).read_bytes()).hexdigest()==row['public_sha256']
 if row['public_path'].endswith('.json'):json.loads((stage/row['public_path']).read_text())
 if row['public_path'].endswith('.xml'):ET.parse(stage/row['public_path'])
manifest=dict(scope='ROOT_EXPORT_OF_CLOSED_LOGS_METADATA_AND_SELECTED_OUTPUTS',source_sha=closed['source_sha'],
 suite_unique_tests=317,new_tests_included=27,ordinary_http_probe='separate overlapping full-chain transport probe; not added',
 helper_records='root transcribed helper outputs and SHA-verified decoded commands, not root raw execution',
 inherited_evidence_drift=0,rows=rows)
(stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
summary=dict(pairs=len(rows),temporary_synthetic_session_redactions=sum(v['temporary_synthetic_session_redactions'] for v in rows),
 json_files=sum(v['public_path'].endswith('.json') for v in rows),xml_files=sum(v['public_path'].endswith('.xml') for v in rows),
 png_files=sum(v['public_path'].endswith('.png') for v in rows),all_exported_pairs_rehashed=True)
(r/'export-validation.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary))
