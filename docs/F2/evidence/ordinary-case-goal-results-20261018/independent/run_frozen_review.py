"""Explicit source-SHA private Git archive, exact inputs and result evidence."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import time
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('--sha', required=True)
parser.add_argument('--window', required=True)
parser.add_argument('nodes', nargs='*')
args = parser.parse_args()
assert re.fullmatch('[0-9a-f]{40}', args.sha)
assert re.fullmatch('[a-zA-Z0-9_-]+', args.window)
root = Path('/workspace/ParkWeave')
base = Path(__file__).resolve().parent
out = base / args.window
out.mkdir(exist_ok=False)
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
assert head == args.sha, 'explicit frozen SHA must still be actual shared HEAD'
selectors = args.nodes or [
 'tests/test_independent_ordinary_goal_results.py',
 'tests/test_ordinary_case_goal_results.py::test_ordinary_outputs_require_original_predecessors_and_explicit_owner_verification',
 'tests/test_ordinary_case_goal_results.py::test_actual_last_pg_lock_wait_crosses_first_deadline_without_false_current_or_commit[VERIFY]',
 'tests/test_ordinary_case_goal_record_pack_process.py::test_normal_process_original_html_verify_download_cold_read_and_revoked_source',
]
scopes = ['src', 'tests', 'scripts', 'pyproject.toml', 'docs/F1/ATBindings.json',
          'docs/验收规格.json', 'docs/F2/TypedDependencyKernelContract-20261018.md',
          'docs/F2/TypedDependencyOpportunityPreviewContract-20261018.md',
          'docs/F2/ResourceQueryMemberGraphContract-20261018.md',
          'docs/F2/ServiceCatalogQueryDependencyContract-20261018.md',
          'docs/F2/CaseStepAssignmentContract-20261018.md',
          'docs/F2/CaseStepNoticeContract-20261018.md',
          'docs/F2/OrdinaryCaseStepContract-20261018.md', 'docs/F2/OrdinaryCaseGoalResultsContract-20261018.md','README.md',
          'docs/F2/UnifiedSourcePropagationOracle-20261016.json']
paths = [x.decode() for x in subprocess.check_output(['git', 'ls-files', '-z', *scopes], cwd=root).split(b'\0') if x]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
write = lambda name, value: (out / name).write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')
pre = {p: sha(root / p) for p in paths}
write('shared-before.json', pre)
archive = subprocess.check_output(['git', 'archive', args.sha, *paths], cwd=root)
mirror = out / 'mirror'
mirror.mkdir()
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
    tf.extractall(mirror, filter='data')
mirror_before = {p: sha(mirror / p) for p in paths}
write('mirror-before.json', mirror_before)
assert pre == mirror_before, 'shared input differs from frozen source archive'
probe = base / 'test_independent_ordinary_goal_results.py'
shutil.copyfile(probe, mirror / 'tests' / probe.name)
own_sources = [probe, base / 'execute_review.py', Path(__file__).resolve(),
               base / 'literal-oracle-plan.json',
               base / 'contract-observed.md']
own_pre = {str(p.relative_to(base)): sha(p) for p in own_sources}
write('independent-source-before.json', own_pre)
owned_temp = Path(tempfile.mkdtemp(prefix='pw-independent-ordinary-goal-results-'))
command = [str(root / '.venv/bin/python'), str(base / 'execute_review.py'), str(out),
           '-q', '-c', str(mirror / 'pyproject.toml'), '--rootdir=' + str(mirror),
           '-p', 'no:cacheprovider', *selectors, '--basetemp=' + str(owned_temp / 'pytest-temp'),
           '--junitxml=' + str(out / 'results.xml')]
env = os.environ.copy()
env.update(PYTHONPATH=':'.join(str(mirror / p) for p in ('src', 'tests', '.')),
           PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1',
           PARKWEAVE_INDEPENDENT_GOAL_RESULTS_EVIDENCE=str(out / 'scenarios'),
           PARKWEAVE_ORDINARY_CASE_STEP_EVIDENCE=str(out / 'root-overlap-evidence'),
           PARKWEAVE_REVIEW_TMP_ROOT=str(owned_temp))
write('command.json', dict(source_sha=args.sha, actual_HEAD=head, argv=command,
                           cwd=str(mirror), selected_nodes=selectors,
                           environment_keys_overridden=sorted(k for k in env if k in (
                               'PYTHONPATH', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD',
                               'PYTHONDONTWRITEBYTECODE', 'PARKWEAVE_INDEPENDENT_GOAL_RESULTS_EVIDENCE',
                               'PARKWEAVE_ORDINARY_CASE_STEP_EVIDENCE','PARKWEAVE_REVIEW_TMP_ROOT'))))
started = datetime.now(timezone.utc).isoformat()
clock = time.perf_counter()
code = None
try:
    with (out / 'stdout.txt').open('w') as stdout, (out / 'stderr.txt').open('w') as stderr:
        try:
            code = subprocess.run(command, cwd=mirror, env=env, stdout=stdout, stderr=stderr, timeout=600).returncode
        except subprocess.TimeoutExpired:
            code = 124
finally:
    shared_post = {p: sha(root / p) for p in paths}
    mirror_post = {p: sha(mirror / p) for p in paths}
    own_post = {str(p.relative_to(base)): sha(p) for p in own_sources}
    write('shared-after.json', shared_post)
    write('mirror-after.json', mirror_post)
    write('independent-source-after.json', own_post)
    result = dict(source_sha=args.sha, actual_HEAD_at_start=head,
                  actual_HEAD_at_end=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                  exit_code=code, selected_nodes=selectors, started_utc=started,
                  finished_utc=datetime.now(timezone.utc).isoformat(), outer_seconds=time.perf_counter() - clock,
                  frozen_input_count=len(pre), archive_sha256=hashlib.sha256(archive).hexdigest(),
                  shared_drift=[p for p in pre if pre[p] != shared_post[p]],
                  mirror_drift=[p for p in pre if mirror_before[p] != mirror_post[p]],
                  shared_mirror_mismatch=[p for p in pre if shared_post[p] != mirror_post[p]],
                  independent_source_drift=[p for p in own_pre if own_pre[p] != own_post[p]],
                  browser=False, real_model=False, tracked_or_git_mutations=False)
    write('controller-result.json', result)
    pg_path = out / 'owned-pg-before-exit.json'
    if pg_path.exists():
        pg = json.loads(pg_path.read_text())
        for row in pg:
            stat = Path('/proc') / str(row['pid']) / 'stat'
            row['state_after_process_exit'] = stat.read_text().rsplit(')', 1)[1].strip().split()[0] if stat.exists() else 'EXITED'
            row['data_exists_after_process_exit'] = Path(row['data']).exists()
        write('owned-pg-after-exit.json', pg)
print(json.dumps(result, sort_keys=True))
raise SystemExit(code if code is not None else 125)
