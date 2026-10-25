"""Descriptor/ABI/registry source checks; no pipe, native calls or fake API."""
import ast
import ctypes as C
from pathlib import Path
import struct
import unittest

from . import initdb_pipe_candidate as n


SID = b'\x01\x02' + b'\x00'*5 + b'\x05' + struct.pack('<II', 32, 544)


def descriptor(sid=SID, flags=0, mask=0x1f01ff):
    ace = struct.pack('<BBHI', 0, flags, 8+len(sid), mask) + sid
    acl = struct.pack('<BBHHH', 2, 0, 8+len(ace), 1, 0) + ace
    return struct.pack('<BBHIIII', 1, 0, 0x9004, 20, 0, 0, 20+len(SID)) + SID + acl


class InitdbPipeSourceChecks(unittest.TestCase):
    def test_exact_private_descriptor_and_mapped_or_generic_mask(self):
        n._private_descriptor(descriptor(), SID)
        n._private_descriptor(descriptor(mask=0x10000000), SID)
        for raw in (descriptor(flags=0x10), descriptor(mask=0x10000001),
                    descriptor(sid=SID[:-1]+b'X'), descriptor()[:-1]):
            with self.assertRaises(n.PipeRefused): n._private_descriptor(raw, SID)

    def test_relative_offsets_and_null_or_additional_components_refuse(self):
        raw = descriptor()
        for offset, value in ((4, 0), (4, 0xfffffff0), (8, 20), (12, 20),
                              (16, 0), (16, 20), (16, len(raw)-7)):
            changed = bytearray(raw)
            struct.pack_into('<I', changed, offset, value)
            with self.assertRaises(n.PipeRefused): n._private_descriptor(bytes(changed), SID)
        changed = bytearray(raw)
        struct.pack_into('<H', changed, 2, 0x8004)  # unprotected
        with self.assertRaises(n.PipeRefused): n._private_descriptor(bytes(changed), SID)

    def test_name_is_only_data_and_security_attributes_layout(self):
        name = n._pipe_name('12345678-1234-4234-8234-123456789abc', 'a'*32)
        self.assertTrue(name.startswith('\\\\.\\pipe\\ParkWeave-'))
        self.assertLess(len(name), 256)
        with self.assertRaises(n.PipeRefused): n._pipe_name('12345678-1234-4234-8234-123456789abc', '../bad')
        self.assertEqual(C.sizeof(n.SecurityAttributes), 24)
        self.assertEqual(n.SecurityAttributes.descriptor.offset, 8)
        self.assertEqual(n.SecurityAttributes.inherit.offset, 16)
        self.assertFalse(n._OwnedInitdbPipe.launch_ready)
        with self.assertRaisesRegex(n.PipeRefused, 'NOT_ACCEPTED'): n.native_initdb_pipe()

    def test_creation_and_security_read_source_exclude_connection_and_secrets(self):
        tree = ast.parse(Path(n.__file__).read_text())
        attrs = {x.attr for x in ast.walk(tree) if isinstance(x, ast.Attribute)}
        self.assertFalse(attrs & {'ConnectNamedPipe', 'WriteFile', 'ReadFile', 'CreateProcessAsUserW',
                                 'CreateRestrictedToken', 'SetTokenInformation', 'GetNamedPipeInfo'})
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == '_OwnedInitdbPipe')
        methods = {x.name:x for x in cls.body if isinstance(x, ast.FunctionDef)}
        creation = next(x for x in ast.walk(methods['_create_native']) if isinstance(x, ast.Call)
                        and isinstance(x.func, ast.Attribute) and x.func.attr == 'CreateNamedPipeW')
        self.assertEqual([creation.args[i].value for i in (1, 2, 3)], [0x40080002, 8, 1])
        read = next(x for x in ast.walk(methods['_verify_native']) if isinstance(x, ast.Call)
                    and isinstance(x.func, ast.Attribute) and x.func.attr == 'GetKernelObjectSecurity')
        self.assertEqual(read.args[1].value, 5)
        close_attrs = {x.attr for x in ast.walk(methods['close']) if isinstance(x, ast.Attribute)}
        self.assertFalse(close_attrs & {'_verify', '_query', '_key_held'})
        use = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == '_pwfile_name_held')
        handlers = [x for x in ast.walk(use) if isinstance(x, ast.ExceptHandler)]
        failure = handlers[0]
        self.assertTrue(any(isinstance(x, ast.Assign) and ast.unparse(x.targets[0]) == 'server.failed'
                            and x.value.value is True for x in failure.body if isinstance(x, ast.Assign)))
        self.assertTrue(any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                            and ast.unparse(x.func) == 'server.close' for x in ast.walk(failure)))


if __name__ == '__main__': unittest.main()
