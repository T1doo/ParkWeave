from pathlib import Path
import hashlib,json,subprocess,xml.etree.ElementTree as ET,datetime
root=Path.cwd();base=root/'.runtime/typed-source-impact';freeze=json.loads((base/'freeze.json').read_text());sha=freeze['source_sha']
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==sha
assert not subprocess.check_output(['git','status','--porcelain'])
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in freeze['files'].items())
windows=[('root-1',base/'root-1-v1.json',base/'root-1-v1.xml',base/'root-1-v1-collection.json'),('root-2',base/'root-2-v1.json',base/'root-2-v1.xml',base/'root-2-v1-collection.json'),('independent-formal',root/'.runtime/typed-source-impact-independent/freeze-a5d9da2-formal-result.json',root/'.runtime/typed-source-impact-independent/freeze-a5d9da2-formal-junit.xml',root/'.runtime/typed-source-impact-independent/freeze-a5d9da2-formal-collection.json'),('review-extra',root/'.runtime/typed-source-impact-review/extra-a5d9da25-result.json',root/'.runtime/typed-source-impact-review/extra-a5d9da25.xml',root/'.runtime/typed-source-impact-review/extra-a5d9da25-collection.json')]
all_nodes=set();all_modules=set();records=[]
for name,path,xml,collection in windows:
 d=json.loads(path.read_text());assert d['source_sha']==sha and d['exit_code']==0
 cases=list(ET.parse(xml).iter('testcase'));count=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
 for c in cases:count['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
 assert count['FAIL']==count['ERROR']==0
 nodes=json.loads(collection.read_text());nodes=nodes['nodeids'] if isinstance(nodes,dict) else nodes;assert isinstance(nodes,list) and len(nodes)==len(cases)==len(set(nodes))
 def key(c):
  p=c.get('classname').split('.');i=next(i for i,v in enumerate(p) if v.startswith('test_'));return 'tests/'+p[i]+'.py::'+'::'.join(p[i+1:]+[c.get('name')])
 assert sorted(nodes)==sorted(key(c) for c in cases)
 assert not all_nodes.intersection(nodes);assert not all_modules.intersection(d['modules'])
 all_nodes.update(nodes);all_modules.update(d['modules'])
 for field in ('source_drift','tracked_changed','changed_files'):assert not d.get(field)
 records.append(dict(name=name,result=str(path.relative_to(root)),junit=str(xml.relative_to(root)),collection=str(collection.relative_to(root)),counts=count,modules=d['modules'],collection_junit_exact=True,source_sha=sha))
old=set(json.loads((root/'.runtime/source-adoption/root-modules.json').read_text()));extra=set(json.loads((base/'review-extra-modules.json').read_text()));new={'tests/test_typed_source_impact.py','tests/test_typed_source_impact_independent.py'}
assert old|extra|new==all_modules
mixed=json.loads((root/'.runtime/typed-source-impact-independent/freeze-a5d9da2-mixed-result.json').read_text());assert mixed['source_sha']==sha and mixed['tests']==3 and mixed['exit_code']==mixed['failures']==mixed['errors']==mixed['skipped']==0 and not mixed['tracked_changed']
validation=json.loads((root/'.runtime/typed-source-impact-independent/freeze-a5d9da2-formal-validation.json').read_text());oracle=validation['oracle_statistics'];assert all(oracle[k]==0 for k in ('missed_count','wrong_count','wrong_preserved_count'));assert len(validation['full_original_html_runs'])==6
result=dict(source_sha=sha,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),windows=records,complete_module_count=len(all_modules),unique_collected_testcases=len(all_nodes),disjoint_module_windows=True,one_whole_repository_run=False,all_frozen_tracked_source_hashes_match=True,tracked_source_files=len(freeze['files']),separate_mixed_probes=dict(PASS=3,source_sha=sha,script_sha256=mixed['runtime_probe_sha256']),literal_oracle=oracle,full_original_html_runs=validation['full_original_html_runs'],external_gates=dict(Windows='NOT_RUN',real_browser='NOT_RUN',formal_AT='NOT_RUN',real_models=0,production='NOT_RUN',remote_CI='NOT_RUN'))
(base/'final-coverage.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('windows','literal_oracle','full_original_html_runs')}))
