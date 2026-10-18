from pathlib import Path,PurePosixPath
from hashlib import sha1,sha256
from xml.etree import ElementTree as ET
import importlib.util,io,json,os,subprocess,sys,tarfile,time
ROOT=Path('/workspace/ParkWeave');SHA='b232570e7f48a12d0b4747a664009bdb74066f4c';OLD='3c0ba9bb816b270116ddcca771829443dac6dd1e'
E=Path(__file__).resolve().parent;B=Path(json.loads((E/'locations.json').read_text())['temporary_root']);M=B/'mirror'
PREVIOUS=ROOT/'.runtime/at22-23-finite-20261018/independent/pw-ind-at22-3c0ba9b-edoa7d65'
paths=['src','tests','scripts','pyproject.toml','docs/F1/ATBindings.json','docs/验收规格.json']
node='tests/test_acceptance_runner.py::test_fixed_bindings_complete_unique_and_safe'
def save(name,value):(E/name).write_text(json.dumps(value,sort_keys=True,ensure_ascii=False,indent=2)+'\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def head():return git('rev-parse','HEAD').decode().strip()
def h(raw):return sha256(raw).hexdigest()
assert head()==SHA,head()
files={}
for item in git('ls-tree','-rz','--full-tree',SHA,'--',*paths).split(b'\0'):
 if item:
  meta,path=item.split(b'\t',1);mode,kind,oid=meta.decode().split();path=path.decode()
  assert kind=='blob' and mode in ('100644','100755')
  files[path]={'git_blob':oid,'mode':mode}
assert len(files)==768
archive=git('archive','--format=tar',SHA,'--',*paths)
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
 for member in tar:
  p=PurePosixPath(member.name);assert not p.is_absolute() and '..' not in p.parts
  if member.isdir():(M/member.name).mkdir(parents=True,exist_ok=True);continue
  assert member.isfile() and member.name in files
  raw=tar.extractfile(member).read();assert sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()==files[member.name]['git_blob']
  target=M/member.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw);files[member.name].update(sha256=h(raw),size=len(raw))
save('frozen-inputs.json',{'source_sha':SHA,'input_count':768,'files':files,'archive_sha256':h(archive)})
old=json.loads((PREVIOUS/'frozen-inputs.json').read_text())['files'];diff=[p for p in files if files[p]['sha256']!=old[p]['sha256']]
assert set(files)==set(old) and diff==['docs/F1/ATBindings.json'],diff
oldb=json.loads(git('show',OLD+':docs/F1/ATBindings.json'));newb=json.loads((M/'docs/F1/ATBindings.json').read_text())
oldcases={c['id']:c for c in oldb['cases']};newcases={c['id']:c for c in newb['cases']}
removed='tests/test_material_text_pack_browser.py::test_missing_materials_are_gaps_without_invented_requirements'
assert len(oldcases)==len(newcases)==42
assert all(c['whole_status']=='NOT_RUN' for c in newcases.values())
assert newcases['AT-23']['engineering_selectors']==[x for x in oldcases['AT-23']['engineering_selectors'] if x!=removed]
oldcases['AT-23']['engineering_selectors'].remove(removed)
assert oldcases==newcases
source_tree=git('rev-parse',SHA+':src').decode().strip();tests_tree=git('rev-parse',SHA+':tests').decode().strip()
assert source_tree==git('rev-parse',OLD+':src').decode().strip() and tests_tree==git('rev-parse',OLD+':tests').decode().strip()
save('cross-version-input-validation.json',{'old_sha':OLD,'new_sha':SHA,'input_count':768,'changed_paths':diff,'removed_executable_selector':removed,'other_binding_fields_identical':True,'whole_status_count_NOT_RUN':42,'source_tree_equal':True,'tests_tree_equal':True})
def check(base,label):
 values={p:h((base/p).read_bytes()) for p in files};changes=[p for p in values if values[p]!=files[p]['sha256']]
 save(label+'.json',{'source_sha':SHA,'observed_shared_head':head(),'input_count':768,'drift_count':len(changes),'changes':changes,'sha256':values})
 assert not changes and head()==SHA,(label,changes,head())
