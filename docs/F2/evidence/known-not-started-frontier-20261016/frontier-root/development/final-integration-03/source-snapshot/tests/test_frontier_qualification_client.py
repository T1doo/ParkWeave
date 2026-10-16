"""Closed new-version qualification fixtures; not HTTP/browser or PG authority."""
import json,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.mark.parametrize('mode',["qualification_shape","qualification_history"])
def test_frontier_new_version_strict_refusal_and_cold_profile(mode):
 p=subprocess.run(['node','tests/frontier_qualification_client_probes.js',mode],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,p.stderr
 value=json.loads(p.stdout);assert value['checks']>=7 and value['actual_http'] is False and value['real_browser']=='NOT_RUN' and value['backend_authority_claimed'] is False
