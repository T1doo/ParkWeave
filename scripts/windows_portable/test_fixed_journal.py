"""Actual private fixed-file IO and lease transitions; no PG/Windows execution."""
import errno
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from . import fixed_journal as j
from .directories import LeaseRefused, PrivateDirectories
from .fixed_directories import FixedPrivateDirectories, FixedPosixFilesystem, FIXED_JOURNAL


def ready_stopped(lease):
    for phase in ('CREDENTIALS', 'CLUSTER', 'CREATE_SCHEMA', 'ROLES', 'SESSIONS', 'SEED', 'CONFIG', 'VERIFY_FILES', 'VERIFY_DATABASE'):
        lease.checkpoint(phase, False, 'STARTING')
    lease.checkpoint('READY', True, 'STOPPED')
    lease.checkpoint('APPLICATION', True, 'STARTING')
    lease.checkpoint('RUNNING', True, 'RUNNING')
    lease.checkpoint('READY_STOPPED', True, 'STOPPED')


@unittest.skipUnless(sys.platform == 'linux', 'real Linux fixed-file IO only')
class ActualFixedJournalChecks(unittest.TestCase):
    def setUp(self):
        self.fds = len(os.listdir('/proc/self/fd'))
        self.temp = tempfile.TemporaryDirectory(prefix='parkweave-fixed-journal-')
        self.base = Path(self.temp.name); self.root = self.base / 'instance'
        self.directories = FixedPrivateDirectories(str(self.base)); self.leases = []
        self.addCleanup(self.finish)

    def finish(self):
        errors = []
        for lease in reversed(self.leases):
            if lease.active:
                try: lease.release()
                except BaseException as error: errors.append(error)
        self.temp.cleanup()
        self.assertEqual(len(os.listdir('/proc/self/fd')), self.fds)
        if errors: raise BaseExceptionGroup('test own fixture cleanup failed', errors)

    def claim(self):
        lease = self.directories.claim_fresh(str(self.root)); self.leases.append(lease)
        return lease

    def reopen(self):
        lease = self.directories.open_existing(str(self.root)); self.leases.append(lease)
        return lease

    def stopped(self):
        lease = self.claim(); ready_stopped(lease); lease.release()
        return self.root / FIXED_JOURNAL

    def test_actual_fixed_inode_full_flow_handoff_and_reopen_without_rename(self):
        lease = self.claim(); inode = lease.fs.identity(); before = set(self.root.iterdir())
        with patch.object(os, 'replace', side_effect=AssertionError('fixed journal rename')), \
             patch.object(os, 'rename', side_effect=AssertionError('fixed journal rename')), \
             patch.object(os, 'pwrite', wraps=os.pwrite) as writes, \
             patch.object(os, 'pread', wraps=os.pread) as reads:
            ready_stopped(lease)
            self.assertEqual(lease.fs.identity(), inode)
            self.assertEqual(lease.fs.length(), 8192)
            lease.release()
            reopened = self.reopen()
            self.assertEqual(reopened.record['generation'], 2)
            self.assertEqual(reopened.record['handoff'], 'OWNED')
            self.assertEqual(reopened.fs.identity(), inode)
            reopened.checkpoint('CLUSTER', True, 'STARTING')
            reopened.checkpoint('VERIFY_DATABASE', True, 'STARTING')
            reopened.checkpoint('READY', True, 'STOPPED')
        self.assertTrue(writes.call_args_list); self.assertTrue(reads.call_args_list)
        self.assertTrue(all(len(call.args[1]) == 4096 and call.args[2] in (0,4096) for call in writes.call_args_list))
        self.assertTrue(all(call.args[1] == 4096 and call.args[2] in (0,4096) for call in reads.call_args_list))
        self.assertEqual(set(self.root.iterdir()), before)
        print('ACTUAL_FIXED: same held inode/8192 bytes across all phases, release and gen2 OWNED; zero rename', flush=True)

    def test_same_lease_contender_is_rejected_before_io_and_cannot_close_owner(self):
        lease = self.claim(); entered, resume = threading.Event(), threading.Event()
        original, errors = lease.fs.flush_file, []
        def paused_flush():
            entered.set()
            if not resume.wait(2): raise RuntimeError('own test thread deadline')
            original()
        def worker():
            try: lease.checkpoint('CREDENTIALS',False,'STARTING')
            except BaseException as error: errors.append(error)
        with patch.object(lease.fs,'flush_file',side_effect=paused_flush):
            thread = threading.Thread(target=worker); thread.start()
            try:
                self.assertTrue(entered.wait(2))
                with self.assertRaisesRegex(LeaseRefused,'FIXED_LEASE_OPERATION_BUSY'): lease.status()
                with self.assertRaisesRegex(LeaseRefused,'FIXED_LEASE_OPERATION_BUSY'): lease.release()
                self.assertTrue(lease.active)
            finally:
                resume.set();thread.join(3)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertFalse(lease.poisoned);self.assertEqual(lease.status(),'CREDENTIALS')

    def test_same_thread_public_reentry_from_flush_cannot_close_or_mutate_owner(self):
        lease = self.claim(); original = lease.fs.flush_file; rejected = []
        def flush_callback():
            with patch.object(lease.fs,'read',side_effect=AssertionError('public reentry IO')):
                for name,args in (('status',()),('release',()),('checkpoint',('CLUSTER',False,'STARTING')),('mark_unknown',('RUNNING',))):
                    with self.assertRaisesRegex(LeaseRefused,'FIXED_LEASE_OPERATION_BUSY'):
                        getattr(lease,name)(*args)
                    rejected.append(name)
            self.assertTrue(lease.active); self.assertFalse(lease.poisoned)
            original()
        with patch.object(lease.fs,'flush_file',side_effect=flush_callback):
            lease.checkpoint('CREDENTIALS',False,'STARTING')
        self.assertEqual(rejected,['status','release','checkpoint','mark_unknown'])
        self.assertEqual(lease.status(),'CREDENTIALS')

    def test_direct_private_verify_also_guards_actual_process_pin_call_path(self):
        lease = self.claim(); original = lease.fs.read; rejected = []
        def read_callback():
            for name,args in (('release',()),('status',()),('checkpoint',('CREDENTIALS',False,'STARTING')),('mark_unknown',('RUNNING',))):
                with self.assertRaisesRegex(LeaseRefused,'FIXED_LEASE_OPERATION_BUSY'):
                    getattr(lease,name)(*args)
                rejected.append(name)
            return original()
        with patch.object(lease.fs,'read',side_effect=read_callback):
            lease._verify()  # Same direct entry used by PinnedExecutable.
        self.assertEqual(rejected,['release','status','checkpoint','mark_unknown'])
        self.assertTrue(lease.active);self.assertFalse(lease.poisoned)
        self.assertEqual(lease.status(),'NEW')

    def test_initial_write_failure_preserves_partial_file_without_automatic_initialization(self):
        original = os.pwrite
        def partial(fd, raw, offset): return original(fd, raw[:257], offset)
        with patch.object(os, 'pwrite', side_effect=partial):
            with self.assertRaises(LeaseRefused): self.claim()
        file = self.root / FIXED_JOURNAL
        self.assertEqual(file.stat().st_size, 257); old = file.read_bytes()
        with self.assertRaises(LeaseRefused): self.reopen()
        with self.assertRaises(FileExistsError): self.claim()
        self.assertEqual(file.read_bytes(), old)

    def test_short_checkpoint_writes_both_slot_directions_poison_without_repair(self):
        lease = self.claim(); original = os.pwrite
        for phase in ('CREDENTIALS', 'CLUSTER'):
            # Separate owned instance per direction: test-only construct a new
            # canonical fixture after observing the previous poisoned artifact.
            if phase == 'CLUSTER':
                if lease.active: lease.release()
                self.root = self.base / 'second'; lease = self.claim()
                lease.checkpoint('CREDENTIALS', False, 'STARTING')
            expected_offset = 0 if phase == 'CREDENTIALS' else j.SLOT
            before = (self.root / FIXED_JOURNAL).read_bytes(); seen = []
            def short(fd, raw, offset):
                seen.append(offset); return original(fd, raw[:257], offset)
            with patch.object(os, 'pwrite', side_effect=short):
                with self.assertRaises(LeaseRefused): lease.checkpoint(phase, False, 'STARTING')
            self.assertEqual(seen, [expected_offset]); self.assertTrue(lease.poisoned)
            after = (self.root / FIXED_JOURNAL).read_bytes()
            self.assertNotEqual(after, before)
            with self.assertRaises(LeaseRefused): j.pair(after)
            lease.release()
            with self.assertRaises(LeaseRefused): self.reopen()
            self.assertEqual((self.root / FIXED_JOURNAL).read_bytes(), after)

    def test_torn_new_owned_cannot_fall_back_to_old_release_pending(self):
        file = self.stopped(); before = file.read_bytes(); original = os.pwrite
        def partial(fd, raw, offset): return original(fd, raw[:257], offset)
        with patch.object(os, 'pwrite', side_effect=partial):
            with self.assertRaises(LeaseRefused): self.reopen()
        after = file.read_bytes(); self.assertNotEqual(after, before)
        with self.assertRaises(LeaseRefused): self.reopen()
        self.assertEqual(file.read_bytes(), after)
        print('ACTUAL_FIXED: torn new OWNED acquisition retained and old PENDING not replayed', flush=True)

    def test_flush_failure_retains_bytes_and_unknown_stays_poisoned(self):
        lease = self.claim(); original = os.fsync
        def failed(fd):
            if fd == lease.fs.journal: raise OSError(errno.EIO, 'injected file flush failure')
            return original(fd)
        with patch.object(os, 'fsync', side_effect=failed):
            with self.assertRaises(OSError): lease.checkpoint('CREDENTIALS', False, 'STARTING')
        self.assertTrue(lease.poisoned)
        current = (self.root / FIXED_JOURNAL).read_bytes()
        with self.assertRaises(LeaseRefused): lease.status()
        lease.release()
        self.assertEqual((self.root / FIXED_JOURNAL).read_bytes(), current)
        with self.assertRaises(LeaseRefused): self.reopen()

    def test_read_failure_and_short_read_poison_even_when_bytes_unchanged(self):
        for mode in ('error', 'short'):
            if mode == 'short': self.root = self.base / 'second'
            lease = self.claim(); original = os.pread
            def read(fd, count, offset):
                if mode == 'error': raise OSError(errno.EIO, 'injected read error')
                return original(fd, count - 1, offset)
            with patch.object(os, 'pread', side_effect=read):
                with self.assertRaises((OSError, LeaseRefused)): lease.status()
            self.assertTrue(lease.poisoned)
            with self.assertRaises(LeaseRefused): lease.checkpoint('CREDENTIALS', False, 'STARTING')
            lease.release()

    def test_final_read_failure_after_flush_preserves_unacknowledged_owned_state(self):
        lease = self.claim(); original = lease.fs.flush_file
        def flushed_then_bad_read():
            original(); lease.fs.read_at = lambda *args: (_ for _ in ()).throw(OSError(errno.EIO, 'injected postflush read error'))
        with patch.object(lease.fs, 'flush_file', side_effect=flushed_then_bad_read):
            with self.assertRaises(OSError): lease.checkpoint('CREDENTIALS', False, 'STARTING')
        self.assertTrue(lease.poisoned); lease.release()
        self.assertEqual(j.pair((self.root / FIXED_JOURNAL).read_bytes())[0]['phase'], 'CREDENTIALS')
        with self.assertRaises(LeaseRefused): self.reopen()

    def test_missing_names_are_never_recreated_and_old_v1_is_not_migrated(self):
        for missing in (FIXED_JOURNAL, '.parkweave-entry.lock'):
            self.root = self.base / ('journal' if missing == FIXED_JOURNAL else 'lock')
            self.stopped(); (self.root / missing).unlink()  # Own fixture fault only.
            before = set(self.root.iterdir())
            with self.assertRaises(FileNotFoundError): self.reopen()
            self.assertEqual(set(self.root.iterdir()), before)
        self.root = self.base / 'v1'
        old = PrivateDirectories(str(self.base)).claim_fresh(str(self.root)); ready_stopped(old); old.release()
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        with self.assertRaises(FileNotFoundError): self.reopen()
        self.assertEqual({p.name: p.read_bytes() for p in self.root.iterdir()}, before)

    def test_inode_swap_and_symlink_refuse_and_poison_original_lease(self):
        for mode in ('replace', 'symlink'):
            if mode == 'symlink': self.root = self.base / 'second'
            lease = self.claim(); file = self.root / FIXED_JOURNAL; saved = self.root / 'own-saved'
            file.rename(saved)
            if mode == 'replace': file.write_bytes(saved.read_bytes()); file.chmod(0o600)
            else: file.symlink_to(saved)
            with self.assertRaises(LeaseRefused): lease.status()
            self.assertTrue(lease.poisoned); lease.release()

    def test_illegal_state_generation_schema_and_canonical_bodies_refused_on_real_file(self):
        file = self.stopped(); original = file.read_bytes(); old, newest = j.pair(original)
        for change in ({'phase':'NEW'}, {'generation': old['generation'] + 2}, {'initialized':False}, {'schema':'unknown'}, {'journal':[1,999]}, {'phase':'RUNNING','runtime':'RUNNING','handoff':'OWNED'}):
            mutated = {**old, **change}
            # Recompute full hash/header/footer deliberately: valid checksum is
            # insufficient for illegal state/version/transition acceptance.
            raw = j.encode(mutated)
            head = j.HEADER.pack(b'PWLJv001',1,newest,mutated['generation'],mutated['sequence'],len(raw),hashlib.sha256(raw).digest(),j.parse_slot(original[newest*j.SLOT:(newest+1)*j.SLOT],newest)[1],bytes(28))
            slot = head + raw + bytes(j.SLOT - 256 - len(raw)) + head
            candidate = original[:newest*j.SLOT] + slot + original[(newest+1)*j.SLOT:]
            file.write_bytes(candidate)
            with self.assertRaises(LeaseRefused): self.reopen()
            self.assertEqual(file.read_bytes(), candidate)
        file.write_bytes(original)
        for raw in (b'{"schema":1,"schema":1}', b' '+j.encode(old)):
            with self.assertRaises(LeaseRefused): j.decode(raw)

    def test_real_competitor_busy_and_crash_after_new_generation_is_not_reopenable(self):
        lease = self.claim(); ready_stopped(lease)
        code = """import sys,os
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[1]+'/src')
from scripts.windows_portable.fixed_directories import FixedPrivateDirectories
try: x=FixedPrivateDirectories(sys.argv[2]).open_existing(sys.argv[3])
except BlockingIOError: print('BUSY',flush=True);sys.exit(23)
print('OWNED',x.record['generation'],flush=True);os._exit(17)
"""
        from parkweave.process_env import minimal_environment
        args = [sys.executable,'-I','-B','-c',code,str(Path(__file__).resolve().parents[2]),str(self.base),str(self.root)]
        def run():
            child = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=minimal_environment(os.environ))
            try: returncode = child.wait(timeout=5)
            except BaseException:
                child.terminate()
                try: child.wait(timeout=2)
                except subprocess.TimeoutExpired: child.kill();child.wait(timeout=2)
                raise
            finally:
                stdout,stderr = child.communicate(timeout=1)
            self.assertEqual(stderr,b'')
            return returncode,stdout.decode('ascii').strip()
        self.assertEqual(run(),(23,'BUSY'))
        lease.release()
        self.assertEqual(run(),(17,'OWNED 2'))
        with self.assertRaises(LeaseRefused): self.reopen()
        print('ACTUAL_FIXED: separate child BUSY while held; later gen2 OWNED os._exit17 blocks reopen',flush=True)

    def test_release_close_unknown_is_completed_only_by_new_real_acquisition(self):
        lease = self.claim(); ready_stopped(lease); original = os.close
        lock = lease.fs.lock
        def closed_then_error(fd):
            original(fd)
            if fd == lock: raise OSError(errno.EIO,'injected close result unknown')
        with patch.object(os,'close',side_effect=closed_then_error):
            with self.assertRaises(BaseExceptionGroup): lease.release()
        self.assertFalse(lease.active)
        reopened = self.reopen()
        self.assertEqual(reopened.record['generation'],2)
        self.assertEqual(reopened.record['handoff'],'OWNED')


