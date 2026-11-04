"""Native implementation source candidate; importing never loads Windows DLLs.

The accepted factory in windows_user_protection remains closed. The explicit
native composition packages this implementation behind original gates. Constructing _NativeDPAPI
would load system DLLs; calling it would perform real current-user DPAPI work.
Neither is authorized by source-only checks. No file, ACL or token operation.

Python caller bytes and returned immutable bytes cannot be reliably erased.
Owned mutable input copies and validated native allocations are cleared here;
this is not protection against the same user, administrators or memory dumps.
"""
import ctypes as C
import os

from .credential_envelope import MAX_CIPHERTEXT, MAX_PLAINTEXT
from .windows_user_protection import (
    DataBlob, PROTECT_ARGTYPES, UNPROTECT_ARGTYPES, RESULT_TYPE,
    CRYPTPROTECT_UI_FORBIDDEN, ProtectionRefused,
)


class NativeFailure(ProtectionRefused):
    def __init__(self, phase, primary_type, cleanup_types, winerror=None):
        self.phase = phase
        self.primary_type = primary_type
        self.cleanup_types = tuple(cleanup_types)
        self.winerror = winerror
        self.outcome = 'UNKNOWN'
        super().__init__('NATIVE_DPAPI_UNKNOWN:'+phase)


class _InputBlob:
    """Own a real, bounded ctypes view over a mutable copy; erase once closed."""
    def __init__(self, data, limit):
        if type(data) is not bytes or not 0 < len(data) <= limit:
            raise ProtectionRefused('NATIVE_DPAPI_INPUT_REFUSED')
        self._data = bytearray(data)
        try:
            self._view = (C.c_ubyte * len(data)).from_buffer(self._data)
            self.blob = DataBlob(len(data), C.addressof(self._view))
        except BaseException:
            # Allocation/view setup failed before an owner can be returned.
            for index in range(len(self._data)):
                self._data[index] = 0
            raise
        self.closed = False

    def close(self):
        if not self.closed:
            C.memset(C.addressof(self._view), 0, len(self._data))
            self.blob.cbData = 0
            self.blob.pbData = None
            self.closed = True


class _NativeDPAPI:
    """Real Windows calls, deliberately unreachable from the accepted factory.

    No supplied DLL/callback/flags/description/DSN/path parameters are accepted.
    System32-only loading avoids current-directory DLL search. This is source
    preparation, not native acceptance or proof of the process SID/lease.
    """
    native_acceptance = False

    def __init__(self):
        if os.name != 'nt':
            raise ProtectionRefused('WINDOWS_REQUIRED')
        crypt = C.WinDLL('crypt32.dll', use_last_error=True, winmode=0x800)
        kernel = C.WinDLL('kernel32.dll', use_last_error=True, winmode=0x800)
        self._crypt, self._kernel = crypt, kernel
        self._protect = crypt.CryptProtectData
        self._protect.argtypes, self._protect.restype = PROTECT_ARGTYPES, RESULT_TYPE
        self._unprotect = crypt.CryptUnprotectData
        self._unprotect.argtypes, self._unprotect.restype = UNPROTECT_ARGTYPES, RESULT_TYPE
        self._size = kernel.LocalSize
        self._size.argtypes, self._size.restype = (C.c_void_p,), C.c_size_t
        self._free = kernel.LocalFree
        self._free.argtypes, self._free.restype = (C.c_void_p,), C.c_void_p
        self.failed = False
        self.unknown = []  # Original output/input storage; never retry an uncertain free.

    def protect(self, data, entropy):
        return self._call(True, data, entropy, MAX_PLAINTEXT, MAX_CIPHERTEXT)

    def unprotect(self, data, entropy):
        return self._call(False, data, entropy, MAX_CIPHERTEXT, MAX_PLAINTEXT)

    def _call(self, protect, data, entropy, input_limit, output_limit):
        if self.failed or type(entropy) is not bytes or len(entropy) != 32:
            raise ProtectionRefused('NATIVE_DPAPI_INPUT_REFUSED')
        source = _InputBlob(data, input_limit)
        extra = None
        output = DataBlob(0, None)
        phase = 'INPUT'
        primary = None
        cleanup = []
        result = None
        allocation_size = 0
        owned_output = False
        winerror = None
        try:
            extra = _InputBlob(entropy, 32)
            phase = 'CALL'
            function = self._protect if protect else self._unprotect
            # NULL description (including unprotect's optional output), reserved
            # and prompt; CURRENT_USER only, UI forbidden, never machine scope.
            ok = function(C.byref(source.blob), None, C.byref(extra.blob),
                          None, None, CRYPTPROTECT_UI_FORBIDDEN, C.byref(output))
            if not ok:
                winerror = C.get_last_error()  # before any cleanup/LocalSize call
            owned_output = bool(ok and output.pbData)
            phase = 'ALLOCATION'
            if owned_output:
                allocation_size = int(self._size(output.pbData))
            if not ok:
                raise ProtectionRefused('NATIVE_DPAPI_CALL_FAILED')
            if not output.pbData or not 0 < output.cbData <= output_limit:
                raise ProtectionRefused('NATIVE_DPAPI_OUTPUT_REFUSED')
            # Never read/clear an unvalidated output extent. LocalSize failure
            # or an excessive allocation produces UNKNOWN, not guessed bounds.
            if not output.cbData <= allocation_size <= MAX_CIPHERTEXT * 2:
                raise ProtectionRefused('NATIVE_DPAPI_ALLOCATION_REFUSED')
            phase = 'COPY'
            result = C.string_at(output.pbData, output.cbData)
        except BaseException as error:
            primary = type(error).__name__
        finally:
            if owned_output:
                try:
                    if not 0 < allocation_size <= MAX_CIPHERTEXT * 2:
                        raise ProtectionRefused('NATIVE_DPAPI_ERASURE_UNKNOWN')
                    C.memset(output.pbData, 0, allocation_size)
                except BaseException as error:
                    cleanup.append(type(error).__name__)
                try:
                    if self._free(output.pbData):
                        raise ProtectionRefused('NATIVE_DPAPI_FREE_UNKNOWN')
                    output.pbData = None
                    output.cbData = 0
                except BaseException as error:
                    cleanup.append(type(error).__name__)
            elif output.pbData:
                # Failure output integers have no documented ownership
                # transfer. Never inspect/erase/free an unknown allocation.
                cleanup.append('FAILED_OUTPUT_OWNERSHIP_UNKNOWN')
            for item in (extra, source):
                if item is not None:
                    try:
                        item.close()
                    except BaseException as error:
                        cleanup.append(type(error).__name__)
        if primary is not None or cleanup:
            self.failed = True
            if cleanup:
                # Keep the original DataBlob and mutable inputs alive. Neither
                # ownership nor successful erasure/free is inferred on failure.
                if not hasattr(self, 'unknown'): self.unknown = []
                self.unknown.append((output, source, extra, allocation_size))
            # Drop this frame's immutable copies before raising a diagnostic.
            # This cannot erase caller bytes or other debugger/traceback frames;
            # never persist frame locals as an installation failure report.
            result = None
            data = None
            entropy = None
            # Only types/numeric API error, no original exception/message.
            # No implicit retry or fallback.
            raise NativeFailure(phase, primary, cleanup, winerror) from None
        return result
