from pathlib import Path
from collections import Counter
from copy import deepcopy
import json,xml.etree.ElementTree as E
r=Path('/workspace/ParkWeave/.runtime/dispatch-accept-recovery-20261018');all_ids=[];green=[];failed=[];modules=Counter();results=[];combined=E.Element('testsuites',source_sha='bfb16026a5bcfcdca101a69f357157d5f1c4a490')
def node(c):return c.get('classname').replace('.','/')+'.py::'+c.get('name')
for label in ['final-v2-A','final-v2-B']:
 result=json.load(open(r/(label+'-result.json')));assert result['source_sha']=='bfb16026a5bcfcdca101a69f357157d5f1c4a490' and not result['input_drift'];results.append(result)
 tree=E.parse(r/(label+'.xml'))
 for suite in tree.getroot():combined.append(deepcopy(suite))
 for c in tree.findall('.//testcase'):
  assert c.get('classname') and c.get('name');n=node(c);all_ids.append(n);modules[c.get('classname').removeprefix('tests.')]+=1
  (failed if c.find('failure') is not None or c.find('error') is not None else green).append(n)
collection=json.load(open(r/'final-v2-node-collection.json'))['test_nodes'];assert len(all_ids)==len(set(all_ids))==576 and set(all_ids)==set(collection)
old={node(c) for c in E.parse(r.parent/'ttl-template-resume-20261018/final-pytest.xml').findall('.//testcase')};new={n for n in all_ids if any(n.startswith('tests/'+m+'.py::') for m in ['test_dispatch_accept_recovery','test_dispatch_accept_recovery_offline','test_dispatch_accept_recovery_browser'])}
assert len(old)==296 and old<=set(green) and len(new)==67 and new<=set(green);assert failed==['tests/test_service_plan_recovery.py::test_actual_resource_expiry_during_last_lifecycle_lock_wait_is_read_only']
E.indent(combined);E.ElementTree(combined).write(r/'final-v2-broad-pytest.xml',encoding='utf-8',xml_declaration=True)
result=dict(source_sha='bfb16026a5bcfcdca101a69f357157d5f1c4a490',unique=576,passed=len(green),failures=1,errors=0,skipped=0,failed_nodes=failed,modules=dict(modules),input_count=745,input_drift_at_each_window_end=[],old296_reexecuted_and_all_passed=True,new67_all_passed=True,all_green=False,scope='24 complete modules at bfb; not transferred to the later test-only fixture freeze',shard_results=results)
(r/'final-v2-broad-summary.json').write_text(json.dumps(result,indent=2)+'\n');print({k:v for k,v in result.items() if k not in ['modules','shard_results']})
