"""Actual narrow production functions under Node VM; controlled promise boundaries."""
import json,subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize('mode',['past','now','one_ms','max','over','zero','far','null','string','boolean',
    'extra','oversize','malformed','storage_error','limit','other_actor','committed','not_observed',
    'wrong_proof','replacement','late_200','late_403','outer_case_ABA','outer_identity_ABA','outer_replacement',
    'current_bad_history','current_bad_receipt','current_bad_role','current_bad_revision','current_bad_executor',
    'current_replacement','current_ABA','render_failure','release_success','send_storage_failure','send_draft_changed','send_late_context','send_reply_unknown','send_replacement'])
def test_manual_submit_original_key_storage_and_async_boundaries(mode):
    root=Path(__file__).resolve().parents[1]
    p=subprocess.run(['node',str(Path(__file__).with_name('receipt_submit_recovery_offline.js')),mode],
                     cwd=root,capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stderr
    proof=json.loads(p.stdout);assert proof['POST_stubs']==(1 if mode in ('send_draft_changed','send_late_context','send_reply_unknown','send_replacement') else 0)
    assert proof['removals']==(1 if mode in ('release_success','send_draft_changed') else 0)
