"""Nontransmitting initdb password-pipe server candidate, never activated.

No import-time DLL or native calls. Creating a server WOULD create a private
kernel object, requiring separate native authorization. No connect, WriteFile,
password, temporary file, process or Job operations are implemented here.
The registry, not a name string, binds this object's lease/generation/handle.
GetNamedPipeInfo is NOT_OBSERVED: creation arguments are not independent readback.
An external client could connect early; absence of a Connect call does not prove
disconnection. This phase supplies no client authentication or secret-write gate.
"""
import ctypes as C
import os
import re
import secrets
import struct
from threading import RLock
import weakref

from .default_dacl_candidate import _sid_buffer
from .endpoint_plan import _key_held
from .fixed_directories import FixedDirectoryLease, _exclusive_entry, _exclusive_operation
from .fixed_windows_journal import FixedWindowsFilesystem, NativeFixedLeaseAPI
from .restricted_token_candidate import _RestrictedPrimaryCandidate, TokenProfile


class PipeRefused(RuntimeError):
    pass


class PipeFailure(PipeRefused):
    def __init__(self, phase, primary_type, cleanup, winerror):
        self.phase, self.primary_type = phase, primary_type
        self.cleanup, self.winerror = tuple(cleanup), winerror
        self.outcome = 'UNKNOWN'
        super().__init__('OWNED_INITDB_PIPE_UNKNOWN:'+phase)


class SecurityAttributes(C.Structure):
    _fields_ = [('length', C.c_uint32), ('descriptor', C.c_void_p), ('inherit', C.c_int32)]


def _need(ok):
    if not ok:
        raise PipeRefused('OWNED_INITDB_PIPE_REFUSED')


def _sid_at(raw, offset):
    _need(type(offset) is int and offset >= 20 and offset % 4 == 0 and offset + 8 <= len(raw))
    size = 8 + 4 * raw[offset + 1]
    _need(raw[offset] == 1 and raw[offset + 1] <= 15 and offset + size <= len(raw))
    return raw[offset:offset + size], offset + size


def _private_descriptor(raw, expected_sid):
    """Strict self-relative OWNER+DACL subset before native pointer validation."""
    _need(type(raw) is bytes and 20 <= len(raw) <= 65536)
    revision, zero, control, owner, group, sacl, dacl = struct.unpack_from('<BBHIIII', raw)
    _need(revision == 1 and zero == 0 and control & 0x9004 == 0x9004)
    _need(control & ~0x9007 == 0 and group == sacl == 0)
    owner_sid, owner_end = _sid_at(raw, owner)
    _need(owner_sid == expected_sid)
    _need(dacl >= 20 and dacl % 4 == 0 and dacl + 8 <= len(raw))
    rev, zero1, size, count, zero2 = struct.unpack_from('<BBHHH', raw, dacl)
    _need(rev in (2, 4) and zero1 == zero2 == 0 and count == 1)
    _need(size >= 24 and size % 4 == 0 and dacl + size <= len(raw))
    _need(owner_end <= dacl or dacl + size <= owner)
    kind, flags, ace_size, mask = struct.unpack_from('<BBHI', raw, dacl + 8)
    _need(kind == 0 and flags == 0 and ace_size >= 16 and 8 + ace_size <= size)
    _need(mask in (0x10000000, 0x001f01ff))
    sid, end = _sid_at(raw, dacl + 16)
    _need(sid == expected_sid and end == dacl + 8 + ace_size)


def _pipe_name(instance_id, nonce):
    from uuid import UUID
    _need(type(instance_id) is str and str(UUID(instance_id)) == instance_id)
    _need(type(nonce) is str and re.fullmatch('[0-9a-f]{32}', nonce) is not None)
    return '\\\\.\\pipe\\ParkWeave-' + instance_id + '-' + nonce


def native_initdb_pipe():
    raise PipeRefused('NATIVE_INITDB_PIPE_NOT_ACCEPTED')


_by_lease = weakref.WeakKeyDictionary()
_by_owner = weakref.WeakKeyDictionary()


