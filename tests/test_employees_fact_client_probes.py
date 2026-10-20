"""Controlled shipped-client probes, separately counted from browser/API/PG."""
import json
from pathlib import Path
import subprocess


def test_employees_client_late_crypto_and_rehashed_flags():
    root=Path(__file__).resolve().parents[1] if Path(__file__).parent.name=='tests' else Path.cwd()
    candidate=Path(__file__).with_name('employees_fact_client_probes.js')
    run=subprocess.run(['node',str(candidate)],cwd=root,text=True,capture_output=True,timeout=20)
    assert run.returncode==0,run.stderr
    result=json.loads(run.stdout)
    assert result['evidence_kind']=='CONTROLLED_CLIENT_FUNCTION_PROBES_NO_HTTP_BROWSER_PG'
    assert [r['scenario'] for r in result['results']]==[
        'late_reject_after_case_switch','late_success_after_sequence_switch','draft_changed_current_sequence',
        'rehashed_selected_changed_mismatch','rehashed_aggregate_changed_mismatch',
        'current403_dispatch_clears_original_private_preparation','old_button_rejects_new_manual_scope_before_projection']
    assert all(r['status']=='PASS' for r in result['results'])
