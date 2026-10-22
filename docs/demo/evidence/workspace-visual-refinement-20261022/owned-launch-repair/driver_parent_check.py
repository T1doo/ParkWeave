"""Injected parent finalization only; no Chrome/process/server/publication execution."""
from pathlib import Path
from unittest.mock import patch
import json,os,tempfile
from scripts import workspace_visual_browser_once as m
source='214fc8b07afa2d541b9b49d010a78f7537e7eb78'
root=Path(tempfile.mkdtemp(prefix='parent-check-',dir=Path(__file__).parent));results=[]
for scenario in ('clean_pass','cleanup_unconfirmed','output_truncated'):
 private=root/scenario;private.mkdir();runner=private/'runner';runner.mkdir();published=[]
 def supervise(*args,**kwargs):
  (private/'worker-state.json').write_text(json.dumps(dict(m.REPORT,status='PASS',source_sha=source,worker_final=True)))
  (private/'worker-output.log').write_bytes(b'x'*(256*1024+1 if scenario=='output_truncated' else 2))
  return dict(status='CLEANUP_UNCONFIRMED' if scenario=='cleanup_unconfirmed' else 'CLEANUP_CONFIRMED',operation_status='PASS')
 def finish(report,*args,**kwargs):published.append(report);return 0 if report['status']=='PASS' else 1
 with patch.dict(os.environ,{'RUNNER_TEMP':str(runner)}),patch.object(m.base,'require_hosted',return_value=source),patch.object(m.tempfile,'mkdtemp',return_value=str(private)),patch.object(m,'supervise',side_effect=supervise),patch.object(m.base,'finish_report',side_effect=finish):code=m.main()
 assert len(published)==1
 want='PASS' if scenario=='clean_pass' else 'FAIL';assert published[0]['status']==want and code==(0 if want=='PASS' else 1)
 if scenario=='output_truncated':assert published[0]['worker_output_truncated'] and len(published[0]['worker_output_text'])==256*1024
 results.append(dict(case=scenario,status='PASS',expected_terminal=want))
print(json.dumps(dict(status='PASS',injected_parent_cases=len(results),results=results,actual_browser_runs=0,actual_servers_started=0,CI_runs=0),indent=2))
