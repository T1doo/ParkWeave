"""Current Case versus separately selected Case projection in actual NodeVM UI."""
from pathlib import Path
import subprocess,shutil
import pytest

@pytest.mark.parametrize('mode',['controlled_plan_other_case','delivery_other_case','approval_propose_other_case','receipt_create_uses_current_preparation'])
def test_case_capture_uses_action_owned_case_not_unrelated_preparation(mode):
 root=Path('/workspace/ParkWeave');node=shutil.which('node');assert node
 result=subprocess.run([node,str(root/'.runtime/case-cancel-after-receipt/independent-review/cross_case_capture.js'),mode],cwd=root,capture_output=True,text=True,timeout=15)
 print(result.stdout,end='');print(result.stderr,end='')
 assert result.returncode==0,result.stdout+result.stderr
