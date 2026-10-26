"""Real byte-policy/ABI/source checks only; no WinAPI calls or DLL loading."""
import ast
import ctypes as C
from dataclasses import replace
from pathlib import Path
import struct
import threading
from types import SimpleNamespace
import unittest

from parkweave.windows_files import Ace, Security, Info, private_acl
from . import pgdata_candidate as n
from . import restricted_initdb_candidate as process

SID = b'\x01\x04'+b'\0'*5+b'\x05'+struct.pack('<IIII', 21, 101, 202, 1001)
USER = 'S-1-5-21-101-202-1001'


def security(root=False, directory=False):
    return Security(USER, 0x9004 if root else 0x8404,
                    (Ace(0, 3 if root else 0x13 if directory else 0x10, n.FILE_ALL, USER),))


def batch(name, identity=42, attrs=0x10):
    raw = bytearray(104+len(name.encode('utf-16-le')))
    struct.pack_into('<II', raw, 56, attrs, len(raw)-104)
    struct.pack_into('<Q', raw, 96, identity)
    raw[104:] = name.encode('utf-16-le')
    return bytes(raw)


class PGDataSourceChecks(unittest.TestCase):
    def test_walk_rejection_and_close_failure_preserve_both_causes(self):
        target = object.__new__(n._NewDataTarget)
        target.deadline = float('inf'); target.root = 100
        target.handles = [101]; target.cleanup_errors = []
        target.lease = SimpleNamespace(fs=SimpleNamespace(root_id=[5, 90]))
        target._verify = lambda: SimpleNamespace(root_id=(5, 100), user=USER, sid=SID, path='R')
        target._entries = lambda handle: (('file', 0x80, 101),)
        target._open = lambda *args: 101
        def close(handle): raise OSError('INJECTED_CLOSE_FAILURE')
        target.api = SimpleNamespace(info=lambda h: Info(0x10 if h == 100 else 0x80, 0, 1, 5, h),
            descriptor=lambda h: (), security=lambda h: replace(security(), owner='S-1-1-0'), close=close)
        with self.assertRaises(BaseExceptionGroup) as caught: target._walk()
        self.assertEqual([type(x) for x in caught.exception.exceptions], [n.DataRefused, OSError])
        self.assertEqual(target.cleanup_errors, [('HANDLE_CLOSE_UNKNOWN', 101)])
        self.assertEqual(target.handles, [])

    def test_unknown_closes_once_preserves_objects_and_stays_poisoned(self):
        lease = object.__new__(n.FixedDirectoryLease)
        lease._operation_owner, lease._operation_depth = None, 0
        lease._entry_lock = threading.Lock(); lease.poisoned = False
        target = object.__new__(n._NewDataTarget)
        target.lease, target.handles, target.cleanup_errors = lease, [10, 11], []
        target.failed, target.closed = False, False
        closed = []
        def close(handle):
            closed.append(handle)
            if handle == 11: raise OSError('INJECTED_CLOSE_FAILURE')
        target.api = SimpleNamespace(close=close)
        target._walk = lambda: (_ for _ in ()).throw(n.DataRefused('ORIGINAL_DRIFT'))
        n._by_lease[lease] = target
        with self.assertRaisesRegex(n.DataRefused, 'ORIGINAL_DRIFT'): n._scan_entry(lease, target)
        self.assertTrue(lease.poisoned and target.failed and target.closed)
        self.assertEqual(target.outcome, 'UNKNOWN')
        self.assertEqual(closed, [11, 10])
        target.close()  # Already attempted unknown integer must never be retried.
        self.assertEqual(closed, [11, 10])
        self.assertIs(n._by_lease[lease], target)  # No deleting/adopting a failed attempt.

    def test_new_policy_is_separate_from_original_protected_object_rule(self):
        private_acl(security(root=True), USER)
        for directory in (False, True):
            value = security(directory=directory)
            with self.assertRaises(Exception): private_acl(value, USER)
            n.check_security(value, USER, root=False, directory=directory)
        n.check_security(security(root=True), USER, root=True, directory=True)

    def test_owner_flags_principals_masks_and_unknown_controls_are_closed(self):
        original = security(directory=True)
        changed = [replace(original, owner='S-1-5-18'), replace(original, control=0x9404),
                   replace(original, control=0x8044), replace(original, aces=None)]
        for field, value in (('kind', 1), ('flags', 3), ('flags', 0x1b), ('flags', 0x10),
                             ('mask', 0x10000000), ('mask', 0x1f01fe), ('sid', 'S-1-1-0'),
                             ('sid', 'S-1-5-18'), ('sid', 'S-1-5-32-544')):
            changed.append(replace(original, aces=(replace(original.aces[0], **{field: value}),)))
        changed.append(replace(original, aces=original.aces*2))
        for value in changed:
            with self.subTest(value=value), self.assertRaises(n.DataRefused):
                n.check_security(value, USER, root=False, directory=True)

    def test_exact_self_relative_root_and_child_raw_acl(self):
        raw = n.root_descriptor(SID)
        self.assertEqual(n._sid_text(SID), USER)
        self.assertEqual(struct.unpack_from('<BBHIIII', raw), (1, 0, 0x9004, 20, 0, 0, 20+len(SID)))
        acl = raw[20+len(SID):]
        n.check_descriptor((USER, 0x9004, acl), SID, root=True, directory=True)
        for directory, flags in ((True, 0x13), (False, 0x10)):
            child = bytearray(acl); child[9] = flags
            n.check_descriptor((USER, 0x8404, bytes(child)), SID, root=False, directory=directory)
            for broken in (bytes(child)+b'\0'*4, bytes(child)[:-1], acl):
                with self.assertRaises(n.DataRefused):
                    n.check_descriptor((USER, 0x8404, broken), SID, root=False, directory=directory)

    def test_metadata_denies_reparse_volume_escape_hardlink_and_bad_identity(self):
        base = Info(0x80, 2**30, 1, 5, 41)  # PG files have no 16KiB resource limit.
        self.assertEqual(n._metadata(base, 5, directory=False), (5, 41))
        for value in (replace(base, attributes=0x480), replace(base, volume=6),
                      replace(base, links=2), replace(base, identity=0), replace(base, attributes=0x10)):
            with self.assertRaises(n.DataRefused): n._metadata(value, 5, directory=False)

    def test_real_directory_buffer_handles_chinese_and_multiple_entries(self):
        first = bytearray(batch('base')); size = (len(first)+7)//8*8
        first.extend(b'\0'*(size-len(first))); struct.pack_into('<I', first, 0, size)
        raw = bytes(first)+batch('中文长名称', 43, 0x80)
        self.assertEqual(n.directory_batch(raw), (('base', 0x10, 42), ('中文长名称', 0x80, 43)))
        self.assertEqual(n.directory_batch(batch('.')), ())
        self.assertEqual(n.directory_batch(batch('..')), ())

    def test_directory_buffer_rejects_truncation_offset_names_and_identity(self):
        rows = [batch('base')[:-1], batch('base', identity=0), batch('..\\escape'), batch('wal:stream')]
        for offset, value in ((0, 1), (0, 65528), (60, 511), (60, 0), (68, 25)):
            raw = bytearray(batch('base')); struct.pack_into('<I' if offset != 68 else '<B', raw, offset, value)
            rows.append(bytes(raw))
        for raw in rows:
            with self.assertRaises(Exception): n.directory_batch(raw)

    def test_native_creation_is_fixed_relative_exclusive_and_registers_handle_first(self):
        tree = ast.parse(Path(n.__file__).read_text())
        methods = {x.name:x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)}
        call = next(x for x in ast.walk(methods['_open']) if isinstance(x, ast.Call) and
                    isinstance(x.func, ast.Attribute) and x.func.attr == 'ntcreate')
        self.assertEqual(ast.unparse(call.args[7]), '2 if create else 1')
        self.assertEqual(ast.unparse(call.args[6]), '3 if anchor else 7')
        self.assertEqual(ast.unparse(call.args[8]), '32 | 2097152 | (1 if create else 0)')
        append = next(x for x in ast.walk(methods['_open']) if isinstance(x, ast.Call) and
                      isinstance(x.func, ast.Attribute) and x.func.attr == 'append')
        status = next(x for x in ast.walk(methods['_open']) if isinstance(x, ast.Call) and
                      isinstance(x.func, ast.Name) and x.func.id == '_need' and 'status == 0' in ast.unparse(x))
        self.assertLess(status.lineno, append.lineno)
        created = next(x for x in ast.walk(methods['_open']) if isinstance(x, ast.Call) and
                       isinstance(x.func, ast.Name) and x.func.id == '_need' and 'io.Information' in ast.unparse(x))
        self.assertLess(append.lineno, created.lineno)
        # Existing startup layouts/real pointer size, not a simulated OS.
        self.assertEqual(C.sizeof(n.ObjectAttributes), 48)
        self.assertEqual(C.sizeof(n.IOStatus), 16)

    def test_capability_required_by_freeze_and_every_creation_freshcheck(self):
        tree = ast.parse(Path(process.__file__).read_text())
        methods = {x.name:x for x in ast.walk(tree) if isinstance(x, ast.FunctionDef)}
        self.assertEqual([x.arg for x in methods['_freeze'].args.kwonlyargs], ['data_target'])
        for method in ('_freeze', '_fresh'):
            self.assertTrue(any(isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and
                                x.func.id == '_path_held' for x in ast.walk(methods[method])))
        self.assertFalse(n._NewDataTarget.launch_ready)
        self.assertFalse(process._RestrictedInitdbBackend.launch_ready)
        with self.assertRaisesRegex(n.DataRefused, 'NOT_ACCEPTED'): n.native_pgdata()
        with self.assertRaises(Exception): n._path_held(object(), object())
        attrs = {x.attr for x in ast.walk(ast.parse(Path(n.__file__).read_text())) if isinstance(x, ast.Attribute)}
        self.assertFalse(attrs & {'ResumeThread', 'SetSecurityInfo', 'SetNamedSecurityInfoW',
                                'SetTokenInformation', 'WriteFile', 'DeleteFileW', 'CreateProcessAsUserW'})


if __name__ == '__main__': unittest.main()
