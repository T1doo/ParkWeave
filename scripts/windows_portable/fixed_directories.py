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


class FixedPosixFilesystem(PosixFilesystem):
    def __init__(self, base):
        super().__init__(base); self.journal = None

    def acquire(self, name, *, fresh):
        super().acquire(name, fresh=fresh)
        flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if fresh else 0)
        self.journal = self.hold(os.open(FIXED_JOURNAL, flags, 0o600, dir_fd=self.root))
        self.journal_id = self.identity(self.journal)
        self.verify(); self.storage = journal.FixedJournal(self)
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

    @_exclusive_operation
    def _verify(self):
        if not self.active or self.poisoned: raise LeaseRefused('LEASE_NOT_WRITABLE')
        try:
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
            raw = journal.encode(value); journal.decode(raw)
            snapshot = self.fs.replace(raw, self.snapshot)
        except BaseException:
            self.poisoned = True
            raise
        self.record, self.snapshot = value, snapshot


class FixedPrivateDirectories(PrivateDirectories):
    def _filesystem(self):
        if os.name == 'posix': return FixedPosixFilesystem(self.base)
        if os.name == 'nt':
            from .fixed_windows_journal import FixedWindowsFilesystem
            return FixedWindowsFilesystem(self.base)
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
            fs.acquire(path.name, fresh=fresh)
            if fresh:
                record = dict(schema=journal.SCHEMA, root=fs.root_id, lock=fs.lock_id, journal=fs.identity(),
                              generation=1, sequence=2, phase='NEW', initialized=False, runtime='STOPPED', handoff='OWNED')
                snapshot = fs.replace(journal.encode(record), None)
            else:
                snapshot = fs.read(); record = journal.decode(snapshot[0])
                if record['phase'] != 'READY_STOPPED' or record['handoff'] != 'RELEASE_PENDING':
                    raise LeaseRefused('CONFIRMED_HANDOFF_REQUIRED')
                record = {**record, 'generation': record['generation'] + 1, 'sequence': record['sequence'] + 1, 'handoff': 'OWNED'}
                snapshot = fs.replace(journal.encode(record), snapshot)
            return FixedDirectoryLease(fs, record, snapshot)
        except BaseException as primary:
            try: fs.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup('FIXED_LEASE_ACQUIRE_FAILED', [primary, cleanup]) from primary
            raise
