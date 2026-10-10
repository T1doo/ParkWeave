from pathlib import Path
import os,sys,subprocess,json,time,tempfile
sys.path.insert(0,str(Path.cwd()/"src"))
from parkweave.process_env import minimal_environment
out=Path(".runtime/template-upgrade");name=sys.argv[1];args=sys.argv[2:]
start=time.time()
with (out/(name+"-pytest.log")).open("w") as log:
 result=subprocess.run([sys.executable,"-m","pytest",*args,"-q","--basetemp="+tempfile.mkdtemp(prefix="pw-template-upgrade-"),"--junitxml="+str(out/(name+"-junit.xml"))],env=minimal_environment(os.environ,PYTHONPATH=str(Path.cwd()/"src"),PYTHONDONTWRITEBYTECODE="1"),stdout=log,stderr=subprocess.STDOUT)
meta=dict(returncode=result.returncode,start=start,end=time.time(),pytest_args=args,minimal_environment=True)
(out/(name+"-execution.json")).write_text(json.dumps(meta,indent=2)+"\n");print(json.dumps(meta));raise SystemExit(result.returncode)
