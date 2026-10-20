"""Actual notification JS under offline DOM/fetch doubles, no browser/navigation."""
from pathlib import Path
import json
import shutil
import subprocess
import pytest


@pytest.mark.parametrize('mode',[
    'empty_continue','refresh_order','continue_then_refresh','identity_aba',
    'current_denied','stale_denied','detail_clears','stale_card','malformed_response','clear_inflight',
    'auth_401_json','auth_403_json','auth_401_html','auth_403_html','auth_401_pending','auth_403_pending',
    'late_auth_401','late_auth_403',
])
def test_original_notice_section_offline_pagination(mode):
    node=shutil.which('node')
    assert node, 'Node is required for the explicitly offline notification check'
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run([node,str(root/'tests/dispatch_notice_pagination_offline.js'),
                           str(root/'src/parkweave/web.html'),mode],
                          capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    evidence=json.loads(result.stdout)
    assert evidence['mode']==mode and len(evidence['checks'])>=2
    assert evidence['scope']=='NODE_VM_WITH_DOM_AND_FETCH_DOUBLES_ONLY'


def test_original_notice_refusal_headers_with_real_unfinished_http_body():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(['node',str(root/'tests/dispatch_notice_auth_http.js'),
                           str(root/'src/parkweave/web.html')],
                          capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    evidence=json.loads(result.stdout)
    assert [x['status'] for x in evidence]==[401,403]
    assert all(x['result']=='PASS' and x['error_body_finished'] is False and x['requests']==2
               and x['scope']=='WHOLE_PAGE_JS_REAL_LOOPBACK_HTTP_MECHANICAL_DOM' for x in evidence)
