"""Metadata wire/guard tests; Linux/injected results are never native acceptance."""
import json
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from scripts.windows_ci import fresh_preflight_once as preflight


def wire(**changes):
    row = dict(source='sys.getwindowsversion', major=10, minor=0, build=26100,
               platform=2, product_type=3, platform_version=[10, 0, 26100])
    return json.dumps({**row, **changes}).encode()


class FreshMetadataContract(unittest.TestCase):
    def test_native_server_and_domain_controller_values(self):
        for product in (2, 3):
            with self.subTest(product_type=product):
                self.assertEqual(preflight.validate_server_metadata(wire(product_type=product))['product_type'], product)

    def test_workstation_wrong_version_unknown_and_malformed_types_refuse(self):
        for changes in [dict(product_type=1), dict(product_type=0), dict(product_type=4),
                        dict(product_type=True), dict(build=20348), dict(build='26100'),
                        dict(major=6), dict(minor=1), dict(platform=1), dict(source='runner label'),
                        dict(platform_version=None), dict(platform_version=[10, True, 26100]),
                        dict(platform_version=[10, 0, -1]), dict(unrecognized=True)]:
            with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                preflight.validate_server_metadata(wire(**changes))

    def test_empty_truncated_non_json_and_oversized_output_refuse(self):
        for raw in (b'', b'null', b'[]', b'{', b'\xff', b'x' * 4097, 'not bytes'):
            with self.subTest(raw_type=type(raw).__name__), self.assertRaises((RuntimeError, ValueError)):
                preflight.validate_server_metadata(raw)

    def test_platform_version_is_diagnostic_not_a_runner_label_fallback(self):
        # Python documents kernel32-derived platform_version for logging only.
        self.assertEqual(preflight.validate_server_metadata(wire(platform_version=[10, 0, 26000]))['build'], 26100)
        with self.assertRaises(RuntimeError):
            preflight.validate_server_metadata(wire(build=20348, platform_version=[10, 0, 26100]))

    def test_one_exact_selected_interpreter_call_with_original_budget(self):
        capture = Mock(return_value=SimpleNamespace(returncode=0, stdout=wire()))
        self.assertEqual(preflight.collect_os_metadata(capture)['build'], 26100)
        capture.assert_called_once_with(preflight.metadata_command(), 'OS_METADATA', 20)
        command = capture.call_args.args[0]
        self.assertEqual(command[:6], [sys.executable, '-I', '-S', '-B', '-c', preflight.OS_METADATA_CODE])

    def test_timeout_and_bad_exit_propagate_without_fallback_or_retry(self):
        error = subprocess.TimeoutExpired(preflight.metadata_command(), 20, output=b'')
        capture = Mock(side_effect=error)
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            preflight.collect_os_metadata(capture)
        self.assertIs(caught.exception, error)
        self.assertEqual(capture.call_count, 1)
        capture = Mock(return_value=SimpleNamespace(returncode=1, stdout=wire()))
        with self.assertRaises(RuntimeError):
            preflight.collect_os_metadata(capture)
        self.assertEqual(capture.call_count, 1)

    @unittest.skipIf(sys.platform == 'win32', 'Linux refusal oracle; native execution is separate')
    def test_real_isolated_child_refuses_linux_with_no_metadata(self):
        result = subprocess.run(preflight.metadata_command(), capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, b'')
        self.assertEqual(result.stderr, b'')

    def test_exact_ci_context_cannot_use_an_old_run_or_private_runner(self):
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        valid = dict(NATIVE_REPOSITORY='T1doo/ParkWeave', NATIVE_REF=preflight.BRANCH,
                     NATIVE_EVENT='push', NATIVE_ATTEMPT='1', NATIVE_NUMBER='1', NATIVE_PUBLIC='true',
                     RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Windows', NATIVE_SHA=head)
        self.assertEqual(preflight.require_context(valid), head)
        for key, value in [('NATIVE_REF', 'refs/heads/main'), ('NATIVE_NUMBER', '2'), ('NATIVE_ATTEMPT', '2'),
                           ('NATIVE_PUBLIC', 'false'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                           ('RUNNER_OS', 'Linux'), ('NATIVE_SHA', '0' * 40), ('PARKWEAVE_DSN', 'SYNTHETIC')]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                preflight.require_context({**valid, key: value})


if __name__ == '__main__':
    unittest.main()
