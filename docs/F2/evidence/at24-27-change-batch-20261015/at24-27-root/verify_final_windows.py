from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as ET
root=Path.cwd(); base=root/'.runtime/at24-27-root'
freeze=json.loads((base/'final-freeze-v2.json').read_text())
windows=[base/'root-1-v2.json',base/'root-2-v2.json',root/'.runtime/at24-27-independent/independent-v3.json',root/'.runtime/at24-27-review-v2/freeze-5a7eee8-extra.json',root/'.runtime/at24-27-common-clear-regression/common-clear-v1.json']
all_nodes=[];all_modules=[];results=[]
for p in windows:
 d=json.loads(p.read_text()); print(p.name,list(d))
 assert d['source_sha']==freeze['source_sha']
 assert d['exit_code']==0 and d['counts'].get('FAIL',0)==d['counts'].get('ERROR',0)==d['counts'].get('SKIP',0)==0
 assert not d['source_drift'] and d['collection_junit_exact_match'] and d['unique_junit_nodes']
 nodes=d['collected_nodes']; assert len(nodes)==d['counts']['PASS']
 all_nodes.extend(nodes);all_modules.extend(d['modules'])
 results.append({'path':str(p.relative_to(root)),'source_sha':d['source_sha'],'counts':d['counts'],'modules':len(d['modules']),'collected_nodes':len(nodes),'elapsed_seconds':d['elapsed_seconds'],'collection_junit_exact_match':True,'source_drift':[],'manifest_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
assert len(all_nodes)==len(set(all_nodes))
assert len(all_modules)==len(set(all_modules))
planned=json.loads((base/'planned-regression-expanded.json').read_text())['complete_modules'];assert set(planned)==set(all_modules)
tracked=freeze['all_tracked_sha256']; drift=[p for p,h in tracked.items() if not Path(p).is_file() or hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h];assert not drift,drift
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==freeze['source_sha']
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
provenance=json.loads((base/'root-v2-runner-provenance.json').read_text())
assert provenance['source_sha']==freeze['source_sha']
for kind in ['runner','plugin']:
 assert hashlib.sha256((base/provenance[kind]).read_bytes()).hexdigest()==provenance[kind+'_sha256']
prior=json.loads(Path('docs/F2/evidence/service-release-preflight-20261015/index.json').read_text())
prior_drift=[]
for e in prior['entries']:
 p=Path(e['raw_path'])
 if not p.is_file() or len(p.read_bytes())!=e['raw_bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=e['raw_sha256']:prior_drift.append(e['raw_path'])
assert not prior_drift,prior_drift
(base/'prior-evidence-preservation.json').write_text(json.dumps({'status':'PASS','prior_archive_source_sha':prior['source_sha'],'raw_entries':len(prior['entries']),'original_raw_drift':prior_drift,'current_source_sha':freeze['source_sha']},indent=2)+'\n')
result={'status':'PASS','source_sha':freeze['source_sha'],'complete_modules':len(all_modules),'unique_testcases':len(all_nodes),'counts':{'PASS':len(all_nodes),'FAIL':0,'ERROR':0,'SKIP':0},'full_repository_run':False,'frozen_tracked_paths':len(tracked),'frozen_source_paths':len(freeze['source_paths']),'all_tracked_drift':drift,'window_results':results,'planned_modules_exact':True,'cross_window_module_disjoint':True,'cross_window_testcase_disjoint':True,'all_window_collection_junit_exact':True}
(base/'final-regression-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
