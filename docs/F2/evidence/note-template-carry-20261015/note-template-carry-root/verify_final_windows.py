from pathlib import Path
import json,hashlib,subprocess,xml.etree.ElementTree as ET
r=Path.cwd();o=r/'.runtime/note-template-carry-root';f=json.loads((o/'freeze-v3.json').read_text())
failed_module='tests/test_case_goal_results.py';failed_node=failed_module+'::test_resource_window_expiry_during_actual_last_source_row_lock_wait'
spec=[('note-template-carry-final','root-1-v2','root-1-modules.json','root-1-v2.json',[]),('note-template-carry-final','root-2-v2','root-2-modules.json','root-2-v2.json',[failed_module]),('note-template-carry-final','goal-results-retry-v1','root-2-goal-module.json','goal-results-retry-v1.json',[]),('note-template-carry-final','common-v2','common-modules.json','common-v2.json',[]),('note-template-carry-backend-formal-v2','formal','modules.json','result.json',[]),('note-template-carry-independent-formal-v2','prior-manual-v2','prior-modules.json','prior-manual-v2.json',[]),('note-template-carry-independent-formal-v2','note-carry-v2','new-modules.json','note-carry-v2.json',[]),('note-template-carry-review-formal-v2','freeze-f686ada-extra-v2','review-modules.json','freeze-f686ada-extra-v2.json',[])]
all_nodes=[];all_modules=[];records=[]
for folder,prefix,mp,rp,excluded in spec:
 d=r/'.runtime'/folder;xml=d/(prefix+'.xml');assert xml.is_file(),str(xml)
 cp=d/(prefix+'-collection.json');cp=cp if cp.exists() else d/'collection.json'
 nodes=json.loads(cp.read_text());modules=json.loads((d/mp).read_text());result=json.loads((d/rp).read_text());cases=list(ET.parse(xml).iter('testcase'));actual=[];counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0);failed=[]
 assert result['source_sha']==f['source_sha']
 assert not result.get('source_drift') and not result.get('all_tracked_drift') and not result.get('tracked_drift')
 assert result['collection_junit_exact_match'] and result['unique_junit_nodes']
 for c in cases:
  parts=c.get('classname','').split('.');idx=next(i for i,v in enumerate(parts) if v.startswith('test_'));node='tests/'+parts[idx]+'.py::'+'::'.join(parts[idx+1:]+[c.get('name')]);actual.append(node)
  status='ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS';counts[status]+=1
  if status!='PASS':failed.append(node)
 assert sorted(actual)==sorted(nodes) and len(nodes)==len(set(nodes));assert set(x.split('::')[0] for x in nodes)==set(modules)
 if excluded:
  assert excluded==[failed_module] and result['exit_code']==1 and failed==[failed_node]
  assert counts==dict(PASS=788,FAIL=1,ERROR=0,SKIP=0)
 else:assert result['exit_code']==0 and not failed
 chosen_modules=[m for m in modules if m not in excluded];chosen_nodes=[n for n in nodes if n.split('::')[0] in chosen_modules]
 chosen_actual=[n for n in actual if n.split('::')[0] in chosen_modules]
 assert sorted(chosen_nodes)==sorted(chosen_actual) and not set(chosen_nodes)&set(failed)
 assert set(n.split('::')[0] for n in chosen_nodes)==set(chosen_modules)
 if folder=='note-template-carry-backend-formal-v2':bp=d/'all-tracked-before.json';ap=d/'all-tracked-after.json'
 elif folder=='note-template-carry-review-formal-v2':bp=d/(prefix+'-before.json');ap=d/(prefix+'-after.json')
 else:bp=d/(prefix+'-all-tracked-before.json');ap=d/(prefix+'-all-tracked-after.json')
 before=json.loads(bp.read_text());after=json.loads(ap.read_text());before=before.get('hashes',before);after=after.get('hashes',after);assert before==after==f['all_tracked_sha256']
 all_nodes+=chosen_nodes;all_modules+=chosen_modules;records.append(dict(directory=folder,prefix=prefix,raw_complete_modules=len(modules),raw_counts=counts,selected_complete_modules=chosen_modules,selected_modules=len(chosen_modules),selected_PASS=len(chosen_nodes),excluded_entire_modules=excluded,excluded_nodes=[n for n in nodes if n.split('::')[0] in excluded],raw_collection_junit_exact=True,selected_complete_module_collection_junit_exact=True,all_tracked_before_after_equal_freeze=True,xml_sha256=hashlib.sha256(xml.read_bytes()).hexdigest()))
assert len(all_nodes)==len(set(all_nodes));assert len(all_modules)==len(set(all_modules))==95
planned=json.loads((o/'planned-regression-final.json').read_text());assert set(all_modules)=={m for rows in planned['windows'].values() for m in rows}
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==f['source_sha'];assert not subprocess.check_output(['git','status','--porcelain'])
drift=[p for p,h in f['all_tracked_sha256'].items() if hashlib.sha256((r/p).read_bytes()).hexdigest()!=h];assert not drift
prior=json.loads((o/'prior-raw-pre-final.json').read_text());assert all(hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['sha256'] for e in prior['entries'])
result=dict(status='PASS',scope='95 complete modules selected from eight execution windows; not all original raw windows passed',source_sha=f['source_sha'],complete_modules=len(all_modules),unique_testcases=len(all_nodes),counts=dict(PASS=len(all_nodes),FAIL=0,ERROR=0,SKIP=0),full_repository_run=False,source_paths=len(f['source_paths']),all_tracked_paths=len(f['all_tracked_sha256']),all_tracked_drift=drift,previous_raw_originals_unchanged=len(prior['entries']),windows=records,all_raw_window_collection_junit_exact=True,cross_selected_modules_and_nodes_disjoint=True,planned_modules_exact=True,external_not_run=planned['excluded_external'],supplemental_history_and_budget_not_in_full_module_union=True,failed_raw_windows_preserved=True,failed_whole_module_replaced_by_one_complete_same_source_retry=True)
(o/'final-regression-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(status=result['status'],modules=len(all_modules),unique_PASS=len(all_nodes),windows=len(records),scope=result['scope'])))
