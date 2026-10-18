from pathlib import Path
import json,xml.etree.ElementTree as ET
raw=Path('/workspace/ParkWeave/.runtime/ordinary-case-step-20261018');f=raw/'frozen-954825ef'
result=json.loads((f/'result.json').read_text());nodes=json.loads((f/'collection.json').read_text());calls=[json.loads(l) for l in (f/'calls.jsonl').read_text().splitlines()];xml=ET.parse(f/'results.xml');pre=json.loads((f/'shared-before.json').read_text());n=len(nodes)
assert result['head']=='954825efb66d16f7e41087e1c108b45042732703' and result['exit_code']==0
assert n==len(set(nodes))==len(xml.findall('.//testcase'))==48
assert not any(xml.findall('.//'+k) for k in ['error','failure','skipped'])
assert {t.get('classname').replace('.','/')+'.py::'+t.get('name') for t in xml.findall('.//testcase')}==set(nodes)
for phase in ['setup','call','teardown']:
 rows=[r for r in calls if r['when']==phase];assert len(rows)==n and {r['nodeid'] for r in rows}==set(nodes) and all(r['outcome']=='passed' for r in rows)
assert all(json.loads((f/p).read_text())==pre for p in ['mirror-before.json','mirror-after.json','shared-after.json'])
origins=json.loads((f/'module-origins.json').read_text());mirror=Path(result['mirror']);checks={name:dict(within_mirror=v['within_mirror'],matches_input=pre.get(str(Path(v['path']).relative_to(mirror)))==v['sha256']) for name,v in origins.items()};assert all(v['within_mirror'] and v['matches_input'] for v in checks.values())
(raw/'module-source-validation.json').write_text(json.dumps(dict(tested_sha=result['head'],count=len(origins),checks=checks),indent=2)+'\n')
value=dict(tested_sha=result['head'],unique_collection=n,setup_passed=n,call_passed=n,teardown_passed=n,junit_passed=n,failures=0,errors=0,skipped=0,selected_inputs=len(pre),all_shared_and_mirror_pre_post_equal=True,module_origins=len(origins),all_origins_match_mirror_input=True,new_selectors=sum(x.startswith(('tests/test_ordinary_case_steps.py::','tests/test_ordinary_case_step_process.py::')) for x in nodes),old_selectors=sum(not x.startswith(('tests/test_ordinary_case_steps.py::','tests/test_ordinary_case_step_process.py::')) for x in nodes),collection=nodes)
(raw/'counting-verification.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({k:v for k,v in value.items() if k!='collection'}))
