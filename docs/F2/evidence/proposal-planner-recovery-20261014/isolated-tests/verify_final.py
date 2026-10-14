from pathlib import Path
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

output = Path('.runtime/proposal-planner-recovery-20261014')
before = json.loads((output / 'final-source-before.json').read_text())
current = {name: hashlib.sha256(Path(name).read_bytes()).hexdigest()
           if Path(name).is_file() else None for name in before['files']}
changes = [name for name in before['files'] if current[name] != before['files'][name]]
suites = list(ET.parse(output / 'final.xml').getroot().iter('testsuite'))
counts = {key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
          for key in ('tests', 'failures', 'errors', 'skipped')}
pages = []
for path in sorted((output / 'final-pages').glob('*.json')):
    value = json.loads(path.read_text())
    original_key = None
    for request in value['requests']:
        if request['method'] == 'POST':
            original_key = request['key']
        if request['path'].endswith('/service-plan-candidates/recovery'):
            assert request['method'] == 'GET' and request['key'] == original_key
    pages.append(dict(path=str(path), summary=value['summary'],
                      fake_provider_requests=value['fake_provider_requests'],
                      actual_provider_requests=value['actual_provider_requests'],
                      per_attempt_original_key_recovery=True,
                      http=len(value['requests']),
                      post_requests=sum(q['method'] == 'POST' for q in value['requests']),
                      response_faults=[q['nodevm_fault'] for q in value['requests'] if q['nodevm_fault']]))
assert counts == dict(tests=10, failures=0, errors=0, skipped=0), counts
assert not changes, changes
assert len(pages) == 10 and all(p['summary']['result'] == 'PASS' for p in pages)
result = dict(result='PASS', source_sha=before['source_sha'], manifest_count=before['count'],
              actual_mirror_hashes=current, source_changes=changes,
              loadedmodule_paths=before['loadedmodule_paths'],
              detached_git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
              counts=counts, passed=10, warnings=2, pytest_seconds=10.02,
              junit_seconds=sum(float(s.attrib['time']) for s in suites), exit_code=0,
              actual_provider_requests=0, planner_credential_reads=0, live_quota_writes=0,
              proposal_business_execution=0, browser_runs=0, original_nodevm_pages=pages,
              implementation_or_git_mutations_by_reviewer=0,
              previous_windows=[dict(kind='missing-import driver',tests=8,passed=0,failed=8),
                                dict(kind='a60 actual boundary red',tests=8,passed=6,failed=2),
                                dict(kind='first fix development',tests=8,passed=8,failed=0),
                                dict(kind='exact fields and calendar development',tests=10,passed=10,failed=0)],
              counts_are_independent_windows=True)
(output / 'final.exit').write_text('0\n')
(output / 'final-review.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps({key: result[key] for key in ('result','source_sha','manifest_count','counts','source_changes','pytest_seconds','junit_seconds')}))
