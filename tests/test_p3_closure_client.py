"""Original whole-page JS with controlled fixtures; not HTTP/PG/browser evidence."""
import json,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.mark.parametrize('mode',[
 'qualification_declined','qualification_withdrawn','qualification_refusal',
 'selection_status_aba','cold_history','late_preview_case','late_preview_identity',
 'late_preview_members','late_preview_clear','late_preview_aba',
 'opaque_unknown_cold_get','committed_unknown_proof_retains_opaque',
 'proposal_lost_ack','proposal_status_disabled'])
def test_original_page_p3_closure_exact_profile_and_preserved_unknown(mode):
 p=subprocess.run(['node','tests/p3_closure_client_probes.js',mode],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,p.stderr
 result=json.loads(p.stdout)
 assert result['checks']>=3 and result['actual_http'] is False and result['postgresql'] is False and result['real_browser']=='NOT_RUN' and result['backend_authority_claimed'] is False
 print(p.stdout.strip())
