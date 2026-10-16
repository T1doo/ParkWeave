from pathlib import Path
import json,subprocess,sys,time
b=Path('.runtime/plan-reapproval-final/v2');selection=json.loads((b/'selection.json').read_text());expected=set(selection['main_windows'])-{'recovery-solo'}
while True:
 try:v=json.loads((b/'scheduler-progress.json').read_text())
 except (FileNotFoundError,json.JSONDecodeError):time.sleep(2);continue
 if not v['active'] and not v['pending']:
  assert set(v['finished'])==expected;break
 time.sleep(2)
results={}
for n in ['ci-metadata-solo','recovery-solo']:
 assert not (b/(n+'.json')).exists(),'No automatic retry'
 with (b/(n+'-runner.log')).open('w') as log:results[n]=subprocess.run([sys.executable,str(b/'run_window.py'),n,str(b/(n+'-modules.json'))],stdout=log,stderr=subprocess.STDOUT).returncode
 print(n,results[n],flush=True)
(b/'solo-schedule-result.json').write_text(json.dumps(dict(policy='Original CI12 then recovery30 once alone after first full parallel suite; budgets/assertions unchanged',parallel_results=v['finished'],results=results),indent=2)+'\n')
raise SystemExit(int(any(results.values())))
