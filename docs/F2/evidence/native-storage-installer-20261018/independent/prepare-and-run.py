from pathlib import Path, PurePosixPath
from hashlib import sha256
import ast, io, json, os, subprocess, sys, tarfile, time

ROOT=Path('/workspace/ParkWeave')
SHA='5930e1cf2bb70532056c7fef894299467707060a'
E=Path(__file__).resolve().parent
M=Path(json.loads((E/'locations.json').read_text())['mirror'])
PYTHON=ROOT/'.venv/bin/python'
DOC='docs/F2/NativeStorageInstaller-20261018.md'
TESTS=['tests/test_native_storage_installer.py','tests/test_installed_writer_launch.py','tests/test_native_run_access_restricted_adapter.py','tests/test_native_run_access_trial_plan.py','tests/test_native_run_access_preflight.py']
PATHS=['src','pyproject.toml',DOC,*TESTS]
def save(name,data):
    (E/name).write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def head():return git('rev-parse','HEAD').decode().strip()
def digest(raw):return sha256(raw).hexdigest()
assert head()==SHA, head()
records={}
for item in git('ls-tree','-r','-z','--full-tree',SHA,'--',*PATHS).split(b'\0'):
    if not item:continue
    fields,path=item.split(b'\t',1);mode,kind,oid=fields.decode().split()
    path=path.decode()
    assert mode in ('100644','100755') and kind=='blob',(mode,kind,path)
    raw=git('cat-file','blob',oid)
    records[path]={'sha256':digest(raw),'size':len(raw),'git_blob':oid}
assert len(records)==187,len(records)
save('frozen-inputs.json',{'source_sha':SHA,'count':len(records),'files':records})
def check(base,label):
    actual={};differences=[]
    for path,expected in records.items():
        f=base/path
        if f.is_symlink() or not f.is_file():
            differences.append({'path':path,'reason':'missing_or_nonregular'});continue
        raw=f.read_bytes();actual[path]={'sha256':digest(raw),'size':len(raw)}
        if actual[path]['sha256']!=expected['sha256'] or len(raw)!=expected['size']:
            differences.append({'path':path,'reason':'bytes_changed','actual':actual[path],'expected':expected})
    out={'source_sha':SHA,'observed_shared_head':head(),'count':len(records),'actual':actual,'drift_count':len(differences),'differences':differences}
    save(label+'.json',out)
    assert not differences,(label,differences)
    assert out['observed_shared_head']==SHA,out['observed_shared_head']
    return out
check(ROOT,'shared-pre')
archive=git('archive',SHA,'--',*PATHS)
with tarfile.open(fileobj=io.BytesIO(archive),mode='r:') as tf:
    for member in tf:
        name=PurePosixPath(member.name)
        assert not name.is_absolute() and '..' not in name.parts,member.name
        if member.isdir():(M/member.name).mkdir(parents=True,exist_ok=True);continue
        assert member.isfile() and member.name in records,member.name
        out=M/member.name;out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(tf.extractfile(member).read())
