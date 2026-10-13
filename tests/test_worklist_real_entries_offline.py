import json,subprocess
from pathlib import Path
import pytest


@pytest.mark.parametrize('mode',['run_403','run_403_invalid_json','run_403_pending_reference','material_to_receipt','material_to_localcase','receipt_reject_409','receipt_reject_422','receipt_reject_ambiguous','receipt_form_pending','receipt_form_unknown','resource_write_semantic','resource_write_pending','resource_write_unknown','history_rendered','history_pending',*[f'manual_receipt_{action}_{phase}' for action in ['SUBMIT','ACKNOWLEDGE','REQUEST_CHANGES','REOPEN'] for phase in ['pending','unknown']],*[
    'pending_'+name for name in ['prepCommandPending','caseFactPending','materialReusePending','receiptLocalPending','dispatchPending','servicePlanPending','resourceBindingPending','runAccessPending','prepRecoveryHandle','prepRecoveryChecking','oppBusy','fbBusy','planApprovalBusy','localCaseRecoveryBusy','servicePlanRecoveryChecking','handoffSubmitting','caseCancelBusy','caseReconBusy','bundleBusy','deliveryBusy','executionPreviewSubmitting','resourceExecutionPreviewSubmitting','dispatchExecutionPreviewSubmitting','receiptExecutionPreviewSubmitting','lifecycleExecutionPreviewSubmitting']]])
def test_full_original_page_entry_isolation(mode):
    result=subprocess.run(['node',str(Path(__file__).with_name('worklist_real_entries_offline.js')),mode],
        cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['checks']>=3
