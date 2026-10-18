from pathlib import Path
from datetime import datetime,timezone
import subprocess,hashlib,json,tarfile,tempfile,io,os,time,sys
root=Path('/workspace/ParkWeave');run=root/'.runtime/case-step-notices-20261018';out=run/sys.argv[1];out.mkdir(exist_ok=False)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
paths=subprocess.check_output(['git','ls-files','-z','src','tests','scripts','pyproject.toml','docs/F1/ATBindings.json','docs/验收规格.json','docs/F2/TypedDependencyKernelContract-20261018.md','docs/F2/TypedDependencyOpportunityPreviewContract-20261018.md','docs/F2/ResourceQueryMemberGraphContract-20261018.md','docs/F2/ServiceCatalogQueryDependencyContract-20261018.md','docs/F2/CaseStepAssignmentContract-20261018.md','docs/F2/CaseStepNoticeContract-20261018.md','docs/F2/UnifiedSourcePropagationOracle-20261016.json'],cwd=root).split(b'\0');paths=[p.decode() for p in paths if p]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pre={p:sha(root/p) for p in paths};(out/'shared-before.json').write_text(json.dumps(pre,sort_keys=True,indent=2)+'\n')
archive=subprocess.check_output(['git','archive',head,*paths],cwd=root)
mirror=Path(tempfile.mkdtemp(prefix='pw-case-step-notices-'))/'mirror';mirror.mkdir()
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(mirror,filter='data')
mpre={p:sha(mirror/p) for p in paths};assert pre==mpre
(out/'mirror-before.json').write_text(json.dumps(mpre,sort_keys=True,indent=2)+'\n')
child=out/'child.py';child.write_text('''import sys,json,hashlib\nfrom pathlib import Path\nimport pytest\nout=Path(sys.argv[1]);mirror=Path.cwd()\nclass Record:\n def pytest_collection_finish(self,session):\n  (out/'collection.json').write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\\n')\n def pytest_runtest_logreport(self,report):\n  with (out/'calls.jsonl').open('a') as f:f.write(json.dumps(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome,duration=report.duration))+'\\n')\ncode=pytest.main(sys.argv[2:],plugins=[Record()])\norigins={}\nfor name,m in tuple(sys.modules.items()):\n file=getattr(m,'__file__',None)\n if file and (name.startswith('parkweave') or name.startswith('test_') or name=='owned_connection_diagnostics'):\n  path=Path(file).resolve()\n  if path.is_file():origins[name]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),within_mirror=path.is_relative_to(mirror))\n(out/'module-origins.json').write_text(json.dumps(origins,indent=2)+'\\n')\nraise SystemExit(code)\n''')
nodes=sys.argv[2:] or ['tests/test_case_step_notices.py','tests/test_dispatch_notices.py','tests/test_dispatch_notice_page_offline.py::test_original_notice_section_offline_pagination[current_denied]','tests/test_dispatch_notice_page_offline.py::test_original_notice_section_offline_pagination[stale_denied]','tests/test_dispatch_notice_page_offline.py::test_original_notice_section_offline_pagination[identity_aba]']
cmd=[str(root/'.venv/bin/python'),str(child),str(out),'-q','-c',str(mirror/'pyproject.toml'),'--rootdir='+str(mirror),'-p','no:cacheprovider',*nodes,'--basetemp='+str(mirror.parent/'pytest-temp'),'--junitxml='+str(out/'results.xml')]
env=os.environ.copy();env.update(PYTHONPATH=str(mirror/'src')+':'+str(mirror/'tests')+':'+str(mirror),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1',PARKWEAVE_CASE_STEP_NOTICE_EVIDENCE=str(out/'html'))
started=datetime.now(timezone.utc).isoformat();t=time.monotonic()
with (out/'stdout.txt').open('w') as stdout,(out/'stderr.txt').open('w') as stderr:
 try:p=subprocess.run(cmd,cwd=mirror,env=env,stdout=stdout,stderr=stderr,timeout=900);code=p.returncode
 except subprocess.TimeoutExpired:code=124
post={p:sha(root/p) for p in paths};mpost={p:sha(mirror/p) for p in paths}
(out/'shared-after.json').write_text(json.dumps(post,sort_keys=True,indent=2)+'\n');(out/'mirror-after.json').write_text(json.dumps(mpost,sort_keys=True,indent=2)+'\n')
report=dict(head=head,nodes=nodes,command=cmd,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),outer_seconds=time.monotonic()-t,exit_code=code,mirror=str(mirror),inputs=len(pre),shared_drift=[p for p in pre if pre[p]!=post[p]],mirror_drift=[p for p in pre if pre[p]!=mpost[p]],archive_sha256=hashlib.sha256(archive).hexdigest(),pg_requested=True,actual_http_asgi=True,nodevm_full_html=True,browser_requested=False)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));print((out/'stdout.txt').read_text()[-5000:]);print((out/'stderr.txt').read_text()[-1000:]);raise SystemExit(code)
