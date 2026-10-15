from pathlib import Path
from collections import Counter
import hashlib,json,re,xml.etree.ElementTree as ET
root=Path.cwd();base=root/'.runtime/template-structure-migration-20261015'
old=root/'.runtime/template-local-migration-20261014/final.xml';new=base/'final.xml'
name='test_old_identity_material_and_result_fields_are_forbidden'
expected_hash='64b56c0c2fdbfc3b9fb5fb4fd14ccb656d6bd955d433fc2630acfb8a5f4f4e83'
assert hashlib.sha256((root/'tests/test_template_candidate.py').read_bytes()).hexdigest()==expected_hash
uuid_re=re.compile(r'(?<=\[case_id-)[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?=\])')
def cases(path):
 result={};normalizations=[]
 for e in ET.parse(path).getroot().iter('testcase'):
  original=(e.attrib['classname'],e.attrib['name']);key=original
  if key[0]=='tests.test_template_candidate' and key[1].startswith(name+'[case_id-'):
   normalized,count=uuid_re.subn('<runtime-case-id>',key[1]);assert count==1;key=(key[0],normalized);normalizations.append(original)
  assert key not in result,key
  result[key]=dict(status='FAIL' if e.find('failure') is not None else 'ERROR' if e.find('error') is not None else 'SKIP' if e.find('skipped') is not None else 'PASS')
 return result,normalizations
before,bnorm=cases(old);after,anorm=cases(new)
missing=sorted(before.keys()-after.keys());old_changed=[k for k in before if k in after and after[k]['status']!='PASS'];extra=sorted(after.keys()-before.keys())
report=dict(source_sha=(base/'source-sha.txt').read_text().strip(),baseline_cases=len(before),final_cases=len(after),missing=missing,baseline_cases_not_pass=old_changed,new_cases=len(extra),new_case_ids=extra,normalization=dict(unchanged_original_source_sha256=expected_hash,function=name,field='case_id',old_ids=bnorm,new_ids=anorm,only_runtime_uuid_normalized=True),statuses=dict(Counter(v['status'] for v in after.values())))
(base/'scope-comparison.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in {'new_case_ids','normalization'}}));assert not missing and not old_changed and all(v['status']=='PASS' for v in after.values())
