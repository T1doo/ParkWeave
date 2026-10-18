import hashlib,io,json,os,pathlib,signal,subprocess,sys,tarfile,tempfile,time
repo=pathlib.Path('/workspace/ParkWeave');revision=sys.argv[1]
run=repo/'.runtime/at22-23-finite-20261018';out=run/(sys.argv[2] if len(sys.argv)>2 else 'root-final');out.mkdir(mode=0o700)
paths=['src','tests','scripts','pyproject.toml','docs/F1/ATBindings.json','docs/验收规格.json']
files=subprocess.check_output(['git','ls-tree','-rz','--name-only',revision,'--',*paths],cwd=repo).decode().rstrip('\0').split('\0')
raw=subprocess.check_output(['git','archive','--format=tar',revision,'--',*paths],cwd=repo)
base=pathlib.Path(tempfile.mkdtemp(prefix='pw-at22-root-',dir='/tmp'));mirror=base/'mirror';mirror.mkdir()
with tarfile.open(fileobj=io.BytesIO(raw)) as tar:tar.extractall(mirror,filter='data')
def hashes():return {p:hashlib.sha256((mirror/p).read_bytes()).hexdigest() for p in files}
pre=hashes();(out/'inputs-before.json').write_text(json.dumps(pre,sort_keys=True,indent=2)+'\n')
child=r'''import hashlib,json,pathlib,sys,time
import pgserver
out=pathlib.Path(sys.argv[1]);mirror=pathlib.Path(sys.argv[2]);servers=[]
original=pgserver.get_server
def observed(data,*args,**kwargs):
 server=original(data,*args,**kwargs)
 pid=server.get_pid()
 servers.append(dict(data=str(pathlib.Path(data).resolve()),pid=pid,cleanup_mode=kwargs.get('cleanup_mode'),started=pathlib.Path('/proc/'+str(pid)+'/stat').read_text().rsplit(')',1)[1].split()[19]))
 (out/'owned-pg.json').write_text(json.dumps(servers,indent=2)+'\n')
 return server
pgserver.get_server=observed
import pytest
nodes=['tests/test_synthetic_rule_readiness_api.py::test_at22_api_business_date_region_and_reviewed_version_keep_original_history','tests/test_acceptance_runner.py::test_fixed_bindings_complete_unique_and_safe']
if len(sys.argv)>3 and sys.argv[3]=='static-only':nodes=nodes[1:]
started=time.perf_counter()
code=pytest.main(['-q','-p','no:cacheprovider',*nodes,'--basetemp='+str(mirror.parent/'artifacts'),'--junitxml='+str(out/'results.xml')])
origins={}
for name,module in sorted(sys.modules.items()):
 if name=='parkweave' or name.startswith('parkweave.') or name.startswith('test_') or name=='conftest':
  p=getattr(module,'__file__',None)
  if p:
   p=pathlib.Path(p);relative=str(p.relative_to(mirror));origins[name]=dict(relative=relative,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
(out/'module-origins.json').write_text(json.dumps(origins,sort_keys=True,indent=2)+'\n')
(out/'result.json').write_text(json.dumps(dict(returncode=int(code),seconds=time.perf_counter()-started,nodes=nodes,actual_module_count=len(origins),actual_modules_all_from_mirror=True),indent=2)+'\n')
sys.exit(int(code))
'''
(out/'run-pytest.py').write_text(child)
sys.path.insert(0,str(repo/'src'));from parkweave.process_env import minimal_environment
runtime=base/'runtime';runtime.mkdir(mode=0o700)
env=minimal_environment(os.environ,PYTHONPATH=str(mirror)+':'+str(mirror/'src')+':'+str(mirror/'tests'),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',XDG_RUNTIME_DIR=str(runtime))
args=[str(repo/'.venv/bin/python'),'-B',str(out/'run-pytest.py'),str(out),str(mirror),sys.argv[3] if len(sys.argv)>3 else 'all']
(out/'invocation.json').write_text(json.dumps(dict(args=args,cwd=str(mirror),env=env,source_sha=revision),sort_keys=True,indent=2)+'\n')
started=time.perf_counter();p=subprocess.Popen(args,cwd=mirror,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
try:stdout,stderr=p.communicate(timeout=180)
except subprocess.TimeoutExpired:
 p.send_signal(signal.SIGINT);stdout,stderr=p.communicate(timeout=30)
(out/'stdout.txt').write_bytes(stdout);(out/'stderr.txt').write_bytes(stderr)
post=hashes();(out/'inputs-after.json').write_text(json.dumps(post,sort_keys=True,indent=2)+'\n')
settled=[]
if (out/'owned-pg.json').exists():
 for server in json.loads((out/'owned-pg.json').read_text()):
  stat=pathlib.Path('/proc/'+str(server['pid'])+'/stat')
  state=stat.read_text().rsplit(')',1)[1].split()[0] if stat.exists() else 'ABSENT'
  settled.append(dict(**server,state_after_test_python_exit=state,data_exists=pathlib.Path(server['data']).exists()))
metadata=dict(source_sha=revision,mirror=str(mirror),input_count=len(pre),input_changes=[p for p in files if pre[p]!=post[p]],archive_sha256=hashlib.sha256(raw).hexdigest(),returncode=p.returncode,outer_seconds=time.perf_counter()-started,source_tree=subprocess.check_output(['git','rev-parse',revision+':src'],cwd=repo).decode().strip(),tests_tree=subprocess.check_output(['git','rev-parse',revision+':tests'],cwd=repo).decode().strip(),owned_pg_settlement=settled)
(out/'metadata.json').write_text(json.dumps(metadata,sort_keys=True,indent=2)+'\n')
print(json.dumps(metadata));sys.exit(p.returncode)
