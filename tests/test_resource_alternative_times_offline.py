"""Actual resource form JS under Node VM doubles; no browser or listener."""
import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize('mode', ['choose_fills_only', 'empty_grid', 'truncated_grid',
    'current_403_clears', 'late_403_other_identity', 'identity_aba_delayed_json',
    'change_resource', 'change_start', 'change_end', 'change_quantity',
    'change_search_from', 'change_search_until', 'two_searches_latest_wins',
    'wrong_resource', 'wrong_quantity', 'wrong_duration', 'wrong_grid', 'unsorted',
    'too_many_results', 'original_flow_explicit'])
def test_actual_resource_suggestions_with_offline_doubles(mode):
    result = subprocess.run(['node', str(Path(__file__).with_name('resource_alternative_times_offline.js')), mode],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data['mode'] == mode and data['checks'] >= 2
    assert data['scope'] == 'NODE_VM_DOM_FETCH_DOUBLES_ONLY'
