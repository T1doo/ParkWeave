from pathlib import Path
from importlib.metadata import distribution
import json,os,shutil,subprocess,venv
out=Path(__file__).parent;target=out/'builder-only-corrected';venv.EnvBuilder(with_pip=True,system_site_packages=False).create(target)
python=target/'bin/python';env=dict(PATH=os.environ['PATH'],LANG='C.UTF-8',PIP_NO_INDEX='1',PIP_CONFIG_FILE='/dev/null',PIP_DISABLE_PIP_VERSION_CHECK='1')
pure=Path(subprocess.check_output([str(python),'-I','-B','-c','import sysconfig;print(sysconfig.get_path("purelib"))'],env=env,text=True).strip())
dist=distribution('setuptools');assert dist.version=='80.9.0';base=Path(dist.locate_file('')).resolve();names=set()
for item in dist.files or ():
 name=Path(str(item)).parts[0]
 if name in ('.','..') or name.endswith(('.pth','.egg-link')):continue
 names.add(name)
assert names=={'setuptools','_distutils_hack','pkg_resources','setuptools-80.9.0.dist-info'}
for name in names:shutil.copytree(base/name,pure/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
assert not list(pure.glob('wheel*')) and not list(pure.glob('*.pth'))
code='''import importlib.util,json,sys
from pathlib import Path
from importlib.metadata import version
assert sys.flags.isolated and version('setuptools')=='80.9.0'
assert not list(Path(sys.prefix).glob('lib/python*/site-packages/wheel*'))
spec=importlib.util.spec_from_file_location('owned_installed_support',sys.argv[1]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
wheel=module.build(Path(sys.argv[2]))
import setuptools
import wheel.wheelfile as vendor
assert '/setuptools/_vendor/wheel/' in vendor.__file__
print(json.dumps(dict(isolated=True,setuptools=version('setuptools'),external_wheel=False,vendored_wheel_path=vendor.__file__,wheel=str(wheel),wheel_bytes=wheel.stat().st_size,dependency_downloads=0)))
'''
with (out/'builder-only.log').open('w') as log:result=subprocess.run([str(python),'-I','-B','-c',code,'/workspace/ParkWeave/scripts/installed_wheel_support.py',str(out/'builder-only-build')],cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=40)
assert result.returncode==0,'minimal original builder failed; log preserved'
report=json.loads((out/'builder-only.log').read_text());(out/'builder-only.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