def _owner_sid_held(lease, server):
    owner = server._owner
    _need(type(owner) is _RestrictedPrimaryCandidate and owner._profile is TokenProfile.CREATE_CANDIDATE)
    _need(not owner._failed and not owner._closed and owner._derived is not None
          and owner._prepared_dacl is not None)
    binding = _by_owner.get(owner)
    _need(binding is not None and binding[0] is lease and binding[1] == server._key)
    snapshot = owner._query(owner._derived)
    _need(snapshot == owner._restricted_snapshot)
    _need(owner._read_default_dacl() == owner._prepared_dacl)
    sid = snapshot[1]
    storage = _sid_buffer(sid)
    canonical = lease.fs.api.sid(C.addressof(storage))
    _need(canonical == lease.fs.api.user_sid())
    _need(type(canonical) is str and re.fullmatch(r'S-1-[0-9]+(?:-[0-9]+){1,15}', canonical) is not None)
    return sid, canonical


@_exclusive_entry
def _create(lease, server):
    _need(type(lease) is FixedDirectoryLease and type(lease.fs) is FixedWindowsFilesystem
          and type(lease.fs.api) is NativeFixedLeaseAPI and server._lease is lease)
    with server._owner._lock, server._lock:  # fixed lease -> token -> server order
        _need(lease not in _by_lease and server._owner not in _by_owner
              and not server._closed and not server.failed)
        lease._verify()
        key = _key_held(lease)
        _need(lease.record['phase'] == 'CLUSTER')
        _by_lease[lease] = server  # reserve one attempt before native actions
        _by_owner[server._owner] = (lease, key)
        server._key = key
        try:
            sid, canonical = _owner_sid_held(lease, server)
            server._name = _pipe_name(key[0], secrets.token_hex(16))
            server._create_native(canonical)
            server._verify_native(sid)
            lease._verify()
            _need(_key_held(lease) == key)
            server._ready = True
        except BaseException as error:
            phase, primary = server.phase, type(error).__name__
            server.failed = True
            try:
                server.close()  # never depends on a still-valid lease/token
            except BaseException:
                pass
            raise PipeFailure(phase, primary, server.cleanup_errors, server.winerror) from None


@_exclusive_operation
def _pwfile_name_held(lease, server, owner):
    _need(type(server) is _OwnedInitdbPipe and server._lease is lease
          and server._owner is owner and _by_lease.get(lease) is server)
    with owner._lock, server._lock:
        _need(server._ready and not server._closed and not server.failed)
        try:
            lease._verify()
            _need(_key_held(lease) == server._key and lease.record['phase'] == 'CLUSTER')
            sid, _ = _owner_sid_held(lease, server)
            server._verify_native(sid)
            lease._verify()
            return server._name  # only this registered object can supply a future command
        except BaseException as error:
            phase, primary = server.phase, type(error).__name__
            server.failed = True
            try:
                server.close()
            except BaseException:
                pass
            raise PipeFailure(phase, primary, server.cleanup_errors, server.winerror) from None


