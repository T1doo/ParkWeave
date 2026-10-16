"""One bounded full CI window rerun after idle, then original full recovery."""
from pathlib import Path
import json,subprocess,sys,time,datetime
B=Path('.runtime/unified-propagation-final');expected=['backend','root-1','root-2','new','independent-new','independent-prior','common','review','employees','additional','ci-metadata']
assert not (B/'ci-metadata-solo.json').exists() and not (B/'recovery-solo.json').exists()
while not all((B/(n+'.json')).is_file() for n in expected):time.sleep(5)
for n in expected:
 d=json.loads((B/(n+'.json')).read_text());assert not d['source_drift'] and not d['all_tracked_drift'] and not d['runner_drift'],n
 if n=='ci-metadata':assert d['exit_code']==1 and d['counts']==dict(PASS=432,FAIL=1,ERROR=0,SKIP=14),d['counts']
 else:assert d['exit_code']==0 and d['counts']['FAIL']==d['counts']['ERROR']==0,n
# The original supervisor fails naturally after reading original CI failure.
for attempt in range(60):
 active=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:a=[s.decode(errors='replace') for s in (p/'cmdline').read_bytes().split(b'\0') if s]
  except OSError:continue
  if len(a)>1 and (a[1:3]==['-m','pytest'] or Path(a[1]).name in {'schedule.py','run_window.py','finish_solo.py'}):active.append(dict(pid=int(p.name),argv=a))
 if not active:break
 time.sleep(2)
assert not active,active
proof=dict(status='NO_OTHER_PYTEST_BEFORE_COMPLETE_CI_RETRY',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),other_pytest=[],original_ci_counts=dict(PASS=432,FAIL=1,ERROR=0,SKIP=14),reason='Original .6s timeout exited124 but stdout empty before synthetic print; preserve whole original window; exactly one full12-module retry in idle environment, no code/assertion/budget changes.',full_ci_modules=12)
(B/'ci-metadata-solo-environment.json').write_text(json.dumps(proof,indent=2)+'\n')
code=subprocess.run([sys.executable,str(B/'run_window.py'),'ci-metadata-solo',str(B/'ci-metadata-modules.json')]).returncode;assert code==0,code
(B/'recovery-solo-environment.json').write_text(json.dumps(dict(status='NO_OTHER_PYTEST_BEFORE_SOLO',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),other_pytest=[],original_budget_unchanged=True,ci_full_retry_completed=True),indent=2)+'\n')
code=subprocess.run([sys.executable,str(B/'run_window.py'),'recovery-solo',str(B/'recovery-solo-modules.json')]).returncode;assert code==0,code
print('complete12 CI once-idle retry and original complete30 recovery-solo PASS',flush=True)
