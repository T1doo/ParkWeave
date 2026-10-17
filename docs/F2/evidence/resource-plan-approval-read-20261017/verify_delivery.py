"""Read the actual remote after ordinary dev-branch push; no tracking-ref assumption."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess

root=Path('/workspace/ParkWeave');r=root/'.runtime/resource-plan-approval-read'
def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True)
f=json.loads((r/'freeze-v2.json').read_text());gate=json.loads((root/'docs/F2/evidence/resource-plan-approval-read-20261017/gate.json').read_text())
head=git('rev-parse','HEAD').strip();branch=git('branch','--show-current').strip()
assert branch=='dev/f3-resource-plan-approval-read-20261017'
subprocess.run(['git','merge-base','--is-ancestor',f['source_sha'],head],cwd=root,check=True)
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==h for p,h in f['files'].items())
docs=git('diff','--name-only',f['source_sha'],head).splitlines()
assert docs and all(p=='README.md' or p.startswith('docs/') for p in docs)
status=git('status','--porcelain');assert not status
remote=git('ls-remote','--heads','origin');(r/'remote-after.txt').write_text(remote)
before={ref:sha for sha,ref in (line.split() for line in (r/'remote-before.txt').read_text().splitlines())}
after={ref:sha for sha,ref in (line.split() for line in remote.splitlines())}
ref='refs/heads/'+branch;actual=after[ref];assert actual==head
changes=[ref for ref,sha in before.items() if after.get(ref)!=sha]
assert not changes and set(after)-set(before)=={ref}
counts=git('rev-list','--left-right','--count',head+'...'+actual).strip();assert counts.split()==['0','0']
info=dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_sha=f['base_sha'],source_sha=f['source_sha'],delivery_sha=head,
          branch=branch,actual_remote_sha=actual,HEAD_to_actual_remote_left_right=[0,0],worktree_porcelain=status,
          old_remote_heads_checked=len(before),old_remote_heads_changed=changes,remote_heads_before=len(before),remote_heads_after=len(after),
          added_remote_heads=sorted(set(after)-set(before)),actual_main_sha=after['refs/heads/main'],source_to_delivery_files=docs,
          source_to_delivery_only_documentation_and_evidence=True,source_inputs=720,source_drift=0,
          final_unique=gate['final']['unique'],final_failures=gate['final']['failure'],final_errors=gate['final']['errors'],final_skips=gate['final']['skipped'],
          Actions_queries=0,forced_push=False,main_written=False,deployed=False,real_model_called=False,
          actual_production_approval_source_provided=False,original_namespace_scope='SYNTHETIC_LOCAL_PREPARATION_ONLY',
          independent_review='pending parent review',complete_project=False)
(r/'delivery-verification.json').write_text(json.dumps(info,indent=2,ensure_ascii=False)+'\n')
print(json.dumps({k:info[k] for k in ('delivery_sha','source_sha','actual_remote_sha','HEAD_to_actual_remote_left_right','worktree_porcelain','old_remote_heads_checked','old_remote_heads_changed','remote_heads_after','actual_main_sha')},ensure_ascii=False))
