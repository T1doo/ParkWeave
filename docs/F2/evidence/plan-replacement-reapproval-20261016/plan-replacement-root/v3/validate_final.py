from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as ET
r=Path('.runtime/plan-replacement-root/v3');freeze=json.loads((r/'freeze.json').read_text());selection=json.loads((r/'final-selection.json').read_text());results=[];nodes=[];mods=[]
for w in selection:
 name=w['window'];x=json.loads((r/'final'/(name+'.json')).read_text())
 assert x['source_sha']==freeze['source_sha'],name
 assert x['exit_code']==0 and x['counts']['FAIL']==0 and x['counts']['ERROR']==0,name
 assert not x['source_drift'] and not x['all_tracked_drift'] and not x['runner_drift'],name
 assert x['collection_junit_exact_match'] and x['unique_junit_nodes'],name
 assert x['modules']==w['modules'],name
 assert x['counts']['SKIP']==0,('unexpected_main_skip',name)
 nodes.extend(x['collected_nodes']);mods.extend(x['modules']);results.append({'window':name,'counts':x['counts'],'elapsed_seconds':x['elapsed_seconds'],'sha256':hashlib.sha256((r/'final'/(name+'.json')).read_bytes()).hexdigest()})
assert len(nodes)==len(set(nodes));assert len(mods)==len(set(mods))==140
planned=[p for w in json.loads((r/'final-windows.json').read_text()) for p in w['modules']];assert sorted(mods)==sorted(planned)
ci=json.loads((r/'final/ci-metadata-solo.json').read_text());assert ci['source_sha']==freeze['source_sha'];assert ci['exit_code']==0 and not ci['source_drift'] and not ci['all_tracked_drift'] and not ci['runner_drift'];assert ci['collection_junit_exact_match'] and ci['unique_junit_nodes'];assert not ci['counts']['FAIL'] and not ci['counts']['ERROR']
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert head==freeze['source_sha'];assert not subprocess.check_output(['git','status','--porcelain','--','src','tests','scripts','pyproject.toml'])
for path,sha in freeze['all_tracked_sha256'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,path
for path,sha in freeze['runner_paths'].items():assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==sha,path
old=json.loads((r.parent/'preserved-evidence-union.json').read_text());assert all(Path(p).is_file() and hashlib.sha256(Path(p).read_bytes()).hexdigest()==sha for p,sha in old.items())
review=json.loads(Path('.runtime/plan-replacement-root/v3/frozen-review/review-result.json').read_text())
assert review['frozen_sha']==head and review['status']=='LIMITED_PASS' and not review['blocking_findings'] and review['before_after_equal']
assert review['product_diff_from_eaa_empty'] and review['before_matches_freeze'] and review['pure_exit_code']==0 and review['pure_protocol_cases']==15 and review['client_exit_code']==0 and review['client_passed']==11
assert review['freeze_manifest_sha256']==hashlib.sha256((r/'freeze.json').read_bytes()).hexdigest()
result={'status':'LIMITED_PASS_WITH_PROFILE_GAP','source_sha':head,'complete_unique_modules':len(mods),'unique_main_nodes':len(nodes),'main_pass':sum(w['counts']['PASS'] for w in results),'main_skip':0,'ci_separate':ci['counts'],'frozen_review':review,'all_tracked_paths_unchanged':len(freeze['all_tracked_sha256']),'source_paths_unchanged':len(freeze['source_paths']),'runner_paths_unchanged':len(freeze['runner_paths']),'prior_raw_paths_unchanged':len(old),'windows':results,'not_run':['original special PG27 separate profile/role gate','Windows native and its browser','formal AT','real product model','production','general unfinished or unknown in-flight plan replacement','actual template upgrade after consumption historical read']}
# All unchanged prior modules must retain their actual identities. The one
# original import-time uuid4 parameter is normalized only at its exact function.
import re
prior_gate=json.loads(Path('.runtime/plan-reapproval-root/v2/final-regression-verification.json').read_text())
prior_nodes=[n for w in prior_gate['windows'].values() for n in json.loads(Path(w['receipt']).read_text())['collected_nodes']]
def canonical(n):
 prefix='tests/test_template_candidate.py::test_old_identity_material_and_result_fields_are_forbidden[case_id-'
 if n.startswith(prefix):
  assert re.fullmatch(re.escape(prefix)+r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\]',n)
  return prefix+'ORIGINAL_IMPORT_TIME_UUID]'
 return n
assert len(prior_nodes)==len(set(prior_nodes))==3642
assert set(map(canonical,prior_nodes))<=set(map(canonical,nodes))
result['prior_actual_nodes_preserved']=len(prior_nodes)
result['import_uuid_normalization']={'exact_function':'test_template_candidate.py::test_old_identity_material_and_result_fields_are_forbidden[case_id-UUID]','prior':[n for n in prior_nodes if canonical(n)!=n],'current':[n for n in nodes if canonical(n)!=n]}
(r/'prior-node-preservation.json').write_text(json.dumps({'prior_source_sha':prior_gate['source_sha'],'source_sha':head,'prior_nodes':len(prior_nodes),'all_present_after_exact_one_function_uuid_normalization':True,'normalization':result['import_uuid_normalization']},indent=2)+'\n')
(r/'final-gate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('windows','frozen_review')}))
