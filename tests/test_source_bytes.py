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


def large_sources(source, *, size=2 * 1024 * 1024, count=2):
    """Owned Git data only; no application/acceptance test is executed."""
    root, _, hashes = source
    for index in range(count):
        path = root / ('tests/test_zlarge_' + str(index) + '.py')
        path.write_bytes(b'#' + b'x' * (size - 2) + b'\n')
        hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    git(root, 'add', '.')
    git(root, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'bounded source fixture')
    return root, git(root, 'rev-parse', 'HEAD').decode().strip(), hashes


def test_more_than_four_mib_checks_all_sources_in_bounded_reads(source, monkeypatch):
    from scripts.windows_ci import source_bytes
    root, head, hashes = large_sources(source)
    original = source_bytes._git
    batches = []
    def observe(root, args, data=None):
        if args == ['cat-file', '--batch']:
            paths = [line.split(':', 1)[1] for line in data.decode().splitlines()]
            batches.append(paths)
            assert sum((root / path).stat().st_size for path in paths) <= 4 * 1024 * 1024
        return original(root, args, data)
    monkeypatch.setattr(source_bytes, '_git', observe)
    assert sum((root / path).stat().st_size for path in hashes) > 4 * 1024 * 1024
    verify_head_test_sources(root, head, hashes)
    assert len(batches) == 2 and [path for batch in batches for path in batch] == sorted(hashes)


@pytest.mark.parametrize('change', ['byte', 'forged_hash', 'crlf', 'staged'])
def test_later_batch_raw_tampering_is_still_refused(source, change):
    root, head, hashes = large_sources(source)
    path = root / sorted(hashes)[-1]
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b'\n', b'\r\n') if change == 'crlf' else b'!' + raw[1:])
    if change == 'forged_hash':hashes[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    if change == 'staged':git(root, 'add', '.')
    with pytest.raises(SourceBytesRefused, match='GIT_BLOB_MISMATCH'):
        verify_head_test_sources(root, head, hashes)


def test_exact_four_mib_file_can_use_its_own_bounded_batch(source):
    root, head, hashes = large_sources(source, size=4 * 1024 * 1024, count=1)
    verify_head_test_sources(root, head, hashes)


def test_single_oversize_blob_refuses_before_any_body_read(source, monkeypatch):
    from scripts.windows_ci import source_bytes
    root, head, hashes = large_sources(source, size=4 * 1024 * 1024 + 1, count=1)
    original = source_bytes._git
    def bounded(root, args, data=None):
        assert args != ['cat-file', '--batch'], 'oversize input must not be read'
        return original(root, args, data)
    monkeypatch.setattr(source_bytes, '_git', bounded)
    with pytest.raises(SourceBytesRefused, match='GIT_BLOB_UNAVAILABLE'):
        verify_head_test_sources(root, head, hashes)


@pytest.mark.parametrize('change', ['header', 'short', 'separator', 'tail'])
def test_later_batch_bad_protocol_is_not_partial_success(source, monkeypatch, change):
    from scripts.windows_ci import source_bytes
    root, head, hashes = large_sources(source)
    original = source_bytes._git
    reads = []
    def broken(root, args, data=None):
        raw = original(root, args, data)
        if args == ['cat-file', '--batch']:
            reads.append(data)
            if len(reads) == 2:
                if change == 'header':return b'!' + raw[1:]
                if change == 'short':return raw[:-2]
                if change == 'separator':return raw[:-1] + b'!'
                return raw + b'\n'
        return raw
    monkeypatch.setattr(source_bytes, '_git', broken)
    with pytest.raises(SourceBytesRefused, match='GIT_BLOB_UNAVAILABLE'):
        verify_head_test_sources(root, head, hashes)
    assert len(reads) == 2
