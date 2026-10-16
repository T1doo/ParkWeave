"""Once-only idle CI then recovery, selected before any test outcome."""
from pathlib import Path
import json,time,subprocess,sys
b=Path('.runtime/plan-reapproval-final');selection=json.loads((b/'selection.json').read_text());expected=set(selection['main_windows'])-{'recovery-solo'}
while True:
 p=b/'scheduler-progress.json'
 if p.is_file():
  v=json.loads(p.read_text())
  if not v['active'] and not v['pending']:
   assert set(v['finished'])==expected and all(x==0 for x in v['finished'].values()),v
   break
 time.sleep(3)
assert (b/'wip-complete.json').is_file()
results={}
for n in ['ci-metadata-solo','recovery-solo']:
 assert not (b/(n+'.json')).exists(),'never repeat a solo window implicitly'
 with (b/(n+'-runner.log')).open('w') as log:
  results[n]=subprocess.run([sys.executable,str(b/'run_window.py'),n,str(b/(n+'-modules.json'))],stdout=log,stderr=subprocess.STDOUT).returncode
 print(n,results[n],flush=True)
(b/'solo-schedule-result.json').write_text(json.dumps(dict(policy='Original CI12 then recovery30 once, alone after all parallel main windows; no budget/assertion edits',results=results),indent=2)+'\n')
raise SystemExit(int(any(results.values())))
