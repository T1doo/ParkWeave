"""Run original complete recovery module once after all queued tests finish."""
from pathlib import Path
import json,subprocess,sys,time,datetime
B=Path('.runtime/unified-propagation-final')
expected=['backend','root-1','root-2','new','independent-new','independent-prior','common','review','employees','additional','ci-metadata']
assert not (B/'recovery-solo.json').exists()
while not all((B/(n+'.json')).is_file() for n in expected):time.sleep(5)
for n in expected:
 d=json.loads((B/(n+'.json')).read_text());assert d['exit_code']==0 and d['counts']['FAIL']==d['counts']['ERROR']==0,n
 assert not d['source_drift'] and not d['all_tracked_drift'] and not d['runner_drift'],n
# Allow completed child/scheduler process reaping; this does not alter test budgets.
for attempt in range(12):
 processes=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:args=(p/'cmdline').read_bytes().split(b'\0')
  except (OSError,PermissionError):continue
  if len(args)>3 and args[1:3]==[b'-m',b'pytest']:processes.append(dict(pid=int(p.name),argv=[a.decode(errors='replace') for a in args if a]))
 if not processes:break
 time.sleep(2)
assert not processes,processes
proof=dict(status='NO_OTHER_PYTEST_BEFORE_SOLO',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),other_pytest=[],prior_windows=expected,original_budget_unchanged=True)
(B/'recovery-solo-environment.json').write_text(json.dumps(proof,indent=2)+'\n')
result=subprocess.run([sys.executable,str(B/'run_window.py'),'recovery-solo',str(B/'recovery-solo-modules.json')]);assert result.returncode==0,result.returncode
print('original complete30 recovery-solo PASS; all tests stopped',flush=True)
