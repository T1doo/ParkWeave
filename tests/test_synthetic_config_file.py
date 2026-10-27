"""CONFIG first creation shares verified owner-only handle transaction."""
import os
from pathlib import Path
import pytest
import parkweave.synthetic_session_file as module
from test_synthetic_session_file import Backend


def config_path():
    return Path(module.__file__).resolve().parents[2]/'.runtime/windows-config.json'


def test_config_owner_verified_before_content_stream():
    backend=Backend()
    stream=module.create_synthetic_config_file(config_path(),_backend=backend)
    assert stream.getvalue()==''
    assert backend.events==['current_user','create_new','inspect1','owner_only','inspect2','verify_owner','transfer','free_descriptor2','free_descriptor1']


@pytest.mark.parametrize('fail',['current_user','create_new','inspect1','owner_only','inspect2','verify_owner','transfer'])
def test_config_owner_failure_never_transfers_content_or_reopens(fail):
    backend=Backend(fail=fail)
    with pytest.raises(module.SessionOwnerError):module.create_synthetic_config_file(config_path(),_backend=backend)
    assert backend.events.count('create_new')<=1
    if fail not in ('current_user','create_new'):assert backend.events[-1]=='close_exact'
    if fail!='transfer':assert 'transfer' not in backend.events


def test_config_dacl_change_and_other_path_refused():
    backend=Backend(changed=True)
    with pytest.raises(module.SessionOwnerError,match='SESSION_PERMISSIONS_CHANGED'):
        module.create_synthetic_config_file(config_path(),_backend=backend)
    assert 'transfer' not in backend.events and backend.events[-1]=='close_exact'
    backend=Backend()
    with pytest.raises(ValueError):module.create_synthetic_config_file('.runtime/windows-config.json',_backend=backend)
    assert not backend.events


@pytest.mark.skipif(os.name!='nt',reason='native Windows CONFIG owner-only creation required')
def test_native_config_first_creation_and_existing_bytes_protected(tmp_path,monkeypatch):
    # Separate owned test tree, never repository's existing CONFIG.
    monkeypatch.setattr(module,'__file__',str(tmp_path/'src/parkweave/synthetic_session_file.py'))
    path=config_path();path.parent.mkdir()
    with module.create_synthetic_config_file(path) as stream:stream.write('SYNTHETIC_CONFIG_ONLY')
    before=path.read_bytes()
    with pytest.raises(FileExistsError):module.create_synthetic_config_file(path)
    assert path.read_bytes()==before
