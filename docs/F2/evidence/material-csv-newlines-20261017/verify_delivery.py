"""Verify a normal new development branch push against actual remote heads."""
from pathlib import Path
import subprocess,json,hashlib,datetime
ROOT=Path('/workspace/ParkWeave');R=ROOT/'.runtime/material-csv-newlines'
def git(*a):return subprocess.check_output(['git',*a],cwd=ROOT,text=True)
f=json.loads((R/'freeze.json').read_text());source=f['source_sha'];head=git('rev-parse','HEAD').strip();branch=git('branch','--show-current').strip();assert branch==f['branch']
assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in f['files'].items())
delta=git('diff','--name-only',source,head).splitlines();assert delta and all(p=='README.md' or p.startswith('docs/') for p in delta)
assert git('status','--porcelain')==''
remote=git('ls-remote','--heads','origin');(R/'remote-after.txt').write_text(remote)
def refs(text):return {ref:sha for sha,ref in (line.split() for line in text.splitlines())}
before=refs((R/'remote-before.txt').read_text());after=refs(remote);target='refs/heads/'+branch
assert after[target]==head and all(after.get(ref)==sha for ref,sha in before.items()) and set(after)-set(before)=={target}
assert git('rev-list','--left-right','--count',head+'...'+after[target]).split()==['0','0']
old=json.loads((R/'inherited-archive-blobs.json').read_text())
for p,blob in old.items():
 b=(ROOT/p).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==blob
report=dict(recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_sha=f['base_sha'],source_sha=source,delivery_sha=head,actual_remote_sha=after[target],branch=branch,HEAD_to_actual_remote_left_right=[0,0],worktree_porcelain='',source_to_delivery_only_docs_evidence=True,source_to_delivery_files=delta,source_inputs=len(f['files']),source_drift=0,inherited_archive_git_blobs_checked=len(old),inherited_archive_drift=0,old_heads_checked=len(before),old_heads_changed=[],remote_heads_after=len(after),main_sha=after['refs/heads/main'],frozen_resource_plan_approval_branch=after['refs/heads/dev/f3-resource-plan-approval-read-20261017'],frozen_formal_preparation_branch=after['refs/heads/dev/f3-formal-preparation-entry-20261017'],frozen_material_file_import_branch=after['refs/heads/dev/f2-material-file-import-20261017'],final_unique=207,independent_review='CSV P2 closed; hint false positive; pure probes only, not added to207',main_changed=False,forced_push=False,deployed=False,Actions_queries=0,real_model_called=False,new_credentials_security_permissions_costs=False,complete_project=False,not_run=['Windows native formalAT','real business/source authorization/approvals','real model','production deployment/full acceptance'])
(R/'delivery-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('source_sha','delivery_sha','actual_remote_sha','HEAD_to_actual_remote_left_right','worktree_porcelain','old_heads_checked','old_heads_changed','remote_heads_after','main_sha','frozen_resource_plan_approval_branch','frozen_formal_preparation_branch','inherited_archive_git_blobs_checked')}))
