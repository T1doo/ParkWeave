import json
from pathlib import Path
import subprocess
import pytest

@pytest.mark.parametrize('mode',['detail_success_late','detail_403_late','body_delay_success_aba',
    'body_delay_403_aba','three_requests_mixed_order','empty_duplicate_continue'])
def test_offline_notice_races(mode):
    result=subprocess.run(['node',str(Path(__file__).with_name('notice_vm_independent.js')),mode],
        capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    data=json.loads(result.stdout)
    assert data['mode']==mode and len(data['checks'])>=3
    assert data['scope']=='INDEPENDENT_OFFLINE_NODE_VM_ONLY'
