"""Explicit Linux seal observations only; no actual FD/kernel/host operation."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import stat
import pytest

ROOT=Path(__file__).resolve().parents[3]


@pytest.mark.parametrize('bad',['owner','seals','size'])
def test_helper_rejects_untrusted_descriptor_before_private_read(bad,monkeypatch):
    spec=importlib.util.spec_from_file_location('independent_trial_sealed_worker',ROOT/'scripts/linux_trial/worker.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    # Synthetic observation constants, not a physical capability restoration.
    for name,value in {'F_SEAL_SEAL':1,'F_SEAL_SHRINK':2,'F_SEAL_GROW':4,'F_SEAL_WRITE':8,'F_GET_SEALS':1034}.items():
        monkeypatch.setattr(m.fcntl,name,value,raising=False)
    monkeypatch.setattr(m.os,'fstat',lambda fd:SimpleNamespace(st_uid=1000 if bad=='owner' else 0,
        st_mode=stat.S_IFREG|0o600,st_size=524289 if bad=='size' else 12))
    monkeypatch.setattr(m.fcntl,'fcntl',lambda *args:0 if bad=='seals' else 15)
    monkeypatch.setattr(m.os,'pread',lambda *args:pytest.fail('untrusted descriptor reached private read'))
    with pytest.raises(PermissionError):m.sealed_input(9876)
