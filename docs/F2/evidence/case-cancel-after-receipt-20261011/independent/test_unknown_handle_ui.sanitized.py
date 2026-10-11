"""Actual cold hydrate plus production capture callback, offline only."""
from pathlib import Path
import subprocess,shutil

def test_cold_unknown_request_blocks_all_case_business_form_submits():
 root=Path('/workspace/ParkWeave')
 script=root/'.runtime/case-cancel-after-receipt/independent-review/cold_hydrate_capture.js'
 node=shutil.which('node');assert node
 result=subprocess.run([node,str(script),'capture'],cwd=root,capture_output=True,text=True,timeout=15)
 print(result.stdout,end='')
 print(result.stderr,end='')
 assert result.returncode==0,result.stdout+result.stderr
