"""Native Windows lease syscalls; no Linux emulation or ACL/owner setters.

Native directory-metadata durability is NOT accepted. The production preflight
refuses before opening/mutating a root until that exact barrier is established.
API code and Linux stand-in checks do not constitute a native safety acceptance.
"""
import ctypes as C
import os
import re
from uuid import uuid4

from .directories import JOURNAL, LOCK, LIMIT, LeaseRefused


class RenameInfo(C.Structure):
    _fields_ = [('ReplaceIfExists', C.c_uint32), ('RootDirectory', C.c_void_p),
                ('FileNameLength', C.c_uint32), ('FileName', C.c_uint16 * 1)]


def rename_buffer(root, name, replace):
    # Win64 FILE_RENAME_INFO: RootDirectory at8, length16, UTF-16 name20.
    from .payload import safe_name
    safe_name(name)
    if '/' in name: raise LeaseRefused('RELATIVE_COMPONENT_REQUIRED')
    raw = name.encode('utf-16-le')
    data = C.create_string_buffer(max(C.sizeof(RenameInfo), RenameInfo.FileName.offset + len(raw) + 2))
    info = C.cast(data, C.POINTER(RenameInfo)).contents
    info.ReplaceIfExists = int(replace); info.RootDirectory = root
    info.FileNameLength = len(raw)
    C.memmove(C.addressof(data) + RenameInfo.FileName.offset, raw, len(raw))
    return data


