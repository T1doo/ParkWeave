"""Verify whole-module selections from complete frozen execution windows."""
from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as E
root=Path.cwd();base=root/'.runtime/multifield-source-final';o=root/'.runtime/multifield-source-root'
f=json.loads((o/'freeze.json').read_text());plan=json.loads((o/'planned-regression.json').read_text())
selection=json.loads((o/'selected-windows.json').read_text());nodes=[];modules=[];windows=[]
for entry in selection:
 name=entry['name'];data=json.loads((base/(name+'.json')).read_text());collected=json.loads((base/(name+'-collection.json')).read_text());cases=list(E.parse(base/(name+'.xml')).iter('testcase'))
 assert data['source_sha']==f['source_sha'] and data['collection_junit_exact_match'] and data['unique_junit_nodes']
 assert not data['source_drift'] and not data['all_tracked_drift'] and not data['runner_drift']
 before=json.loads((base/(name+'-all-tracked-before.json')).read_text());after=json.loads((base/(name+'-all-tracked-after.json')).read_text());assert before==after==f['all_tracked_sha256']
 actual=[];statuses={}
 for case in cases:
  bits=case.get('classname','').split('.');i=next(i for i,v in enumerate(bits) if v.startswith('test_'));node='tests/'+bits[i]+'.py::'+'::'.join(bits[i+1:]+[case.get('name')]);actual.append(node)
  statuses[node]='ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
 assert sorted(collected)==sorted(actual) and len(actual)==len(set(actual))
 chosen=entry.get('selected_modules',data['modules']);assert set(chosen)<=set(data['modules'])
 chosen_nodes=[n for n in actual if n.split('::')[0] in chosen]
 assert set(n.split('::')[0] for n in chosen_nodes)==set(chosen) and all(statuses[n]=='PASS' for n in chosen_nodes)
 if set(chosen)!=set(data['modules']):assert entry['reason'] and data['exit_code']!=0
 else:assert data['exit_code']==0
 nodes+=chosen_nodes;modules+=chosen
 windows.append(dict(name=name,raw_counts=data['counts'],selected_modules=chosen,selected_PASS=len(chosen_nodes),excluded_whole_modules=sorted(set(data['modules'])-set(chosen)),reason=entry.get('reason'),xml_sha256=hashlib.sha256((base/(name+'.xml')).read_bytes()).hexdigest()))
expected={m for values in plan['windows'].values() for m in values}
assert len(nodes)==len(set(nodes)) and len(modules)==len(set(modules)) and set(modules)==expected
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==f['source_sha']
assert not subprocess.check_output(['git','status','--porcelain'])
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in f['all_tracked_sha256'].items())
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in f['runner_paths'].items())
b=json.loads((o/'baseline.json').read_text())
prior={k:dict(count=len(b[k]),drift=[p for p,h in b[k].items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]) for k in ['prior_raw_sha256','prior_audit_raw_sha256']}
assert all(not x['drift'] for x in prior.values())
record=dict(status='PASS',source_sha=f['source_sha'],scope='Disjoint complete modules selected only from complete same-source execution windows; raw failed windows, if any, remain preserved',complete_modules=len(modules),unique_testcases=len(nodes),counts=dict(PASS=len(nodes),FAIL=0,ERROR=0,SKIP=0),full_repository_run=False,windows=windows,all_tracked_paths=len(f['all_tracked_sha256']),source_paths=len(f['source_paths']),all_tracked_before_after_exact=True,previous_originals=prior,external_not_run=plan['external_not_run'],blocked_external_modules=plan.get('blocked_external_modules',[]),supplemental_review_not_in_union=True)
(o/'final-regression-verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['status','source_sha','complete_modules','unique_testcases','counts']}))
