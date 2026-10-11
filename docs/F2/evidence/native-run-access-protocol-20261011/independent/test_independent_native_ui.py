"""Two focused timer counterexamples in offline NodeVM."""
import json
from pathlib import Path
import subprocess
import pytest

@pytest.mark.parametrize('mode', ['status_expiry', 'pending_expiry'])
def test_native_expiry_boundary(mode):
    result = subprocess.run(['node', str(Path(__file__).with_name('native_expiry_probe.js')), mode],
                            capture_output=True, text=True, timeout=15)
    print(result.stdout, end='')
    print(result.stderr, end='')
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['browser_attempts'] == 0
