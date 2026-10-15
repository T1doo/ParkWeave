from pathlib import Path
import subprocess,json,hashlib
r=Path.cwd();o=r/'.runtime/note-template-carry-root';f=json.loads((o/'freeze-v3.json').read_text())
def git(*a):return subprocess.check_output(['git',*a])
head=git('rev-parse','HEAD').decode().strip();assert not git('status','--porcelain');assert not git('diff',f['source_sha'],head,'--','src','tests','scripts','pyproject.toml')
refs=json.loads((o/'remote-before.json').read_text())['refs'];branch=git('branch','--show-current').decode().strip();actual=dict((x.split()[1],x.split()[0]) for x in git('ls-remote','--heads','origin',*[p.removeprefix('refs/heads/') for p in refs],branch).decode().splitlines());assert all(actual[k]==v for k,v in refs.items());assert actual['refs/heads/'+branch]==head
assert git('rev-list','--left-right','--count','HEAD...@{upstream}').decode().strip()=='0\t0'
history=[]
for p in ['docs/Plan.md','docs/F2/Plan.md','docs/F2/Log.md','docs/DeliveryCriticalPath-20261010.md']:
 old=git('show',f['source_sha']+':'+p);new=(r/p).read_bytes();assert new.endswith(old),p;history.append(dict(path=p,original_sha256=hashlib.sha256(old).hexdigest(),old_bytes=len(old),original_exact_suffix=True))
allowed_history={'docs/Plan.md','docs/F2/Plan.md','docs/F2/Log.md','docs/DeliveryCriticalPath-20261010.md'}
old_other_drift=[p for p,h in f['all_tracked_sha256'].items() if p not in allowed_history and hashlib.sha256((r/p).read_bytes()).hexdigest()!=h]
assert not old_other_drift
index=json.loads((r/'docs/F2/evidence/note-template-carry-20261015/index.json').read_text());blob_drift=[]
for e in index['entries']:
 p=e['export_path'];b=(r/p).read_bytes();assert hashlib.sha256(b).hexdigest()==e['export_sha256'];assert git('show',head+':'+p)==b
prior=json.loads((o/'prior-raw-pre-final.json').read_text());assert all(hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['sha256'] for e in prior['entries'])
result=dict(status='PASS',delivery_sha=head,validated_source_sha=f['source_sha'],branch=branch,remote_refs=actual,prior_remote_refs_unchanged=True,source_tests_scripts_delta=[],worktree_clean=True,upstream_ahead=0,upstream_behind=0,archive_committed_blobs_exact=len(index['entries']),previous_originals_unchanged=len(prior['entries']),history=history,all_other_frozen_tracked_unchanged=len(f['all_tracked_sha256'])-len(allowed_history),report_sha256=hashlib.sha256((r/'docs/F2/NoteTemplateCarry-20261015.md').read_bytes()).hexdigest(),archive_index_sha256=hashlib.sha256((r/'docs/F2/evidence/note-template-carry-20261015/index.json').read_bytes()).hexdigest())
(r/'.runtime/note-template-carry-delivery/final-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
