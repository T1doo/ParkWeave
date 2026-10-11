import json
from pathlib import Path
import subprocess
import pytest

MODES=['malicious_json','malicious_object','malicious_extra','malicious_actor_type','malicious_future','malicious_nine',
       'eight_absolute_capacity','expiry_absolute_no_renew','late_recovery_json_identity_aba','late_recovery_403_identity_aba',
       'wrong_proof_event_actor','wrong_proof_event_dispatch','wrong_proof_scope','wrong_proof_key','storage_changed_during_recovery']

@pytest.mark.parametrize('mode',MODES)
def test_actual_handoff_js_new_private_storage_recovery_probe(mode):
    result=subprocess.run(['node',str(Path(__file__).with_name('handoff_vm_independent.js')),mode],
                          capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stdout+result.stderr
    output=json.loads(result.stdout);assert output['mode']==mode and output['checks']>=3
