"""Actual private Linux synthetic files/leases only; PE bytes never executed."""
import hashlib
import json
import os
from pathlib import Path
import sys
import struct
import tempfile
import time
import unittest
from unittest.mock import patch

from . import payload, runtime_payload as r, processes as p
from .fixed_directories import FixedPrivateDirectories
from .test_payload import pe as name_only_pe


def pe(names=(),delay=()):
    # Complete bounded lookup tables for this static-symbol consumer. These
    # remain nonexecuted synthetic PE bytes, not Windows loading evidence.
    raw=bytearray(name_only_pe(names,delay))
    for is_delay,items,start,stride in ((False,names,512,20),(True,delay,768,32)):
        for i,_ in enumerate(items):
            offset=1792+(i+(8 if is_delay else 0))*16
            if offset+16>len(raw):raw.extend(b'\0'*(offset+16-len(raw)))
            struct.pack_into('<I',raw,start+i*stride+(16 if is_delay else 0),0x1000+offset-512)
            struct.pack_into('<QQ',raw,offset,(1<<63)|1,0)
    if len(raw)>2048:struct.pack_into('<I',raw,0x98+240+16,len(raw)-512)
    return bytes(raw)

SOURCE = 'a' * 40


@unittest.skipUnless(sys.platform == 'linux', 'real Linux file snapshot only, not native acceptance')
class RuntimePayloadFileChecks(unittest.TestCase):
    def setUp(self):
        self.fd_count = len(os.listdir('/proc/self/fd'))
        self.temp = tempfile.TemporaryDirectory(prefix='parkweave-runtime-payload-')
        self.base = Path(self.temp.name); self.root = self.base / 'instance'
        self.directories = FixedPrivateDirectories(str(self.base)); self.leases = []
        self.lease = self.claim(self.root)
        self.addCleanup(self.finish)
        self.files = {name: pe(('kernel32.dll',)) if name.endswith(('.dll', '.exe')) else b'synthetic frozen share data'
                      for name in r.REQUIRED}
        self.files[r.PG + 'share/postgres.bki'] = b'SYNTHETIC NONEXECUTABLE BKI $libdir/plpgsql'
        self.files[r.PG + 'share/empty.txt'] = b''
        self.write_payload()

    def claim(self, root):
        lease = self.directories.claim_fresh(str(root)); self.leases.append(lease)
        # Synthetic journal phases only, no credentials/database are created.
        lease.checkpoint('CREDENTIALS', False, 'STARTING'); lease.checkpoint('CLUSTER', False, 'STARTING')
        return lease

    def put(self, name, data, root=None):
        root = self.root if root is None else root; path = root / name
        parent = root
        for part in Path(name).parts[:-1]:
            parent /= part; parent.mkdir(mode=0o700, exist_ok=True)
        path.write_bytes(data); path.chmod(0o600)

    def write_manifest(self, manifest):
        raw = json.dumps(manifest, sort_keys=True).encode()
        self.put(payload.MANIFEST, raw); self.digest = hashlib.sha256(raw).hexdigest()

    def write_payload(self):
        for name, data in self.files.items(): self.put(name, data)
        self.write_manifest(dict(schema=payload.SCHEMA, status='INITIALIZATION_NOT_ENABLED', source_commit=SOURCE,
                                 usable_product=False, native_initialization='OWNER_MUTATION_PAUSED',
                                 files=payload.file_manifest(self.files)))

    def guard(self, lease=None, digest=None):
        return r.RuntimePayloadPrerequisite(lease or self.lease, manifest_sha256=digest or self.digest, source_commit=SOURCE)

    def inspect(self, guard=None): return (guard or self.guard()).inspect(self.lease, time.monotonic() + 10)

    def finish(self):
        try:
            for lease in reversed(self.leases):
                if lease.active: lease.release()
        finally: self.temp.cleanup()
        self.assertEqual(len(os.listdir('/proc/self/fd')), self.fd_count)

    def test_actual_snapshot_covers_pg_share_bin_lib_and_never_reads_mutable_contents_or_activates(self):
        for name in ('data/private.txt', 'secrets/private.txt', 'files/private.txt'):
            self.put(name, b'SYNTHETIC MUTABLE SENTINEL')
        read_names = []; original = p.PinnedPayloadFile.__init__
        def record(pin, lease, spec): read_names.append(spec.relative_executable); original(pin, lease, spec)
        with patch.object(p.PinnedPayloadFile, '__init__', record): result = self.inspect()
        self.assertEqual(set(read_names), set(self.files) | {payload.MANIFEST})
        self.assertEqual(result['runtime_files'], len(self.files)); self.assertFalse(result['activation_allowed'])
        self.assertEqual(result['native_loading'], 'NOT_ACCEPTED')
        self.assertEqual(result['bootstrap_modules'], [r.PG + 'lib/plpgsql.dll'])
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'NATIVE_RUNTIME_LOADING_NOT_ACCEPTED'):
            self.guard().require_for_cluster(self.lease, time.monotonic() + 10)
        native_guard = self.guard()
        with patch.object(r.os, 'name', 'nt'), self.assertRaisesRegex(r.RuntimePayloadRefused, 'NATIVE_PAYLOAD_ENUMERATION_NOT_ACCEPTED'):
            self.inspect(native_guard)

    def test_first_postgres_pin_refuses_actual_fifo_without_waiting_for_writer(self):
        target = self.root / (r.PG + 'bin/postgres.exe'); target.unlink(); os.mkfifo(target, 0o600)
        original = os.open; observed = []
        def guarded(name, flags, *args, **kwargs):
            if name == 'postgres.exe':
                self.assertTrue(flags & os.O_NONBLOCK, 'refuse before attempting a potentially blocking FIFO open')
                observed.append('NONBLOCKING_LEAF_OPEN')
            return original(name, flags, *args, **kwargs)
        with patch.object(os, 'open', guarded), self.assertRaises(p.ProcessRefused): self.inspect()
        self.assertEqual(observed, ['NONBLOCKING_LEAF_OPEN'])

    def test_missing_extra_drift_link_and_alias_actual_files_are_refused(self):
        target = self.root / (r.PG + 'share/pg_ident.conf.sample'); original = target.read_bytes()
        target.unlink()
        with self.assertRaises((r.RuntimePayloadRefused, p.ProcessRefused, FileNotFoundError)): self.inspect()
        self.put(r.PG + 'share/pg_ident.conf.sample', original)
        self.put(r.PG + 'share/pg_ident.conf.sample', b'drift')
        with self.assertRaises(p.ProcessRefused): self.inspect()
        self.put(r.PG + 'share/pg_ident.conf.sample', original)
        extra = r.PG + 'bin/unlisted.dll'; self.put(extra, pe())
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'UNEXPECTED_FILE'): self.inspect()
        (self.root / extra).unlink()
        target.unlink(); target.symlink_to(self.root / payload.MANIFEST)
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'RUNTIME_LINK'): self.inspect()
        target.unlink(); self.put(r.PG + 'share/pg_ident.conf.sample', original)
        hardlink = self.root / 'owned-test-hardlink'; os.link(target, hardlink)
        with self.assertRaises(p.ProcessRefused): self.inspect()
        hardlink.unlink()
        self.put(r.PG + 'bin/POSTGRES.EXE', self.files[r.PG + 'bin/postgres.exe'])
        with self.assertRaises(r.RuntimePayloadRefused): self.inspect()

    def test_external_manifest_and_source_scope_pins_cannot_be_self_repaired(self):
        old = self.digest; manifest = json.loads((self.root / payload.MANIFEST).read_bytes())
        manifest['source_commit'] = 'b' * 40; self.write_manifest(manifest)
        with self.assertRaises(p.ProcessRefused): self.inspect(self.guard(digest=old))
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'SOURCE_OR_SCOPE'): self.inspect()
        manifest['source_commit'] = SOURCE; manifest['usable_product'] = True; self.write_manifest(manifest)
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'SOURCE_OR_SCOPE'): self.inspect()

    def test_native_capability_cannot_be_forged_or_replace_posix_pin_policy(self):
        from .native_runtime_staging import NativeRuntimeInstallation
        from .controller import CandidateRefused
        forged = object.__new__(NativeRuntimeInstallation)
        # Refuse before native queries, reads, or any purported capability data.
        with self.assertRaises(CandidateRefused):
            r.RuntimePayloadPrerequisite(self.lease,manifest_sha256=self.digest,
                source_commit=SOURCE,native_installation=forged)
        with self.assertRaises(CandidateRefused):
            forged.inspect_pg_static(self.lease,dict(source_commit=SOURCE,manifest_sha256=self.digest),time.monotonic()+5)
        with self.assertRaisesRegex(r.RuntimePayloadRefused,'ORIGINAL_NATIVE_INSTALLATION_REQUIRED'):
            r.RuntimePayloadPrerequisite(self.lease,manifest_sha256=self.digest,
                source_commit=SOURCE,native_installation={'files':self.files})

    def test_static_delayed_import_and_bootstrap_dynamic_missing_are_not_closed_by_manifest_claim(self):
        self.files[r.PG + 'bin/postgres.exe'] = pe(delay=('missing.dll',)); self.write_payload()
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'STATIC_IMPORT_UNRESOLVED'): self.inspect()
        self.files[r.PG + 'bin/postgres.exe'] = pe(('kernel32.dll',))
        self.files[r.PG + 'share/postgres.bki'] += b' $libdir/unshipped_conversion'; self.write_payload()
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'DYNAMIC_BOOTSTRAP_MISSING'): self.inspect()

    def test_platform_requirements_remain_visible_without_becoming_private_missing_or_loading_permission(self):
        self.files[r.PG + 'bin/postgres.exe'] = pe(('vcruntime140.dll','msvcp140.dll',
            'api-ms-win-crt-runtime-l1-1-0.dll','pdh.dll'))
        self.write_payload()
        report = self.inspect()
        self.assertEqual(report['static_loading'],'STATIC_PLATFORM_REQUIREMENTS_UNVERIFIED')
        self.assertEqual(len(report['unresolved']),4)
        self.assertTrue(all(row['observed'] is False for row in report['platform_requirements']))
        self.assertEqual(report['missing_private_dependencies'],[])
        self.assertFalse(report['activation_allowed'])
        with self.assertRaisesRegex(r.RuntimePayloadRefused,'NATIVE_RUNTIME_LOADING_NOT_ACCEPTED'):
            self.guard().require_for_cluster(self.lease,time.monotonic()+10)
        self.assertNotIn('vcruntime140.dll',payload.OS_DLLS)
        self.files[r.PG + 'bin/postgres.exe'] = pe(('api-ms-win-madeup.dll',))
        self.write_payload()
        with self.assertRaisesRegex(r.RuntimePayloadRefused,'PG_STATIC_IMPORT_UNRESOLVED'):self.inspect()

    def test_same_lease_state_and_ancestor_names_must_still_match_before_return(self):
        other = self.claim(self.base / 'other')
        guard = self.guard()
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'SAME_PAYLOAD_LEASE'):
            guard.inspect(other, time.monotonic() + 10)
        original = payload.dll_closure
        def move(data):
            (self.root / 'runtime' / 'postgresql').rename(self.root / 'runtime' / 'moved')
            return original(data)
        with patch.object(payload, 'dll_closure', side_effect=move), self.assertRaises(FileNotFoundError): self.inspect()
        (self.root / 'runtime' / 'moved').rename(self.root / 'runtime' / 'postgresql')
        guard = self.guard(); self.lease.checkpoint('CREATE_SCHEMA', False, 'STARTING')
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'STATE_CHANGED'): self.inspect(guard)

    def test_expired_clock_and_failure_poison_do_not_silently_retry_payload(self):
        guard = self.guard()
        with patch.object(r, 'PinnedPayloadFile', side_effect=AssertionError('expired read')):
            with self.assertRaisesRegex(r.RuntimePayloadRefused, 'DEADLINE'):
                guard.inspect(self.lease, time.monotonic() - 1)
        with self.assertRaisesRegex(r.RuntimePayloadRefused, 'SAME_PAYLOAD_LEASE'): self.inspect(guard)

    def test_real_pinned_data_read_does_not_relax_executable_or_catalogue_admission(self):
        name = r.PG + 'share/empty.txt'; spec = p.PayloadFileSpec(name, hashlib.sha256(b'').hexdigest(), 0)
        pin = p.PinnedPayloadFile(self.lease, spec)
        try: self.assertEqual(pin.read_bytes(), b'')
        finally: pin.close()
        with self.assertRaises(p.ProcessRefused): p.PrivateProcessAdapter(self.lease, {'not_executable': spec})
        name = r.PG + 'share/postgres.bki'; raw = self.files[name]
        with self.assertRaises(p.ProcessRefused):
            p.PinnedExecutable(self.lease, p.Command(name, hashlib.sha256(raw).hexdigest(), len(raw)))

    def test_read_and_close_double_failure_preserves_both_without_retry_or_fd_leak(self):
        name = r.PG + 'share/pg_ident.conf.sample'; self.put(name, b'drift')
        original = p.PinnedPayloadFile.close; calls = []
        def close(pin):
            original(pin)
            if pin.command.relative_executable == payload.MANIFEST:
                calls.append(pin.command.relative_executable); raise OSError('SYNTHETIC_CLOSE_UNKNOWN_AFTER_CLOSE')
        guard = self.guard()
        with patch.object(p.PinnedPayloadFile, 'close', close), self.assertRaises(BaseExceptionGroup) as failure:
            self.inspect(guard)
        self.assertIsInstance(failure.exception.exceptions[0], p.ProcessRefused)
        self.assertIsInstance(failure.exception.exceptions[1], OSError)
        self.assertEqual(calls, [payload.MANIFEST]); self.assertTrue(guard.failed)


if __name__ == '__main__': unittest.main()
