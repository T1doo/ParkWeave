"""Selected profile cannot silently add accounts to a retained sealed identity."""
import json,secrets
import pytest
from parkweave.local_identity import LocalSessionVault,SAMPLE_ROLES,SAMPLE_SCHEMA
from parkweave.store import Denied


def test_four_independent_password_accounts_are_sealed_and_profile_bound(tmp_path):
    passwords={r:secrets.token_urlsafe(24) for r in SAMPLE_ROLES}
    marker=dict(schema=SAMPLE_SCHEMA,system_identifier='1234567',database_oid=1234,
        ids={r:'local-sample-'+r for r in SAMPLE_ROLES})
    with pytest.raises(Denied):LocalSessionVault(passwords)
    duplicate={**passwords,'executor':passwords['enterprise']}
    with pytest.raises(Denied):LocalSessionVault(duplicate,sample_collaboration=True)
    vault=LocalSessionVault(passwords,sample_collaboration=True);tokens=vault.generate();vault.publish(tmp_path,marker)
    path=tmp_path/vault.filename;before=path.read_bytes();assert set(json.loads(before)['roles'])==set(SAMPLE_ROLES)
    for role in SAMPLE_ROLES:
        assert LocalSessionVault.unlock(tmp_path,marker,role,passwords[role])==tokens[role]
        assert tokens[role].encode() not in before and passwords[role].encode() not in before
        other=next(r for r in SAMPLE_ROLES if r!=role)
        with pytest.raises(Denied):LocalSessionVault.unlock(tmp_path,marker,role,passwords[other])
    with pytest.raises(Denied):LocalSessionVault.unlock(tmp_path,{**marker,'schema':'parkweave-local-material-installation/1'},'enterprise',passwords['enterprise'])
    assert path.read_bytes()==before and not (tmp_path/'sessions.json').exists()


def test_sample_config_regular_bound_and_hash_are_checked_before_read(tmp_path):
    import hashlib,os,time
    from parkweave.local_sample import environment,PROFILE,IDS
    directory=tmp_path/'local-sample';directory.mkdir(mode=0o700);p=directory/'config.json'
    marker=dict(schema=SAMPLE_SCHEMA,ids=IDS,sample=dict(profile=PROFILE,config_sha256=hashlib.sha256(b'{}').hexdigest()))
    p.write_bytes(b'{}');p.chmod(0o600)
    assert environment(tmp_path,marker)['PARKWEAVE_LOCAL_SYNTHETIC_DEMO_CONFIG']=='{}'
    p.write_bytes(b'X'*16385)
    with pytest.raises(Denied):environment(tmp_path,marker)
    p.unlink();os.mkfifo(p,0o600);start=time.monotonic()
    with pytest.raises(Denied):environment(tmp_path,marker)
    assert time.monotonic()-start<1
    p.unlink();p.write_bytes(b'[]');p.chmod(0o600)
    with pytest.raises(Denied):environment(tmp_path,marker)
