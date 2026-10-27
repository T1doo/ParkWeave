"""Actual local ctypes buffers and source contracts, never Windows/DPAPI calls."""
import ast
import ctypes as C
from pathlib import Path
import unittest

from . import dpapi_native_candidate as n
from . import windows_user_protection as original


class NativeSourceChecks(unittest.TestCase):
    def test_real_input_allocation_embedded_nul_and_erasure(self):
        value = b'SYNTHETIC\0BLOB'
        item = n._InputBlob(value, 32)
        address = item.blob.pbData
        self.assertEqual(item.blob.cbData, len(value))
        self.assertEqual(C.string_at(address, len(value)), value)
        item.close()
        self.assertEqual(C.string_at(address, len(value)), b'\0' * len(value))
        self.assertEqual(bytes(item._data), b'\0' * len(value))
        self.assertFalse(item.blob.pbData)
        self.assertEqual(item.blob.cbData, 0)
        item.close()  # idempotent, never touches a freed native address

    def test_invalid_input_rejected_without_native_allocation(self):
        for value in (b'', bytearray(b'x'), 'x', b'x' * 33):
            with self.subTest(kind=type(value).__name__):
                with self.assertRaises(original.ProtectionRefused):
                    n._InputBlob(value, 32)

    def test_closed_factory_and_redacted_public_failure(self):
        with self.assertRaisesRegex(original.ProtectionRefused,
                                    'NATIVE_CURRENT_USER_PROTECTION_NOT_ACCEPTED'):
            original.native_user_protection()
        failure = n.NativeFailure('COPY', 'ValueError', ['OSError'])
        self.assertEqual(failure.outcome, 'UNKNOWN')
        self.assertEqual(str(failure), 'NATIVE_DPAPI_UNKNOWN:COPY')
        self.assertFalse(n._NativeDPAPI.native_acceptance)

    def test_no_import_time_loader_and_fixed_native_call_shape(self):
        tree = ast.parse(Path(n.__file__).read_text())
        # Executable module statements are imports/classes only: no eager API.
        self.assertTrue(all(isinstance(node, (ast.Expr, ast.Import, ast.ImportFrom,
                                              ast.ClassDef)) for node in tree.body))
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                   and x.name == '_NativeDPAPI')
        init = next(x for x in cls.body if isinstance(x, ast.FunctionDef)
                    and x.name == '__init__')
        self.assertEqual([x.arg for x in init.args.args], ['self'])
        loaders = [x for x in ast.walk(init) if isinstance(x, ast.Call)
                   and isinstance(x.func, ast.Attribute) and x.func.attr == 'WinDLL']
        self.assertEqual([x.args[0].value for x in loaders], ['crypt32.dll', 'kernel32.dll'])
        self.assertTrue(all(any(k.arg == 'winmode' and k.value.value == 0x800
                                for k in call.keywords) for call in loaders))
        method = next(x for x in cls.body if isinstance(x, ast.FunctionDef)
                      and x.name == '_call')
        call = next(x for x in ast.walk(method) if isinstance(x, ast.Call)
                    and isinstance(x.func, ast.Name) and x.func.id == 'function')
        self.assertEqual(len(call.args), 7)
        self.assertTrue(all(isinstance(call.args[i], ast.Constant)
                            and call.args[i].value is None for i in (1, 3, 4)))
        self.assertEqual(call.args[5].id, 'CRYPTPROTECT_UI_FORBIDDEN')
        failure = method.body[-2]
        cleared = {t.id for node in failure.body if isinstance(node, ast.Assign)
                   and isinstance(node.value, ast.Constant) and node.value.value is None
                   for t in node.targets if isinstance(t, ast.Name)}
        self.assertTrue({'result', 'data', 'entropy'} <= cleared)


if __name__ == '__main__':
    unittest.main()