class NativeLeaseAPI:
    def __init__(self):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8:
            raise LeaseRefused('NATIVE_WINDOWS_X64_REQUIRED')
        from parkweave.windows_handles import WinAPI
        self.readonly = WinAPI()  # Original SYSTEM32-only loaders and ABI.
        self.k = self.readonly.k
        def bind(name, result, args):
            function = getattr(self.k, name); function.restype = result; function.argtypes = args
            return function
        self.writefile = bind('WriteFile', C.c_int32, [C.c_void_p, C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32), C.c_void_p])
        self.flushfile = bind('FlushFileBuffers', C.c_int32, [C.c_void_p])
        self.renamefile = bind('SetFileInformationByHandle', C.c_int32, [C.c_void_p, C.c_uint32, C.c_void_p, C.c_uint32])
        self.mkdir = bind('CreateDirectoryW', C.c_int32, [C.c_wchar_p, C.c_void_p])

    def __getattr__(self, name): return getattr(self.readonly, name)

    def require_directory_durability(self):
        # FlushFileBuffers documents writable FILE handles, not an accepted
        # user-mode directory-rename barrier. Never request admin volume flush
        # or assume file flush/WRITE_THROUGH alone proves parent persistence.
        raise LeaseRefused('WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED')

    def sync_directory(self, handle):
        # Deliberately no writable-volume/admin or undocumented success fallback.
        self.require_directory_durability()

    def descriptor(self, handle):
        from parkweave.windows_handles import U16, U32, PTR
        owner, dacl, sd = PTR(), PTR(), PTR()
        if self.readonly.getsecurity(handle, 1, 1 | 4, C.byref(owner), None, C.byref(dacl), None, C.byref(sd)):
            raise LeaseRefused('DESCRIPTOR_READ_REFUSED')
        primary = None
        try:
            self.need(self.readonly.valid_sd(sd)); control, revision = U16(), U32()
            self.need(self.readonly.control(sd, C.byref(control), C.byref(revision)))
            if not dacl.value: raise LeaseRefused('PRIVATE_DACL_REQUIRED')
            self.need(self.readonly.valid_acl(dacl))
            size = C.c_uint16.from_address(dacl.value + 2).value
            if not 8 <= size <= 65535: raise LeaseRefused('DACL_LIMIT')
            return (self.sid(owner), control.value, C.string_at(dacl, size))
        except BaseException as error:
            primary = error
            raise
        finally:
            if sd.value:
                try:
                    if self.localfree(sd): raise LeaseRefused('DESCRIPTOR_ALLOCATION_CLOSE_UNKNOWN')
                except BaseException as cleanup:
                    if primary is not None:
                        raise BaseExceptionGroup('DESCRIPTOR_AND_FREE_UNKNOWN', [primary, cleanup])
                    raise

    def relative_file(self, parent, name, *, fresh=False, write=False, exclusive=False, rename=False):
        from parkweave.windows_handles import (UnicodeString, ObjectAttributes, IOStatus, PTR,
            nt_status,completed_nt_handle,require_nt_create_ready,retain_pending_nt_create)
        require_nt_create_ready(self.readonly)
        from parkweave.windows_files import component
        component(name)
        raw = name.encode('utf-16-le'); text = C.create_string_buffer(raw + b'\0\0')
        unicode = UnicodeString(len(raw), len(raw) + 2, C.cast(text, PTR))
        attributes = ObjectAttributes(C.sizeof(ObjectAttributes), parent, C.pointer(unicode), 0x40, None, None)
        handle, io = PTR(), IOStatus()
        # No WRITE_OWNER/WRITE_DAC or privilege APIs. DELETE applies only to the
        # newly created temp that will be renamed, never the persistent lock.
        access = 0x20000 | 0x80 | 0x100000 | 1
        if write: access |= 0x40000000
        if rename: access |= 0x10000
        options = 0x20 | 0x200000 | 0x40 | (2 if write else 0)
        status = self.ntcreate(C.byref(handle), access, C.byref(attributes), C.byref(io), None,
                               0x80, 0 if exclusive else 1, 2 if fresh else 1, options, None, 0)
        status=nt_status(status)
        if status==0x103:
            retain_pending_nt_create(self.readonly,handle,io,attributes,unicode,text)
            raise LeaseRefused('NATIVE_RELATIVE_FILE_PENDING_UNKNOWN')
        owned=completed_nt_handle(status,handle.value)
        if status != 0 or not owned:
            primary = LeaseRefused('NATIVE_RELATIVE_FILE_REFUSED')
            if owned:
                try: self.close(handle.value)
                except BaseException as cleanup:
                    raise BaseExceptionGroup('NATIVE_OPEN_CLEANUP_UNKNOWN', [primary, cleanup]) from primary
            raise primary
        return handle.value

    def write_all(self, handle, raw):
        pending = raw
        while pending:
            buffer = C.create_string_buffer(pending); count = C.c_uint32()
            self.need(self.writefile(handle, buffer, len(pending), C.byref(count), None))
            if not 0 < count.value <= len(pending): raise LeaseRefused('NATIVE_SHORT_WRITE')
            pending = pending[count.value:]

    def flush(self, handle): self.need(self.flushfile(handle))

    def rename(self, source, root, name, *, replace):
        data = rename_buffer(root, name, replace)
        self.need(self.renamefile(source, 3, data, C.sizeof(data)))  # FileRenameInfo.

    def create_directory(self, parent_path, name):
        # All ancestors are held without SHARE_DELETE for this exact path.
        # Inherit only; a nonconforming resulting descriptor is refused, never
        # repaired. Original setup pause precedes this code.
        from parkweave.windows_files import component
        component(name)
        self.need(self.mkdir(parent_path + '\\' + name, None))


