"""Lease-bound, read-only PG payload snapshot. Never runtime activation proof.

Reuses original manifest/PE parsing and held-file pinning. Windows reads the
original issued installer's target pins; loader acceptance remains closed.
Only immutable PG payload names are read, never data/files/secrets contents.
"""
import hashlib
import math
import os
import re
import stat
import time

from . import payload
from .fixed_directories import FixedDirectoryLease
from .processes import PinnedPayloadFile, PayloadFileSpec

PG = 'runtime/postgresql/'
REQUIRED = frozenset(PG + name for name in (
    'bin/initdb.exe', 'bin/postgres.exe', 'bin/pg_ctl.exe', 'lib/plpgsql.dll',
    'share/postgres.bki', 'share/postgresql.conf.sample', 'share/pg_hba.conf.sample',
    'share/pg_ident.conf.sample', 'share/extension/plpgsql.control', 'share/extension/plpgsql--1.0.sql'))


class RuntimePayloadRefused(payload.PayloadRefused):
    pass


def require(value, code):
    if not value: raise RuntimePayloadRefused(code)


class RuntimePayloadPrerequisite:
    """One exact lease and externally frozen manifest/source, not a trust root.

    This checks a PG-only static snapshot. It does not verify the publisher,
    Python closure, native loading, symbols/forwarders or initdb's internal
    bootstrap/standalone backend and pipe-command execution.
    """
    def __init__(self, lease, *, manifest_sha256, source_commit, native_installation=None):
        require(type(lease) is FixedDirectoryLease, 'EXACT_FIXED_LEASE_REQUIRED')
        require(type(manifest_sha256) is str and re.fullmatch('[0-9a-f]{64}', manifest_sha256), 'EXTERNAL_MANIFEST_PIN_REQUIRED')
        require(type(source_commit) is str and re.fullmatch('[0-9a-f]{40}', source_commit), 'EXACT_SOURCE_PIN_REQUIRED')
        lease._verify()
        self.lease, self.manifest_sha256, self.source_commit = lease, manifest_sha256, source_commit
        self.binding = self._binding()
        self.failed = False
        self.native_installation = native_installation
        if native_installation is not None:
            from .native_runtime_staging import NativeRuntimeInstallation
            require(type(native_installation) is NativeRuntimeInstallation,'ORIGINAL_NATIVE_INSTALLATION_REQUIRED')
            native_installation._issued_binding(lease,dict(manifest_sha256=manifest_sha256,source_commit=source_commit))

    def _binding(self):
        return (bytes(self.lease.snapshot[0]), tuple(self.lease.snapshot[1]),
                tuple(self.lease.fs.root_id), tuple(self.lease.fs.lock_id))

    def _check(self, lease, deadline):
        require(not self.failed and lease is self.lease, 'SAME_PAYLOAD_LEASE_REQUIRED')
        require(type(deadline) in (int, float) and math.isfinite(deadline) and
                0 < deadline - time.monotonic() <= 30, 'PAYLOAD_DEADLINE')
        lease._verify()
        require(self._binding() == self.binding and lease.status() == 'CLUSTER', 'PAYLOAD_LEASE_STATE_CHANGED')

    def inspect(self, lease, deadline):
        held, primary, result = [], None, None
        try:
            self._check(lease, deadline)
            if os.name == 'nt':
                require(self.native_installation is not None,'NATIVE_PAYLOAD_ENUMERATION_NOT_ACCEPTED')
                result = self.native_installation.inspect_pg_static(lease,
                    dict(source_commit=self.source_commit,manifest_sha256=self.manifest_sha256),deadline)
                self._check(lease,deadline)
                return result
            # Native Windows uses the original issued installer pins above.
            require(os.name == 'posix' and os.scandir in os.supports_fd, 'NATIVE_PAYLOAD_ENUMERATION_NOT_ACCEPTED')
            def pin(name, row):
                self._check(lease, deadline)
                item = PinnedPayloadFile(lease, PayloadFileSpec(name, row['sha256'], row['bytes']))
                held.append(item.close)
                return item
            meta = os.stat(payload.MANIFEST, dir_fd=lease.fs.root, follow_symlinks=False)
            require(0 < meta.st_size <= 4 * 1024 * 1024, 'PAYLOAD_MANIFEST_SIZE')
            manifest_pin = pin(payload.MANIFEST, dict(bytes=meta.st_size, sha256=self.manifest_sha256))
            manifest = payload.parse_manifest(manifest_pin.read_bytes())
            require(manifest.get('source_commit') == self.source_commit and manifest.get('usable_product') is False and
                    manifest.get('native_initialization') == 'OWNER_MUTATION_PAUSED', 'PAYLOAD_SOURCE_OR_SCOPE_CHANGED')
            expected = {name: row for name, row in manifest['files'].items() if name.startswith(PG)}
            require(REQUIRED <= set(expected), 'PG_BOOTSTRAP_PAYLOAD_MISSING')
            # Pin the root through the same ancestor chain as every original
            # executable. The second held directory is runtime/postgresql.
            first = pin(PG + 'bin/postgres.exe', expected[PG + 'bin/postgres.exe'])
            require(len(first.directory_links) == 3, 'PG_RUNTIME_CHAIN_REQUIRED')
            pg_root = first.directory_links[1][2]
            actual, seen, directories = set(), set(), set()
            expected_dirs = {PG.rstrip('/')}
            for name in expected:
                parts = name.split('/')
                expected_dirs.update('/'.join(parts[:n]) for n in range(2, len(parts)))
            def scan(fd, prefix):
                self._check(lease, deadline)
                with os.scandir(fd) as entries:
                    for entry in entries:
                        name = prefix + '/' + entry.name; payload.safe_name(name)
                        require(name.casefold() not in seen and len(seen) < payload.MAX_FILES * 2, 'PG_RUNTIME_ALIAS_OR_LIMIT')
                        seen.add(name.casefold())
                        info = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                        require(not stat.S_ISLNK(info.st_mode), 'PG_RUNTIME_LINK')
                        if stat.S_ISDIR(info.st_mode):
                            require(name in expected_dirs, 'PG_RUNTIME_UNEXPECTED_DIRECTORY')
                            child = os.open(entry.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY | os.O_CLOEXEC, dir_fd=fd)
                            held.append(lambda child=child: os.close(child))
                            opened = os.fstat(child)
                            require((opened.st_dev, opened.st_ino) == (info.st_dev, info.st_ino) and
                                    opened.st_uid == os.geteuid() and not opened.st_mode & 0o077, 'PG_RUNTIME_DIRECTORY_CHANGED')
                            directories.add(name); scan(child, name)
                        else:
                            require(stat.S_ISREG(info.st_mode) and name in expected, 'PG_RUNTIME_UNEXPECTED_FILE')
                            actual.add(name)
            scan(pg_root, PG.rstrip('/'))
            require(actual == set(expected) and directories == expected_dirs - {PG.rstrip('/')}, 'PG_RUNTIME_SET_CHANGED')
            data, pins = {}, [manifest_pin, first]
            for name, row in expected.items():
                item = first if name == PG + 'bin/postgres.exe' else pin(name, row)
                if item is not first: pins.append(item)
                data[name] = item.read_bytes()
            # Same frozen bootstrap subset used by the existing builder. Do not
            # claim support for every optional extension merely present in share.
            report = static_report(data,dict(source_commit=self.source_commit,manifest_sha256=self.manifest_sha256))
            for item in pins:
                self._check(lease, deadline); item.verify()
            # Repeat actual name enumeration while original file/ancestor pins
            # are held. This is a cooperative snapshot, not a same-UID sandbox.
            actual.clear(); seen.clear(); directories.clear(); scan(pg_root, PG.rstrip('/'))
            require(actual == set(expected) and directories == expected_dirs - {PG.rstrip('/')}, 'PG_RUNTIME_SET_CHANGED')
            self._check(lease, deadline)
            result = report
        except BaseException as error:
            primary = error
            self.failed = True
        cleanup = []
        for close in reversed(held):
            try: close()
            except BaseException as error: cleanup.append(error)
        if cleanup:
            self.failed = True
            raise BaseExceptionGroup('RUNTIME_PAYLOAD_READ_AND_CLOSE_UNKNOWN', ([primary] if primary else []) + cleanup) from primary
        if primary is not None: raise primary
        return result

    def require_for_cluster(self, lease, deadline):
        self.inspect(lease, deadline)
        # No env/boolean override or claimed synthetic receipt can open this.
        raise RuntimePayloadRefused('NATIVE_RUNTIME_LOADING_NOT_ACCEPTED')


