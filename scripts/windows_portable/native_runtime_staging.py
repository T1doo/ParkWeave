"""Held-handle immutable runtime installation; Windows acceptance remains closed.

Only an original fresh lease can create files. Reopen checks the complete
immutable tree without repair. No ACL setter, path-based copy or overwrite.
"""
import ctypes as C
from dataclasses import dataclass
from hashlib import sha256
import os
import re
import time
import weakref

from parkweave.windows_files import component, root_parts, private_acl, DIRECTORY, REPARSE, UNSAFE_ATTRIBUTES
from parkweave.windows_handles import (PTR, UnicodeString, ObjectAttributes, IOStatus,
    nt_status, completed_nt_handle, require_nt_create_ready, retain_pending_nt_create)
from . import payload
from .controller import CandidateRefused
from .endpoint_plan import _key_held
from .fixed_directories import FixedDirectoryLease, FIXED_JOURNAL
from .directories import JOURNAL
from .fixed_windows_journal import FixedWindowsFilesystem, NativeFixedLeaseAPI
from .native_secret_store_candidate import _NativeSecretFiles, private_file_descriptor
from .pgdata_candidate import directory_batch

DYNAMIC = frozenset(('data', 'secrets', 'files', 'logs', 'tmp'))
CONTROL = frozenset(('.parkweave-entry.lock', FIXED_JOURNAL))
TOP_DIRECTORIES = frozenset(('runtime', 'vendor', 'app', 'launcher'))
TOP_FILES = frozenset(('ParkWeave.cmd', 'runtime-assets.json', 'static-dll-audit.json', payload.MANIFEST))
CHUNK = 1024 * 1024
_issued = weakref.WeakKeyDictionary()


def need(ok):
    if not ok: raise CandidateRefused('NATIVE_RUNTIME_STAGING_REFUSED')


@dataclass(frozen=True)
class RuntimeSource:
    root: str
    manifest: bytes

    def plan(self, runtime):
        root_parts(self.root)  # Pure syntax check, no OS operation.
        need(sha256(self.manifest).hexdigest() == runtime['manifest_sha256'])
        parsed = payload.parse_manifest(self.manifest)
        need(parsed['source_commit'] == runtime['source_commit'])
        return installation_plan(self.manifest)


def installation_plan(raw):
    """Resolve all case/ancestor collisions before any destination creation."""
    rows = dict(payload.parse_manifest(raw)['files'])
    rows[payload.MANIFEST] = dict(bytes=len(raw), sha256=sha256(raw).hexdigest())
    nodes = {}
    for name in rows:
        parts = name.split('/')
        need(parts[0].casefold() not in DYNAMIC | CONTROL | {JOURNAL})
        need(parts[0] in (TOP_DIRECTORIES if len(parts)>1 else TOP_FILES))
        for i, part in enumerate(parts):
            component(part)
            path = '/'.join(parts[:i+1]); kind = i < len(parts)-1
            prior = nodes.setdefault(path.casefold(), (path, kind))
            need(prior == (path, kind))
    need(len(nodes) <= 2 * payload.MAX_FILES and sum(row['bytes'] for row in rows.values()) <= payload.MAX_BYTES)
    directories = tuple(sorted((p for p, d in nodes.values() if d), key=lambda p: (p.count('/'), p)))
    return directories, tuple((name, rows[name]['bytes'], rows[name]['sha256']) for name in sorted(rows))


