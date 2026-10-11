import json
from pathlib import Path
import subprocess
import pytest

MODES=['old_button_after_draft','old_button_after_search','old_button_identity_aba','delayed_json_identity_aba',
       'late_403_other_identity','current_403_clear','bundle_unknown_read_search','change_ttl','change_purpose',
       'outside_window','duplicate_candidates','quantity_bool','select_no_automatic_write','empty_sampling_message','truncated_sampling_message',
       'actual_bundle_controls_read_search']

@pytest.mark.parametrize('mode',MODES)
def test_new_independent_actual_js_suggestion_probe(mode):
    completed=subprocess.run(['node',str(Path(__file__).with_name('alternatives_vm_independent.js')),mode],capture_output=True,text=True,timeout=10)
    assert completed.returncode==0,completed.stdout+completed.stderr
    result=json.loads(completed.stdout);assert result['mode']==mode and result['checks']>=4
