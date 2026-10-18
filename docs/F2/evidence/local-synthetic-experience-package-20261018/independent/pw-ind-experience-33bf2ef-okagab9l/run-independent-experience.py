from pathlib import Path,PurePosixPath
import ast,hashlib,json,os,re,stat,subprocess,sys,time,zipfile
r=Path(__file__).resolve().parent;p=json.loads((r/'preparation.json').read_text());repo=Path(p['repo']);mirror=Path(p['mirror']);outer=Path(p['outer']);expected=json.loads((r/'expected-inputs.json').read_text());assert not (r/'run-result.json').exists()
def save(n,d):(r/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def check_inputs():
 shared={n:digest(repo/n) for n in expected};copied={n:digest(mirror/n) for n in expected};assert shared==copied==expected;return shared,copied
check_inputs();assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==p['source_sha']
start=time.monotonic();zip_path=Path(p['zip_path']);assert digest(zip_path)==p['zip_sha256']
source_allowlist=['src/parkweave','pyproject.toml','scripts/demo_preflight.py','scripts/package_local_synthetic_demo.py','docs/demo/LocalSyntheticExperience.md','docs/demo/LocalSyntheticWalk.html','docs/F2/LocalSyntheticDemoContract-20261017.md']
source_names=[n for n in subprocess.check_output(['git','ls-tree','-r','--name-only','-z',p['source_sha'],'--',*source_allowlist],cwd=repo).decode().split('\0') if n]
assert len(source_names)==len(set(source_names))==184;generated={'BUNDLE.json','START_HERE.txt','Comparison.txt','SHA256SUMS'};pack=outer/'extracted-experience';pack.mkdir()
with zipfile.ZipFile(zip_path) as z:
 names=z.namelist();assert len(names)==len(set(names))==188 and set(names)==set(source_names)|generated
 for info in z.infolist():
  name=info.filename;parts=PurePosixPath(name).parts;assert not name.startswith('/') and '..' not in parts and '\\' not in name and ':' not in name and str(PurePosixPath(name))==name
  assert stat.S_IFMT(info.external_attr>>16)==stat.S_IFREG and not info.flag_bits&1 and not any(part in ('.git','.runtime','.env') or part.startswith('.env.') for part in parts)
 bundle=json.loads(z.read('BUNDLE.json'));assert bundle['source_commit']==p['source_sha'] and bundle['profile']=='LOCAL_SYNTHETIC_DEMO' and bundle['runtime_inputs_included'] is False and bundle['business_operations_performed'] is False and set(bundle['tracked_source_files'])==set(source_names)
 byte_records=[]
 for name in source_names:
  data=z.read(name);frozen=(mirror/name).read_bytes();row=bundle['tracked_source_files'][name];assert data==frozen and row['bytes']==len(data) and row['sha256']==hashlib.sha256(data).hexdigest()==expected[name]
  byte_records.append(dict(path=name,bytes=len(data),sha256=row['sha256'],frozen_source_equal=True))
 sums=z.read('SHA256SUMS').decode().splitlines();hashes={}
 for line in sums:
  h,name=line.split('  ',1);assert name not in hashes and re.fullmatch('[a-f0-9]{64}',h);hashes[name]=h
 assert len(hashes)==187 and set(hashes)==set(names)-{'SHA256SUMS'} and all(hashlib.sha256(z.read(n)).hexdigest()==h for n,h in hashes.items())
 for name in names:
  target=pack/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(name))
 assert p['source_sha'] in z.read('START_HERE.txt').decode() and p['source_sha'] in z.read('Comparison.txt').decode()
 save('ZIP-validation.json',dict(source_commit=p['source_sha'],zip_path=str(zip_path),zip_bytes=zip_path.stat().st_size,zip_sha256=p['zip_sha256'],entries=188,source_entries=184,product_source_entries=sum(n.startswith('src/parkweave/') for n in source_names),generated_entries=sorted(generated),all_source_bytes_equal_frozen_commit=True,manifest_lengths_and_sha256_equal=True,SHA256SUMS_verified=187,regular_safe_entries_only=True,private_runtime_paths_included=False,only_explicit_source_allowlist_and_generated_public_templates=True,source_files=byte_records,extracted_package=str(pack),limits='No universal semantic secret scanner is claimed; all payload source bytes exactly equal the explicit184 frozen Git allowlist, plus four inspected generated public metadata/templates. No environment or private runtime input files are read for packaging.'))
