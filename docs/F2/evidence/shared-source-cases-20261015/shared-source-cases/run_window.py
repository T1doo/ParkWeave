from pathlib import Path
import hashlib,json,subprocess,time,sys,os,xml.etree.ElementTree as ET
base=Path('.runtime/shared-source-cases');name=sys.argv[1];modules=json.loads(Path(sys.argv[2]).read_text());source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain','--','src','tests','scripts','pyproject.toml']), 'source tree must be committed'
assert all(Path(p).is_file() for p in modules)
paths=[p for p in subprocess.check_output(['git','ls-files','-z','--','src','tests','scripts','pyproject.toml']).decode().split('\0') if p]
def manifest():return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
before=manifest();(base/(name+'-before.json')).write_text(json.dumps(before,indent=2)+'\n')
args=[sys.executable,'-m','pytest','-q','-p','shared_capture',*modules,'--basetemp=/tmp/parkweave-shared-'+name,'--junitxml='+str(base/(name+'.xml'))]
env=dict(os.environ,TYPED_COLLECTION=str(base/(name+'-collection.json')),TYPED_PRIVATE=str(base/('redaction-'+name+'.private.json')));env['PYTHONPATH']=str(base.resolve())+os.pathsep+os.getcwd()+os.pathsep+env.get('PYTHONPATH','')
start=time.monotonic();started=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
with (base/(name+'.log')).open('w') as log:code=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env=env).returncode
after=manifest();(base/(name+'-after.json')).write_text(json.dumps(after,indent=2)+'\n');cases=list(ET.parse(base/(name+'.xml')).iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
for c in cases:counts['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
def node_id(c):
 parts=c.get('classname','').split('.');pos=next((i for i,v in enumerate(parts) if v.startswith('test_')),None)
 return 'UNMATCHED_JUNIT::'+c.get('name','') if pos is None else 'tests/'+parts[pos]+'.py::'+'::'.join(parts[pos+1:]+[c.get('name')])
collected=json.loads((base/(name+'-collection.json')).read_text());actual=[node_id(c) for c in cases]
record=dict(source_sha=source,started_utc=started,finished_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),argv=args,modules=modules,exit_code=code,elapsed_seconds=time.monotonic()-start,counts=counts,tracked_source_paths=len(paths),source_drift=[p for p in paths if before[p]!=after[p]],collected_nodes=collected,testcase_keys=[dict(classname=c.get('classname'),name=c.get('name')) for c in cases],collection_junit_exact_match=sorted(collected)==sorted(actual),unique_junit_nodes=len(actual)==len(set(actual)))
(base/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in ['argv','modules','collected_nodes','testcase_keys']}));sys.exit(code or int(bool(record['source_drift']) or not record['collection_junit_exact_match'] or not record['unique_junit_nodes']))
