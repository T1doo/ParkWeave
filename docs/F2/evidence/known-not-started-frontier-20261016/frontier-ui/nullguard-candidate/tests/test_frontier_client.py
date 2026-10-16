"""Finite explicit request/client epoch probes; controlled data, not HTTP/browser."""
import json,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.mark.parametrize('mode,checks',[('selection_aba',9),('body_identity',5)])
def test_explicit_frontier_profile_context_and_original_approval_identity(mode,checks):
 p=subprocess.run(['node','tests/frontier_client_probes.js',mode],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,p.stderr
 value=json.loads(p.stdout);assert value['checks']==checks and value['actual_http'] is False and value['real_browser']=='NOT_RUN'
