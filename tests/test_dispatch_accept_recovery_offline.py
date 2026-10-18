"""Narrow production reader/context contracts under Node VM, no actual HTTP."""
import json,subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize('mode',['past','now','one_ms','max','over','zero','far','null','string','boolean',
    'extra','oversize','malformed','storage_error','limit','other_actor','committed','not_observed',
    'wrong_proof','replacement','late_200','late_403','outer_case_ABA','outer_identity_ABA','outer_replacement','current_bad_history','current_bad_role','current_bad_revision','current_bad_offer','current_bad_executor','render_failure'])
def test_actual_accept_recovery_storage_and_async_boundaries(mode):
    root=Path(__file__).resolve().parents[1]
    p=subprocess.run(['node',str(Path(__file__).with_name('dispatch_accept_recovery_offline.js')),mode],
                     cwd=root,capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stderr
    proof=json.loads(p.stdout);assert proof['POST_stubs']==0 and proof['removals']==0
