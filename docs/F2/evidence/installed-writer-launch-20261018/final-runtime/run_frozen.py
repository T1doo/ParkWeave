from pathlib import Path
from hashlib import sha256
from io import BytesIO
import ast,json,os,re,subprocess,tarfile,tempfile,time

R=Path.cwd();D=R/'.runtime/installed-writer-launch-20261018/final-v2';S='8ea6993e85982a9849f6999a19017ee5462b9874';B='edca7e871ffeac9a58d772f3745daf729c4ea5a5'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==S
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
selected=['src','pyproject.toml','tests/test_installed_writer_launch.py','tests/test_ordinary_runtime_write.py','tests/test_native_run_access_restricted_adapter.py','tests/test_native_run_access_trial_plan.py','tests/test_native_run_access_preflight.py','docs/F2/InstalledWriterLaunch-20261018.md']
raw=subprocess.check_output(['git','archive','--format=tar',S,'--',*selected]);mirror=Path(tempfile.mkdtemp(prefix='pw-root-installed-launch-'));payload={}
with tarfile.open(fileobj=BytesIO(raw)) as archive:
 for member in archive:
  if not member.isfile():continue
  assert not member.name.startswith('/') and '..' not in Path(member.name).parts
  data=archive.extractfile(member).read();payload[member.name]=data;p=mirror/member.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
assert len(payload)==186
def verify():
 for name,data in payload.items():
  assert (R/name).read_bytes()==data,('shared',name)
  assert (mirror/name).read_bytes()==data,('mirror',name)
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==S
 return dict(shared_drift=0,mirror_drift=0,source_sha=S)
pre=verify();manifest={n:sha256(raw).hexdigest() for n,raw in payload.items()}
(D/'frozen-inputs.json').write_text(json.dumps(dict(source_sha=S,mirror=str(mirror),input_sha256=manifest,pre=pre),indent=2)+'\n')
def parse(path,raw):
 return ast.parse(raw,filename=path)
def node(tree,name):
 names=name.split('.');body=tree.body
 for name in names:
  found=next(n for n in body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name==name);body=getattr(found,'body',[])
 return found
preserved={}
for path,names in {
 'src/parkweave/native_run_access_restricted_host.py':['RuntimeLayout','verified_record','_protected_bytes','_code_check','_dependencies_check','_imports_check','_identities_check','LinuxHost._claim','LinuxHost._spawn','LinuxHost._publish','LinuxHost.stop'],
 'src/parkweave/native_run_access_restricted_runtime.py':['RuntimeGuard','_RestrictedConnection','RestrictedStore','RestrictedEngine.execute','serve_restricted'],
}.items():
 old=parse(path,subprocess.check_output(['git','show',B+':'+path]));new=parse(path,payload[path])
 for name in names:
  assert ast.dump(node(old,name))==ast.dump(node(new,name)),(path,name)
  preserved[path+':'+name]=True
old=parse('old',subprocess.check_output(['git','show',B+':src/parkweave/native_run_access_restricted_host.py']));new=parse('new',payload['src/parkweave/native_run_access_restricted_host.py'])
assert ast.dump(ast.Module(body=node(old,'launch_request').body,type_ignores=[]))==ast.dump(ast.Module(body=node(new,'launch_request').body[1:],type_ignores=[]))
preserved['legacy_launch_request_after_new_exact_type_guard']=True
for path in ('src/parkweave/native_run_access_writer.py','src/parkweave/native_run_access.py','src/parkweave/native_run_access_activation.py','src/parkweave/ordinary_runtime_write.py','src/parkweave/web.html','tests/test_native_run_access_restricted_adapter.py','tests/test_native_run_access_trial_plan.py','tests/test_native_run_access_preflight.py','tests/test_ordinary_runtime_write.py'):
 assert subprocess.check_output(['git','show',B+':'+path])==payload[path],path
 preserved[path+':byte_identical']=True
(D/'preserved-contracts.json').write_text(json.dumps(dict(baseline_sha=B,source_sha=S,preserved=preserved,scope='Static AST/byte equality; not OS/PG execution'),indent=2)+'\n')
env={k:v for k,v in os.environ.items() if not k.startswith('PARKWEAVE_')};env.update(PYTHONPATH=str(mirror/'src'),PYTHONDONTWRITEBYTECODE='1')
results=[]
for label,script,count in [('installed','test_installed_writer_launch.py',26),('factory','test_ordinary_runtime_write.py',24)]:
 tree=parse(script,payload['tests/'+script]);expected={cls.name+'.'+m.name for cls in tree.body if isinstance(cls,ast.ClassDef) for m in cls.body if isinstance(m,ast.FunctionDef) and m.name.startswith('test_')};assert len(expected)==count
 argv=[str(R/'.venv/bin/python'),'-B',str(mirror/'tests'/script)];start=time.monotonic();p=subprocess.run(argv,cwd=mirror,env=env,capture_output=True,text=True,timeout=60);elapsed=time.monotonic()-start
 (D/('frozen-'+label+'.stdout')).write_text(p.stdout);(D/('frozen-'+label+'.stderr')).write_text(p.stderr)
 ids=re.findall(r'^test_\w+ \(__main__\.([\w.]+)\) \.\.\.',p.stderr,re.M);item=dict(label=label,argv=argv,exit_code=p.returncode,elapsed_seconds=elapsed,actual_ids=ids,expected_ids=sorted(expected),passed=len(ids) if p.returncode==0 else None);results.append(item)
 (D/'frozen-progress.json').write_text(json.dumps(results,indent=2)+'\n')
 assert p.returncode==0 and len(ids)==count and set(ids)==expected and p.stderr.rstrip().endswith('OK') and f'Ran {count} tests in ' in p.stderr,item
post=verify();result=dict(source_sha=S,baseline_sha=B,src_tree=subprocess.check_output(['git','rev-parse',S+':src'],text=True).strip(),tests_tree=subprocess.check_output(['git','rev-parse',S+':tests'],text=True).strip(),mirror=str(mirror),python=subprocess.check_output([str(R/'.venv/bin/python'),'--version'],text=True).strip(),input_files=186,pre=pre,post=post,unique_methods=50,installed_new_methods=19,legacy_assertion_wrappers=7,ordinary_factory_methods=24,failed=0,errors=0,skipped=0,results=results,independent_overlap='ALL_50',scope='PURE_OFFLINE_PROTECTED_OBSERVATION_FD_PROCESS_DI_AND_MEMORY_FACTORY_TESTS',real_DB_IPC_Popen_memfd_installation_issuance_permission_activation_browser_models=0,runtime_capability='CURRENT_ENV_UNSUPPORTED; positive constants/FD/processes are DI only',preserved_contracts='preserved-contracts.json')
(D/'frozen-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='results'}))