class NativeRuntimeInstallation:
    native_acceptance = False

    def __init__(self, lease, source, runtime, *, create, deadline):
        self.handles = []; self.cleanup_errors = []; self.rows = {}; self.closed = False
        self.identities = set(); self.source_nodes = {}
        self.lease = lease; self.failed = False
        need(os.name == 'nt' and type(lease) is FixedDirectoryLease and
             type(lease.fs) is FixedWindowsFilesystem and type(lease.fs.api) is NativeFixedLeaseAPI
             and type(source) is RuntimeSource and type(create) is bool)
        self.api = lease.fs.api; self.deadline = deadline; self.key = _key_held(lease)
        self.root_sd = self.api.descriptor(lease.fs.root); self.root_path = self.api.final_path(lease.fs.root)
        self.directories, self.files = source.plan(runtime)
        self.probe = object.__new__(_NativeSecretFiles)
        _NativeSecretFiles.__init__(self.probe, lease, deadline)  # Token identity, no files.
        kernel = self.api.readonly.k
        self.query = kernel.GetFileInformationByHandleEx
        self.query.argtypes, self.query.restype = [PTR, C.c_int, PTR, C.c_uint32], C.c_int
        self.seek = kernel.SetFilePointerEx
        self.seek.argtypes, self.seek.restype = [PTR, C.c_int64, PTR, C.c_uint32], C.c_int
        need(lease.record['phase'] == ('NEW' if create else 'READY_STOPPED'))
        need(not create or self.key[-1] == 1 and lease.record['initialized'] is False)
        self.dest = {'': lease.fs.root}
        if create:
            # Source and all ancestors stay held until invocation cleanup.
            source_root = self._source(source.root)
            self._walk_source(source_root)
            manifest = self._open(source_root, payload.MANIFEST)
            need(self._read_all(manifest, len(source.manifest)) == source.manifest)
            need({name for name, _, _ in self._entries(lease.fs.root)} == CONTROL)
            for path in self.directories:
                parent, _, leaf = path.rpartition('/')
                self.dest[path] = self._create(self.dest[parent], leaf, True)
                self._record(path, self.dest[path], True)
            for path, size, digest in self.files:
                self._gate()
                parent, _, leaf = path.rpartition('/')
                original = self._source_file(source_root, path)
                before = self._inspect(original, False)
                need(before[0].size == size)
                target = self._create(self.dest[parent], leaf, False)
                expected = self._inspect(target, False)
                observed = sha256(); remaining = size
                while remaining:
                    self._gate()
                    raw = self.api.read(original, min(CHUNK, remaining))
                    need(0 < len(raw) <= remaining)
                    buf, written = C.create_string_buffer(raw), C.c_uint32()
                    self.api.need(self.api.writefile(target, buf, len(raw), C.byref(written), None))
                    need(written.value == len(raw))  # Uncertain/partial write is never retried.
                    observed.update(raw); remaining -= len(raw)
                need(self.api.read(original, 1) == b'' and observed.hexdigest() == digest)
                need(self._inspect(original, False) == before)
                self.api.flush(target)
                need(self._hash(target, size) == digest)
                after = self._inspect(target, False)
                need((after[0].volume, after[0].identity, after[1:]) ==
                     (expected[0].volume, expected[0].identity, expected[1:]))
                # Reopen read-only only after confirmed writer close. Keep original ID.
                self._close_handle(target)
                pin = self._open(self.dest[parent], leaf)
                need(self._inspect(pin, False) == after)
                self._record(path, pin, False)
        else:
            for path in self.directories:
                parent, _, leaf = path.rpartition('/')
                handle = self._open(self.dest[parent], leaf)
                self.dest[path] = handle; self._record(path, handle, True)
            for path, size, digest in self.files:
                parent, _, leaf = path.rpartition('/')
                handle = self._open(self.dest[parent], leaf)
                self._record(path, handle, False)
                need(self._hash(handle, size) == digest)
        self.verify()
        _issued[self] = (lease, self.api, self.probe, self.key, self.root_sd, self.root_path,
                        tuple(sorted(runtime.items())), self.files, self.directories,
                        tuple(sorted(self.rows.items())), tuple(sorted(self.dest.items())), tuple(self.handles))

    def _issued_binding(self, lease, runtime):
        # Exact constructor issuance, not a caller-supplied dictionary or clone.
        binding = _issued.get(self)
        need(binding is not None and type(self) is NativeRuntimeInstallation and lease is self.lease
             and not self.closed and not self.failed and not self.cleanup_errors and not self.probe.unknown
             and binding == (lease, self.api, self.probe, self.key, self.root_sd, self.root_path,
                 tuple(sorted(runtime.items())), self.files, self.directories,
                 tuple(sorted(self.rows.items())), tuple(sorted(self.dest.items())), tuple(self.handles)))

    def inspect_pg_static(self, lease, runtime, deadline):
        return self._inspect_pg_snapshot(lease,runtime,deadline)

    def system_crt_requirements(self,lease,runtime,deadline):
        return self._inspect_pg_snapshot(lease,runtime,deadline,requirements_only=True)

    def _inspect_pg_snapshot(self, lease, runtime, deadline, *, requirements_only=False):
        """Read the original installed pins, never reopen paths or mutable data."""
        from .fixed_secret_store import _under_lease
        from .runtime_payload import PG, REQUIRED, static_report
        import math
        self._issued_binding(lease, runtime)
        need(type(deadline) in (int,float) and math.isfinite(deadline)
             and 0 < deadline-time.monotonic() <= 30)
        def inspect():
            try:
                self._issued_binding(lease, runtime)
                phases=('NEW','READY_STOPPED','CLUSTER') if requirements_only else ('CLUSTER',)
                need(lease.record['phase'] in phases)
                self.deadline = deadline; self.probe.deadline = deadline
                self.verify()
                def read(path, size, digest):
                    handle, directory, original = self.rows[path]
                    need(not directory and self._inspect(handle, False) == original and original[0].size == size)
                    self.api.need(self.seek(handle, 0, None, 0))
                    chunks = []; remaining = size; observed = sha256()
                    while remaining:
                        self._gate(); raw = self.api.read(handle, min(CHUNK, remaining))
                        need(0 < len(raw) <= remaining)
                        chunks.append(raw); observed.update(raw); remaining -= len(raw)
                    need(self.api.read(handle, 1) == b'' and observed.hexdigest() == digest
                         and self._inspect(handle, False) == original)
                    return b''.join(chunks)
                manifest_row = next(row for row in self.files if row[0] == payload.MANIFEST)
                manifest = payload.parse_manifest(read(*manifest_row))
                need(manifest.get('source_commit') == runtime['source_commit']
                     and manifest_row[2] == runtime['manifest_sha256']
                     and manifest.get('usable_product') is False
                     and manifest.get('native_initialization') == 'OWNER_MUTATION_PAUSED')
                rows = tuple(row for row in self.files if row[0].startswith(PG))
                need(REQUIRED <= {row[0] for row in rows})
                data={name:read(name,size,digest) for name,size,digest in rows}
                if requirements_only:
                    from .crt_pe import requirements
                    report=requirements(data)
                else:report=static_report(data,runtime)
                # Keep all original pins held through PE and BKI parsing and a
                # second complete immutable namespace check. No native loading.
                self.verify(); self._issued_binding(lease,runtime)
                return report
            except BaseException:
                self.failed = True
                raise
        return _under_lease(lease, inspect)

    def __reduce__(self): raise TypeError('NATIVE_RUNTIME_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('NATIVE_RUNTIME_NOT_TRANSFERABLE')
    def __deepcopy__(self, memo): raise TypeError('NATIVE_RUNTIME_NOT_TRANSFERABLE')

    def _gate(self):
        need(not self.failed and not self.closed and time.monotonic() < self.deadline)
        self.lease._verify(); self.probe._gate()
        need(_key_held(self.lease) == self.key and self.api is self.lease.fs.api and
             self.api.descriptor(self.lease.fs.root) == self.root_sd and
             self.api.final_path(self.lease.fs.root) == self.root_path)

    def _hold(self, handle):
        self.handles.append(handle); return handle

    def _open(self, parent, name):
        self._gate()
        return self._hold(self.api.open_relative(parent, name, True))

    def _inspect(self, handle, directory, *, private=True, volume=None):
        info = self.api.info(handle)
        need(not info.attributes & (REPARSE | UNSAFE_ATTRIBUTES) and
             bool(info.attributes & DIRECTORY) == directory and info.identity > 0 and
             (volume is None or info.volume == volume) and
             (directory or info.links == 1 and 0 <= info.size <= 128*CHUNK))
        if private: private_acl(self.api.security(handle), self.probe.user)
        return info, self.api.descriptor(handle), self.api.final_path(handle)

    def _source(self, root):
        drive, parts = root_parts(root)
        handle = self._hold(self.api.open_drive(drive))
        guid = self.api.final_path(handle); volume = self.api.info(handle).volume
        need(re.fullmatch(r'\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\', guid) and
             self.api.filesystem(handle) == 'NTFS' and self.api.drive_type(guid) == 3)
        self._inspect(handle, True, private=False, volume=volume)
        for part in parts:
            handle = self._open(handle, part)
            self._inspect(handle, True, private=False, volume=volume)
        self._inspect(handle, True)
        need((volume, self.api.info(handle).identity) != tuple(self.lease.fs.root_id))
        self.source_volume = volume
        return handle

    def _source_file(self, root, path):
        handle = self.source_nodes[path]
        self._inspect(handle, False, volume=self.source_volume)
        self.api.need(self.seek(handle, 0, None, 0))
        return handle

    def _entries(self, handle):
        rows = []; seen = set()
        for index in range(4096):
            self._gate(); buf = C.create_string_buffer(65536)
            if not self.query(handle, 11 if index == 0 else 10, buf, len(buf)):
                need(C.get_last_error() == 18); return tuple(rows)
            for row in directory_batch(buf.raw):
                need(row[0].casefold() not in seen and len(rows) < 2 * payload.MAX_FILES)
                need(not row[1] & (REPARSE | UNSAFE_ATTRIBUTES))
                seen.add(row[0].casefold()); rows.append(row)
        need(False)

    def _walk_source(self, root):
        expected = set(self.directories) | {row[0] for row in self.files}
        seen = set()
        def visit(parent, prefix):
            for name, attrs, identity in self._entries(parent):
                path = prefix + name
                need(path in expected and path not in seen); seen.add(path)
                handle = self._open(parent, name)
                self.source_nodes[path] = handle
                info = self._inspect(handle, bool(attrs & DIRECTORY), volume=self.source_volume)[0]
                need(info.identity == identity and info.attributes == attrs)
                if attrs & DIRECTORY: visit(handle, path + '/')
        visit(root, '')
        need(seen == expected)

    def _create(self, parent, leaf, directory):
        self._gate(); component(leaf); require_nt_create_ready(self.api.readonly)
        raw = leaf.encode('utf-16-le'); buf = C.create_string_buffer(raw + b'\0\0')
        name = UnicodeString(len(raw), len(raw)+2, C.cast(buf, PTR))
        sd = C.create_string_buffer(private_file_descriptor(self.probe.sid_bytes))
        attrs = ObjectAttributes(C.sizeof(ObjectAttributes), parent, C.pointer(name), 0x40, C.cast(sd, PTR), None)
        handle, io = PTR(), IOStatus()
        status = nt_status(self.api.ntcreate(C.byref(handle), 0x120081 | (0 if directory else 0x40000000),
            C.byref(attrs), C.byref(io), None, 0x10 if directory else 0x80, 1, 2,
            0x20 | 0x200000 | (1 if directory else 0x40), None, 0))
        if status == 0x103:
            retain_pending_nt_create(self.api.readonly, handle, io, attrs, name, buf, sd); need(False)
        need(completed_nt_handle(status, handle.value))
        owned = self._hold(handle.value)  # Retain before any subsequent assertion.
        need(status == 0 and io.Information == 2)
        info, descriptor, path = self._inspect(owned, directory, volume=self.key[1][0])
        need(path == self.api.final_path(parent).rstrip('\\') + '\\' + leaf)
        need(descriptor[0] == self.probe.user and descriptor[1] & ~1 in (0x1004, 0x9004) and
             descriptor[2] == private_file_descriptor(self.probe.sid_bytes)[20+len(self.probe.sid_bytes):])
        return owned

    def _read_all(self, handle, size):
        need(size <= 4*CHUNK and self.api.info(handle).size == size)
        self.api.need(self.seek(handle, 0, None, 0))
        raw = self.api.read(handle, size+1); need(len(raw) == size); return raw

    def _hash(self, handle, size):
        before = self._inspect(handle, False); need(before[0].size == size)
        self.api.need(self.seek(handle, 0, None, 0)); digest = sha256(); remaining = size
        while remaining:
            self._gate(); raw = self.api.read(handle, min(CHUNK, remaining))
            need(0 < len(raw) <= remaining); digest.update(raw); remaining -= len(raw)
        need(self.api.read(handle, 1) == b'' and self._inspect(handle, False) == before)
        return digest.hexdigest()

    def _record(self, path, handle, directory):
        observed = self._inspect(handle, directory, volume=self.key[1][0])
        need(observed[2] == self.root_path.rstrip('\\') + '\\' + path.replace('/', '\\'))
        identity = (observed[0].volume, observed[0].identity)
        need(identity not in self.identities); self.identities.add(identity)
        self.rows[path] = (handle, directory, observed)

    def verify(self):
        self._gate()
        for path, (handle, directory, observed) in self.rows.items():
            need(self._inspect(handle, directory, volume=self.key[1][0]) == observed)
        # Exact immutable namespace; dynamic business directories are not walked.
        for path, handle in self.dest.items():
            prefix = path + '/' if path else ''
            expected = {p[len(prefix):].split('/')[0] for p in self.rows if p.startswith(prefix)}
            actual = {name for name, _, _ in self._entries(handle)}
            if not path:
                need(CONTROL <= actual and actual - DYNAMIC - CONTROL == expected)
            else: need(actual == expected)
        return self

    def _close_handle(self, handle):
        self.handles.remove(handle)  # Never retry uncertain CloseHandle.
        try: self.api.close(handle)
        except BaseException:
            self.cleanup_errors.append(('RUNTIME_CLOSE_UNKNOWN', handle)); raise

    def close(self):
        errors = []
        for handle in reversed(tuple(self.handles)):
            try: self._close_handle(handle)
            except BaseException as error: errors.append(error)
        self.closed = True
        if getattr(getattr(self, 'probe', None), 'unknown', None):
            self.cleanup_errors.append(('RUNTIME_IDENTITY_CLOSE_UNKNOWN', None))
            errors.append(CandidateRefused('RUNTIME_IDENTITY_CLOSE_UNKNOWN'))
        if errors:
            self.failed = True; self.lease.poisoned = True
            raise BaseExceptionGroup('NATIVE_RUNTIME_CLOSE_UNKNOWN', errors)
