from pathlib import Path
from hashlib import sha256
from io import BytesIO
import ast, json, os, re, shutil, subprocess, sys, tarfile, time
ROOT=Path('/workspace/ParkWeave')
SHA='25a650b8885f14f8c904b5da50e51c41cbe4d944'
OUT=Path(__file__).resolve().parent
BASE=Path(sys.argv[1]).resolve()
MIRROR=BASE/'mirror'
MIRROR.mkdir(exist_ok=False)
PATHS=['src','pyproject.toml','tests/test_ordinary_runtime_write.py','tests/test_native_run_access_activation_offline.py','tests/native_run_access_activation_offline.js','tests/native_run_access_offline.js','docs/F2/OrdinaryActivationUI-20261018.md']
def save(name,value):
 (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def git(*args):
 return subprocess.check_output(['git',*args],cwd=ROOT)
def hx(data):
 return sha256(data).hexdigest()
head_pre=git('rev-parse','HEAD').decode().strip()
assert head_pre==SHA,head_pre
archive=git('archive','--format=tar',SHA,'--',*PATHS)
(OUT/'archive.tar').write_bytes(archive)
entries={}
with tarfile.open(fileobj=BytesIO(archive),mode='r:') as tf:
 for m in tf.getmembers():
  path=Path(m.name)
  assert not path.is_absolute() and '..' not in path.parts,m.name
  if m.isdir():continue
  assert m.isfile(),m.name
  data=tf.extractfile(m).read();entries[m.name]=data
  dest=MIRROR/m.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
objects=[]
for record in git('ls-tree','-r','-z',SHA,'--',*PATHS).split(b'\0'):
 if not record:continue
 prefix,name=record.split(b'\t',1);mode,kind,oid=prefix.split()
 assert kind==b'blob' and mode in (b'100644',b'100755'),record
 objects.append((name.decode(),oid.decode()))
assert len(objects)==len(entries)==185,(len(objects),len(entries))
assert sum(p.startswith('src/') for p in entries)==179
batch=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,input=''.join(oid+'\n' for _,oid in objects).encode(),stdout=subprocess.PIPE,check=True).stdout
stream=BytesIO(batch)
for name,oid in objects:
 header=stream.readline().split();assert header[:2]==[oid.encode(),b'blob']
 data=stream.read(int(header[2]));assert stream.read(1)==b'\n'
 assert data==entries[name],name
assert not stream.read()
expected={p:hx(data) for p,data in sorted(entries.items())}
def check(base):
 got={p:hx((base/p).read_bytes()) for p in expected}
 return {'inputs':len(got),'drift':[p for p in expected if got[p]!=expected[p]],'sha256_by_path':got}
