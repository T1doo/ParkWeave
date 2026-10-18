from pathlib import Path
from hashlib import sha256
from io import BytesIO
import ast,json,os,re,subprocess,tarfile,tempfile,time

R=Path.cwd();D=R/'.runtime/ordinary-activation-ui-20261018';S='25a650b8885f14f8c904b5da50e51c41cbe4d944'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==S
assert not subprocess.check_output(['git','status','--porcelain'],text=True).strip()
selected=['src','pyproject.toml','tests/test_ordinary_runtime_write.py','tests/test_native_run_access_activation_offline.py','tests/native_run_access_activation_offline.js','tests/native_run_access_offline.js','docs/F2/OrdinaryActivationUI-20261018.md']
raw=subprocess.check_output(['git','archive','--format=tar',S,'--',*selected])
mirror=Path(tempfile.mkdtemp(prefix='pw-root-ordinary-activation-'));payload={}
with tarfile.open(fileobj=BytesIO(raw)) as archive:
 for member in archive:
  if not member.isfile():continue
  assert not member.name.startswith('/') and '..' not in Path(member.name).parts
  data=archive.extractfile(member).read();payload[member.name]=data;p=mirror/member.name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
assert len(payload)==185
manifest={name:sha256(data).hexdigest() for name,data in payload.items()}
def verify():
 drift=[]
 for name,data in payload.items():
  if (R/name).read_bytes()!=data:drift.append('shared:'+name)
  if (mirror/name).read_bytes()!=data:drift.append('mirror:'+name)
 assert not drift,drift
 assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==S
 return dict(shared_drift=0,mirror_drift=0,source_sha=S)
pre=verify();(D/'frozen-inputs.json').write_text(json.dumps(dict(source_sha=S,mirror=str(mirror),sha256=manifest,pre=pre),indent=2)+'\n')
ordinary_ast=ast.parse(payload['tests/test_ordinary_runtime_write.py'])
ordinary={cls.name+'.'+method.name for cls in ordinary_ast.body if isinstance(cls,ast.ClassDef) for method in cls.body if isinstance(method,ast.FunctionDef) and method.name.startswith('test_')}
ui_ast=ast.parse(payload['tests/test_native_run_access_activation_offline.py']);modes={}
for n in ui_ast.body:
 if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('ACTIVATION_MODES','LEGACY_MODES'):modes[n.targets[0].id]=ast.literal_eval(n.value)
ui={'ActivationUI.test_'+m for m in modes['ACTIVATION_MODES']}|{'ExistingNativeUI.test_'+m for m in modes['LEGACY_MODES']}
assert len(ordinary)==24 and len(ui)==45
env={k:v for k,v in os.environ.items() if not k.startswith('PARKWEAVE_')};env.update(PYTHONPATH=str(mirror/'src'),PYTHONDONTWRITEBYTECODE='1')
results=[]
for label,script,expected in [('writer','test_ordinary_runtime_write.py',ordinary),('ui','test_native_run_access_activation_offline.py',ui)]:
 argv=[str(R/'.venv/bin/python'),'-B',str(mirror/'tests'/script)];start=time.monotonic();p=subprocess.run(argv,cwd=mirror,env=env,capture_output=True,text=True,timeout=60);elapsed=time.monotonic()-start
 (D/('frozen-'+label+'.stdout')).write_text(p.stdout);(D/('frozen-'+label+'.stderr')).write_text(p.stderr)
 ids=re.findall(r'^test_\w+ \(__main__\.([\w.]+)\) \.\.\.',p.stderr,re.M)
 result=dict(label=label,argv=argv,exit_code=p.returncode,elapsed_seconds=elapsed,actual_ids=ids,expected_ids=sorted(expected),passed=len(ids) if p.returncode==0 else None)
 results.append(result);(D/'frozen-progress.json').write_text(json.dumps(results,indent=2)+'\n')
 assert p.returncode==0 and len(ids)==len(expected) and set(ids)==expected and p.stderr.rstrip().endswith('OK') and f'Ran {len(expected)} tests in ' in p.stderr,result
post=verify()
result=dict(source_sha=S,src_tree=subprocess.check_output(['git','rev-parse',S+':src'],text=True).strip(),tests_tree=subprocess.check_output(['git','rev-parse',S+':tests'],text=True).strip(),mirror=str(mirror),python=subprocess.check_output([str(R/'.venv/bin/python'),'--version'],text=True).strip(),node=subprocess.check_output(['node','--version'],text=True).strip(),input_files=185,input_manifest='frozen-inputs.json',pre=pre,post=post,unique_methods=69,new_activation_methods=33,legacy_ui_methods=12,writer_methods=24,failed=0,errors=0,skipped=0,results=results,independent_overlap='ALL_69',scope='PURE_OFFLINE_MEMORY_CONNECTION_PROTECTED_BINDER_RPC_DI_AND_FULL_PAGE_NODEVM_MOCK_FETCH',real_database_ipc_services_browser_installation_activation_authority_models=0)
(D/'frozen-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='results'}))
