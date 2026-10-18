from pathlib import Path
from hashlib import sha256
from io import BytesIO
import ast, fcntl, json, os, re, socket, subprocess, sys, tarfile, time
ROOT=Path('/workspace/ParkWeave')
SHA='8ea6993e85982a9849f6999a19017ee5462b9874'
OUT=Path(__file__).resolve().parent
BASE=Path(sys.argv[1]).resolve();MIRROR=BASE/'mirror';MIRROR.mkdir(exist_ok=False)
PATHS=['src','pyproject.toml','tests/test_installed_writer_launch.py','tests/test_ordinary_runtime_write.py','tests/test_native_run_access_restricted_adapter.py','tests/test_native_run_access_trial_plan.py','tests/test_native_run_access_preflight.py','docs/F2/InstalledWriterLaunch-20261018.md']
def save(name,value):(OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def hx(data):return sha256(data).hexdigest()
head_pre=git('rev-parse','HEAD').decode().strip();assert head_pre==SHA,head_pre
archive=git('archive','--format=tar',SHA,'--',*PATHS);(OUT/'archive.tar').write_bytes(archive)
entries={}
with tarfile.open(fileobj=BytesIO(archive),mode='r:') as tf:
 for m in tf.getmembers():
  path=Path(m.name);assert not path.is_absolute() and '..' not in path.parts,m.name
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
assert len(objects)==len(entries)==186,(len(objects),len(entries))
assert sum(p.startswith('src/') for p in entries)==179
batch=subprocess.run(['git','cat-file','--batch'],cwd=ROOT,input=''.join(oid+'\n' for _,oid in objects).encode(),stdout=subprocess.PIPE,check=True).stdout
stream=BytesIO(batch)
for name,oid in objects:
 header=stream.readline().split();assert header[:2]==[oid.encode(),b'blob']
 data=stream.read(int(header[2]));assert stream.read(1)==b'\n';assert data==entries[name],name
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
save('preparation.json',{'source_sha':SHA,'head_pre':head_pre,'head_after_pre':head_after_pre,'archive_sha256':hx(archive),'inputs':186,'src_files':179,'paths':PATHS,'mirror':str(MIRROR),'evidence':str(OUT),'contract_sha256':expected['docs/F2/InstalledWriterLaunch-20261018.md'],'shared_pre_drift':0,'mirror_pre_drift':0})
save('versions.json',{'python_executable':sys.executable,'python_version':sys.version,'node_used':False})
env={k:v for k,v in os.environ.items() if not k.startswith('PARKWEAVE')};removed=sorted(k for k in os.environ if k.startswith('PARKWEAVE'))
env.update(PYTHONPATH=str(MIRROR/'src'),PYTHONDONTWRITEBYTECODE='1')
def expected_ids(rel):
 tree=ast.parse((MIRROR/rel).read_text())
 return sorted('__main__.'+cls.name+'.'+n.name for cls in tree.body if isinstance(cls,ast.ClassDef) for n in cls.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_'))
installed_expected=expected_ids('tests/test_installed_writer_launch.py');ordinary_expected=expected_ids('tests/test_ordinary_runtime_write.py')
assert len(installed_expected)==26 and len(ordinary_expected)==24
all_expected=sorted(installed_expected+ordinary_expected);assert len(set(all_expected))==50
save('expected-test-ids.json',{'installed':installed_expected,'ordinary':ordinary_expected,'all':all_expected,'count':50})
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
results=[];start_all=time.monotonic()
for label,rel,want in [('installed','tests/test_installed_writer_launch.py',installed_expected),('ordinary','tests/test_ordinary_runtime_write.py',ordinary_expected)]:
 argv=['/workspace/ParkWeave/.venv/bin/python','-B',str(MIRROR/rel)]
 save(label+'-invocation.json',{'argv':argv,'cwd':str(MIRROR),'env_whitelist':{k:env[k] for k in ['PYTHONPATH','PYTHONDONTWRITEBYTECODE']},'removed_environment_names':removed,'automatic_retries':0,'framework':'direct unittest.main(verbosity=2); no pytest runner/conftest/fixtures; installed script imports pytest assertion/MonkeyPatch utility through original legacy tests.','expected_ids':want})
 start=time.monotonic()
 with (OUT/(label+'.stdout.txt')).open('wb') as stdout,(OUT/(label+'.stderr.txt')).open('wb') as stderr:
  run=subprocess.run(argv,cwd=MIRROR,env=env,stdout=stdout,stderr=stderr)
 elapsed=time.monotonic()-start;raw=(OUT/(label+'.stderr.txt')).read_text();actual=parse(raw)
 match=re.search(r'^Ran (\d+) tests in ([0-9.]+)s$',raw,re.M)
 row={'label':label,'source_sha':SHA,'exit_code':run.returncode,'outer_elapsed_seconds':elapsed,'reported_count':int(match[1]) if match else None,'unittest_elapsed_seconds':float(match[2]) if match else None,'actual_count':len(actual),'passed':sum(x['result']=='ok' for x in actual),'failures':sum(x['result']=='FAIL' for x in actual),'errors':sum(x['result']=='ERROR' for x in actual),'skipped':sum(x['result'].startswith('skipped') for x in actual),'actual_ids_equal_expected':sorted(x['id'] for x in actual)==want,'actual_tests':actual,'child_reaped':True}
 save(label+'-result.json',row);results.append(row)
actual_ids=sorted(x['id'] for r in results for x in r['actual_tests'])
save('actual-test-ids.json',{'ids':actual_ids,'unique':len(set(actual_ids)),'count':len(actual_ids),'expected_equal':actual_ids==all_expected})
shared_post=check(ROOT);mirror_post=check(MIRROR);save('shared-post.json',shared_post);save('mirror-post.json',mirror_post)
head_post=git('rev-parse','HEAD').decode().strip();assert not shared_post['drift'] and not mirror_post['drift'] and head_post==SHA
assert actual_ids==all_expected and len(set(actual_ids))==50
summary={'source_sha':SHA,'src_tree':git('rev-parse',SHA+':src').decode().strip(),'tests_tree':git('rev-parse',SHA+':tests').decode().strip(),'passed':sum(r['passed'] for r in results),'failures':sum(r['failures'] for r in results),'errors':sum(r['errors'] for r in results),'skipped':sum(r['skipped'] for r in results),'exit_codes':{r['label']:r['exit_code'] for r in results},'blockers':0 if all(r['exit_code']==0 and r['actual_ids_equal_expected'] for r in results) else 1,'p1':0,'p2':0,'test_methods_unique':50,'actual_ids_equal_expected':True,'installed_methods':26,'installed_new_methods':19,'installed_legacy_wrappers':7,'parameter_negatives_not_added':True,'ordinary_methods':24,'test_executions':{'installed':1,'ordinary':1},'automatic_retries':0,'outer_elapsed_seconds':time.monotonic()-start_all,'per_script':[{k:v for k,v in r.items() if k!='actual_tests'} for r in results],'input_verification':{'inputs':186,'src_files':179,'shared_pre_drift':0,'mirror_pre_drift':0,'shared_post_drift':0,'mirror_post_drift':0,'shared_head_pre':head_pre,'shared_head_after_pre':head_after_pre,'shared_head_post':head_post,'contract_sha256':expected['docs/F2/InstalledWriterLaunch-20261018.md'],'archive_sha256':hx(archive)},'static_review':{'open_p1':0,'open_p2':0,'contract_scope_consistent':True,'findings':['Ordinary installed layout/receipt and trial creation contract remain separate and exact.','Parent private input validation creates no engine, store or authority.','Ordinary engine needs original issued sealed-FD authorization, class-dispatch permit and exact spec/private/boot binding.','Original RuntimeGuard, restricted connection, writer business authority and default-closed listener checks remain.','Missing host capability accurately refuses; positive seal/FD/root/process observations are DI only.']},'capability_observation':{'scope':'No new host capability probe in final-v2. Positive capabilities/FD/process observations remain explicit DI; original absent-capability refusal method is executed.'},'overlap':{'same_frozen_two_scripts_expected_50':True,'actual_parent_raw_ids':'PENDING; parent executing frozen run','counts_not_added':True},'module_source_scope':'Direct scripts run from exact archive mirror with PYTHONPATH=mirror/src and -B. No extra import probe or test-process module-origin instrumentation was added. Ordinary raw stderr also identifies mirror source warning paths.','scope':['26 direct unittest methods: 19 installed-profile methods plus seven wrappers invoking original assertions, with one wrapper containing two parameter negatives counted once.','24 direct unittest methods: original ordinary write wiring using MemoryConnection and protected binder/RPC DI.','Root/FD/fcntl/Popen/socket/metadata positive observations are explicit DI. Original host control flow and strict payload/type checks execute.','Installed test globally blocks real database, OS child, socket, memfd and permission operations.','No shared source/tests/docs/Git writes; only private mirror/evidence output.'],'not_run':['pytest runner/conftest/PG fixtures','real DB or SQL engine','real IPC/Popen child service/OS identity','browser/real model/network','installation/storage migration/ACL change','real policy/key/Grant/assignment/approval issuance or activation','actual ordinary installation restart/rebind or physical recovery','Windows/formal AT35/full F2'],'owned_children':{'direct_unittest_children_reaped':True,'real_host_children_started':0,'services_started':0,'other_test_windows':0},'evidence_directory':str(OUT),'mirror':str(MIRROR),'raw_evidence_paths':[str(OUT/name) for name in ['preparation.json','frozen-inputs.json','shared-pre.json','shared-post.json','mirror-pre.json','mirror-post.json','versions.json','expected-test-ids.json','actual-test-ids.json','installed-invocation.json','installed.stdout.txt','installed.stderr.txt','installed-result.json','ordinary-invocation.json','ordinary.stdout.txt','ordinary.stderr.txt','ordinary-result.json','prepare-and-run.py']]}
main_root=ROOT/'.runtime/installed-writer-launch-20261018/final-v2'
main_file=main_root/'frozen-result.json'
main=json.loads(main_file.read_text());assert main['source_sha']==SHA
main_ids=[];raw_sources=[]
for filename,want in [('frozen-installed.stderr',26),('frozen-factory.stderr',24)]:
 path=main_root/filename;rows=parse(path.read_text());assert len(rows)==want and all(x['result']=='ok' for x in rows)
 main_ids.extend(x['id'].removeprefix('__main__.') for x in rows)
 raw_sources.append({'path':str(path),'sha256':hx(path.read_bytes()),'actual_count':len(rows)})
main_stored=[x.removeprefix('__main__.') for r in main['results'] for x in r['actual_ids']]
own_ids=[x.removeprefix('__main__.') for x in actual_ids]
assert sorted(main_ids)==sorted(main_stored)==sorted(own_ids)
assert len(main_ids)==len(set(main_ids))==len(own_ids)==len(set(own_ids))==50
assert git('diff','5683796d3976c7664dae1c57fd19008ea4172e54',SHA,'--','src')==b''
validation={'source_sha':SHA,'main_unique_actual':50,'independent_unique_actual':50,'intersection':50,'missing_from_main':[],'extra_to_main':[],'duplicate_ids_main':0,'duplicate_ids_independent':0,'actual_main_raw_ids_equal_result_and_independent':True,'all_main_raw_statuses_ok':True,'all_50_overlap':True,'counts_not_added':True,'main_raw_evidence':raw_sources,'main_result':{'path':str(main_file),'sha256':hx(main_file.read_bytes())},'scope':'Actual-ID metadata reconciliation only; no test rerun.'}
save('actual-overlap-validation.json',validation)
summary['overlap']={'same_frozen_two_scripts_expected_50':True,'actual_parent_raw_ids':'CONFIRMED: final-v2 frozen-installed.stderr26 + frozen-factory.stderr24, equal result and own actual IDs','all_50_overlap':True,'intersection':50,'missing_from_main':[],'extra_to_main':[],'counts_not_added':True,'validation_path':str(OUT/'actual-overlap-validation.json')}
summary['static_review']['expired_guard_coverage_corrected']={'status':'CLOSED_IN_FINAL_V2','method':'InstalledLaunchTests.test_changed_protected_bytes_and_expired_policy_refuse_without_renewal','evidence':'Expired subcase now enters Harness.observations supported-capability/root DI, matches the original UTC rejection message with assertRaisesRegex, and keeps a protected-reader AssertionError sentinel. This method actually passed once in this final-v2 mirror. No real host capability or private read was performed.'}
summary['static_review']['product_src_unchanged_from_5683796']=True
summary['previous_window']={'source_sha':'5683796d3976c7664dae1c57fd19008ea4172e54','previous_report':str(ROOT/'.runtime/installed-writer-launch-20261018/independent/pw-ind-installed-5683796-dTYYpj/independent-final-review.json'),'sha256':hx((ROOT/'.runtime/installed-writer-launch-20261018/independent/pw-ind-installed-5683796-dTYYpj/independent-final-review.json').read_bytes()),'kept_unchanged':True,'old_scores_not_added':True,'old_capability_first_coverage_limit_remains_on_old_window':True}
assert summary['previous_window']['sha256']=='77f4ef5deb4fa082a1193f72794e1cb3dd595f0df3ef576095b869961bffb471'
summary['raw_evidence_paths'].append(str(OUT/'actual-overlap-validation.json'))
save('independent-final-review.json',summary)
report=OUT/'independent-final-review.json'
print(json.dumps({'report':str(report),'sha256':hx(report.read_bytes()),'source_sha':SHA,'passed':summary['passed'],'failures':summary['failures'],'errors':summary['errors'],'skipped':summary['skipped'],'blockers':summary['blockers'],'installed_exit':results[0]['exit_code'],'ordinary_exit':results[1]['exit_code'],'installed_elapsed':results[0]['outer_elapsed_seconds'],'ordinary_elapsed':results[1]['outer_elapsed_seconds'],'shared_post_drift':0,'mirror_post_drift':0,'head_post':head_post,'new_capability_probe':'NOT_RUN'},indent=2))
assert summary['passed']==50 and summary['blockers']==0
