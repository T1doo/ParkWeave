from pathlib import Path
import json,xml.etree.ElementTree as ET
raw=Path('/workspace/ParkWeave/.runtime/service-catalog-query-20261018');f=raw/'frozen-9fd652a2'
result=json.loads((f/'result.json').read_text());nodes=json.loads((f/'collection.json').read_text());calls=[json.loads(l) for l in (f/'calls.jsonl').read_text().splitlines()];xml=ET.parse(f/'results.xml');pre=json.loads((f/'shared-before.json').read_text())
assert len(nodes)==len(set(nodes))==15 and len(xml.findall('.//testcase'))==15
assert not any(xml.findall('.//'+k) for k in ['error','failure','skipped'])
assert {n.get('classname').replace('.','/')+'.py::'+n.get('name') for n in xml.findall('.//testcase')}==set(nodes)
for phase in ['setup','call','teardown']:
 rows=[r for r in calls if r['when']==phase];assert len(rows)==15 and {r['nodeid'] for r in rows}==set(nodes) and all(r['outcome']=='passed' for r in rows)
assert all(json.loads((f/p).read_text())==pre for p in ['mirror-before.json','mirror-after.json','shared-after.json'])
origins=json.loads((f/'module-origins.json').read_text());mirror=Path(result['mirror']);checks={name:dict(within_mirror=v['within_mirror'],matches_input=pre.get(str(Path(v['path']).relative_to(mirror)))==v['sha256']) for name,v in origins.items()};assert all(v['within_mirror'] and v['matches_input'] for v in checks.values())
(raw/'module-source-validation.json').write_text(json.dumps(dict(tested_sha=result['head'],count=len(origins),checks=checks),indent=2)+'\n')
value=dict(tested_sha=result['head'],unique_collection=15,setup_passed=15,call_passed=15,teardown_passed=15,junit_passed=15,failures=0,errors=0,skipped=0,selected_inputs=len(pre),all_shared_and_mirror_pre_post_equal=True,module_origins=len(origins),all_origins_match_mirror_input=True,new_selectors=14,existing_resource_adopt_compatibility_selector=1,old17_or141_matrices_rerun=False,collection=nodes)
(raw/'counting-verification.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({k:v for k,v in value.items() if k!='collection'}))