class WindowsFilesystem:
    def __init__(self, base, *, api=None):
        self.base, self.api = base, api
        self.handles, self.bindings = [], []

    def hold(self, handle): self.handles.append(handle); return handle
    def identity(self, handle):
        info = self.api.info(handle); return [info.volume, info.identity]

    def _object(self, handle, *, directory, private=False):
        from parkweave.windows_files import metadata, private_acl
        info = self.api.info(handle); metadata(info, directory, self.volume)
        if private: private_acl(self.api.security(handle), self.api.user_sid())
        return [info.volume, info.identity]

    def acquire(self, name, *, fresh):
        if fresh:
            from scripts.windows.lifecycle import require_setup_readiness
            require_setup_readiness()
        if self.api is None: self.api = NativeLeaseAPI()
        # No false durable publication on an unaccepted Windows barrier.
        self.api.require_directory_durability()
        self._acquire_handles(name, fresh=fresh)

    def _acquire_handles(self, name, *, fresh):
        """Shared handle mechanics only; each storage path owns its preflight."""
        from parkweave.windows_files import root_parts
        drive, parts = root_parts(self.base)
        handle = self.hold(self.api.open_drive(drive))
        guid = self.api.final_path(handle)
        if (not re.fullmatch(r'\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\', guid)
                or self.api.filesystem(handle) != 'NTFS' or self.api.drive_type(guid) != 3):
            raise LeaseRefused('FIXED_LOCAL_NTFS_REQUIRED')
        self.volume = self.api.info(handle).volume
        self._object(handle, directory=True)
        for part in parts:
            handle = self.hold(self.api.open_relative(handle, part, False))
            self._object(handle, directory=True)
        self._object(handle, directory=True, private=True)
        if fresh: self.api.create_directory(self.base, name)
        # FILE_READ_DATA on a directory is FILE_LIST_DIRECTORY. The immutable
        # runtime verifier enumerates this exact original root, read-only.
        self.root = self.hold(self.api.open_relative(handle, name, True))
        self._object(self.root, directory=True, private=True)
        self.lock = self.hold(self.api.relative_file(self.root, LOCK, fresh=fresh, write=True, exclusive=True))
        self._object(self.lock, directory=False, private=True)
        self.root_id, self.lock_id = self.identity(self.root), self.identity(self.lock)
        self.bindings = [(h, self.identity(h), self.api.descriptor(h)) for h in self.handles]
        self.verify()

    def verify(self):
        for handle, identity, descriptor in self.bindings:
            if self.identity(handle) != identity or self.api.descriptor(handle) != descriptor:
                raise LeaseRefused('NATIVE_BINDING_CHANGED')
        self._object(self.root, directory=True, private=True)
        self._object(self.lock, directory=False, private=True)
        # Original parent/ancestor handles and lock exclude SHARE_DELETE;
        # canonical final paths additionally bind the child to that exact root.
        if self.api.final_path(self.lock) != self.api.final_path(self.root).rstrip('\\') + '\\' + LOCK:
            raise LeaseRefused('NATIVE_LOCK_PATH_CHANGED')

    def read(self):
        handle = self.api.relative_file(self.root, JOURNAL)
        try:
            identity = self._object(handle, directory=False, private=True)
            before, descriptor = self.api.info(handle), self.api.descriptor(handle)
            raw = self.api.read(handle, LIMIT + 1)
            if self.api.info(handle) != before or self.api.descriptor(handle) != descriptor:
                raise LeaseRefused('NATIVE_JOURNAL_CHANGED')
            return raw, identity
        finally: self.api.close(handle)

    def replace(self, raw, expected):
        self.verify()
        if expected is not None and self.read() != expected: raise LeaseRefused('NATIVE_JOURNAL_IDENTITY_CHANGED')
        name = '.parkweave-journal-' + uuid4().hex + '.tmp'
        handle = self.api.relative_file(self.root, name, fresh=True, write=True, exclusive=True, rename=True)
        try:
            self._object(handle, directory=False, private=True)
            self.api.write_all(handle, raw); self.api.flush(handle)
            self.verify()
            if expected is not None and self.read() != expected: raise LeaseRefused('NATIVE_JOURNAL_IDENTITY_CHANGED')
            self.api.rename(handle, self.root, JOURNAL, replace=expected is not None)
            self.api.flush(handle)
            self.api.sync_directory(self.root)  # Required, never substituted by file flush.
        finally: self.api.close(handle)
        result = self.read()
        if result[0] != raw: raise LeaseRefused('NATIVE_JOURNAL_PUBLICATION_UNKNOWN')
        self.verify()
        return result

    def close(self):
        errors = []
        lock = getattr(self, 'lock', None)
        order = [h for h in reversed(self.handles) if h != lock] + ([lock] if lock in self.handles else [])
        self.handles.clear()
        for handle in order:
            try: self.api.close(handle)
            except BaseException as error: errors.append(error)
        if errors: raise BaseExceptionGroup('NATIVE_LEASE_CLOSE_UNKNOWN', errors)
