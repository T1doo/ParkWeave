"""Actual stdlib child-process fault checks; never Chrome/PG/model/CI."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
source=Path(__file__).parent;root=Path(sys.argv[1]) if len(sys.argv)>1 else source;runner=source/'fixture_supervisor.py'
results=[]
sentinel=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'])
try:
 for scenario in ['normal','orphan','double_fork_setsid','stubborn','primary_checkpoint','term_fork','pidfd_denied','enumeration_failure','signal_denied']:
  directory=root/('case-'+scenario);directory.mkdir()
  run=subprocess.run([sys.executable,'-B',str(runner),scenario,str(directory),str(sentinel.pid)],capture_output=True,text=True,timeout=12)
  assert run.returncode==0,(scenario,run.stderr)
  r=json.loads(run.stdout);assert sentinel.poll() is None,(scenario,'independent sentinel was touched')
  assert all(s['pid']!=sentinel.pid for s in r['signals'])
  assert all(s['via']=='BIRTH_CHECKED_PIDFD' for s in r['signals'])
  if scenario in ['normal','orphan','double_fork_setsid','stubborn','primary_checkpoint','term_fork']:
   assert r['status']=='CLEANUP_CONFIRMED' and r['subtree_complete'] and r['bound_processes_exited'],(scenario,r)
   assert r['remaining_children']==r['remaining_private_session_members']==[]
  if scenario=='normal':assert not r['signals'] and r['worker_returncode']==0
  if scenario=='double_fork_setsid':assert any(p['initial_session']!=r['processes'][0]['pid'] for p in r['processes'])
  if scenario=='primary_checkpoint':assert r['preserved_checkpoint']['error']=='original primary failure' and r['preserved_checkpoint']['error_type']=='InjectedLaunchTimeout'
  if scenario=='pidfd_denied':assert not r['processes'] and not r['signals'] and not r['handshake']
  if scenario in ['pidfd_denied','enumeration_failure','signal_denied']:assert r['status']=='CLEANUP_UNCONFIRMED' and r['errors']
  if scenario=='signal_denied':assert len([e for e in r['errors'] if e['stage']=='pidfd_signal'])==1
  (directory/'result.json').write_text(json.dumps(r,indent=2)+'\n');results.append({'case':scenario,'status':'PASS','processes':len(r['processes']),'cleanup_result':r['status']})
finally:
 sentinel.terminate();sentinel.wait(timeout=5)
print(json.dumps({'status':'PASS','actual_stdlib_process_cases':len(results),'results':results,'browser_runs':0,'model_calls':0,'CI_runs':0},indent=2))
