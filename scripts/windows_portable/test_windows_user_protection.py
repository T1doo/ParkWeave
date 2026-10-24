"""Fake allocations/address tokens only; no real DPAPI, pointers or credentials."""
import ctypes as C
import importlib.util
import json
import sys
import traceback
import unittest
from unittest.mock import patch

from . import credential_envelope as e
from . import windows_user_protection as w
from .test_credential_envelope import binding, payloads


SENTINEL = 'SYNTHETIC_ERROR_CONTENT_MUST_NOT_APPEAR_IN_REPORTS'


class Buffers(w.FakeAPI):
    def __init__(self, **changes):
        self.changes = changes; self.buffers = {}; self.calls = []; self.events = []

    def invoke(self, operation, data, entropy, *, flags, reserved, prompt):
        self.calls.append((operation, flags, reserved, prompt, len(entropy)))
        if self.changes.get('call_error'): raise RuntimeError(SENTINEL)
        raw = b'FAKE_ONLY:'+data if operation == 'protect' else data[len(b'FAKE_ONLY:'):]
        raw = self.changes.get('output', raw)
        self.buffers[101] = bytearray(raw)
        return w.FakeResult(self.changes.get('ok', True), self.changes.get('length', len(raw)), self.changes.get('pointer', 101))

    def owns(self, pointer): return pointer in self.buffers

    def read(self, pointer, length):
        self.events.append('read')
        if self.changes.get('read_error'): raise RuntimeError(SENTINEL)
        return bytes(self.buffers[pointer][:length])

    def zero(self, pointer):
        self.events.append('zero'); self.buffers[pointer][:] = b'\0'*len(self.buffers[pointer])
        if self.changes.get('zero_error'): raise OSError(SENTINEL)
        return not self.changes.get('zero_unknown', False)

    def free(self, pointer):
        self.events.append('free'); del self.buffers[pointer]
        if self.changes.get('free_error'): raise ValueError(SENTINEL)
        return not self.changes.get('free_unknown', False)


