"""Positive protected-directory controls for executable-input rejection."""
from pathlib import Path
import stat
from types import SimpleNamespace
import pytest
from parkweave import native_run_access_restricted_host as host
from parkweave.store import Denied
from test_native_run_access_restricted_adapter import adapter_inputs


@pytest.mark.parametrize('relative',['__pycache__/store.cpython-312.pyc','native_run_access_writer.cpython-312-x86_64-linux-gnu.so'])
def test_valid_protected_source_then_executable_cache_or_extension_refused(monkeypatch,relative):
    _,_,data,_=adapter_inputs();layout=host.RuntimeLayout.model_validate(data)
    root=Path(data['source_root']+'/parkweave');source=Path(next(iter(data['source_files'])))
    unsafe=root/relative;nodes=[source];reads=[]
    def metadata(path):
        return SimpleNamespace(st_mode=(stat.S_IFDIR|0o755) if path==root or path in root.parents else (stat.S_IFREG|0o444),st_uid=0)
    monkeypatch.setattr(host.Path,'lstat',metadata)
    monkeypatch.setattr(host.Path,'rglob',lambda *args:iter(nodes))
    def source_reader(path,*args,**kwargs):
        reads.append((path,kwargs.get('expected')))
        return b'SYNTHETIC_VALIDATED_CODE_BYTES'
    monkeypatch.setattr(host,'_protected_bytes',source_reader)
    host._code_check(layout)
    assert reads==[(layout.interpreter,layout.interpreter_sha256),(str(source),data['source_files'][str(source)])]
    nodes.append(unsafe)
    with pytest.raises(Denied):host._code_check(layout)
