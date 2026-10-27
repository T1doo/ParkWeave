"""Observed cancellation fences with controlled preflight/fetch doubles only.

Fixture allow flags do not establish tracked schema33 eligibility. The real
before_receipt policy is tested separately; reconciliation retains its old gate.
Fresh retry here proves exact-409 classification and page controls, not PG effects.
"""
import json,subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
@pytest.mark.parametrize('route',['before_accept','before_receipt','reconcile_request','reconcile_record','reconcile_finish'])
@pytest.mark.parametrize('variant',['captured','ordinary','stale_context','stale_source','malformed','stale_retry','other_conflict','unknown','classification'])
def test_cancel_capture_original_fence_and_preserve_unknown(route,variant):
 p=subprocess.run(['node','tests/frontier_cancel_client_probes.js',route+':'+variant],cwd=ROOT,capture_output=True,text=True,timeout=15)
 assert p.returncode==0,p.stderr
 value=json.loads(p.stdout);assert value['checks']>=1 and value['actual_http'] is False and value['real_browser']=='NOT_RUN'
