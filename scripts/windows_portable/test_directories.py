"""Real bounded Linux file/process tests; separately labelled Windows stand-ins.

Every filesystem mutation is inside this test's own TemporaryDirectory. No PG,
Windows APIs, ACL setters, unknown lock removal or PID-based cleanup runs.
"""
import ctypes as C
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from . import directories as d
from . import windows_directory_handles as w


def complete(lease, *, reopen=False):
    phases = (['CLUSTER', 'VERIFY_DATABASE'] if reopen else
              ['CREDENTIALS', 'CLUSTER', 'CREATE_SCHEMA', 'ROLES', 'SESSIONS', 'SEED', 'CONFIG', 'VERIFY_FILES', 'VERIFY_DATABASE'])
    for phase in phases: lease.checkpoint(phase, reopen, 'STARTING')
    lease.checkpoint('READY', True, 'STOPPED')
    lease.checkpoint('APPLICATION', True, 'STARTING')
    lease.checkpoint('RUNNING', True, 'RUNNING')
    lease.checkpoint('READY_STOPPED', True, 'STOPPED')


CHILD = r'''
import os,sys
from scripts.windows_portable.directories import PrivateDirectories
from scripts.windows_portable.test_directories import complete
base,root,mode=sys.argv[1:]
if mode=='contend':
 print('READY',flush=True);sys.stdin.readline()
try:
 lease=(PrivateDirectories(base).claim_fresh(root) if mode=='crash_new' else PrivateDirectories(base).open_existing(root))
except BlockingIOError:
 print('BUSY',flush=True);sys.exit(0)
print('ACQUIRED',flush=True)
if mode=='crash_new':
 complete(lease);os._exit(17)
if mode=='crash_after_acquire':os._exit(17)
if mode=='hold':sys.stdin.readline()
complete(lease,reopen=True)
lease.release()
print('STOPPED_RELEASED',flush=True)
'''


