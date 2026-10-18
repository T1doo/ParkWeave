from pathlib import Path
from datetime import datetime,timezone
import subprocess,hashlib,json,tarfile,tempfile,io,os,time,sys
root=Path('/workspace/ParkWeave');run=root/'.runtime/at28-resource-observation-20261018';out=run/sys.argv[1];out.mkdir(exist_ok=False)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
baseline=json.loads((run/'independent/baseline-inputs.json').read_text())
paths=sorted(set(baseline['files'])|{'docs/F2/AT28CurrentResourceObservationContract-20261018.md','tests/test_at28_resource_observation.py','tests/at28_resource_observation_html.js'})
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pre={p:sha(root/p) for p in paths};(out/'shared-before.json').write_text(json.dumps(pre,sort_keys=True,indent=2)+'\n')
archive=subprocess.check_output(['git','archive',head,*paths],cwd=root)
mirror=Path(tempfile.mkdtemp(prefix='pw-at28-resource-observation-'))/'mirror';mirror.mkdir()
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(mirror,filter='data')
mpre={p:sha(mirror/p) for p in paths};assert pre==mpre
(out/'mirror-before.json').write_text(json.dumps(mpre,sort_keys=True,indent=2)+'\n')
child=out/'child.py';child.write_text('''import sys,json,hashlib\nfrom pathlib import Path\nimport pytest\nout=Path(sys.argv[1]);mirror=Path.cwd()\ntokens=set()\nclass Record:\n @pytest.hookimpl(hookwrapper=True)\n def pytest_fixture_setup(self,fixturedef,request):\n  outcome=yield\n  if outcome.excinfo:return\n  value=outcome.get_result()\n  def collect(value):\n   if isinstance(value,dict) and isinstance(value.get('tokens'),dict):tokens.update(v for v in value['tokens'].values() if isinstance(v,str) and len(v)==43)\n   if isinstance(value,tuple):\n    if len(value)>2 and isinstance(value[2],dict):tokens.update(v for v in value[2].values() if isinstance(v,str) and len(v)==43)\n    for item in value:\n     if isinstance(item,tuple):collect(item)\n  collect(value)\n def pytest_collection_finish(self,session):\n  (out/'collection.json').write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\\n')\n def pytest_runtest_logreport(self,report):\n  with (out/'calls.jsonl').open('a') as f:f.write(json.dumps(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))+'\\n')\ncode=pytest.main(sys.argv[2:],plugins=[Record()])\n(out/'private-synthetic-tokens.json').write_text(json.dumps(sorted(tokens))+'\\n')\norigins={}\nfor name,m in tuple(sys.modules.items()):\n file=getattr(m,'__file__',None)\n if file and (name.startswith('parkweave') or name.startswith('scripts.') or name.startswith('test_') or name in ('owned_connection_diagnostics','ordinary_case_step_support','service_release_acceptance_support','conftest')):\n  path=Path(file).resolve()\n  if path.is_file():origins[name]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),within_mirror=path.is_relative_to(mirror))\n(out/'module-origins.json').write_text(json.dumps(origins,indent=2)+'\\n')\nraise SystemExit(code)\n''')
nodes=sys.argv[2:] or ['tests/test_at28_resource_observation.py',
 'tests/test_resource_alternative_times_offline.py::test_actual_resource_suggestions_with_offline_doubles[original_flow_explicit]',
 'tests/test_resource_holds.py::test_catalog_and_anonymous_availability_do_not_expose_other_enterprise_hold',
 'tests/test_acceptance_runner.py::test_fixed_bindings_complete_unique_and_safe']
cmd=[str(root/'.venv/bin/python'),str(child),str(out),'-q','-c',str(mirror/'pyproject.toml'),'--rootdir='+str(mirror),'-p','no:cacheprovider',*nodes,'--basetemp='+str(mirror.parent/'pytest-temp'),'--junitxml='+str(out/'results.xml')]
env=os.environ.copy();env.update(PYTHONPATH=str(mirror/'src')+':'+str(mirror/'tests')+':'+str(mirror),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1',PARKWEAVE_CASE_STEP_NOTICE_EVIDENCE=str(out/'notice-html'),PARKWEAVE_CASE_STEP_EVIDENCE=str(out/'isolated-html'),PARKWEAVE_ORDINARY_CASE_STEP_EVIDENCE=str(out/'ordinary-artifacts'))
started=datetime.now(timezone.utc).isoformat();t=time.monotonic()
with (out/'stdout.txt').open('w') as stdout,(out/'stderr.txt').open('w') as stderr:
 try:p=subprocess.run(cmd,cwd=mirror,env=env,stdout=stdout,stderr=stderr,timeout=900);code=p.returncode
 except subprocess.TimeoutExpired:code=124
import shutil
for folder in (mirror.parent/'pytest-temp').glob('test_*'):
 if folder.is_dir() and not folder.is_symlink():
  for artifact in folder.rglob('*'):
   if artifact.is_file() and artifact.suffix in ('.json','.jsonl','.log','.stdout','.stderr','.txt'):
    target=out/'process-artifacts'/folder.name/artifact.relative_to(folder)
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(artifact,target)
post={p:sha(root/p) for p in paths};mpost={p:sha(mirror/p) for p in paths}
(out/'shared-after.json').write_text(json.dumps(post,sort_keys=True,indent=2)+'\n');(out/'mirror-after.json').write_text(json.dumps(mpost,sort_keys=True,indent=2)+'\n')
report=dict(head=head,nodes=nodes,command=cmd,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),outer_seconds=time.monotonic()-t,exit_code=code,mirror=str(mirror),inputs=len(pre),shared_drift=[p for p in pre if pre[p]!=post[p]],mirror_drift=[p for p in pre if pre[p]!=mpost[p]],archive_sha256=hashlib.sha256(archive).hexdigest(),pg_requested=True,actual_http_asgi=True,nodevm_requested=True,browser_requested=False,ordinary_api_process=True,worker_requested=False,fixture_local_finish_selected=False,physical_pg_restart_selected=False,two_scope_same_database=False,isolated_template_positive=False,ordinary_formal_success=False,previous_same_enterprise_AB_selected=False,AT28_observation_only=True,whole_AT28_pass=False)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));print((out/'stdout.txt').read_text()[-5000:]);print((out/'stderr.txt').read_text()[-1000:]);raise SystemExit(code)
