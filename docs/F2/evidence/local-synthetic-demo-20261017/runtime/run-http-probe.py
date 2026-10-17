from pathlib import Path
import os,sys,hashlib,json,subprocess,time,tempfile
root=Path('/workspace/ParkWeave');os.chdir(root);r=root/'.runtime/local-synthetic-demo'
source='8ae2892fe56465fbf53e23ae2010258ce7881b47'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==source
assert json.loads((r/'final-validation.json').read_text())['exit_code']==0
manifest=json.loads((r/'final-inputs.json').read_text())
def drift():return [p for p,h in manifest.items() if hashlib.sha256((root/p).read_bytes()).hexdigest()!=h]
assert not drift()
probe=r/'test_ordinary_http_probe.py';probe_sha=hashlib.sha256(probe.read_bytes()).hexdigest()
cwd=r/'http-cwd';cwd.mkdir(exist_ok=False)
base=Path(tempfile.mkdtemp(prefix='pw-demo-http-'))/'pytest'
argv=[str(root/'.venv/bin/python'),'-B','-m','pytest','-q','-p','no:cacheprovider','-p','conftest','--rootdir='+str(root),'--basetemp='+str(base),'--junitxml='+str(r/'ordinary-http-pytest.xml'),str(probe)]
sys.path.insert(0,str(root/'src'));from parkweave.process_env import minimal_environment
env=minimal_environment(os.environ,PYTHONPATH=os.pathsep.join(str(root/p) for p in ('src','tests','')),PYTHONDONTWRITEBYTECODE='1')
inv=dict(source_sha=source,argv=argv,cwd=str(cwd),basetemp=str(base),probe_sha256=probe_sha,input_count=len(manifest),started=time.time(),scope='additional separate ordinary-process HTTP original full-chain + cold read + PREPARE revocation; overlaps suite, not added')
(r/'ordinary-http-invocation.json').write_text(json.dumps(inv,indent=2)+'\n')
with (r/'ordinary-http-pytest.log').open('w') as log:result=subprocess.run(argv,cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT)
record=dict(source_sha=source,exit_code=result.returncode,elapsed_seconds=time.time()-inv['started'],basetemp=str(base),input_drift=drift(),probe_unchanged=hashlib.sha256(probe.read_bytes()).hexdigest()==probe_sha,worktree_status=subprocess.check_output(['git','status','--porcelain'],text=True))
(r/'ordinary-http-validation.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
assert result.returncode==0 and not record['input_drift'] and record['probe_unchanged'] and not record['worktree_status']
