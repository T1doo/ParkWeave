from pathlib import Path
import hashlib,json,os,subprocess,sys,time,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/typed-source-impact-review'
FREEZE='a5d9da251c223e3a64e20d3d47987d5b58fcdb6f';prefix='extra-a5d9da25'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()==FREEZE
modules=json.loads((ROOT/'.runtime/typed-source-impact/review-extra-modules.json').read_text());assert len(modules)==8
tracked=subprocess.check_output(['git','ls-files','-z','src','tests','scripts','pyproject.toml'],cwd=ROOT).decode().strip('\0').split('\0')
paths=list(tracked)+[str(p.relative_to(ROOT)) for p in (ROOT/'src/parkweave.egg-info').glob('*') if p.is_file()]
def manifest():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
before=manifest();(OUT/(prefix+'-before.json')).write_text(json.dumps(before,indent=2)+'\n')
freeze=json.loads((ROOT/'.runtime/typed-source-impact/freeze.json').read_text())['files'];assert all(before[p]==h for p,h in freeze.items())
args=[sys.executable,'-m','pytest','-q','-p','typed_review_collection',*modules,'--basetemp=/tmp/pw-typed-source-impact-extra-a5d9da25','--junitxml='+str(OUT/(prefix+'.xml'))]
env=os.environ.copy();env['PYTHONPATH']='.:src:tests:.runtime/typed-source-impact-review';env['XDG_CACHE_HOME']=str(ROOT/'.runtime/xdg-cache')
start=time.monotonic()
with (OUT/(prefix+'.log')).open('w') as log:code=subprocess.run(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
after=manifest();(OUT/(prefix+'-after.json')).write_text(json.dumps(after,indent=2)+'\n')
counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0);actual=[];skips=[];junit_seconds=None
if (OUT/(prefix+'.xml')).exists():
    root=ET.parse(OUT/(prefix+'.xml')).getroot();junit_seconds=root[0].get('time')
    for t in root.iter('testcase'):
        parts=t.get('classname','').split('.');pos=next(i for i,v in enumerate(parts) if v.startswith('test_'))
        actual.append('tests/'+parts[pos]+'.py::'+'::'.join(parts[pos+1:]+[t.get('name')]))
        state='ERROR' if t.find('error') is not None else 'FAIL' if t.find('failure') is not None else 'SKIP' if t.find('skipped') is not None else 'PASS';counts[state]+=1
        if state=='SKIP':skips.append(dict(node=actual[-1],reason=t.find('skipped').get('message')))
collected=json.loads((OUT/(prefix+'-collection.json')).read_text()) if (OUT/(prefix+'-collection.json')).exists() else []
report=dict(source_sha=FREEZE,argv=args,modules=modules,exit_code=code,counts=counts,junit_seconds=junit_seconds,elapsed_seconds=time.monotonic()-start,collected_nodes=len(collected),executed_nodes=len(actual),collection_junit_exact=sorted(collected)==sorted(actual),duplicates=len(actual)-len(set(actual)),tracked_paths=len(tracked),manifest_paths=len(paths),changed_files=[p for p in paths if before[p]!=after[p]],skips=skips)
(OUT/(prefix+'-result.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));sys.exit(code)
