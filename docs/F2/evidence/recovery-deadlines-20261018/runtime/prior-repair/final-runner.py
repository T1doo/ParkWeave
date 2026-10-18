from pathlib import Path
import os,sys,json,subprocess,hashlib,time,tempfile,concurrent.futures,xml.etree.ElementTree as E
root=Path('/workspace/ParkWeave');r=root/'.runtime/ttl-template-repair-20261017';os.chdir(root)
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
source=git('rev-parse','HEAD');assert not git('status','--porcelain')
paths=git('ls-files','src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md').splitlines()
def inputs():return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
before=inputs();(r/'final-inputs.json').write_text(json.dumps(before,indent=2)+'\n')
sys.path.insert(0,str(root/'src'));from parkweave.process_env import minimal_environment
env=minimal_environment(os.environ,PYTHONPATH=os.pathsep.join(str(root/p) for p in ['tests','src','.']),PYTHONDONTWRITEBYTECODE='1')
modules=json.loads((root/'.runtime/preparation-read-write-timing/final-invocation.json').read_text())['modules']+['test_service_plan_ttl_boundaries.py']
common=[str(root/'.venv/bin/python'),'-B','-m','pytest','-q','-p','no:cacheprovider','--rootdir='+str(root)]
collect=common+['--collect-only']+[str(root/'tests'/m) for m in modules]
p=subprocess.run(collect,env=env,capture_output=True,text=True);(r/'final-collection.log').write_text(p.stdout+p.stderr);assert p.returncode==0
nodes=[line.strip() for line in p.stdout.splitlines() if line.startswith('tests/') and '::' in line];assert len(nodes)==len(set(nodes))==296
old=E.parse(root/'.runtime/preparation-read-write-timing/final-pytest.xml').findall('.//testcase')
weights={t.get('classname').replace('.','/')+'.py::'+t.get('name'):max(float(t.get('time','1')),0.1) for t in old}
old_nodes=set(weights);assert len(old_nodes)==284 and old_nodes<=set(nodes)
shards=[[] for _ in range(4)];costs=[0.0]*4
# These five original cases write the same three evidence PNG names; keep them in
# one worker. Every other shared evidence path has only one writing test case.
screenshots=[n for n in nodes if '::test_five_actual_committed_lost_responses_' in n];assert len(screenshots)==5
shards[0]+=screenshots;costs[0]=sum(weights.get(n,0.2) for n in screenshots)
for n in sorted(set(nodes)-set(screenshots),key=lambda n:weights.get(n,0.2),reverse=True):
 target=min(range(4),key=lambda k:costs[k]);shards[target].append(n);costs[target]+=weights.get(n,0.2)
order={n:i for i,n in enumerate(nodes)}
for values in shards:values.sort(key=order.get)
assert set().union(*(set(s) for s in shards))==set(nodes) and sum(map(len,shards))==296
inv=dict(source_sha=source,started=time.time(),cwd=str(root),input_count=len(before),modules=modules,collection_argv=collect,selected_nodes=nodes,shards=[dict(id=i,nodes=values,estimated_seconds=costs[i]) for i,values in enumerate(shards)],scope='one frozen complete 296 unique regression, original284 plus12 new; four bounded nonoverlapping workers, no automatic retries')
(r/'final-invocation.json').write_text(json.dumps(inv,indent=2)+'\n')
def run_shard(i):
 base=Path(tempfile.mkdtemp(prefix='pw-ttl-template-final-'+str(i)+'-'))/'pytest';xml=r/('final-shard-'+str(i)+'.xml');argv=common+['--basetemp='+str(base),'--junitxml='+str(xml)]+shards[i]
 call=dict(source_sha=source,argv=argv,cwd=str(root),basetemp=str(base),started=time.time(),expected_count=len(shards[i]));(r/('final-shard-'+str(i)+'-invocation.json')).write_text(json.dumps(call,indent=2)+'\n')
 with (r/('final-shard-'+str(i)+'.log')).open('w') as log:p=subprocess.run(argv,env=env,stdout=log,stderr=subprocess.STDOUT)
 result=dict(id=i,exit_code=p.returncode,elapsed_seconds=time.time()-call['started']);(r/('final-shard-'+str(i)+'-result.json')).write_text(json.dumps(result,indent=2)+'\n');return result
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(run_shard,range(4)))
merged=E.Element('testsuites');cases=[]
for i in range(4):
 tree=E.parse(r/('final-shard-'+str(i)+'.xml')).getroot()
 for suite in ([tree] if tree.tag=='testsuite' else list(tree)):
  merged.append(suite);cases+=suite.findall('testcase')
E.ElementTree(merged).write(r/'final-pytest.xml',encoding='utf-8',xml_declaration=True)
actual={t.get('classname').replace('.','/')+'.py::'+t.get('name') for t in cases};after=inputs();drift=[p for p,h in before.items() if after[p]!=h]
result=dict(source_sha=source,source_tree=git('rev-parse','HEAD:src'),testcases=len(cases),unique=len(actual),missing=sorted(set(nodes)-actual),extra=sorted(actual-set(nodes)),failures=len(merged.findall('.//failure')),errors=len(merged.findall('.//error')),skipped=len(merged.findall('.//skipped')),shards=results,input_count=len(before),input_drift=drift,head_unchanged=git('rev-parse','HEAD')==source,working_tree=git('status','--porcelain'),elapsed_seconds=time.time()-inv['started'],original_unique=284,new_boundary_unique=12,independent_overlap_not_included=True)
(r/'final-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
assert result['unique']==result['testcases']==296 and not any(result[k] for k in ['missing','extra','failures','errors','skipped','input_drift','working_tree']) and result['head_unchanged'] and all(x['exit_code']==0 for x in results)
