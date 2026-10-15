from pathlib import Path
import hashlib,json,subprocess,time,sys,os,xml.etree.ElementTree as ET
base=Path('.runtime/at24-27-independent');name=sys.argv[1];modules=json.loads(Path(sys.argv[2]).read_text());source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert not list(base.glob(name+'*')), 'Evidence windows must never be overwritten'
assert len(modules)==len(set(modules)), 'Repeated module forbidden'
runner_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();plugin_hash=hashlib.sha256((base/'shared_capture.py').read_bytes()).hexdigest()
assert source==sys.argv[3], 'exact frozen SHA required'
assert not subprocess.check_output(['git','status','--porcelain','--','src','tests','scripts','pyproject.toml']), 'source tree must be committed'
assert all(Path(p).is_file() for p in modules)
paths=[p for p in subprocess.check_output(['git','ls-files','-z','--','src','tests','scripts','pyproject.toml']).decode().split('\0') if p]
def manifest():return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in paths}
def own_traces():
 return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.is_file() and '.private.' not in p.name and
  (p.name.endswith(('.stdout.jsonl','.stderr.log')) or p.name.startswith(('oracle-','baseline-','at-results-','html-results-','read-observations-','selected-capacity-progress-')) and p.suffix=='.jsonl')}
own_before=own_traces()
all_paths=[p for p in subprocess.check_output(['git','ls-files','-z']).decode().split('\0') if p and Path(p).is_file()]
def all_manifest():return {p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in all_paths}
all_before=all_manifest();(base/(name+'-all-tracked-before.json')).write_text(json.dumps(all_before,indent=2)+'\n')
before=manifest();(base/(name+'-before.json')).write_text(json.dumps(before,indent=2)+'\n')
args=[sys.executable,'-m','pytest','-q','-p','shared_capture',*modules,'--basetemp=/tmp/parkweave-at24-27-independent-'+name,'--junitxml='+str(base/(name+'.xml'))]
env=dict(os.environ,AT_BATCH_WINDOW=name,TYPED_COLLECTION=str(base/(name+'-collection.json')),TYPED_PRIVATE=str(base/('redaction-'+name+'.private.json')),TYPED_HTTP=str(base/(name+'-http-traffic.json')));env['PYTHONPATH']=str(base.resolve())+os.pathsep+os.getcwd()+os.pathsep+env.get('PYTHONPATH','')
start=time.monotonic();started=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat()
with (base/(name+'.log')).open('w') as log:code=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT,env=env).returncode
all_after=all_manifest();(base/(name+'-all-tracked-after.json')).write_text(json.dumps(all_after,indent=2)+'\n')
head_after=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
source_status_after=subprocess.check_output(['git','status','--porcelain','--','src','tests','scripts','pyproject.toml'],text=True)
after=manifest();(base/(name+'-after.json')).write_text(json.dumps(after,indent=2)+'\n');cases=list(ET.parse(base/(name+'.xml')).iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
own_after=own_traces();own_new=[dict(path=p,sha256=value,source_sha=source) for p,value in own_after.items() if own_before.get(p)!=value]
(base/(name+'-own-traces.json')).write_text(json.dumps(dict(records=own_new,count=len(own_new)),indent=2)+'\n')
related=base/'related-test-artifacts'/name
related_files=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),source_sha=source) for p in related.rglob('*') if p.is_file() and '.private.' not in p.name] if related.exists() else []
(base/(name+'-related-traces.json')).write_text(json.dumps(dict(records=related_files,count=len(related_files),prior_runtime_not_copied=True),indent=2)+'\n')
for c in cases:counts['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
def node_id(c):
 parts=c.get('classname','').split('.');pos=next((i for i,v in enumerate(parts) if v.startswith('test_')),None)
 return 'UNMATCHED_JUNIT::'+c.get('name','') if pos is None else 'tests/'+parts[pos]+'.py::'+'::'.join(parts[pos+1:]+[c.get('name')])
collected=json.loads((base/(name+'-collection.json')).read_text());actual=[node_id(c) for c in cases]
record=dict(source_sha=source,head_after=head_after,all_tracked_paths=len(all_paths),all_tracked_drift=[p for p in all_paths if all_before[p]!=all_after[p]],started_utc=started,finished_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),argv=args,modules=modules,exit_code=code,elapsed_seconds=time.monotonic()-start,counts=counts,tracked_source_paths=len(paths),source_drift=[p for p in paths if before[p]!=after[p]],source_status_after=source_status_after,runner_sha256=runner_hash,plugin_sha256=plugin_hash,runner_unchanged=runner_hash==hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),plugin_unchanged=plugin_hash==hashlib.sha256((base/'shared_capture.py').read_bytes()).hexdigest(),real_model_calls=0,real_browser='NOT_RUN',Windows='NOT_RUN',production='NOT_RUN',collected_nodes=collected,testcase_keys=[dict(classname=c.get('classname'),name=c.get('name')) for c in cases],collection_junit_exact_match=sorted(collected)==sorted(actual),unique_junit_nodes=len(actual)==len(set(actual)))
(base/(name+'.json')).write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:v for k,v in record.items() if k not in ['argv','modules','collected_nodes','testcase_keys']}));assert head_after==source, 'HEAD changed during formal window'
sys.exit(code or int(bool(record['source_drift']) or bool(source_status_after) or not record['collection_junit_exact_match'] or not record['unique_junit_nodes'] or not record['runner_unchanged'] or not record['plugin_unchanged']))
