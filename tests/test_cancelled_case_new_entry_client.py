"""Real HTML function probes with explicit NodeVM doubles; no HTTP/browser/PG claim."""
import json, os, subprocess
from pathlib import Path
import pytest
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'src/parkweave/web.html').is_file())
MODES=['positive','cold_disabled','not_cancelled','foreign_owner','foreign_case','wrong_scope','not_owner',
 'unknown_handle','corrupt_handle','cold_unknown','pending','lease','original_unknown','stale_context',
 'token_change','read_replaced','unconfirmed_after_get','pending_after_get','unknown_after_get',
 'fresh_not_cancelled','fresh_foreign_owner','fresh_foreign_case','fresh_stale_source','fresh_stale_revision','revoked']
@pytest.mark.parametrize('mode',MODES)
def test_cancelled_case_new_entry_only_read_navigation(mode):
    probe=os.environ.get('NEW_CASE_PROBE','tests/cancelled_case_new_entry_probes.js')
    p=subprocess.run(['node',probe,mode],cwd=ROOT,capture_output=True,text=True,timeout=15)
    assert p.returncode==0,p.stderr
    x=json.loads(p.stdout)
    assert x['mode']==mode and x['checks']>=4 and x['actual_http'] is False and x['real_browser']=='NOT_RUN'
