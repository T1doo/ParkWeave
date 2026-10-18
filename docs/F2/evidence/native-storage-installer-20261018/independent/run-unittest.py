from pathlib import Path
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
(out/'unittest-result.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
sys.exit(0 if result.wasSuccessful() else 1)