shared_pre=check(ROOT);mirror_pre=check(MIRROR)
save('shared-pre.json',shared_pre);save('mirror-pre.json',mirror_pre)
assert not shared_pre['drift'] and not mirror_pre['drift']
save('frozen-inputs.json',{'source_sha':SHA,'src_tree':git('rev-parse',SHA+':src').decode().strip(),'tests_tree':git('rev-parse',SHA+':tests').decode().strip(),'inputs':expected})
head_after_pre=git('rev-parse','HEAD').decode().strip();assert head_after_pre==SHA
save('preparation.json',{'source_sha':SHA,'head_pre':head_pre,'head_after_pre':head_after_pre,'archive_sha256':hx(archive),'inputs':185,'src_files':179,'paths':PATHS,'mirror':str(MIRROR),'evidence':str(OUT),'contract_sha256':expected['docs/F2/OrdinaryActivationUI-20261018.md'],'shared_pre_drift':0,'mirror_pre_drift':0})
env={k:v for k,v in os.environ.items() if not k.startswith('PARKWEAVE')}
removed=sorted(k for k in os.environ if k.startswith('PARKWEAVE'))
env.update(PYTHONPATH=str(MIRROR/'src'),PYTHONDONTWRITEBYTECODE='1')
node=shutil.which('node');assert node
node_version=subprocess.run([node,'--version'],cwd=MIRROR,env=env,capture_output=True,text=True,check=True)
save('versions.json',{'python_executable':sys.executable,'python_version':sys.version,'node_path':node,'node_realpath':str(Path(node).resolve()),'node_version':node_version.stdout.strip(),'node_version_stderr':node_version.stderr})
ordinary_tree=ast.parse((MIRROR/'tests/test_ordinary_runtime_write.py').read_text())
ordinary_expected=sorted('__main__.OrdinaryWriteTests.'+n.name for cls in ordinary_tree.body if isinstance(cls,ast.ClassDef) and cls.name=='OrdinaryWriteTests' for n in cls.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_'))
activation_tree=ast.parse((MIRROR/'tests/test_native_run_access_activation_offline.py').read_text())
mode_sets={}
for n in activation_tree.body:
 if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in ('ACTIVATION_MODES','LEGACY_MODES'):
  mode_sets[n.targets[0].id]=ast.literal_eval(n.value)
activation_expected=sorted(['__main__.ActivationUI.test_'+m for m in mode_sets['ACTIVATION_MODES']]+['__main__.ExistingNativeUI.test_'+m for m in mode_sets['LEGACY_MODES']])
assert len(ordinary_expected)==24 and len(activation_expected)==45
assert len(mode_sets['ACTIVATION_MODES'])==33 and len(mode_sets['LEGACY_MODES'])==12
all_expected=sorted(ordinary_expected+activation_expected);assert len(set(all_expected))==69
save('expected-test-ids.json',{'ordinary':ordinary_expected,'activation':activation_expected,'all':all_expected,'count':69})
def parse(text):
 actual=[];pending=None
 for line in text.splitlines():
  m=re.match(r'^(test_\w+) \(([^)]+)\) \.\.\. (.*)$',line)
  if m:
   assert pending is None,pending
   pending={'method':m[1],'id':m[2]};tail=m[3]
  else:tail=line
  if pending is not None and (tail in ('ok','FAIL','ERROR') or tail.startswith('skipped')):
   pending['result']=tail;actual.append(pending);pending=None
 assert pending is None,pending
 return actual
results=[]
outer_start=time.monotonic()
for label,rel,want in [('ordinary','tests/test_ordinary_runtime_write.py',ordinary_expected),('activation','tests/test_native_run_access_activation_offline.py',activation_expected)]:
 argv=['/workspace/ParkWeave/.venv/bin/python','-B',str(MIRROR/rel)]
 save(label+'-invocation.json',{'argv':argv,'cwd':str(MIRROR),'env_whitelist':{k:env[k] for k in ['PYTHONPATH','PYTHONDONTWRITEBYTECODE']},'removed_environment_names':removed,'automatic_retries':0,'framework':'direct unittest.main(verbosity=2), no pytest/conftest','expected_ids':want})
 start=time.monotonic()
 with (OUT/(label+'.stdout.txt')).open('wb') as stdout,(OUT/(label+'.stderr.txt')).open('wb') as stderr:
  run=subprocess.run(argv,cwd=MIRROR,env=env,stdout=stdout,stderr=stderr)
 elapsed=time.monotonic()-start
 raw=(OUT/(label+'.stderr.txt')).read_text()
 actual=parse(raw)
 match=re.search(r'^Ran (\d+) tests in ([0-9.]+)s$',raw,re.M)
 row={'label':label,'source_sha':SHA,'exit_code':run.returncode,'outer_elapsed_seconds':elapsed,'reported_count':int(match[1]) if match else None,'unittest_elapsed_seconds':float(match[2]) if match else None,'actual_count':len(actual),'passed':sum(x['result']=='ok' for x in actual),'failures':sum(x['result']=='FAIL' for x in actual),'errors':sum(x['result']=='ERROR' for x in actual),'skipped':sum(x['result'].startswith('skipped') for x in actual),'actual_ids_equal_expected':sorted(x['id'] for x in actual)==want,'actual_tests':actual,'child_reaped':True}
 save(label+'-result.json',row);results.append(row)
actual_ids=sorted(x['id'] for r in results for x in r['actual_tests'])
save('actual-test-ids.json',{'ids':actual_ids,'unique':len(set(actual_ids)),'count':len(actual_ids),'expected_equal':actual_ids==all_expected})
modules=['parkweave','parkweave.api','parkweave.ordinary_runtime_write','parkweave.ordinary_runtime_read','parkweave.native_run_access','parkweave.native_run_access_writer','parkweave.native_run_access_restricted_host','parkweave.native_run_access_activation']
origin_code="import importlib,json;from pathlib import Path;from hashlib import sha256;names="+repr(modules)+";mods={n:importlib.import_module(n) for n in names};print(json.dumps({n:{'origin':str(Path(m.__file__).resolve()),'sha256':sha256(Path(m.__file__).read_bytes()).hexdigest()} for n,m in mods.items()},indent=2))"
origin_argv=['/workspace/ParkWeave/.venv/bin/python','-B','-c',origin_code]
origin=subprocess.run(origin_argv,cwd=MIRROR,env=env,capture_output=True)
(OUT/'module-origin.stdout.json').write_bytes(origin.stdout);(OUT/'module-origin.stderr.txt').write_bytes(origin.stderr)
save('module-origin-invocation.json',{'argv':origin_argv,'cwd':str(MIRROR),'exit_code':origin.returncode,'scope':'Separate import-only process with same cwd/PYTHONPATH; no test-process origin instrumentation.'})
assert origin.returncode==0
for item in json.loads(origin.stdout).values():
 path=Path(item['origin']);rel=str(path.relative_to(MIRROR));assert rel.startswith('src/') and item['sha256']==expected[rel]
shared_post=check(ROOT);mirror_post=check(MIRROR)
save('shared-post.json',shared_post);save('mirror-post.json',mirror_post)
head_post=git('rev-parse','HEAD').decode().strip()
assert not shared_post['drift'] and not mirror_post['drift'] and head_post==SHA
assert actual_ids==all_expected and len(set(actual_ids))==69
summary={'source_sha':SHA,'src_tree':git('rev-parse',SHA+':src').decode().strip(),'tests_tree':git('rev-parse',SHA+':tests').decode().strip(),'passed':sum(r['passed'] for r in results),'failures':sum(r['failures'] for r in results),'errors':sum(r['errors'] for r in results),'skipped':sum(r['skipped'] for r in results),'exit_codes':{r['label']:r['exit_code'] for r in results},'blockers':0 if all(r['exit_code']==0 and r['actual_ids_equal_expected'] for r in results) else 1,'p1':0,'p2':0,'test_methods_unique':69,'actual_ids_equal_expected':True,'ordinary_methods':24,'activation_methods':45,'new_activation_modes':33,'legacy_node_modes':12,'test_executions':{'ordinary':1,'activation':1},'automatic_retries':0,'outer_elapsed_seconds':time.monotonic()-outer_start,'per_script':[{k:v for k,v in r.items() if k!='actual_tests'} for r in results],'input_verification':{'inputs':185,'src_files':179,'shared_pre_drift':0,'mirror_pre_drift':0,'shared_post_drift':0,'mirror_post_drift':0,'shared_head_pre':head_pre,'shared_head_after_pre':head_after_pre,'shared_head_post':head_post,'contract_sha256':expected['docs/F2/OrdinaryActivationUI-20261018.md'],'archive_sha256':hx(archive)},'static_review':{'open_p1':0,'open_p2':0,'closed_p2':['Binder return/publication gap: un-published client gets runtime scope before publication.','ACTIVATE reason uses model-compatible Unicode White_Space normalization.','Activation history proof settles only original entry lease; current403/navigation clear this private lease and retain opaque Run/key barrier.'],'contract_scope_consistent':True,'legacy_node_script_unchanged_expected':True},'overlap':{'same_frozen_two_scripts_expected_69':True,'actual_parent_raw_ids':'PENDING; parent executing its own frozen run','counts_not_added':True},'module_origin_scope':'Separate import-only process verified eight actual imported mirror/src modules and frozen hashes. Actual unittest processes were not instrumented; ordinary stderr also names mirror source warning paths. Node script reads mirror web.html via its original cwd-relative fs read.','scope':['24 direct unittest methods: original scope/client/native/FastAPI wiring with MemoryConnection and protected binder/RPC DI.','45 direct unittest methods invoke original NodeVM scripts: full page script, minimal DOM, synthetic DTOs and mock fetch.','Original legacy Node script copied byte-for-byte from frozen Git.','No product, test, contract or Git mutation; only private mirror/evidence writes.'],'not_run':['pytest/conftest','PG/database/real SQL engine','real IPC/API server/service','browser','installation/migration/activation','real writer permission/MAC/idempotency/PG atomicity acceptance','new key/identity/session/Grant/assignment/policy issuance','real model/network/Windows'],'owned_children':{'unittest_children_reaped':True,'node_children':'Original per-case subprocess.run returned for every passing Node mode; no service spawned.','origin_probe_reaped':True,'services_started':0},'evidence_directory':str(OUT),'mirror':str(MIRROR),'raw_evidence_paths':[str(OUT/name) for name in ['preparation.json','frozen-inputs.json','shared-pre.json','shared-post.json','mirror-pre.json','mirror-post.json','versions.json','expected-test-ids.json','actual-test-ids.json','ordinary-invocation.json','ordinary.stdout.txt','ordinary.stderr.txt','ordinary-result.json','activation-invocation.json','activation.stdout.txt','activation.stderr.txt','activation-result.json','module-origin-invocation.json','module-origin.stdout.json','module-origin.stderr.txt','prepare-and-run.py']]}
save('independent-final-review.json',summary)
report=OUT/'independent-final-review.json'
print(json.dumps({'report':str(report),'sha256':hx(report.read_bytes()),'source_sha':SHA,'passed':summary['passed'],'failures':summary['failures'],'errors':summary['errors'],'skipped':summary['skipped'],'blockers':summary['blockers'],'ordinary_exit':results[0]['exit_code'],'activation_exit':results[1]['exit_code'],'ordinary_elapsed':results[0]['outer_elapsed_seconds'],'activation_elapsed':results[1]['outer_elapsed_seconds'],'shared_post_drift':0,'mirror_post_drift':0,'head_post':head_post},indent=2))
assert summary['passed']==69 and summary['blockers']==0
