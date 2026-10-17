from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET,datetime
root=Path('/workspace/ParkWeave');p=root/'.runtime/specialist-material-review';out=root/'docs/F2/evidence/specialist-material-review-20261017';pairs=json.loads((out/'public-pairs.json').read_text());names={a['original'] for a in pairs};required={'.runtime/specialist-material-review/'+n for n in ('final-validation.json','failure-ledger.json','continuation-at-final-validation.json','independent-review.json','freeze.json','final-v1-invocation.json','final-v1.xml','final-nodes.json','export-attempt-v1.json')};assert required<=names
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for a in pairs:assert sha(root/a['original'])==a['original_sha256'] and sha(root/a['exported'])==a['exported_sha256']
g=json.loads((out/'gate.json').read_text());v=json.loads((out/'final-validation.json').read_text());l=json.loads((out/'failure-ledger.json').read_text());assert g['final']['unique']==v['unique']==l['windows']['final-v1']['testcases']==267 and len(pairs)==g['public_pairs'] and g['source_drift']==g['inherited_F2_drift']==0
counts={'.json':0,'.xml':0,'.png':0}
for f in out.rglob('*'):
 if not f.is_file():continue
 if f.suffix=='.json':
  def unique(xs):
   d={}
   for k,v in xs:assert k not in d;d[k]=v
   return d
  json.loads(f.read_bytes(),object_pairs_hook=unique,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonJSON constant')))
 elif f.suffix=='.xml':ET.fromstring(f.read_bytes())
 elif f.suffix=='.png':assert f.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
 if f.suffix in counts:counts[f.suffix]+=1
x=dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha=g['source_sha'],export_attempt='v2 sequential after closed validation',first_attempt_preserved='.runtime/specialist-material-review-export-v1',completed_validation_exported=True,required_final_records_sorted=sorted(required),current_original_and_exported_pairs_rehashed=len(pairs),pair_mismatches=0,archive_parse_counts=counts,final_unique=267,source_drift=0,inherited_F2_drift=0,redactions=g['redacted_occurrences'],redacted_files=[a['exported'] for a in pairs if a['redacted_occurrences']],safe_to_continue_to_docs_commit=True)
(p/'post-export-integrity.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps(x))
