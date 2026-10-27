"""Handle-bound private directory leases; journal is never DDL authority.

Linux uses real openat/flock/fsync. Windows has a separate native handle
backend; unsupported native prerequisites refuse, never fall back to POSIX or
pathname locking. No ACL mutation, stale-lock deletion, PID signalling or retry.
"""
import json
import os
from pathlib import Path
import re
import stat
from uuid import uuid4


LOCK = '.parkweave-entry.lock'
JOURNAL = '.parkweave-lease.json'
LIMIT = 4096
PHASES = frozenset(('NEW', 'CREDENTIALS', 'CLUSTER', 'CREATE_SCHEMA', 'ROLES', 'SESSIONS',
                    'SEED', 'CONFIG', 'VERIFY_FILES', 'VERIFY_DATABASE', 'READY', 'APPLICATION',
                    'RUNNING', 'READY_STOPPED', 'UNKNOWN'))
NEXT = dict(NEW='CREDENTIALS', CREDENTIALS='CLUSTER', CREATE_SCHEMA='ROLES', ROLES='SESSIONS',
            SESSIONS='SEED', SEED='CONFIG', CONFIG='VERIFY_FILES', VERIFY_FILES='VERIFY_DATABASE',
            VERIFY_DATABASE='READY', READY='APPLICATION', APPLICATION='RUNNING', RUNNING='READY_STOPPED',
            READY_STOPPED='CLUSTER')


class LeaseRefused(RuntimeError):
    """Fixed public codes only; underlying OS exceptions remain private causes."""


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result: raise LeaseRefused('JOURNAL_DUPLICATE_KEY')
        result[key] = value
    return result


def _encode(record):
    raw = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    if len(raw) > LIMIT: raise LeaseRefused('JOURNAL_LIMIT')
    return raw


def _decode(raw):
    if not 0 < len(raw) <= LIMIT: raise LeaseRefused('JOURNAL_LIMIT')
    try: value = json.loads(raw, object_pairs_hook=_pairs)
    except (ValueError, UnicodeError): raise LeaseRefused('JOURNAL_INVALID') from None
    fields = {'schema', 'root', 'lock', 'generation', 'sequence', 'phase', 'initialized', 'runtime', 'handoff'}
    if (type(value) is not dict or set(value) != fields or value['schema'] != 'parkweave-directory-lease/1'
            or type(value['generation']) is not int or not 1 <= value['generation'] < 2**31
            or type(value['sequence']) is not int or not 1 <= value['sequence'] < 2**31
            or type(value['initialized']) is not bool or type(value['phase']) is not str or value['phase'] not in PHASES
            or value['runtime'] not in ('STARTING', 'RUNNING', 'STOPPED', 'UNKNOWN')
            or value['handoff'] not in ('OWNED', 'RELEASE_PENDING')
            or any(type(value[k]) is not list or len(value[k]) != 2 or
                   any(type(v) is not int or v < 0 for v in value[k]) for k in ('root', 'lock'))
            or value['phase'] == 'READY_STOPPED' and (not value['initialized'] or value['runtime'] != 'STOPPED')):
        raise LeaseRefused('JOURNAL_INVALID')
    return value


