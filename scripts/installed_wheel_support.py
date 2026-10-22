"""Offline final-wheel installation using copies of existing pinned dependencies."""
from hashlib import sha1,sha256
from importlib.metadata import distribution
import json,os,re,shutil,subprocess,sys,tempfile,venv,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=('ordinary_synthetic_demo.py','material_only_demo.py','linux_fixture_server.py','local_demo_inputs.py')


def run(argv,*,cwd,env,timeout,log):
    with log.open('wb') as stream:
        result=subprocess.run(argv,cwd=cwd,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
    assert result.returncode==0,'offline package command failed;private log retained'


def build(directory):
    """Use the already installed builder; never resolve/install build dependencies."""
    directory.mkdir(mode=0o700)
    source=directory/'source';source.mkdir()
    for name in ('pyproject.toml','README.md','LICENSE'):
        if (ROOT/name).is_file():shutil.copy2(ROOT/name,source/name)
    shutil.copytree(ROOT/'src',source/'src',ignore=shutil.ignore_patterns('__pycache__','*.egg-info'))
    wheels=directory/'wheels';wheels.mkdir()
    env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ}
    env.update(PIP_NO_INDEX='1',PIP_CONFIG_FILE='/dev/null',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONDONTWRITEBYTECODE='1')
    run([sys.executable,'-I','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation','--wheel-dir',str(wheels),'.'],cwd=source,env=env,timeout=30,log=directory/'build.log')
    found=list(wheels.glob('*.whl'));assert len(found)==1
    return found[0]


def package_manifest(wheel):
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    metadata=json.loads(wheel.with_name('package-source.json').read_text())
    assert wheel.name==metadata['file'] and wheel.stat().st_size==metadata['bytes']
    assert sha256(wheel.read_bytes()).hexdigest()==metadata['sha256']
    assert re.fullmatch('[0-9a-f]{40}',metadata['package_source_sha'])
    tree=subprocess.check_output(['git','ls-tree','-r',head,'--','src/parkweave'],cwd=ROOT,text=True)
    blobs={line.split('\t',1)[1]:line.split()[2] for line in tree.splitlines()}
    files={}
    with zipfile.ZipFile(wheel) as z:
        for info in z.infolist():
            if info.filename.startswith('parkweave/') and not info.is_dir():
                assert '..' not in Path(info.filename).parts and not info.filename.endswith(('.pyc','.pth'))
                raw=z.read(info);source=ROOT/'src'/info.filename
                assert source.is_file() and not source.is_symlink() and raw==source.read_bytes()
                assert sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()==blobs['src/'+info.filename]
                files[info.filename]=sha256(raw).hexdigest()
    assert {p.relative_to(ROOT/'src').as_posix() for p in (ROOT/'src/parkweave').rglob('*.py')}=={p for p in files if p.endswith('.py')}
    assert all('parkweave/'+name in files for name in ('local-resource-approval-schema.sql','schema.sql','web.html','local_resource_approval.py'))
    return files


def install(wheel,directory):
    """Fresh venv, dependency files copied from explicit existing distributions."""
    directory.mkdir(mode=0o700)
    env={k:os.environ[k] for k in ('PATH','LANG') if k in os.environ}
    env.update(PIP_NO_INDEX='1',PIP_CONFIG_FILE='/dev/null',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONDONTWRITEBYTECODE='1')
    target=directory/'venv';venv.EnvBuilder(with_pip=True,system_site_packages=False).create(target)
    python=target/'bin/python'
    pure=Path(subprocess.check_output([str(python),'-I','-c','import sysconfig;print(sysconfig.get_path("purelib"))'],env=env,text=True).strip())
    roots={};versions={}
    for line in (ROOT/'requirements-linux-evidence.txt').read_text().splitlines():
        if not line or line.startswith('#'):continue
        name,version=line.split('==');dist=distribution(name);assert dist.version==version
        versions[name]=version;base=Path(dist.locate_file('')).resolve()
        direct=dist.read_text('direct_url.json')
        assert not direct or not json.loads(direct).get('dir_info',{}).get('editable')
        for item in dist.files or ():
            first=Path(str(item)).parts[0]
            if first in ('.','..') or first.endswith(('.pth','.egg-link')):continue
            assert re.fullmatch(r'[A-Za-z0-9_.-]+',first) and not first.startswith(('parkweave','__editable__'))
            source=base/first
            if source.exists():
                assert not source.is_symlink() and source.resolve().is_relative_to(base)
                if first in roots:assert roots[first]==source
                roots[first]=source
    assert len(roots)<=256
    copied=0;count=0
    for name,source in sorted(roots.items()):
        dest=pure/name;assert not dest.exists()
        paths=list(source.rglob('*')) if source.is_dir() else [source]
        for path in paths:
            if path.is_file():
                assert not path.is_symlink() and not path.stat().st_mode&0o6000
                copied+=path.stat().st_size;count+=1
        assert copied<=256*1024*1024 and count<=15000
        if source.is_dir():shutil.copytree(source,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
        else:shutil.copy2(source,dest)
    assert not list(pure.glob('*.pth')) and not list(pure.glob('*.egg-link'))
    wheel_input=directory/'wheel-input';wheel_input.mkdir();local_wheel=wheel_input/wheel.name;shutil.copy2(wheel,local_wheel)
    run([str(python),'-I','-m','pip','install','--no-index','--no-deps','--no-compile',str(local_wheel.resolve())],cwd=directory,env=env,timeout=25,log=directory/'install.log')
    assert not list(pure.glob('*.pth')) and not list(pure.glob('*.egg-link'))
    harness=directory/'harness';(harness/'scripts').mkdir(parents=True);(harness/'src').mkdir()
    for name in SCRIPTS:
        source=ROOT/'scripts'/name
        assert source.read_bytes()==subprocess.check_output(['git','show','HEAD:scripts/'+name],cwd=ROOT)
        shutil.copy2(source,harness/'scripts'/name)
    shutil.copy2(ROOT/'scripts/installed_wheel_entry.py',harness/'entry.py')
    manifest=dict(wheel_sha256=sha256(wheel.read_bytes()).hexdigest(),wheel_bytes=wheel.stat().st_size,
        frozen_package_source=json.loads(wheel.with_name('package-source.json').read_text()),
        checked_out_source_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        package_files=package_manifest(wheel),python=str(python),prefix=str(target),purelib=str(pure),
        forbidden_roots=[str(ROOT),str(ROOT/'src')],dependency_versions=versions,dependency_copy_bytes=copied,
        dependency_copy_files=count,dependency_downloads=0,system_site_packages=False,
        entrypoint_sha256=sha256((harness/'entry.py').read_bytes()).hexdigest(),
        harness_scripts={name:sha256((harness/'scripts'/name).read_bytes()).hexdigest() for name in SCRIPTS})
    (harness/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    return python,harness,manifest
