"""Fixed two-slot storage connected to original lease transitions, opt-in only.

No automatic v1 conversion and no Windows durability/OWNER gate relaxation.
"""
import os
import stat
import threading
from functools import wraps
from pathlib import Path

from . import fixed_journal as journal
from .directories import DirectoryLease, LeaseRefused, PosixFilesystem, PrivateDirectories

FIXED_JOURNAL = '.parkweave-lease.slots'


def _random_bytes():
    from secrets import token_bytes
    return token_bytes(16)


def _new_instance_id(fs):
    from uuid import UUID
    fs.verify()
    pinned = (tuple(fs.root_id), tuple(fs.lock_id), tuple(fs.identity()))
    if (fs.journal_format is not journal.FixedFormat.INSTANCE_V2 or fs.length() != 0
            or any(len(x) != 2 or any(type(n) is not int or not 0 <= n < 2**64 for n in x) for x in pinned)
            or len(set(pinned)) != 3 or len({x[0] for x in pinned}) != 1):
        raise LeaseRefused('FIXED_INSTANCE_ACQUISITION_REFUSED')
    # Called once only after exclusive acquisition. Failure is not retried;
    # the existing root/lock/journal must remain, not be claimed afresh.
    raw = _random_bytes()
    if type(raw) is not bytes or len(raw) != 16: raise LeaseRefused('FIXED_RANDOM_SOURCE_REFUSED')
    fs.verify()
    if (fs.journal_format is not journal.FixedFormat.INSTANCE_V2 or fs.length() != 0
            or pinned != (tuple(fs.root_id), tuple(fs.lock_id), tuple(fs.identity()))):
        raise LeaseRefused('FIXED_INSTANCE_ACQUISITION_CHANGED')
    return str(UUID(bytes=raw, version=4))


class FixedPosixFilesystem(PosixFilesystem):
    def __init__(self, base, *, format=journal.FixedFormat.V1):
        self._journal_format = journal.require_format(format)
        super().__init__(base); self.journal = None

    @property
    def journal_format(self): return self._journal_format

    def acquire(self, name, *, fresh):
        super().acquire(name, fresh=fresh)
        flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if fresh else 0)
        self.journal = self.hold(os.open(FIXED_JOURNAL, flags, 0o600, dir_fd=self.root))
        self.journal_id = self.identity(self.journal)
        self.verify(); self.storage = journal.FixedJournal(self, format=self.journal_format)
        if fresh: os.fsync(self.root)  # Linux only; never called a Windows barrier.

    def verify(self):
        super().verify()
        if self.journal is None: return
        info = os.fstat(self.journal)
        current = os.stat(FIXED_JOURNAL, dir_fd=self.root, follow_symlinks=False)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or not 0 <= info.st_size <= journal.SIZE
                or not stat.S_ISREG(current.st_mode) or self.identity(self.journal) != self.journal_id
                or [current.st_dev, current.st_ino] != self.journal_id):
            raise LeaseRefused('FIXED_INODE_CHANGED')

    def identity(self, handle=None):
        return super().identity(self.journal if handle is None else handle)

    def signature(self):
        info = os.fstat(self.journal)
        return tuple(getattr(info, key) for key in ('st_dev', 'st_ino', 'st_uid', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))

    def length(self): return os.fstat(self.journal).st_size
    def read_at(self, offset, count): return os.pread(self.journal, count, offset)
    def write_at(self, offset, raw): return os.pwrite(self.journal, raw, offset)
    def flush_file(self): os.fsync(self.journal)
    def read(self): return self.storage.read()
    def replace(self, raw, expected): return self.storage.write(raw, expected)


def _guard_operation(*, public):
    def decorate(method):
        @wraps(method)
        def guarded(self, *args, **kwargs):
            nested = self._operation_owner == threading.get_ident() and self._operation_depth > 0
            if nested and public:
                raise LeaseRefused('FIXED_LEASE_OPERATION_BUSY')
            if not nested:
                if not self._entry_lock.acquire(blocking=False):
                    raise LeaseRefused('FIXED_LEASE_OPERATION_BUSY')  # No IO performed.
                self._operation_owner = threading.get_ident()
            self._operation_depth += 1
            try: return method(self, *args, **kwargs)
            finally:
                self._operation_depth -= 1
                if not nested:
                    self._operation_owner = None
                    self._entry_lock.release()
        return guarded
    return decorate


_exclusive_operation = _guard_operation(public=False)
_exclusive_entry = _guard_operation(public=True)


