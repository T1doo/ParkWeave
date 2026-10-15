from pathlib import Path
import json,re,xml.etree.ElementTree as ET
p=Path('.runtime/template-local-migration-20261014')
root=ET.parse(p/'final.xml').getroot();items=[]
for c in root.iter('testcase'):
 status='ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS'
 items.append(dict(id=c.get('classname')+'::'+c.get('name'),status=status,seconds=c.get('time')))
counts={k:sum(x['status']==k for x in items) for k in ('PASS','FAIL','ERROR','SKIP')}
window=json.loads((p/'final-window.json').read_text());text=(p/'final.log').read_text()
result=dict(source_sha=window['source_sha'],modules=39,counts=counts,tests=len(items),warnings=int(re.findall(r'(\d+) warnings?',text)[-1]) if re.findall(r'(\d+) warnings?',text) else 0,exit_code=window['exit_code'],elapsed_seconds=window['elapsed_seconds'],manifest_files=window['files'],source_drift=window['source_drift'],test_results=items)
(p/'final-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='test_results'}))
assert window['exit_code']==0 and not window['source_drift'] and not(counts['FAIL'] or counts['ERROR'])

old=json.loads((p/'source87-first-results.json').read_text())
import hashlib,subprocess
from uuid import UUID
prefix='tests.test_template_candidate::test_old_identity_material_and_result_fields_are_forbidden[case_id-'
def normalized(identifier):
    if identifier.startswith(prefix):
        value=identifier[len(prefix):-1]
        assert identifier.endswith(']') and str(UUID(value))==value and UUID(value).version==4
        return prefix+'<per-run-uuid4>]'
    return identifier
old_ids={x['id'] for x in old['test_results']};new_ids={x['id'] for x in items}
old_dynamic=[x for x in old_ids if x.startswith(prefix)];new_dynamic=[x for x in new_ids if x.startswith(prefix)]
assert len(old_dynamic)==len(new_dynamic)==1
old_source=subprocess.check_output(['git','show',old['source_sha']+':tests/test_template_candidate.py'])
new_source=subprocess.check_output(['git','show',result['source_sha']+':tests/test_template_candidate.py'])
assert old_source==new_source and b"('case_id', str(uuid.uuid4()))" in old_source
old_normal={normalized(x) for x in old_ids};new_normal={normalized(x) for x in new_ids}
assert old_normal<=new_normal and len(old_normal)==1350 and len(new_normal)==1355
added=new_normal-old_normal
assert len(added)==5 and all(x.startswith('tests.test_template_migration_event_capacity::') for x in added)
assert len(old_ids&new_ids)==1349
assert all(next(y for y in items if y['id']==x['id'])['status']=='PASS' for x in old['test_results'] if x['status']=='FAIL')
proof=dict(source_sha=result['source_sha'],original_source=old['source_sha'],all_original_test_scope_retained=True,total=1355,original_scope_total=1350,new_capacity_tests=5,exact_original_ids_retained=1349,original_failed=12,all_original_failed_exact_ids_now_pass=True,dynamic_uuid_mapping=[dict(old=old_dynamic[0],new=new_dynamic[0])],unchanged_candidate_test_source_sha256=hashlib.sha256(old_source).hexdigest(),raw_missing=sorted(old_ids-new_ids),raw_added=sorted(new_ids-old_ids),normalization='Only the exact forbidden case_id uuid4 parameter; original raw XML and comparison failure preserved; no test/code/outcome changed.')
(p/'original-failed-test-recheck.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps({k:v for k,v in proof.items() if k not in ('raw_missing','raw_added')}))
