from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/ParkWeave')
OUT = ROOT / '.runtime/at24-27-repair-review'
SHA = '77059b467f3c0bfe1a74023e58823b14c9ac9a38'
PREFIX = 'actual-one-line-wip-focused26-v1'
modules = json.loads((ROOT / '.runtime/at24-27-root/first-formal-failed-nodes.json').read_text())
assert len(modules) == len(set(modules)) == 26
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SHA
assert subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines()==['src/parkweave/web.html']
repair=json.loads((ROOT/'.runtime/at24-27-root/common-clear-dom-repair.json').read_text())
assert repair['base_source_sha']==SHA and hashlib.sha256((ROOT/'src/parkweave/web.html').read_bytes()).hexdigest()==repair['after_sha256']
assert repair['new'] in (ROOT/'src/parkweave/web.html').read_text() and repair['old'] not in (ROOT/'src/parkweave/web.html').read_text()
paths = [p for p in subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0') if p]
source_paths = [p for p in paths if p == 'pyproject.toml' or p.startswith(('src/', 'tests/', 'scripts/'))]
assert len(paths) == 12417 and len(source_paths) == 605
freeze = json.loads((ROOT / '.runtime/at24-27-root/final-freeze.json').read_text())


def manifest():
    return {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths}


legacy_roots = [ROOT/'.runtime'/name for name in ('partial-plan-20261013','template-full-chain-20261013','template-repeat-cold-20261013','template-partial-20261014','template-plan-continuity-20261013')]
def legacy_snapshot():
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in legacy_roots for p in folder.rglob('*') if p.is_file()}
legacy_before=legacy_snapshot()
(OUT/(PREFIX+'-legacy-artifacts-before.json')).write_text(json.dumps(legacy_before,indent=2)+'\n')
before = manifest()
assert [p for p in source_paths if before[p]!=freeze['source_paths'][p]]==['src/parkweave/web.html']
(OUT / (PREFIX + '-before.json')).write_text(json.dumps(dict(source_sha=SHA, hashes=before, source_paths=source_paths), indent=2) + '\n')
args = [sys.executable, '-m', 'pytest', '-q', '-p', 'focused26_capture', *modules,
    '--basetemp=/tmp/parkweave-at24-27-repair-focused26-actualweb-v1',
    '--junitxml=' + str(OUT / (PREFIX + '.xml'))]
env = {**os.environ, 'PYTHONPATH': str(OUT) + os.pathsep + str(ROOT) + os.pathsep + os.environ.get('PYTHONPATH', ''),
    'XDG_CACHE_HOME': str(ROOT / '.runtime/xdg-cache'),
    'AT_REVIEW_COLLECTION': str(OUT / (PREFIX + '-collection.json')),
    'AT_REVIEW_PRIVATE': str(OUT / ('redaction-' + PREFIX + '.private.json')),
    'AT_REVIEW_ARTIFACT_PATHS': str(OUT / (PREFIX + '-artifact-paths.json')),
    'AT_REVIEW_ARTIFACT_ROOT': str(OUT / ('related-test-artifacts/' + PREFIX))}
start = time.monotonic(); started = datetime.now(timezone.utc).isoformat()
with (OUT / (PREFIX + '.log')).open('w') as log:
    code = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env).returncode
elapsed = time.monotonic() - start
after = manifest()
legacy_after=legacy_snapshot()
(OUT/(PREFIX+'-legacy-artifacts-after.json')).write_text(json.dumps(legacy_after,indent=2)+'\n')
assert legacy_before==legacy_after,'old fixed runtime artifacts changed'
after_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
(OUT / (PREFIX + '-after.json')).write_text(json.dumps(dict(source_sha=after_head, hashes=after, source_paths=source_paths), indent=2) + '\n')
tree = ET.parse(OUT / (PREFIX + '.xml'))
cases = list(tree.iter('testcase')); counts = dict(PASS=0, FAIL=0, ERROR=0, SKIP=0)
for case in cases:
    counts['ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'] += 1


def node_id(case):
    parts = case.get('classname', '').split('.')
    position = next((i for i, part in enumerate(parts) if part.startswith('test_')), None)
    assert position is not None
    return 'tests/' + parts[position] + '.py::' + '::'.join(parts[position + 1:] + [case.get('name')])


collected = json.loads((OUT / (PREFIX + '-collection.json')).read_text())
actual = [node_id(case) for case in cases]
drift = [p for p in paths if before[p] != after[p]]
record = dict(source_sha=SHA, after_source_sha=after_head, started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
    modules=modules, argv=args, exit_code=code, elapsed_seconds=elapsed,
    junit_seconds=sum(float(suite.get('time', 0)) for suite in tree.iter('testsuite')), counts=counts,
    tracked_source_paths=len(source_paths), all_tracked_paths=len(paths), source_drift=[p for p in source_paths if before[p] != after[p]],
    all_tracked_drift=drift, collected_nodes=collected, junit_nodes=actual,
    testcase_keys=[dict(classname=case.get('classname'), name=case.get('name')) for case in cases],
    collection_junit_exact_match=sorted(collected) == sorted(actual), unique_junit_nodes=len(actual) == len(set(actual)),
    expected_module_set_equal={node.split('::', 1)[0] for node in collected} == {node.split('::', 1)[0] for node in modules},
    tracked_status_after=subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True),
    environment='LINUX_SYNTHETIC_OWNED_POSTGRESQL', wip_results_reused=False, actual_source_status='77059b4_PLUS_SINGLE_UNCOMMITTED_SHARED_HTML_LINE', actual_web_sha256=before['src/parkweave/web.html'], not_final72_module_acceptance=True, bridge_asgi_pg_items=7, synthetic_DOM_transport_items=19)
(OUT / (PREFIX + '.json')).write_text(json.dumps(record, indent=2) + '\n')
gate = code == 0 and not drift and after_head == SHA and record['collection_junit_exact_match'] and record['unique_junit_nodes'] and record['expected_module_set_equal'] and subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).splitlines()==['src/parkweave/web.html']
print(json.dumps({k: v for k, v in record.items() if k not in {'modules', 'argv', 'collected_nodes', 'junit_nodes', 'testcase_keys'}}, ensure_ascii=False))
raise SystemExit(0 if gate else 1)
