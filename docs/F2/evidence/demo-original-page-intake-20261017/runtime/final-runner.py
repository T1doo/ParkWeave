from pathlib import Path
import os,sys,hashlib,json,subprocess,time,tempfile,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');r=root/'.runtime/demo-original-page-intake';os.chdir(root)
source='9c50ff798fd4c6a78f1756aba75cffac2a8d137a'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==source
assert not subprocess.check_output(['git','status','--porcelain']).strip()
assert subprocess.check_output(['git','rev-parse','HEAD:src'],text=True)==subprocess.check_output(['git','rev-parse','897fc694:src'],text=True)
paths=subprocess.check_output(['git','ls-files','src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md'],text=True).splitlines()
def inputs():return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
before=inputs();(r/'final-inputs.json').write_text(json.dumps(before,indent=2)+'\n')
base=Path(tempfile.mkdtemp(prefix='pw-demo-intake-final-'))/'pytest'
argv=[str(root/'.venv/bin/python'),'-B','-m','pytest','-q','-p','no:cacheprovider','--rootdir='+str(root),'--basetemp='+str(base),'--junitxml='+str(r/'final-pytest.xml'),str(root/'tests/test_demo_original_page_intake_browser.py'),str(root/'tests/test_local_synthetic_demo_browser.py')]
sys.path.insert(0,str(root/'src'));from parkweave.process_env import minimal_environment
env=minimal_environment(os.environ,PYTHONPATH=str(root/'src')+os.pathsep+str(root),PYTHONDONTWRITEBYTECODE='1')
inv=dict(source_sha=source,argv=argv,cwd=str(root),basetemp=str(base),input_count=len(before),started=time.time(),environment_keys=sorted(env),scope='two complete browser modules; 3 unique; new2 + prior1; explicit synthetic installation state only; no real model')
(r/'final-invocation.json').write_text(json.dumps(inv,indent=2)+'\n')
with (r/'final-pytest.log').open('w') as log: completed=subprocess.run(argv,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
after=inputs();drift=[p for p,h in before.items() if after[p]!=h];tree=ET.parse(r/'final-pytest.xml');cases=tree.findall('.//testcase');names=[(x.attrib['classname'],x.attrib['name']) for x in cases]
result=dict(source_sha=source,exit_code=completed.returncode,elapsed_seconds=time.time()-inv['started'],input_count=len(before),input_drift=drift,status=subprocess.check_output(['git','status','--porcelain'],text=True),unique=len(set(names)),testcases=len(cases),failures=len(tree.findall('.//failure')),errors=len(tree.findall('.//error')),skipped=len(tree.findall('.//skipped')),product_tree_unchanged=True)
(r/'final-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert result['exit_code']==0 and result['unique']==result['testcases']==3 and not any(result[k] for k in ('failures','errors','skipped','input_drift','status'))
