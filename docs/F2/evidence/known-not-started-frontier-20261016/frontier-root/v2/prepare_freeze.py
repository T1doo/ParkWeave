"""Create an immutable complete-module selection only after source integration."""
from pathlib import Path
import hashlib,json,subprocess,datetime,ast
R=Path('/workspace/ParkWeave');V=R/'.runtime/frontier-root/v2'
def git(*a):return subprocess.check_output(['git',*a],cwd=R,text=True).strip()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert git('branch','--show-current')=='dev/f3-known-not-started-frontier-20261016'
assert not git('status','--porcelain'), 'all tracked source must already be committed'
head=git('rev-parse','HEAD');assert head!='c2263edd889c2b9b4ada9f502b3a41b32eb9341f'
remote=git('ls-remote','--heads','origin');heads={x.split()[1]:x.split()[0] for x in remote.splitlines()}
assert heads['refs/heads/main']=='31e7acb7e53bb1ab6465b9daae59de28757f7583'
assert heads['refs/heads/dev/f3-plan-replacement-reapproval-20261016']=='c2263edd889c2b9b4ada9f502b3a41b32eb9341f'
assert 'refs/heads/dev/f3-known-not-started-frontier-20261016' not in heads
assert subprocess.run(['git','merge-base','--is-ancestor',heads['refs/heads/main'],head],cwd=R).returncode==0
assert git('rev-parse','refs/remotes/origin/main')==heads['refs/heads/main']
old=json.loads((R/'.runtime/plan-replacement-root/v4/final-windows.json').read_text());mods=[p for w in old for p in w['modules']];assert len(mods)==len(set(mods))==140
added=json.loads((R/'.runtime/frontier-root/v2/direct-effect-regression-design.json').read_text())['added_directly_affected_complete_modules'];assert not set(added)&set(mods)
new=sorted(str(p.relative_to(R)) for p in (R/'tests').glob('test_frontier_*.py'))
ind=[p for p in new if any(s in p for s in ('independent','epoch_probes','p4_race'))];page=[p for p in new if any(s in p for s in ('real_html','chromium'))];core=[p for p in new if p not in ind+page]
windows=old[:-1]+[dict(window='direct-business-01',modules=added[:8]),dict(window='direct-business-02',modules=added[8:]),dict(window='frontier-core-client',modules=core),dict(window='frontier-independent',modules=ind),dict(window='frontier-page',modules=page)]+old[-1:]
allmods=[p for w in windows for p in w['modules']];assert len(allmods)==len(set(mods+added+new));assert all((R/p).is_file() for p in allmods)
ci=json.loads((R/'.runtime/plan-replacement-root/v4/final/ci-metadata-solo.json').read_text())['modules'];assert not set(ci)&set(allmods)
assert not (V/'freeze.json').exists() and not (V/'final').exists();(V/'final').mkdir()
for w in windows+[dict(window='ci-metadata-solo',modules=ci)]:
 (V/'final'/(w['window']+'-modules.json')).write_text(json.dumps(w['modules'],indent=2)+'\n')
(V/'final-windows.json').write_text(json.dumps(windows,indent=2)+'\n');(V/'final-selection.json').write_text(json.dumps(windows,indent=2)+'\n')
source=[p for p in git('ls-files','-z','--','src','tests','scripts','pyproject.toml').split('\0') if p]
tracked=[p for p in git('ls-files','-z').split('\0') if p]
runners=[str(p.relative_to(R)) for p in (V/'runner').glob('*.py')]+[str(p.relative_to(R)) for p in V.glob('*.py')]+[str((V/'final-windows.json').relative_to(R))]+[str(p.relative_to(R)) for p in (V/'final').glob('*-modules.json')]
freeze=dict(scope='FROZEN_KNOWN_NOT_STARTED_ORIGINAL_BUSINESS_FRONTIER',source_sha=head,base_sha='c2263edd889c2b9b4ada9f502b3a41b32eb9341f',utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_paths={p:sha(R/p) for p in source},all_tracked_sha256={p:sha(R/p) for p in tracked},runner_paths={p:sha(R/p) for p in runners},max_root_test_windows=3,max_independent_test_windows=0,bounded_retry_policy='At most one same-SHA identical complete-module retry per failed window, original assertions and budgets unchanged; failed raw retained, final selection may substitute only the whole matching window.',special_pg27='NOT_RUN original profile/role gate unchanged',selected_complete_modules=len(allmods),prior_complete_modules=140,direct_added_modules=len(added),new_modules=new,remote_heads_count=len(heads),remote_heads_sha256=hashlib.sha256((remote+'\n').encode()).hexdigest())
(V/'freeze.json').write_text(json.dumps(freeze,sort_keys=True,indent=2)+'\n');print(json.dumps({k:v for k,v in freeze.items() if k not in ('source_paths','all_tracked_sha256','runner_paths')}))
