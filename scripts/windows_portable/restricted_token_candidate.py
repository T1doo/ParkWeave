"""Unwired token-derivation source candidate, not a restricted-launch authority.

No import-time DLL, DACL mutation, process/Job creation, environment or secret IO.
Calling derive on Windows WOULD create/query real tokens and needs separate
authorization. No caller can turn this result into PG_RESTRICT_EXEC permission.
REL_17_11/common/restricted_token.c provides the two deny-only group choices;
native acceptance, default DACL and actual process creation remain outstanding.
"""
import ctypes as C
import os
import struct


class TokenRefused(RuntimeError):
    pass


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

    def __init__(self):
        _need(os.name == 'nt')
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

    def derive(self):
        _need(not self._started and not self._closed and not self._failed)
        self._started = True
        base, derived = C.c_void_p(), C.c_void_p()
        try:
            self._phase = 'OPEN_CURRENT_PRIMARY'
            ok = self._adv.OpenProcessToken(self._kernel.GetCurrentProcess(),
                                            0x0008 | 0x0002, C.byref(base))
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
            _check(snapshots, self._query(derived), set(sids), (notify.low, notify.high))
            _need(self._query(base) == snapshots)
            self._derived = derived.value  # retained privately, never launch evidence
        except BaseException as error:
            primary_type = type(error).__name__
            self._failed = True
            cleanup_type = None
            try:
                self.close()
            except BaseException as cleanup_error:
                cleanup_type = type(cleanup_error).__name__
            raise TokenFailure(primary_type, cleanup_type, self._phase, self._winerror) from None

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
        if errors:
            self._failed = True
            raise TokenRefused('RESTRICTED_TOKEN_CLOSE_UNKNOWN')
