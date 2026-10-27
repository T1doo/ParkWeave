"""Actual ABI/UTF-16 memory and source contracts; no Win32 API substitutes."""
import ast
import ctypes as C
from pathlib import Path
import unittest

from . import restricted_startup_candidate as n


def text(buffer):
    return C.string_at(C.addressof(buffer), C.sizeof(buffer)).decode('utf-16-le')


class RestrictedStartupSourceChecks(unittest.TestCase):
    def test_x64_structure_layout_and_extended_cb(self):
        self.assertEqual(C.sizeof(C.c_void_p), 8)
        self.assertEqual(C.sizeof(n.StartupInfo), 104)
        self.assertEqual(C.sizeof(n.StartupInfoEx), 112)
        self.assertEqual(n.StartupInfo.dwFlags.offset, 60)
        self.assertEqual(n.StartupInfo.hStdInput.offset, 80)
        self.assertEqual(n.StartupInfoEx.lpAttributeList.offset, 104)
        info = n.StartupInfoEx()
        info.StartupInfo.cb = C.sizeof(info)
        self.assertEqual(C.c_uint32.from_address(C.addressof(info)).value, 112)

    def test_writable_utf16_command_quotes_unicode_and_refusals(self):
        buffer = n.command_buffer(r'C:\Program Files\Park\initdb.exe', ('--encoding=UTF8', 'a b', ''))
        self.assertEqual(text(buffer), '"C:\\Program Files\\Park\\initdb.exe" --encoding=UTF8 "a b" ""\0')
        buffer[0] = ord('X')
        self.assertTrue(text(buffer).startswith('X'))
        unicode = n.command_buffer(r'C:\Park\initdb.exe', ('园区😀',))
        self.assertIn('园区😀', text(unicode))
        for executable, args in ((r'C:\Park\initdb.exe', ('bad\0value',)),
                                 (r'C:\Park\initdb.exe', ('\ud800',)),
                                 ('relative.exe', ()), (r'C:\Park\initdb.exe', ['a'])):
            with self.assertRaises(n.StartupRefused): n.command_buffer(executable, args)

    def test_environment_double_terminator_case_duplicates_and_secret_keys(self):
        environment = {'TEMP': r'C:\private\临时', 'SystemRoot': r'C:\Windows', 'PATH': r'C:\Park\bin'}
        self.assertEqual(text(n.environment_buffer(environment)),
                         'PATH=C:\\Park\\bin\0SystemRoot=C:\\Windows\0TEMP=C:\\private\\临时\0\0')
        self.assertEqual(text(n.environment_buffer({})), '\0\0')
        for values in ({'SystemRoot': 'a', 'SYSTEMROOT': 'b'}, {'PG_RESTRICT_EXEC': '1'},
                       {'PGPASSWORD': 'SYNTHETIC'}, {'PATH': 'bad\0entry'},
                       {'PATH': '\ud800'}, {k: '😀'*8192 for k in ('PATH','TEMP','TMP')}):
            with self.assertRaises(n.StartupRefused): n.environment_buffer(values)

    def test_pseudo_handles_are_data_refusals_not_real_duplicates(self):
        top = 1 << (8 * C.sizeof(C.c_void_p))
        for value in (0, -1, -2, -4, True, '128', top, top-1, top-2, top-4, top-6):
            self.assertFalse(n._handle(value))
        self.assertTrue(n._handle(128))  # integer shape only, never authority

    def test_no_creation_entry_and_delete_abi_is_void(self):
        with self.assertRaisesRegex(n.StartupRefused, 'NOT_ACCEPTED'):
            n.native_restricted_startup()
        self.assertFalse(n._OwnedStartup.launch_ready)
        self.assertFalse(n._OwnedStartup.native_acceptance)
        tree = ast.parse(Path(n.__file__).read_text())
        self.assertTrue(all(isinstance(x, (ast.Expr, ast.Import, ast.ImportFrom,
                                          ast.ClassDef, ast.FunctionDef)) for x in tree.body))
        attrs = {x.attr for x in ast.walk(tree) if isinstance(x, ast.Attribute)}
        self.assertFalse(attrs & {'CreateProcessAsUserW', 'CreateProcessW', 'SetTokenInformation',
                                 'CreateRestrictedToken', 'CreateJobObjectW'})
        signatures = next(x.value for x in ast.walk(tree) if isinstance(x, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'signatures' for t in x.targets))
        delete = next(value for key, value in zip(signatures.keys, signatures.values)
                      if key.value == 'DeleteProcThreadAttributeList')
        self.assertIsNone(delete.elts[1].value)


if __name__ == '__main__': unittest.main()
