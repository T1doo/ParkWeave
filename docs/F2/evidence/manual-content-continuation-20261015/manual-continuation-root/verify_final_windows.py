from pathlib import Path
import json,hashlib,subprocess,xml.etree.ElementTree as ET
r=Path.cwd();o=r/'.runtime/manual-continuation-root';f=json.loads((o/'freeze-v2.json').read_text());spec=[('manual-continuation-final','root-1-v2','root-1-modules.json'),('manual-continuation-final','root-2-v2','root-2-modules.json'),('manual-continuation-final','common-v3','common-modules.json'),('manual-continuation-backend-formal-v2','formal','modules.json'),('manual-continuation-independent-formal-v2','manual-independent-v2','modules.json'),('manual-continuation-review-formal-v2','freeze-14bc83f-extra-v2','review-modules.json')]
all_nodes=[];all_modules=[];records=[]
for folder,prefix,mp in spec:
 d=r/'.runtime'/folder;xml=d/(prefix+'.xml');assert xml.is_file(),str(xml)
 nodes=json.loads((d/(prefix+'-collection.json') if (d/(prefix+'-collection.json')).exists() else d/'collection.json').read_text());modules=json.loads((d/mp).read_text());cases=list(ET.parse(xml).iter('testcase'));actual=[]
 for c in cases:
  assert c.find('failure') is None and c.find('error') is None and c.find('skipped') is None,(folder,c.attrib)
  parts=c.get('classname','').split('.');idx=next(i for i,v in enumerate(parts) if v.startswith('test_'));actual.append('tests/'+parts[idx]+'.py::'+'::'.join(parts[idx+1:]+[c.get('name')]))
 assert sorted(actual)==sorted(nodes) and len(nodes)==len(set(nodes));assert set(x.split('::')[0] for x in nodes)==set(modules)
 all_nodes+=nodes;all_modules+=modules;records.append(dict(directory=folder,prefix=prefix,modules=len(modules),PASS=len(nodes),collection_junit_exact=True,xml_sha256=hashlib.sha256(xml.read_bytes()).hexdigest()))
assert len(all_nodes)==len(set(all_nodes));assert len(all_modules)==len(set(all_modules))==92
planned=json.loads((o/'planned-regression-final.json').read_text());assert set(all_modules)=={m for rows in planned['windows'].values() for m in rows}
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==f['source_sha'];assert not subprocess.check_output(['git','status','--porcelain'])
drift=[p for p,h in f['all_tracked_sha256'].items() if hashlib.sha256((r/p).read_bytes()).hexdigest()!=h];assert not drift
prior=json.loads((o/'prior-raw-preservation.json').read_text());assert all(hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['sha256'] for e in prior['entries'])
result=dict(status='PASS',source_sha=f['source_sha'],complete_modules=len(all_modules),unique_testcases=len(all_nodes),counts=dict(PASS=len(all_nodes),FAIL=0,ERROR=0,SKIP=0),full_repository_run=False,source_paths=len(f['source_paths']),all_tracked_paths=len(f['all_tracked_sha256']),all_tracked_drift=drift,previous_raw_originals_unchanged=len(prior['entries']),windows=records,all_window_collection_junit_exact=True,cross_window_modules_and_nodes_disjoint=True,planned_modules_exact=True)
(o/'final-regression-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
