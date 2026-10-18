from pathlib import Path,PurePosixPath
from hashlib import sha1,sha256
import importlib.util,io,json,os,signal,subprocess,sys,tarfile,time
ROOT=Path('/workspace/ParkWeave');SHA='3c0ba9bb816b270116ddcca771829443dac6dd1e'
E=Path(__file__).resolve().parent
B=Path(json.loads((E/'locations.json').read_text())['temporary_root']);M=B/'mirror'
PATHS=['src','tests','scripts','pyproject.toml','docs/F1/ATBindings.json','docs/验收规格.json']
NODES=['tests/test_synthetic_rule_readiness_api.py::test_at22_api_business_date_region_and_reviewed_version_keep_original_history','tests/test_acceptance_runner.py::test_fixed_bindings_complete_unique_and_safe']
def save(name,value):(E/name).write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def head():return git('rev-parse','HEAD').decode().strip()
def h(raw):return sha256(raw).hexdigest()
assert head()==SHA,head()
assert os.geteuid()!=0,'root environment not authorized for this fixture run'
rows={}
for item in git('ls-tree','-rz','--full-tree',SHA,'--',*PATHS).split(b'\0'):
 if item:
  meta,name=item.split(b'\t',1);mode,kind,oid=meta.decode().split();name=name.decode()
  assert kind=='blob' and mode in ('100644','100755'),(name,kind,mode)
  rows[name]={'git_blob':oid,'mode':mode}
assert len(rows)==768,len(rows)
archive=git('archive','--format=tar',SHA,'--',*PATHS)
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as tar:
 for member in tar:
  p=PurePosixPath(member.name)
  assert not p.is_absolute() and '..' not in p.parts,member.name
  if member.isdir():(M/member.name).mkdir(parents=True,exist_ok=True);continue
  assert member.isfile() and member.name in rows,member.name
  raw=tar.extractfile(member).read()
  assert sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==rows[member.name]['git_blob'],member.name
  target=M/member.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
  rows[member.name].update(sha256=h(raw),size=len(raw))
save('frozen-inputs.json',{'source_sha':SHA,'input_count':768,'paths':PATHS,'archive_sha256':h(archive),'files':rows})
def check(base,name):
 actual={};drift=[]
 for p,expect in rows.items():
  path=base/p
  if path.is_symlink() or not path.is_file():drift.append({'path':p,'reason':'not_regular_or_missing'});continue
  raw=path.read_bytes();actual[p]=h(raw)
  if actual[p]!=expect['sha256']:drift.append({'path':p,'reason':'changed_bytes','actual':actual[p]})
 value={'source_sha':SHA,'observed_shared_head':head(),'input_count':768,'drift_count':len(drift),'differences':drift,'sha256':actual}
 save(name+'.json',value);assert not drift,(name,drift);assert value['observed_shared_head']==SHA
