"""Real sealed fixture identities/PG; availability failures never reset accounts."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

from fastapi.testclient import TestClient
import pytest

from parkweave.local_identity import LocalSessionVault,LocalIdentityStorageUnavailable
from parkweave.local_installation import PersistentInstallation
from scripts import local_product as product,material_only_demo as material

pytestmark=pytest.mark.skipif(sys.platform!='linux',reason='Linux sealed local installation only')


def short_parent():
    base=material.ROOT/'.runtime'/'ir';base.mkdir(mode=0o700,parents=True,exist_ok=True)
    parent=base/secrets.token_hex(4);parent.mkdir(mode=0o700)
    return parent


@pytest.mark.parametrize('fault',['MISSING','MALFORMED','SYMLINK'])
def test_missing_or_damaged_identity_has_safe_recovery_and_original_restore(tmp_path,fault):
    parent=short_parent()
    passwords={role:secrets.token_urlsafe(24) for role in ('enterprise','specialist')}
    oldmask=os.umask(0o077)
    try:path=product.install(LocalSessionVault(passwords),parent)
    finally:os.umask(oldmask)
    marker=json.loads((path/'state.json').read_text());vault=path/LocalSessionVault.filename
    original=vault.read_bytes();backup=path/'original-sealed-fixture-retained';vault.rename(backup)
    if fault=='MALFORMED':vault.write_bytes(b'{"roles":"NOT_A_VALID_SEALED_DOCUMENT"}');vault.chmod(0o600)
    if fault=='SYMLINK':vault.symlink_to(backup.name)
    base='http://127.0.0.1:58764'
    with PersistentInstallation.open_existing(path) as lease,lease.postgres():
        with lease.connect() as connection:before=material.authority(connection)
        app=product.application(path,marker,58764)
        with TestClient(app,base_url=base,client=('127.0.0.1',12345)) as client:
            for _ in range(7):
                result=client.post('/api/local/session',headers={'Origin':base},
                    json=dict(role='enterprise',password=passwords['enterprise']))
                assert result.status_code==503
                value=result.json()
                assert value['code']=='LOCAL_IDENTITY_STORAGE_UNAVAILABLE' and value['automatic_reset'] is False
                assert value['recovery']=='RESTORE_ORIGINAL_SEALED_IDENTITIES'
                assert all(secret not in result.text for secret in (*passwords.values(),str(path)))
            if vault.is_symlink() or vault.exists():vault.unlink()  # Only this test's replacement.
            backup.rename(vault)  # Exact original ciphertext, not regeneration.
            for role in ('enterprise','specialist'):
                result=client.post('/api/local/session',headers={'Origin':base},
                    json=dict(role=role,password=passwords[role]))
                assert result.status_code==200 and result.json()['actor_id']==marker['ids'][role]
            wrong=client.post('/api/local/session',headers={'Origin':base},
                json=dict(role='enterprise',password=passwords['specialist']))
            assert wrong.status_code==403 and 'recovery' not in wrong.json()
        with lease.connect() as connection:assert material.authority(connection)==before
    assert vault.read_bytes()==original and not backup.exists()
    assert not (path/'sessions.json').exists() and not (path/'data/postmaster.pid').exists()


def test_actual_noninteractive_install_refuses_before_plaintext_fallback(tmp_path):
    parent=short_parent()
    result=subprocess.run([sys.executable,'-B','-m','scripts.local_product','install','--parent',str(parent)],
        cwd=material.ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
    assert result.returncode==1 and 'PRIVATE_TERMINAL_REQUIRED' in result.stderr
    assert not list(parent.iterdir())


@pytest.mark.parametrize('inputs,code',[
    (['short'],'PASSWORD_LENGTH'),
    (['SYNTHETIC-private-original','SYNTHETIC-private-different'],'PASSWORD_CONFIRMATION'),
    (['SYNTHETIC-private-identical']*4,'PASSWORD_DISTINCT'),
])
def test_invalid_password_setup_has_fixed_recovery_before_any_install(tmp_path,monkeypatch,capsys,inputs,code):
    parent=short_parent()
    monkeypatch.setattr(sys,'argv',['local-product','install','--parent',str(parent)])
    values=iter(inputs);monkeypatch.setattr(product,'private_password',lambda _:next(values))
    def forbidden(*args):pytest.fail('invalid setup must not initialize any product')
    monkeypatch.setattr(product,'install',forbidden)
    assert product.main()==1
    output=capsys.readouterr()
    assert code in output.err and all(value not in output.out+output.err for value in inputs)
    assert not list(parent.iterdir())


def test_missing_parent_refuses_before_requesting_password(tmp_path,monkeypatch,capsys):
    parent=Path('/tmp')/('pw-missing-'+secrets.token_hex(4))
    monkeypatch.setattr(sys,'argv',['local-product','install','--parent',str(parent)])
    def forbidden(*args):pytest.fail('invalid parent must refuse before any secret input')
    monkeypatch.setattr(product,'private_password',forbidden)
    assert product.main()==1 and 'INSTALL_PARENT_UNAVAILABLE' in capsys.readouterr().err
    assert not parent.exists()


def test_long_install_parent_is_explained_before_password_or_new_directory(tmp_path,monkeypatch,capsys):
    parent=tmp_path/('long-parent-'+'x'*70)
    monkeypatch.setattr(sys,'argv',['local-product','install','--parent',str(parent)])
    def forbidden(*args):pytest.fail('long installation path must refuse before secret input')
    monkeypatch.setattr(product,'private_password',forbidden)
    assert product.main()==1 and 'INSTALL_PARENT_TOO_LONG' in capsys.readouterr().err
    assert not parent.exists()


@pytest.mark.parametrize('failure,code',[(EOFError,'PASSWORD_INPUT_INTERRUPTED'),(OSError,'PRIVATE_TERMINAL_UNAVAILABLE')])
def test_terminal_input_failure_is_safe_and_does_not_install(monkeypatch,capsys,failure,code):
    monkeypatch.setattr(sys,'argv',['local-product','install'])
    def interrupted(*args):raise failure('SYNTHETIC private terminal message')
    monkeypatch.setattr(product.getpass,'getpass',interrupted)
    assert product.main()==1
    output=capsys.readouterr()
    assert code in output.err and 'SYNTHETIC private terminal message' not in output.out+output.err


def test_identity_close_error_refuses_before_decryption_without_retry(tmp_path,monkeypatch):
    from parkweave import local_identity as identity
    vault=tmp_path/LocalSessionVault.filename;vault.write_bytes(b'{}');vault.chmod(0o600)
    original=identity.os.close;calls=[]
    def close(fd):
        target=os.readlink('/proc/self/fd/'+str(fd))
        if target==str(vault):
            calls.append(fd);original(fd)
            raise OSError('SYNTHETIC private close detail')
        return original(fd)
    monkeypatch.setattr(identity.os,'close',close)
    with pytest.raises(LocalIdentityStorageUnavailable) as error:
        LocalSessionVault.unlock(tmp_path,{},'enterprise','SYNTHETIC invalid secret')
    assert str(error.value)=='LOCAL_IDENTITY_STORAGE_UNAVAILABLE' and len(calls)==1
