"""Offline actual handoff JavaScript. No browser, server/listener or HTTP call."""
import json
import subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize('mode',['explicit_success','lost_response_cold_get_only','storage_failure','duplicate_click','identity_aba_delayed_json','late_403_new_identity','wrong_recovery_proof','bounded_handles','current_recovery_403_keeps_original_handle'])
def test_pending_manual_handoff_actual_js_under_offline_doubles(mode):
 p=subprocess.run(['node',str(Path(__file__).with_name('pending_receipt_handoff_offline.js')),mode],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=15)
 assert p.returncode==0,p.stderr
 result=json.loads(p.stdout);assert result['mode']==mode and result['checks']>=2
 assert result['scope']=='NODE_VM_WITH_DOM_FETCH_STORAGE_DOUBLES_ONLY'
