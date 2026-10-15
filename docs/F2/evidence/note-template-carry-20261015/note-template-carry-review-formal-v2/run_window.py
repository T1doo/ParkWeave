"""New frozen independent window. No run is allowed before explicit SHA config."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/ParkWeave')
OUT = Path(__file__).resolve().parent
settings = json.loads((OUT / 'execution-config.json').read_text())
SHA = settings['source_sha']
assert SHA and settings['status'] == 'READY_FROZEN_SHA', 'Await parent explicit new frozen SHA; no shared source run started.'
kind = sys.argv[1]
module_files = {'extra':'review-modules.json','history':'history-modules.json','budget':'budget-modules.json'}
expected_modules = {'extra':16,'history':1,'budget':1}
assert kind in module_files
PREFIX = 'freeze-' + SHA[:7] + '-' + kind + '-v1'
assert not (OUT / (PREFIX + '.log')).exists(), 'Never overwrite an earlier run.'
modules = json.loads((OUT / module_files[kind]).read_text())
assert len(modules) == len(set(modules)) == expected_modules[kind]


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


assert git('rev-parse', 'HEAD').decode().strip() == SHA
assert not git('status', '--porcelain', '--untracked-files=no')
paths = [p for p in git('ls-files', '-z').decode().split('\0') if p]
source_paths = [p for p in paths if p == 'pyproject.toml' or p.startswith(('src/', 'tests/', 'scripts/'))]
assert len(paths) >= 13252 and len(source_paths) >= 608
freeze = json.loads((ROOT / settings['freeze_path']).read_text())
assert freeze['source_sha'] == SHA
assert len(paths)==len(freeze['all_tracked_sha256']) and len(source_paths)==len(freeze['source_paths'])


def manifest():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


before = manifest()
assert before == freeze['all_tracked_sha256']
assert {p: before[p] for p in source_paths} == freeze['source_paths']
(OUT / (PREFIX + '-before.json')).write_text(json.dumps(dict(source_sha=SHA, hashes=before,
    source_paths=source_paths), indent=2) + '\n')
legacy_dest = OUT / 'legacy-artifacts' / PREFIX
# Explicit preparation avoids recording into a missing artifact destination.
legacy_dest.mkdir(parents=True, exist_ok=False)
args = [sys.executable, '-m', 'pytest', '-q', '-p', 'shared_capture', '-p', 'legacy_artifact_capture',
        '-o', 'cache_dir=' + str(OUT / 'pytest-cache' / PREFIX), *modules,
        '--basetemp=/tmp/parkweave-note-carry-review-' + PREFIX,
        '--junitxml=' + str(OUT / (PREFIX + '.xml'))]
env = {**os.environ,
    'PYTHONPATH': os.pathsep.join([str(OUT), str(ROOT), str(OUT / 'probes'), str(ROOT / 'tests'),
                                  os.environ.get('PYTHONPATH', '')]),
    'PYTHONDONTWRITEBYTECODE': '1',
    'XDG_CACHE_HOME': str(ROOT / '.runtime/xdg-cache'),
    'TYPED_COLLECTION': str(OUT / (PREFIX + '-collection.json')),
    'TYPED_PRIVATE': str(OUT / ('redaction-' + PREFIX + '.private.json')),
    'AT_BATCH_ARTIFACT_ROOT': str(OUT / 'related-test-artifacts'),
    'AT_BATCH_WINDOW': PREFIX, 'REVIEW_SEAM_WINDOW': PREFIX, 'NOTE_CARRY_REVIEW_WINDOW': PREFIX,
    'LEGACY_ARTIFACT_DESTINATION': str(legacy_dest)}
started = datetime.now(timezone.utc).isoformat()
begin = time.monotonic()
with (OUT / (PREFIX + '.log')).open('x') as stream:
    code = subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, env=env).returncode
elapsed = time.monotonic() - begin
after = manifest()
after_head = git('rev-parse', 'HEAD').decode().strip()
(OUT / (PREFIX + '-after.json')).write_text(json.dumps(dict(source_sha=after_head, hashes=after,
    source_paths=source_paths), indent=2) + '\n')
tree = ET.parse(OUT / (PREFIX + '.xml'))
cases = list(tree.iter('testcase'))
all_junit_elements=cases
junit_artifact_markers=[dict(classname=c.get('classname'),name=c.get('name'),error=c.find('error') is not None) for c in cases if not c.get('classname') or not c.get('name')]
cases=[c for c in cases if c.get('classname') and c.get('name')]
counts = dict(PASS=0, FAIL=0, ERROR=0, SKIP=0)
for case in cases:
    counts['ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None
           else 'SKIP' if case.find('skipped') is not None else 'PASS'] += 1


def node_id(case):
    parts = case.get('classname', '').split('.')
    position = next((i for i, part in enumerate(parts) if part.startswith('test_')), None)
    assert position is not None
    module = next(m for m in modules if Path(m).stem == parts[position])
    return module + '::' + '::'.join(parts[position + 1:] + [case.get('name')])


collected = json.loads((OUT / (PREFIX + '-collection.json')).read_text())
actual = [node_id(case) for case in cases]
drift = [p for p in paths if before[p] != after[p]]
status = git('status', '--porcelain', '--untracked-files=no').decode()
record = dict(source_sha=SHA, after_source_sha=after_head, started_utc=started,
    finished_utc=datetime.now(timezone.utc).isoformat(), modules=modules, argv=args,
    exit_code=code, elapsed_seconds=elapsed,
    junit_seconds=sum(float(suite.get('time', 0)) for suite in tree.iter('testsuite')),
    counts=counts, junit_artifact_markers=junit_artifact_markers, raw_junit_elements=len(all_junit_elements), tracked_source_paths=len(source_paths), all_tracked_paths=len(paths),
    source_drift=[p for p in source_paths if before[p] != after[p]], all_tracked_drift=drift,
    collected_nodes=collected, junit_nodes=actual,
    testcase_keys=[dict(classname=case.get('classname'), name=case.get('name')) for case in cases],
    collection_junit_exact_match=sorted(collected) == sorted(actual),
    unique_junit_nodes=len(actual) == len(set(actual)),
    expected_module_set_equal={node.split('::', 1)[0] for node in collected} == set(modules),
    tracked_status_after=status, environment='LINUX_SYNTHETIC_OWNED_POSTGRESQL',
    previous_scores_reused=False,
    legacy_destination_precreated=True, legacy_plugin_sha256=hashlib.sha256((OUT / 'legacy_artifact_capture.py').read_bytes()).hexdigest())
(OUT / (PREFIX + '.json')).write_text(json.dumps(record, indent=2) + '\n')
gate = (code == 0 and not junit_artifact_markers and not drift and not status and after_head == SHA and
        record['collection_junit_exact_match'] and record['unique_junit_nodes'] and
        record['expected_module_set_equal'])
print(json.dumps({key: value for key, value in record.items()
                 if key not in {'modules', 'argv', 'collected_nodes', 'junit_nodes', 'testcase_keys'}}))
raise SystemExit(0 if gate else 1)
