from pathlib import Path
import json,subprocess,sys,time,os
b=Path('.runtime/plan-reapproval-final/v2');queue=json.loads((b/'parallel-order.json').read_text());selection=json.loads((b/'selection.json').read_text())
assert set(queue)==set(selection['main_windows'])-{'recovery-solo'} and len(queue)==len(set(queue))
assert not any((b/(n+'.json')).exists() for n in queue)
active={};finished={}
def save():
 p=b/'scheduler-progress.tmp';p.write_text(json.dumps(dict(finished=finished,active=list(active),pending=queue),indent=2)+'\n');os.replace(p,b/'scheduler-progress.json')
while queue or active:
 for n,p in list(active.items()):
  code=p.poll()
  if code is None:continue
  finished[n]=code;del active[n];print('finished',n,code,flush=True)
 while queue and len(active)<4:
  n=queue.pop(0)
  with (b/(n+'-runner.log')).open('w') as log:active[n]=subprocess.Popen([sys.executable,str(b/'run_window.py'),n,str(b/(n+'-modules.json'))],stdout=log,stderr=subprocess.STDOUT)
  print('started',n,active[n].pid,flush=True)
 save()
 if queue or active:time.sleep(2)
print('All parallel windows completed; CI12 and recovery30 run once alone, even if another check failed.',flush=True)
raise SystemExit(int(any(finished.values())))
