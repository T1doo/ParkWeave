"""Injected probe outcomes and CI guards; never Windows or Doctor acceptance."""
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from scripts.windows_ci import powershell_entry_once as probe


class EntryProbeContract(unittest.TestCase):
    def test_one_original_shell_call_with_same_timeout_and_fixed_flush_marker(self):
        capture = Mock(return_value=SimpleNamespace(stdout=b'', stderr=b'PS_ENTERED\r\n', returncode=0))
        result = probe.observe_entry(capture)
        self.assertEqual(result['status'], 'PASS_PS_ENTERED')
        capture.assert_called_once_with(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command',
                                        "[Console]::Error.WriteLine('PS_ENTERED'); [Console]::Error.Flush(); exit 0"],
                                       'POWERSHELL_ENTRY', 25)

    def test_timeout_without_marker_cannot_enable_internal_tracing(self):
        capture = Mock(side_effect=subprocess.TimeoutExpired(probe.probe_command(), 25, output=b'', stderr=b''))
        result = probe.observe_entry(capture)
        self.assertEqual(result['status'], 'FAIL_ENTRY_PROBE')
        self.assertTrue(result['timed_out'])
        self.assertFalse(result['ps_entered'])
        self.assertEqual(result['interpretation'], 'NO_ENTRY_MARKER_OBSERVED')
        self.assertEqual(capture.call_count, 1)

    def test_marker_then_timeout_is_distinct_and_not_a_clean_start(self):
        capture = Mock(side_effect=subprocess.TimeoutExpired(probe.probe_command(), 25, stderr=b'PS_ENTERED\r\n'))
        result = probe.observe_entry(capture)
        self.assertTrue(result['ps_entered'])
        self.assertEqual(result['status'], 'FAIL_ENTRY_PROBE')
        self.assertEqual(result['interpretation'], 'ENTRY_SEEN_BUT_NOT_CLEANLY_COMPLETED')
        self.assertEqual(capture.call_count, 1)

    def test_bad_stream_exit_and_large_output_do_not_become_success(self):
        for stdout, stderr, code in [(b'PS_ENTERED\n', b'', 0), (b'', b'', 0),
                                     (b'', b'PS_ENTERED\n', 1), (b'', b'OTHER\nPS_ENTERED\n', 0),
                                     (b'x' * 4097, b'PS_ENTERED\n', 0)]:
            with self.subTest(code=code, out_size=len(stdout)):
                result = probe.observe_entry(Mock(return_value=SimpleNamespace(stdout=stdout, stderr=stderr, returncode=code)))
                self.assertEqual(result['status'], 'FAIL_ENTRY_PROBE')
                self.assertNotIn('OTHER', str(result))

    def test_exact_new_public_context_without_business_environment(self):
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        valid = dict(NATIVE_REPOSITORY='T1doo/ParkWeave', NATIVE_REF=probe.BRANCH, NATIVE_EVENT='push',
                     NATIVE_ATTEMPT='1', NATIVE_NUMBER='1', NATIVE_PUBLIC='true',
                     RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Windows', NATIVE_SHA=head)
        self.assertEqual(probe.require_context(valid), head)
        for key, value in [('NATIVE_REF', 'refs/heads/main'), ('NATIVE_NUMBER', '2'), ('NATIVE_ATTEMPT', '2'),
                           ('NATIVE_PUBLIC', 'false'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                           ('PARKWEAVE_DSN', 'SYNTHETIC'), ('NATIVE_SHA', '0' * 40)]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                probe.require_context({**valid, key: value})


if __name__ == '__main__':
    unittest.main()
