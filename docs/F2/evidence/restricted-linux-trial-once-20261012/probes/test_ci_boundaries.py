"""Pure pre-trigger boundaries only: no host, service, SQL or permission actions."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import stat
import os
import pytest

ROOT=Path(__file__).resolve().parents[3]


def load(name):
    spec=importlib.util.spec_from_file_location('independent_trial_'+name,ROOT/'scripts/linux_trial'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


@pytest.mark.parametrize('bad',['owner','seals','size'])
def test_helper_rejects_untrusted_descriptor_before_private_read(monkeypatch,bad):
    m=load('worker');seals=m.fcntl.F_SEAL_SEAL|m.fcntl.F_SEAL_WRITE|m.fcntl.F_SEAL_GROW|m.fcntl.F_SEAL_SHRINK
    monkeypatch.setattr(m.os,'fstat',lambda fd:SimpleNamespace(st_uid=1000 if bad=='owner' else 0,
        st_mode=stat.S_IFREG|0o600,st_size=524289 if bad=='size' else 12))
    monkeypatch.setattr(m.fcntl,'fcntl',lambda *args:0 if bad=='seals' else seals)
    monkeypatch.setattr(m.os,'pread',lambda *args:pytest.fail('untrusted descriptor reached private read'))
    with pytest.raises(PermissionError):m.sealed_input(9876)


def test_setup_refuses_wrong_actual_pg_uid_before_proof_or_sql(monkeypatch):
    m=load('worker')
    monkeypatch.setattr(m.os,'geteuid',lambda:0)
    monkeypatch.setattr(m,'capture_fixture_cluster',lambda *args:pytest.fail('wrong UID reached proof'))
    with pytest.raises(PermissionError):m.setup({'pg_uid':10001})


def context():
    return dict(root='/tmp/SYNTHETIC_NO_REAL_DIRECTORY',source_sha='a'*40)


def test_controller_refuses_unowned_child_before_signal():
    m=load('controller');c=m.Controller(context())
    child=SimpleNamespace(poll=lambda:pytest.fail('unowned child inspected'),send_signal=lambda *a:pytest.fail('unowned child signaled'))
    with pytest.raises(PermissionError):c.stop(child)


def test_cleanup_failure_is_not_reported_as_owned_stop_pass():
    m=load('controller');c=m.Controller(context())
    child=object();c.processes.append(child)
    def refuse(process):raise PermissionError('SYNTHETIC cleanup refusal')
    c.stop=refuse
    assert c.cleanup() is False
    assert c.value['cleanup'] is False and c.value['cases']['OWNED_STOP']=='FAIL'
    assert m.public_summary(c.value)['cases']['OWNED_STOP']=='FAIL'
