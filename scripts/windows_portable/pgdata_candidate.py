"""Unwired NEW-only PGDATA capability, native execution NOT_ACCEPTED.

Dedicated policy, not windows_files.private_acl relaxation: a protected root
with one concrete current-user OI/CI ACE; descendants inherit that exact ACE.
No generic rights/CREATOR_OWNER/extra principals, conversion or ACL repair.
Checks are cooperative observations, not an atomic snapshot or protection
against malicious same-user/admin mutation. No resume, password or PG calls.
Reopen remains refused: authenticated persistent profile publication is not
implemented by this invocation-local capability. No directory durability claim.
"""
import ctypes as C
from dataclasses import dataclass
import hashlib
import math
import os
import re
import struct
import time
import weakref

from parkweave.windows_files import (Ace, Security, DIRECTORY, REPARSE,
    UNSAFE_ATTRIBUTES, PROTECTED, DACL_PRESENT, component, private_acl)
from parkweave.windows_handles import UnicodeString, ObjectAttributes, IOStatus, PTR
from .default_dacl_candidate import _sid_buffer
from .endpoint_plan import _key_held
from .fixed_directories import FixedDirectoryLease, _exclusive_entry, _exclusive_operation
from .fixed_windows_journal import FixedWindowsFilesystem, NativeFixedLeaseAPI

PROFILE = 'parkweave-pgdata-current-user-inheritance/1'
FILE_ALL = 0x1f01ff


class DataRefused(RuntimeError):
    pass


def _need(ok):
    if not ok: raise DataRefused('PRIVATE_PGDATA_REFUSED')


def _sid_text(raw):
    _sid_buffer(raw)
    return 'S-1-' + str(int.from_bytes(raw[2:8], 'big')) + ''.join(
        '-'+str(x[0]) for x in struct.iter_unpack('<I', raw[8:]))


def root_descriptor(sid):
    """Self-relative descriptor bytes only; not a current-user credential."""
    _sid_buffer(sid)
    ace = struct.pack('<BBHI', 0, 3, 8+len(sid), FILE_ALL) + sid
    acl = struct.pack('<BBHHH', 2, 0, 8+len(ace), 1, 0) + ace
    return struct.pack('<BBHIIII', 1, 0, 0x9004, 20, 0, 0, 20+len(sid)) + sid + acl


def check_descriptor(value, sid, *, root, directory):
    _need(type(value) is tuple and len(value) == 3)
    owner, control, raw = value
    flags = 3 if root else (0x13 if directory else 0x10)
    ace = struct.pack('<BBHI', 0, flags, 8+len(sid), FILE_ALL) + sid
    expected = struct.pack('<BBHHH', 2, 0, 8+len(ace), 1, 0) + ace
    check_security(Security(owner, control, (Ace(0, flags, FILE_ALL, _sid_text(sid)),)),
                   _sid_text(sid), root=root, directory=directory)
    _need(type(raw) is bytes and raw == expected)  # No ignored payload/free ACE area.


