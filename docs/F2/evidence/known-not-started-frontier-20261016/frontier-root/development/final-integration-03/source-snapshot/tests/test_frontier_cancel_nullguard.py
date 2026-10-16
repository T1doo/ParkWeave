"""Null-safe original cancellation blocking, controlled function-level matrix."""
import json,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.mark.parametrize('mode,checks',[('null_identity',42),('view_flags',13),('known_phase',15)])
def test_original_cancellation_blocking_has_explicit_case_identity(mode,checks):
 p=subprocess.run(['node','tests/frontier_cancel_nullguard_probes.js',mode],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,p.stderr
 value=json.loads(p.stdout)
 assert value['checks']==checks and value['actual_http'] is False and value['real_browser']=='NOT_RUN'
