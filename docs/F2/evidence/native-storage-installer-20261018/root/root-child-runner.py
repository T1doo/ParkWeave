import json,sys,time,unittest
import test_native_storage_installer as module
suite=unittest.defaultTestLoader.loadTestsFromTestCase(module.InstallerTests)
def ids(s):
 for t in s:
  if isinstance(t,unittest.TestSuite):yield from ids(t)
  else:yield t.id()
methods=list(ids(suite));started=time.perf_counter()
result=unittest.TextTestRunner(verbosity=2).run(suite)
summary=dict(tests_run=result.testsRun,unique_methods=methods,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),seconds=time.perf_counter()-started,successful=result.wasSuccessful())
open(sys.argv[1],'w').write(json.dumps(summary,sort_keys=True,indent=2)+'\n')
sys.exit(0 if result.wasSuccessful() else 1)
