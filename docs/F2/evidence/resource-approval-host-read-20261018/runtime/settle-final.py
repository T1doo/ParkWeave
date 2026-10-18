from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/resource-approval-host-read-20261018'
plan=json.loads((r/'final-plan.json').read_text());result=json.loads((r/'final-result.json').read_text());source=plan['source_sha']
assert source=='b963783419624ae5450e7fa3ba0160ca0ce41444' and result['source_sha']==source and result['exit_code']==0
assert not any(result[k] for k in ('failures','errors','skipped','input_drift'))
tree=E.parse(r/'final.xml');cases=tree.findall('.//testcase');nodes=[c.get('classname').replace('.','/')+'.py::'+c.get('name') for c in cases]
assert len(nodes)==len(set(nodes))==190 and set(nodes)==set(plan['test_nodes'])
inputs=json.loads((r/'final-inputs.json').read_text());assert len(inputs)==749 and all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in inputs.items())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==source and not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
new=[x for x in nodes if x.split('::')[0] in plan['modules'][:2]];assert len(new)==len(set(new))==55
contract='docs/F2/ResourceApprovalHostRead-20261018.md';frozen=subprocess.check_output(['git','show',source+':'+contract],cwd=root);assert (root/contract).read_bytes()==frozen
summary=dict(source_sha=source,src_tree=subprocess.check_output(['git','rev-parse','HEAD:src'],cwd=root,text=True).strip(),unique=190,passed=190,failures=0,errors=0,skipped=0,module_counts=plan['module_counts'],labels=['final'],input_count=749,input_drift=[],new55_included=True,new_nodes=sorted(new),test_nodes=sorted(nodes),elapsed_seconds=result['elapsed_seconds'],contract_freeze_sha256=hashlib.sha256(frozen).hexdigest(),clean_source_window=True,scope='8 entire directly related modules; no entire-repository or production/formal AT acceptance')
(r/'final-summary.json').write_text(json.dumps(summary,indent=2)+'\n');(r/'accepted-tests.json').write_text(json.dumps(dict(source_sha=source,unique=190,labels=['final'],independent_overlaps=True),indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ('test_nodes','new_nodes','module_counts')}))
