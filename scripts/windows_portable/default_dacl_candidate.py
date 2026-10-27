"""Unwired native ACL memory builder, never a TokenDefaultDacl setter.

Inputs/output are data, not token/user/lease identity or authorization evidence.
No import-time DLL load. No Token/ACL setter, process, environment or file IO.
The original ACE order is preserved, not canonicalized: appending an explicit
allow after inherited entries may be noncanonical and does not prove access.
The future setter must resolve applicability separately. Native NOT_RUN.
"""
import ctypes as C
import os
import struct


class DaclRefused(RuntimeError):
    pass


class DaclFailure(DaclRefused):
    def __init__(self, phase, error_type, winerror):
        self.phase, self.error_type, self.winerror = phase, error_type, winerror
        self.outcome = 'UNKNOWN'
        super().__init__('DEFAULT_DACL_CANDIDATE_UNKNOWN:'+phase)


class AclSize(C.Structure):
    _fields_ = [('count', C.c_uint32), ('used', C.c_uint32), ('free', C.c_uint32)]


def _need(ok):
    if not ok:
        raise DaclRefused('DEFAULT_DACL_CANDIDATE_REFUSED')


def _acl_buffer(data):
    # NULL is not an empty ACL. Fixed allocation bounds even a corrupt WORD
    # AclSize before native validation; no guessing an unowned pointer extent.
    _need(type(data) is bytes and 8 <= len(data) <= 65532 and len(data) % 4 == 0)
    buffer = C.create_string_buffer(65536)
    C.memmove(buffer, data, len(data))
    return buffer


def _sid_buffer(data):
    _need(type(data) is bytes and 8 <= len(data) <= 68)
    _need(data[0] == 1 and data[1] <= 15 and len(data) == 8 + 4 * data[1])
    buffer = C.create_string_buffer(68)
    C.memmove(buffer, data, len(data))
    return buffer


def _ace_bytes(buffer, used, pointer, expected_offset):
    base = C.addressof(buffer)
    _need(type(used) is int and 8 <= used <= C.sizeof(buffer))
    _need(type(pointer) is int and pointer == base + expected_offset)
    _need(expected_offset >= 8 and expected_offset % 4 == 0 and expected_offset + 4 <= used)
    size = C.c_uint16.from_buffer(buffer, expected_offset + 2).value
    _need(size >= 4 and size % 4 == 0 and expected_offset + size <= used)
    return bytes(buffer[expected_offset:expected_offset + size])


def native_default_dacl():
    raise DaclRefused('NATIVE_DEFAULT_DACL_NOT_ACCEPTED')


class _NativeDefaultDaclBuilder:
    native_acceptance = False
    launch_ready = False

    def __init__(self):
        _need(os.name == 'nt')
        self._adv = C.WinDLL('advapi32.dll', use_last_error=True, winmode=0x800)
        pointer, dword, boolean = C.c_void_p, C.c_uint32, C.c_int32
        signatures = {
            'IsValidAcl': ([pointer], boolean),
            'IsValidSid': ([pointer], boolean),
            'GetLengthSid': ([pointer], dword),
            'GetAclInformation': ([pointer, pointer, dword, C.c_int32], boolean),
            'GetAce': ([pointer, dword, C.POINTER(pointer)], boolean),
            'InitializeAcl': ([pointer, dword, dword], boolean),
            'AddAce': ([pointer, dword, dword, pointer, dword], boolean),
            'AddAccessAllowedAceEx': ([pointer, dword, dword, dword, pointer], boolean),
        }
        for name, (arguments, result) in signatures.items():
            fn = getattr(self._adv, name)
            fn.argtypes, fn.restype = arguments, result
        self.failed = False
        self._phase, self._winerror = 'NEW', None

    def _api(self, ok):
        if not ok:
            self._winerror = C.get_last_error()
            _need(False)

    def _observe(self, buffer, length):
        _need(8 <= length <= 65532 and length % 4 == 0)
        self._phase = 'VALIDATE_ACL'
        # IsValidAcl has no documented extended error; do not read stale errno.
        _need(self._adv.IsValidAcl(buffer))
        revision, size = C.c_uint32(), AclSize()
        self._phase = 'ACL_REVISION'
        self._api(self._adv.GetAclInformation(buffer, C.byref(revision), C.sizeof(revision), 1))
        self._phase = 'ACL_SIZE'
        self._api(self._adv.GetAclInformation(buffer, C.byref(size), C.sizeof(size), 2))
        _need(revision.value in (2, 4) and size.count <= 2048)
        _need(8 <= size.used <= length and size.used % 4 == 0 and size.used + size.free == length)
        rows, offset = [], 8
        for index in range(size.count):
            pointer = C.c_void_p()
            self._phase = 'GET_ACE'
            self._api(self._adv.GetAce(buffer, index, C.byref(pointer)))
            raw = _ace_bytes(buffer, size.used, pointer.value, offset)
            rows.append(raw)
            offset += len(raw)
        _need(offset == size.used)
        return revision.value, size.used, rows

    def build(self, original, user_sid):
        _need(not self.failed)
        self._phase, self._winerror = 'INPUT', None
        try:
            old, sid = _acl_buffer(original), _sid_buffer(user_sid)
            self._phase = 'VALIDATE_SID'
            _need(self._adv.IsValidSid(sid))  # no documented extended error
            _need(self._adv.GetLengthSid(sid) == len(user_sid))
            revision, used, rows = self._observe(old, len(original))
            extra_size = 8 + len(user_sid)
            total = used + extra_size
            _need(total <= 65532 and len(rows) < 2048)
            output = C.create_string_buffer(65536)
            self._phase = 'INITIALIZE_ACL'
            self._api(self._adv.InitializeAcl(output, total, revision))
            if rows:
                self._phase = 'COPY_EXISTING_ACES'
                self._api(self._adv.AddAce(output, revision, 0xffffffff,
                                           C.c_void_p(C.addressof(old) + 8), used - 8))
            self._phase = 'APPEND_CURRENT_USER'
            self._api(self._adv.AddAccessAllowedAceEx(output, revision, 1, 0x10000000, sid))
            actual_revision, actual_used, actual_rows = self._observe(output, total)
            expected = struct.pack('<BBHI', 0, 1, extra_size, 0x10000000) + user_sid
            _need(actual_revision == revision and actual_used == total)
            _need(actual_rows == rows + [expected])
            return bytes(output[:total])
        except BaseException as error:
            self.failed = True
            error_type = type(error).__name__
        # No original exception/messages, pointers or ACL/SID in public fields.
        # Traceback locals remain private diagnostic material, not export data.
        raise DaclFailure(self._phase, error_type, self._winerror) from None