check(ROOT,'shared-pre');check(M,'mirror-pre')
save('expected-nodes.json',{'source_sha':SHA,'nodes':NODES,'unique_count':2})
# Load the original standalone whitelist from this exact mirror, not the shared source.
spec=importlib.util.spec_from_file_location('private_minimal_environment',M/'src/parkweave/process_env.py')
minimal=importlib.util.module_from_spec(spec);spec.loader.exec_module(minimal)
runtime=B/'runtime';runtime.mkdir()
env=minimal.minimal_environment(os.environ,PYTHONPATH=os.pathsep.join(map(str,[M,M/'src',M/'tests'])),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',XDG_RUNTIME_DIR=str(runtime))
assert not any(k.startswith('PARKWEAVE') for k in env)
child=E/'run-pytest.py'
child.write_text('''from pathlib import Path
from hashlib import sha256
import json,os,sys,time
out=Path(sys.argv[1]);mirror=Path(sys.argv[2]);base=mirror.parent
assert os.geteuid()!=0
import pgserver
servers=[];original=pgserver.get_server
def write(name,value):(out/name).write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\\n')
def observed(data,*args,**kwargs):
 server=original(data,*args,**kwargs);pid=server.get_pid();p=Path('/proc')/str(pid)/'stat'
 stat=p.read_text().rsplit(')',1)[1].split()
 record={'data':str(Path(data).resolve()),'pid':pid,'cleanup_mode':kwargs.get('cleanup_mode'),'started':stat[19],'state_at_start':stat[0]}
 assert Path(record['data']).is_relative_to(base)
 servers.append(record);write('owned-pg.json',servers)
 return server
pgserver.get_server=observed
import pytest
nodes=json.loads((out/'expected-nodes.json').read_text())['nodes']
class Observation:
 def __init__(self):self.collected=[];self.reports=[]
 def pytest_collection_finish(self,session):
  self.collected=[i.nodeid for i in session.items];write('actual-collected-nodes.json',{'ids':self.collected})
 def pytest_runtest_logreport(self,report):
  self.reports.append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'duration_seconds':report.duration})
  write('phase-reports.json',{'reports':self.reports})
observer=Observation()
argv=['-q','-p','no:cacheprovider','--rootdir='+str(mirror),'--basetemp='+str(base/'artifacts'),'--junitxml='+str(out/'results.xml'),*nodes]
write('pytest-argv.json',{'args':argv,'cwd':str(Path.cwd()),'euid':os.geteuid()})
started=time.perf_counter();code=pytest.main(argv,plugins=[observer]);elapsed=time.perf_counter()-started
origins={}
for name,module in sorted(sys.modules.items()):
 if name=='parkweave' or name.startswith('parkweave.') or name.startswith('test_') or name in ('conftest','owned_connection_diagnostics','parkweave_acceptance') or name=='scripts' or name.startswith('scripts.'):
  path=getattr(module,'__file__',None)
  if path:
   path=Path(path).resolve();relative=path.relative_to(mirror).as_posix()
   origins[name]={'relative':relative,'sha256':sha256(path.read_bytes()).hexdigest()}
write('module-origins.json',origins)
for index,server in enumerate(servers):
 log=Path(server['data'])/'log'
 if log.is_file():(out/('owned-pg-'+str(index)+'-before-atexit.log')).write_bytes(log.read_bytes())
write('pytest-result.json',{'source_sha':'3c0ba9bb816b270116ddcca771829443dac6dd1e','returncode':int(code),'elapsed_seconds':elapsed,'collected_ids':observer.collected,'phase_reports':observer.reports,'actual_module_count':len(origins),'actual_modules_all_from_mirror':True,'python_version':sys.version,'python_executable':sys.executable,'pytest_version':pytest.__version__})
sys.exit(int(code))
''')
args=[str(ROOT/'.venv/bin/python'),'-B',str(child),str(E),str(M)]
save('invocation.json',{'source_sha':SHA,'argv':args,'cwd':str(M),'env':env,'minimal_environment_source_sha256':rows['src/parkweave/process_env.py']['sha256'],'nodes':NODES,'automatic_retries':0,'outer_timeout_seconds':180,'scope':'only original isolated synthetic PG fixture + ASGI TestClient + candidate/journal SQLite; no browser/root/sealed host/production installation/model'})
started=time.perf_counter()
with (E/'stdout.txt').open('wb') as stdout,(E/'stderr.txt').open('wb') as stderr:
 p=subprocess.Popen(args,cwd=M,env=env,stdout=stdout,stderr=stderr)
 save('owned-test-process.json',{'pid':p.pid,'argv':args,'started_monotonic':started})
 timed_out=False
 try:rc=p.wait(timeout=180)
 except subprocess.TimeoutExpired:
  timed_out=True;p.send_signal(signal.SIGINT);rc=p.wait(timeout=30)
elapsed=time.perf_counter()-started
check(ROOT,'shared-post');check(M,'mirror-post')
settlement=[]
if (E/'owned-pg.json').is_file():
 for row in json.loads((E/'owned-pg.json').read_text()):
  stat=Path('/proc')/str(row['pid'])/'stat'
  if stat.exists():
   fields=stat.read_text().rsplit(')',1)[1].split();state=fields[0];same_instance=fields[19]==row['started']
  else:state='ABSENT';same_instance=None
  settlement.append({**row,'state_after_test_python_exit':state,'same_pid_instance':same_instance,'data_exists':Path(row['data']).exists(),'active_owned_process':same_instance is True and state!='Z'})
save('owned-process-settlement.json',{'test_python_pid':p.pid,'test_python_returncode':rc,'test_python_exited':p.poll() is not None,'owned_pg':settlement,'pending_owned_observer':False,'signals_sent':['SIGINT'] if timed_out else []})
# Copy only public synthetic case output, not PGDATA or session-bearing fixture state.
case_files=[]
for case in sorted((B/'artifacts').rglob('at22-api-case.json')):
 target=E/('case-'+str(len(case_files))+'.json');target.write_bytes(case.read_bytes())
 case_files.append({'original':str(case),'copy':str(target),'sha256':h(target.read_bytes())})
save('case-artifacts.json',{'files':case_files})
save('run-result.json',{'source_sha':SHA,'exit_code':rc,'outer_elapsed_seconds':elapsed,'timed_out':timed_out,'signals_sent':['SIGINT'] if timed_out else [],'mirror':str(M),'source_tree':git('rev-parse',SHA+':src').decode().strip(),'tests_tree':git('rev-parse',SHA+':tests').decode().strip(),'input_count':768,'case_count':len(case_files),'owned_pg':settlement})
print(json.dumps({'source_sha':SHA,'exit_code':rc,'outer_elapsed_seconds':elapsed,'input_count':768,'shared_prepost_drift':0,'mirror_prepost_drift':0,'case_count':len(case_files),'owned_pg':settlement,'evidence':str(E)},sort_keys=True),flush=True)
sys.exit(rc)
