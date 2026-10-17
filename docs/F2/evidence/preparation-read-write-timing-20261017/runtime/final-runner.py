from pathlib import Path
import os,sys,hashlib,json,subprocess,time,tempfile,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');r=root/'.runtime/preparation-read-write-timing';os.chdir(root)
source=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain']).strip()
paths=subprocess.check_output(['git','ls-files','src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md'],text=True).splitlines()
def inputs():return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
before=inputs();(r/'final-inputs.json').write_text(json.dumps(before,indent=2)+'\n')
base=Path(tempfile.mkdtemp(prefix='pw-preparation-timing-final-'))/'pytest'
modules=json.loads((r/'final-modules.json').read_text())+['test_resource_response_binding_browser.py']
argv=[str(root/'.venv/bin/python'),'-B','-m','pytest','-q','-p','no:cacheprovider','--rootdir='+str(root),'--basetemp='+str(base),'--junitxml='+str(r/'final-pytest.xml')]+[str(root/'tests'/m) for m in modules]
sys.path.insert(0,str(root/'src'));from parkweave.process_env import minimal_environment
env=minimal_environment(os.environ,PYTHONPATH=str(root/'src')+os.pathsep+str(root),PYTHONDONTWRITEBYTECODE='1')
inv=dict(source_sha=source,argv=argv,modules=modules,cwd=str(root),basetemp=str(base),input_count=len(before),started=time.time(),environment_keys=sorted(env),scope='original 279 unique collected scope plus 5 resource binding regressions; ordinary separate process with isolated synthetic fixture authority; no assignment provisioning or real model')
(r/'final-invocation.json').write_text(json.dumps(inv,indent=2)+'\n')
with (r/'final-pytest.log').open('w') as log: completed=subprocess.run(argv,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
after=inputs();drift=[p for p,h in before.items() if after[p]!=h];tree=ET.parse(r/'final-pytest.xml');cases=tree.findall('.//testcase');names=[(x.attrib['classname'],x.attrib['name']) for x in cases]
result=dict(source_sha=source,exit_code=completed.returncode,elapsed_seconds=time.time()-inv['started'],input_count=len(before),input_drift=drift,status=subprocess.check_output(['git','status','--porcelain'],text=True),unique=len(set(names)),testcases=len(cases),failures=len(tree.findall('.//failure')),errors=len(tree.findall('.//error')),skipped=len(tree.findall('.//skipped')))
(r/'final-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));assert result['exit_code']==0 and result['unique']==result['testcases']==284 and not any(result[k] for k in ('failures','errors','skipped','input_drift','status'))