class ProtectionChecks(unittest.TestCase):
    def test_no_import_time_loader_native_entry_stays_closed_and_blob_layout(self):
        spec = importlib.util.spec_from_file_location('scripts.windows_portable._user_protection_abi_probe', w.__file__)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {spec.name: module}), patch.object(C, 'WinDLL', create=True, side_effect=AssertionError('no native loader')), patch.object(C, 'CDLL', side_effect=AssertionError('no native loader')):
            spec.loader.exec_module(module)
            with self.assertRaisesRegex(module.ProtectionRefused, 'NATIVE_CURRENT_USER_PROTECTION_NOT_ACCEPTED'):
                module.native_user_protection()
        self.assertEqual(w.DataBlob.cbData.offset, 0)
        self.assertEqual(w.DataBlob.pbData.offset, C.sizeof(C.c_void_p))
        self.assertEqual(C.sizeof(w.DataBlob), 2*C.sizeof(C.c_void_p))
        self.assertEqual(len(w.PROTECT_ARGTYPES), 7)
        self.assertEqual(len(w.UNPROTECT_ARGTYPES), 7)
        self.assertIs(w.PROTECT_ARGTYPES[1], C.c_wchar_p)
        self.assertIs(w.UNPROTECT_ARGTYPES[1], C.POINTER(C.c_wchar_p))
        self.assertEqual(C.sizeof(w.RESULT_TYPE), 4)
        with self.assertRaises(w.ProtectionRefused): w.IsolatedUserProtection(None)

    def test_explicit_fake_roundtrip_flags_no_prompts_and_cleanup(self):
        api = Buffers(); adapter = w.IsolatedUserProtection(api); b = binding(); purpose = e.Purpose.DATABASE
        raw = e.encode_plaintext(b, purpose, payloads()[purpose]); entropy = e.entropy_bytes(b, purpose)
        fake_cipher = adapter.protect(raw, entropy)
        self.assertEqual(e.decode_plaintext(b, purpose, adapter.unprotect(fake_cipher, entropy)), payloads()[purpose])
        self.assertEqual(api.events, ['read', 'zero', 'free']*2)
        self.assertFalse(api.buffers)
        self.assertTrue(adapter.fixture_only); self.assertFalse(adapter.native_acceptance)
        self.assertEqual(api.calls, [('protect', 1, None, None, 32), ('unprotect', 1, None, None, 32)])
        self.assertFalse(any(flags & w.CRYPTPROTECT_LOCAL_MACHINE for _, flags, _, _, _ in api.calls))

    def test_input_limits_refuse_before_api(self):
        api = Buffers(); adapter = w.IsolatedUserProtection(api)
        for data, entropy in ((b'', b'e'*32), (b'x'*(e.MAX_PLAINTEXT+1), b'e'*32), (bytearray(b'x'), b'e'*32), (b'x', b'e'*31)):
            with self.subTest(input_refusal=True), self.assertRaises(w.ProtectionRefused): adapter.protect(data, entropy)
        with self.assertRaises(w.ProtectionRefused): adapter.unprotect(b'x'*(e.MAX_CIPHERTEXT+1), b'e'*32)
        self.assertFalse(api.calls)

    def test_invalid_pointer_never_dereferenced_or_freed(self):
        for pointer in (0, -1, True, '101', 2**(8*C.sizeof(C.c_void_p)), 999):
            api = Buffers(pointer=pointer); adapter = w.IsolatedUserProtection(api)
            with self.subTest(pointer_invalid=True), self.assertRaises(w.ProtectionFailure): adapter.protect(b'SYNTHETIC', b'e'*32)
            self.assertEqual(api.events, [])
            self.assertTrue(adapter.failed)  # Unknown token is never guessed or retried.

    def test_allocated_failure_or_invalid_length_still_zero_and_free(self):
        for changes in (dict(ok=False), dict(ok=1), dict(length=0), dict(length=True), dict(length=-1),
                        dict(length=e.MAX_CIPHERTEXT+1), dict(length=100)):
            api = Buffers(**changes); adapter = w.IsolatedUserProtection(api)
            with self.subTest(output_refusal=True), self.assertRaises(w.ProtectionFailure): adapter.protect(b'SYNTHETIC', b'e'*32)
            self.assertEqual(api.events[-2:], ['zero', 'free'])
            self.assertFalse(api.buffers)

    def test_primary_and_both_cleanup_errors_retained_without_secret_output(self):
        api = Buffers(read_error=True, zero_error=True, free_error=True); adapter = w.IsolatedUserProtection(api)
        with self.assertRaises(w.ProtectionFailure) as raised: adapter.protect(b'SYNTHETIC', b'e'*32)
        failure = raised.exception
        self.assertIsInstance(failure.primary, RuntimeError)
        self.assertEqual([type(x) for x in failure.cleanup], [OSError, ValueError])
        public = str(failure)+repr(failure)+json.dumps(failure.public())+''.join(traceback.format_exception(failure))
        self.assertNotIn(SENTINEL, public)
        self.assertEqual(api.events, ['read', 'zero', 'free'])
        with self.assertRaises(w.ProtectionRefused): adapter.protect(b'SYNTHETIC', b'e'*32)
        self.assertEqual(len(api.calls), 1)

    def test_call_error_and_cleanup_false_are_sticky_unknown(self):
        for changes in (dict(call_error=True), dict(zero_unknown=True), dict(free_unknown=True)):
            api = Buffers(**changes); adapter = w.IsolatedUserProtection(api)
            with self.subTest(unknown=True), self.assertRaises(w.ProtectionFailure): adapter.protect(b'SYNTHETIC', b'e'*32)
            self.assertTrue(adapter.failed)
            self.assertFalse(api.buffers)
            if not changes.get('call_error'): self.assertEqual(api.events[-2:], ['zero', 'free'])

    def test_successful_api_corrupt_output_still_rejected_by_application_envelope(self):
        b = binding(); purpose = e.Purpose.DATABASE
        damaged = json.loads(e.encode_plaintext(b, purpose, payloads()[purpose]))
        damaged['payload']['postgres'] += '_DAMAGED'
        api = Buffers(output=e.canonical(damaged)); adapter = w.IsolatedUserProtection(api)
        raw = adapter.unprotect(b'FAKE_ONLY:SYNTHETIC', e.entropy_bytes(b, purpose))
        with self.assertRaises(e.EnvelopeRefused): e.decode_plaintext(b, purpose, raw)
        self.assertFalse(api.buffers)


if __name__ == '__main__':
    unittest.main()
