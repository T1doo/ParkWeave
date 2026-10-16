"""Original full HTML with controlled GET/transport; no HTTP/browser claims."""
import json,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.mark.parametrize('mode',['capture_shape','dispatch_offer','dispatch_accept','dispatch_reassign','receipt_create','receipt_submit','receipt_ack','receipt_local','ordinary_receipt','lifecycle'])
def test_original_business_writer_captures_get_fence_without_refresh(mode):
 p=subprocess.run(['node','tests/frontier_business_client_probes.js',mode],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,p.stderr
 value=json.loads(p.stdout);assert value['checks']>=3 and value['actual_http'] is False and value['real_browser']=='NOT_RUN' and value['automatic_fresh_get'] is False
