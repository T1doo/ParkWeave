"""Actual remote check after normal push; do not query Actions/tracking refs."""
from pathlib import Path
import subprocess,json,hashlib,datetime
ROOT=Path('/workspace/ParkWeave');R=ROOT/'.runtime/formal-preparation-entry'
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True)
f=json.loads((R/'freeze.json').read_text());head=git('rev-parse','HEAD').strip();branch=git('branch','--show-current').strip()
assert branch=='dev/f3-formal-preparation-entry-20261017'
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in f['files'].items())
delta=git('diff','--name-only',f['source_sha'],head).splitlines();assert delta and all(p=='README.md' or p.startswith('docs/') for p in delta)
status=git('status','--porcelain');assert status==''
remote=git('ls-remote','--heads','origin');(R/'remote-after.txt').write_text(remote)
before={ref:sha for sha,ref in (line.split() for line in (R/'remote-before.txt').read_text().splitlines())};after={ref:sha for sha,ref in (line.split() for line in remote.splitlines())}
target='refs/heads/'+branch;assert after[target]==head
assert all(after.get(ref)==sha for ref,sha in before.items()) and set(after)-set(before)=={target}
assert git('rev-list','--left-right','--count',head+'...'+after[target]).split()==['0','0']
data=dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_sha=f['base_sha'],source_sha=f['source_sha'],delivery_sha=head,
    actual_remote_sha=after[target],branch=branch,HEAD_to_actual_remote_left_right=[0,0],worktree_porcelain=status,
    old_heads_checked=len(before),old_heads_changed=[],remote_heads_after=len(after),main_sha=after['refs/heads/main'],
    original_review_branch_sha=after['refs/heads/dev/f3-resource-plan-approval-read-20261017'],
    source_to_delivery_only_docs_evidence=True,source_to_delivery_files=delta,source_inputs=723,source_drift=0,
    final_unique=186,formal_business_record_success_implemented=False,real_source_access_attempted=False,
    source_specific_provenance_and_formal_approval_mapping_implemented=False,
    main_changed=False,forced_push=False,Actions_queries=0,deployed=False,real_model_called=False,
    new_credentials_security_permissions_costs=False,complete_project=False,independent_review='new slice pending parent review')
(R/'delivery-verification.json').write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({k:data[k] for k in ('source_sha','delivery_sha','actual_remote_sha','HEAD_to_actual_remote_left_right','worktree_porcelain','old_heads_checked','old_heads_changed','main_sha','original_review_branch_sha')}))
