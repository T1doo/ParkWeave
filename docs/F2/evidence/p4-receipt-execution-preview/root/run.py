from pathlib import Path
import os,sys,subprocess,json,tempfile,time
ROOT=Path('/workspace/ParkWeave');OUT=ROOT/'.runtime/p4-receipt-execution-preview';sys.path.insert(0,str(ROOT/'src'))
from parkweave.process_env import minimal_environment
name=sys.argv[1];args=[sys.executable,str(OUT/'wrapper.py'),*sys.argv[2:],'-q','--basetemp='+tempfile.mkdtemp(prefix='pw-service-plan-recovery-'),'--junitxml='+str(OUT/(name+'-junit.xml'))];start=time.time()
with (OUT/(name+'-pytest.log')).open('w') as log:r=subprocess.run(args,cwd=ROOT,env=minimal_environment(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONDONTWRITEBYTECODE='1'),stdout=log,stderr=subprocess.STDOUT)
(OUT/(name+'-execution.json')).write_text(json.dumps(dict(returncode=r.returncode,start=start,end=time.time(),modules=[a for a in sys.argv[2:] if a.endswith(".py")],pytest_args=sys.argv[2:],minimal_environment=True),indent=2)+'\n');print(json.dumps(dict(returncode=r.returncode,modules=len([a for a in sys.argv[2:] if a.endswith(".py")]))));raise SystemExit(r.returncode)
