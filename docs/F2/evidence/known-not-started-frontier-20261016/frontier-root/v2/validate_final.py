"""Verify actual same-SHA complete windows and prior nodes without migrating scores."""
from pathlib import Path
import hashlib,json,subprocess,re
V=Path('.runtime/frontier-root/v2');freeze=json.loads((V/'freeze.json').read_text());selection=json.loads((V/'final-selection.json').read_text());results=[];nodes=[];modules=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for w in selection:
 name=w['window'];p=V/'final'/(name+'.json');x=json.loads(p.read_text())
 assert x['source_sha']==freeze['source_sha'] and x['modules']==w['modules'],name
 assert x['exit_code']==0 and x['counts']['FAIL']==x['counts']['ERROR']==x['counts']['SKIP']==0,name
 assert not x['source_drift'] and not x['all_tracked_drift'] and not x['runner_drift'],name
 assert x['collection_junit_exact_match'] and x['unique_junit_nodes'],name
 nodes.extend(x['collected_nodes']);modules.extend(x['modules']);results.append(dict(window=name,counts=x['counts'],elapsed_seconds=x['elapsed_seconds'],sha256=sha(p),started_utc=x['started_utc'],finished_utc=x['finished_utc']))
assert len(nodes)==len(set(nodes)) and len(modules)==len(set(modules))==freeze['selected_complete_modules']
assert sorted(modules)==sorted(p for w in json.loads((V/'final-windows.json').read_text()) for p in w['modules'])
oldroot=Path('.runtime/plan-replacement-root/v4');prior_windows=json.loads((oldroot/'final-selection.json').read_text());prior_nodes=[n for w in prior_windows for n in json.loads((oldroot/'final'/(w['window']+'.json')).read_text())['collected_nodes']]
assert len(prior_nodes)==len(set(prior_nodes))==3690
prefix='tests/test_template_candidate.py::test_old_identity_material_and_result_fields_are_forbidden[case_id-'
def canonical(n):
 if n.startswith(prefix):
  assert re.fullmatch(re.escape(prefix)+r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\]',n)
  return prefix+'ORIGINAL_IMPORT_TIME_UUID]'
 return n
assert set(map(canonical,prior_nodes))<=set(map(canonical,nodes))
ci_name=json.loads((V/'ci-final-selection.json').read_text())['window'] if (V/'ci-final-selection.json').exists() else 'ci-metadata-solo'
assert ci_name in ('ci-metadata-solo','ci-metadata-solo-retry01')
ci=json.loads((V/'final'/(ci_name+'.json')).read_text());assert ci['source_sha']==freeze['source_sha'] and ci['exit_code']==0
assert not ci['source_drift'] and not ci['all_tracked_drift'] and not ci['runner_drift']
assert ci['collection_junit_exact_match'] and ci['unique_junit_nodes'];assert ci['counts']==dict(PASS=433,FAIL=0,ERROR=0,SKIP=14)
recovery_name=next(w['window'] for w in selection if w['modules']==['tests/test_service_plan_recovery.py'])
recovery=next(x for x in results if x['window']==recovery_name);assert recovery['counts']==dict(PASS=30,FAIL=0,ERROR=0,SKIP=0)
assert recovery['started_utc']>ci['finished_utc'];assert ci['started_utc']>max(x['finished_utc'] for x in results if x['window']!=recovery_name)
reviewpath=Path('.runtime/frontier-review-v2/frozen-v1/review-result.json');review=json.loads(reviewpath.read_text());assert review['status']=='LIMITED_PASS' and not review['blocking_findings']
assert review['frozen_sha']==freeze['source_sha'] and review['freeze_manifest_sha256']==sha(V/'freeze.json')
assert review['utc']<=ci['started_utc']
for p in (V/'final').glob('*.json'):
 x=json.loads(p.read_text())
 if isinstance(x,dict) and {'source_sha','finished_utc','counts','modules'}<=set(x) and x['source_sha']==freeze['source_sha'] and p.name!=recovery_name+'.json':
  assert x['finished_utc']<=recovery['started_utc'],p
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert head==freeze['source_sha'];assert not subprocess.check_output(['git','status','--porcelain'])
for key in ('source_paths','all_tracked_sha256','runner_paths'):
 for p,h in freeze[key].items():assert sha(p)==h,p
old=json.loads(Path('.runtime/frontier-root/preserved-evidence-union.json').read_text())
for p,h in old.items():assert Path(p).is_file() and sha(p)==h,p
planned_windows=json.loads((V/'final-windows.json').read_text())
assert len(selection)==len(planned_windows)
for selected,planned in zip(selection,planned_windows):
 assert selected['modules']==planned['modules'] and selected['window'] in (planned['window'],planned['window']+'-retry01')
newmods=[p for p in modules if p not in [m for w in prior_windows for m in w['modules']]]
newfeaturemods=[p for p in modules if p.startswith('tests/test_frontier_')]
newnodes=[n for n in nodes if n.split('::')[0] in newfeaturemods]
result=dict(status='LIMITED_PASS_WITH_PROFILE_GAP',source_sha=head,complete_unique_modules=len(modules),unique_main_nodes=len(nodes),main_pass=sum(x['counts']['PASS'] for x in results),main_skip=0,prior_actual_nodes_preserved=3690,prior_complete_modules_preserved=140,new_feature_modules=newfeaturemods,new_feature_passes=len(newnodes),added_direct_modules=[p for p in newmods if p not in newfeaturemods],ci_separate=ci['counts'],ci_actual_window=ci_name,recovery_actual_window=recovery_name,frozen_review_receipt=str(reviewpath),frozen_review_receipt_sha256=sha(reviewpath),all_tracked_paths_unchanged=len(freeze['all_tracked_sha256']),source_paths_unchanged=len(freeze['source_paths']),runner_paths_unchanged=len(freeze['runner_paths']),prior_raw_paths_unchanged=len(old),windows=results,not_run=['original special PG27 profile/role gate','native Windows and its browser','broad browser acceptance','formal AT','real product model B0-B2','production','general protocol migration/backfill or process restart','arbitrary superuser/unregistered invisible DDL protection','tracked schema33 after-accept cancellation guarded by original profile'])
(V/'prior-node-preservation.json').write_text(json.dumps(dict(source_sha=head,prior_source_sha='2dd98b67d52746dcdc3f358d2d60042cbea93909',prior_nodes=len(prior_nodes),all_present=True,exact_import_uuid_function=prefix+'UUID]',prior=[n for n in prior_nodes if canonical(n)!=n],current=[n for n in nodes if canonical(n)!=n]),indent=2)+'\n')
(V/'final-gate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='windows'}))
