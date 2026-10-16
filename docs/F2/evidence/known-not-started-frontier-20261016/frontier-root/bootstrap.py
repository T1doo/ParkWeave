"""Record this continuation's actual environment and preserve prior evidence."""
from pathlib import Path
import json,hashlib,subprocess,datetime
root=Path('/workspace/ParkWeave');out=root/'.runtime/frontier-root';base='c2263edd889c2b9b4ada9f502b3a41b32eb9341f'
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
assert git('rev-parse','HEAD')==base and not git('status','--porcelain')
remote=git('ls-remote','--heads','origin');heads={line.split()[1]:line.split()[0] for line in remote.splitlines()}
assert heads['refs/heads/dev/f3-plan-replacement-reapproval-20261016']==base
assert heads['refs/heads/main']=='31e7acb7e53bb1ab6465b9daae59de28757f7583'
assert git('rev-parse','refs/remotes/origin/main')==heads['refs/heads/main']
assert subprocess.run(['git','merge-base','--is-ancestor',heads['refs/heads/main'],base],cwd=root).returncode==0
assert 'refs/heads/dev/f3-known-not-started-frontier-20261016' not in heads
(out/'initial-remote-heads.txt').write_text(remote+'\n')
oldroot=root/'.runtime/plan-replacement-root';preserved=json.loads((oldroot/'preserved-evidence-union.json').read_text())
seal=json.loads((oldroot/'seal.json').read_text());preserved.update(seal['eligible_raw_sha256'])
def add(p):preserved[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
add(oldroot/'seal.json')
audit=root/'.runtime/plan-replacement-audit'
for p in audit.rglob('*'):
 if p.is_file() and '__pycache__' not in p.parts:add(p)
for name in ('root','oracle','backend','ui','review','ui-fixture','real-html','chromium'):
 for p in (root/'.runtime'/('plan-replacement-'+name)).rglob('*private.json'):
  if p.is_file():add(p)
for path,sha in preserved.items():assert (root/path).is_file() and hashlib.sha256((root/path).read_bytes()).hexdigest()==sha,path
(out/'preserved-evidence-union.json').write_text(json.dumps(preserved,sort_keys=True,indent=2)+'\n')
record={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'head':base,'branch':git('branch','--show-current'),'status':git('status','--porcelain'),'worktrees':git('worktree','list','--porcelain'),'remote_heads_count':len(heads),'remote_heads_sha256':hashlib.sha256((remote+'\n').encode()).hexdigest(),'read_only_main':heads['refs/heads/main'],'remote_main_is_ancestor':True,'local_main_present':subprocess.run(['git','show-ref','--verify','--quiet','refs/heads/main'],cwd=root).returncode==0,'sole_shared_source_git_integrator':'root','isolated_private_agents':['frontier-backend','frontier-oracle','frontier-review','frontier-ui'],'prior_evidence_paths_unchanged':len(preserved),'default_network_read':'PASS','old_task_instances_restored':False}
(out/'baseline.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
