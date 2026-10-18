import hashlib, io, json, os, pathlib, subprocess, sys, tarfile, tempfile, time
repo=pathlib.Path('/workspace/ParkWeave'); output=repo/'.runtime/native-storage-installer-20261018'
revision=sys.argv[1]
paths=['src','pyproject.toml','docs/F2/NativeStorageInstaller-20261018.md','tests/test_native_storage_installer.py','tests/test_installed_writer_launch.py','tests/test_native_run_access_restricted_adapter.py','tests/test_native_run_access_trial_plan.py','tests/test_native_run_access_preflight.py']
files=subprocess.check_output(['git','ls-tree','-rz','--name-only',revision,'--',*paths],cwd=repo).decode().rstrip('\0').split('\0')
archive=subprocess.check_output(['git','archive','--format=tar',revision,'--',*paths],cwd=repo)
mirror=pathlib.Path(tempfile.mkdtemp(prefix='parkweave-native-install-root-',dir='/tmp'))
with tarfile.open(fileobj=io.BytesIO(archive)) as tar:tar.extractall(mirror,filter='data')
def hashes():return {p:hashlib.sha256((mirror/p).read_bytes()).hexdigest() for p in files}
before=hashes();(output/'root-input-before.json').write_text(json.dumps(before,sort_keys=True,indent=2)+'\n')
child='''import json,sys,time,unittest\nimport test_native_storage_installer as module\nsuite=unittest.defaultTestLoader.loadTestsFromTestCase(module.InstallerTests)\ndef ids(s):\n for t in s:\n  if isinstance(t,unittest.TestSuite):yield from ids(t)\n  else:yield t.id()\nmethods=list(ids(suite));started=time.perf_counter()\nresult=unittest.TextTestRunner(verbosity=2).run(suite)\nsummary=dict(tests_run=result.testsRun,unique_methods=methods,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),seconds=time.perf_counter()-started,successful=result.wasSuccessful())\nopen(sys.argv[1],'w').write(json.dumps(summary,sort_keys=True,indent=2)+'\\n')\nsys.exit(0 if result.wasSuccessful() else 1)\n'''
(output/'root-child-runner.py').write_text(child)
env=dict(os.environ,PYTHONPATH=str(mirror/'src')+':'+str(mirror/'tests'),PYTHONDONTWRITEBYTECODE='1')
started=time.perf_counter()
result=subprocess.run([str(repo/'.venv/bin/python'),'-B',str(output/'root-child-runner.py'),str(output/'root-result.json')],cwd=mirror,env=env,capture_output=True,timeout=30)
(output/'root.stdout').write_bytes(result.stdout);(output/'root.stderr').write_bytes(result.stderr)
after=hashes();(output/'root-input-after.json').write_text(json.dumps(after,sort_keys=True,indent=2)+'\n')
metadata=dict(revision=revision,mirror=str(mirror),input_count=len(files),input_changes=[p for p in files if before[p]!=after[p]],archive_sha256=hashlib.sha256(archive).hexdigest(),returncode=result.returncode,outer_seconds=time.perf_counter()-started,source_tree=subprocess.check_output(['git','rev-parse',revision+':src'],cwd=repo).decode().strip(),tests_tree=subprocess.check_output(['git','rev-parse',revision+':tests'],cwd=repo).decode().strip())
(output/'root-metadata.json').write_text(json.dumps(metadata,sort_keys=True,indent=2)+'\n')
print(json.dumps(metadata));sys.exit(result.returncode)
