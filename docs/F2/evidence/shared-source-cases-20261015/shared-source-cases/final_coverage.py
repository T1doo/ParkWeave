from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as ET
B=Path('.runtime/shared-source-cases');I=Path('.runtime/shared-source-cases-independent');R=Path('.runtime/shared-source-cases-review')
F=json.loads((B/'final-freeze.json').read_text());OLD=json.loads((B/'freeze.json').read_text());sha=F['source_sha'];old_sha=OLD['source_sha'];windows=[]
IP='freeze-'+sha[:7]+'-formal'
def load(p):return json.loads(p.read_text())
def node(c):
 a=c.attrib['classname'].split('.');pos=next(i for i,k in enumerate(a) if k.startswith('test_'))
 return 'tests/'+a[pos]+'.py::'+'::'.join(a[pos+1:]+[c.attrib['name']])
def verify(name,result,collection,xml,modules,count,seconds):
 cases=list(ET.parse(xml).iter('testcase'));actual=[node(c) for c in cases]
 assert len(cases)==count and not any(c.find(k) is not None for c in cases for k in ['failure','error','skipped'])
 assert sorted(actual)==sorted(collection) and len(set(actual))==count
 assert result['source_sha']==(sha if name=='independent' else old_sha) and result['exit_code']==0
 windows.append(dict(name=name,source_sha=result['source_sha'],modules=modules,counts=dict(PASS=count,FAIL=0,ERROR=0,SKIP=0),seconds=seconds,nodeids=collection,result_path=str(result_paths[name]),junit_path=str(xml)))
result_paths={n:B/(n+'.json') for n in ['root-1-v1','root-2-v1']}
result_paths['independent']=I/(IP+'-result.json');result_paths['review']=R/'extra-bc4f384f-result.json'
for name in ['root-1-v1','root-2-v1']:
 r=load(result_paths[name]);assert not r['source_drift'] and r['collection_junit_exact_match'] and r['unique_junit_nodes']
 verify(name,r,load(B/(name+'-collection.json')),B/(name+'.xml'),r['modules'],r['counts']['PASS'],dict(value=r['elapsed_seconds'],kind='runner'))
 for suffix in ['before','after']:assert load(B/(name+'-'+suffix+'.json'))==OLD['hashes']
r=load(result_paths['independent']);assert r['head_after']==sha and not r['tracked_changed'] and not r['tracked_status_after'] and r['exact_collection_junit_match'] and r['duplicate_collection_count']==r['duplicate_junit_count']==0
verify('independent',r,[x['nodeid'] for x in load(I/(IP+'-collection.json'))['items']],I/(IP+'-junit.xml'),r['modules'],r['collected'],dict(value=r['junit_seconds'],kind='JUnit'))
r=load(result_paths['review']);assert not r['source_changes'] and r['collection_junit_exact'] and r['alltracked_before_after_equal'] and not r['alltracked_blob_mismatches_after']
verify('review',r,load(R/'extra-bc4f384f-collection.json'),R/'extra-bc4f384f.xml',r['modules'],r['counts']['PASS'],dict(value=r['elapsed_seconds'],kind='runner',junit=r['junit_seconds']))
all_nodes=[n for w in windows for n in w['nodeids']];mods=[m for w in windows for m in w['modules']]
assert len(all_nodes)==len(set(all_nodes)) and len(mods)==len(set(mods))==64
assert set(mods)==set(load(B/'planned-regression.json')['all_modules'])
for p,h in F['hashes'].items():
 assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
 assert hashlib.sha256(subprocess.check_output(['git','show',sha+':'+p])).hexdigest()==h
assert subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()==sha
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
changed=[p for p in F['hashes'] if F['hashes'][p]!=OLD['hashes'][p]]
assert changed==['tests/shared_source_cases_real_html.js'],changed
assert subprocess.check_output(['git','diff','--name-only',old_sha,sha]).decode().splitlines()==changed
references=subprocess.check_output(['rg','-l','shared_source_cases_real_html.js','src','tests','scripts']).decode().splitlines()
assert references==['tests/test_shared_source_cases_independent.py'],references
assert references[0] not in [m for w in windows if w['name']!='independent' for m in w['modules']]
continuity=dict(previous_source_sha=old_sha,final_validation_sha=sha,changed_paths=changed,unchanged_tracked_source_paths=len(F['hashes'])-1,product_src_scripts_pyproject_diff_zero=True,only_direct_driver_reference=references,retained_windows_not_executing_changed_driver=['root-1-v1','root-2-v1','review'],same_SHA_all_windows=False)
(B/'source-continuity.json').write_text(json.dumps(continuity,indent=2)+'\n')
output=dict(status='PASS_FOUR_DISJOINT_COMPLETE_MODULE_WINDOWS',source_sha=sha,complete_modules=len(mods),unique_tests=len(all_nodes),whole_repository_run=False,windows=windows,tracked_source_paths=len(F['hashes']),source_drift=[],source_continuity=continuity,separate_schema_probe_result=str(R/'schema-bc4f384f-result.json'))
(B/'final-coverage.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps({k:v for k,v in output.items() if k!='windows'}))
