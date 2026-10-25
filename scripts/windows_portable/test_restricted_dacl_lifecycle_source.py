"""Memory and admission/source checks only, never native Token/DACL operations."""
import ast
import ctypes as C
from pathlib import Path
import struct
import unittest

from . import restricted_token_candidate as n


SID = b'\x01\x02' + b'\x00'*5 + b'\x05' + struct.pack('<II', 32, 544)


def ace(kind=0, flags=0, sid=SID):
    return struct.pack('<BBHI', kind, flags, 8 + len(sid), 0x10000000) + sid


def acl(*rows):
    return struct.pack('<BBHHH', 2, 0, 8+sum(map(len, rows)), len(rows), 0) + b''.join(rows)


class RestrictedDaclLifecycleSourceChecks(unittest.TestCase):
    def test_owned_query_buffer_null_outside_and_size_refusals(self):
        raw = acl(ace())
        offset = C.sizeof(n.DefaultDacl)
        buffer = C.create_string_buffer(offset + len(raw))
        header = n.DefaultDacl.from_buffer(buffer)
        header.pointer = C.addressof(buffer) + offset
        C.memmove(header.pointer, raw, len(raw))
        self.assertEqual(n._dacl_bytes(buffer, C.sizeof(buffer)), raw)
        for pointer in (None, C.addressof(buffer), C.addressof(buffer)+C.sizeof(buffer)-7):
            header.pointer = pointer
            with self.assertRaises(n.TokenRefused): n._dacl_bytes(buffer, C.sizeof(buffer))
        header.pointer = C.addressof(buffer)+offset
        C.c_uint16.from_buffer(buffer, offset+2).value = 65532
        with self.assertRaises(n.TokenRefused): n._dacl_bytes(buffer, C.sizeof(buffer))

    def test_only_understood_canonical_explicit_ace_subset_admitted(self):
        n._admit_default_dacl(acl(), SID)  # empty ACL is not NULL
        n._admit_default_dacl(acl(ace(1), ace(0, 1)), SID)
        for raw in (acl(ace(0), ace(1)), acl(ace(0, 0x10)), acl(ace(5)),
                    acl(ace(0, 0x40)), acl(ace(sid=SID+b'EXTR')), acl(ace(sid=b'\x02'+SID[1:]))):
            with self.assertRaises(n.TokenRefused): n._admit_default_dacl(raw, SID)
        everyone = b'\x01\x01' + b'\x00'*5 + b'\x01' + struct.pack('<I', 0)
        with self.assertRaises(n.TokenRefused): n._admit_default_dacl(acl(ace(sid=everyone)), SID)
        n._admit_default_dacl(acl(ace(kind=1, sid=everyone), ace()), SID)
        system = b'\x01\x01' + b'\x00'*5 + b'\x05' + struct.pack('<I', 18)
        n._admit_default_dacl(acl(ace(sid=system), ace()), SID)

    def test_setter_is_derived_only_serialized_and_factory_stays_closed(self):
        self.assertEqual(n.TokenProfile.DERIVE_ONLY.value, 0xa)
        self.assertEqual(n.TokenProfile.CREATE_CANDIDATE.value, 0x8b)
        self.assertEqual(C.sizeof(n.DefaultDacl), C.sizeof(C.c_void_p))
        with self.assertRaises(n.TokenRefused): n.native_restricted_process()
        self.assertFalse(n._RestrictedPrimaryCandidate.launch_ready)
        self.assertFalse(hasattr(n._RestrictedPrimaryCandidate.prepare_default_dacl, '__wrapped__'))
        tree = ast.parse(Path(n.__file__).read_text())
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                   and x.name == '_RestrictedPrimaryCandidate')
        methods = {x.name: x for x in cls.body if isinstance(x, ast.FunctionDef)}
        for name in ('derive', 'prepare_default_dacl', 'close'):
            self.assertIn('_serialized', [d.id for d in methods[name].decorator_list])
        calls = [x for x in ast.walk(methods['prepare_default_dacl']) if isinstance(x, ast.Call)
                 and isinstance(x.func, ast.Attribute) and x.func.attr == 'SetTokenInformation']
        self.assertEqual(len(calls), 1)
        self.assertEqual(ast.unparse(calls[0].args[0]), 'self._derived')
        self.assertEqual(calls[0].args[1].value, 6)
        self.assertEqual(ast.unparse(calls[0].args[3]), 'C.sizeof(value)')


if __name__ == '__main__': unittest.main()
