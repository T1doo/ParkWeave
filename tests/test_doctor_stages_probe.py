"""Injected bounded Doctor diagnostic contracts; not native Windows acceptance."""
from hashlib import sha256
import json
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from scripts.windows_ci import doctor_stages_once as probe


def stdout():
    return json.dumps(dict(project='ParkWeave', platform='win32', model='DISABLED',
        new_setup=dict(status='BLOCKED', reason='OWNER_MUTATION_PAUSED', native_acceptance='NOT_ACCEPTED'))).encode()


def stderr(stages):
    return b''.join(('PW_STAGE:' + name + '\r\n').encode() for name in stages)


class DoctorStagesContract(unittest.TestCase):
    def test_single_original_file_call_same_interpreter_trace_and_25_second_limit(self):
        capture = Mock(return_value=SimpleNamespace(stdout=stdout(), stderr=stderr(probe.STAGES), returncode=0))
        result = probe.observe_doctor(capture)
        capture.assert_called_once_with(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
            str(probe.ROOT / 'scripts/windows/Doctor.ps1'), '-Python', sys.executable, '-TraceStages'], 'DOCTOR_STAGES', 25)
        self.assertEqual(result['status'], 'PASS_FRESH_DOCTOR_DIAGNOSTIC_ONLY')
        self.assertEqual(result['unreturned_boundaries'], [])

    def test_original_timeout_keeps_partial_stages_and_both_complete_stream_hashes(self):
        partial = probe.STAGES[:probe.STAGES.index('PY_CHECK_PYTHON_RETURNED')]
        raw = stderr(partial)
        capture = Mock(side_effect=subprocess.TimeoutExpired(probe.probe_command(), 25, output=b'', stderr=raw))
        result = probe.observe_doctor(capture)
        self.assertEqual(result['status'], 'FAIL_DOCTOR_DIAGNOSTIC')
        self.assertEqual(result['last_stage'], 'PY_CHECK_PYTHON_BEGIN')
        self.assertEqual(result['unreturned_boundaries'], ['LIFECYCLE_CALL', 'CHECK_PYTHON_CHILD'])
        self.assertTrue(result['timed_out'])
        self.assertEqual(result['error_type'], 'TimeoutExpired')
        self.assertEqual(result['stderr_sha256'], sha256(raw).hexdigest())
        capture.assert_called_once()

    def test_no_marker_is_distinct_from_dot_source_and_imports(self):
        for stages, pending in [((), []), (('PS_DOCTOR_ENTERED',), ['DOT_SOURCE_COMMON']),
                                (probe.STAGES[:probe.STAGES.index('PY_ENTERED') + 1], ['LIFECYCLE_CALL', 'PYTHON_IMPORTS'])]:
            with self.subTest(stages=stages):
                capture = Mock(side_effect=subprocess.TimeoutExpired(probe.probe_command(), 25, stderr=stderr(stages)))
                result = probe.observe_doctor(capture)
                self.assertEqual(result['unreturned_boundaries'], pending)
                self.assertEqual(result['stages'], list(stages))

    def test_unknown_content_cannot_leak_or_pass_and_error_protocol_is_validated(self):
        raw = b'PRIVATE_SENTINEL\nPSSecurityException\nPW_STAGE:PRIVATE_SENTINEL\n'
        bad = b'PARKWEAVE_LIFECYCLE_DIAGNOSTIC {"schema":1,"action":"doctor","boundary_phase":"python_guard","category":"ModuleNotFoundError","boundary_reason":"UNCLASSIFIED"}\n'
        result = probe.observe_doctor(Mock(return_value=SimpleNamespace(stdout=bad, stderr=raw, returncode=1)))
        self.assertEqual(result['status'], 'FAIL_DOCTOR_DIAGNOSTIC')
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(result))
        self.assertEqual(result['stderr_sha256'], sha256(raw).hexdigest())
        self.assertEqual(result['original_diagnostic']['category'], 'ModuleNotFoundError')
        self.assertEqual(result['safe_error_categories'], ['PSSecurityException'])

    def test_missing_duplicate_reversed_or_wrong_stdout_never_becomes_pass(self):
        for stages, output, code in [(probe.STAGES[:-1], stdout(), 0),
                                     (probe.STAGES + probe.STAGES[-1:], stdout(), 0),
                                     (tuple(reversed(probe.STAGES)), stdout(), 0),
                                     (probe.STAGES, b'{}', 0), (probe.STAGES, stdout(), 1)]:
            with self.subTest(code=code, count=len(stages)):
                result = probe.observe_doctor(Mock(return_value=SimpleNamespace(stdout=output, stderr=stderr(stages), returncode=code)))
                self.assertEqual(result['status'], 'FAIL_DOCTOR_DIAGNOSTIC')

    def test_exact_new_first_public_hosted_context(self):
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        valid = dict(NATIVE_REPOSITORY='T1doo/ParkWeave', NATIVE_REF=probe.BRANCH, NATIVE_EVENT='push',
                     NATIVE_ATTEMPT='1', NATIVE_NUMBER='1', NATIVE_PUBLIC='true',
                     RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Windows', NATIVE_SHA=head)
        self.assertEqual(probe.require_context(valid), head)
        source_branch = 'refs/heads/dev/windows-doctor-source-boundary-20261020'
        self.assertEqual(probe.require_context({**valid, 'NATIVE_REF': source_branch}, source_branch), head)
        with self.assertRaises(RuntimeError):
            probe.require_context({**valid, 'NATIVE_REF': 'refs/heads/main'}, 'refs/heads/main')
        for key, value in [('NATIVE_REF', 'refs/heads/main'), ('NATIVE_NUMBER', '2'), ('NATIVE_ATTEMPT', '2'),
                           ('NATIVE_PUBLIC', 'false'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                           ('PARKWEAVE_DSN', 'PRIVATE_SENTINEL'), ('NATIVE_SHA', '0' * 40)]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                probe.require_context({**valid, key: value})

    def test_path_command_boundary_is_distinct_from_common_file_entry(self):
        stages = ('PS_DOCTOR_ENTERED', 'PS_COMMON_PATH_BEGIN')
        result = probe.observe_doctor(Mock(side_effect=subprocess.TimeoutExpired(probe.probe_command(), 25, stderr=stderr(stages))))
        self.assertEqual(result['unreturned_boundaries'], ['DOT_SOURCE_COMMON', 'COMMON_PATH_COMMAND'])
        self.assertNotIn('COMMON_FILE_ENTRY', result['unreturned_boundaries'])

    def test_default_verification_has_no_trace_argument_or_markers_and_same_budget(self):
        capture = Mock(return_value=SimpleNamespace(stdout=stdout(), stderr=b'', returncode=0))
        result = probe.observe_doctor(capture, trace=False)
        capture.assert_called_once_with(['powershell.exe', '-NoProfile', '-NonInteractive', '-File',
            str(probe.ROOT / 'scripts/windows/Doctor.ps1'), '-Python', sys.executable], 'DOCTOR_DEFAULT', 25)
        self.assertEqual(result['status'], 'PASS_FRESH_DOCTOR_DEFAULT_ONLY')
        self.assertEqual(result['stages'], [])
        for output, error, code in [(b'{}', b'', 0), (stdout(), b'PRIVATE_SENTINEL', 0),
                                    (stdout(), stderr(probe.STAGES), 0), (stdout(), b'', 1)]:
            with self.subTest(code=code, stderr_size=len(error)):
                result = probe.observe_doctor(Mock(return_value=SimpleNamespace(stdout=output, stderr=error, returncode=code)), trace=False)
                self.assertEqual(result['status'], 'FAIL_DOCTOR_DIAGNOSTIC')

    def test_default_verification_timeout_does_not_retry_or_raise_budget(self):
        capture = Mock(side_effect=subprocess.TimeoutExpired(probe.probe_command(False), 25, output=b'', stderr=b''))
        result = probe.observe_doctor(capture, trace=False)
        self.assertTrue(result['timed_out'])
        self.assertEqual(result['status'], 'FAIL_DOCTOR_DIAGNOSTIC')
        capture.assert_called_once()

    def test_exact_authorized_branch_and_mode_pair(self):
        head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
        branch = 'refs/heads/dev/windows-doctor-joinpath-20261020'
        valid = dict(NATIVE_REPOSITORY='T1doo/ParkWeave', NATIVE_REF=branch, NATIVE_EVENT='push',
                     NATIVE_ATTEMPT='1', NATIVE_NUMBER='1', NATIVE_PUBLIC='true',
                     RUNNER_ENVIRONMENT='github-hosted', RUNNER_OS='Windows', NATIVE_SHA=head)
        self.assertEqual(probe.require_context(valid, branch, False), head)
        for mode in (True, 0, None):
            with self.subTest(mode=mode), self.assertRaises(RuntimeError):
                probe.require_context(valid, branch, mode)
        with self.assertRaises(RuntimeError):
            probe.require_context({**valid, 'NATIVE_REF': probe.BRANCH}, probe.BRANCH, False)


if __name__ == '__main__':
    unittest.main()
