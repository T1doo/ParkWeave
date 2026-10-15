from pathlib import Path
from collections import Counter
import json
D=Path('.runtime/shared-source-cases-audit');P='.runtime/shared-source-cases-independent/freeze-731529b-formal';groups={}
for group,manifest,key in [('shared',P+'-own-new-traces.json','path'),('typed',P+'-inherited-typed-traces.json','copied_path')]:
 rows=[]
 for f in json.loads(Path(manifest).read_text())['records']:
  p=Path(f[key])
  if p.name.startswith('oracle-'):rows.extend(json.loads(x) for x in p.read_text().splitlines() if x.strip())
 groups[group]={'records':len(rows),'expected_affected_pairs':sum(len(x['expected_affected']) for x in rows),'actual_affected_pairs':sum(len(x['actual_affected']) for x in rows),'intentional_unknown_or_expansion':sum(bool(x.get('intentional_unknown',x.get('intentional_unknown_expansion'))) for x in rows),'state_subtypes':dict(Counter(x['actual_state'] for x in rows)) if group=='shared' else {},'unknown_scope_count':sum(x.get('unknown_scope') is not None for x in rows),'zero_missed_wrong_wrong_preserved':all(x['missed_count']==x['wrong_count']==x['wrong_preserved_count']==0 for x in rows)}
s,t=groups['shared'],groups['typed']
assert s['records']==12 and s['intentional_unknown_or_expansion']==4 and s['state_subtypes']['UNKNOWN']==2 and s['state_subtypes']['NO_PLAN']==s['state_subtypes']['NO_PREPARATION']==1 and s['expected_affected_pairs']==24
assert t['records']==11 and t['unknown_scope_count']==3 and t['intentional_unknown_or_expansion']==2 and t['expected_affected_pairs']==38
out={'status':'PASS','groups':groups,'unknown_records_not_counted_as_fine_grained_accuracy':True,'reviewer_first_assertion_receipt':'oracle-breakdown-first-assertion.txt','no_source_primary_or_raw_changes':True}
(D/'oracle-unknown-breakdown.json').write_text(json.dumps(out,sort_keys=True,indent=2)+'\n');print(json.dumps(out,sort_keys=True))
