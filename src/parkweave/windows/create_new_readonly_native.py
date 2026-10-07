"""Default-off native creation and explicitly non-CAS experimental rename.

No security setters, CRT conversion or production integration. Kernel calls are
real; all local tests inject a fake API. Native execution is not acceptance.
"""
import ctypes as C
from dataclasses import dataclass
from enum import Enum
import io
import math
import os
from pathlib import Path
import re
import sys
import time
from uuid import UUID

from ..windows_handles import (WinAPI, UnicodeString, ObjectAttributes, IOStatus,
                               ACL, PTR, U16, U32, I32)
from ..windows_files import root_parts, Info
from . import create_new_readonly_candidate as p

CREATE_ACCESS = 0x20082  # WRITE_DATA | READ_CONTROL | READ_ATTRIBUTES
DELETE = 0x10000
REPLACEMENT_TEMP_ACCESS = CREATE_ACCESS | DELETE
READ_PARENT_ACCESS = 0x1200a0  # READ_CONTROL | READ_ATTRIBUTES | TRAVERSE | SYNCHRONIZE
FILE_QUERY_ACCESS = 0x20080  # READ_CONTROL | READ_ATTRIBUTES, no file sync/execute.
REPLACEMENT_PARENT_ACCESS = READ_PARENT_ACCESS | 0x2 | 0x40  # ADD_FILE / DELETE_CHILD
FILE_CREATE = 2
FILE_OPEN = 1
OPEN_REPARSE = 0x200000
NON_DIRECTORY = 0x40
DIRECTORY = 1
SYNC_NONALERT = 0x20
SHARE_READ_WRITE = 3  # Pin ancestor names: never SHARE_DELETE.
SHARE_READ_DELETE = 5
ERROR_IO_PENDING = 997
ERROR_IO_INCOMPLETE = 996
WAIT_OBJECT_0 = 0
MAX_WRITE = 16384
_PENDING_RETENTION = {}  # Strong process-lifetime retention until explicit reap.


class Overlapped(C.Structure):
    _fields_ = [('Internal', C.c_size_t), ('InternalHigh', C.c_size_t),
                ('Offset', U32), ('OffsetHigh', U32), ('hEvent', PTR)]


class RenameInfo(C.Structure):
    _fields_ = [('ReplaceIfExists', C.c_uint8), ('RootDirectory', PTR),
                ('FileNameLength', U32), ('FileName', U16 * 1)]


class AclSize(C.Structure):
    _fields_ = [('count', U32), ('used', U32), ('free', U32)]


class Namespace(Enum):
    FIXED_RUNTIME = 'FIXED_RUNTIME'
    EXPLICIT_NONCAS_EXCLUSIVE_CANDIDATE_NAMESPACE = 'EXPLICIT_NONCAS_EXCLUSIVE_CANDIDATE_NAMESPACE'


@dataclass(frozen=True)
class ReplacementContract:
    require_target_cas: bool = True
    explicit_noncas_exclusive_candidate_namespace: bool = False
    temp_access: int = REPLACEMENT_TEMP_ACCESS
    parent_access: int = REPLACEMENT_PARENT_ACCESS


@dataclass(frozen=True)
class NativeCreationContract:
    # READ_ATTRIBUTES is necessary for same-handle reparse/metadata queries;
    # this native contract is deliberately distinct from ENG098's fake seam.
    access: int = CREATE_ACCESS


@dataclass(frozen=True)
class OwnedRecord:
    # Only this adapter's completed creation issues/retains this exact object.
    kind: p.ObjectKind
    basename: str
    identity: Info
    descriptor: p.Descriptor
    byte_count: int


@dataclass(frozen=True)
class ReplacementReceipt:
    final: OwnedRecord
    target_cas: bool = False
    same_user_namespace_race_unresolved: bool = True
    content_readback_verified: bool = False
    durability_verified: bool = False
    outcome: str = 'PUBLISHED_FINAL_VERIFIED_NONCAS'


def _refuse(reason):
    raise p.CandidateRefused(reason)


def _cleanup(call, primary=None):
    try:
        call()
    except Exception:
        if primary is not None:
            primary.candidate_cleanup_failed = True
        else:
            _refuse('CLEANUP_REFUSED')


