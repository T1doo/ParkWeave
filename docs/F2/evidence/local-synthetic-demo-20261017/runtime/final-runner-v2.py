from pathlib import Path
import os,sys,hashlib,json,subprocess,time,tempfile
root=Path('/workspace/ParkWeave');r=root/'.runtime/local-synthetic-demo';os.chdir(root)
sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert sha=='8551da0326c3deda5dbdaf09a506849724bc130e'
assert not subprocess.check_output(['git','status','--porcelain']).strip()
paths=subprocess.check_output(['git','ls-files','src','tests','scripts','pyproject.toml','docs/F2/LocalSyntheticDemoContract-20261017.md'],text=True).splitlines()
def inputs():return {p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in paths}
before=inputs();(r/'final-inputs.json').write_text(json.dumps(before,indent=2)+'\n')
cwd=r/'final-cwd-v2';cwd.mkdir(exist_ok=False)
temporary=Path(tempfile.mkdtemp(prefix='pw-demo-final-'));base=temporary/'pytest';assert not base.exists()
modules=['test_local_synthetic_demo.py','test_local_synthetic_demo_browser.py','test_service_selection.py','test_service_capability_contract.py','test_service_selection_candidates.py','test_service_selection_web.py','test_service_selection_nodevm_actual.py','test_service_selection_full_chain.py','test_service_selection_source_safe.py','test_service_capability_catalog_actual.py','test_service_plan_candidates.py','test_native_preparation_entry.py']
argv=[str(root/'.venv/bin/python'),'-B','-m','pytest','-q','-p','no:cacheprovider','--rootdir='+str(root),'--basetemp='+str(base),'--junitxml='+str(r/'final-pytest.xml')]+[str(root/'tests'/name) for name in modules]
sys.path.insert(0,str(root/'src'));from parkweave.process_env import minimal_environment
env=minimal_environment(os.environ,PYTHONPATH=str(root/'src')+os.pathsep+str(root),PYTHONDONTWRITEBYTECODE='1')
inv=dict(source_sha=sha,cwd=str(cwd),argv=argv,input_count=len(before),start_time=time.time(),environment_keys=sorted(env),scope='12 complete related modules; explicit synthetic PG initial states; no real model')
(r/'final-invocation.json').write_text(json.dumps(inv,indent=2)+'\n')
with (r/'final-pytest.log').open('w') as log: result=subprocess.run(argv,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
after=inputs();drift=[p for p,h in before.items() if after[p]!=h]
output=dict(source_sha=sha,exit_code=result.returncode,elapsed_seconds=time.time()-inv['start_time'],input_count=len(before),input_drift=drift,status=subprocess.check_output(['git','status','--porcelain'],text=True))
(r/'final-validation.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output))
assert result.returncode==0 and not drift and not output['status']
