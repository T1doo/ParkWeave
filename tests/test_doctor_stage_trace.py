"""Local diagnostic contracts; no native Windows or Doctor acceptance claim."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/windows/lifecycle.py'
SPEC = importlib.util.spec_from_file_location('doctor_stage_trace_contract', SCRIPT)
lifecycle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lifecycle)


class DoctorTraceContract(unittest.TestCase):
    @unittest.skipIf(sys.platform == 'win32', 'local Linux rejection contract only')
    def test_real_cli_default_and_traced_rejection_preserve_exit_and_stdout(self):
        environment = lifecycle.minimal_environment(os.environ, PYTHONDONTWRITEBYTECODE='1')
        plain = subprocess.run([sys.executable, '-B', str(SCRIPT), 'doctor'],
                               capture_output=True, env=environment)
        traced = subprocess.run([sys.executable, '-B', str(SCRIPT), 'doctor', '--trace-stages'],
                                capture_output=True, env=environment)
        self.assertEqual((plain.returncode, traced.returncode), (1, 1))
        self.assertEqual(plain.stdout, traced.stdout)
        self.assertNotIn(b'PW_STAGE:', plain.stderr)
        self.assertEqual([line for line in traced.stderr.splitlines() if line.startswith(b'PW_STAGE:')],
                         [b'PW_STAGE:PY_ENTERED', b'PW_STAGE:PY_IMPORTS_READY', b'PW_STAGE:PY_MAIN_ENTERED'])
        self.assertNotIn(b'PY_WINDOWS_READY', traced.stderr)

    def test_check_python_brackets_original_single_child_and_does_not_forward_secrets(self):
        stderr = io.StringIO()
        with patch.object(lifecycle, '_DOCTOR_TRACE', True), contextlib.redirect_stderr(stderr), \
                patch.dict(os.environ, {'PARKWEAVE_OWNER_DSN': 'PRIVATE_SENTINEL', 'PYTHONPATH': 'PRIVATE_SENTINEL'}), \
                patch.object(lifecycle.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='["win32",3,12,64]')) as run:
            lifecycle.check_python('explicit-python')
        self.assertEqual(run.call_count, 1)
        self.assertEqual(run.call_args.args[0], ['explicit-python', '-c',
            "import sys,struct,json;print(json.dumps([sys.platform,*sys.version_info[:2],struct.calcsize('P')*8]))"])
        self.assertNotIn('timeout', run.call_args.kwargs)
        self.assertNotIn('PARKWEAVE_OWNER_DSN', run.call_args.kwargs['env'])
        self.assertNotIn('PYTHONPATH', run.call_args.kwargs['env'])
        self.assertEqual(stderr.getvalue(), 'PW_STAGE:PY_CHECK_PYTHON_BEGIN\nPW_STAGE:PY_CHECK_PYTHON_RETURNED\n')

    def test_failed_check_keeps_refusal_and_exception_does_not_emit_return_marker(self):
        for result in (SimpleNamespace(returncode=1, stdout='PRIVATE_SENTINEL'), FileNotFoundError('PRIVATE_SENTINEL')):
            stderr = io.StringIO()
            options = {'side_effect': result} if isinstance(result, Exception) else {'return_value': result}
            with self.subTest(exception=isinstance(result, Exception)), \
                    patch.object(lifecycle, '_DOCTOR_TRACE', True), contextlib.redirect_stderr(stderr), \
                    patch.object(lifecycle.subprocess, 'run', **options) as run:
                with self.assertRaises((lifecycle.BoundaryError, FileNotFoundError)):
                    lifecycle.check_python('explicit-python')
            run.assert_called_once()
            self.assertNotIn('PRIVATE_SENTINEL', stderr.getvalue())
            self.assertEqual('PW_STAGE:PY_CHECK_PYTHON_RETURNED' in stderr.getvalue(), not isinstance(result, Exception))

    def test_other_actions_cannot_enable_diagnostic(self):
        stderr = io.StringIO()
        with patch.object(sys, 'argv', ['lifecycle.py', 'setup', '--trace-stages']), \
                contextlib.redirect_stderr(stderr), patch.object(lifecycle, 'require_windows') as native, \
                patch.object(lifecycle, 'setup') as setup:
            with self.assertRaises(SystemExit) as error:
                lifecycle.main()
        self.assertEqual(error.exception.code, 2)
        native.assert_not_called()
        setup.assert_not_called()

    def test_noncanonical_flag_order_is_refused_without_silent_tracing(self):
        environment = lifecycle.minimal_environment(os.environ, PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--trace-stages', 'doctor'],
                                capture_output=True, env=environment)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn(b'PW_STAGE:', result.stderr)
        self.assertEqual(result.stdout, b'')


if __name__ == '__main__':
    unittest.main()
