import json,selectors,subprocess
from pathlib import Path
import pytest
from test_preparation import preparation_fixture,headers


@pytest.mark.parametrize('mode',['intake_success','intake_candidate','intake_unknown','intake_wrong_run','run_403','run_403_invalid_json','run_403_pending_reference','material_to_receipt','material_to_localcase','receipt_reject_409','receipt_reject_422','receipt_reject_ambiguous','receipt_form_pending','receipt_form_unknown','resource_write_semantic','resource_write_pending','resource_write_unknown','history_rendered','history_pending',*[f'manual_receipt_{action}_{phase}' for action in ['SUBMIT','ACKNOWLEDGE','REQUEST_CHANGES','REOPEN'] for phase in ['pending','unknown']],*[
    'pending_'+name for name in ['prepCommandPending','caseFactPending','materialReusePending','receiptLocalPending','dispatchPending','servicePlanPending','resourceBindingPending','runAccessPending','prepRecoveryHandle','prepRecoveryChecking','oppBusy','fbBusy','planApprovalBusy','localCaseRecoveryBusy','servicePlanRecoveryChecking','handoffSubmitting','caseCancelBusy','caseReconBusy','bundleBusy','deliveryBusy','executionPreviewSubmitting','resourceExecutionPreviewSubmitting','dispatchExecutionPreviewSubmitting','receiptExecutionPreviewSubmitting','lifecycleExecutionPreviewSubmitting']]])
def test_full_original_page_entry_isolation(mode):
    result=subprocess.run(['node',str(Path(__file__).with_name('worklist_real_entries_offline.js')),mode],
        cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)['checks']>=3


def test_cold_original_entries_use_owned_asgi_run_preparation_and_evidence(preparation_fixture):
    f=preparation_fixture
    proc=subprocess.Popen(['node',str(Path(__file__).with_name('worklist_real_entries_offline.js')),'intake_cold_asgi'],
        cwd=Path(__file__).resolve().parents[1],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    requests=[];selector=selectors.DefaultSelector();selector.register(proc.stdout,selectors.EVENT_READ)
    try:
        while True:
            assert selector.select(timeout=15),'Cold entry bridge made no progress within15 seconds'
            line=proc.stdout.readline()
            if not line:break
            message=json.loads(line)
            if 'request' not in message:
                assert message['mode']=='intake_cold_asgi' and message['checks']>=12
                break
            request=message['request'];options=request['options'];method=options.get('method','GET')
            requests.append((method,request['path']))
            h=headers(f[2],key=options.get('headers',{}).get('Idempotency-Key'))
            response=f[3].request(method,request['path'],headers=h,json=json.loads(options['body']) if options.get('body') else None)
            assert response.status_code<400,(method,request['path'],response.status_code)
            if method=='POST' and request['path']=='/api/runs':f[0].finish(f[0].claim('synthetic-cold-entry'))
            proc.stdin.write(json.dumps({'status':response.status_code,'body':response.json()})+'\n');proc.stdin.flush()
        assert proc.wait(timeout=15)==0,proc.stderr.read()
        assert len([r for r in requests if r[0]=='POST'])==4
    finally:
        selector.close()
        if proc.poll() is None:proc.terminate();proc.wait(timeout=5)
