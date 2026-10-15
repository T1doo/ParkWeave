from pathlib import Path
from datetime import datetime,timezone
import os,sys,json,hashlib,subprocess,time,shutil,xml.etree.ElementTree as ET
OUT=Path(__file__).resolve().parent;ROOT=OUT/'private-worktree';tag=sys.argv[1]
assert not (OUT/(tag+'.log')).exists()
paths=['src/parkweave/material_package_continuation.py','src/parkweave/plan_source_conflicts.py','src/parkweave/service_case_steps.py','src/parkweave/api.py','tests/test_material_package_continuation.py']
def hashes():return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
before=hashes();started=datetime.now(timezone.utc).isoformat();clock=time.monotonic()
snapshot=OUT/'window-sources'/tag
for name in paths:
 target=snapshot/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target);target.chmod(0o444)
env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(OUT),str(ROOT/'src'),str(ROOT/'tests')]),XDG_CACHE_HOME=str(OUT/'xdg-cache'),TYPED_COLLECTION=str(OUT/(tag+'-collection.json')),TYPED_PRIVATE=str(OUT/(tag+'-redaction.private.json')),AT_BATCH_ARTIFACT_ROOT=str(OUT/'artifacts'),AT_BATCH_WINDOW=tag)
args=[sys.executable,'-m','pytest','-q','-p','shared_capture','-o','cache_dir='+str(OUT/('cache-'+tag)),*sys.argv[2:],'--basetemp='+str(Path('/tmp')/('parkweave-multifield-backend-'+tag)),'--junitxml='+str(OUT/(tag+'.xml'))]
(OUT/(tag+'-launch.json')).write_text(json.dumps(dict(started_utc=started,private_tree=str(ROOT),before_sha256=before,argv=args),indent=2)+'\n')
with (OUT/(tag+'.log')).open('w') as stream:code=subprocess.run(args,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT).returncode
counts=dict(PASS=0,FAIL=0,ERROR=0,SKIP=0);nodes=[]
if (OUT/(tag+'.xml')).exists():
 for c in ET.parse(OUT/(tag+'.xml')).iter('testcase'):
  if not c.get('classname') or not c.get('name'):continue
  counts['ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS']+=1
  nodes.append(c.get('classname')+'::'+c.get('name'))
result=dict(tag=tag,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-clock,exit_code=code,counts=counts,nodes=nodes,before_sha256=before,after_sha256=hashes(),private_source_unchanged=before==hashes(),private_tree=str(ROOT))
(OUT/(tag+'-result.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['tag','exit_code','counts','elapsed_seconds','private_source_unchanged']}));sys.exit(code)
