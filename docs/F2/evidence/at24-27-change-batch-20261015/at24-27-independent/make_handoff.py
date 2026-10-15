"""Summarize one completed evidence window without executing business actions."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
NAME = sys.argv[1]


def read(suffix):
    return json.loads((BASE / (NAME + suffix)).read_text())


validation = read('-validation.json')
result = read('.json')
coverage = read('-fixed-case-coverage.json')
flows = read('-html-summary.json')['flows']
own = read('-own-traces.json')['records']
groups = {str(number): [] for number in range(24, 28)}
for record in own:
    path = ROOT / record['path']
    if not path.name.startswith('at-results-'):
        continue
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256']
    for line_number, line in enumerate(path.read_text().splitlines(), 1):
        row = json.loads(line)
        assert row['result'] == 'PASS' and row['source_sha'] == result['source_sha']
        item = {key: row[key] for key in ('scenario', 'case', 'mode', 'result', 'test') if key in row}
        item.update(trace=record['path'], trace_line=line_number, trace_sha256=record['sha256'],
                    http_status_fields={key: value for key, value in row.items() if key.endswith('status') and isinstance(value, int)},
                    assertion_flags={key: value for key, value in row.items() if isinstance(value, bool)},
                    classifications={key: value for key, value in row.items() if key.endswith('classification')})
        for number in set(re.findall(r'\b(?:AT-)?(24|25|26|27)\b', row['at'])):
            groups[number].append(item)
assert all(groups.values())
per_at = dict(source_sha=result['source_sha'], status='EXECUTED_LINUX_SYNTHETIC_SCOPE_NOT_GLOBAL_AT_SIGNOFF',
              per_at_records=groups, design_case_coverage=coverage['mappings'])
(BASE / (NAME + '-per-at.json')).write_text(json.dumps(per_at, indent=2, sort_keys=True) + '\n')
handoff = dict(source_sha=result['source_sha'], status='FROZEN_FULL_WINDOW_PASS_WITH_EXPLICIT_SCOPE_LIMITS',
    counts=result['counts'], modules=dict(Counter(node.split('::')[0] for node in result['collected_nodes'])),
    elapsed_seconds=result['elapsed_seconds'], started_utc=result['started_utc'], finished_utc=result['finished_utc'],
    validation=NAME+'-validation.json', per_at=NAME+'-per-at.json', collection=NAME+'-collection.json',
    junit=NAME+'.xml', log=NAME+'.log', result=NAME+'.json',
    source_manifests=[NAME+'-before.json', NAME+'-after.json'],
    all_tracked_manifests=[NAME+'-all-tracked-before.json', NAME+'-all-tracked-after.json'],
    new_oracle=validation['independent_oracle_statistics']['test_at24_27_change_batch_independent'],
    html_scope_counts=dict(Counter(row['scope'] for row in flows)),
    html_and_http=NAME+'-html-summary.json', own_trace_manifest=NAME+'-own-traces.json',
    previous_test_trace_manifest=NAME+'-related-traces.json', python_http=NAME+'-http-traffic.json',
    historical_windows_not_combined={
      'startup_failure_no_tests': 'independent-v1-launch.log',
      'interrupted_208_of_235_not_complete_pass': 'independent-v2-interrupted-validation.json',
    }, tool_transient_without_pytest_restart=NAME+'-tool-transient.json',
    explicit_limits=[
      'Each isolated scenario reconstructs the fixed six-goal A/B profile; distinct scenario fixtures are not one shared mutable history.',
      'Original full HTML executes in Node VM/DOM doubles over actual HTTP/ASGI/owned PostgreSQL; real browser and Windows were not run.',
      'New HTML has 9 real-backend-response modes and 3 controlled client exception/DTO negatives; the two actual note GET 403 snapshots are separate.',
      'MIGRATE choice 422 proves the closed request type rejects that choice, not execution of migration.',
      'Breaking full apply 409 uses complete current proof after actual KEEP_CURRENT; superseded-ref 403 rejects an old target, not a business rollback.',
      'Actual catalog contract change rejects local ADOPT; this does not claim a new ServiceRelease was adopted by the old Case.',
      'Actual row-bound UNKNOWN proof is original plan read plus note projection and ADOPT refusal; successful typed/shared traversal is not claimed there.',
      'No-business-write comparisons exclude authorization_audit; permitted original read-time invalidation is reported separately.',
      'Selected-capacity rebind preserves original first-delivery approval; replacement formal approval remains NOT_IMPLEMENTED.',
      'Real models, production and formal global AT acceptance were not executed.',
    ], private_registry='EXCLUDED_FROM_EXPORT_0600', helper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(BASE / (NAME + '-handoff.json')).write_text(json.dumps(handoff, indent=2, sort_keys=True) + '\n')
print(json.dumps(dict(source_sha=result['source_sha'], counts=result['counts'], per_at_records={key:len(value) for key,value in groups.items()}, handoff=NAME+'-handoff.json')))
