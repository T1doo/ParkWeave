"""Production recovery-reader deadline boundaries; actual HTTP cold/hot tests remain separate."""
import json,subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize('mode',['past','at_now','one_ms_valid','max_valid','over_max','zero','far_future','null','string','boolean','missing','extra_field'])
def test_actual_reader_deadline_boundaries_keep_other_original_handle(mode):
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(['node',str(Path(__file__).with_name('service_plan_handle_ttl_boundaries.js')),mode],
                          cwd=root,capture_output=True,text=True,timeout=15)
    assert result.returncode==0,result.stderr
    proof=json.loads(result.stdout)
    assert proof['checks']>=6 and proof['other_handle_preserved'] and proof['HTTP_requests']==0
