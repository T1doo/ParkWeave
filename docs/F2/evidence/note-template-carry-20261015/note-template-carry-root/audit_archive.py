from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET,ast
from fast_known_redaction import KnownTokenRedactor
from export_archive import private_values
root=Path.cwd();out=root/'docs/F2/evidence/note-template-carry-20261015';index=json.loads((out/'index.json').read_text());matcher=KnownTokenRedactor(private_values());structured={'.json':0,'.jsonl':0,'.xml':0,'.py':0};raw_bytes=export_bytes=0
for e in index['entries']:
 raw=(root/e['raw_path']).read_bytes();data=(root/e['export_path']).read_bytes()
 assert len(raw)==e['raw_bytes'] and hashlib.sha256(raw).hexdigest()==e['raw_sha256']
 assert len(data)==e['export_bytes'] and hashlib.sha256(data).hexdigest()==e['export_sha256']
 assert not matcher.has_residual(data.decode())
 suffix=Path(e['export_path']).suffix
 if suffix=='.json':json.loads(data)
 elif suffix=='.jsonl':
  for line in data.splitlines():
   if line.strip():json.loads(line)
 elif suffix=='.xml':ET.fromstring(data)
 elif suffix=='.py':ast.parse(data)
 if suffix in structured:structured[suffix]+=1
 raw_bytes+=len(raw);export_bytes+=len(data)
result={'status':'ROOT_EXPORT_CHECKPOINT_PASS_PENDING_INDEPENDENT_AUDIT','source_sha':index['source_sha'],'entries':len(index['entries']),'raw_bytes':raw_bytes,'export_bytes':export_bytes,'known_synthetic_values':len(private_values()),'known_synthetic_residuals':0,'raw_export_hash_and_size_exact':True,'raw_originals_unchanged':True,'structured_parse':structured,'redactions':{k:sum(e['redactions'][k] for e in index['entries']) for k in ['exact_private_value','fixture_repr_line']},'independent_final_gate':'../note-template-carry-audit-20261015/final-gate.json','historical_checkpoint_not_final_independent_verdict':True,'shared_helper_provenance':'KnownTokenRedactor shared helper; this root check is not independent reconstruction.'}
(out/'audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