class _OwnedInitdbPipe:
    native_acceptance = False
    launch_ready = False
    client_authentication = 'NOT_IMPLEMENTED'
    metadata_readback = 'GET_NAMED_PIPE_INFO_NOT_OBSERVED'

    def __init__(self, lease, owner):
        _need(os.name == 'nt' and C.sizeof(C.c_void_p) == 8
              and type(lease) is FixedDirectoryLease and type(owner) is _RestrictedPrimaryCandidate)
        self._lease, self._owner, self._lock = lease, owner, RLock()
        self._kernel = C.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
        self._adv = C.WinDLL('advapi32.dll', use_last_error=True, winmode=0x800)
        pointer, dword, boolean = C.c_void_p, C.c_uint32, C.c_int32
        signatures = {
            'CreateNamedPipeW': ([C.c_wchar_p, dword, dword, dword, dword, dword, dword,
                                  C.POINTER(SecurityAttributes)], pointer),
            'GetFileType': ([pointer], dword),
            'GetHandleInformation': ([pointer, C.POINTER(dword)], boolean),
            'GetKernelObjectSecurity': ([pointer, dword, pointer, dword, C.POINTER(dword)], boolean),
            'IsValidSecurityDescriptor': ([pointer], boolean),
            'GetSecurityDescriptorLength': ([pointer], dword),
            'ConvertStringSecurityDescriptorToSecurityDescriptorW':
                ([C.c_wchar_p, dword, C.POINTER(pointer), C.POINTER(dword)], boolean),
            'LocalFree': ([pointer], pointer), 'CloseHandle': ([pointer], boolean),
        }
        for name, (arguments, result) in signatures.items():
            library = self._adv if name in ('GetKernelObjectSecurity', 'IsValidSecurityDescriptor',
                'GetSecurityDescriptorLength', 'ConvertStringSecurityDescriptorToSecurityDescriptorW') else self._kernel
            function = getattr(library, name)
            function.argtypes, function.restype = arguments, result
        self._handle = self._sd = self._name = self._key = None
        self._claimed_group = None
        self._ready = self._closed = self._sd_release_attempted = self.failed = False
        self.phase, self.winerror, self.cleanup_errors = 'NEW', None, []

    def __reduce__(self): raise TypeError('OWNED_PIPE_NOT_TRANSFERABLE')
    def __copy__(self): raise TypeError('OWNED_PIPE_NOT_TRANSFERABLE')
    def __deepcopy__(self, memo): raise TypeError('OWNED_PIPE_NOT_TRANSFERABLE')

    def _api(self, ok):
        if not ok:
            self.winerror = C.get_last_error()
            _need(False)

    def create(self):
        _create(self._lease, self)

    def _release_sd(self):
        if self._sd is not None and not self._sd_release_attempted:
            self._sd_release_attempted = True
            reported = False
            try:
                if self._kernel.LocalFree(self._sd):
                    self.cleanup_errors.append(('FREE_CREATION_SD', 'WIN32_RETURN', C.get_last_error()))
                    reported = True
                    _need(False)
            except BaseException as error:
                if not reported:
                    self.cleanup_errors.append(('FREE_CREATION_SD', type(error).__name__, None))
                raise
            self._sd = None

    def _create_native(self, canonical):
        self.phase = 'CREATE_SECURITY_DESCRIPTOR'
        sd, size = C.c_void_p(), C.c_uint32()
        ok = self._adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            'O:' + canonical + 'D:P(A;;GA;;;' + canonical + ')', 1, C.byref(sd), C.byref(size))
        if not ok:
            self.winerror = C.get_last_error()
        if ok and sd.value:
            self._sd = sd.value  # successful transfer, before later validation
        _need(ok and sd.value and 20 <= size.value <= 65536)
        attributes = SecurityAttributes(C.sizeof(SecurityAttributes), self._sd, 0)
        self.phase = 'CREATE_ORIGINAL_PIPE'
        handle = self._kernel.CreateNamedPipeW(self._name, 0x40080002, 0x8, 1,
                                                4096, 4096, 0, C.byref(attributes))
        if handle in (None, 0, (1 << 64) - 1):
            self.winerror = C.get_last_error()
            _need(False)
        self._handle = handle  # original returned server, before any verification
        self.phase = 'RELEASE_CREATION_SD'
        self._release_sd()

    def _verify_native(self, sid):
        self.phase = 'VERIFY_ORIGINAL_PIPE'
        _need(self._handle is not None and self._kernel.GetFileType(self._handle) == 3)
        flags = C.c_uint32()
        self._api(self._kernel.GetHandleInformation(self._handle, C.byref(flags)))
        _need(flags.value & 1 == 0)
        buffer, used = C.create_string_buffer(65536), C.c_uint32()
        self.phase = 'READ_PIPE_SECURITY'
        self._api(self._adv.GetKernelObjectSecurity(self._handle, 5, buffer,
                                                   C.sizeof(buffer), C.byref(used)))
        _need(20 <= used.value <= C.sizeof(buffer))
        raw = bytes(buffer[:used.value])
        _private_descriptor(raw, sid)  # all relative components bounded first
        _need(self._adv.IsValidSecurityDescriptor(buffer))  # no extended error
        _need(self._adv.GetSecurityDescriptorLength(buffer) == used.value)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed, self._ready = True, False
            if self._handle is not None:
                try:
                    if not self._kernel.CloseHandle(self._handle):
                        self.cleanup_errors.append(('CLOSE_PIPE', 'WIN32_FALSE', C.get_last_error()))
                except BaseException as error:
                    self.cleanup_errors.append(('CLOSE_PIPE', type(error).__name__, None))
            try:
                self._release_sd()
            except BaseException:
                pass
            if self.cleanup_errors:
                self.failed = True
                raise PipeFailure('CLOSE', None, self.cleanup_errors, self.winerror)
