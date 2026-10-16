"""One predeclared complete evidence-output retry, then original first solos."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, subprocess, sys, time

r = Path('.runtime/plan-reapproval-root/v2')
b = Path('.runtime/plan-reapproval-final/v2')
load = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
now = lambda: datetime.now(timezone.utc).isoformat()
context_path = r / 'related-08-evidence-retry-context.json'
context = load(context_path)
freeze = load(r / 'freeze.json')
assert context['status'] == 'PREPARED_NOT_EXECUTED'
assert context['source_sha'] == freeze['source_sha']
selection = load(b / 'selection.json')
expected = set(selection['main_windows']) - {'recovery-solo'}
while True:
    try:
        progress = load(b / 'scheduler-progress.json')
    except (FileNotFoundError, json.JSONDecodeError):
        time.sleep(2)
        continue
    if not progress['active'] and not progress['pending']:
        assert set(progress['finished']) == expected
        break
    time.sleep(2)

manifest_path = Path(context['original_directory_manifest'])
assert sha(manifest_path) == context['original_directory_manifest_sha256']
originals = load(manifest_path)['entries']
def preserved():
    for entry in originals:
        assert sha(Path(entry['original_path'])) == entry['sha256']
        assert sha(Path(entry['copy_path'])) == entry['sha256']

preserved()
assert sha(b / 'related-08.json') == context['original_receipt_sha256']
assert sha(b / 'related-08.xml') == context['original_xml_sha256']
assert sha(b / 'related-08.log') == context['original_log_sha256']
assert all(sha(Path(p)) == h for p, h in freeze['runner_paths'].items())
assert load(b / 'related-08-modules.json') == context['modules']
override = context['environment_override']
assert set(override) == {'PARKWEAVE_T07_EVIDENCE_DIR'}
assert not Path(override['PARKWEAVE_T07_EVIDENCE_DIR']).exists()
retry = context['retry_window']
started = now()
before = r / 'evidence-retry-execution-before.json'
assert not before.exists()
before.write_text(json.dumps(dict(status='STARTING_PREDECLARED_COMPLETE_RETRY',
    utc=started, context_path=str(context_path), context_sha256=sha(context_path),
    controller_sha256=sha(Path(__file__)), source_sha=freeze['source_sha'],
    all_parallel_finished=progress, environment_override=override,
    original_ci_started=False, original_recovery_started=False), indent=2)+'\n')

def run(name, modules_path, env=None):
    log = b / (name+'-runner.log')
    assert not log.exists() and not (b / (name+'.json')).exists(), 'No overwrite/retry'
    with log.open('w') as stream:
        code = subprocess.run([sys.executable, str(b/'run_window.py'), name,
            str(modules_path)], env=env, stdout=stream, stderr=subprocess.STDOUT).returncode
    print(name, code, flush=True)
    return code

assert not (b/'ci-metadata-solo.json').exists() and not (b/'recovery-solo.json').exists()
results = {retry: run(retry, b/'related-08-modules.json', dict(os.environ, **override))}
preserved()
for name in ('ci-metadata-solo', 'recovery-solo'):
    results[name] = run(name, b/(name+'-modules.json'))
preserved()
after = r / 'evidence-retry-execution-after.json'
assert not after.exists()
after.write_text(json.dumps(dict(status='COMPLETE', started_utc=started,
    finished_utc=now(), source_sha=freeze['source_sha'], results=results,
    context_sha256=sha(context_path), controller_sha256=sha(Path(__file__)),
    original10_and_exact_copies_unchanged=True,
    policy='One predeclared full12module508item artifact-output retry; original CI12 then recovery30 once alone after all affected windows; original budgets/assertions/helpers unchanged'), indent=2)+'\n')
raise SystemExit(int(any(results.values())))
