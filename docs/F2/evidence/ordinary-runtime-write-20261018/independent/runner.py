from pathlib import Path,PurePosixPath
import ast,hashlib,io,json,os,re,subprocess,sys,tarfile,time,traceback
ROOT=Path('/workspace/ParkWeave');TMP=Path(__file__).parent
E=ROOT/'.runtime/ordinary-runtime-write-20261018/independent'/TMP.name
E.mkdir(parents=True,exist_ok=False)
SOURCE='d62cfb996b1377a92ab686bb4fa0c9a4362e9c20'
CONTRACT='docs/F2/OrdinaryRuntimeWrite-20261018.md'
TEST='tests/test_ordinary_runtime_write.py'
MIRROR=TMP/'mirror';MIRROR.mkdir(mode=0o700)
TMPDATA=TMP/'temporary-data';TMPDATA.mkdir(mode=0o700)

def sha(b):return hashlib.sha256(b).hexdigest()
def dump(n,x):
 b=(json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode()
 (E/n).write_bytes(b);(TMP/n).write_bytes(b)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def snapshot(root,files):return {n:sha((root/n).read_bytes()) for n in files}
def method_ids(stderr):
 pairs=re.findall(r'^(test_\w+) \(__main__\.OrdinaryWriteTests\.(test_\w+)\) \.\.\.',stderr,re.M)
 if any(a!=b for a,b in pairs):raise ValueError('unittest names disagree')
 return ['test_ordinary_runtime_write.OrdinaryWriteTests.'+a for a,b in pairs]
start=time.monotonic();result=None
try:
 assert git('rev-parse','HEAD').decode().strip()==SOURCE
 src_tree=git('rev-parse',SOURCE+':src').decode().strip()
 tests_tree=git('rev-parse',SOURCE+':tests').decode().strip()
 raw=git('archive','--format=tar',SOURCE,'--','src',TEST,'pyproject.toml',CONTRACT)
 frozen={}
 with tarfile.open(fileobj=io.BytesIO(raw)) as t:
  for m in t:
   p=PurePosixPath(m.name)
   assert not p.is_absolute() and '..' not in p.parts and '\\' not in m.name
   if m.isdir():continue
   assert m.isfile()
   data=t.extractfile(m).read();frozen[m.name]=sha(data)
   target=MIRROR/m.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 assert len(frozen)==182 and sum(n.startswith('src/') for n in frozen)==179
 shared_pre=snapshot(ROOT,frozen);mirror_pre=snapshot(MIRROR,frozen)
 assert shared_pre==mirror_pre==frozen
 dump('git-frozen-inputs.json',frozen);dump('shared-pre.json',shared_pre);dump('mirror-pre.json',mirror_pre)
 test_ast=ast.parse((MIRROR/TEST).read_text())
 methods=sorted(n.name for cls in test_ast.body if isinstance(cls,ast.ClassDef) and cls.name=='OrdinaryWriteTests' for n in cls.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_'))
 expected=['test_ordinary_runtime_write.OrdinaryWriteTests.'+n for n in methods]
 assert len(expected)==len(set(expected))==21
 dump('expected-ids.json',expected)
 env={k:os.environ[k] for k in ('PATH','LANG','LC_ALL','TZ','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT') if k in os.environ}
 env.update(PYTHONPATH=str(MIRROR/'src'),PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',TMPDIR=str(TMPDATA))
 assert not any(k.startswith('PARKWEAVE') for k in env)
 argv=[str(ROOT/'.venv/bin/python'),'-B',str(MIRROR/TEST)]
 invocation=dict(source_sha=SOURCE,argv=argv,cwd=str(MIRROR),env=env,no_PARKWEAVE_environment=True,pytest=False,conftest=False,automatic_retries=0,evidence_dir=str(E))
 dump('invocation.json',invocation)
 run_start=time.monotonic()
 with (E/'unittest.stdout').open('wb') as stdout,(E/'unittest.stderr').open('wb') as stderr:
  proc=subprocess.run(argv,cwd=MIRROR,env=env,stdout=stdout,stderr=stderr,timeout=60)
 elapsed=time.monotonic()-run_start
 for name in ('unittest.stdout','unittest.stderr'):(TMP/name).write_bytes((E/name).read_bytes())
 stderr=(E/'unittest.stderr').read_text()
 actual=method_ids(stderr)
 summaries=re.findall(r'^Ran (\d+) tests? in ([0-9.]+)s$',stderr,re.M)
 ok=proc.returncode==0 and bool(re.search(r'^OK\s*$',stderr,re.M))
 counts=dict(passed=21 if ok and len(actual)==21 else None,failures=0 if ok else None,errors=0 if ok else None,skipped=0 if ok else None)
 dump('run-result.json',dict(source_sha=SOURCE,exit_code=proc.returncode,elapsed_seconds=elapsed,unittest_summary=summaries,**counts))
 dump('actual-ids.json',actual)
 shared_post=snapshot(ROOT,frozen);mirror_post=snapshot(MIRROR,frozen)
 dump('shared-post.json',shared_post);dump('mirror-post.json',mirror_post)
 assert shared_post==mirror_post==shared_pre==mirror_pre==frozen
 assert git('rev-parse','HEAD').decode().strip()==SOURCE
 assert len(actual)==len(set(actual))==21 and set(actual)==set(expected)
 assert summaries and int(summaries[-1][0])==21
 assert ok,'unittest execution failed; original stdout/stderr preserved'
 root_r=ROOT/'.runtime/ordinary-runtime-write-20261018'
 root_result=json.loads((root_r/'frozen-result.json').read_text())
 root_stderr=(root_r/'frozen.stderr').read_text()
 root_ids=method_ids(root_stderr)
 assert root_result['source_sha']==SOURCE and root_result['exit_code']==0
 assert len(root_ids)==len(set(root_ids))==21 and set(root_ids)==set(actual)
 assert root_result['input_sha256']==frozen
 dump('overlap-validation.json',dict(source_sha=SOURCE,independent_unique=21,root_unique=21,intersection=21,independent_only=[],root_only=[],added_unique_count=0,root_stderr_sha256=sha((root_r/'frozen.stderr').read_bytes()),root_result_sha256=sha((root_r/'frozen-result.json').read_bytes()),all_overlap=True))
 write=(MIRROR/'src/parkweave/ordinary_runtime_write.py').read_text()
 assert 'complete = False' in write and 'finally:' in write and "getattr(store, '_native_run_access', None) is bridge" in write
 assert write.index('WriterPolicy.model_validate(public[\'policy\'])')<write.index('bridge = bind_api(')
 warning_paths=sorted(set(re.findall(re.escape(str(MIRROR))+r'/src/parkweave/[^:\n]+',stderr)))
 contract_hash=frozen[CONTRACT]
 result=dict(source_sha=SOURCE,src_tree=src_tree,tests_tree=tests_tree,status='PASS_LIMITED_OFFLINE_WIRING_REVIEW',exit_code=proc.returncode,passed=21,failures=0,errors=0,skipped=0,blockers=0,P1=0,P2=0,fixed_P2=dict(id='configuration_failure_leaves_new_bridge',status='CLOSED',static='complete/finally removes only current own bridge',actual_offline_test='test_unexpected_startup_error_and_interruption_clean_only_own_bridge',cases=['RuntimeError','AttributeError','KeyboardInterrupt','another bridge retained']),exact_test_methods=21,expected_ids='expected-ids.json',actual_ids='actual-ids.json',overlap_in_root21=21,overlap_added_count=0,overlap_validation='overlap-validation.json',input_files=182,product_source_files=179,contract_sha256=contract_hash,shared_PRE_POST_drift=0,mirror_PRE_POST_drift=0,all_inputs_equal_frozen_Git_blobs=True,actual_argv=argv,cwd=str(MIRROR),PYTHONPATH=str(MIRROR/'src'),import_origin_observation=dict(explicit_PYTHONPATH_mirror=True,module_paths_observed_in_original_unittest_warning=warning_paths,full_test_child_module_origin_instrumentation=False),elapsed_unittest_outer_seconds=elapsed,total_outer_seconds=time.monotonic()-start,pytest_invoked=False,conftest_loaded=False,real_DB_IPC_services_browser_setup_installation_activation_model=0,new_persistent_accounts_sessions_keys_roles_Grants_assignments=0,scope='UNittest directly; MemoryConnection and protected-host-read/binder/RPC DI; original scope, public Client and Native/FastAPI routing; actual unprotected file refusal',limits=['No real writer authorization, signed history or original ledger idempotency was proved. Injected EXPIRED/REVOKED/MISSING_PERMISSION and replay-conflict/unknown replies only prove refusal propagation and absence of local retries.','Concurrent tests prove delayed-call scope refusal and independent key/body routing, not PostgreSQL lock races or atomic event/assignment commits.','Positive root-protected host loading and binding use DI. The actual temporary unprotected-file rejection does not establish a production different-UID installation.','No installation, migration, activation, IPC endpoint, database, service, browser, account, session, key, role, business Grant or assignment was created. In-memory fixture strings/models are not issued authority.','Full per-module import instrumentation was not added to the exact requested test command; PYTHONPATH points at the verified mirror and the original warning shows a mirror/src module path.','Original third-party StarletteDeprecationWarning and Pydantic schema-field warning remain in raw stderr.','This is not complete AT35, F2 completion, real business, Windows or production acceptance.'],owned_children_settlement='The sole unittest subprocess returned via subprocess.run; no service child or observer was launched.',evidence_dir=str(E),temporary_mirror=str(MIRROR))
 dump('independent-final-review.json',result)
 (E/'runner.py').write_bytes(Path(__file__).read_bytes())
 print(json.dumps(dict(report=str(E/'independent-final-review.json'),report_sha256=sha((E/'independent-final-review.json').read_bytes()),source_sha=SOURCE,exit_code=proc.returncode,passed=21,failures=0,errors=0,skipped=0,blockers=0,all21_overlap=True,input_files=182,input_drift=0,elapsed_seconds=elapsed),ensure_ascii=False))
except BaseException:
 trace=traceback.format_exc();(E/'runner-failure.txt').write_text(trace);(TMP/'runner-failure.txt').write_text(trace)
 raise
