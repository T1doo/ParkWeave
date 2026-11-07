import pytest
from scripts.windows_portable.source_identity import validate,from_manifest,matches_manifest


def test_legacy_git_identity_is_preserved_exactly():
    value={'source_commit':'a'*40,'manifest_sha256':'b'*64}
    assert validate(value)==value
    assert from_manifest({'source_commit':'a'*40},'b'*64)==value


def test_snapshot_identity_is_not_a_git_commit_and_cannot_cross_match():
    manifest={'source_commit':None,'source_snapshot_sha256':'c'*64}
    value=from_manifest(manifest,'b'*64)
    assert value=={'source_snapshot_sha256':'c'*64,'manifest_sha256':'b'*64}
    assert matches_manifest(manifest,value)
    assert not matches_manifest({'source_commit':'c'*40},value)
    assert not matches_manifest({**manifest,'source_snapshot_sha256':'d'*64},value)


@pytest.mark.parametrize('value',[
    {'source_commit':None,'manifest_sha256':'b'*64},
    {'source_commit':'a'*40,'source_snapshot_sha256':'c'*64,'manifest_sha256':'b'*64},
    {'source_snapshot_sha256':'c'*40,'manifest_sha256':'b'*64},
    {'source_snapshot_sha256':'c'*64,'manifest_sha256':'bad'},
])
def test_incomplete_ambiguous_or_unpinned_identity_is_refused(value):
    with pytest.raises(ValueError):validate(value)


def test_manifest_with_two_source_identities_is_refused():
    with pytest.raises(ValueError):from_manifest({'source_commit':'a'*40,'source_snapshot_sha256':'c'*64},'b'*64)
