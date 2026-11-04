import json
import secrets

import pytest

pytest.importorskip('cryptography')
from parkweave.local_identity import LocalSessionVault
from parkweave.store import Denied


def test_role_sealing_tamper_and_physical_binding_are_read_only(tmp_path):
    passwords = {role: secrets.token_urlsafe(24) for role in ('enterprise', 'specialist')}
    marker = dict(system_identifier='1234567', database_oid=1234,
                  ids=dict(enterprise='local-enterprise', specialist='local-reviewer'))
    provider = LocalSessionVault(passwords)
    tokens = provider.generate()
    provider.publish(tmp_path, marker)
    path = tmp_path / provider.filename
    ciphertext = path.read_bytes()
    for role in passwords:
        assert LocalSessionVault.unlock(tmp_path, marker, role, passwords[role]) == tokens[role]
        assert tokens[role].encode() not in ciphertext
    with pytest.raises(Denied):
        LocalSessionVault.unlock(tmp_path, marker, 'enterprise', passwords['specialist'])
    with pytest.raises(Denied):
        LocalSessionVault.unlock(tmp_path, {**marker, 'database_oid':1235}, 'enterprise', passwords['enterprise'])
    copied = tmp_path / 'copied'
    copied.mkdir(mode=0o700)
    (copied / provider.filename).write_bytes(ciphertext)
    (copied / provider.filename).chmod(0o600)
    with pytest.raises(Denied):
        LocalSessionVault.unlock(copied, marker, 'enterprise', passwords['enterprise'])
    value = json.loads(ciphertext)
    value['roles']['enterprise'][2] = value['roles']['specialist'][2]
    changed = json.dumps(value).encode()
    path.write_bytes(changed)
    with pytest.raises(Denied):
        LocalSessionVault.unlock(tmp_path, marker, 'enterprise', passwords['enterprise'])
    assert path.read_bytes() == changed
    assert not (tmp_path / 'sessions.json').exists()
