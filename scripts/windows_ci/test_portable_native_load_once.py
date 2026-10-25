"""Linux-safe source/policy/failure checks. No assets fetched or native APIs used."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from . import portable_native_load_once as driver
from . import portable_native_load_probe as probe
from . import owned_job


class NativeLoadPreparationChecks(unittest.TestCase):
    def run_preparation_drift_fixture(self, *, change_frozen=False):
        """Exercise real parent sequencing/files, replace only native/network seams."""
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp); repo = base / 'repo'
            original = repo / 'scripts/windows_ci/portable_native_load_probe.py'
            original.parent.mkdir(parents=True); original.write_bytes(b'ORIGINAL_REVIEWED_PROBE')
            lock = repo / 'scripts/windows_portable/runtime-assets.json'
            lock.parent.mkdir(parents=True); lock.write_bytes(b'fictional lock')
            dispatched = []
            def verified(*args):
                raw = original.read_bytes()
                self.assertEqual(raw, b'ORIGINAL_REVIEWED_PROBE')
                return raw
            def prepare(workspace, rows, deadline, checkpoint):
                original.write_bytes(b'CHANGED_DURING_PREPARATION')
                if change_frozen:
                    frozen = workspace.root / 'evidence/frozen-probe.py'
                    if frozen.exists(): frozen.write_bytes(b'CHANGED_FROZEN_COPY')
                workspace.put('payload/runtime/python/python.exe', b'fictional executable')
                return driver.payload.file_manifest({'runtime/python/python.exe': b'fictional executable'})
            def owned(args, **kwargs):
                dispatched.append((Path(args[4]), Path(args[4]).read_bytes()))
                kwargs['stdout'].write(json.dumps({'status': 'OBSERVED',
                    'product_source': probe.PRODUCT_SOURCE, 'pid': 17}).encode())
                return SimpleNamespace(returncode=0, cleanup='OWNED_TREE_STOPPED')
            context = {'RUNNER_TEMP': str(base), 'GITHUB_SHA': 'a' * 40, 'GITHUB_REF': driver.EXECUTION_REF}
            with patch.object(driver, 'window_gate'), patch.object(driver, 'verify_source', side_effect=verified), \
                    patch.object(driver, 'selected_assets', return_value=[]), \
                    patch.object(driver, 'prepare', side_effect=prepare), \
                    patch.object(driver, 'os', SimpleNamespace(name='nt')), \
                    patch.object(driver, 'child_environment', return_value={}), \
                    patch.object(driver, 'MonitoredBackend', return_value=SimpleNamespace(_owned_parent_pid=17)), \
                    patch.object(driver.owned_job, 'run', side_effect=owned) as dispatch, \
                    redirect_stdout(io.StringIO()):
                result = driver.run(repo, context)
            return result, dispatched, dispatch.call_count, original.read_bytes()

    def test_prepare_drift_can_only_dispatch_original_verified_probe_bytes(self):
        result, dispatched, count, repository_bytes = self.run_preparation_drift_fixture()
        self.assertEqual(result['status'], 'OBSERVED_NOT_PRODUCT_ACCEPTANCE')  # Mock observation only.
        self.assertEqual(count, 1)
        self.assertEqual(repository_bytes, b'CHANGED_DURING_PREPARATION')
        self.assertEqual(dispatched[0][1], b'ORIGINAL_REVIEWED_PROBE')
        self.assertEqual(dispatched[0][0].parts[-2:], ('evidence', 'frozen-probe.py'))

    def test_changed_frozen_copy_refuses_before_owned_dispatch(self):
        result, dispatched, count, _ = self.run_preparation_drift_fixture(change_frozen=True)
        self.assertEqual(result['status'], 'FAIL')
        self.assertEqual(result['primary_error']['reason'], 'WORKSPACE_FILE_CHANGED')
        self.assertEqual(count, 0)
        self.assertEqual(dispatched, [])

    def test_both_clis_refuse_before_work_or_native_access(self):
        with patch.object(driver, 'verify_source') as source, patch.object(driver, 'Workspace') as workspace, \
                patch.object(driver, 'fetch_asset') as fetch, patch.object(probe, 'own_windows_modules') as native:
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(driver.main(), 2)
                self.assertEqual(probe.main(), 2)
            self.assertIn('WINDOW_NOT_APPROVED', output.getvalue())
            for called in (source, workspace, fetch, native): called.assert_not_called()

    def test_workflow_is_closed_and_has_no_review_branch_trigger_or_install(self):
        path = Path(__file__).resolve().parents[2] / '.github/workflows/portable-native-load-once.yml'
        text = path.read_text()
        self.assertIn('if: ${{ false }}', text)
        self.assertIn('timeout-minutes: 6', text)
        self.assertIn('persist-credentials: false', text)
        self.assertNotIn('dev/portable-runtime-module-pack-20261024', text)
        for forbidden in ('setup-python', 'pip install', 'workflow_dispatch', 'permissions: write'):
            self.assertNotIn(forbidden, text)
        self.assertFalse(driver.WINDOW_APPROVED)
        self.assertFalse(probe.WINDOW_APPROVED)
        self.assertIsNone(driver.EXPECTED_RUN_NUMBER)

    def test_exact_product_lock_selects_23_assets_without_pg(self):
        path = Path(__file__).resolve().parents[1] / 'windows_portable/runtime-assets.json'
        raw = path.read_bytes(); rows = driver.selected_assets(raw)
        self.assertEqual(len(rows), 23)
        self.assertEqual(sum(row['bytes'] for row in rows), 20708411)
        self.assertTrue(all(row['kind'] != 'postgresql' for row in rows))
        with self.assertRaisesRegex(probe.ProbeRefused, 'LOCK_SOURCE_REFUSED'):
            driver.selected_assets(raw + b' ')

    def test_download_verifies_exact_body_and_never_follows_redirects(self):
        import hashlib
        row = {'url': 'https://www.python.org/fictional-offline-fixture', 'bytes': 3,
               'sha256': hashlib.sha256(b'abc').hexdigest()}
        class Response(io.BytesIO):
            status = 200
            def geturl(self): return row['url']
        class Opener:
            def __init__(self, raw): self.raw = raw; self.calls = 0
            def open(self, *args, **kwargs): self.calls += 1; return Response(self.raw)
        valid = Opener(b'abc')
        self.assertEqual(driver.fetch_asset(row, 1, opener=valid, clock=lambda: 0), b'abc')
        self.assertEqual(valid.calls, 1)
        for data in (b'ab', b'abd', b'abcd'):
            with self.subTest(data=data), self.assertRaises(probe.ProbeRefused):
                driver.fetch_asset(row, 1, opener=Opener(data), clock=lambda: 0)
        with self.assertRaisesRegex(probe.ProbeRefused, 'ASSET_REDIRECT_REFUSED'):
            driver.NoRedirect().redirect_request(None)
        with self.assertRaisesRegex(probe.ProbeRefused, 'PREPARATION_DEADLINE'):
            driver.fetch_asset(row, 1, opener=Opener(b'abc'), clock=lambda: 1)

    def test_origin_policy_separates_private_system_and_external_dlls(self):
        expected = {'runtime/python/python314.dll': {}, 'vendor/psycopg_binary.libs/libpq-fixed.dll': {}}
        root = r'C:\temp\fictional\payload'; system = r'C:\Windows\System32'
        self.assertEqual(probe.classify_module(root + r'\runtime\python\python314.dll', root,
            system, expected, probe.SYSTEM_NAMES)['kind'], 'PACKAGE')
        self.assertEqual(probe.classify_module(system + r'\kernel32.dll', root,
            system, expected, probe.SYSTEM_NAMES)['kind'], 'SYSTEM_DIRECTORY')
        for path in (system + r'\python314.dll', system + r'\vcruntime140.dll',
                     r'C:\hostedtoolcache\libpq-fixed.dll', system + r'\unknown.dll',
                     root + r'\..\foreign.dll'):
            with self.subTest(path=path), self.assertRaises(probe.ProbeRefused):
                probe.classify_module(path, root, system, expected, probe.SYSTEM_NAMES)

    def test_external_file_replacement_is_detected_and_nothing_is_deleted(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = driver.Workspace(tmp)
            original = workspace.put('payload/fictional.bin', b'original')
            moved = original.with_name('retained-original'); original.rename(moved)
            original.write_bytes(b'external replacement')
            with self.assertRaisesRegex(probe.ProbeRefused, 'WORKSPACE_FILE_CHANGED'):
                workspace.check_files()
            self.assertEqual(original.read_bytes(), b'external replacement')
            self.assertEqual(moved.read_bytes(), b'original')

    def test_replaced_root_is_not_used_for_checkpoint_or_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = driver.Workspace(tmp); root = workspace.root
            moved = root.with_name(root.name + '-retained'); root.rename(moved)
            root.mkdir(); marker = root / 'external-marker'; marker.write_bytes(b'keep')
            with self.assertRaisesRegex(probe.ProbeRefused, 'WORKSPACE_IDENTITY_CHANGED'):
                workspace.checkpoint({'status': 'FAIL'})
            self.assertEqual(marker.read_bytes(), b'keep')
            self.assertTrue((moved / 'evidence').is_dir())

    def test_directory_identity_change_with_identical_bytes_is_detected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); folder = root / 'part'; folder.mkdir(); (folder / 'file').write_bytes(b'x')
            expected = {'part/file': {'bytes': 1, 'sha256': hashlib.sha256(b'x').hexdigest()}}
            before = probe.verify_files(root, expected)
            folder.rename(root / 'old'); folder.mkdir(); (folder / 'file').write_bytes(b'x')
            with self.assertRaisesRegex(probe.ProbeRefused, 'PAYLOAD_FILE_SET_CHANGED'):
                probe.verify_files(root, expected)
            self.assertNotEqual(probe.directory_state(folder), before['part/'])

    def test_child_environment_does_not_inherit_credentials_or_tool_path(self):
        class Space: root = Path('C:/fictional/private-test')
        env = driver.child_environment({'SystemRoot': 'C:/Windows', 'PATH': 'foreign-tools',
            'DATABASE_URL': 'private-marker', 'OPENAI_API_KEY': 'private-marker'}, Space())
        self.assertNotIn('private-marker', json.dumps(env))
        self.assertNotIn('foreign-tools', json.dumps(env))
        self.assertEqual(env['PSYCOPG_IMPL'], 'binary')

    def test_primary_failure_survives_owned_job_cleanup_failure(self):
        class Backend:
            def create_job(self): self.job = object(); return self.job
            def launch(self, *args): return object(), object(), 17
            def bind(self, *args): pass
            def resume(self, *args): pass
            def wait(self, *args): raise probe.ProbeRefused('OUTPUT_IDENTITY_CHANGED')
            def stop_tree(self, job):
                self.stopped = job
                raise owned_job.OwnedJobError('JOB_STOP_UNCONFIRMED')
            def close(self, handle): pass
        backend = Backend()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'not-executable-fixture'; path.write_bytes(b'no native code')
            with self.assertRaisesRegex(probe.ProbeRefused, 'OUTPUT_IDENTITY_CHANGED') as caught:
                owned_job.run([str(path)], timeout=1, stdout=None, stderr=None, _backend=backend)
        self.assertIs(backend.stopped, backend.job)
        self.assertEqual(caught.exception.cleanup, 'OWNED_TREE_STOP_UNCONFIRMED')
        self.assertEqual(caught.exception.cleanup_error_category, 'OwnedJobError')

    def test_output_monitor_detects_replaced_path_without_windows_calls(self):
        class Win:
            WAIT_OBJECT_0 = 0; WAIT_TIMEOUT = 258
            calls = 0
            def WaitForSingleObject(self, *args): self.calls += 1; return self.WAIT_OBJECT_0
            def GetExitCodeProcess(self, *args): return 0
        with tempfile.TemporaryDirectory() as tmp:
            workspace = driver.Workspace(tmp); path = workspace.root / 'evidence/stdout'
            with path.open('x+b') as output:
                backend = object.__new__(driver.MonitoredBackend)
                backend.workspace = workspace; backend.outputs = (output,)
                backend.output_identities = (os.fstat(output.fileno()),); backend.win = Win()
                self.assertEqual(backend.wait(object(), 1), 0)
                path.rename(path.with_name('original-output')); path.write_bytes(b'external')
                with self.assertRaisesRegex(probe.ProbeRefused, 'OUTPUT_IDENTITY_CHANGED'):
                    backend.wait(object(), 1)
                self.assertEqual(backend.win.calls, 1)
                self.assertEqual(path.read_bytes(), b'external')

    def test_failure_reports_are_bounded_and_redact_raw_exception_text(self):
        error = probe.ProbeRefused('authorization=private-marker')
        self.assertNotIn('private-marker', json.dumps(driver.error_record(error)))
        stdout = io.BytesIO(b'{"status":"FAIL","reason":"MODULE_PATH_READ_FAILED"}')
        report = driver.collect_report(stdout, io.BytesIO())
        self.assertEqual(report['probe']['reason'], 'MODULE_PATH_READ_FAILED')
        with self.assertRaisesRegex(probe.ProbeRefused, 'PROBE_REPORT_FIELDS_REFUSED'):
            driver.collect_report(io.BytesIO(b'{"authorization":"private-marker"}'), io.BytesIO())
        with self.assertRaisesRegex(probe.ProbeRefused, 'PROBE_OUTPUT_BUDGET'):
            driver.collect_report(io.BytesIO(b'x' * (128 * 1024 + 1)), io.BytesIO())
        with self.assertRaisesRegex(probe.ProbeRefused, 'PROBE_REPORT_BUSINESS_REFUSED'):
            driver.collect_report(io.BytesIO(b'{"status":"OBSERVED","database_connections":true}'), io.BytesIO())


if __name__ == '__main__':
    unittest.main()
