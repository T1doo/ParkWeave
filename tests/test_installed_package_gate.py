"""Actual offline wheel: reject missing declared resources before installation."""
from hashlib import sha256
import csv,io,json,subprocess,warnings,zipfile
import pytest
from scripts import installed_wheel_support as installed


def metadata(wheel,source):
    wheel.with_name('package-source.json').write_text(json.dumps(dict(package_source_sha=source,file=wheel.name,
        bytes=wheel.stat().st_size,sha256=sha256(wheel.read_bytes()).hexdigest()))+'\n')


@pytest.fixture(scope='module')
def current_wheel(tmp_path_factory):
    wheel=installed.build(tmp_path_factory.mktemp('package-gate')/'build')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=installed.ROOT,text=True).strip()
    metadata(wheel,source)
    return wheel,source


def test_current_package_has_complete_declared_resources_and_new_observation(current_wheel):
    wheel,_=current_wheel;files=installed.package_manifest(wheel)
    assert all('parkweave/'+name in files for name in ('difference_observation.py','local_resource_approval.py',
        'migration-033.sql','local-resource-approval-schema.sql','web.html','park_demo_web.html'))


@pytest.mark.parametrize('fault',['parkweave/park_demo_web.html','parkweave/migration-033.sql','NONEXISTENT_SOURCE','DUPLICATE_MEMBER'])
def test_invalid_package_never_reaches_venv_or_pip(current_wheel,tmp_path,monkeypatch,fault):
    original,source=current_wheel;wheel=tmp_path/original.name
    with zipfile.ZipFile(original) as source_zip,zipfile.ZipFile(wheel,'w') as target:
        for item in source_zip.infolist():
            if item.filename==fault:continue
            data=source_zip.read(item)
            if item.filename.endswith('.dist-info/RECORD'):
                lines=[r for r in csv.reader(io.StringIO(data.decode())) if r[0]!=fault]
                text=io.StringIO(newline='');csv.writer(text).writerows(lines);data=text.getvalue().encode()
            target.writestr(item,data)
        if fault=='DUPLICATE_MEMBER':
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                target.writestr('parkweave/web.html',source_zip.read('parkweave/web.html'))
    metadata(wheel,'0'*40 if fault=='NONEXISTENT_SOURCE' else source)
    def forbidden(*args,**kwargs):pytest.fail('invalid package reached virtualenv creation')
    monkeypatch.setattr(installed.venv,'EnvBuilder',forbidden)
    directory=tmp_path/'must-not-exist'
    message='Git object unavailable' if fault=='NONEXISTENT_SOURCE' else 'duplicate wheel member' if fault=='DUPLICATE_MEMBER' else 'package file set differs'
    with pytest.raises(AssertionError,match=message):installed.install(wheel,directory)
    assert not directory.exists()


def test_owned_guide_close_preserves_body_and_cleanup_errors():
    from types import SimpleNamespace
    from scripts.local_approval_installed_browser_once import close_guide
    primary=AssertionError('controlled original guide failure');cleanup=RuntimeError('controlled owned guide close failure')
    class Guide:
        def close(self):raise cleanup
    run=SimpleNamespace(report={})
    with pytest.raises(BaseExceptionGroup) as raised:close_guide(run,Guide(),primary)
    assert raised.value.exceptions==(primary,cleanup)
    assert run.report['guide_close_error']==dict(error_type='RuntimeError',error=str(cleanup))


def test_owned_guide_close_alone_keeps_its_actual_error():
    from types import SimpleNamespace
    from scripts.local_approval_installed_browser_once import close_guide
    cleanup=RuntimeError('controlled owned guide close failure')
    class Guide:
        def close(self):raise cleanup
    with pytest.raises(RuntimeError) as raised:close_guide(SimpleNamespace(report={}),Guide(),None)
    assert raised.value is cleanup
