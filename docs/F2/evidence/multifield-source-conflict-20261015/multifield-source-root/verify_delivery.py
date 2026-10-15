"""Read-only final checks after normal development branch push."""
from pathlib import Path
import subprocess, json, hashlib, datetime

root = Path.cwd()
out = root / '.runtime/multifield-source-root'
freeze = json.loads((out / 'freeze.json').read_text())
before = json.loads((out / 'remote-before.json').read_text())
regression = json.loads((out / 'final-regression-verification.json').read_text())
baseline = json.loads((out / 'baseline.json').read_text())
def git(*args):
    return subprocess.check_output(['git', *args], cwd=root)
def sha(data):
    return hashlib.sha256(data).hexdigest()

head = git('rev-parse', 'HEAD').decode().strip()
subprocess.run(['git', 'merge-base', '--is-ancestor', freeze['source_sha'], head], check=True)
branch = git('branch', '--show-current').decode().strip()
assert branch == freeze['branch'] and branch.startswith('dev/')
assert not git('status', '--porcelain')
delivery_delta = git('diff', '--name-only', freeze['source_sha'], head).decode().splitlines()
assert all(p.startswith('docs/') for p in delivery_delta), 'delivery must only add documentation/evidence after source freeze'
assert not git('diff', '--name-only', freeze['source_sha'], head, '--', 'src', 'tests', 'scripts', 'pyproject.toml')
assert regression['status'] == 'PASS' and regression['source_sha'] == freeze['source_sha']
assert not [p for p, h in freeze['source_paths'].items() if sha((root / p).read_bytes()) != h]
history = json.loads((root / '.runtime/multifield-source-delivery/history-prefix-receipt.json').read_text())
history_names = {entry['path'] for entry in history}
for p, h in freeze['all_tracked_sha256'].items():
    if p in history_names:
        old = git('show', freeze['source_sha'] + ':' + p)
        assert sha(old) == h and (root / p).read_bytes().endswith(old)
    else:
        assert sha((root / p).read_bytes()) == h, p
prior = {}
for key in ['prior_raw_sha256', 'prior_audit_raw_sha256']:
    drift = [p for p, h in baseline[key].items() if not Path(p).is_file() or sha(Path(p).read_bytes()) != h]
    assert not drift
    prior[key] = {'count': len(baseline[key]), 'drift': drift}
remote = dict((line.split()[1], line.split()[0]) for line in git('ls-remote', '--heads', 'origin').decode().splitlines())
assert all(remote.get(ref) == h for ref, h in before['selected_refs'].items())
remote_existing_drift = {ref: {'before': h, 'after': remote.get(ref)} for ref, h in before['refs'].items() if remote.get(ref) != h}
assert not remote_existing_drift, 'pre-existing remote references changed'
assert remote['refs/heads/' + branch] == head
for ref, h in before['selected_refs'].items():
    subprocess.run(['git', 'merge-base', '--is-ancestor', h, head], check=True)
divergence = git('rev-list', '--left-right', '--count', 'HEAD...origin/' + branch).decode().strip()
assert divergence.split() == ['0', '0']
paths = git('ls-files', '-z', '--', 'docs/F2/evidence/multifield-source-conflict-20261015', 'docs/F2/evidence/multifield-source-conflict-audit-20261015').decode().split('\0')
paths = [p for p in paths if p]
assert paths
for p in paths:
    assert git('show', head + ':' + p) == (root / p).read_bytes(), p
gate = json.loads((root / 'docs/F2/evidence/multifield-source-conflict-audit-20261015/final-gate.json').read_text())
record = dict(status='PASS', utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), source_sha=freeze['source_sha'], delivery_sha=head,
              branch=branch, remote_branch_sha=remote['refs/heads/' + branch], ahead=0, behind=0, worktree_clean=True,
              frozen_source_paths=len(freeze['source_paths']), frozen_source_drift=[], frozen_original_paths=len(freeze['all_tracked_sha256']),
              history_exact_suffix=history, previous_originals=prior, preserved_remote_refs=before['selected_refs'],
              all_existing_remote_refs_checked=len(before['refs']), existing_remote_ref_drift=remote_existing_drift,
              new_remote_refs={ref: h for ref, h in remote.items() if ref not in before['refs']},
              source_is_ancestor=True, preserved_refs_are_ancestors=True, archive_gitblob_exact_paths=len(paths),
              regression=dict(complete_modules=regression['complete_modules'], unique_testcases=regression['unique_testcases'], counts=regression['counts']),
              independent_gate_status=gate.get('status'), external_not_run=regression['external_not_run'], main_read_only=True,
              normal_push_only=True, product_model_calls=0, delivery_delta_paths=delivery_delta, post_freeze_product_delta=[])
assert gate.get('status') == 'PASS', 'independent gate must pass'
receipt_dir = root / '.runtime/multifield-source-delivery'
receipt_dir.mkdir(exist_ok=True)
(receipt_dir / 'final-verification.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: record[k] for k in ['status', 'source_sha', 'delivery_sha', 'branch', 'ahead', 'behind', 'worktree_clean', 'archive_gitblob_exact_paths']}))
