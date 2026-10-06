"""Raw Git/work-tree integrity controls; local fixtures only."""
import hashlib
from pathlib import Path
import subprocess

import pytest

from scripts.windows_ci.source_bytes import SourceBytesRefused, verify_head_test_sources


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.DEVNULL)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / 'producer'
    root.mkdir()
    git(root, 'init')
    (root / 'tests').mkdir()
    (root / '.gitattributes').write_bytes(b'* text=auto\ntests/*.py text eol=lf\n')
    (root / 'tests/test_one.py').write_bytes(b'def test_one():\n    assert True\n')
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'fixture')
    head = git(root, 'rev-parse', 'HEAD').decode().strip()
    checkout = tmp_path / 'checkout'
    subprocess.check_call(['git', 'clone', '--no-checkout', str(root), str(checkout)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    git(checkout, 'config', 'core.autocrlf', 'true')
    git(checkout, 'checkout', head)
    hashes = {'tests/test_one.py': hashlib.sha256((root / 'tests/test_one.py').read_bytes()).hexdigest()}
    return checkout, head, hashes


def test_autocrlf_checkout_preserves_bound_lf(source):
    root, head, hashes = source
    assert b'\r' not in (root / 'tests/test_one.py').read_bytes()
    verify_head_test_sources(root, head, hashes)


@pytest.mark.parametrize('change', ['crlf', 'byte', 'forged_hash', 'staged'])
def test_raw_tampering_is_refused(source, change):
    root, head, hashes = source
    path = root / 'tests/test_one.py'
    data = path.read_bytes()
    path.write_bytes(data.replace(b'\n', b'\r\n') if change == 'crlf' else data + b'# changed\n')
    if change == 'forged_hash':
        hashes['tests/test_one.py'] = hashlib.sha256(path.read_bytes()).hexdigest()
    if change == 'staged':
        git(root, 'add', '.')
    with pytest.raises(SourceBytesRefused, match='GIT_BLOB_MISMATCH'):
        verify_head_test_sources(root, head, hashes)


@pytest.mark.parametrize('head', ['0' * 40, 'bad', 'A' * 40])
def test_wrong_or_malformed_claim_refused(source, head):
    root, _, hashes = source
    with pytest.raises(SourceBytesRefused, match='SOURCE_HEAD_MISMATCH'):
        verify_head_test_sources(root, head, hashes)


def test_untracked_file_not_bound_to_head(source):
    root, head, hashes = source
    path = root / 'tests/test_extra.py'
    path.write_bytes(b'# untracked\n')
    hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(SourceBytesRefused, match='GIT_BLOB_UNAVAILABLE'):
        verify_head_test_sources(root, head, hashes)


@pytest.mark.parametrize('operation,reason', [('rev-parse','SOURCE_HEAD_UNAVAILABLE'), ('cat-file','GIT_BLOB_UNAVAILABLE')])
def test_git_timeout_has_fixed_operation_reason(source, monkeypatch, operation, reason):
    root, head, hashes = source
    original = subprocess.run
    def run(command, **kwargs):
        assert kwargs['timeout'] == 5
        if operation in command:
            raise subprocess.TimeoutExpired(command, 5)
        return original(command, **kwargs)
    monkeypatch.setattr(subprocess, 'run', run)
    with pytest.raises(SourceBytesRefused, match=reason):
        verify_head_test_sources(root, head, hashes)