@unittest.skipUnless(sys.platform == 'linux', 'real Linux filesystem/process evidence only')
class ActualLinuxLeaseChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='parkweave-directory-lease-')
        self.addCleanup(self.temp.cleanup)
        self.base, self.root = Path(self.temp.name), Path(self.temp.name) / 'instance'
        self.dirs = d.PrivateDirectories(str(self.base))
        self.leases = []
        self.addCleanup(self.close_leases)

    def close_leases(self):
        for lease in self.leases:
            if lease.active:
                try: lease.release()
                except BaseException: pass  # Test assertion already observes injected failure.

    def fresh(self):
        lease = self.dirs.claim_fresh(str(self.root)); self.leases.append(lease); return lease

    def existing(self):
        lease = self.dirs.open_existing(str(self.root)); self.leases.append(lease); return lease

    def child(self, mode):
        # Controlled Python child only, no inherited credentials or PG env.
        repo = str(Path(__file__).resolve().parents[2])
        env = {'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': repo + os.pathsep + repo + '/src',
               'PYTHONDONTWRITEBYTECODE': '1', 'LANG': 'C.UTF-8'}
        process = subprocess.Popen([sys.executable, '-B', '-c', CHILD, str(self.base), str(self.root), mode],
                                   cwd=repo, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True)
        def cleanup():
            if process.poll() is None:
                process.terminate()  # This exact returned Popen, never a guessed PID.
                try: process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill(); process.communicate(timeout=3)
        self.addCleanup(cleanup)
        return process

    def test_real_lock_inode_stays_fixed_journal_replaces_and_reopen_bumps_generation(self):
        lease = self.fresh(); lock = (self.root / d.LOCK).stat().st_ino
        first_journal = (self.root / d.JOURNAL).stat().st_ino
        complete(lease)
        self.assertNotEqual(first_journal, (self.root / d.JOURNAL).stat().st_ino)
        self.assertEqual(lock, (self.root / d.LOCK).stat().st_ino)
        self.assertEqual(json.loads((self.root / d.JOURNAL).read_bytes())['handoff'], 'OWNED')
        lease.release()
        self.assertEqual(json.loads((self.root / d.JOURNAL).read_bytes())['handoff'], 'RELEASE_PENDING')
        second = self.existing()
        self.assertEqual((second.status(), second.record['generation'], second.record['handoff']), ('READY_STOPPED', 2, 'OWNED'))
        self.assertEqual(lock, (self.root / d.LOCK).stat().st_ino)
        complete(second, reopen=True); second.release()

    def test_two_real_process_contenders_are_refused_while_original_kernel_lock_is_held(self):
        lease = self.fresh(); complete(lease)
        children = [self.child('contend'), self.child('contend')]
        import select
        for process in children:
            ready, _, _ = select.select([process.stdout], [], [], 5)
            self.assertTrue(ready); self.assertEqual(process.stdout.readline(), 'READY\n')
        self.assertTrue(all(p.poll() is None for p in children))
        # Both returned own workers are alive at the barrier. Release both
        # before waiting for either, while the parent keeps the real lock.
        for process in children: os.write(process.stdin.fileno(), b'go\n')
        outputs = [p.communicate(timeout=5) for p in children]
        self.assertEqual([p.returncode for p in children], [0, 0])
        self.assertEqual(outputs, [('BUSY\n', ''), ('BUSY\n', '')])
        lease.release()
        winner = self.child('probe'); out, err = winner.communicate(timeout=5)
        self.assertEqual((winner.returncode, out, err), (0, 'ACQUIRED\nSTOPPED_RELEASED\n', ''))
        print('ACTUAL_LINUX: two own processes alive at barrier, both BUSY; after close one ACQUIRED/STOPPED_RELEASED', flush=True)

    def test_real_child_crash_before_release_intent_cannot_reopen_even_if_ready_was_written(self):
        process = self.child('crash_new'); out, err = process.communicate(timeout=5)
        self.assertEqual((process.returncode, out, err), (17, 'ACQUIRED\n', ''))
        self.assertEqual(json.loads((self.root / d.JOURNAL).read_bytes())['phase'], 'READY_STOPPED')
        with self.assertRaisesRegex(d.LeaseRefused, 'CONFIRMED_HANDOFF'): self.existing()
        print('ACTUAL_LINUX: os._exit(17) after READY but before release intent refused', flush=True)

    def test_real_reacquirer_crash_retires_old_pending_handoff_before_returning(self):
        lease = self.fresh(); complete(lease); lease.release()
        process = self.child('crash_after_acquire'); out, err = process.communicate(timeout=5)
        self.assertEqual((process.returncode, out, err), (17, 'ACQUIRED\n', ''))
        record = json.loads((self.root / d.JOURNAL).read_bytes())
        self.assertEqual((record['generation'], record['handoff']), (2, 'OWNED'))
        with self.assertRaisesRegex(d.LeaseRefused, 'CONFIRMED_HANDOFF'): self.existing()

    def test_close_reports_unknown_after_actual_kernel_close_without_retry_or_postclose_write(self):
        lease = self.fresh(); complete(lease)
        realclose, lock = os.close, lease.fs.lock
        calls = []
        def close(fd):
            calls.append(fd); realclose(fd)
            if fd == lock: raise OSError('injected result unknown after actual close')
        with patch.object(os, 'close', side_effect=close):
            with self.assertRaises(BaseExceptionGroup): lease.release()
        self.assertFalse(lease.active); self.assertEqual(calls.count(lock), 1)
        with patch.object(os, 'close', side_effect=AssertionError('ambiguous fd retried')):
            lease.fs.close()
        before = (self.root / d.JOURNAL).read_bytes()
        with self.assertRaisesRegex(d.LeaseRefused, 'LEASE_NOT_WRITABLE'): lease.checkpoint('CLUSTER', True, 'STARTING')
        self.assertEqual((self.root / d.JOURNAL).read_bytes(), before)
        # This is a NEW real exclusive observation, not a claim old close returned success.
        new = self.existing(); self.assertEqual(new.record['generation'], 2)

    def test_failed_close_retaining_actual_lock_blocks_new_acquisition_and_is_not_retried(self):
        lease = self.fresh(); complete(lease)
        realclose, lock = os.close, lease.fs.lock
        identity, calls = lease.fs.lock_id, []
        def close(fd):
            calls.append(fd)
            if fd == lock: raise OSError('injected known failure before close')
            realclose(fd)
        try:
            with patch.object(os, 'close', side_effect=close):
                with self.assertRaises(BaseExceptionGroup): lease.release()
            self.assertEqual(calls.count(lock), 1)
            with self.assertRaises(BlockingIOError): self.existing()
        finally:
            # Injection guarantees this own test fd never closed; inspect the
            # held identity before cleanup. Production NEVER retries an unknown fd.
            self.assertEqual(d.PosixFilesystem.identity(lock), identity)
            realclose(lock)

    def test_actual_identity_drift_symlink_hardlink_and_foreign_journal_are_refused(self):
        lease = self.fresh(); complete(lease); lease.release()
        original = (self.root / d.JOURNAL).read_bytes()
        other = self.base / 'outside'; other.write_bytes(b'never modify')
        (self.root / d.JOURNAL).unlink(); (self.root / d.JOURNAL).symlink_to(other)
        with self.assertRaises(OSError): self.existing()
        self.assertEqual(other.read_bytes(), b'never modify')
        (self.root / d.JOURNAL).unlink(); (self.root / d.JOURNAL).write_bytes(original)
        (self.root / d.JOURNAL).chmod(0o600)
        os.link(self.root / d.JOURNAL, self.root / 'test-owned-alias')
        with self.assertRaisesRegex(d.LeaseRefused, 'PRIVATE_REGULAR_FILE'): self.existing()

    def test_live_root_and_lock_replacement_prevents_any_journal_publication(self):
        lease = self.fresh(); before = (self.root / d.JOURNAL).read_bytes()
        (self.root / d.LOCK).rename(self.root / 'test-owned-original-lock')
        replacement = self.root / d.LOCK; replacement.write_bytes(b'own test replacement'); replacement.chmod(0o600)
        with self.assertRaisesRegex(d.LeaseRefused, 'LOCK_PATH_IDENTITY'): lease.checkpoint('CREDENTIALS', False, 'STARTING')
        self.assertEqual((self.root / d.JOURNAL).read_bytes(), before)
        self.assertEqual(replacement.read_bytes(), b'own test replacement')
        with self.assertRaises(BaseExceptionGroup): lease.release()
        self.assertFalse(lease.active)

    def test_postrename_sync_window_lock_drift_is_detected_before_publish_returns(self):
        lease = self.fresh(); sync = os.fsync; replaced = []
        def sync_then_replace(fd):
            sync(fd)
            if fd == lease.fs.root and not replaced:
                (self.root / d.LOCK).rename(self.root / 'test-owned-postsync-lock')
                path = self.root / d.LOCK; path.write_bytes(b'known test replacement'); path.chmod(0o600)
                replaced.append(True)
        with patch.object(os, 'fsync', side_effect=sync_then_replace):
            with self.assertRaisesRegex(d.LeaseRefused, 'LOCK_PATH_IDENTITY_CHANGED'):
                lease.checkpoint('CREDENTIALS', False, 'STARTING')
        self.assertTrue(lease.poisoned); self.assertEqual(replaced, [True])
        self.assertEqual((self.root / d.LOCK).read_bytes(), b'known test replacement')
        lease.release()

    def test_final_read_window_root_drift_is_detected_not_written_through_new_path(self):
        lease = self.fresh(); read = lease.fs.read; changed = []
        old = self.base / 'test-owned-old-instance'
        def read_then_rename():
            result = read()
            if json.loads(result[0])['phase'] == 'CREDENTIALS' and not changed:
                self.root.rename(old); self.root.mkdir(mode=0o700)
                (self.root / 'untouched-marker').write_bytes(b'known test marker')
                changed.append(True)
            return result
        with patch.object(lease.fs, 'read', side_effect=read_then_rename):
            with self.assertRaisesRegex(d.LeaseRefused, 'ANCESTOR_IDENTITY_CHANGED'):
                lease.checkpoint('CREDENTIALS', False, 'STARTING')
        self.assertTrue(lease.poisoned); self.assertEqual(changed, [True])
        self.assertEqual([p.name for p in self.root.iterdir()], ['untouched-marker'])
        lease.release()

    def test_unsafe_paths_existing_roots_ancestors_and_permissions_are_not_repaired(self):
        for root in ('relative', str(self.base / '..' / 'other'), str(self.base / 'a' / 'b'), str(self.base / 'CON')):
            with self.assertRaises(d.LeaseRefused): self.dirs.claim_fresh(root)
        self.root.mkdir(mode=0o700)
        with self.assertRaises(FileExistsError): self.fresh()
        self.assertEqual(list(self.root.iterdir()), [])
        link = self.base / 'base-link'; link.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(OSError): d.PrivateDirectories(str(link)).open_existing(str(link / 'instance'))
        self.base.chmod(0o755)
        with self.assertRaisesRegex(d.LeaseRefused, 'PRIVATE_DIRECTORY'): self.dirs.open_existing(str(self.root))
        self.assertEqual(self.base.stat().st_mode & 0o777, 0o755)
        self.base.chmod(0o700)  # Restore only this test's own temporary object.

    def test_atomic_checkpoints_are_complete_for_concurrent_real_file_reader(self):
        lease = self.fresh(); stop = threading.Event(); samples, failures = [], []
        def read():
            try:
                for _ in range(2048):
                    if stop.is_set(): break
                    samples.append(d._decode((self.root / d.JOURNAL).read_bytes()))
            except BaseException as error: failures.append(error)
        reader = threading.Thread(target=read); reader.start()
        try: complete(lease); lease.release()
        finally: stop.set(); reader.join(timeout=3)
        self.assertFalse(reader.is_alive()); self.assertFalse(failures); self.assertTrue(samples)
        self.assertTrue(all(row['root'] == lease.fs.root_id for row in samples))
        self.assertEqual([row['sequence'] for row in samples], sorted(row['sequence'] for row in samples))
        print('ACTUAL_LINUX: concurrent reader observed complete bounded JSON snapshots only', flush=True)

    def test_real_file_write_sync_and_rename_failures_poison_lease_without_repair(self):
        for operation in ('write', 'fsync', 'replace'):
            with self.subTest(operation=operation):
                root = self.base / ('failure-' + operation)
                lease = self.dirs.claim_fresh(str(root)); self.leases.append(lease)
                before = (root / d.JOURNAL).read_bytes()
                with patch.object(os, operation, side_effect=OSError('injected ' + operation)):
                    with self.assertRaises(OSError): lease.checkpoint('CREDENTIALS', False, 'STARTING')
                self.assertTrue(lease.poisoned)
                self.assertEqual((root / d.JOURNAL).read_bytes(), before)
                with self.assertRaises(d.LeaseRefused): lease.mark_unknown('CREDENTIALS')
                lease.release()
                with self.assertRaises(d.LeaseRefused): self.dirs.open_existing(str(root))

    def test_unknown_partial_duplicate_corrupt_or_oversized_journal_never_recovers(self):
        lease = self.fresh(); lease.mark_unknown('CREDENTIALS'); lease.release()
        with self.assertRaises(d.LeaseRefused): self.existing()
        for raw in (b'{"schema":1,"schema":2}', b'not json', b'x' * (d.LIMIT + 1)):
            (self.root / d.JOURNAL).write_bytes(raw)
            with self.assertRaises(d.LeaseRefused): self.existing()

    def test_strict_phase_order_prevents_ready_skips_and_no_secrets_or_extra_fields_in_journal(self):
        lease = self.fresh()
        with self.assertRaises(d.LeaseRefused): lease.checkpoint('READY_STOPPED', True, 'STOPPED')
        with self.assertRaises(d.LeaseRefused): lease.checkpoint('fake-secret-phase', False, 'STARTING')
        complete(lease); lease.release()
        record = d._decode((self.root / d.JOURNAL).read_bytes())
        self.assertEqual(set(record), {'schema','root','lock','generation','sequence','phase','initialized','runtime','handoff'})

    def test_existing_controller_runs_real_directory_state_machine_with_other_ports_fake(self):
        from scripts.windows import lifecycle
        from .controller import Controller
        from .test_controller import FakeInstallation
        fake = FakeInstallation()
        controller = Controller(self.dirs, fake, fake, database=fake)
        # Real directory state only; runtime identity/DB/process ports remain fake.
        from . import application_readiness as ready
        with patch.object(ready,'require_application_ready'), patch.object(ready,'check_before_running'), patch.object(ready,'activate_application'):
            with patch.object(lifecycle, 'require_setup_readiness'):
                first = controller.create(str(self.root), lambda app: None)
            second = controller.reopen(str(self.root), lambda app: None)
        self.assertEqual((first['runtime'], second['mode']), ('STOPPED_CONFIRMED', 'REOPEN'))
        record = d._decode((self.root / d.JOURNAL).read_bytes())
        self.assertEqual((record['generation'], record['phase'], record['handoff']), (2, 'READY_STOPPED', 'RELEASE_PENDING'))