def static_report(data, runtime):
    """Identical bounded PE/BKI policy for held POSIX and Windows snapshots."""
    require(REQUIRED <= set(data), 'PG_BOOTSTRAP_PAYLOAD_MISSING')
    dynamic = set()
    for name, raw in data.items():
        tail = name[len(PG + 'share/'):] if name.startswith(PG + 'share/') else None
        if tail is not None and ('/' not in tail and tail.endswith(('.bki', '.sql')) or
                tail == 'extension/plpgsql.control' or tail.startswith('extension/plpgsql--') and tail.endswith('.sql')):
            dynamic.update(PG + 'lib/' + m.decode('ascii') + '.dll' for m in re.findall(rb'\$libdir/([a-zA-Z0-9_-]+)', raw))
    require(PG + 'lib/plpgsql.dll' in dynamic and dynamic <= set(data), 'PG_DYNAMIC_BOOTSTRAP_MISSING')
    closure = payload.dll_closure(data)
    require(closure['status'] == 'PRIVATE_IMPORTS_PRESENT_OS_LOADING_UNVERIFIED', 'PG_STATIC_IMPORT_UNRESOLVED')
    return dict(scope='LEASE_BOUND_PG_STATIC_SNAPSHOT', **runtime, runtime_files=len(data),
                runtime_bytes=sum(map(len,data.values())),bootstrap_modules=sorted(dynamic),
                static_loading=closure['status'],native_loading='NOT_ACCEPTED',activation_allowed=False)
