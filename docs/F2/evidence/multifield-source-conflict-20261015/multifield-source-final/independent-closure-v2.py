"""Read frozen completed windows; issue receipt only after every check passes."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/ParkWeave')
BASE = ROOT / '.runtime/multifield-source-final'
NAME, MODULES_PATH, EXPECTED = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
freeze_path = ROOT / '.runtime/multifield-source-root/freeze.json'
freeze = json.loads(freeze_path.read_text())
result_path = BASE / (NAME + '.json')
result = json.loads(result_path.read_text())
modules = json.loads((ROOT / MODULES_PATH).read_text())
collection_path = BASE / (NAME + '-collection.json')
collection = json.loads(collection_path.read_text())
xml_path = BASE / (NAME + '.xml')
cases = list(ET.parse(xml_path).iter('testcase'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(suffix):
    return json.loads((BASE / (NAME + suffix)).read_text())

def node_id(case):
    parts = case.get('classname', '').split('.')
    position = next((i for i, value in enumerate(parts) if value.startswith('test_')), None)
    assert position is not None and case.get('name'), 'unnamed or unmatched JUnit record'
    return 'tests/' + parts[position] + '.py::' + '::'.join(parts[position + 1:] + [case.get('name')])

assert result['source_sha'] == freeze['source_sha'] == subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT), 'tracked worktree must remain clean'
assert result['exit_code'] == 0 and result['counts'] == dict(PASS=EXPECTED, FAIL=0, ERROR=0, SKIP=0)
assert result['modules'] == modules
assert len(collection) == EXPECTED and len(set(collection)) == EXPECTED
assert sorted(collection) == sorted(result['collected_nodes'])
assert len(cases) == EXPECTED
actual = [node_id(case) for case in cases]
assert len(set(actual)) == EXPECTED and sorted(actual) == sorted(collection)
assert all(case.find('error') is None and case.find('failure') is None and case.find('skipped') is None for case in cases)
assert result['collection_junit_exact_match'] and result['unique_junit_nodes']
assert result['source_drift'] == result['all_tracked_drift'] == result['runner_drift'] == []
for prefix, frozen_key, count_key in [('', 'source_paths', 'tracked_source_paths'), ('-all-tracked', 'all_tracked_sha256', 'all_tracked_paths')]:
    before, after = read(prefix + '-before.json'), read(prefix + '-after.json')
    assert before == after == freeze[frozen_key]
    assert len(before) == result[count_key]
    assert all(sha(ROOT / path) == expected for path, expected in after.items())
assert all(sha(ROOT / path) == expected for path, expected in freeze['runner_paths'].items())
provenance = read('-collection-plugin-provenance.json')
assert provenance == result['capture_plugin_provenance']
assert provenance['actual_path'] == provenance['expected_path'] == str(BASE / 'shared_capture.py')
assert provenance['sha256'] == sha(BASE / 'shared_capture.py') and provenance['product_logic_patched'] is False
module_counts = dict(Counter(node.split('::', 1)[0] for node in actual))
assert sorted(module_counts) == sorted(modules)
private_path = BASE / ('redaction-' + NAME + '.private.json')
private_info = dict(exists=private_path.exists(), exported=False)
if private_path.exists():
    assert private_path.stat().st_mode & 0o777 == 0o600
    private_info['mode'] = '0600'
    private_info['value_count'] = len(json.loads(private_path.read_text()))

receipt = dict(
    status='PASS', source_sha=freeze['source_sha'], name=NAME,
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    started_utc=result['started_utc'], finished_utc=result['finished_utc'], elapsed_seconds=result['elapsed_seconds'],
    complete_modules=module_counts, collected_nodes=EXPECTED, named_junit_pass=EXPECTED,
    collection_junit_exact=True, source_paths=result['tracked_source_paths'], all_tracked_paths=result['all_tracked_paths'],
    source_alltracked_helpers_drift=0, private_registry=private_info,
    outputs={str(path.relative_to(ROOT)): sha(path) for path in [result_path, collection_path, xml_path, BASE / (NAME + '.log'),
        BASE / (NAME + '-before.json'), BASE / (NAME + '-after.json'),
        BASE / (NAME + '-all-tracked-before.json'), BASE / (NAME + '-all-tracked-after.json'),
        BASE / (NAME + '-collection-plugin-provenance.json'), BASE / (NAME + '-collection-artifact-paths.json')]},
    validator_sha256=sha(Path(__file__).resolve()), freeze_sha256=sha(freeze_path),
    real_browser='NOT_RUN', windows='NOT_RUN', real_model='NOT_RUN', production='NOT_RUN',
)
target = BASE / (NAME + '-independent-closure.json')
with target.open('x') as stream:
    stream.write(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({k: receipt[k] for k in ['status', 'source_sha', 'name', 'complete_modules', 'named_junit_pass', 'source_paths', 'all_tracked_paths', 'source_alltracked_helpers_drift']}))
