"""Shipped HTML functions with controlled data; these are not HTTP/browser tests."""
import json,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.mark.parametrize('mode,checks',[('shape',28),('history',8),('aba',6)])
def test_replacement_explicit_mode_exact_proof_approval_and_aba(mode,checks):
 result=subprocess.run(['node','tests/plan_replacement_client_probes.js',mode],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert result.returncode==0,result.stderr
 value=json.loads(result.stdout)
 assert value['checks']==checks and value['actual_http'] is False and value['real_browser']=='NOT_RUN'
