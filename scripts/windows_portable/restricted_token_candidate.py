"""Unwired token-derivation source candidate, not a restricted-launch authority.

No import-time DLL, process/Job creation, environment or secret IO.
Calling derive on Windows WOULD create/query real tokens and needs separate
authorization. prepare_default_dacl WOULD change only this owned derived token.
No caller can turn these observations into PG_RESTRICT_EXEC permission.
REL_17_11/common/restricted_token.c provides the two deny-only group choices;
native acceptance, default DACL and actual process creation remain outstanding.
"""
import ctypes as C
import os
import struct
from enum import Enum
from threading import RLock


class TokenRefused(RuntimeError):
    pass


class TokenProfile(Enum):
    DERIVE_ONLY = 0x000a
    CREATE_CANDIDATE = 0x008b


def _serialized(method):
    def held(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return held


class DefaultDacl(C.Structure):
    _fields_ = [('pointer', C.c_void_p)]


def _dacl_bytes(buffer, used):
    _need(type(used) is int and C.sizeof(DefaultDacl) <= used <= C.sizeof(buffer))
    pointer = DefaultDacl.from_buffer(buffer).pointer
    base = C.addressof(buffer)
    _need(type(pointer) is int and base + C.sizeof(DefaultDacl) <= pointer <= base + used - 8)
    offset = pointer - base
    _need(offset % 4 == 0)
    size = C.c_uint16.from_buffer(buffer, offset + 2).value
    _need(8 <= size <= 65532 and size % 4 == 0 and offset + size <= used)
    return bytes(buffer[offset:offset + size])


def _admit_default_dacl(raw, current_sid):
    """Narrow canonical subset, after the native builder validated the ACL."""
    _need(type(raw) is bytes and 8 <= len(raw) <= 65532 and len(raw) % 4 == 0)
    _need(type(current_sid) is bytes and 8 <= len(current_sid) <= 68
          and current_sid[0] == 1 and current_sid[1] <= 15
          and len(current_sid) == 8 + 4 * current_sid[1])
    nt_authority = b'\x00' * 5 + b'\x05'
    trusted = {current_sid, b'\x01\x01' + nt_authority + struct.pack('<I', 18),
               b'\x01\x02' + nt_authority + struct.pack('<II', 32, 544)}
    revision, zero1, size, count, zero2 = struct.unpack_from('<BBHHH', raw)
    _need(revision in (2, 4) and zero1 == zero2 == 0 and size == len(raw) and count <= 2048)
    offset, seen_allow = 8, False
    for _ in range(count):
        _need(offset + 16 <= len(raw))  # header + mask + minimum complete SID
        kind, flags, size = struct.unpack_from('<BBH', raw, offset)
        _need(kind in (0, 1) and flags & ~0x0f == 0)
        _need(size >= 16 and size % 4 == 0 and offset + size <= len(raw))
        _need(not (kind == 1 and seen_allow))
        seen_allow = seen_allow or kind == 0
        sid = raw[offset + 8:offset + size]
        _need(sid[0] == 1 and sid[1] <= 15 and len(sid) == 8 + 4 * sid[1])
        _need(kind == 1 or sid in trusted)  # never preserve an unknown allow
        offset += size
    _need(offset <= len(raw))  # remaining free space belongs to the original ACL


class TokenFailure(TokenRefused):
    def __init__(self, primary_type, cleanup_type, phase, winerror):
        self.primary_type, self.cleanup_type = primary_type, cleanup_type
        self.phase, self.winerror = phase, winerror
        self.outcome = 'UNKNOWN'
        super().__init__('RESTRICTED_TOKEN_DERIVATION_UNKNOWN')


class SidAttributes(C.Structure):
    _fields_ = [('sid', C.c_void_p), ('attributes', C.c_uint32)]


class GroupLayout(C.Structure):
    _fields_ = [('count', C.c_uint32), ('groups', SidAttributes * 1)]


class Luid(C.Structure):
    _fields_ = [('low', C.c_uint32), ('high', C.c_int32)]


class Privilege(C.Structure):
    _fields_ = [('luid', Luid), ('attributes', C.c_uint32)]


def _need(ok):
    if not ok:
        raise TokenRefused('RESTRICTED_TOKEN_CANDIDATE_REFUSED')


def _sid(buffer, length, pointer, minimum):
    """Parse only a SID fully inside this actual GetTokenInformation buffer."""
    base = C.addressof(buffer)
    _need(type(length) is int and 0 < length <= C.sizeof(buffer))
    _need(type(pointer) is int and base + minimum <= pointer <= base + length - 8)
    offset = pointer - base
    header = bytes(buffer[offset:offset + 8])
    _need(header[0] == 1 and header[1] <= 15)
    size = 8 + 4 * header[1]
    _need(offset + size <= length)
    return bytes(buffer[offset:offset + size])


def _parse(buffer, length, kind):
    _need(type(length) is int and 0 < length <= C.sizeof(buffer))
    if kind == 8:  # TokenType
        _need(length == 4)
        return C.c_uint32.from_buffer(buffer).value
    if kind == 1:  # TOKEN_USER
        _need(length >= C.sizeof(SidAttributes))
        row = SidAttributes.from_buffer(buffer)
        return _sid(buffer, length, row.sid, C.sizeof(SidAttributes))
    if kind == 4:  # TOKEN_OWNER, distinct from TOKEN_USER.
        _need(length >= C.sizeof(C.c_void_p))
        pointer = C.c_void_p.from_buffer(buffer).value
        return _sid(buffer, length, pointer, C.sizeof(C.c_void_p))
    _need(kind in (2, 3) and length >= 4)
    count = C.c_uint32.from_buffer(buffer).value
    offset, row_type = ((GroupLayout.groups.offset, SidAttributes) if kind == 2
                        else (4, Privilege))
    _need(count <= 2048 and offset + count * C.sizeof(row_type) <= length)
    rows = {}
    for index in range(count):
        row = row_type.from_buffer(buffer, offset + index * C.sizeof(row_type))
        key = (_sid(buffer, length, row.sid, offset + count * C.sizeof(row_type)) if kind == 2 else
               (row.luid.low, row.luid.high))
        _need(key not in rows)
        rows[key] = row.attributes
    return rows


def _check(base, derived, disabled_sids, change_notify):
    """Observation comparison only; dictionaries are never a native capability."""
    _need(base[8] == derived[8] == 1 and base[1] == derived[1])
    _need(set(base[2]) == set(derived[2]))
    for sid, attributes in base[2].items():
        expected = (attributes | 0x10) & ~0x6 if sid in disabled_sids else attributes
        _need(derived[2][sid] == expected)
    _need(set(derived[3]) <= set(base[3]))
    for luid, attributes in derived[3].items():
        # Documented lower bound: all non-change-notify privileges disabled.
        # Do not assume disabled entries must have been removed entirely.
        _need(not attributes & 0x2 or luid == change_notify)
        _need(not attributes & 0x2 or base[3][luid] & 0x2)


def native_restricted_process():
    raise TokenRefused('NATIVE_RESTRICTED_PROCESS_NOT_ACCEPTED')


class _RestrictedPrimaryCandidate:
    native_acceptance = False
    launch_ready = False

    def __init__(self, profile=TokenProfile.DERIVE_ONLY):
        _need(type(profile) is TokenProfile and os.name == 'nt' and C.sizeof(C.c_void_p) == 8)
        self._profile, self._lock = profile, RLock()
        self._adv = C.WinDLL('advapi32.dll', use_last_error=True, winmode=0x800)
        self._kernel = C.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
        handle, dword, boolean = C.c_void_p, C.c_uint32, C.c_int32
        declarations = {
            'OpenProcessToken': ([handle, dword, C.POINTER(handle)], boolean),
            'CreateRestrictedToken': ([handle, dword, dword, C.POINTER(SidAttributes),
                dword, C.c_void_p, dword, C.c_void_p, C.POINTER(handle)], boolean),
            'GetTokenInformation': ([handle, C.c_int32, C.c_void_p, dword,
                                     C.POINTER(dword)], boolean),
            'LookupPrivilegeValueW': ([C.c_wchar_p, C.c_wchar_p, C.POINTER(Luid)], boolean),
            'SetTokenInformation': ([handle, C.c_int32, C.c_void_p, dword], boolean),
        }
        for name, (arguments, result) in declarations.items():
            fn = getattr(self._adv, name)
            fn.argtypes, fn.restype = arguments, result
        self._kernel.GetCurrentProcess.argtypes = []
        self._kernel.GetCurrentProcess.restype = handle
        self._kernel.CloseHandle.argtypes = [handle]
        self._kernel.CloseHandle.restype = boolean
        self._handles = []
        self._started = self._failed = self._closed = False
        self._derived = None
        self._phase, self._winerror = 'NEW', None
        self._restricted_snapshot = self._prepared_dacl = None
        self._dacl_attempted = False
        self._owner_attempted, self._prepared_owner = False, None

    def _api(self, ok):
        if not ok:
            self._winerror = C.get_last_error()
            _need(False)

    def _query(self, token):
        result = {}
        for kind in (8, 1, 2, 3):
            # Fixed bounded buffer: no retry/resize based on untrusted lengths.
            buffer = C.create_string_buffer(65536)
            used = C.c_uint32()
            self._phase = 'QUERY_' + str(kind)
            self._api(self._adv.GetTokenInformation(token, kind, buffer,
                                                   C.sizeof(buffer), C.byref(used)))
            result[kind] = _parse(buffer, used.value, kind)
        return result

    @_serialized
    def derive(self):
        _need(not self._started and not self._closed and not self._failed)
        self._started = True
        base, derived = C.c_void_p(), C.c_void_p()
        try:
            self._phase = 'OPEN_CURRENT_PRIMARY'
            ok = self._adv.OpenProcessToken(self._kernel.GetCurrentProcess(),
                                            self._profile.value, C.byref(base))
            if not ok:
                self._winerror = C.get_last_error()
            if ok and base.value:
                self._handles.append(base.value)  # successful transfer, before queries
            _need(ok and base.value)
            snapshots = self._query(base)
            # Binary S-1-5-32-544 and S-1-5-32-547; no SID allocator to release.
            sids = [b'\x01\x02' + b'\x00' * 5 + b'\x05' + struct.pack('<II', 32, rid)
                    for rid in (544, 547)]
            storage = [C.create_string_buffer(sid, len(sid)) for sid in sids]
            groups = (SidAttributes * 2)(*(SidAttributes(C.addressof(x), 0) for x in storage))
            self._phase = 'DERIVE'
            ok = self._adv.CreateRestrictedToken(base, 1, 2, groups,
                                                 0, None, 0, None, C.byref(derived))
            if not ok:
                self._winerror = C.get_last_error()
            if ok and derived.value and derived.value != base.value:
                self._handles.append(derived.value)
            _need(ok and derived.value and derived.value != base.value)
            notify = Luid()
            self._phase = 'LOOKUP_CHANGE_NOTIFY'
            self._api(self._adv.LookupPrivilegeValueW(None, 'SeChangeNotifyPrivilege', C.byref(notify)))
            restricted = self._query(derived)
            _check(snapshots, restricted, set(sids), (notify.low, notify.high))
            _need(self._query(base) == snapshots)
            self._derived = derived.value  # retained privately, never launch evidence
            self._restricted_snapshot = restricted
        except BaseException as error:
            primary_type = type(error).__name__
            self._failed = True
            cleanup_type = None
            try:
                self.close()
            except BaseException as cleanup_error:
                cleanup_type = type(cleanup_error).__name__
            raise TokenFailure(primary_type, cleanup_type, self._phase, self._winerror) from None

    def _read_default_dacl(self):
        buffer, used = C.create_string_buffer(65536), C.c_uint32()
        self._phase = 'QUERY_DEFAULT_DACL'
        self._api(self._adv.GetTokenInformation(self._derived, 6, buffer,
                                               C.sizeof(buffer), C.byref(used)))
        return _dacl_bytes(buffer, used.value)

    def _read_owner(self, token=None):
        buffer, used = C.create_string_buffer(4096), C.c_uint32()
        self._phase = 'QUERY_TOKEN_OWNER'
        self._api(self._adv.GetTokenInformation(self._derived if token is None else token,
            4, buffer, C.sizeof(buffer), C.byref(used)))
        return _parse(buffer, used.value, 4)

    @_serialized
    def prepare_owner(self):
        """Source-only owned derived token setter; no factory invokes it."""
        _need(self._profile is TokenProfile.CREATE_CANDIDATE and self._derived is not None
              and not self._failed and not self._closed and not self._owner_attempted)
        self._owner_attempted = True
        try:
            current = self._query(self._derived)
            _need(current == self._restricted_snapshot)
            original = self._read_owner()
            from .default_dacl_candidate import _sid_buffer
            storage = _sid_buffer(current[1])
            value = C.c_void_p(C.addressof(storage))  # TOKEN_OWNER is one PSID.
            _need(self._read_owner() == original and self._query(self._derived) == current)
            self._phase = 'SET_OWNED_DERIVED_TOKEN_OWNER'
            self._api(self._adv.SetTokenInformation(self._derived, 4, C.byref(value), C.sizeof(value)))
            _need(self._read_owner() == current[1] and self._query(self._derived) == current)
            self._prepared_owner = current[1]
        except BaseException as error:
            primary_type, phase, winerror = type(error).__name__, self._phase, self._winerror
            self._failed = True
            cleanup_type = None
            try: self.close()
            except BaseException as cleanup_error: cleanup_type = type(cleanup_error).__name__
            raise TokenFailure(primary_type, cleanup_type, phase, winerror) from None

    @_serialized
    def prepare_default_dacl(self):
        """Serialize this owner; repeated reads are not an OS atomic CAS."""
        _need(self._profile is TokenProfile.CREATE_CANDIDATE and self._derived is not None
              and not self._failed and not self._closed and not self._dacl_attempted)
        self._dacl_attempted = True  # never retry an uncertain setter
        try:
            current = self._query(self._derived)
            _need(current == self._restricted_snapshot)
            original = self._read_default_dacl()
            from .default_dacl_candidate import _NativeDefaultDaclBuilder
            candidate = _NativeDefaultDaclBuilder().build(original, current[1])
            self._phase = 'ADMIT_DEFAULT_DACL_SUBSET'
            _admit_default_dacl(original, current[1])
            _need(self._read_default_dacl() == original)
            _need(self._query(self._derived) == current)
            allocation = C.create_string_buffer(candidate, len(candidate))
            value = DefaultDacl(C.addressof(allocation))
            self._phase = 'SET_OWNED_DERIVED_DEFAULT_DACL'
            self._api(self._adv.SetTokenInformation(self._derived, 6,
                                                   C.byref(value), C.sizeof(value)))
            _need(self._read_default_dacl() == candidate)
            _need(self._query(self._derived) == current)
            self._prepared_dacl = candidate  # private observation, not authority
        except BaseException as error:
            primary_type, phase, winerror = type(error).__name__, self._phase, self._winerror
            self._failed = True
            cleanup_type = None
            try:
                self.close()
            except BaseException as cleanup_error:
                cleanup_type = type(cleanup_error).__name__
            raise TokenFailure(primary_type, cleanup_type, phase, winerror) from None

    @_serialized
    def close(self):
        if self._closed:
            return
        self._closed = True
        errors = 0
        # Attempt each original handle once; never reopen by PID or retry close.
        for handle in reversed(self._handles):
            try:
                if not self._kernel.CloseHandle(handle):
                    errors += 1
            except BaseException:
                errors += 1
        self._derived = None
        self._prepared_owner = None
        self._prepared_dacl = self._restricted_snapshot = None
        if errors:
            self._failed = True
            raise TokenRefused('RESTRICTED_TOKEN_CLOSE_UNKNOWN')