class CtypesAPI(WinAPI):
    """System-DLL-only x64 bindings; object access is operation-specific."""
    def __init__(self):
        self.quarantine = []
        self.pending_handles = set()
        self.retained_cleanup = set()
        super().__init__()
        def bind(lib, name, result, args):
            fn = getattr(lib, name)
            fn.restype, fn.argtypes = result, args
            return fn
        self.aclinfo = bind(self.a, 'GetAclInformation', I32, [PTR, PTR, U32, I32])
        self.event = bind(self.k, 'CreateEventW', PTR, [PTR, I32, I32, C.c_wchar_p])
        self.writefile = bind(self.k, 'WriteFile', I32, [PTR, PTR, U32, PTR, C.POINTER(Overlapped)])
        self.wait = bind(self.k, 'WaitForSingleObject', U32, [PTR, U32])
        self.result = bind(self.k, 'GetOverlappedResult', I32, [PTR, C.POINTER(Overlapped), C.POINTER(U32), I32])
        self.cancel = bind(self.k, 'CancelIoEx', I32, [PTR, C.POINTER(Overlapped)])
        self.setinfo = bind(self.k, 'SetFileInformationByHandle', I32, [PTR, I32, PTR, U32])

    def close(self, handle):
        if isinstance(handle, PTR):
            handle = handle.value
        p._handle(handle)
        if handle in self.pending_handles:
            _refuse('PENDING_IO_RETAINED')
        super().close(handle)

    def has_pending(self):
        return bool(self.quarantine)

    def poll_pending(self):
        """Explicit readonly completion poll; no wait, new IO or deadline reset.

        Only success or ERROR_OPERATION_ABORTED proves terminal completion.
        Unknown errors remain quarantined. No successful creation receipt.
        """
        for item in tuple(self.quarantine):
            if len(item) != 4 or id(item) in getattr(self, 'retained_cleanup', set()):
                continue
            handle, buf, ov, event = item
            count = U32()
            completed = self.result(handle, C.byref(ov), C.byref(count), False)
            if not completed and C.get_last_error() != 995:
                continue
            self.pending_handles.discard(handle)
            failed = False
            for resource in (event, handle):
                try:
                    self.close(resource)
                except Exception:
                    failed = True
            if failed:
                if not hasattr(self, 'retained_cleanup'):
                    self.retained_cleanup = set()
                self.retained_cleanup.add(id(item))
                _refuse('CLEANUP_REFUSED')
            self.quarantine.remove(item)
        if not self.quarantine:
            _PENDING_RETENTION.pop(id(self), None)
        return not self.quarantine

    def need(self, value):
        if not value:
            _refuse('NATIVE_READ_REFUSED')

    def current_user_sid(self):
        return self._user_sid()  # TokenUser, never TokenOwner/privilege.

    def descriptor(self, handle):
        owner, dacl, sd = PTR(), PTR(), PTR()
        status = self.getsecurity(handle, 1, 1 | 4, C.byref(owner), None,
                                  C.byref(dacl), None, C.byref(sd))
        try:
            if status or not sd.value or not owner.value or not dacl.value:
                _refuse('DESCRIPTOR_REFUSED')
            self.need(self.valid_sd(sd))
            self.need(self.valid_acl(dacl))
            control, revision = U16(), U32()
            self.need(self.control(sd, C.byref(control), C.byref(revision)))
            header = C.cast(dacl, C.POINTER(ACL)).contents
            if not 8 <= header.Size <= 65535 or header.Size % 4:
                _refuse('DESCRIPTOR_REFUSED')
            sizes = AclSize()
            self.need(self.aclinfo(dacl, C.byref(sizes), C.sizeof(sizes), 2))
            if (sizes.used + sizes.free != header.Size or not 8 <= sizes.used <= header.Size
                    or sizes.count != header.AceCount or not 1 <= sizes.count <= 128):
                _refuse('DESCRIPTOR_REFUSED')
            cursor, end = dacl.value + 8, dacl.value + sizes.used
            for index in range(sizes.count):
                ace = PTR()
                self.need(self.getace(dacl, index, C.byref(ace)))
                if ace.value != cursor or cursor + 4 > end:
                    _refuse('DESCRIPTOR_REFUSED')
                length = U16.from_address(cursor + 2).value
                if length < 16 or length % 4 or cursor + length > end:
                    _refuse('DESCRIPTOR_REFUSED')
                cursor += length
            if cursor != end:
                _refuse('DESCRIPTOR_REFUSED')
            value = p.Descriptor(self.sid(owner), C.string_at(dacl, header.Size), control.value)
            p._aces(value.raw_dacl)
            return value
        finally:
            if sd.value:
                _cleanup(lambda: self.need(not self.localfree(sd)), sys.exc_info()[1])

    def sid(self, pointer):
        self.need(self.valid_sid(pointer))
        out = PTR()
        try:
            self.need(self.sidstring(pointer, C.byref(out)))
            return C.wstring_at(out)
        finally:
            if out.value:
                _cleanup(lambda: self.need(not self.localfree(out)), sys.exc_info()[1])

    def relative(self, parent, name, *, access, disposition, share, directory=False):
        p.component(name)
        raw = name.encode('utf-16-le')
        buf = C.create_string_buffer(raw + b'\0\0')
        u = UnicodeString(len(raw), len(raw) + 2, C.cast(buf, PTR))
        oa = ObjectAttributes(C.sizeof(ObjectAttributes), parent, C.pointer(u), 0x40, None, None)
        handle, ios = PTR(), IOStatus()
        options = OPEN_REPARSE | (DIRECTORY | SYNC_NONALERT if directory else NON_DIRECTORY)
        status = self.ntcreate(C.byref(handle), access, C.byref(oa), C.byref(ios),
                               None, 0x80, share, disposition, options, None, 0)
        if status != 0 or not handle.value or ios.Information != (2 if disposition == FILE_CREATE else 1):
            if status == 0x103:
                self.quarantine.append((buf, u, oa, handle, ios))
                if handle.value:
                    self.pending_handles.add(handle.value)
                _PENDING_RETENTION[id(self)] = self
            error = FileExistsError('EXISTING_OBJECT') if status & 0xffffffff == 0xc0000035 else p.CandidateRefused('NATIVE_OPEN_REFUSED')
            if status == 0x103:
                error.candidate_cleanup_failed = True
            if handle.value:
                _cleanup(lambda: self.close(handle.value), error)
            raise error
        return handle.value

    def open_drive(self, drive):
        handle = self.create('\\\\?\\' + drive, READ_PARENT_ACCESS, SHARE_READ_WRITE,
                             None, 3, 0x02000000 | OPEN_REPARSE, None)
        if handle in (None, PTR(-1).value):
            _refuse('NATIVE_OPEN_REFUSED')
        return handle

    def write_at(self, handle, data, offset, deadline, clock):
        """Wait on independent event, never on the strict-access file handle."""
        event = self.event(None, True, False, None)
        if not event:
            _refuse('EVENT_CREATE_REFUSED')
        buf = C.create_string_buffer(data)
        ov = Overlapped(0, 0, offset & 0xffffffff, offset >> 32, event)
        pending = False
        try:
            if not self.writefile(handle, buf, len(data), None, C.byref(ov)):
                if C.get_last_error() != ERROR_IO_PENDING:
                    _refuse('WRITE_REFUSED')
                pending = True
            else:
                pending = True  # Completion still obtained through exact OVERLAPPED.
            left = deadline - clock()
            if left <= 0 or self.wait(event, min(0xfffffffe, max(1, math.ceil(left * 1000)))) != WAIT_OBJECT_0:
                _refuse('WRITE_DEADLINE')
            count = U32()
            if not self.result(handle, C.byref(ov), C.byref(count), False):
                if C.get_last_error() == 995:
                    pending = False  # Completed with failure, buffer can retire.
                _refuse('WRITE_COMPLETION_REFUSED')
            pending = False
            if clock() > deadline or not 0 < count.value <= len(data):
                _refuse('WRITE_COMPLETION_REFUSED')
            return count.value
        finally:
            if pending:
                # Cancellation is a request, not proof of completion. Retain all
                # memory and the event; never refresh deadline or free pending IO.
                self.quarantine.append((handle, buf, ov, event))
                self.pending_handles.add(handle)
                _PENDING_RETENTION[id(self)] = self
                primary = sys.exc_info()[1]
                try:
                    self.cancel(handle, C.byref(ov))
                except Exception:
                    pass  # Retention precedes even a failed cancellation call.
                if primary is not None:
                    primary.candidate_cleanup_failed = True
            else:
                _cleanup(lambda: self.close(event), sys.exc_info()[1])

    def rename_relative(self, source, parent, name):
        p.component(name)
        raw = name.encode('utf-16-le')
        size = max(C.sizeof(RenameInfo), RenameInfo.FileName.offset + len(raw))
        buf = C.create_string_buffer(size)
        info = RenameInfo.from_buffer(buf)
        info.ReplaceIfExists, info.RootDirectory, info.FileNameLength = 1, parent, len(raw)
        C.memmove(C.addressof(buf) + RenameInfo.FileName.offset, raw, len(raw))
        if not self.setinfo(source, 3, buf, size):
            _refuse('RENAME_REFUSED')


