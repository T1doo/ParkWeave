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


# Product packaging contract, independent of the builder's selection logic.
RUNTIME_MODULES = (
    '__init__.py', 'application_readiness.py', 'cluster_processes.py', 'controller.py',
    'credential_envelope.py', 'directories.py', 'endpoint_plan.py', 'fixed_directories.py',
    'fixed_journal.py', 'fixed_secret_store.py', 'fixed_store_security.py', 'fixed_windows_journal.py',
    'initialize.py', 'instance_processes.py', 'isolated_pipe.py', 'payload.py', 'polling_database.py',
    'processes.py', 'runtime_payload.py', 'windows_directory_handles.py', 'windows_endpoint.py',
    'windows_process_handles.py', 'windows_user_protection.py',
)
JOB_MODULES = ('owned_job.py', 'job_stop_observation.py')


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
                     'a//b', 'a./b', 'a /b', 'CON.txt', 'x/Lpt9', 'x/NUL', 'x\x01y',
                     'x/CONIN$', 'x/CONOUT$', 'COM¹.txt', 'LPT².log', 'x/com³'):
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
        self.assertEqual(build.PTH.splitlines(), [b'python312.zip', b'.', b'../../vendor', b'../../launcher',
                                                b'../../app/src', b'../../app'])

    def test_assembly_rejects_asset_hash_before_archive_or_source_use(self):
        f = self.root / 'python-3.12.10-embed-amd64.zip'; f.write_bytes(b'corrupt')
        lock = self.root / 'lock.json'
        lock.write_text(json.dumps(dict(schema='parkweave-windows-runtime-assets/1', assets=[dict(
            file=f.name, kind='python', version='3.12.10', bytes=7, sha256='0' * 64)])))
        def git(args, **kw):
            if args[1] == 'rev-parse': return b'a' * 40 + b'\n'
            if args[1] == 'show':
                name = args[2].split(':', 1)[1]
                if name.endswith('runtime-assets.json'): return lock.read_bytes()
                if name == 'pyproject.toml': return b'[project]\nrequires-python = ">=3.12,<3.13"\n'
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

    def assembly_fixture(self, version='3.12.10', wheel_tag='py3-none-any', *,
                         internal_tag=None, requires_python='>=3.9', pure=True, extra_python=None,
                         app_requires_python='>=3.12,<3.15'):
        repo = self.root / 'repo'; repo.mkdir(); assets = self.root / 'assets'; assets.mkdir()
        (repo / 'pyproject.toml').write_text('[project]' + chr(10) + 'requires-python = "' + app_requires_python + '"' + chr(10), encoding='utf-8')
        stem = 'python' + ''.join(version.split('.')[:2])
        wheel_name = 'fixture-1.0-' + wheel_tag + '.whl'
        fixtures = {
            'python-' + version + '-embed-amd64.zip': ('python', {
                'python.exe': pe(('kernel32.dll',)), 'pythonw.exe': pe(),
                stem + '.dll': pe(), stem + '.zip': b'fixture-not-a-runtime',
                stem + '._pth': b'original fixture', 'LICENSE.txt': b'fixture license'}),
            'postgres.zip': ('postgresql', {'pgsql/bin/postgres.exe': pe(), 'pgsql/bin/initdb.exe': pe(),
                'pgsql/bin/pg_ctl.exe': pe(), 'pgsql/server_license.txt': b'fixture license',
                'pgsql/share/extension/plpgsql.control': b"module_pathname='$libdir/plpgsql'",
                'pgsql/share/snowball_create.sql': b"'$libdir/dict_snowball'",
                'pgsql/lib/plpgsql.dll': pe(('postgres.exe',)), 'pgsql/lib/dict_snowball.dll': pe(('postgres.exe',))}),
            wheel_name: ('wheel', {'fixture/__init__.py': b'', 'fixture-1.0.dist-info/LICENSE': b'fixture license',
                'fixture-1.0.dist-info/WHEEL': ('Wheel-Version: 1.0\nRoot-Is-Purelib: ' +
                    str(pure).lower() + '\nTag: ' + (internal_tag or wheel_tag) + '\n').encode(),
                'fixture-1.0.dist-info/METADATA': ('Metadata-Version: 2.4\nName: fixture\nVersion: 1.0\n' +
                    'Requires-Python: ' + requires_python + '\n\n').encode()})}
        fixtures['python-' + version + '-embed-amd64.zip'][1].update(extra_python or {})
        rows = []
        for name, (kind, members) in fixtures.items():
            path = assets / name
            with zipfile.ZipFile(path, 'w') as z:
                for n, data in members.items(): z.writestr(n, data)
            licenses = {n: sha256(data).hexdigest() for n, data in members.items() if 'license' in n.lower()}
            rows.append(dict(file=name, kind=kind, version=version if kind == 'python' else '1.0',
                url='https://fixture.invalid/' + name,
                bytes=path.stat().st_size, sha256=sha256(path.read_bytes()).hexdigest(), license_files=licenses))
        here = Path(build.__file__).parent; copied = repo / 'scripts/windows_portable'; copied.mkdir(parents=True)
        for name in set(RUNTIME_MODULES) | {'build.py', 'entry.py', 'ParkWeave.cmd'}:
            (copied / name).write_bytes((here / name).read_bytes())
        job_dir = repo / 'scripts/windows_ci'; job_dir.mkdir()
        for name in JOB_MODULES:
            (job_dir / name).write_bytes((here.parent / 'windows_ci' / name).read_bytes())
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
        return repo, assets, lock, source

    def test_full_frozen_fixture_assembly_verifies_and_preserves_original_block(self):
        repo, assets, lock, source = self.assembly_fixture()
        copied = repo / 'scripts/windows_portable'
        files, manifest = build.assemble(repo, source, assets, lock)
        source_names = tuple('scripts/windows_portable/' + n for n in RUNTIME_MODULES) + tuple(
            'scripts/windows_ci/' + n for n in JOB_MODULES)
        for name in source_names:
            frozen = subprocess.check_output(['git', 'show', source + ':' + name], cwd=repo)
            self.assertEqual(files['app/' + name], frozen)
            self.assertEqual(manifest['files']['app/' + name]['sha256'], sha256(frozen).hexdigest())
        self.assertEqual({n for n in files if n.startswith('app/scripts/windows_portable/')},
                         {'app/scripts/windows_portable/' + n for n in RUNTIME_MODULES})
        self.assertEqual({n for n in files if n.startswith('app/scripts/windows_ci/')},
                         {'app/scripts/windows_ci/' + n for n in JOB_MODULES})
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
        (copied / 'controller.py').write_text('uncommitted changed controller')
        again, _ = build.assemble(repo, source, assets, lock)
        self.assertEqual(again['launcher/entry.py'], files['launcher/entry.py'])
        self.assertEqual(again['app/scripts/windows_portable/controller.py'],
                         files['app/scripts/windows_portable/controller.py'])

    def test_locked_314_layout_is_selected_without_312_fallback(self):
        repo, assets, lock, source = self.assembly_fixture('3.14.9', 'cp314-cp314-win_amd64', pure=False)
        files, manifest = build.assemble(repo, source, assets, lock)
        self.assertEqual(files['runtime/python/python314._pth'],
                         b'python314.zip\n.\n../../vendor\n../../launcher\n../../app/src\n../../app\n')
        self.assertIn('runtime/python/python314.dll', files)
        self.assertFalse(any('python312' in name for name in files))
        self.assertFalse(manifest['usable_product'])

    def test_filename_compatible_but_internal_wheel_abi_mismatch_is_refused(self):
        for version, filename, internal in (
                ('3.12.10', 'cp312-cp312-win_amd64', 'cp314-cp314-win_amd64'),
                ('3.14.9', 'cp314-cp314-win_amd64', 'cp312-cp312-win_amd64')):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as tmp:
                previous = self.root; self.root = Path(tmp)
                try:
                    repo, assets, lock, source = self.assembly_fixture(version,
                        wheel_tag=filename, internal_tag=internal, pure=False)
                    with self.assertRaisesRegex(p.PayloadRefused, 'WHEEL_TAG_MISMATCH'):
                        build.assemble(repo, source, assets, lock)
                finally: self.root = previous

    def test_pure_python_tag_does_not_override_requires_python(self):
        repo, assets, lock, source = self.assembly_fixture(requires_python='>=3.14')
        with self.assertRaisesRegex(p.PayloadRefused, 'WHEEL_REQUIRES_PYTHON'):
            build.assemble(repo, source, assets, lock)

    def test_wheel_platform_and_abi_minimum_are_not_bypassed_by_broad_tags(self):
        for tag in ('cp314-cp314-win_amd64', 'cp313-abi3-win_amd64',
                    'cp37-abi3-manylinux_2_17_x86_64', 'py3-abi3-win_amd64',
                    'py3-none-win32', 'cp312-cp312t-win_amd64'):
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as tmp:
                previous = self.root; self.root = Path(tmp)
                try:
                    repo, assets, lock, source = self.assembly_fixture(wheel_tag=tag, pure=False)
                    with self.assertRaisesRegex(p.PayloadRefused, 'WHEEL_TARGET_TAG'):
                        build.assemble(repo, source, assets, lock)
                finally: self.root = previous

    def test_older_abi3_and_compressed_pure_tags_remain_compatible(self):
        for version, tag, internal, pure, requirement in (
                ('3.12.10', 'cp37-abi3-win_amd64', None, False, '>=3.6'),
                ('3.12.10', 'cp312-abi3-win_amd64', None, False, '>=3.12'),
                ('3.14.9', 'cp37-abi3-win_amd64', None, False, '>=3.6'),
                ('3.12.10', 'py2.py3-none-any', 'py2-none-any\nTag: py3-none-any', True,
                 '!=3.0.*,!=3.1.*,>=2.7')):
            with self.subTest(version=version, tag=tag), tempfile.TemporaryDirectory() as tmp:
                previous = self.root; self.root = Path(tmp)
                try:
                    repo, assets, lock, source = self.assembly_fixture(version, tag,
                        internal_tag=internal, pure=pure, requires_python=requirement)
                    files, _ = build.assemble(repo, source, assets, lock)
                    self.assertIn('vendor/fixture/__init__.py', files)
                finally: self.root = previous

    def test_python_layout_is_closed_and_requires_one_exact_locked_asset(self):
        row = dict(kind='python', version='3.12.10', file='python-3.12.10-embed-amd64.zip')
        for rows, reason in (([], 'SINGLE_PYTHON_ASSET'), ([row, row], 'SINGLE_PYTHON_ASSET'),
                ([dict(row, version='3.14.9')], 'PYTHON_ASSET_LAYOUT'),
                ([dict(row, version='3.13.17', file='python-3.13.17-embed-amd64.zip')], 'PYTHON_ASSET_LAYOUT')):
            with self.subTest(rows=rows), self.assertRaisesRegex(p.PayloadRefused, reason):
                build.python_layout(rows)

    def test_metadata_version_is_required_single_and_explicitly_supported(self):
        asset = dict(file='fixture-1.0-py3-none-any.whl', version='1.0')
        wheel = b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
        fields = b'Name: fixture\nVersion: 1.0\nRequires-Python: >=3.9\n\n'
        def verify(header):
            build.verify_wheel(asset, {'fixture-1.0.dist-info/WHEEL': wheel,
                'fixture-1.0.dist-info/METADATA': header + fields}, (3, 12, 10))
        verify(b'Metadata-Version: 1.1\n')
        verify(b'Metadata-Version: 2.4\n')
        for header, reason in (
                (b'', 'WHEEL_METADATA_FIELD:Metadata-Version'),
                (b'Metadata-Version: 2.4\nMetadata-Version: 2.4\n', 'WHEEL_METADATA_FIELD:Metadata-Version'),
                (b'Metadata-Version: 3.0\n', 'WHEEL_CORE_METADATA_VERSION'),
                (b'Metadata-Version: 999.0\n', 'WHEEL_CORE_METADATA_VERSION'),
                (b'Metadata-Version: 1.0\n', 'WHEEL_CORE_METADATA_VERSION'),
                (b'Metadata-Version: 2.0\n', 'WHEEL_CORE_METADATA_VERSION'),
                (b'Metadata-Version: 2.7\n', 'WHEEL_CORE_METADATA_VERSION')):
            with self.subTest(header=header), self.assertRaisesRegex(p.PayloadRefused, reason):
                verify(header)

    def test_leading_zero_interpreter_tags_do_not_claim_312_compatibility(self):
        for tag, pure in (('cp3012-abi3-win_amd64', False), ('py3012-none-any', True),
                          ('py3.py3012-none-any', True)):
            with self.subTest(tag=tag), tempfile.TemporaryDirectory() as tmp:
                previous = self.root; self.root = Path(tmp)
                try:
                    repo, assets, lock, source = self.assembly_fixture(wheel_tag=tag, pure=pure)
                    with self.assertRaisesRegex(p.PayloadRefused, 'WHEEL_PYTHON_TAG'):
                        build.assemble(repo, source, assets, lock)
                finally: self.root = previous

    def test_consistent_filename_lock_and_metadata_still_require_valid_identity(self):
        wheel = b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
        for name, version, reason in (('_fixture', '1.0', 'WHEEL_METADATA_NAME'),
                ('fixture.', '1.0', 'WHEEL_METADATA_NAME'),
                ('fixture', 'not_a_version', 'WHEEL_RELEASE_VERSION'),
                ('fixture', '01.0', 'WHEEL_RELEASE_VERSION'),
                ('fixture', '1.0rc1', 'WHEEL_RELEASE_VERSION'),
                ('fixture', '1.0.0.1', 'WHEEL_RELEASE_VERSION')):
            directory = name + '-' + version + '.dist-info/'
            metadata = ('Metadata-Version: 2.4\nName: ' + name + '\nVersion: ' + version + '\n\n').encode()
            asset = dict(file=name + '-' + version + '-py3-none-any.whl', version=version)
            with self.subTest(name=name, version=version), self.assertRaisesRegex(p.PayloadRefused, reason):
                build.verify_wheel(asset, {directory + 'WHEEL': wheel,
                    directory + 'METADATA': metadata}, (3, 12, 10))

    def test_locked_python_archive_cannot_mix_312_and_314_layouts(self):
        repo, assets, lock, source = self.assembly_fixture('3.14.9',
            extra_python={'python312._pth': b'stale interpreter paths'})
        with self.assertRaisesRegex(p.PayloadRefused, 'PYTHON_ARCHIVE_LAYOUT'):
            build.assemble(repo, source, assets, lock)

    def test_required_python_release_bounds_are_checked_or_fail_closed(self):
        build.python_requirement('>=3.12.10,<3.13,!=3.11.*', (3, 12, 10))
        for requirement, reason in (('>=3.12.11', 'WHEEL_REQUIRES_PYTHON'),
                ('<3.12.10', 'WHEEL_REQUIRES_PYTHON'), ('!=3.12.*', 'WHEEL_REQUIRES_PYTHON'),
                ('~=3.12', 'WHEEL_PYTHON_SPECIFIER'), ('>=3.12.*', 'WHEEL_PYTHON_SPECIFIER')):
            with self.subTest(requirement=requirement), self.assertRaisesRegex(p.PayloadRefused, reason):
                build.python_requirement(requirement, (3, 12, 10))

    def test_actual_wheel_metadata_is_required_unambiguous_and_not_a_native_any_shortcut(self):
        asset = dict(file='fixture-1.0-py3-none-any.whl', version='1.0')
        wheel_path = 'fixture-1.0.dist-info/WHEEL'; metadata_path = 'fixture-1.0.dist-info/METADATA'
        wheel = b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n'
        metadata = b'Metadata-Version: 2.4\nName: fixture\nVersion: 1.0\nRequires-Python: >=3.9\n\n'
        members = {wheel_path: wheel, metadata_path: metadata}
        for changed, reason in (
                ({metadata_path: metadata}, 'WHEEL_METADATA_FILES'),
                ({**members, 'other-1.0.dist-info/WHEEL': wheel}, 'WHEEL_METADATA_FILES'),
                ({**members, wheel_path: wheel + b'Tag: py3-none-any\n'}, 'WHEEL_TAG_DUPLICATE'),
                ({**members, wheel_path: wheel.replace(b'1.0', b'2.0')}, 'WHEEL_FORMAT_VERSION'),
                ({**members, metadata_path: metadata.replace(b'Name: fixture', b'Name: other')}, 'WHEEL_METADATA_IDENTITY'),
                ({**members, 'fixture/native.pyd': pe()}, 'WHEEL_ANY_NATIVE_FILE')):
            with self.subTest(reason=reason), self.assertRaisesRegex(p.PayloadRefused, reason):
                build.verify_wheel(asset, changed, (3, 12, 10))
        platform_asset = dict(asset, file='fixture-1.0-py3-none-win_amd64.whl')
        platform_wheel = wheel.replace(b'Root-Is-Purelib: true', b'Root-Is-Purelib: false').replace(
            b'py3-none-any', b'py3-none-win_amd64')
        with self.assertRaisesRegex(p.PayloadRefused, 'WHEEL_NATIVE_ABI'):
            build.verify_wheel(platform_asset,
                {**members, wheel_path: platform_wheel, 'fixture/native.pyd': pe()}, (3, 12, 10))




    def test_application_contract_refuses_a_compatible_dependency_on_wrong_runtime(self):
        repo, assets, lock, source = self.assembly_fixture(
            '3.14.9', 'cp314-cp314-win_amd64', pure=False, app_requires_python='>=3.12,<3.13')
        with self.assertRaisesRegex(p.PayloadRefused, 'APPLICATION_REQUIRES_PYTHON'):
            build.assemble(repo, source, assets, lock)

    def test_application_python_metadata_is_required_and_fail_closed(self):
        for raw in (b'', b'[project]', b'not toml', b'[project]\nrequires-python = 312'):
            with self.subTest(raw=raw), self.assertRaisesRegex(p.PayloadRefused, 'APPLICATION_PYTHON_METADATA'):
                build.verify_application_python(raw, (3, 12, 10))
        valid = b'[project]\nrequires-python = ">=3.12,<3.13"'
        build.verify_application_python(valid, (3, 12, 10))
        with self.assertRaisesRegex(p.PayloadRefused, 'APPLICATION_REQUIRES_PYTHON'):
            build.verify_application_python(valid, (3, 14, 9))


if __name__ == '__main__': unittest.main()
