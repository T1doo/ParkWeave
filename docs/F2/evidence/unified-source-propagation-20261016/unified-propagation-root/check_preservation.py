"""Read-only preservation of prior task evidence and original remote branches."""
from pathlib import Path
import hashlib,json,datetime,subprocess
R=Path('.runtime/unified-propagation-root');b=json.loads((R/'baseline.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
drift=[p for p,h in b['prior_raw_sha256'].items() if not Path(p).is_file() or sha(Path(p))!=h];assert not drift,drift
cutoff=datetime.datetime.fromisoformat(b['utc']).timestamp();old=[];newer=[]
for p in Path('.runtime').iterdir():
 if p.is_dir() and p.name.startswith(('fact-assertion-provenance-','fact-provenance-','at24-27-','manual-continuation-','multifield-source-','note-template-carry-')):
  old.append(str(p))
  for q in p.rglob('*'):
   if not q.is_file() or any(s in q.parts for s in ('__pycache__','.pytest_cache','pytest-cache','pg','postgres','postgresql','pgdata','xdg-cache')):continue
   if q.stat().st_mtime>cutoff:newer.append(str(q))
assert not newer,('old non-cache task writes after baseline',newer)
remote={line.split('\t')[1]:line.split('\t')[0] for line in subprocess.check_output(['git','ls-remote','--heads','origin'],text=True).splitlines()}
assert all(remote.get(p)==h for p,h in b['refs'].items())
d=dict(status='PASS',prior_raw_preserved=len(b['prior_raw_sha256']),prior_raw_drift=[],old_task_roots_checked=old,old_non_cache_files_written_after_baseline=[],baseline_remote_heads_preserved=len(b['refs']),main_sha=remote['refs/heads/main'],default_network=True,utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
(R/'final-preservation.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:v for k,v in d.items() if k!='old_task_roots_checked'}))
