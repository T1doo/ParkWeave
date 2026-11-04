"""Real Python import behavior with held Linux test files; no native approval."""
from hashlib import sha256
import importlib
import importlib.metadata
import importlib.util
from importlib._bootstrap_external import _code_to_timestamp_pyc
import os
from pathlib import Path
import pkgutil
import sys
import subprocess

import pytest

from scripts.windows_ci.pinned_vendor_imports import PinnedVendorFinder


class HeldTestFiles:
    """Test-only FD reader. Never a NativeBootstrapPins or trial credential."""
    def __init__(self,root):
        self.payload=root;self.files={}
        for path in (root/'vendor').rglob('*'):
            if path.is_file():
                fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
                raw=os.pread(fd,path.stat().st_size+1,0)
                self.files[path.relative_to(root).as_posix()]=(fd,len(raw),sha256(raw).hexdigest())
    def read(self,name):
        if name not in self.files:raise FileNotFoundError('unlisted test file')
        fd,size,digest=self.files[name];raw=os.pread(fd,size+1,0)
        assert sha256(raw).hexdigest()==digest
        return raw
    def close(self):
        for fd,_,_ in self.files.values():os.close(fd)


def test_matching_mtime_pyc_injection_cannot_replace_pinned_source(tmp_path):
    package=tmp_path/'vendor/pw_pin_fixture';package.mkdir(parents=True)
    source=package/'__init__.py';source.write_text('TRUSTED = 1\n')
    (package/'data.txt').write_text('frozen resource')
    metadata=tmp_path/'vendor/pw_pin_fixture-0.1.2.dist-info';metadata.mkdir()
    (metadata/'METADATA').write_text('Metadata-Version: 2.1\nName: pw-pin-fixture\nVersion: 0.1.2\n')
    pins=HeldTestFiles(tmp_path)
    # Added AFTER pinning. -B would not prevent a normal loader reading this.
    pyc=Path(importlib.util.cache_from_source(str(source)));pyc.parent.mkdir()
    pyc.write_bytes(_code_to_timestamp_pyc(compile('TRUSTED = 999\n',str(source),'exec'),
        int(source.stat().st_mtime),source.stat().st_size))
    ordinary=importlib.util.module_from_spec(importlib.util.spec_from_file_location('ordinary_pin_fixture',source))
    ordinary.__spec__.loader.exec_module(ordinary)
    assert ordinary.TRUSTED==999  # Actual exploit precondition, not an API double.
    (package/'injected.py').write_text('UNTRUSTED = True\n')
    (metadata/'entry_points.txt').write_text('[unlisted]\na = injected:main\n')
    finder=PinnedVendorFinder(pins).install()
    try:
        actual=importlib.import_module('pw_pin_fixture')
        assert actual.TRUSTED==1 and actual.__path__==['pinned-vendor://vendor/pw_pin_fixture']
        assert pkgutil.get_data('pw_pin_fixture','data.txt')==b'frozen resource'
        assert importlib.metadata.version('pw-pin-fixture')=='0.1.2'
        assert importlib.metadata.distribution('pw-pin-fixture').read_text('entry_points.txt') is None
        with pytest.raises(ModuleNotFoundError):importlib.import_module('pw_pin_fixture.injected')
    finally:
        sys.meta_path.remove(finder);sys.modules.pop('pw_pin_fixture',None);pins.close()


def test_fresh_no_site_bootstrap_cannot_fallback_to_ambient_packages(tmp_path):
    ambient=tmp_path/'site-packages';ambient.mkdir()
    (ambient/'pw_ambient_fixture.py').write_text('UNPINNED = True\n')
    repo=Path(__file__).resolve().parents[1]
    code='''import sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from scripts.windows_ci.pinned_vendor_imports import restrict_bootstrap_imports
sys.path.insert(0,sys.argv[2])
class Pins:
    files={}
    payload=Path(sys.argv[2])
restrict_bootstrap_imports(Path(sys.argv[1]),Pins())
try: import pw_ambient_fixture
except ModuleNotFoundError: pass
else: raise AssertionError('unlisted ambient package imported')
assert all('site-packages' not in p for p in sys.path)
'''
    result=subprocess.run([sys.executable,'-I','-B','-S','-c',code,str(repo),str(ambient)],
        text=True,capture_output=True,timeout=10)
    assert result.returncode==0,result.stderr
