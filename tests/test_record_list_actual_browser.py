"""Focused hosted browser receipt; no fixture passed off as formal source."""
import pytest
import os
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_ordinary_case_steps import ordinary

pytestmark=pytest.mark.skipif(os.environ.get('PW_BROWSER_NUMBER')!='10' or os.environ.get('RUNNER_ENVIRONMENT')!='github-hosted',
    reason='Only exact hosted run10 driver executes this focused browser receipt')


def test_same_named_lists_actual_browser_and_current_read_revocation(ordinary,tmp_path,request):
    run=getattr(request.config,'_record_list_browser',None)
    if run is None:pytest.skip('Exact hosted run10 driver supplies the sandboxed browser')
    from scripts.record_list_browser_once import perform
    perform(run,ordinary,tmp_path)