# One actual invocation of the unchanged stdlib test module; unittest verbose records actual IDs.
allowed_os=('PATH','SystemRoot','SYSTEMROOT','WINDIR','COMSPEC','PATHEXT','TEMP','TMP','TMPDIR','LANG','LC_ALL','TZ');env={k:os.environ[k] for k in allowed_os if k in os.environ};env['PYTHONDONTWRITEBYTECODE']='1'
testfile=mirror/'tests/test_demo_preflight.py';tree=ast.parse(testfile.read_text());expected_ids=sorted(c.name+'.'+f.name for c in tree.body if isinstance(c,ast.ClassDef) and any(isinstance(b,ast.Attribute) and b.attr=='TestCase' for b in c.bases) for f in c.body if isinstance(f,ast.FunctionDef) and f.name.startswith('test_'));assert len(expected_ids)==13
save('expected-13-test-ids.json',expected_ids)
argv=[sys.executable,'-B',str(testfile),'-v'];save('unittest-invocation.json',dict(argv=argv,cwd=str(mirror),environment=env,source_sha=p['source_sha'],automatic_retries=0,timeout_seconds=120,uses_pytest=False))
with (r/'unittest.stdout.txt').open('w') as out,(r/'unittest.stderr.txt').open('w') as err:
 before=time.monotonic();done=subprocess.run(argv,cwd=mirror,env=env,stdout=out,stderr=err,timeout=120);test_elapsed=time.monotonic()-before
text=(r/'unittest.stderr.txt').read_text();matched=re.findall(r'^test_[^\n]*\(__main__\.([^\)]+)\) \.\.\. (ok|FAIL|ERROR|skipped[^\n]*)$',text,re.M);actual_ids=[name for name,status in matched];outcomes={name:status for name,status in matched};save('actual-13-test-ids.json',actual_ids)
assert done.returncode==0 and len(actual_ids)==len(set(actual_ids))==13 and sorted(actual_ids)==expected_ids and set(outcomes.values())=={'ok'} and 'Ran 13 tests' in text
# An empty application environment on the actual ZIP extraction. This is a missing-input refusal, not a DB validation.
probe_argv=[sys.executable,'-B',str(pack/'scripts/demo_preflight.py'),'--local-synthetic','--check-existing-inputs','--json'];save('empty-env-invocation.json',dict(argv=probe_argv,cwd=str(pack),environment=env,no_PARKWEAVE_environment=True,automatic_retries=0,timeout_seconds=30))
with (r/'empty-env.stdout.json').open('w') as out,(r/'empty-env.stderr.txt').open('w') as err:
 probe=subprocess.run(probe_argv,cwd=pack,env=env,stdout=out,stderr=err,timeout=30)
report=json.loads((r/'empty-env.stdout.json').read_text());assert probe.returncode==2 and report['status']=='BLOCKED_MISSING_EXISTING_INPUTS' and report['missing_input_names']==['PARKWEAVE_DSN','PARKWEAVE_MODE','PARKWEAVE_SERVICE_PROFILE','PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG'] and report['database']=='NOT_PROBED' and report['business_ready'] is False and report['sessions']==report['grants']==report['run_assignment']=='NOT_CHECKED'
shared,copied=check_inputs();save('shared-POST-inputs.json',shared);save('mirror-POST-inputs.json',copied);assert digest(zip_path)==p['zip_sha256'] and subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==p['source_sha']
result=dict(source_sha=p['source_sha'],source_tree=p['source_tree'],passed=13,failures=0,errors=0,skipped=0,unittest_exit_code=done.returncode,unittest_elapsed_seconds=test_elapsed,elapsed_seconds=time.monotonic()-start,actual_unique_ids=actual_ids,automatic_retries=0,empty_env_preflight_exit_code=probe.returncode,empty_env_status=report['status'],empty_env_missing_names=report['missing_input_names'],DB_positive_probe='NOT_RUN',input_count=len(expected),shared_mirror_PREPOST_drift=[],zip_sha256_POST=p['zip_sha256'],no_PG_browser_or_network_start=True,all_owned_child_commands_exited=True,scope='One13-test stdlib invocation and one empty-env missing-input probe, no pytest/DB/browser/worker/API startup/network/model/install. Probe-positive and SQL protection tests are Python stubs, not actual PostgreSQL validation.')
save('run-result.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