class WindowsStandInChecks(unittest.TestCase):
    def test_actual_abi_buffer_is_win64_relative_name_not_path_or_ads(self):
        self.assertEqual((w.RenameInfo.RootDirectory.offset, w.RenameInfo.FileNameLength.offset, w.RenameInfo.FileName.offset), (8,16,20))
        data = w.rename_buffer(123, d.JOURNAL, True)
        info = C.cast(data, C.POINTER(w.RenameInfo)).contents
        self.assertEqual((info.RootDirectory, info.ReplaceIfExists), (123, 1))
        raw = C.string_at(C.addressof(data) + 20, info.FileNameLength)
        self.assertEqual(raw.decode('utf-16-le'), d.JOURNAL)
        for name in ('../x', 'a/b', 'C:x', 'CON'):
            with self.assertRaises(Exception): w.rename_buffer(123, name, True)

    def test_relative_ntcreate_flags_exclude_acl_owner_and_lock_sharing(self):
        from types import SimpleNamespace
        captured = []
        def create(handle, access, attributes, io, allocation, attrs, sharing, disposition, options, ea, size):
            C.cast(handle, C.POINTER(C.c_void_p))[0] = 123
            captured.append((access, attributes._obj.RootDirectory, sharing, disposition, options))
            return 0
        api = object.__new__(w.NativeLeaseAPI); api.readonly = SimpleNamespace(ntcreate=create)
        self.assertEqual(api.relative_file(42, d.LOCK, write=True, exclusive=True), 123)
        access, parent, sharing, disposition, options = captured[0]
        self.assertEqual((parent, sharing, disposition), (42, 0, 1))
        self.assertFalse(access & (0x80000 | 0x40000))
        self.assertTrue(options & 0x200000); self.assertTrue(options & 0x40)

    def test_native_durability_gap_refuses_before_any_root_handle_or_mutation(self):
        api = object.__new__(w.NativeLeaseAPI)
        fs = w.WindowsFilesystem('C:\\private', api=api)
        with self.assertRaisesRegex(d.LeaseRefused, 'WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED'):
            fs.acquire('instance', fresh=False)
        self.assertEqual(fs.handles, [])

    def test_native_fresh_pause_precedes_any_backend_call(self):
        from scripts.windows.lifecycle import BoundaryError
        fs = w.WindowsFilesystem('C:\\private', api=object())
        with self.assertRaises(BoundaryError): fs.acquire('instance', fresh=True)
        self.assertEqual(fs.handles, [])

    def test_handle_close_unknown_does_not_retry_and_keeps_lock_last(self):
        from types import SimpleNamespace
        calls = []
        def close(handle):
            calls.append(handle)
            if handle == 3: raise OSError('injected native close unknown')
        fs = w.WindowsFilesystem('C:\\private', api=SimpleNamespace(close=close))
        fs.handles, fs.lock = [1,2,3], 3
        with self.assertRaises(BaseExceptionGroup): fs.close()
        fs.close()
        self.assertEqual(calls, [2,1,3])


if __name__ == '__main__': unittest.main()