class PosixFilesystem:
    def __init__(self, base):
        if os.name != 'posix' or not hasattr(os, 'O_NOFOLLOW'):
            raise LeaseRefused('POSIX_HANDLE_BACKEND_REQUIRED')
        raw = os.fspath(base)
        if not isinstance(raw, str) or not raw.startswith('/') or '\x00' in raw or raw == '/':
            raise LeaseRefused('EXPLICIT_PRIVATE_BASE_REQUIRED')
        self.base = Path(raw)
        if str(self.base) != raw or any(p in ('.', '..', '') for p in raw.split('/')[1:]):
            raise LeaseRefused('CANONICAL_PRIVATE_BASE_REQUIRED')
        self.handles, self.chain = [], []

    def hold(self, fd):
        self.handles.append(fd); return fd

    @staticmethod
    def identity(fd):
        info = os.fstat(fd)
        return [info.st_dev, info.st_ino]

    def _directory(self, fd, *, private=False):
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode): raise LeaseRefused('DIRECTORY_REQUIRED')
        if private and (info.st_uid != os.geteuid() or info.st_mode & 0o077):
            raise LeaseRefused('PRIVATE_DIRECTORY_REQUIRED')
        if not private and info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX:
            raise LeaseRefused('UNSAFE_ANCESTOR')
        return self.identity(fd)

    def _file(self, fd):
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.geteuid()
                or info.st_mode & 0o077 or not 0 <= info.st_size <= LIMIT):
            raise LeaseRefused('PRIVATE_REGULAR_FILE_REQUIRED')
        return self.identity(fd)

    def acquire(self, name, *, fresh):
        fd = self.hold(os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC))
        self._directory(fd)
        for part in self.base.parts[1:]:
            child = self.hold(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd))
            self.chain.append((fd, part, child)); self._directory(child)
            fd = child
        self._directory(fd, private=True)
        self.anchor = fd
        if fresh:
            os.mkdir(name, 0o700, dir_fd=fd)  # Exclusive; never chmod an existing root.
            os.fsync(fd)
        root = self.hold(os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd))
        self.chain.append((fd, name, root)); self._directory(root, private=True)
        self.root = root
        flags = os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | (os.O_CREAT | os.O_EXCL if fresh else 0)
        lock = self.hold(os.open(LOCK, flags, 0o600, dir_fd=root))
        self._file(lock)
        import fcntl
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # This inode is never replaced or unlinked, including during cleanup.
        self.lock = lock
        self.root_id, self.lock_id = self.identity(root), self.identity(lock)
        if fresh: os.fsync(root)
        self.verify()

    def verify(self):
        for parent, name, child in self.chain:
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or [current.st_dev, current.st_ino] != self.identity(child):
                raise LeaseRefused('ANCESTOR_IDENTITY_CHANGED')
            self._directory(child, private=child in (self.root, self.anchor))
        if self._directory(self.root, private=True) != self.root_id or self._file(self.lock) != self.lock_id:
            raise LeaseRefused('LEASE_IDENTITY_CHANGED')
        current = os.stat(LOCK, dir_fd=self.root, follow_symlinks=False)
        if not stat.S_ISREG(current.st_mode) or [current.st_dev, current.st_ino] != self.lock_id:
            raise LeaseRefused('LOCK_PATH_IDENTITY_CHANGED')

    def read(self):
        fd = os.open(JOURNAL, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.root)
        try:
            identity = self._file(fd); before = os.fstat(fd)
            raw = os.read(fd, LIMIT + 1)
            after = os.fstat(fd)
            # Reading can legitimately update atime; compare mutation/identity
            # fields, never mistake our own read for a foreign journal write.
            fields = ('st_dev', 'st_ino', 'st_uid', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
            if any(getattr(after, k) != getattr(before, k) for k in fields):
                raise LeaseRefused('JOURNAL_CHANGED_DURING_READ')
            return raw, identity
        finally: os.close(fd)

    def replace(self, raw, expected):
        self.verify()
        if expected is None:
            try: os.stat(JOURNAL, dir_fd=self.root, follow_symlinks=False)
            except FileNotFoundError: pass
            else: raise LeaseRefused('JOURNAL_ALREADY_EXISTS')
        elif self.read() != expected:
            raise LeaseRefused('JOURNAL_IDENTITY_CHANGED')
        name = '.parkweave-journal-' + uuid4().hex + '.tmp'
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.root)
        try:
            self._file(fd)
            view = memoryview(raw)
            while view:
                count = os.write(fd, view)
                if count <= 0: raise LeaseRefused('JOURNAL_SHORT_WRITE')
                view = view[count:]
            os.fsync(fd)
            self.verify()
            if expected is not None and self.read() != expected: raise LeaseRefused('JOURNAL_IDENTITY_CHANGED')
            if expected is None:
                # Atomic exclusive initial publication; cannot clobber a file
                # appearing after the initial absence check.
                os.link(name, JOURNAL, src_dir_fd=self.root, dst_dir_fd=self.root, follow_symlinks=False)
                own = os.stat(name, dir_fd=self.root, follow_symlinks=False)
                if [own.st_dev, own.st_ino] != self.identity(fd): raise LeaseRefused('TEMP_IDENTITY_CHANGED')
                os.unlink(name, dir_fd=self.root)  # Only this newly created, held inode.
            else:
                os.replace(name, JOURNAL, src_dir_fd=self.root, dst_dir_fd=self.root)
            os.fsync(self.root)
        finally:
            # Keep failed temporary artifacts. Never unlink an unknown object.
            os.close(fd)
        result = self.read()
        if result[0] != raw: raise LeaseRefused('JOURNAL_PUBLICATION_UNKNOWN')
        self.verify()  # Recheck path/held inode binding after final read+sync.
        return result

    def close(self):
        errors = []
        # Release the persistent kernel lock last. Never explicitly unlock and
        # then touch files; pop before close so an ambiguous fd is never retried.
        lock = getattr(self, 'lock', None)
        order = [fd for fd in reversed(self.handles) if fd != lock] + ([lock] if lock in self.handles else [])
        self.handles.clear()
        for fd in order:
            try: os.close(fd)
            except BaseException as error: errors.append(error)
        if errors: raise BaseExceptionGroup('LEASE_CLOSE_UNKNOWN', errors)


