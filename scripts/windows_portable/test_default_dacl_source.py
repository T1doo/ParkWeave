"""Owned ctypes buffers/source contracts; no Win32 calls or fake API results."""
import ast
import ctypes as C
from pathlib import Path
import struct
import unittest

from . import default_dacl_candidate as n


SID = b'\x01\x02' + b'\x00' * 5 + b'\x05' + struct.pack('<II', 32, 544)


class DefaultDaclSourceChecks(unittest.TestCase):
    def test_fixed_acl_storage_distinguishes_null_and_empty_acl(self):
        empty = struct.pack('<BBHHH', 2, 0, 8, 0, 0)
        buffer = n._acl_buffer(empty)
        self.assertEqual(C.sizeof(buffer), 65536)
        self.assertEqual(buffer.raw[:8], empty)
        self.assertEqual(buffer.raw[8:], b'\0' * (65536 - 8))
        for invalid in (None, b'', b'x' * 7, b'x' * 9, b'x' * 65536, bytearray(empty)):
            with self.assertRaises(n.DaclRefused): n._acl_buffer(invalid)

    def test_sid_owned_storage_and_exact_extent(self):
        buffer = n._sid_buffer(SID)
        self.assertEqual(C.sizeof(buffer), 68)
        self.assertEqual(buffer.raw[:len(SID)], SID)
        self.assertEqual(buffer.raw[len(SID):], b'\0' * (68 - len(SID)))
        for invalid in (None, SID[:-1], SID + b'\0'*4, b'\x02' + SID[1:],
                        b'\x01\x10' + SID[2:]):
            with self.assertRaises(n.DaclRefused): n._sid_buffer(invalid)

    def test_ace_bytes_preserve_opaque_payload_and_check_pointer_before_read(self):
        raw = struct.pack('<BBH', 0x42, 0x11, 12) + b'OPAQUE!!'
        buffer = C.create_string_buffer(65536)
        C.memmove(C.addressof(buffer) + 8, raw, len(raw))
        pointer = C.addressof(buffer) + 8
        self.assertEqual(n._ace_bytes(buffer, 20, pointer, 8), raw)
        for used, address, offset in ((19, pointer, 8), (20, pointer-1, 8),
                                      (20, pointer, 9), (20, pointer+65536, 8)):
            with self.assertRaises(n.DaclRefused): n._ace_bytes(buffer, used, address, offset)
        C.c_uint16.from_buffer(buffer, 10).value = 3
        with self.assertRaises(n.DaclRefused): n._ace_bytes(buffer, 20, pointer, 8)

    def test_source_has_only_memory_builder_no_mutation_activation(self):
        tree = ast.parse(Path(n.__file__).read_text())
        self.assertTrue(all(isinstance(x, (ast.Expr, ast.Import, ast.ImportFrom,
                                          ast.ClassDef, ast.FunctionDef)) for x in tree.body))
        attrs = {x.attr for x in ast.walk(tree) if isinstance(x, ast.Attribute)}
        self.assertFalse(attrs & {'SetTokenInformation', 'GetTokenInformation',
                                 'CreateProcessAsUserW', 'CreateJobObjectW'})
        with self.assertRaisesRegex(n.DaclRefused, 'NOT_ACCEPTED'):
            n.native_default_dacl()
        self.assertFalse(n._NativeDefaultDaclBuilder.launch_ready)
        self.assertFalse(n._NativeDefaultDaclBuilder.native_acceptance)
        self.assertEqual(C.sizeof(n.AclSize), 12)
        # Check the two fixed native operations, not simulated success results.
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                   and x.name == '_NativeDefaultDaclBuilder')
        build = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == 'build')
        calls = {x.func.attr: x for x in ast.walk(build) if isinstance(x, ast.Call)
                 and isinstance(x.func, ast.Attribute)}
        append = calls['AddAccessAllowedAceEx']
        self.assertEqual([append.args[i].value for i in (2, 3)], [1, 0x10000000])
        self.assertEqual(calls['AddAce'].args[2].value, 0xffffffff)


if __name__ == '__main__': unittest.main()