check(ROOT,'shared-pre');check(M,'mirror-pre')
spec=importlib.util.spec_from_file_location('private_minimal_environment',M/'src/parkweave/process_env.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
runtime=B/'runtime';runtime.mkdir()
env=module.minimal_environment(os.environ,PYTHONPATH=os.pathsep.join(map(str,[M,M/'src',M/'tests'])),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',XDG_RUNTIME_DIR=str(runtime))
args=[str(ROOT/'.venv/bin/python'),'-B','-m','pytest','-q','-p','no:cacheprovider','--rootdir='+str(M),'--basetemp='+str(B/'artifacts'),'--junitxml='+str(E/'results.xml'),node]
save('invocation.json',{'source_sha':SHA,'argv':args,'cwd':str(M),'env':env,'exact_node':node,'automatic_retries':0,'business_nodes_requested':0,'pg_nodes_requested':0})
t0=time.perf_counter()
with (E/'stdout.txt').open('wb') as stdout,(E/'stderr.txt').open('wb') as stderr:
 result=subprocess.run(args,cwd=M,env=env,stdout=stdout,stderr=stderr,timeout=60,check=False)
elapsed=time.perf_counter()-t0
check(ROOT,'shared-post');check(M,'mirror-post')
rows=[]
for c in ET.parse(E/'results.xml').getroot().iter('testcase'):
 rows.append({'id':c.attrib['classname'].replace('.','/')+'.py::'+c.attrib['name'],'outcome':next((t for t in ('failure','error','skipped') if c.find(t) is not None),'PASS')})
assert rows==[{'id':node,'outcome':'PASS'}],rows
assert result.returncode==0
pgdirs=[str(p) for p in B.rglob('parkweave-pg*')];assert not pgdirs,pgdirs
rootxml=ROOT/'.runtime/at22-23-finite-20261018/binding-only/results.xml'
assert rootxml.is_file(),rootxml
rootnodes=[c.attrib['classname'].replace('.','/')+'.py::'+c.attrib['name'] for c in ET.parse(rootxml).getroot().iter('testcase')]
assert node in rootnodes and len(set(rootnodes))==len(rootnodes)
report={'source_sha':SHA,'source_tree':source_tree,'tests_tree':tests_tree,'passed':1,'failures':0,'errors':0,'skipped':0,'blockers':0,'exit_code':result.returncode,'outer_elapsed_seconds':elapsed,'actual_unique_nodes':[node],'business_nodes_executed':0,'original_3c0_business_result_not_transferred':True,'source_3c0_report':str(PREVIOUS/'independent-final-review.json'),'source_3c0_report_sha256':h((PREVIOUS/'independent-final-review.json').read_bytes()),'cross_version_input_difference':diff,'shared_prepost_drift':0,'mirror_prepost_drift':0,'input_count':768,'all_42_whole_status_NOT_RUN':True,'AT23_old_browser_executable_selector_removed':True,'overlap':{'root_result_xml':str(rootxml),'root_actual_nodes':rootnodes,'independent_static_count':1,'intersection_count':1,'counts_are_not_additive':True,'root_window_contains_extra_repeated_business_node':len(rootnodes)>1},'scope':'Only existing fixed-bindings static pytest node, directly named on CLI; no fixture PG/business/API/browser/model/installation/security actions requested.','PG_observation':{'owned_pg_data_paths_found':pgdirs,'PG_fixture_not_required_by_static_node':True,'no_observer_or_test_command_pending':True},'limitations':['Application and conftest imports occur in the standard pytest path; no new runtime import instrumentation was added for this static-only supplement.','The AT22 business result remains qualified to frozen 3c0; this b232 window validates only the binding revision.','AT23 historic material/browser evidence is not rerun or upgraded; no whole AT22/23 completion inferred.'],'evidence_directory':str(E),'mirror':str(M),'raw_evidence':{n:str(E/n) for n in ['run-static.py','invocation.json','stdout.txt','stderr.txt','results.xml','frozen-inputs.json','shared-pre.json','shared-post.json','mirror-pre.json','mirror-post.json','cross-version-input-validation.json']}}
save('binding-static-final-review.json',report)
print(json.dumps({'report':str(E/'binding-static-final-review.json'),'sha256':h((E/'binding-static-final-review.json').read_bytes()),'source_sha':SHA,'passed':1,'business_executed':0,'outer_elapsed_seconds':elapsed},sort_keys=True))