class DirectoryLease:
    def __init__(self, filesystem, record, snapshot):
        self.fs, self.record, self.snapshot = filesystem, record, snapshot
        self.active, self.poisoned = True, False

    def _verify(self):
        if not self.active or self.poisoned: raise LeaseRefused('LEASE_NOT_WRITABLE')
        self.fs.verify()
        if self.fs.read() != self.snapshot: raise LeaseRefused('JOURNAL_IDENTITY_CHANGED')

    def status(self):
        self._verify(); return self.record['phase']

    def _publish(self, update):
        self._verify()
        value = {**self.record, **update, 'sequence': self.record['sequence'] + 1}
        raw = _encode(_decode(_encode(value)))
        try: snapshot = self.fs.replace(raw, self.snapshot)
        except BaseException:
            self.poisoned = True
            raise
        self.record, self.snapshot = value, snapshot

    def checkpoint(self, phase, initialized, runtime):
        previous = self.record['phase']
        expected = ('VERIFY_DATABASE' if self.record['initialized'] else 'CREATE_SCHEMA') if previous == 'CLUSTER' else NEXT.get(previous)
        if (type(phase) is not str or phase not in PHASES or phase in ('NEW', 'UNKNOWN')
                or type(initialized) is not bool or runtime not in ('STARTING', 'RUNNING', 'STOPPED')
                or self.record['phase'] == 'UNKNOWN'
                or phase != expected or self.record['initialized'] and not initialized
                or initialized != self.record['initialized'] and phase != 'READY'
                or phase in ('READY', 'RUNNING', 'READY_STOPPED') and not initialized
                or runtime != ('RUNNING' if phase == 'RUNNING' else 'STOPPED' if phase in ('READY', 'READY_STOPPED') else 'STARTING')
                or phase == 'READY_STOPPED' and runtime != 'STOPPED'):
            raise LeaseRefused('CHECKPOINT_REFUSED')
        self._publish(dict(phase=phase, initialized=initialized, runtime=runtime, handoff='OWNED'))

    def mark_unknown(self, phase):
        if type(phase) is not str or phase not in PHASES | {'PREPARE', 'ACQUIRE'}:
            raise LeaseRefused('UNKNOWN_PHASE_REFUSED')
        self._publish(dict(phase='UNKNOWN', runtime='UNKNOWN', handoff='OWNED'))

    def release(self):
        if not self.active: raise LeaseRefused('LEASE_ALREADY_RELEASED')
        errors = []
        try:
            if not self.poisoned:
                # Freeze a durable intent while ownership is still held. Only a
                # later real kernel-exclusive acquisition may complete handoff.
                self._publish(dict(handoff='RELEASE_PENDING'))
        except BaseException as error: errors.append(error)
        finally:
            self.active = False  # One-way freeze BEFORE any close can release ownership.
            try: self.fs.close()
            except BaseException as error: errors.append(error)
        if errors: raise BaseExceptionGroup('LEASE_RELEASE_UNKNOWN', errors)


class PrivateDirectories:
    def __init__(self, base):
        self.base = os.fspath(base)

    def _filesystem(self):
        if os.name == 'posix': return PosixFilesystem(self.base)
        if os.name == 'nt':
            from .windows_directory_handles import WindowsFilesystem
            return WindowsFilesystem(self.base)
        raise LeaseRefused('UNSUPPORTED_DIRECTORY_BACKEND')

    def _acquire(self, root, *, fresh):
        if fresh and os.name == 'nt':
            from scripts.windows.lifecycle import require_setup_readiness
            require_setup_readiness()  # Original native pause, no override.
        root = os.fspath(root)
        path, base = Path(root), Path(self.base)
        if (not path.is_absolute() or path.parent != base or str(path) != root
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_-]{0,79}', path.name)):
            raise LeaseRefused('EXACT_PRIVATE_CHILD_REQUIRED')
        from .payload import safe_name, PayloadRefused
        try: safe_name(path.name)  # Reject Windows device names on Linux builds too.
        except PayloadRefused: raise LeaseRefused('EXACT_PRIVATE_CHILD_REQUIRED') from None
        fs = self._filesystem()
        try:
            fs.acquire(path.name, fresh=fresh)
            if fresh:
                record = dict(schema='parkweave-directory-lease/1', root=fs.root_id, lock=fs.lock_id,
                              generation=1, sequence=1, phase='NEW', initialized=False,
                              runtime='STOPPED', handoff='OWNED')
                snapshot = fs.replace(_encode(record), None)
            else:
                snapshot = fs.read(); record = _decode(snapshot[0])
                if (record['root'] != fs.root_id or record['lock'] != fs.lock_id
                        or record['phase'] != 'READY_STOPPED' or record['handoff'] != 'RELEASE_PENDING'):
                    raise LeaseRefused('CONFIRMED_HANDOFF_REQUIRED')
                # Retire the old intent before returning ANY new-generation
                # lease. A crash here leaves OWNED, which cannot be re-admitted.
                record = {**record, 'generation': record['generation'] + 1,
                          'sequence': record['sequence'] + 1, 'handoff': 'OWNED'}
                snapshot = fs.replace(_encode(_decode(_encode(record))), snapshot)
            return DirectoryLease(fs, record, snapshot)
        except BaseException as primary:
            try: fs.close()
            except BaseException as cleanup:
                raise BaseExceptionGroup('LEASE_ACQUIRE_FAILED', [primary, cleanup]) from primary
            raise

    def claim_fresh(self, root): return self._acquire(root, fresh=True)
    def open_existing(self, root): return self._acquire(root, fresh=False)
