from pathlib import Path
import subprocess,json
base=Path('.runtime/template-local-migration-20261014')
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
source=Path(base/'source-sha.txt').read_text().strip();branch='dev/f2-worklist-entry-isolation-20261013'
assert git('branch','--show-current')==branch
assert git('remote','get-url','origin')=='https://github.com/T1doo/ParkWeave.git'
head=git('rev-parse','HEAD');raw=git('ls-remote','--heads','origin')+'\n';(base/'remote-final.tsv').write_text(raw)
parse=lambda text:{ref:sha for sha,ref in (line.split() for line in text.splitlines())}
before=parse((base/'remote-before.tsv').read_text());after=parse(raw);own='refs/heads/'+branch
other_changes={ref:[before.get(ref),after.get(ref)] for ref in before.keys()|after.keys() if ref!=own and before.get(ref)!=after.get(ref)}
protected={'main':'31e7acb7e53bb1ab6465b9daae59de28757f7583','dev/f1-foundation':'b58cf201de3d6ca4e249bec3e8544ea53163807a','dev/f2-resource-alternative-times-20261011':'e40bd24329ec21bd881ee7521e63e32a8ee3c13a'}
assert not other_changes,other_changes
assert after[own]==head
assert all(after['refs/heads/'+name]==sha for name,sha in protected.items())
counts=git('rev-list','--left-right','--count','HEAD...refs/remotes/origin/'+branch).split();assert counts==['0','0'],counts
assert git('status','--porcelain')==''
source_diff=git('diff','--name-only',source,'HEAD','--','src','tests','scripts','pyproject.toml');assert source_diff==''
assert subprocess.run(['git','merge-base','--is-ancestor',source,'HEAD']).returncode==0
record=dict(source_sha=source,delivery_sha=head,branch=branch,remote_branch_sha=after[own],remote_heads_before=len(before),remote_heads_after=len(after),other_branch_changes=other_changes,protected=protected,unpushed_ahead=int(counts[0]),unpushed_behind=int(counts[1]),working_tree_clean=True,source_to_delivery_product_test_diff=[],source_ancestor=True)
(base/'delivery-verification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record))
