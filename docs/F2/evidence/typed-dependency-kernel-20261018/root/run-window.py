from pathlib import Path
from datetime import datetime,timezone
import subprocess,hashlib,json,tarfile,tempfile,io,os,time,sys
root=Path('/workspace/ParkWeave');run=root/'.runtime/typed-dependency-kernel-20261018';name=sys.argv[1]
out=run/name;out.mkdir(exist_ok=False)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
paths=subprocess.check_output(['git','ls-files','-z','src','tests','scripts','pyproject.toml','docs/F1/ATBindings.json','docs/验收规格.json','docs/F2/TypedDependencyKernelContract-20261018.md','docs/F2/UnifiedSourcePropagationOracle-20261016.json'],cwd=root).split(b'\0');paths=[p.decode() for p in paths if p]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
pre={p:sha(root/p) for p in paths};(out/'inputs-before.json').write_text(json.dumps(pre,sort_keys=True,indent=2)+'\n')
archive=subprocess.check_output(['git','archive',head,*paths],cwd=root)
mirror=Path(tempfile.mkdtemp(prefix='pw-typed-kernel-'))/'mirror';mirror.mkdir()
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(mirror,filter='data')
assert all(sha(mirror/p)==h for p,h in pre.items())
nodes=sys.argv[2:] or ['tests/test_dependency_graph.py']
child=out/'child.py'
child.write_text('''import sys,json,hashlib\nfrom pathlib import Path\nimport pytest\nargs=sys.argv[1:]\nclass Record:\n def pytest_collection_finish(self,session):\n  self.nodes=[i.nodeid for i in session.items]\n  Path('collection.json').write_text(json.dumps(self.nodes,indent=2)+'\\n')\np=Record();code=pytest.main(args,plugins=[p])\norigins={}\nfor name,m in tuple(sys.modules.items()):\n f=getattr(m,'__file__',None)\n if f and (name.startswith('parkweave') or name.startswith('test_dependency_graph')):\n  path=Path(f).resolve()\n  if path.is_file():origins[name]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())\nPath('module-origins.json').write_text(json.dumps(origins,indent=2)+'\\n')\nraise SystemExit(code)\n''')
cmd=[str(root/'.venv/bin/python'),str(child),'-q','-p','no:cacheprovider',*nodes,'--junitxml='+str(out/'results.xml')]
env=os.environ.copy();env['PYTHONPATH']=str(mirror/'src')+':'+str(mirror/'tests')+':'+str(mirror);env['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1';env['PYTHONDONTWRITEBYTECODE']='1'
started=datetime.now(timezone.utc).isoformat();t=time.monotonic()
with (out/'stdout.txt').open('w') as stdout,(out/'stderr.txt').open('w') as stderr:
 try:p=subprocess.run(cmd,cwd=mirror,env=env,stdout=stdout,stderr=stderr,timeout=90);code=p.returncode
 except subprocess.TimeoutExpired:code=124
elapsed=time.monotonic()-t
post={p:sha(root/p) for p in paths};mpost={p:sha(mirror/p) for p in paths}
(out/'inputs-after.json').write_text(json.dumps(post,sort_keys=True,indent=2)+'\n')
for rel in ['collection.json','module-origins.json']:
 if (mirror/rel).exists():(out/rel).write_bytes((mirror/rel).read_bytes())
report=dict(head=head,nodes=nodes,command=cmd,started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat(),outer_seconds=elapsed,exit_code=code,mirror=str(mirror),inputs=len(pre),shared_drift=[p for p in pre if pre[p]!=post[p]],mirror_drift=[p for p in pre if pre[p]!=mpost[p]],archive_sha256=hashlib.sha256(archive).hexdigest(),pg_requested=False,browser_requested=False)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report));print((out/'stdout.txt').read_text()[-6000:]);print((out/'stderr.txt').read_text()[-1500:])
