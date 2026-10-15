from pathlib import Path
import subprocess,json,hashlib
r=Path.cwd();o=r/'.runtime/manual-continuation-root';f=json.loads((o/'freeze-v2.json').read_text())
def git(*a):return subprocess.check_output(['git',*a])
head=git('rev-parse','HEAD').decode().strip();assert not git('status','--porcelain');assert not git('diff',f['source_sha'],head,'--','src','tests','scripts','pyproject.toml')
refs=json.loads((o/'remote-pre-final.json').read_text())['refs'];branch=git('branch','--show-current').decode().strip();actual=dict((x.split()[1],x.split()[0]) for x in git('ls-remote','--heads','origin',*[p.removeprefix('refs/heads/') for p in refs],branch).decode().splitlines());assert all(actual[k]==v for k,v in refs.items());assert actual['refs/heads/'+branch]==head
assert git('rev-list','--left-right','--count','HEAD...@{upstream}').decode().strip()=='0\t0'
history=[]
for p in ['docs/Plan.md','docs/F2/Plan.md','docs/F2/Log.md','docs/DeliveryCriticalPath-20261010.md']:
 old=git('show',f['source_sha']+':'+p);new=(r/p).read_bytes();assert new.endswith(old),p;history.append(dict(path=p,original_sha256=hashlib.sha256(old).hexdigest(),old_bytes=len(old),original_exact_suffix=True))
index=json.loads((r/'docs/F2/evidence/manual-content-continuation-20261015/index.json').read_text());blob_drift=[]
for e in index['entries']:
 p=e['export_path'];b=(r/p).read_bytes();assert hashlib.sha256(b).hexdigest()==e['export_sha256'];assert git('show',head+':'+p)==b
prior=json.loads((o/'prior-raw-preservation.json').read_text());assert all(hashlib.sha256((r/e['path']).read_bytes()).hexdigest()==e['sha256'] for e in prior['entries'])
result=dict(status='PASS',delivery_sha=head,validated_source_sha=f['source_sha'],branch=branch,remote_refs=actual,prior_remote_refs_unchanged=True,source_tests_scripts_delta=[],worktree_clean=True,upstream_ahead=0,upstream_behind=0,archive_committed_blobs_exact=len(index['entries']),previous_originals_unchanged=len(prior['entries']),history=history)
(o/'delivery-final-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
