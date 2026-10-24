"""Fake-API/ABI contract only. No DLL loading, DPAPI, file IO or native default.

IsolatedUserProtection outputs are fixture bytes, never accepted native evidence.
The production entry remains unconditionally refused, including on Windows.
"""
from abc import ABC, abstractmethod
import ctypes as C
from dataclasses import dataclass

from .credential_envelope import MAX_CIPHERTEXT, MAX_PLAINTEXT


CRYPTPROTECT_UI_FORBIDDEN = 1
CRYPTPROTECT_LOCAL_MACHINE = 4  # Documented forbidden flag, never sent.


class DataBlob(C.Structure):
    _fields_ = [('cbData', C.c_uint32), ('pbData', C.c_void_p)]


# Signatures are data for review only; no DLL, callable or native binding is made.
PROTECT_ARGTYPES = (C.POINTER(DataBlob), C.c_wchar_p, C.POINTER(DataBlob),
                    C.c_void_p, C.c_void_p, C.c_uint32, C.POINTER(DataBlob))
UNPROTECT_ARGTYPES = (C.POINTER(DataBlob), C.POINTER(C.c_wchar_p), C.POINTER(DataBlob),
                      C.c_void_p, C.c_void_p, C.c_uint32, C.POINTER(DataBlob))
RESULT_TYPE = C.c_int32  # Win32 BOOL, not Python truthiness or C long width.


@dataclass(frozen=True, repr=False)
class FakeResult:
    ok: bool
    length: int
    pointer: int


class FakeAPI(ABC):
    """Explicit trusted fault-injection seam; no fallback or native adapter.

    The fake owns allocations before returning a result, including error
    results. owns() must recognize its own address tokens without dereferencing
    unknown pointers. read/zero/free operate only on such recognized tokens.
    zero/free must return exactly True. If invoke raises before returning an
    allocation token, its own partial-allocation cleanup remains its duty.
    """
    @abstractmethod
    def invoke(self, operation, data, entropy, *, flags, reserved, prompt): ...
    @abstractmethod
    def owns(self, pointer): ...
    @abstractmethod
    def read(self, pointer, length): ...
    @abstractmethod
    def zero(self, pointer): ...
    @abstractmethod
    def free(self, pointer): ...


class ProtectionRefused(RuntimeError):
    pass


class ProtectionFailure(ProtectionRefused):
    def __init__(self, phase, primary, cleanup):
        self.phase, self.primary, self.cleanup = phase, primary, tuple(cleanup)
        self.outcome = 'UNKNOWN'
        super().__init__('ISOLATED_USER_PROTECTION_FAILED:'+phase)

    def public(self):
        return dict(phase=self.phase, outcome=self.outcome,
                    primary_type=type(self.primary).__name__,
                    cleanup_types=[type(e).__name__ for e in self.cleanup])


def native_user_protection():
    raise ProtectionRefused('NATIVE_CURRENT_USER_PROTECTION_NOT_ACCEPTED')


class IsolatedUserProtection:
    """Sticky failure is per fake adapter, not a persistent installation state."""
    fixture_only = True
    native_acceptance = False

    def __init__(self, api):
        if not isinstance(api, FakeAPI):
            raise ProtectionRefused('EXPLICIT_FAKE_API_REQUIRED')
        self.api, self.failed = api, False

    def protect(self, data, entropy):
        return self._invoke('protect', data, entropy, MAX_PLAINTEXT, MAX_CIPHERTEXT)

    def unprotect(self, data, entropy):
        return self._invoke('unprotect', data, entropy, MAX_CIPHERTEXT, MAX_PLAINTEXT)

    def _invoke(self, operation, data, entropy, input_limit, output_limit):
        if self.failed or type(data) is not bytes or not 0 < len(data) <= input_limit or type(entropy) is not bytes or len(entropy) != 32:
            raise ProtectionRefused('ISOLATED_PROTECTION_INPUT_REFUSED')
        result = None; owned = False; output = None; primary = None; cleanup = []; phase = 'CALL'
        try:
            result = self.api.invoke(operation, data, entropy, flags=CRYPTPROTECT_UI_FORBIDDEN, reserved=None, prompt=None)
            phase = 'RESULT'
            if type(result) is not FakeResult or type(result.pointer) is not int or not 0 < result.pointer < 2**(8*C.sizeof(C.c_void_p)):
                raise ProtectionRefused('INVALID_FAKE_OUTPUT_POINTER')
            # Establish allocation ownership before validating length/success so
            # an allocated failure or bad count still gets both cleanup calls.
            owned = self.api.owns(result.pointer) is True
            if not owned:
                raise ProtectionRefused('UNKNOWN_FAKE_OUTPUT_POINTER')
            if type(result.ok) is not bool or not result.ok or type(result.length) is not int or not 0 < result.length <= output_limit:
                raise ProtectionRefused('INVALID_FAKE_OUTPUT_RESULT')
            phase = 'COPY'
            output = self.api.read(result.pointer, result.length)
            if type(output) is not bytes or len(output) != result.length:
                raise ProtectionRefused('INVALID_FAKE_OUTPUT_COPY')
        except BaseException as error:
            primary = error
        finally:
            if owned:
                for action in (self.api.zero, self.api.free):
                    try:
                        if action(result.pointer) is not True:
                            raise ProtectionRefused('FAKE_OUTPUT_CLEANUP_UNKNOWN')
                    except BaseException as error: cleanup.append(error)
        if primary is not None or cleanup:
            self.failed = True
            raise ProtectionFailure(phase, primary, cleanup) from None
        return output
