from pathlib import Path
import sys,shutil,subprocess,json,hashlib,os,time,xml.etree.ElementTree as ET
r=Path('/workspace/ParkWeave');base=r/'.runtime/plan-reapproval-independent';b=base/sys.argv[1];b.mkdir(exist_ok=False);project=b/'project';project.mkdir()
for name in ('src','tests','scripts'):shutil.copytree(r/name,project/name,ignore=shutil.ignore_patterns('__pycache__','.pytest_cache','*.pyc'))
shutil.copy2(r/'pyproject.toml',project/'pyproject.toml')
# Documentation is not a data source for business expected values. Include only
# small exact contract/oracle files required by imported test module constants.
for name in ('PlanReapprovalOracle-20261016.json','PlanReapprovalContract-20261016.md'):
 p=r/'docs/F2'/name
 if p.exists():q=project/'docs/F2'/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
paths=sorted([p.relative_to(project).as_posix() for n in ('src','tests','scripts') for p in (project/n).rglob('*') if p.is_file()]+['pyproject.toml'])
def hashes(root):return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
shared=hashes(r);copied=hashes(project);assert shared==copied
for candidate in (base/'candidate-v4/tests').glob('*'):
 if candidate.is_file():shutil.copy2(candidate,project/'tests'/candidate.name)
paths=sorted(set(paths)|{p.relative_to(project).as_posix() for p in (project/'tests').glob('test_plan_source_reapproval*.py')})
copied=hashes(project)
(b/'source-before.json').write_text(json.dumps(dict(scope='ISOLATED_WIP_SOURCE_SNAPSHOT_NOT_FROZEN',head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),files=copied,candidate_delta={p:copied[p] for p in paths if p not in shared or copied[p]!=shared[p]}),indent=2)+'\n')
plugin=b/'ra_independent_capture.py';plugin.write_text("""from pathlib import Path
import os,json,hashlib

def pytest_configure(config):
 import parkweave
 actual=Path(parkweave.__file__).resolve();expected=Path(os.environ['RA_PROJECT'])/'src/parkweave/__init__.py'
 assert actual==expected, 'exact private source package required'
 target=Path(os.environ['RA_COLLECTION'])
 target.with_name('product-package.json').write_text(json.dumps(dict(actual=str(actual),expected=str(expected),sha256=hashlib.sha256(actual.read_bytes()).hexdigest()),indent=2)+'\\n')

def pytest_collection_finish(session):
 Path(os.environ['RA_COLLECTION']).write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\\n')
""")
env=dict(os.environ,PYTHONPATH=str(project/'src')+os.pathsep+str(project/'tests')+os.pathsep+str(b),RA_COLLECTION=str(b/'collection.json'),RA_PROJECT=str(project))
argv=[str(r/'.venv/bin/python'),'-m','pytest','-vv','-p','ra_independent_capture','tests/test_plan_source_reapproval_chromium.py','--basetemp=/tmp/parkweave-reapproval-independent-'+sys.argv[1],'--junitxml='+str(b/'junit.xml')]
start=time.monotonic()
with (b/'stdout.log').open('w') as log:code=subprocess.run(argv,cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
current=hashes(project);(b/'source-after.json').write_text(json.dumps(current,indent=2)+'\n')
cases=list(ET.parse(b/'junit.xml').iter('testcase'));counts={k:0 for k in ('PASS','FAIL','ERROR','SKIP')}
for c in cases:counts['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
collected=json.loads((b/'collection.json').read_text());actual=['tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cases]
result=dict(scope='ISOLATED_WIP_PREFLIGHT_NOT_FROZEN',argv=argv,exit_code=code,elapsed_seconds=time.monotonic()-start,counts=counts,private_source_drift=[p for p in paths if current[p]!=copied[p]],collection_junit_exact=sorted(actual)==sorted(collected),unique_junit=len(actual)==len(set(actual)),actual_source_manifest='source-before.json',product_package=str(project/'src/parkweave'),shared_source_edited=False)
(b/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(code)