class NativeTextStream(io.TextIOBase):
    def __init__(self, adapter, handle, request, descriptor, identity, deadline):
        self.adapter, self.handle, self.request = adapter, handle, request
        self.descriptor, self.identity, self.deadline = descriptor, identity, deadline
        self.offset, self.failed, self.record = 0, False, None

    @property
    def encoding(self):
        return 'utf-8'

    def writable(self):
        return not self.closed and not self.failed

    def write(self, value):
        if self.closed or self.failed:
            _refuse('STREAM_CLOSED')
        if type(value) is not str:
            raise TypeError('text required')
        data = value.encode('utf-8', 'strict')
        try:
            self.adapter._parent_check()
            self.adapter._file_check(self.handle, self.descriptor, self.identity, self.offset)
            while data:
                if self.adapter.clock() >= self.deadline:
                    _refuse('WRITE_DEADLINE')
                count = self.adapter.api.write_at(self.handle, data[:MAX_WRITE], self.offset,
                                                  self.deadline, self.adapter.clock)
                if type(count) is not int or not 0 < count <= min(MAX_WRITE, len(data)):
                    _refuse('WRITE_COMPLETION_REFUSED')
                self.offset += count
                data = data[count:]
            self.adapter._file_check(self.handle, self.descriptor, self.identity, self.offset)
            self.adapter._parent_check()
            return len(value)
        except Exception:
            self.failed = True
            raise

    def close(self):
        if self.closed:
            return
        error = None
        try:
            if not self.failed:
                self.adapter._parent_check()
                info = self.adapter._file_check(self.handle, self.descriptor, self.identity, self.offset)
                self.record = OwnedRecord(self.request.kind, self.request.basename, info, self.descriptor, self.offset)
        except Exception as caught:
            error = caught
        try:
            self.adapter.api.close(self.handle)
        except Exception:
            if error is not None:
                error.candidate_cleanup_failed = True
            else:
                error = p.CandidateRefused('CLEANUP_REFUSED')
        finally:
            super().close()
        if error is not None:
            self.failed, self.record = True, None
            raise error
        if self.record is not None:
            self.adapter._issued[id(self.record)] = self.record