def pg_command_path(value):
    """A conservative DOS argv representation, never filesystem authority."""
    _need(type(value) is str and re.match(r'^\\\\\?\\[A-Za-z]:\\', value) is not None)
    path = value[4:]
    _need(len(path.encode('utf-16-le', errors='strict'))//2 <= 240)
    parts = path[3:].split('\\')
    _need(parts and len(parts) <= 64)
    for part in parts: component(part)
    return path.replace('\\', '/'), path[:3], tuple(parts)


def descriptor_digest(value):
    from .credential_envelope import canonical
    owner, control, raw = value
    return hashlib.sha256(canonical([owner, control, raw.hex()])).hexdigest()


def check_security(value, user, *, root, directory):
    _need(type(value) is Security and type(user) is str and
          re.fullmatch(r'S-1-[0-9]+(?:-[0-9]+){1,15}', user) is not None)
    # Concrete FILE_ALL and concrete user SID have no generic mapping or
    # effective/inherit-only splitting. Reject all broader ACL shapes.
    flags = 3 if root else (0x13 if directory else 0x10)
    _need(value.owner == user and type(value.control) is int and
          value.control & DACL_PRESENT and
          bool(value.control & PROTECTED) == root and
          value.control & ~(0x8000|0x1000|0x400|0x4) == 0 and
          type(value.aces) is tuple and value.aces == (Ace(0, flags, FILE_ALL, user),))


def _metadata(info, volume, *, directory):
    _need(type(info.volume) is int and info.volume == volume and
          type(info.identity) is int and 0 < info.identity < 2**64 and
          type(info.attributes) is int and not info.attributes & (REPARSE|UNSAFE_ATTRIBUTES) and
          bool(info.attributes & DIRECTORY) == directory and
          (directory or info.links == 1))
    return (info.volume, info.identity)


def directory_batch(raw):
    """Bounded FILE_ID_BOTH_DIR_INFO parsing, Windows WCHAR always 16 bits."""
    _need(type(raw) is bytes and 104 <= len(raw) <= 65536)
    result, offset, seen = [], 0, set()
    while True:
        _need(offset+104 <= len(raw))
        advance = struct.unpack_from('<I', raw, offset)[0]
        attrs, length = struct.unpack_from('<II', raw, offset+56)
        identity = struct.unpack_from('<Q', raw, offset+96)[0]
        short = raw[offset+68]
        _need(0 < length <= 510 and length % 2 == 0 and short <= 24 and short % 2 == 0)
        end = offset+104+length
        _need(end <= len(raw) and (not advance or advance % 8 == 0 and advance >= 104+length and offset+advance+104 <= len(raw)))
        name = raw[offset+104:end].decode('utf-16-le', errors='strict')
        if name not in ('.', '..'):
            component(name)
            _need(name.casefold() not in seen and identity > 0)
            seen.add(name.casefold()); result.append((name, attrs, identity))
        if not advance: return tuple(result)
        offset += advance


@dataclass(frozen=True, repr=False)
class _Binding:
    key: tuple
    user: str
    sid: bytes
    data_id: tuple
    root_id: tuple
    data_sd: tuple
    root_sd: tuple
    path: str
    command_path: str
    command_chain: tuple
    profile: str = PROFILE


_issued = weakref.WeakKeyDictionary()
_by_lease = weakref.WeakKeyDictionary()


def native_pgdata():
    raise DataRefused('NATIVE_PGDATA_NOT_ACCEPTED')


@_exclusive_entry
def _create_entry(lease, target):
    _need(type(lease) is FixedDirectoryLease and type(lease.fs) is FixedWindowsFilesystem
          and type(lease.fs.api) is NativeFixedLeaseAPI and type(target) is _NewDataTarget and target.lease is lease)
    _need(lease not in _by_lease)
    _by_lease[lease] = target  # One attempt, including an unknown create outcome.
    try:
        key = _key_held(lease)
        _need(key[-1] == 1 and lease.record['phase'] == 'CLUSTER' and not lease.record['initialized'])
        target._create_native(key)
    except BaseException:
        target._fail()
        raise


@_exclusive_operation
def _path_held(lease, target):
    _need(type(target) is _NewDataTarget and target.lease is lease and _by_lease.get(lease) is target)
    try:
        binding = target._verify()
        return binding.command_path
    except BaseException:
        target._fail()
        raise


@_exclusive_entry
def _scan_entry(lease, target):
    _need(type(target) is _NewDataTarget and target.lease is lease and _by_lease.get(lease) is target)
    try:
        before = target._walk()
        _need(target._walk() == before)  # Stable selected metadata, not DB contents.
        target._verify()
        return len(before)
    except BaseException:
        target._fail()
        raise


@_exclusive_entry
def _close_entry(lease, target):
    _need(type(target) is _NewDataTarget and target.lease is lease)
    target._close_native()


@_exclusive_operation
def _profile_held(lease, target):
    _need(type(target) is _NewDataTarget and target.lease is lease and _by_lease.get(lease) is target)
    try:
        binding = target._verify()
        _need(binding.key[-1] == 1)  # Invocation-local NEW capability only.
        return dict(profile=PROFILE, instance_id=binding.key[0], sid=binding.user,
                    parent_identity=list(binding.data_id), root_identity=list(binding.root_id),
                    root_control=binding.root_sd[1], root_security_sha256=descriptor_digest(binding.root_sd))
    except BaseException:
        target._fail()
        raise


class _NewDataTarget:
    native_acceptance = False
    launch_ready = False

    def __init__(self, lease, deadline):
        _need(os.name == 'nt' and C.sizeof(PTR) == 8 and type(lease) is FixedDirectoryLease)
        _need(type(deadline) in (int, float) and math.isfinite(deadline))
        self.lease, self.deadline = lease, deadline
        self.handles, self.data, self.root = [], None, None
        self.failed, self.closed, self.outcome, self.cleanup_errors = False, False, 'NOT_CREATED', []
        self.api = lease.fs.api
        _need(type(self.api) is NativeFixedLeaseAPI)
        self.query = self.api.k.GetFileInformationByHandleEx
        self.query.argtypes, self.query.restype = [PTR, C.c_int32, PTR, C.c_uint32], C.c_int32

    def __reduce__(self): raise TypeError('PGDATA_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('PGDATA_NOT_TRANSFERABLE')
    def __deepcopy__(self, memo): raise TypeError('PGDATA_NOT_TRANSFERABLE')

    def create(self):
        _create_entry(self.lease, self)

    def scan_stopped(self):
        # Caller must independently establish owned PG stopped. This method
        # neither establishes that fact nor authorizes resume or credentials.
        return _scan_entry(self.lease, self)

    def _time(self):
        _need(time.monotonic() < self.deadline)

    def _open(self, parent, name, *, create=False, descriptor=None, anchor=False):
        self._time(); component(name)
        raw = name.encode('utf-16-le'); text = C.create_string_buffer(raw+b'\0\0')
        unicode = UnicodeString(len(raw), len(raw)+2, C.cast(text, PTR))
        sd = C.create_string_buffer(descriptor) if descriptor is not None else None
        attrs = ObjectAttributes(C.sizeof(ObjectAttributes), parent, C.pointer(unicode),
                                 0x40, C.cast(sd, PTR) if sd is not None else None, None)
        handle, io = PTR(), IOStatus()
        status = self.api.ntcreate(C.byref(handle), 0x120081, C.byref(attrs), C.byref(io),
            None, 0x10 if create else 0, 3 if anchor else 7, 2 if create else 1,
            0x20|0x200000|(1 if create else 0), None, 0)
        # A failed NTSTATUS does not transfer ownership of an output integer.
        _need(status == 0 and handle.value not in (None, PTR(-1).value))
        self.handles.append(handle.value)  # Success-owned before further checks.
        if create: _need(io.Information == 2)  # FILE_CREATED, never OPEN_IF.
        return handle.value

    def _identity(self, handle, *, directory):
        info = self.api.info(handle)
        return _metadata(info, self.lease.fs.root_id[0], directory=directory)

    def _dos_path(self):
        self._time()
        buffer = C.create_unicode_buffer(4096)
        count = self.api.getpath(self.root, buffer, len(buffer), 0)  # VOLUME_NAME_DOS.
        _need(0 < count < len(buffer))
        return pg_command_path(buffer.value)

    def _pin_command_path(self, root_id, guid_path):
        before, drive, parts = self._dos_path()
        handle = self.api.open_drive(drive)
        self.handles.append(handle)
        chain = []
        for name in (None, *parts):
            if name is not None: handle = self._open(handle, name, anchor=True)
            identity = self._identity(handle, directory=True)
            chain.append((handle, identity, self.api.descriptor(handle)))
        _need(chain[-1][1] == root_id and self.api.final_path(handle) == guid_path and
              self._dos_path()[0] == before)
        return before, tuple(chain)  # Held until this target closes, not just path resolution.

    def _create_native(self, key):
        self.lease._verify()
        self.user = self.api.user_sid()
        # Read the actual current TOKEN_USER through existing API; never accept
        # an imported SID or substitute token owner for the user principal.
        token, used, primary, cleanup = PTR(), C.c_uint32(), None, None
        self.api.need(self.api.opentoken(self.api.process(), 8, C.byref(token)))
        _need(token.value not in (None, PTR(-1).value))
        try:
            buffer = C.create_string_buffer(4096)
            self.api.need(self.api.tokeninfo(token, 1, buffer, len(buffer), C.byref(used)))
            from .restricted_token_candidate import _parse
            sid = _parse(buffer, used.value, 1)
            _need(_sid_text(sid) == self.user)
        except BaseException as error:
            primary = error
        finally:
            try: self.api.close(token.value)
            except BaseException as error:
                cleanup = error
                self.cleanup_errors.append(('TOKEN_CLOSE_UNKNOWN', token.value))
        if primary is not None or cleanup is not None:
            raise BaseExceptionGroup('PGDATA_USER_QUERY_UNKNOWN',
                                     [x for x in (primary, cleanup) if x is not None])
        self.data = self._open(self.lease.fs.root, 'data', anchor=True)
        data_id = self._identity(self.data, directory=True)
        private_acl(self.api.security(self.data), self.user)
        data_sd = self.api.descriptor(self.data)
        _need(self.api.final_path(self.data) == self.api.final_path(self.lease.fs.root).rstrip('\\')+'\\data')
        self.root = self._open(self.data, 'postgresql', create=True,
                              descriptor=root_descriptor(sid), anchor=True)
        root_id = self._identity(self.root, directory=True)
        _need(len({tuple(self.lease.fs.root_id), data_id, root_id}) == 3)
        check_security(self.api.security(self.root), self.user, root=True, directory=True)
        root_sd = self.api.descriptor(self.root)
        path = self.api.final_path(self.data).rstrip('\\')+'\\postgresql'
        _need(self.api.final_path(self.root) == path)
        check_descriptor(root_sd, sid, root=True, directory=True)
        command_path, chain = self._pin_command_path(root_id, path)
        binding = _Binding(key, self.user, sid, data_id, root_id, data_sd, root_sd, path, command_path, chain)
        _issued[self] = binding
        self._verify()
        _need(self._entries(self.root) == ())  # Only this invocation's new empty root.
        self._verify()
        self.outcome = 'NEW_ROOT_OBSERVED_NOT_NATIVE_ACCEPTANCE'

    def _verify(self):
        self._time()
        _need(not self.closed and not self.failed and _by_lease.get(self.lease) is self)
        binding = _issued.get(self)
        _need(binding is not None and binding.profile == PROFILE and _key_held(self.lease) == binding.key)
        self.lease._verify()
        _need(self.api is self.lease.fs.api and self.api.user_sid() == binding.user and
              self._identity(self.data, directory=True) == binding.data_id and
              self._identity(self.root, directory=True) == binding.root_id and
              self.api.descriptor(self.data) == binding.data_sd and
              self.api.descriptor(self.root) == binding.root_sd and
              self.api.final_path(self.data) == self.api.final_path(self.lease.fs.root).rstrip('\\')+'\\data' and
              self.api.final_path(self.root) == binding.path)
        check_security(self.api.security(self.root), binding.user, root=True, directory=True)
        for handle, identity, descriptor in binding.command_chain:
            _need(self._identity(handle, directory=True) == identity and self.api.descriptor(handle) == descriptor)
        _need(self._dos_path()[0] == binding.command_path)
        self.lease._verify()
        return binding

    def _entries(self, handle):
        rows, seen, restart = [], set(), True
        for _ in range(4096):
            self._time()
            buffer = C.create_string_buffer(65536)
            ok = self.query(handle, 11 if restart else 10, buffer, len(buffer))
            if not ok:
                _need(C.get_last_error() == 18)  # ERROR_NO_MORE_FILES only.
                return tuple(sorted(rows))
            restart = False
            for row in directory_batch(buffer.raw):
                _need(row[0].casefold() not in seen and len(rows) < 100000)
                seen.add(row[0].casefold()); rows.append(row)
        _need(False)

    def _walk(self):
        binding = self._verify(); result, seen = [], {binding.root_id}
        def visit(parent, parts):
            self._time(); _need(len(parts) <= 64)
            parent_info, parent_sd = self.api.info(parent), self.api.descriptor(parent)
            entries = self._entries(parent)
            for name, attrs, identity in entries:
                _need(len(result) < 100000)
                directory = bool(attrs & DIRECTORY)
                handle = self._open(parent, name)
                primary, cleanup = None, None
                try:
                    ident = self._identity(handle, directory=directory)
                    _need(ident[1] == identity and ident not in seen)
                    seen.add(ident)
                    security = self.api.security(handle)
                    check_security(security, binding.user, root=False, directory=directory)
                    descriptor = self.api.descriptor(handle)
                    check_descriptor(descriptor, binding.sid, root=False, directory=directory)
                    _need(self.api.final_path(handle) == binding.path+'\\'+'\\'.join((*parts, name)))
                    result.append(((*parts, name), ident, descriptor, directory))
                    if directory: visit(handle, (*parts, name))
                    _need(self._identity(handle, directory=directory) == ident and
                          self.api.descriptor(handle) == descriptor)
                except BaseException as error:
                    primary = error
                finally:
                    try: self._close_one(handle)
                    except BaseException as error: cleanup = error
                if primary is not None and cleanup is not None:
                    raise BaseExceptionGroup('PGDATA_OBJECT_AND_CLOSE_UNKNOWN', [primary, cleanup])
                if primary is not None: raise primary
                if cleanup is not None: raise cleanup
            # Any selected structural/ACL drift refuses, never repairs. Sizes
            # and content hashes are deliberately not a whole-database claim.
            _need(self.api.info(parent) == parent_info and self.api.descriptor(parent) == parent_sd and
                  self._entries(parent) == entries)
        visit(self.root, ())
        return tuple(result)

    def _close_one(self, handle):
        # Remove before close: an unknown close is never retried by integer.
        self.handles.remove(handle)
        try: self.api.close(handle)
        except BaseException:
            self.cleanup_errors.append(('HANDLE_CLOSE_UNKNOWN', handle))
            raise

    def close(self):
        _close_entry(self.lease, self)

    def _close_native(self):
        errors = []
        for handle in tuple(reversed(self.handles)):
            try: self._close_one(handle)
            except BaseException as error: errors.append(error)
        self.closed = True
        if errors:
            self.failed, self.outcome, self.lease.poisoned = True, 'UNKNOWN', True
            raise BaseExceptionGroup('PGDATA_CLOSE_UNKNOWN', errors)

    def _fail(self):
        self.failed, self.outcome, self.lease.poisoned = True, 'UNKNOWN', True
        try: self._close_native()
        except BaseException: pass  # Retain primary and cleanup_errors; no delete/repair.
