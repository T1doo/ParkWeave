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
assert {x['id'] for x in old['test_results']} <= {x['id'] for x in items}
assert len(items)==1355
assert all(next(y for y in items if y['id']==x['id'])['status']=='PASS' for x in old['test_results'] if x['status']=='FAIL')
(p/'original-failed-test-recheck.json').write_text(json.dumps(dict(source_sha=result['source_sha'],original_source=old['source_sha'],same_test_identifiers=True,total=1355, original_scope_total=1350, new_capacity_tests=5,original_failed=12,all_original_failed_now_pass=True),indent=2)+'\n')
