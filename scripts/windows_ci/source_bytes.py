"""Bind acceptance test fingerprints to an actual Git HEAD and raw bytes."""
import hashlib
import os
from pathlib import Path
import re
import subprocess


class SourceBytesRefused(ValueError):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _git(root, args, data=None):
    # Local, read-only Git plumbing; do not pass application credentials.
    names = ('PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT', 'TMP', 'TEMP',
             'LANG', 'LC_ALL', 'HOME', 'USERPROFILE', 'XDG_CONFIG_HOME')
    env = {name: os.environ[name] for name in names if name in os.environ}
    try:
        result = subprocess.run(['git', '-C', str(root), *args], input=data,
                                **({'stdin': subprocess.DEVNULL} if data is None else {}),
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                env=env, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired):
        raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE') from None
    if result.returncode:
        raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')
    return result.stdout


def verify_head(root, expected_head):
    if not isinstance(expected_head, str) or not re.fullmatch(r'[0-9a-f]{40}', expected_head):
        raise SourceBytesRefused('SOURCE_HEAD_MISMATCH')
    try:
        actual = _git(root, ['rev-parse', '--verify', 'HEAD']).strip().decode('ascii')
    except (UnicodeError, SourceBytesRefused):
        raise SourceBytesRefused('SOURCE_HEAD_UNAVAILABLE') from None
    if actual != expected_head:
        raise SourceBytesRefused('SOURCE_HEAD_MISMATCH')
    return actual


def verify_head_test_sources(root, expected_head, hashes):
    """Require HEAD blob == manifest SHA256 == working-tree raw bytes.

    Git's checkout conversion is not an integrity exception. A manual CRLF
    conversion or a forged fingerprint still fails this three-way contract.
    """
    verify_head(root, expected_head)
    if not isinstance(hashes, dict) or not hashes or len(hashes) > 1024:
        raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')
    for path in hashes:
        if not isinstance(path, str) or not re.fullmatch(r'tests/test_[A-Za-z0-9_]+\.py', path):
            raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')
        if not isinstance(hashes[path], str) or not re.fullmatch(r'[0-9a-f]{64}', hashes[path]):
            raise SourceBytesRefused('GIT_BLOB_MISMATCH')
    paths = sorted(hashes)
    queries = ''.join(expected_head + ':' + path + '\n' for path in paths).encode('ascii')
    checks = _git(root, ['cat-file', '--batch-check'], queries).splitlines()
    if len(checks) != len(paths):
        raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')
    sizes = []
    for check in checks:
        match = re.fullmatch(rb'([0-9a-f]{40}) blob ([0-9]{1,10})', check)
        if not match:
            raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')
        sizes.append(int(match[2]))
    limit = 4 * 1024 * 1024
    if any(size > limit for size in sizes):
        raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')
    root = Path(root).resolve()
    batch_start = 0
    while batch_start < len(paths):
        batch_end, batch_bytes = batch_start, 0
        while batch_end < len(paths) and batch_bytes + sizes[batch_end] <= limit:
            batch_bytes += sizes[batch_end]
            batch_end += 1
        # Keep the complete source set. Only each cat-file body read is bounded;
        # cumulative bytes/call count can exceed the former aggregate 4 MiB.
        batch_queries = ''.join(expected_head + ':' + path + '\n'
                                for path in paths[batch_start:batch_end]).encode('ascii')
        raw = _git(root, ['cat-file', '--batch'], batch_queries)
        cursor = 0
        for path, header, size in zip(paths[batch_start:batch_end], checks[batch_start:batch_end], sizes[batch_start:batch_end]):
            end = raw.find(b'\n', cursor, cursor + 256)
            if end < 0 or raw[cursor:end] != header:
                raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')
            cursor = end + 1
            blob = raw[cursor:cursor + size]
            cursor += size
            if raw[cursor:cursor + 1] != b'\n' or len(blob) != size:
                raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')
            cursor += 1
            work_file = root / path
            try:
                if work_file.is_symlink() or work_file.resolve().parent != root / 'tests':
                    raise SourceBytesRefused('GIT_BLOB_MISMATCH')
                if work_file.stat().st_size != size:
                    raise SourceBytesRefused('GIT_BLOB_MISMATCH')
                with work_file.open('rb') as stream:
                    work = stream.read(size + 1)
            except OSError:
                raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE') from None
            if hashlib.sha256(blob).hexdigest() != hashes[path] or work != blob:
                raise SourceBytesRefused('GIT_BLOB_MISMATCH')
        if cursor != len(raw):
            raise SourceBytesRefused('GIT_BLOB_UNAVAILABLE')
        batch_start = batch_end
