from pathlib import Path
import sys,subprocess,tarfile,io,json,hashlib,os,time,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');base=root/'.runtime/plan-reapproval-root/browser-repair';name,sha=sys.argv[1:3];b=base/name;b.mkdir(exist_ok=False);project=b/'project';project.mkdir()
raw=subprocess.check_output(['git','archive','--format=tar',sha,'src','tests','scripts','pyproject.toml'],cwd=root)
with tarfile.open(fileobj=io.BytesIO(raw)) as archive:archive.extractall(project,filter='data')
files=sorted(p.relative_to(project).as_posix() for p in project.rglob('*') if p.is_file())
def snapshot():return {p:hashlib.sha256((project/p).read_bytes()).hexdigest() for p in files}
original=snapshot();deltas={}
if name!='baseline':
 for p in (base/'candidate').glob('test_*.py'):
  path=project/'tests'/p.name;path.write_bytes(p.read_bytes());deltas['tests/'+p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
before=snapshot();(b/'source-before.json').write_text(json.dumps(dict(scope='PRIVATE_WIP_NOT_FORMAL',git_snapshot=sha,git_archive_sha256=hashlib.sha256(raw).hexdigest(),source_files=before,candidate_deltas=deltas,product_source_changed=any(before[p]!=original[p] for p in files if p.startswith('src/'))),indent=2)+'\n')
plugin=b/'browser_repair_capture.py';plugin.write_text("""from pathlib import Path
import os,json,sys,re,hashlib
values=set()
def pytest_configure(config):
 import parkweave
 actual=Path(parkweave.__file__).resolve();expected=Path(os.environ['REPAIR_PROJECT'])/'src/parkweave/__init__.py';assert actual==expected
 Path(os.environ['REPAIR_OUT'],'actual-package.json').write_text(json.dumps(dict(actual=str(actual),expected=str(expected),sha256=hashlib.sha256(actual.read_bytes()).hexdigest()),indent=2)+'\\n')
def pytest_collection_finish(session):
 out=Path(os.environ['REPAIR_OUT']);out.joinpath('collection.json').write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\\n');routes=[]
 for name,module in list(sys.modules.items()):
  value=getattr(module,'OUT',None) if name.startswith('test_') else None
  if isinstance(value,Path) and ('.runtime' in value.parts or str(value).startswith('.runtime/')):
   target=out/'artifacts'/name;setattr(module,'OUT',target);routes.append(dict(module=name,original=str(value),actual=str(target)))
 out.joinpath('artifact-routing.json').write_text(json.dumps(dict(product_logic_changed=False,before_fixtures=True,routes=routes),indent=2)+'\\n')
def pytest_fixture_post_finalizer(fixturedef,request):
 if fixturedef.argname not in {'fixture','preparation_fixture','receipt_fixture','link_fixture','fresh_chain'} or not fixturedef.cached_result:return
 value=fixturedef.cached_result[0]
 if isinstance(value,dict):value=value.get('f',value.get('tokens'))
 tokens=value[2] if isinstance(value,tuple) and len(value)>2 and isinstance(value[2],dict) else value if isinstance(value,dict) else {}
 values.update(v for v in tokens.values() if isinstance(v,str) and re.fullmatch(r'[A-Za-z0-9_-]{32,128}',v))
 path=Path(os.environ['REPAIR_OUT'],'redaction.private.json');path.write_text(json.dumps(sorted(values))+'\\n');path.chmod(0o600)
""")
items=['tests/test_case_resource_delivery_browser.py::test_late_http_result_does_not_fill_current_private_view[identity]','tests/test_new_enterprise_local_chain_browser.py::test_goal_selection_unknown_save_keeps_original_body_and_cas'] if name=='baseline' else ['tests/test_case_resource_delivery_browser.py','tests/test_new_enterprise_local_chain_browser.py']
argv=[str(root/'.venv/bin/python'),'-m','pytest','-vv','-p','browser_repair_capture',*items,'--basetemp=/tmp/parkweave-browser-repair-'+name,'--junitxml='+str(b/'junit.xml')]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(project/'src')+os.pathsep+str(project/'tests')+os.pathsep+str(b),REPAIR_PROJECT=str(project),REPAIR_OUT=str(b))
start=time.monotonic()
with (b/'stdout.log').open('w') as log:code=subprocess.run(argv,cwd=project,env=env,stdout=log,stderr=subprocess.STDOUT).returncode
after=snapshot();(b/'source-after.json').write_text(json.dumps(after,indent=2)+'\n');cases=list(ET.parse(b/'junit.xml').iter('testcase'));counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0)
for c in cases:counts['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
actual=['tests/'+c.get('classname').split('.')[-1]+'.py::'+c.get('name') for c in cases];collected=json.loads((b/'collection.json').read_text());result=dict(scope='PRIVATE_WIP_NOT_FORMAL',git_snapshot=sha,argv=argv,exit_code=code,elapsed_seconds=time.monotonic()-start,counts=counts,collection_junit_exact=sorted(actual)==sorted(collected),unique_junit=len(actual)==len(set(actual)),source_drift=[p for p in files if before[p]!=after[p]],product_source_changed=any(before[p]!=original[p] for p in files if p.startswith('src/')))
(b/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(code)
