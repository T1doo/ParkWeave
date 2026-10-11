"""Actual UI logic in offline NodeVM; explicit browser denial remains untouched."""
import json,shutil,subprocess
import pytest

@pytest.mark.parametrize('mode',['lost_response','cold_recovery','unknown_not_observed','corrupt_proof','revoked','late_read','late_post','pending_other_operation','cancelled_dispatch'])
def test_case_cancel_ui(mode):
 node=shutil.which('node')
 assert node,'Node is required for this offline acceptance'
 result=subprocess.run([node,'tests/case_cancellation_offline.js',mode],capture_output=True,text=True,timeout=15)
 assert result.returncode==0,result.stderr
 data=json.loads(result.stdout);assert data['mode']==mode and data['checks']>0
