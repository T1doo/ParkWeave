from pathlib import Path
import hashlib,io,json,os,subprocess,tarfile,tempfile,time
root=Path('/workspace/ParkWeave');r=root/'.runtime/ordinary-reuse-user-flow-20261018'
assert not (r/'frozen-freeze.json').exists()
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
contracts=list(json.loads((root/'.runtime/original-collaboration-dom-20261018/verified-freeze.json').read_text())['contracts'])+['docs/F2/MaterialReuseDOM-20261018.md']
paths=subprocess.check_output(['git','ls-files','src','tests','scripts','pyproject.toml',*contracts],cwd=root,text=True).splitlines()
expected={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in paths}
outer=Path(tempfile.mkdtemp(prefix='pw-material-reuse-frozen-'+sha[:7]+'-'));mirror=outer/'mirror';mirror.mkdir()
archive=subprocess.check_output(['git','archive',sha,'src','tests','scripts','pyproject.toml',*contracts],cwd=root)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(mirror,filter='data')
assert all(hashlib.sha256((mirror/name).read_bytes()).hexdigest()==digest for name,digest in expected.items())
selected=json.loads((r/'selected-tests.json').read_text())
env={name:os.environ[name] for name in ('PATH','LANG','LC_ALL','TZ','TEMP','TMP','TMPDIR') if name in os.environ};env.update(PYTHONPATH=os.pathsep.join(str(mirror/name) for name in ('tests','src','.')),PYTHONDONTWRITEBYTECODE='1')
command=[str(root/'.venv/bin/python'),'-B','-m','pytest','--collect-only','-q','-p','no:cacheprovider','--rootdir='+str(mirror),*selected]
collected=subprocess.run(command,cwd=mirror,env=env,text=True,capture_output=True)
(r/'frozen-collection.txt').write_text(collected.stdout+collected.stderr)
assert collected.returncode==0,collected.stderr
nodes=[line for line in collected.stdout.splitlines() if line.startswith('tests/') and '::' in line and ' ' not in line]
assert len(nodes)==len(set(nodes))==43,len(nodes)
freeze=dict(source_sha=sha,source_tree=subprocess.check_output(['git','rev-parse',sha+':src'],cwd=root,text=True).strip(),tests_tree=subprocess.check_output(['git','rev-parse',sha+':tests'],cwd=root,text=True).strip(),input_count=len(expected),contracts={name:expected[name] for name in contracts},outer=str(outer),mirror=str(mirror),nodes=nodes,automatic_retries=0)
(r/'frozen-inputs.json').write_text(json.dumps(expected,indent=2)+'\n');(r/'frozen-freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
print(json.dumps({key:value for key,value in freeze.items() if key!='nodes'},indent=2))
