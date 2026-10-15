"""Only balance unchanged frozen test runners; never alter product/test logic."""
from pathlib import Path
import subprocess,json,time,os,hashlib
base=Path('.runtime/fact-provenance-final-v2')
resume=json.loads((base/'rebalance-to-five.json').read_text())['state']
existing=resume['active']
pending=resume['pending']
active=set(existing);completed=resume['completed'];started=resume['started'];children={};logs={}
deadline=time.monotonic()+7200
while active or pending:
 if time.monotonic()>deadline:raise SystemExit('bounded scheduler deadline; preserve existing owned processes and logs')
 for name in list(active):
  result=base/(name+'.json')
  if not result.exists():continue
  d=json.loads(result.read_text());completed[name]={'exit_code':d['exit_code'],'counts':d['counts']};active.remove(name)
  if d['exit_code'] or d['source_drift'] or d['all_tracked_drift'] or not d['collection_junit_exact_match']:
   (base/'scheduler-stopped-for-failure.json').write_text(json.dumps(dict(failed=name,completed=completed,active=sorted(active),not_launched=pending),indent=2)+'\n');raise SystemExit(1)
 while pending and len(active)<5:
  name=pending.pop(0);assert not (base/(name+'.json')).exists()
  argv=['.venv/bin/python',str(base/'run_window_v2.py'),name,str(base/(name+'-modules.json'))]
  logs[name]=(base/(name+'-runner.log')).open('w');p=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=logs[name],stderr=subprocess.STDOUT)
  children[name]=p;active.add(name);started[name]=dict(pid=p.pid,argv=argv,utc=time.time())
 for name,p in children.items():
  if p.poll() is not None and name in active and not (base/(name+'.json')).exists():
   (base/'scheduler-stopped-for-launch-failure.json').write_text(json.dumps(dict(window=name,exit_code=p.returncode),indent=2)+'\n');raise SystemExit(1)
 (base/'scheduler-progress-v2.json').write_text(json.dumps(dict(active=sorted(active),pending=pending,completed=completed,started=started,source_sha=json.loads(Path('.runtime/fact-assertion-provenance-root/freeze-v2.json').read_text())['source_sha'],max_parallel=5),indent=2)+'\n')
 if active:time.sleep(2)
for p in children.values():assert p.wait()==0
for f in logs.values():f.close()
print('ALL QUEUED WINDOWS COMPLETED')
