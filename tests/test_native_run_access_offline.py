"""The actual inline workbench logic; offline NodeVM only."""
import json
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('mode',['disabled_pending','lost_response','not_observed','revoked','late_read','late_recovery','authority_expiry','effective_fixture','writer_confirmation'])
def test_native_run_access_ui(mode):
    node=shutil.which('node')
    assert node,'offline Node is required'
    result=subprocess.run([node,'tests/native_run_access_offline.js',mode],capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    data=json.loads(result.stdout)
    assert data['mode']==mode and data['checks']>0 and data['browser_attempts']==0