class FixedDirectoryLease(DirectoryLease):
    def __init__(self, *args):
        super().__init__(*args)
        self._journal_format = journal.require_format(getattr(self.fs, 'journal_format', journal.FixedFormat.V1))
        self._operation_owner, self._operation_depth = None, 0
        self._entry_lock = threading.Lock()

    # Hold one per-lease operation across read/compare/write/ack and close.
    # Public callbacks cannot reenter. First private validation takes the same
    # entry gate; only explicit same-thread private nesting reuses ownership.
    @_exclusive_entry
    def checkpoint(self, *args): return super().checkpoint(*args)

    @_exclusive_entry
    def status(self): return super().status()

    @_exclusive_entry
    def mark_unknown(self, *args): return super().mark_unknown(*args)

    @_exclusive_entry
    def release(self): return super().release()

    @_exclusive_entry
    def instance_uuid(self):
        return self._verified_instance_uuid()

    @_exclusive_operation
    def _verified_instance_uuid(self):
        self._verify()
        if self._journal_format is not journal.FixedFormat.INSTANCE_V2:
            raise LeaseRefused('FIXED_INSTANCE_V2_REQUIRED')
        record = journal.decode(self.snapshot[0], format=self._journal_format)
        if record['phase'] == 'UNKNOWN': raise LeaseRefused('FIXED_INSTANCE_UNKNOWN')
        return record['instance_id']  # No generation, caller UUID or plaintext secret lookup.

    @_exclusive_operation
    def _verify(self):
        if not self.active or self.poisoned: raise LeaseRefused('LEASE_NOT_WRITABLE')
        try:
            if journal.require_format(getattr(self.fs, 'journal_format', journal.FixedFormat.V1)) is not self._journal_format:
                raise LeaseRefused('FIXED_LEASE_FORMAT_CHANGED')
            self.fs.verify()
            if self.fs.read() != self.snapshot: raise LeaseRefused('FIXED_SNAPSHOT_CHANGED')
        except BaseException:
            self.poisoned = True
            raise

    @_exclusive_operation
    def _publish(self, update):
        # Read/identity failures poison as well as writes. Restoring old bytes
        # cannot silently re-enable this already uncertain invocation.
        try:
            self._verify()
            value = {**self.record, **update, 'sequence': self.record['sequence'] + 1}
            raw = journal.encode(value); journal.decode(raw, format=self._journal_format)
            snapshot = self.fs.replace(raw, self.snapshot)
        except BaseException:
            self.poisoned = True
            raise
        self.record, self.snapshot = value, snapshot


class FixedPrivateDirectories(PrivateDirectories):
    def __init__(self, base, *, format=journal.FixedFormat.V1):
        self._journal_format = journal.require_format(format)
        super().__init__(base)

    @property
    def journal_format(self): return self._journal_format

    def _filesystem(self):
        if os.name == 'posix': return FixedPosixFilesystem(self.base, format=self.journal_format)
        if os.name == 'nt':
            from .fixed_windows_journal import FixedWindowsFilesystem
            return FixedWindowsFilesystem(self.base, format=self.journal_format)
        raise LeaseRefused('UNSUPPORTED_DIRECTORY_BACKEND')

    def _acquire(self, root, *, fresh):
        if fresh and os.name == 'nt':
            from scripts.windows.lifecycle import require_setup_readiness
            require_setup_readiness()
        # Reuse the original exact path/device validation before any filesystem
        # acquisition without changing the old v1 format or its default route.
        root = os.fspath(root); path, base = Path(root), Path(self.base)
        import re
        from .payload import safe_name, PayloadRefused
        if (not path.is_absolute() or path.parent != base or str(path) != root
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}', path.name)):
            raise LeaseRefused('EXACT_PRIVATE_CHILD_REQUIRED')
        try: safe_name(path.name)
        except PayloadRefused: raise LeaseRefused('EXACT_PRIVATE_CHILD_REQUIRED') from None
        fs = self._filesystem()
        try:
            selected = journal.require_format(self.journal_format)
            if journal.require_format(fs.journal_format) is not selected:
                raise LeaseRefused('FIXED_ACQUISITION_FORMAT_MISMATCH')
            fs.acquire(path.name, fresh=fresh)
            if fresh:
                record = dict(schema=journal.schema(selected), root=fs.root_id, lock=fs.lock_id, journal=fs.identity(),
                              generation=1, sequence=2, phase='NEW', initialized=False, runtime='STOPPED', handoff='OWNED')
                if selected is journal.FixedFormat.INSTANCE_V2: record['instance_id'] = _new_instance_id(fs)
                fs.verify()
                snapshot = fs.replace(journal.encode(record), None)
            else:
                snapshot = fs.read(); record = journal.decode(snapshot[0], format=selected)
                if record['phase'] != 'READY_STOPPED' or record['handoff'] != 'RELEASE_PENDING':
                    raise LeaseRefused('CONFIRMED_HANDOFF_REQUIRED')
                record = {**record, 'generation': record['generation'] + 1, 'sequence': record['sequence'] + 1, 'handoff': 'OWNED'}
                fs.verify()
                snapshot = fs.replace(journal.encode(record), snapshot)
            if fs.journal_format is not selected or self.journal_format is not selected:
                raise LeaseRefused('FIXED_ACQUISITION_FORMAT_CHANGED')
            return FixedDirectoryLease(fs, record, snapshot)
        except BaseException as primary:
            try: fs.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup('FIXED_LEASE_ACQUIRE_FAILED', [primary, cleanup]) from primary
            raise
