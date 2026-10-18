from pathlib import Path
import hashlib,io,json,os,subprocess,tarfile,tempfile,sys
R=Path.cwd();D=R/'.runtime/at21-synthetic-readiness-20261018';label=sys.argv[1];assert not (D/(label+'-freeze.json')).exists()
head=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert not subprocess.check_output(['git','status','--porcelain'])
paths=['src','tests','scripts','pyproject.toml','docs/验收规格.json','docs/F1/ATBindings.json']
expected={p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in subprocess.check_output(['git','ls-files',*paths],text=True).splitlines()}
outer=Path(tempfile.mkdtemp(prefix='pw-at21-'+label+'-'+head[:7]+'-'));mirror=outer/'mirror';mirror.mkdir();blob=subprocess.check_output(['git','archive',head,'--',*paths]);tarfile.open(fileobj=io.BytesIO(blob)).extractall(mirror,filter='data')
assert all(hashlib.sha256((mirror/p).read_bytes()).hexdigest()==sha for p,sha in expected.items())
selected=json.loads((D/'case-plan.json').read_text())['selectors'];env={k:os.environ[k] for k in ['PATH','LANG','LC_ALL','TZ','TEMP','TMP','TMPDIR'] if k in os.environ};env.update(PYTHONPATH=os.pathsep.join(str(mirror/p) for p in ['tests','src','.']),PYTHONDONTWRITEBYTECODE='1')
argv=[str(R/'.venv/bin/python'),'-B','-m','pytest','--collect-only','-q','-p','no:cacheprovider','--rootdir='+str(mirror),*selected];p=subprocess.run(argv,cwd=mirror,env=env,text=True,capture_output=True,timeout=60);(D/(label+'-collection.stdout')).write_text(p.stdout);(D/(label+'-collection.stderr')).write_text(p.stderr);assert p.returncode==0
nodes=[line for line in p.stdout.splitlines() if line.startswith('tests/') and '::' in line and ' ' not in line];assert len(nodes)==len(set(nodes))==5,nodes
freeze=dict(source_sha=head,source_tree=subprocess.check_output(['git','rev-parse','HEAD:src'],text=True).strip(),tests_tree=subprocess.check_output(['git','rev-parse','HEAD:tests'],text=True).strip(),mirror=str(mirror),outer=str(outer),input_count=len(expected),nodes=nodes,archive_sha256=hashlib.sha256(blob).hexdigest(),automatic_retries=0)
(D/(label+'-inputs.json')).write_text(json.dumps(expected,indent=2)+'\n');(D/(label+'-freeze.json')).write_text(json.dumps(freeze,indent=2)+'\n');print(json.dumps(freeze))