class FixedContractChecks(unittest.TestCase):
    def test_every_partial_prefix_never_replays_old_pending_after_any_change(self):
        ids = dict(schema=j.SCHEMA,root=[1,2],lock=[1,3],journal=[1,4])
        older = dict(**ids,generation=1,sequence=20,phase='READY_STOPPED',initialized=True,runtime='STOPPED',handoff='OWNED')
        pending = {**older,'sequence':21,'handoff':'RELEASE_PENDING'}
        slot1 = j.slot_bytes(older,1,bytes(32)); slot0 = j.slot_bytes(pending,0,hashlib.sha256(slot1).digest())
        original = slot0+slot1; self.assertEqual(j.pair(original)[0],pending)
        owned = {**pending,'sequence':22,'generation':2,'handoff':'OWNED'}
        replacement = j.slot_bytes(owned,1,hashlib.sha256(slot0).digest())
        for count in range(1,j.SLOT):
            torn = slot0 + replacement[:count] + slot1[count:]
            if torn == original: continue  # No changed byte, no acquisition ack.
            try: observed,_ = j.pair(torn)
            except LeaseRefused: continue
            self.assertEqual(observed,owned)  # Full effective new bytes, still OWNED.
        print('CODEC_ONLY: all4095 partial slot prefixes checked, no changed-byte rollback to old PENDING',flush=True)

    def test_native_windows_fixed_io_retains_original_durability_preflight(self):
        from .fixed_windows_journal import FixedWindowsFilesystem
        class API:
            def require_directory_durability(self): raise LeaseRefused('WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED')
        fs = FixedWindowsFilesystem('C:\\private',api=API())
        with self.assertRaisesRegex(LeaseRefused,'WINDOWS_DIRECTORY_DURABILITY_NOT_ACCEPTED'):
            fs.acquire('instance',fresh=False)
        self.assertEqual(fs.handles,[]); self.assertIsNone(fs.journal)


if __name__ == '__main__': unittest.main()
