from pathlib import Path
from collections import Counter
from copy import deepcopy
import hashlib,json,subprocess,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/dispatch-accept-recovery-20261018';labels=['final-v2-A','final-v2-B']
plan=json.load(open(r/'final-v2-plan.json'));source=plan['source_sha'];results=[];all_ids=[];modules=Counter();combined=E.Element('testsuites',source_sha=source);manifests=[]
def ids(tree):return [c.get('classname').replace('.','/')+'.py::'+c.get('name') for c in tree.findall('.//testcase') if c.get('classname') and c.get('name')]
for label in labels:
 result=json.load(open(r/(label+'-result.json')));assert result['source_sha']==source and result['exit_code']==0 and not any(result[k] for k in ['failures','errors','skipped','input_drift'])
 tree=E.parse(r/(label+'.xml'));test_ids=ids(tree);assert len(test_ids)==result['testcases']==result['unique'];assert not set(all_ids)&set(test_ids);all_ids+=test_ids;results.append(result)
 for suite in tree.getroot():combined.append(deepcopy(suite))
 for c in tree.findall('.//testcase'):modules[c.get('classname').removeprefix('tests.')]+=1
 inputs=json.load(open(r/(label+'-inputs.json')));assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in inputs.items());manifests.append(inputs)
assert manifests[0]==manifests[1]
collection=json.load(open(r/'final-v2-node-collection.json'));assert set(all_ids)==set(collection['test_nodes']) and len(all_ids)==len(set(all_ids))==collection['unique']
old=ids(E.parse(root/'.runtime/ttl-template-resume-20261018/final-pytest.xml'));assert len(old)==296 and set(old)<=set(all_ids)
assert modules['test_dispatch_accept_recovery']==31 and modules['test_dispatch_accept_recovery_offline']==31 and modules['test_dispatch_accept_recovery_browser']==5
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()==source and not subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True).strip()
E.indent(combined);E.ElementTree(combined).write(r/'final-v2-pytest.xml',encoding='utf-8',xml_declaration=True)
summary=dict(source_sha=source,source_tree=subprocess.check_output(['git','rev-parse','HEAD:src'],cwd=root,text=True).strip(),modules=dict(modules),unique=len(all_ids),failures=0,errors=0,skipped=0,labels=labels,input_count=len(manifests[0]),input_drift=[],elapsed_max_seconds=max(x['elapsed_seconds'] for x in results),shard_results=results,old296_reexecuted_all_included=True,new67_already_included=True,collection_missing=[],collection_extra=[],shards_overlap=0,test_nodes=sorted(all_ids),clean_source_window=True)
(r/'final-v2-summary.json').write_text(json.dumps(summary,indent=2)+'\n');(r/'accepted-tests.json').write_text(json.dumps(dict(source_sha=source,labels=labels,unique=len(all_ids),independent_is_overlapping=True),indent=2)+'\n');print({k:v for k,v in summary.items() if k not in ['test_nodes','shard_results','modules']})
