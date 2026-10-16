from pathlib import Path
import subprocess,concurrent.futures,json,time
r=Path('.runtime/frontier-root/v2');windows=json.loads((r/'final-windows.json').read_text())
jobs=[w for w in windows if w['window'] not in ('recovery-solo',)]
priority={'direct-business-01':0,'direct-business-02':1,'ci-diagnostics-early':2,'frontier-core-client':3,'frontier-page':4,'frontier-independent':5}
jobs.sort(key=lambda w:priority.get(w['window'],6))
status={'scope':'FROZEN_COMPLETE_MODULE_WINDOWS','max_concurrent_root_windows':3,'independent_window_separate':'frontier-independent','jobs':[]}
def run(w):
 name=w['window'];args=['.venv/bin/python',str(r/'runner/run_window.py'),name,str(r/'final'/(name+'-modules.json'))];start=time.monotonic()
 with (r/'final'/(name+'-runner.log')).open('w') as f:code=subprocess.run(args,stdout=f,stderr=subprocess.STDOUT).returncode
 receipt={'window':name,'exit_code':code,'elapsed_seconds':time.monotonic()-start,'argv':args}
 path=r/'final'/(name+'.json')
 if path.exists():receipt['counts']=json.loads(path.read_text())['counts']
 return receipt
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 for future in concurrent.futures.as_completed([pool.submit(run,w) for w in jobs]):
  receipt=future.result();status['jobs'].append(receipt);(r/'final/pool-status.json').write_text(json.dumps(status,indent=2)+'\n');print(json.dumps(receipt),flush=True)
status['complete']=True;(r/'final/pool-status.json').write_text(json.dumps(status,indent=2)+'\n')
raise SystemExit(int(any(x['exit_code'] for x in status['jobs'])))
