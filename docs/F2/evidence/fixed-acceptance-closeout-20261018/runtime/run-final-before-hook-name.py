from pathlib import Path
from datetime import datetime,timezone
import subprocess,json,hashlib,tempfile,tarfile,io,os,time,sys,shutil
root=Path('/workspace/ParkWeave');run=root/'.runtime/fixed-acceptance-closeout-20261018';out=run/'frozen-7f02fe3f';out.mkdir(exist_ok=False)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip();assert head=='7f02fe3f463fb402eb497fb4342d93037b24cc18'
paths=subprocess.check_output(['git','ls-files','-z','src','tests','scripts','pyproject.toml','README.md','docs/验收规格.json','docs/F1/ATBindings.json','docs/F1/AcceptanceSourceBatchContract-20261018.md'],cwd=root).decode().strip('\x00').split('\x00');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pre={p:sha(root/p) for p in paths};(out/'shared-before.json').write_text(json.dumps(pre,indent=2)+'\n')
mirror=Path(tempfile.mkdtemp(prefix='pw-source-batches-final-'))/'mirror'
clone=subprocess.run(['git','clone','--quiet','--shared','--no-checkout',str(root),str(mirror)],text=True,capture_output=True);(out/'clone.stdout').write_text(clone.stdout);(out/'clone.stderr').write_text(clone.stderr);assert clone.returncode==0
archive=subprocess.check_output(['git','archive',head,*paths],cwd=root)
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(mirror,filter='data')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=mirror,text=True).strip()==head
mpre={p:sha(mirror/p) for p in paths};assert pre==mpre;(out/'mirror-before.json').write_text(json.dumps(mpre,indent=2)+'\n')
env=os.environ.copy();env={k:v for k,v in env.items() if not k.startswith('PARKWEAVE_')};env.update(PYTHONPATH=str(mirror/'src')+':'+str(mirror/'tests')+':'+str(mirror),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
child=out/'child.py';child.write_text(r"""import sys,json,hashlib
from pathlib import Path
import pytest
out=Path(sys.argv[1]);mirror=Path.cwd()
class Record:
 def pytest_collection_finish(self,session):(out/'collection.json').write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\n')
 def pytest_runtest_logreport(self,r):
  with (out/'calls.jsonl').open('a') as f:f.write(json.dumps(dict(nodeid=r.nodeid,when=r.when,outcome=r.outcome,duration=r.duration))+'\n')
code=pytest.main(sys.argv[2:],plugins=[Record()]);origins={}
for name,m in tuple(sys.modules.items()):
 p=getattr(m,'__file__',None)
 if p and (name.startswith(('parkweave','scripts.','test_')) or name in ('conftest','owned_connection_diagnostics')):
  p=Path(p).resolve()
  if p.is_file():origins[name]=dict(path=str(p),within_mirror=p.is_relative_to(mirror),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(out/'module-origins.json').write_text(json.dumps(origins,indent=2)+'\n');raise SystemExit(code)
""")
commands=[];started=datetime.now(timezone.utc).isoformat();t=time.monotonic()
def execute(cmd,name,timeout):
 with (out/(name+'.stdout')).open('w') as stdout,(out/(name+'.stderr')).open('w') as stderr:p=subprocess.run(cmd,cwd=mirror,env=env,stdout=stdout,stderr=stderr,timeout=timeout)
 commands.append(dict(name=name,args=cmd,exit_code=p.returncode));return p.returncode
code=execute([str(root/'.venv/bin/python'),str(child),str(out),'-q','-c',str(mirror/'pyproject.toml'),'--rootdir='+str(mirror),'-p','no:cacheprovider','tests/test_source_bytes.py','tests/test_acceptance_runner.py','--basetemp='+str(mirror.parent/'pytest-temp'),'--junitxml='+str(out/'results.xml')],'unit',120)
if code==0:
 observer=out/'observe-source.py';observer.write_text(r"""from pathlib import Path
import json,hashlib,sys
from scripts.windows_ci import source_bytes
root=Path.cwd();head=sys.argv[2];hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'tests').glob('test_*.py')}
original=source_bytes._git;calls=[]
def observe(root,args,data=None):
 result=original(root,args,data);record=dict(args=args,returned_bytes=len(result))
 if args==['cat-file','--batch']:
  paths=[x.split(':',1)[1] for x in data.decode().splitlines()];record.update(paths=paths,body_bytes=sum((root/p).stat().st_size for p in paths))
 calls.append(record);return result
source_bytes._git=observe;source_bytes.verify_head_test_sources(root,head,hashes)
result=dict(head=head,files=len(hashes),aggregate_bytes=sum((root/p).stat().st_size for p in hashes),calls=calls,hashes=hashes,all_paths_checked=True,source_binding_passed=True,acceptance_runner_invoked=False)
Path(sys.argv[1]).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ('hashes','calls')}))
""")
 code=execute([str(root/'.venv/bin/python'),'-B',str(observer),str(out/'actual-source-verification.json'),head],'source-verification',30)
if code==0:code=execute([str(root/'.venv/bin/python'),'-B','scripts/run_acceptance.py','--ids','AT-13','--source-head',head,'--report',str(out/'original-runner-at13.json')],'original-runner-at13',120)
private=mirror/'.runtime'
for p in private.glob('pytest-*'):
 if p.is_file():target=out/'original-runner-artifacts'/p.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(p,target)
post={p:sha(root/p) for p in paths};mpost={p:sha(mirror/p) for p in paths};(out/'shared-after.json').write_text(json.dumps(post,indent=2)+'\n');(out/'mirror-after.json').write_text(json.dumps(mpost,indent=2)+'\n')
report=dict(head=head,commands=commands,exit_code=code,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),outer_seconds=time.monotonic()-t,inputs=len(pre),four_maps_equal=pre==mpre==post==mpost,mirror=str(mirror),archive_sha256=hashlib.sha256(archive).hexdigest(),old_AT21_AT32_or_risk_windows_retried=False,full_regression=False,real_model_calls=0,independent_dynamic=0)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));print((out/'unit.stdout').read_text()[-2400:]);print((out/'original-runner-at13.stdout').read_text()[-1000:] if (out/'original-runner-at13.stdout').exists() else 'AT13 not started');raise SystemExit(code)
