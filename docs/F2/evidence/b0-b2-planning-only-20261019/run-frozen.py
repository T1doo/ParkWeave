from pathlib import Path
from datetime import datetime, timezone
import subprocess, json, hashlib, tempfile, tarfile, io, os, time, shutil

root=Path('/workspace/ParkWeave');run=root/'.runtime/b0-b2-planning-only-20261019'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
assert head==json.loads((run/'source-freeze.json').read_text())['head']
out=run/('frozen-'+head[:8]);out.mkdir(exist_ok=False)
extra=['docs/验收规格.json','docs/F1/ATBindings.json','docs/sources/V1/平台产品设计 (2).md','docs/sources/V1/分阶段开发计划 (2).md','docs/F2/B0B2PlanningOnlyContract-20261019.md']
paths=subprocess.check_output(['git','ls-files','-z','src','tests','scripts','pyproject.toml','README.md',*extra],cwd=root).decode().rstrip('\x00').split('\x00')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pre={p:sha(root/p) for p in paths};(out/'shared-before.json').write_text(json.dumps(pre,indent=2)+'\n')
mirror=Path(tempfile.mkdtemp(prefix='pw-b0-b2-planning-frozen-'))/'mirror'
clone=subprocess.run(['git','clone','--quiet','--shared','--no-checkout',str(root),str(mirror)],capture_output=True,text=True)
(out/'clone-result.json').write_text(json.dumps(dict(exit_code=clone.returncode,stdout=clone.stdout,stderr=clone.stderr),indent=2)+'\n');assert clone.returncode==0
archive=subprocess.check_output(['git','archive',head,*paths],cwd=root)
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(mirror,filter='data')
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=mirror,text=True).strip()==head
mpre={p:sha(mirror/p) for p in paths};assert mpre==pre
(out/'mirror-before.json').write_text(json.dumps(mpre,indent=2)+'\n')
env={k:v for k,v in os.environ.items() if not k.startswith('PARKWEAVE_')}
env.update(PYTHONPATH=str(mirror/'src')+':'+str(mirror/'tests')+':'+str(mirror),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
child=out/'child.py'
child.write_text(r'''import sys,json,hashlib
from pathlib import Path
import pytest
out=Path(sys.argv[1]);mirror=Path.cwd()
class Record:
 def pytest_collection_finish(self,session):(out/'collection.json').write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\n')
 def pytest_runtest_logreport(self,report):
  with (out/'calls.jsonl').open('a') as f:f.write(json.dumps(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))+'\n')
 @pytest.hookimpl(hookwrapper=True)
 def pytest_fixture_setup(self,fixturedef,request):
  outcome=yield
  if fixturedef.argname=='preparation_fixture' and outcome.excinfo is None:
   value=outcome.get_result();p=out/'private-fixture-session-values.json'
   prior=json.loads(p.read_text()) if p.exists() else []
   p.write_text(json.dumps(sorted(set(prior)|set(value[2].values())),indent=2)+'\n');p.chmod(0o600)
code=pytest.main(sys.argv[2:],plugins=[Record()]);origins={}
for name,m in tuple(sys.modules.items()):
 p=getattr(m,'__file__',None)
 if p and (name.startswith(('parkweave','scripts.','test_')) or name in ('conftest','owned_connection_diagnostics')):
  p=Path(p).resolve()
  if p.is_file():origins[name]=dict(path=str(p),within_mirror=p.is_relative_to(mirror),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(out/'module-origins.json').write_text(json.dumps(origins,indent=2)+'\n');raise SystemExit(code)
''')
selectors=['tests/test_b0_b2_planning_only.py','tests/test_service_selection.py']
cmd=[str(root/'.venv/bin/python'),str(child),str(out),'-q','-c',str(mirror/'pyproject.toml'),'--rootdir='+str(mirror),'-p','no:cacheprovider',*selectors,'--basetemp='+str(mirror.parent/'pytest-temp'),'--junitxml='+str(out/'results.xml')]
(out/'command.json').write_text(json.dumps(dict(args=cmd,selectors=selectors,source_sha=head,full_regression=False,BC_rerun=False,old_risk_windows_rerun=False),indent=2)+'\n')
t=time.monotonic();started=datetime.now(timezone.utc).isoformat()
with (out/'pytest.stdout').open('w') as stdout,(out/'pytest.stderr').open('w') as stderr:
 p=subprocess.run(cmd,cwd=mirror,env=env,stdout=stdout,stderr=stderr,timeout=180)
post={p:sha(root/p) for p in paths};mpost={p:sha(mirror/p) for p in paths}
(out/'shared-after.json').write_text(json.dumps(post,indent=2)+'\n');(out/'mirror-after.json').write_text(json.dumps(mpost,indent=2)+'\n')
artifacts=list((mirror.parent/'pytest-temp').glob('*/planning-only'))
assert len(artifacts)<=1
if artifacts:
 shutil.copytree(artifacts[0],out/'planning-artifacts')
 token_file=artifacts[0]/'private-fixture-sessions.json'
 if token_file.exists():
  private=out/'private-fixture-session-values.json'
  tokens=set(json.loads(private.read_text())) if private.exists() else set()
  tokens.update(json.loads(token_file.read_text()))
  private.write_text(json.dumps(sorted(tokens),indent=2)+'\n');private.chmod(0o600)

result=dict(head=head,exit_code=p.returncode,inputs=len(pre),four_maps_equal=pre==post==mpre==mpost,
 started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),seconds=time.monotonic()-t,
 mirror=str(mirror),archive_sha256=hashlib.sha256(archive).hexdigest(),real_model_calls=0,
 independent_dynamic=0,full_business_application_attempts=0,AT31_guard_rerun=False,full_regression=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));print((out/'pytest.stdout').read_text()[-1800:]);raise SystemExit(p.returncode)
