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


@pytest.mark.parametrize('mode',['lost_response','cold_recovery','unknown_not_observed','corrupt_proof','revoked','late_read','late_post','pending_other_operation','cancelled_dispatch','late_recovery','wrong_scope','late_receipt','late_dispatch'])
def test_accepted_case_cancel_ui(mode):
 node=shutil.which('node');assert node,'Node is required for this offline acceptance'
 result=subprocess.run([node,'tests/case_cancellation_offline.js','after_'+mode],capture_output=True,text=True,timeout=15)
 assert result.returncode==0,result.stderr
 data=json.loads(result.stdout);assert data['mode']=='after_'+mode and data['checks']>0


@pytest.mark.parametrize('mode',['lost_response','record_lost_response','finish_lost_response','cold_recovery','unknown_not_observed','corrupt_proof','wrong_scope','wrong_action','missing_causal_event','revoked','expired_handle','cold_hydrate','storage_bounds','future_handle','unknown_handle_all_forms','unknown_handle_other_case','resource_release_and_history','cross_case_plan_delivery_approval','receipt_create_uses_preparation','dynamic_writes','late_read','late_post','late_recovery','explicit_outcomes','unresolved_does_not_finalize','pending_other_operation','late_phase_read','late_receipt','late_dispatch'])
def test_manual_receipt_cancellation_reconciliation_ui(mode):
 node=shutil.which('node');assert node,'Node is required for this offline acceptance'
 result=subprocess.run([node,'tests/case_cancellation_reconciliation_offline.js',mode],capture_output=True,text=True,timeout=15)
 assert result.returncode==0,result.stderr
 data=json.loads(result.stdout);assert data['mode']==mode and data['checks']>0 and data['browser_attempts']==0
