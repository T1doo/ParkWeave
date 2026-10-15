from pathlib import Path
import subprocess,sys,time,json,hashlib,xml.etree.ElementTree as ET
root=Path.cwd();base=root/'.runtime/source-adoption';prefix='delta-4c163fe';source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert source=='4c163fe23d8a841ece7b796e40e35511d70a0797'
assert not subprocess.check_output(['git','status','--porcelain','--','src','tests','scripts','pyproject.toml'])
modules=['tests/test_'+name+'.py' for name in ['ci_diagnostics','summary_publication','safe_annotations','regression_shards','minimal_observations','lifecycle_diagnostics','windows_ci_preparation','ci_cleanup']]
paths=[p for p in subprocess.check_output(['git','ls-files','-z','--','src','tests','scripts','pyproject.toml']).decode().split('\0') if p]
def manifest():return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
before=manifest();(base/(prefix+'-before.json')).write_text(json.dumps(before,indent=2)+'\n')
args=[sys.executable,'-m','pytest','-q','-p','capture_collection',*modules,'--junitxml='+str(base/(prefix+'.xml'))]
start=time.monotonic()
with (base/(prefix+'.log')).open('w') as log:code=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT).returncode
after=manifest();(base/(prefix+'-after.json')).write_text(json.dumps(after,indent=2)+'\n');cases=list(ET.parse(base/(prefix+'.xml')).iter('testcase'));counts={k:0 for k in ['PASS','FAIL','ERROR','SKIP']}
for c in cases:counts['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
nodes=json.loads((base/(prefix+'-same-run-collection.json')).read_text())
def node_id(case):
    parts=case.get('classname').split('.')
    pos=next(i for i,v in enumerate(parts) if v.startswith('test_'))
    return 'tests/'+parts[pos]+'.py::'+'::'.join(parts[pos+1:]+[case.get('name')])
actual=[node_id(c) for c in cases]
assert sorted(nodes)==sorted(actual) and len(set(actual))==len(actual)
changed=subprocess.check_output(['git','diff','--name-only','6b8da028182d9b4ce35996eaaef2e6a78cff0666',source,'--','src','tests','scripts','pyproject.toml'],text=True).splitlines()
record=dict(source_sha=source,base_business_execution_sha='6b8da028182d9b4ce35996eaaef2e6a78cff0666',argv=args,modules=modules,exit_code=code,elapsed_seconds=time.monotonic()-start,counts=counts,tracked_source_paths=len(paths),source_drift=[p for p in paths if before[p]!=after[p]],collected_nodes=nodes,collection_junit_exact_match=True,testcase_keys=[dict(classname=c.get('classname'),name=c.get('name')) for c in cases],changed_since_business_window=changed,all_src_bytes_unchanged=not subprocess.check_output(['git','diff','6b8da028',source,'--','src']))
(base/(prefix+'.json')).write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in ['argv','modules','collected_nodes','testcase_keys']}));sys.exit(code)
