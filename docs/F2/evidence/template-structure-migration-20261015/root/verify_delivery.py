from pathlib import Path
import json,subprocess
root=Path.cwd();base=root/'.runtime/template-structure-migration-20261015'
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
branch=git('branch','--show-current');head=git('rev-parse','HEAD');source=(base/'source-sha.txt').read_text().strip()
assert branch=='dev/f2-worklist-entry-isolation-20261013'
remote=git('ls-remote','--heads','origin');(base/'remote-final.tsv').write_text(remote+'\n')
parse=lambda text:{ref:sha for sha,ref in (l.split() for l in text.splitlines())}
before=parse((base/'remote-before.tsv').read_text());after=parse(remote);own='refs/heads/'+branch
assert after[own]==head
changed={ref:[before.get(ref),after.get(ref)] for ref in before.keys()|after.keys() if ref!=own and before.get(ref)!=after.get(ref)}
assert not changed,changed
subprocess.run(['git','fetch','origin',own+':refs/remotes/origin/'+branch],check=True)
status=git('status','--porcelain=v1');aheadbehind=git('rev-list','--left-right','--count','HEAD...origin/'+branch)
assert not status,status
assert aheadbehind.split()==['0','0'],aheadbehind
assert not git('diff',source,'HEAD','--','src','tests','scripts','pyproject.toml')
for ref in ['refs/heads/main','refs/heads/dev/f1-foundation','refs/heads/dev/f2-resource-alternative-times-20261011']:
 assert before[ref]==after[ref]
 subprocess.run(['git','merge-base','--is-ancestor',after[ref],'HEAD'],check=True)
report=dict(source_sha=source,delivery_sha=head,branch=branch,remote_head=after[own],remote_heads=len(after),other_heads_unchanged=len(after)-1,unexpected_other_ref_changes=changed,protected_refs={r:after[r] for r in ['refs/heads/main','refs/heads/dev/f1-foundation','refs/heads/dev/f2-resource-alternative-times-20261011']},working_tree_clean=True,ahead=0,behind=0,source_test_script_pyproject_diff=False)
(base/'delivery-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
