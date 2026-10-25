"""Real local ctypes buffers/source contracts only, no native API substitutes."""
import ast
import ctypes as C
from pathlib import Path
import struct
import unittest

from . import restricted_token_candidate as n


ADMIN = b'\x01\x02' + b'\x00' * 5 + b'\x05' + struct.pack('<II', 32, 544)


class RestrictedSourceChecks(unittest.TestCase):
    def test_real_group_buffer_and_outside_or_overlapping_sid_refused(self):
        end = n.GroupLayout.groups.offset + C.sizeof(n.SidAttributes)
        buffer = C.create_string_buffer(end + len(ADMIN))
        C.c_uint32.from_buffer(buffer).value = 1
        row = n.SidAttributes.from_buffer(buffer, n.GroupLayout.groups.offset)
        row.sid, row.attributes = C.addressof(buffer) + end, 0x10
        C.memmove(row.sid, ADMIN, len(ADMIN))
        self.assertEqual(n._parse(buffer, C.sizeof(buffer), 2), {ADMIN: 0x10})
        for pointer in (C.addressof(buffer) - 1, C.addressof(buffer),
                        C.addressof(buffer) + C.sizeof(buffer) - 7):
            row.sid = pointer
            with self.assertRaises(n.TokenRefused): n._parse(buffer, C.sizeof(buffer), 2)
        C.c_uint32.from_buffer(buffer).value = 2049
        with self.assertRaises(n.TokenRefused): n._parse(buffer, C.sizeof(buffer), 2)

    def test_actual_privilege_layout_and_bounded_token_type(self):
        buffer = C.create_string_buffer(4 + C.sizeof(n.Privilege))
        C.c_uint32.from_buffer(buffer).value = 1
        privilege = n.Privilege.from_buffer(buffer, 4)
        privilege.luid.low, privilege.luid.high, privilege.attributes = 23, -1, 2
        self.assertEqual(n._parse(buffer, C.sizeof(buffer), 3), {(23, -1): 2})
        with self.assertRaises(n.TokenRefused): n._parse(buffer, 4, 3)
        primary = C.create_string_buffer(struct.pack('<I', 1), 4)
        self.assertEqual(n._parse(primary, 4, 8), 1)
        with self.assertRaises(n.TokenRefused): n._parse(primary, 5, 8)

    def test_comparison_is_observation_not_launch_authority(self):
        base = {8: 1, 1: b'USER', 2: {ADMIN: 6}, 3: {(23, 0): 2, (24, 0): 2}}
        derived = {8: 1, 1: b'USER', 2: {ADMIN: 16}, 3: {(23, 0): 2, (24, 0): 0}}
        n._check(base, derived, {ADMIN}, (23, 0))
        for changed in ({**derived, 8: 2}, {**derived, 1: b'OTHER'},
                        {**derived, 2: {ADMIN: 6}}, {**derived, 3: {(24, 0): 2}}):
            with self.assertRaises(n.TokenRefused): n._check(base, changed, {ADMIN}, (23, 0))
        disabled = {**base, 3: {(23, 0): 0, (24, 0): 2}}
        with self.assertRaises(n.TokenRefused): n._check(disabled, derived, {ADMIN}, (23, 0))
        self.assertFalse(n._RestrictedPrimaryCandidate.launch_ready)
        self.assertFalse(n._RestrictedPrimaryCandidate.native_acceptance)
        with self.assertRaisesRegex(n.TokenRefused, 'NOT_ACCEPTED'):
            n.native_restricted_process()

    def test_module_has_no_eager_native_calls_or_creation_api(self):
        tree = ast.parse(Path(n.__file__).read_text())
        self.assertTrue(all(isinstance(x, (ast.Expr, ast.Import, ast.ImportFrom,
                                          ast.ClassDef, ast.FunctionDef)) for x in tree.body))
        attrs = {x.attr for x in ast.walk(tree) if isinstance(x, ast.Attribute)}
        self.assertFalse(attrs & {'CreateProcessAsUserW',
                                 'AdjustTokenPrivileges', 'CreateJobObjectW'})
        source = Path(n.__file__).read_text()
        self.assertNotIn("['PG_RESTRICT_EXEC']", source)
        self.assertEqual(C.sizeof(n.Luid), 8)
        self.assertEqual(C.sizeof(n.Privilege), 12)
        # A failed Win32 call's nonzero out value is not ownership evidence.
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                   and x.name == '_RestrictedPrimaryCandidate')
        derive = next(x for x in cls.body if isinstance(x, ast.FunctionDef)
                      and x.name == 'derive')
        transfers = [node for node in ast.walk(derive) if isinstance(node, ast.If)
                     and any(isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
                             and x.func.attr == 'append' for stmt in node.body for x in ast.walk(stmt))]
        self.assertEqual(len(transfers), 2)
        self.assertTrue(all(isinstance(x.test, ast.BoolOp)
                            and isinstance(x.test.values[0], ast.Name)
                            and x.test.values[0].id == 'ok' for x in transfers))


if __name__ == '__main__': unittest.main()