check(M,'mirror-pre')
node=ast.parse((M/TESTS[0]).read_text())
case=next(n for n in node.body if isinstance(n,ast.ClassDef) and n.name=='InstallerTests')
expected=['test_native_storage_installer.InstallerTests.'+n.name for n in case.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')]
assert len(expected)==28 and len(set(expected))==28,len(expected)
save('expected-test-ids.json',{'count':28,'ids':sorted(expected)})
child=E/'run-unittest.py'
child.write_text('''from pathlib import Path
from hashlib import sha256
import importlib, json, os, sys, time, unittest
out=Path(sys.argv[1]);mirror=Path(sys.argv[2])
module=importlib.import_module('test_native_storage_installer')
class Result(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.actual_ids=[];self.passed_ids=[]
    def startTest(self,test):self.actual_ids.append(test.id());super().startTest(test)
    def addSuccess(self,test):self.passed_ids.append(test.id());super().addSuccess(test)
started=time.perf_counter()
result=unittest.TextTestRunner(verbosity=2,resultclass=Result).run(unittest.defaultTestLoader.loadTestsFromTestCase(module.InstallerTests))
elapsed=time.perf_counter()-started
origins={}
for name,value in sorted(sys.modules.items()):
    if name=='parkweave' or name.startswith('parkweave.') or name in ('test_native_storage_installer','test_installed_writer_launch','test_native_run_access_restricted_adapter','test_native_run_access_trial_plan','test_native_run_access_preflight'):
        origin=getattr(value,'__file__',None)
        if origin:
            p=Path(origin).resolve();relative=p.relative_to(mirror).as_posix()
            origins[name]={'path':str(p),'mirror_relative':relative,'sha256':sha256(p.read_bytes()).hexdigest()}
data={'python_version':sys.version,'python_executable':sys.executable,'source_scope':'private exact Git archive mirror','actual_ids':result.actual_ids,'passed_ids':result.passed_ids,'tests_run':result.testsRun,'passed':len(result.passed_ids),'failures':[{'id':t.id(),'traceback':tb} for t,tb in result.failures],'errors':[{'id':t.id(),'traceback':tb} for t,tb in result.errors],'skipped':[{'id':t.id(),'reason':reason} for t,reason in result.skipped],'elapsed_seconds':elapsed,'origins':origins,'pytest_imported_as_support_utility':'pytest' in sys.modules,'conftest_loaded':any(name=='conftest' or name.endswith('.conftest') for name in sys.modules)}
(out/'unittest-result.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\\n')
sys.exit(0 if result.wasSuccessful() else 1)
''')
env={k:v for k,v in os.environ.items() if not k.startswith('PARKWEAVE')}
env['PYTHONPATH']=str(M/'src')+os.pathsep+str(M/'tests')
env['PYTHONDONTWRITEBYTECODE']='1'
argv=[str(PYTHON),'-B',str(child),str(E),str(M)]
save('invocation.json',{'source_sha':SHA,'argv':argv,'cwd':str(M),'env_whitelist':{k:env.get(k) for k in ('PYTHONPATH','PYTHONDONTWRITEBYTECODE','LANG','LC_ALL')},'parkweave_env_keys_removed':sorted(k for k in os.environ if k.startswith('PARKWEAVE')),'pytest':False,'automatic_retries':0,'class':'test_native_storage_installer.InstallerTests','expected_count':28})
started=time.perf_counter()
with (E/'unittest.stdout.txt').open('wb') as stdout,(E/'unittest.stderr.txt').open('wb') as stderr:
    completed=subprocess.run(argv,cwd=M,env=env,stdout=stdout,stderr=stderr,check=False)
outer=time.perf_counter()-started
save('run-result.json',{'source_sha':SHA,'exit_code':completed.returncode,'outer_elapsed_seconds':outer,'stdout':str(E/'unittest.stdout.txt'),'stderr':str(E/'unittest.stderr.txt'),'test_result':str(E/'unittest-result.json')})
check(M,'mirror-post');check(ROOT,'shared-post')
result=json.loads((E/'unittest-result.json').read_text())
assert sorted(result['actual_ids'])==sorted(expected),(result['actual_ids'],expected)
assert len(result['actual_ids'])==len(set(result['actual_ids']))==28
for value in result['origins'].values():
    assert value['mirror_relative'] in records,value
    assert value['sha256']==records[value['mirror_relative']]['sha256'],value
assert not result['conftest_loaded']
save('module-origins.json',{'source_sha':SHA,'all_actual_origins_are_frozen_mirror_bytes':True,'modules':result['origins']})
print(json.dumps({'source_sha':SHA,'input_count':187,'shared_pre_drift':0,'shared_post_drift':0,'mirror_pre_drift':0,'mirror_post_drift':0,'test_exit_code':completed.returncode,'actual_unique_count':len(set(result['actual_ids'])),'passed':result['passed'],'failures':len(result['failures']),'errors':len(result['errors']),'skipped':len(result['skipped']),'outer_elapsed_seconds':outer,'method_elapsed_seconds':result['elapsed_seconds'],'origin_count':len(result['origins']),'evidence':str(E)},sort_keys=True))
sys.exit(completed.returncode)
