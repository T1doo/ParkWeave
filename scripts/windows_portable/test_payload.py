"""Offline packaging fault injection only; PE fixtures are never executable."""
from contextlib import redirect_stdout, redirect_stderr
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from . import build, entry, payload as p


def pe(names=(), delay=()):
    data = bytearray(2048); data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80); data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', data, 0x84, 0x8664, 1); struct.pack_into('<H', data, 0x94, 240)
    opt = 0x98; struct.pack_into('<H', data, opt, 0x20b); struct.pack_into('<I', data, opt + 108, 16)
    section = opt + 240
    struct.pack_into('<III', data, section + 12, 0x1000, 1536, 512)
    for index, items, start, stride in ((1, names, 512, 20), (13, delay, 768, 32)):
        if not items: continue
        struct.pack_into('<II', data, opt + 112 + index * 8, 0x1000 + start - 512, (len(items) + 1) * stride)
        for i, name in enumerate(items):
            loc = 1152 + index * 16 + i * 96
            if index == 13: struct.pack_into('<I', data, start + i * stride, 1)
            struct.pack_into('<I', data, start + i * stride + (12 if index == 1 else 4), loc - 512 + 0x1000)
            raw = name.encode() + b'\0'; data[loc:loc + len(raw)] = raw
    return bytes(data)


class PayloadChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def directory(self):
        files = {'app/readme.txt': b'actual payload', 'runtime/python/python312._pth': build.PTH}
        for name, data in files.items():
            path = self.root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(data)
        manifest = dict(schema=p.SCHEMA, status='INITIALIZATION_NOT_ENABLED', source_commit='a' * 40, files=p.file_manifest(files))
        (self.root / p.MANIFEST).write_text(json.dumps(manifest))
        return manifest

    def test_integrity_accepts_exact_files_then_rejects_drift_missing_and_extra(self):
        expected = self.directory(); self.assertEqual(p.verify_directory(self.root), expected)
        path = self.root / 'app/readme.txt'; path.write_bytes(b'wrong payload')
        with self.assertRaises(p.PayloadRefused): p.verify_directory(self.root)
        path.unlink()
        with self.assertRaises(p.PayloadRefused): p.verify_directory(self.root)
        path.write_bytes(b'actual payload'); (self.root / 'extra.pth').write_text('import os')
        with self.assertRaises(p.PayloadRefused): p.verify_directory(self.root)

    def test_windows_paths_reject_escaping_ads_devices_and_aliases(self):
        for name in ('../a', '/a', 'C:/a', '//server/a', 'a\\b', 'a:b', 'a/../b',
                     'a//b', 'a./b', 'a /b', 'CON.txt', 'x/Lpt9', 'x/NUL', 'x\x01y'):
            with self.subTest(name=name), self.assertRaises(p.PayloadRefused): p.safe_name(name)
        self.assertEqual(p.safe_name('app/中文说明.txt'), 'app/中文说明.txt')

    def test_archive_rejects_case_collisions_symlinks_and_parent_files(self):
        for rows in ((('A.txt', b'a'), ('a.txt', b'a')), (('a', b'a'), ('a/b', b'b'))):
            path = self.root / ('a' + str(len(list(self.root.iterdir()))) + '.zip')
            with zipfile.ZipFile(path, 'w') as z:
                for name, data in rows: z.writestr(name, data)
            with self.assertRaises(p.PayloadRefused): p.archive_files(path)
        path = self.root / 'link.zip'
        with zipfile.ZipFile(path, 'w') as z:
            i = zipfile.ZipInfo('link'); i.external_attr = 0o120777 << 16; z.writestr(i, 'target')
        with self.assertRaises(p.PayloadRefused): p.archive_files(path)

    def test_directory_rejects_symlink_and_duplicate_manifest_keys(self):
        self.directory(); f = self.root / 'app/readme.txt'; f.unlink(); f.symlink_to(self.root / p.MANIFEST)
        with self.assertRaises(p.PayloadRefused): p.verify_directory(self.root)
        (self.root / p.MANIFEST).write_text('{"schema":1,"schema":2}')
        with self.assertRaises(p.PayloadRefused): p.verify_directory(self.root)

    def test_bounded_archive_and_manifest_are_enforced(self):
        self.directory()
        with patch.object(p, 'MAX_BYTES', 1), self.assertRaises(p.PayloadRefused): p.verify_directory(self.root)
        with self.assertRaises(p.PayloadRefused): p.file_manifest({'A': b'a', 'a': b'b'})

    def test_pe_reads_normal_and_delay_imports_and_rejects_other_architecture(self):
        self.assertEqual(p.pe_imports(pe(('KERNEL32.dll',), ('private.dll',))), ['kernel32.dll', 'private.dll'])
        bad = bytearray(pe()); struct.pack_into('<H', bad, 0x84, 0x14c)
        for raw in (bad, b'not PE', pe()[:250]):
            with self.assertRaises(p.PayloadRefused): p.pe_imports(raw)

    def test_dll_domains_do_not_resolve_from_external_path_or_other_process(self):
        files = {'runtime/python/python.exe': pe(('private.dll',))}
        self.assertEqual(p.dll_closure(files)['unresolved'][0]['dependency'], 'private.dll')
        files['runtime/postgresql/bin/private.dll'] = pe()
        self.assertEqual(p.dll_closure(files)['status'], 'UNRESOLVED')
        files['vendor/unrelated/private.dll'] = pe()
        self.assertEqual(p.dll_closure(files)['status'], 'UNRESOLVED')
        files['runtime/python/private.dll'] = pe()
        self.assertEqual(p.dll_closure(files)['status'], 'PRIVATE_IMPORTS_PRESENT_OS_LOADING_UNVERIFIED')
        result = p.dll_closure({'runtime/python/python.exe': pe(('api-ms-win-fictional-not-real.dll',))})
        self.assertEqual(result['status'], 'UNRESOLVED')
        self.assertEqual(len(result['unverified_api_contracts']), 1)

    def test_domain_dll_conflict_and_delayed_missing_import_refuse(self):
        files = {'vendor/a/x.dll': pe(), 'vendor/b/X.dll': pe(('kernel32.dll',))}
        with self.assertRaises(p.PayloadRefused): p.dll_closure(files)
        result = p.dll_closure({'runtime/python/python.exe': pe(delay=('missing.dll',))})
        self.assertEqual(result['status'], 'UNRESOLVED')

    def test_zip_is_reproducible_and_never_overwrites(self):
        files = {'app/file.txt': b'plain data'}; manifest = {'fixed': True}
        a = self.root / 'a.zip'; b = self.root / 'b.zip'
        self.assertEqual(build.write_zip(a, files, manifest), build.write_zip(b, files, manifest))
        old = a.read_bytes()
        with self.assertRaises(FileExistsError): build.write_zip(a, {}, {})
        self.assertEqual(a.read_bytes(), old)

    def test_entry_reads_original_gate_without_calling_main_or_setup(self):
        path = self.root / 'app/scripts/windows/lifecycle.py'; path.parent.mkdir(parents=True)
        path.write_text("def setup_readiness(): return {'status':'BLOCKED','reason':'OWNER_MUTATION_PAUSED'}\n"
                        "def setup(): raise AssertionError('must not call setup')\n"
                        "def main(): raise AssertionError('must not call main')\n")
        self.assertEqual(entry.readiness(self.root)['reason'], 'OWNER_MUTATION_PAUSED')

    def test_cmd_and_embedded_paths_have_no_system_python_or_site_fallback(self):
        text = (Path(build.__file__).parent / 'ParkWeave.cmd').read_text()
        self.assertIn('setlocal DisableDelayedExpansion', text)
        self.assertIn('"%~dp0runtime\\python\\python.exe" -I -B', text)
        self.assertNotIn('import site', build.PTH.decode())
        self.assertEqual(build.PTH.splitlines(), [b'python312.zip', b'.', b'../../vendor', b'../../launcher', b'../../app/src'])

    def test_assembly_rejects_asset_hash_before_archive_or_source_use(self):
        f = self.root / 'bad.zip'; f.write_bytes(b'corrupt')
        lock = self.root / 'lock.json'
        lock.write_text(json.dumps(dict(schema='parkweave-windows-runtime-assets/1', assets=[dict(
            file='bad.zip', bytes=7, sha256='0' * 64)])))
        def git(args, **kw):
            if args[1] == 'rev-parse': return b'a' * 40 + b'\n'
            if args[1] == 'show':
                name = args[2].split(':', 1)[1]
                if name.endswith('runtime-assets.json'): return lock.read_bytes()
                return (Path(build.__file__).parent / Path(name).name).read_bytes()
            raise AssertionError('must not archive source after bad asset')
        with patch.object(build.subprocess, 'check_output', side_effect=git):
            with self.assertRaisesRegex(p.PayloadRefused, 'ASSET_HASH'): build.assemble(self.root, 'a' * 40, self.root, lock)

    def test_assembly_refuses_noncommit_and_builder_or_lock_drift(self):
        lock = self.root / 'lock.json'; lock.write_text('{"schema":"parkweave-windows-runtime-assets/1","assets":[]}')
        with patch.object(build.subprocess, 'check_output', return_value=b'b' * 40 + b'\n'):
            with self.assertRaisesRegex(p.PayloadRefused, 'SOURCE_COMMIT_REQUIRED'): build.assemble(self.root, 'a' * 40, self.root, lock)
        with patch.object(build.subprocess, 'check_output', side_effect=[b'a' * 40 + b'\n', b'wrong builder']):
            with self.assertRaisesRegex(p.PayloadRefused, 'BUILDER_SOURCE_DRIFT'): build.assemble(self.root, 'a' * 40, self.root, lock)

    def test_full_frozen_fixture_assembly_verifies_and_preserves_original_block(self):
        repo = self.root / 'repo'; repo.mkdir(); assets = self.root / 'assets'; assets.mkdir()
        fixtures = {
            'python.zip': ('python', {'python.exe': pe(('kernel32.dll',)), 'pythonw.exe': pe(),
                'python312.dll': pe(), 'python312.zip': b'fixture-not-a-runtime',
                'python312._pth': b'original fixture', 'LICENSE.txt': b'fixture license'}),
            'postgres.zip': ('postgresql', {'pgsql/bin/postgres.exe': pe(), 'pgsql/bin/initdb.exe': pe(),
                'pgsql/bin/pg_ctl.exe': pe(), 'pgsql/server_license.txt': b'fixture license',
                'pgsql/share/extension/plpgsql.control': b"module_pathname='$libdir/plpgsql'",
                'pgsql/share/snowball_create.sql': b"'$libdir/dict_snowball'",
                'pgsql/lib/plpgsql.dll': pe(('postgres.exe',)), 'pgsql/lib/dict_snowball.dll': pe(('postgres.exe',))}),
            'wheel.whl': ('wheel', {'fixture/__init__.py': b'', 'fixture.dist-info/LICENSE': b'fixture license'})}
        rows = []
        for name, (kind, members) in fixtures.items():
            path = assets / name
            with zipfile.ZipFile(path, 'w') as z:
                for n, data in members.items(): z.writestr(n, data)
            licenses = {n: sha256(data).hexdigest() for n, data in members.items() if 'license' in n.lower()}
            rows.append(dict(file=name, kind=kind, version='FIXTURE_ONLY', url='https://fixture.invalid/' + name,
                bytes=path.stat().st_size, sha256=sha256(path.read_bytes()).hexdigest(), license_files=licenses))
        here = Path(build.__file__).parent; copied = repo / 'scripts/windows_portable'; copied.mkdir(parents=True)
        for name in ('build.py', 'payload.py', 'entry.py', 'ParkWeave.cmd'):
            (copied / name).write_bytes((here / name).read_bytes())
        lock = copied / 'runtime-assets.json'
        lock.write_text(json.dumps(dict(schema='parkweave-windows-runtime-assets/1', assets=rows)))
        for name in ('api.py', 'web.html', 'park_demo_web.html'):
            path = repo / 'src/parkweave' / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text('fixture only')
        path = repo / 'scripts/windows/lifecycle.py'; path.parent.mkdir(parents=True)
        path.write_text("def setup_readiness(): return {'status':'BLOCKED','reason':'OWNER_MUTATION_PAUSED'}\n"
                        "def setup(): raise AssertionError('must not initialize')\n")
        for args in (['init', '-q', '--initial-branch=fixture'], ['add', '.'],
                     ['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'offline fixture']):
            subprocess.run(['git', *args], cwd=repo, check=True, capture_output=True)
        source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
        files, manifest = build.assemble(repo, source, assets, lock)
        self.assertIn('runtime/postgresql/lib/plpgsql.dll', files)
        self.assertIn('runtime/postgresql/lib/dict_snowball.dll', files)
        self.assertFalse(manifest['usable_product']); self.assertEqual(manifest['status'], 'INITIALIZATION_NOT_ENABLED')
        out = self.root / 'candidate.zip'; build.write_zip(out, files, manifest)
        unpacked = self.root / 'unpacked'; unpacked.mkdir()
        with zipfile.ZipFile(out) as z: z.extractall(unpacked)
        self.assertEqual(p.verify_directory(unpacked), manifest)
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('must not run native code')):
            self.assertEqual(entry.readiness(unpacked)['reason'], 'OWNER_MUTATION_PAUSED')
        (copied / 'entry.py').write_text('uncommitted changed launcher')
        again, _ = build.assemble(repo, source, assets, lock)
        self.assertEqual(again['launcher/entry.py'], files['launcher/entry.py'])


if __name__ == '__main__': unittest.main()
