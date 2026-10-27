"""Finite full-page NodeVM checks; no browser, PostgreSQL or real authority."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
ACTIVATION_MODES = (
    'gates', 'confirmation', 'mutated_snapshot', 'lease_expiry', 'authority_expiry',
    'post403', 'late_post200', 'late_post403', 'token_aba', 'timeout', 'post409',
    'post422', 'navigation', 'unknown_expiry', 'late_get200', 'late_get403',
    'verified', 'history_revoked', 'history_expired', 'unverified', 'wrong_body',
    'wrong_source', 'wrong_target', 'wrong_validity', 'wrong_revision',
    'wrong_namespace', 'wrong_receipt_namespace', 'extra_body', 'not_observed',
    'unicode_reason', 'unicode_blank', 'auto_get403', 'verified_then_read403',
)
LEGACY_MODES = (
    'disabled_pending', 'lost_response', 'not_observed', 'revoked', 'late_read',
    'late_recovery', 'authority_expiry', 'effective_fixture', 'writer_confirmation',
    'writer_unverified_recovery', 'writer_verified_recovery', 'writer_wrong_body_recovery',
)


class ActivationUI(unittest.TestCase):
    pass


class ExistingNativeUI(unittest.TestCase):
    pass


def case(script, mode):
    def test(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith('PARKWEAVE_')}
        result = subprocess.run(['node', str(ROOT / 'tests' / script), mode],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['mode'], mode)
        self.assertGreater(report['checks'], 0)
        self.assertEqual(report['browser_attempts'], 0)
    return test


for _cls, _script, _modes in (
    (ActivationUI, 'native_run_access_activation_offline.js', ACTIVATION_MODES),
    (ExistingNativeUI, 'native_run_access_offline.js', LEGACY_MODES),
):
    for _mode in _modes:
        setattr(_cls, 'test_' + _mode, case(_script, _mode))
del _cls, _script, _modes, _mode

if __name__ == '__main__':
    unittest.main(verbosity=2)
