from pathlib import Path
from hashlib import sha256
import json,os,subprocess,time
from scripts import installed_wheel_support as installed
out=Path(__file__).parent;started=time.monotonic()
wheel=next((out/'build/wheels').glob('*.whl'))
python,harness,manifest=installed.install(wheel,out/'install')
env=dict(PATH=os.environ['PATH'],LANG='C.UTF-8',PIP_NO_INDEX='1',PIP_CONFIG_FILE='/dev/null',PIP_DISABLE_PIP_VERSION_CHECK='1')
assert 'PYTHONPATH' not in env
with (out/'pip-check.log').open('w') as log:result=subprocess.run([str(python),'-I','-B','-m','pip','check'],cwd=harness,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=15)
assert result.returncode==0,'offline installed dependency check failed'
code='''from pathlib import Path
from hashlib import sha256
from importlib import import_module,metadata,resources
import json,os,sys
manifest=json.loads(Path(sys.argv[1]).read_text());pure=Path(manifest['purelib']);package=pure/'parkweave'
assert sys.flags.isolated and sys.flags.no_user_site and sys.prefix==manifest['prefix'] and 'PYTHONPATH' not in os.environ
assert not any(str(Path(p).resolve()) in manifest['forbidden_roots'] for p in sys.path if p)
assert not list(pure.glob('*.pth')) and not list(pure.glob('*.egg-link'))
for name in ('parkweave.api','parkweave.difference_observation','parkweave.local_demo_selections','parkweave.local_resource_approval','parkweave.service_case_steps','parkweave.source_change_adoption','parkweave.typed_source_impact','parkweave.case_goal_results'):import_module(name)
for name,version in manifest['dependency_versions'].items():assert metadata.version(name)==version
loaded={}
for name,module in sys.modules.copy().items():
 if name=='parkweave' or name.startswith('parkweave.'):
  path=Path(module.__file__).resolve();assert path.is_relative_to(package)
  loaded[name]=path.relative_to(pure).as_posix()
actual={p.relative_to(pure).as_posix() for p in package.rglob('*') if p.is_file()}
assert actual==set(manifest['package_files'])
for name,digest in manifest['package_files'].items():
 path=pure/name;assert path.resolve()==path and not path.is_symlink() and sha256(path.read_bytes()).hexdigest()==digest
opened=[]
for name in manifest['package_files']:
 if name.endswith(('.sql','.html','.json')):
  relative=name.removeprefix('parkweave/');raw=resources.files('parkweave').joinpath(relative).read_bytes()
  assert sha256(raw).hexdigest()==manifest['package_files'][name];opened.append(relative)
assert all(name in opened for name in ('web.html','park_demo_web.html','migration-033.sql','local-resource-approval-schema.sql'))
print(json.dumps(dict(isolated=True,source_fallback=False,package_root=str(package),package_files=len(actual),dependency_versions=len(manifest['dependency_versions']),loaded_modules=loaded,read_resources=opened,API_started=False,PostgreSQL_started=False,browser=False)))
'''
with (out/'isolated-read.log').open('w') as log:result=subprocess.run([str(python),'-I','-B','-c',code,str(harness/'manifest.json')],cwd=harness,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=15)
assert result.returncode==0,'installed isolated imports/resource check failed'
attestation=json.loads((out/'isolated-read.log').read_text())
report=dict(scope='CURRENT_PACKAGE_GATE_OFFLINE_PREFLIGHT_NOT_FINAL_VISUAL_BROWSER_ACCEPTANCE',source_sha=manifest['checked_out_source_sha'],helper_sha256=sha256(Path(installed.__file__).read_bytes()).hexdigest(),wheel=dict(file=wheel.name,bytes=wheel.stat().st_size,SHA256=manifest['wheel_sha256']),dependency_downloads=0,dependency_copy_bytes=manifest['dependency_copy_bytes'],dependency_copy_files=manifest['dependency_copy_files'],dependency_versions=manifest['dependency_versions'],pip_check_exit=0,isolated_read_exit=0,attestation=attestation,seconds=round(time.monotonic()-started,3),product_business_tests_rerun=0,CI=False,visual_final_tree=False)
(out/'preflight.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('dependency_versions','attestation')}))
