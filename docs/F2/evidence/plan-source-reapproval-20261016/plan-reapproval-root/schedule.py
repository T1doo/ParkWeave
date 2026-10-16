from pathlib import Path
import subprocess,json,time,sys
b=Path('.runtime/plan-reapproval-final')
queue=['backend','root-1','root-2','new-independent','extra-backend','extra-browser','new-chromium','prior-unified','independent-new','independent-prior','common','review','employees','additional','new-core']
active={};finished={}
assert not any((b/(n+'.json')).exists() for n in queue)
while queue or active:
 for n,p in list(active.items()):
  code=p.poll()
  if code is None:continue
  finished[n]=code;del active[n]
  print('finished',n,code,flush=True)
 while queue and len(active)<(4 if (b/'wip-complete.json').is_file() else 3):
  n=queue.pop(0);stream=(b/(n+'-runner.log')).open('w');active[n]=subprocess.Popen([sys.executable,str(b/'run_window.py'),n,str(b/(n+'-modules.json'))],stdout=stream,stderr=subprocess.STDOUT);stream.close();print('started',n,active[n].pid,flush=True)
 (b/'scheduler-progress.json').write_text(json.dumps(dict(finished=finished,active=list(active),pending=queue),indent=2)+'\n')
 if queue or active:time.sleep(3)
assert all(code==0 for code in finished.values()),finished
print('All parallel main windows complete; CI12 then recovery30 must run alone.',flush=True)
