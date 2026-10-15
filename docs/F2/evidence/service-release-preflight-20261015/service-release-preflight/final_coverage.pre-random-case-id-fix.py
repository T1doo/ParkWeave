from pathlib import Path
from collections import Counter
import hashlib,json,subprocess,xml.etree.ElementTree as ET
B=Path('.runtime/service-release-preflight');I=Path('.runtime/service-release-preflight-independent');R=Path('.runtime/service-release-preflight-review')
def load(p):return json.loads(p.read_text())
F=load(B/'final-freeze.json');sha=F['source_sha'];windows=[]
def node(c):
 a=c.attrib['classname'].split('.');pos=next(i for i,k in enumerate(a) if k.startswith('test_'))
 return 'tests/'+a[pos]+'.py::'+'::'.join(a[pos+1:]+[c.attrib['name']])
def verify(name,r,collection,xml,result_path,seconds):
 cases=list(ET.parse(xml).iter('testcase'));actual=[node(c) for c in cases]
 assert cases and not any(c.find(k) is not None for c in cases for k in ['failure','error','skipped'])
 assert sorted(actual)==sorted(collection) and len(actual)==len(set(actual))
 assert r['source_sha']==sha and r['exit_code']==0
 windows.append(dict(name=name,source_sha=r['source_sha'],modules=r['modules'],counts=dict(PASS=len(cases),FAIL=0,ERROR=0,SKIP=0),seconds=seconds,nodeids=collection,result_path=str(result_path),junit_path=str(xml),started_utc=r.get('started_utc'),finished_utc=r.get('finished_utc',r.get('ended_utc')),junit_timestamp=next(ET.parse(xml).iter('testsuite')).get('timestamp')))
for name in ['root-1-v1','root-2-v1']:
 p=B/(name+'.json');r=load(p);assert not r['source_drift'] and r['collection_junit_exact_match'] and r['unique_junit_nodes']
 for suffix in ['before','after']:assert load(B/(name+'-'+suffix+'.json'))==F['hashes']
 verify(name,r,load(B/(name+'-collection.json')),B/(name+'.xml'),p,dict(value=r['elapsed_seconds'],kind='runner'))
ip='freeze-'+sha[:7]+'-formal';p=I/(ip+'-result.json');r=load(p)
assert r['head_after']==sha and not r['tracked_changed'] and not r['tracked_status_after'] and r['runner_unchanged'] and r['exact_collection_junit_match'] and r['duplicate_collection_count']==r['duplicate_junit_count']==0
for suffix in ['before','after']:
 m=load(I/(ip+'-'+suffix+'.json'));assert m['head']==sha and all(m['files'][p]==h for p,h in F['hashes'].items())
verify('independent',r,[x['nodeid'] for x in load(I/(ip+'-collection.json'))['items']],I/(ip+'-junit.xml'),p,dict(value=r['junit_seconds'],kind='JUnit'))
rp='extra-v2-'+sha[:8];p=R/(rp+'-result.json');r=load(p)
assert r['head_after']==sha and not r['source_changes'] and r['collection_junit_exact'] and r['alltracked_before_after_equal'] and not r['alltracked_blob_mismatches_after']
for suffix in ['before','after']:
 m=load(R/(rp+'-source-'+suffix+'.json'));assert all(m[p]==h for p,h in F['hashes'].items())
verify('review',r,load(R/(rp+'-collection.json')),R/(rp+'.xml'),p,dict(value=r['elapsed_seconds'],kind='runner',junit=r['junit_seconds']))
allnodes=[n for w in windows for n in w['nodeids']];mods=[m for w in windows for m in w['modules']]
assert len(allnodes)==len(set(allnodes))==2187 and len(mods)==len(set(mods))==67
assert set(mods)==set(load(B/'planned-regression.json')['complete_modules'])
assert sorted(allnodes)==sorted(load(B/'planned-collection.json'))
assert subprocess.check_output(['git','rev-parse','HEAD']).decode().strip()==sha
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
for p,h in F['hashes'].items():
 assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h
 assert hashlib.sha256(subprocess.check_output(['git','show',sha+':'+p])).hexdigest()==h
out=dict(status='PASS_FOUR_DISJOINT_COMPLETE_MODULE_WINDOWS_SAME_SHA',source_sha=sha,complete_modules=len(mods),unique_tests=len(allnodes),same_SHA_all_windows=True,whole_repository_run=False,windows=windows,tracked_source_paths=len(F['hashes']),source_drift=[],previous_test_scores_reused=False,real_model_calls=0,Windows='NOT_RUN',real_browser='NOT_RUN',formal_AT='NOT_RUN',production='NOT_RUN')
(B/'final-coverage.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='windows'}))
