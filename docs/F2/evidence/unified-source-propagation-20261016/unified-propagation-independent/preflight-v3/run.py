from pathlib import Path
import subprocess,json,hashlib,os,time,xml.etree.ElementTree as ET
r=Path('/workspace/ParkWeave');b=r/'.runtime/unified-propagation-independent/preflight-v3'
modules=['tests/test_unified_dependency_propagation_literal.py','tests/test_unified_dependency_propagation_independent.py']
paths=sorted(set(subprocess.check_output(['git','ls-files','-z','--','src','tests','scripts','pyproject.toml'],cwd=r).decode().split('\0'))-{''} | {str(p.relative_to(r)) for d in ('src','tests') for p in (r/d).rglob('*') if p.is_file() and p.suffix in ('.py','.js','.html') and '__pycache__' not in p.parts})
def snapshot():return dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),status=subprocess.check_output(['git','status','--porcelain'],cwd=r,text=True),paths={p:hashlib.sha256((r/p).read_bytes()).hexdigest() for p in paths})
before=snapshot();(b/'before.json').write_text(json.dumps(before,indent=2)+'\n')
env=dict(os.environ,PYTHONPATH=str(b)+os.pathsep+str(r)+os.pathsep+os.environ.get('PYTHONPATH',''),TYPED_CAPTURE_PLUGIN=str(b/'shared_capture.py'),TYPED_COLLECTION=str(b/'collection.json'),TYPED_PRIVATE=str(b/'redaction.private.json'),AT_BATCH_ARTIFACT_ROOT=str(b/'artifacts'),AT_BATCH_WINDOW='independent')
argv=[str(r/'.venv/bin/python'),'-m','pytest','-vv','-p','shared_capture',*modules,'--basetemp=/tmp/parkweave-unified-independent-preflight-v3','--junitxml='+str(b/'junit.xml')]
start=time.monotonic()
with (b/'stdout.log').open('w') as out:code=subprocess.run(argv,cwd=r,env=env,stdout=out,stderr=subprocess.STDOUT).returncode
after=snapshot();(b/'after.json').write_text(json.dumps(after,indent=2)+'\n')
cases=list(ET.parse(b/'junit.xml').iter('testcase'));counts={k:0 for k in ('PASS','FAIL','ERROR','SKIP')}
for c in cases:counts['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
actual=['tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cases]
collected=json.loads((b/'collection.json').read_text());result=dict(scope='INDEPENDENT_WIP_PREFLIGHT_NOT_FROZEN',argv=argv,exit_code=code,elapsed_seconds=time.monotonic()-start,counts=counts,source_drift=[p for p in paths if before['paths'][p]!=after['paths'][p]],head_stable=before['head']==after['head'],collection_junit_exact=sorted(actual)==sorted(collected),unique_junit=len(set(actual))==len(actual))
(b/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(code)