class NativeAdapter:
    def __init__(self, *, enabled=False, expected_parent, namespace=Namespace.FIXED_RUNTIME,
                 namespace_id=None, _api=None, _runtime_for_tests=None, clock=time.monotonic):
        if enabled is not True:
            _refuse('NATIVE_OPERATION_DISABLED')
        if _api is None and (os.name != 'nt' or C.sizeof(PTR) != 8):
            _refuse('WINDOWS_X64_REQUIRED')
        if type(namespace) is not Namespace:
            _refuse('NAMESPACE_REFUSED')
        runtime = str(Path(__file__).resolve().parents[3] / '.runtime')
        if _api is None and Path(__file__).resolve().parts[-4:] != (
                'src', 'parkweave', 'windows', 'create_new_readonly_native.py'):
            _refuse('SOURCE_SCOPE_REFUSED')
        if _runtime_for_tests is not None:
            if _api is None:
                _refuse('TEST_SCOPE_REFUSED')
            runtime = _runtime_for_tests
        if namespace is Namespace.EXPLICIT_NONCAS_EXCLUSIVE_CANDIDATE_NAMESPACE:
            try:
                if str(UUID(namespace_id)) != namespace_id:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                _refuse('NAMESPACE_REFUSED')
            runtime += '\\eng099-noncas-' + namespace_id
        elif namespace_id is not None:
            _refuse('NAMESPACE_REFUSED')
        self.api, self.clock, self.namespace = _api or CtypesAPI(), clock, namespace
        self.handles, self._issued, self.active_streams, self._pinned = [], {}, [], []
        try:
            drive, parts = root_parts(runtime)
            parent = self._hold(self.api.open_drive(drive))
            guid = self.api.final_path(parent)
            if (not re.fullmatch(r'\\\\\?\\Volume\{[0-9a-fA-F-]{36}\}\\', guid)
                    or self.api.filesystem(parent) != 'NTFS' or self.api.drive_type(guid) != 3):
                _refuse('LOCAL_NTFS_REQUIRED')
            volume = self.api.info(parent).volume
            self._pinned.append((parent, self.api.info(parent), guid))
            expected_path = guid.rstrip('\\')
            for name in parts:
                p._metadata(self.api.info(parent), directory=True, volume=volume)
                parent = self._hold(self.api.relative(parent, name, access=READ_PARENT_ACCESS,
                                                       disposition=FILE_OPEN, share=SHARE_READ_WRITE, directory=True))
                expected_path += '\\' + name
                if self.api.final_path(parent) != expected_path:
                    _refuse('PARENT_PATH_MISMATCH')
                self._pinned.append((parent, self.api.info(parent), expected_path))
            p._metadata(self.api.info(parent), directory=True, volume=volume)
            self.parent, self.parent_ancestor, self.parent_name = parent, self.handles[-2], parts[-1]
            self.user = self.api.current_user_sid()
            p._private_descriptor(expected_parent, self.user, directory=True)
            self.parent_descriptor, self.parent_identity = expected_parent, self.api.info(parent)
            self._parent_check()
        except Exception:
            self.close(primary=sys.exc_info()[1])
            raise

    def _hold(self, handle):
        p._handle(handle)
        if handle in self.handles:
            _refuse('BORROWED_HANDLE_ALIAS')
        self.handles.append(handle)
        return handle

    def _parent_check(self):
        if not self.handles:
            _refuse('ADAPTER_CLOSED')
        if self.api.has_pending():
            _refuse('PENDING_IO_RETAINED')
        for handle, identity, path in self._pinned:
            observed = self.api.info(handle)
            p._metadata(observed, directory=True, volume=self.parent_identity.volume)
            if observed != identity or self.api.final_path(handle) != path:
                _refuse('ANCESTOR_CHANGED')
        if self.api.current_user_sid() != self.user:
            _refuse('USER_CHANGED')
        info, descriptor = self.api.info(self.parent), self.api.descriptor(self.parent)
        p._metadata(info, directory=True)
        p._private_descriptor(descriptor, self.user, directory=True)
        if info != self.parent_identity or descriptor != self.parent_descriptor:
            _refuse('PARENT_CHANGED')

    def _file_check(self, handle, descriptor, identity, size):
        info, observed = self.api.info(handle), self.api.descriptor(handle)
        p._metadata(Info(info.attributes, 0, info.links, info.volume, info.identity),
                    directory=False, volume=self.parent_identity.volume)
        p._private_descriptor(observed, self.user, directory=False)
        if (observed != descriptor or info.identity != identity.identity
                or info.volume != identity.volume or info.size != size):
            _refuse('FILE_CHANGED')
        return info

    def open_new(self, request, *, expected_child, deadline,
                 contract=NativeCreationContract()):
        if type(contract) is not NativeCreationContract or contract.access != CREATE_ACCESS:
            _refuse('CREATION_CAPABILITY_REFUSED')
        return self._open(request, expected_child, deadline, CREATE_ACCESS)

    def _open(self, request, descriptor, deadline, access):
        name = p._request(request)
        if type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline <= self.clock():
            _refuse('INVALID_DEADLINE')
        p._private_descriptor(descriptor, self.user, directory=False)
        self._parent_check()
        handle = None
        try:
            if self.clock() >= deadline:
                _refuse('WRITE_DEADLINE')
            created = self.api.relative(self.parent, name, access=access,
                                        disposition=FILE_CREATE, share=0)
            p._handle(created)
            if created in self.handles:
                _refuse('BORROWED_HANDLE_ALIAS')
            handle = created
            info = self.api.info(handle)
            self._file_check(handle, descriptor, info, 0)
            self._parent_check()
            self._file_check(handle, descriptor, info, 0)
            if self.clock() >= deadline:
                _refuse('WRITE_DEADLINE')
            stream = NativeTextStream(self, handle, request, descriptor, info, deadline)
            self.active_streams.append(stream)
            handle = None
            return stream
        finally:
            if handle is not None:
                _cleanup(lambda: self.api.close(handle), sys.exc_info()[1])

    def replace_record(self, target, request, *, expected_child, text, contract, deadline):
        """True native rename implementation, with honest non-CAS receipts.

        Default demands unsupported expected-ID CAS and refuses before writes.
        Only explicit experimental UUID namespace permits non-CAS execution.
        """
        if type(contract) is not ReplacementContract:
            _refuse('REPLACEMENT_CONTRACT_REQUIRED')
        if contract.require_target_cas is not False:
            _refuse('TARGET_ID_CAS_UNAVAILABLE')
        if (contract.explicit_noncas_exclusive_candidate_namespace is not True
                or self.namespace is not Namespace.EXPLICIT_NONCAS_EXCLUSIVE_CANDIDATE_NAMESPACE
                or contract.temp_access != REPLACEMENT_TEMP_ACCESS
                or contract.parent_access != REPLACEMENT_PARENT_ACCESS):
            _refuse('REPLACEMENT_CAPABILITY_REFUSED')
        if (type(target) is not OwnedRecord or self._issued.get(id(target)) is not target
                or target.kind is not p.ObjectKind.PROCESS_RECORD_INITIAL
                or target.basename != 'windows-processes.json'
                or type(request) is not p.Request or request.kind is not p.ObjectKind.BINDING_TEMP):
            _refuse('OWNED_TARGET_REQUIRED')
        self._parent_check()
        parent = old = final_query = None
        stream = None
        renamed = False
        try:
            parent = self.api.relative(self.parent_ancestor, self.parent_name,
                                        access=contract.parent_access, disposition=FILE_OPEN,
                                        share=SHARE_READ_WRITE, directory=True)
            if parent in self.handles:
                _refuse('BORROWED_HANDLE_ALIAS')
            if self.api.info(parent) != self.parent_identity or self.api.descriptor(parent) != self.parent_descriptor:
                _refuse('PARENT_CHANGED')
            old = self.api.relative(self.parent, target.basename, access=FILE_QUERY_ACCESS,
                                     disposition=FILE_OPEN, share=SHARE_READ_DELETE)
            if old in self.handles or old == parent:
                old = None
                _refuse('BORROWED_HANDLE_ALIAS')
            self._file_check(old, target.descriptor, target.identity, target.byte_count)
            stream = self._open(request, expected_child, deadline, contract.temp_access)
            stream.write(text)
            self._file_check(old, target.descriptor, target.identity, target.byte_count)
            self._parent_check()
            if self.clock() >= deadline:
                _refuse('WRITE_DEADLINE')
            # Standard replacement can refuse an open target. Release our exact
            # query handle; no claim of expected-inode CAS across this interval.
            self.api.close(old)
            old = None
            self.api.rename_relative(stream.handle, parent, target.basename)
            renamed = True
            self._parent_check()
            info = self._file_check(stream.handle, expected_child, stream.identity, stream.offset)
            # Verify the original temp handle's final rooted name, without a
            # second open conflicting with its share=0 exclusive access.
            final_name = self.api.final_path(stream.handle)
            parent_name = self.api.final_path(self.parent).rstrip('\\')
            if final_name != parent_name + '\\' + target.basename:
                _refuse('FINAL_NAME_MISMATCH')
            stream.request = p.Request(p.ObjectKind.PROCESS_RECORD_INITIAL, p.Operation.CREATE_NEW, target.basename)
            stream.close()
            final_query = self.api.relative(self.parent, target.basename, access=FILE_QUERY_ACCESS,
                                             disposition=FILE_OPEN, share=SHARE_READ_DELETE)
            if final_query in self.handles or final_query == parent:
                final_query = None
                _refuse('BORROWED_HANDLE_ALIAS')
            self._file_check(final_query, expected_child, stream.record.identity, stream.record.byte_count)
            self._parent_check()
            if self.clock() >= deadline:
                _refuse('WRITE_DEADLINE')
            self._issued.pop(id(target), None)
            return ReplacementReceipt(stream.record)
        except Exception as error:
            if stream is not None:
                stream.failed = True
                if stream.record is not None:
                    self._issued.pop(id(stream.record), None)
            if renamed:
                error.publication_may_have_occurred = True
                self._issued.pop(id(target), None)
            raise
        finally:
            primary = sys.exc_info()[1]
            if stream is not None:
                _cleanup(stream.close, primary)
            if old is not None:
                _cleanup(lambda: self.api.close(old), primary)
            if final_query is not None:
                _cleanup(lambda: self.api.close(final_query), primary)
            if parent is not None and parent not in self.handles:
                _cleanup(lambda: self.api.close(parent), primary)

    def close(self, primary=None):
        failed = False
        for stream in self.active_streams:
            if not stream.closed:
                try:
                    stream.close()
                except Exception:
                    failed = True
        self.active_streams.clear()
        while self.handles:
            handle = self.handles.pop()
            try:
                self.api.close(handle)
            except Exception:
                failed = True
        self._issued.clear()
        if failed:
            if primary is not None:
                primary.candidate_cleanup_failed = True
            else:
                _refuse('CLEANUP_REFUSED')
