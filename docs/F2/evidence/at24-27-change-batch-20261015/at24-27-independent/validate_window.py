"""Read-only post-run evidence validation; never reruns a business action."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
NAME, SOURCE = sys.argv[1:3]


def read(suffix):
    return json.loads((OUT / (NAME + suffix)).read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(suffix, data):
    (OUT / (NAME + suffix)).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


result = read('.json')
assert result['source_sha'] == result['head_after'] == SOURCE
assert result['exit_code'] == 0 and result['counts'] == dict(PASS=235, FAIL=0, ERROR=0, SKIP=0)
assert result['collection_junit_exact_match'] and result['unique_junit_nodes']
assert not result['source_drift'] and not result['all_tracked_drift'] and not result['source_status_after']
assert result['runner_unchanged'] and result['plugin_unchanged']
assert read('-before.json') == read('-after.json')
assert read('-all-tracked-before.json') == read('-all-tracked-after.json')
collection = read('-collection.json')
assert len(collection) == len(set(collection)) == 235
xml = ET.parse(OUT / (NAME + '.xml'))
passed = {}
for case in xml.iter('testcase'):
    parts = case.attrib['classname'].split('.')
    index = next(i for i, value in enumerate(parts) if value.startswith('test_'))
    node = 'tests/' + parts[index] + '.py::' + '::'.join(parts[index + 1:] + [case.attrib['name']])
    assert case.find('failure') is None and case.find('error') is None and case.find('skipped') is None
    passed[node] = True
assert set(passed) == set(collection)
coverage = json.loads((OUT / 'coverage-design.json').read_text())
assert coverage['design_case_count'] == 20
review_oracle = ROOT / '.runtime/at24-27-review/fixed-oracles-v2.json'
assert digest(review_oracle) == 'e5da8d65d71c1e657a4a8aca18da38b5d6cf97536c469bce524dadd0c2e42a07'
review_ids = {row['id'] for row in json.loads(review_oracle.read_text())['cases']}
coverage_ids = [row['id'] for row in coverage['mappings']]
assert len(coverage_ids) == len(set(coverage_ids)) == 20 and set(coverage_ids) == review_ids
for row in coverage['mappings']:
    assert all(node in passed for node in row['test_nodes']), row['id']
    row['execution_status'] = 'PASS_IN_FROZEN_LINUX_SYNTHETIC_SCOPE'
coverage.update(source_sha=SOURCE, pytest_case_count=37, status='EXECUTED_DESIGN_SCENARIOS_NOT_GLOBAL_AT_SIGNOFF')
save('-fixed-case-coverage.json', coverage)

artifacts = read('-own-traces.json')['records'] + read('-related-traces.json')['records']
assert len({record['path'] for record in artifacts}) == len(artifacts)
flows = []; oracle_groups = defaultdict(list); baseline = []; at_results = []; observations = []
for record in artifacts:
    path = ROOT / record['path']
    assert record['source_sha'] == SOURCE and '.private.' not in path.name and digest(path) == record['sha256']
    if path.suffix != '.jsonl':
        continue
    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
    if path.name.startswith('oracle-'):
        group = path.parent.name if 'related-test-artifacts' in str(path) else 'test_at24_27_change_batch_independent'
        for row in rows:
            assert row.get('head', row.get('source_sha')) == SOURCE
        oracle_groups[group].extend(rows)
    if path.name.startswith('baseline-'):
        baseline.extend(rows)
    if path.name.startswith('at-results-'):
        at_results.extend(rows)
    if path.name.startswith('read-observations-'):
        observations.extend(rows)
    if path.name.endswith('.stdout.jsonl'):
        output = [row for row in rows if 'scope' in row]
        assert len(output) == 1
        item = output[0]
        flows.append(dict(scope=item['scope'], mode=item['mode'], checks=item['checks'],
            negative_transport_fixture=item.get('negative_transport_fixture', False),
            requests=len(item['calls']), posts=sum(call['method'] == 'POST' for call in item['calls']),
            trace=record['path'], sha256=record['sha256']))
assert len(flows) == 41
assert len({(row['scope'], row['mode']) for row in flows}) == 41
assert Counter(row['scope'] for row in flows) == {
    'FULL_ORIGINAL_HTML_TYPED_SOURCE_REAL_HTTP_ASGI_OWNED_PG': 6,
    'FULL_ORIGINAL_HTML_SHARED_SOURCE_REAL_HTTP_ASGI_OWNED_PG': 9,
    'FULL_ORIGINAL_HTML_SERVICE_RELEASE_PREFLIGHT_REAL_HTTP_ASGI_OWNED_PG': 14,
    'FULL_ORIGINAL_HTML_AT24_27_FIXED_TWO_CASE_REAL_HTTP_ASGI_OWNED_PG': 12,
}
current = [row for row in flows if row['scope'] == 'FULL_ORIGINAL_HTML_AT24_27_FIXED_TWO_CASE_REAL_HTTP_ASGI_OWNED_PG']
assert len(current) == 12
assert {row['mode'] for row in current} == {'accept', 'lost_note', 'capacity', 'capacity_lost_adopt',
    'lost_note_unknown', 'lost_note_bad_unknown', 'current_403', 'late_aba', 'late_403',
    'late_json_reject', 'late_transport_reject', 'at27'}
assert {row['mode'] for row in current if row['negative_transport_fixture']} == {'late_json_reject', 'late_transport_reject', 'lost_note_bad_unknown'}
assert len(baseline) == 37 and all(row['source_sha'] == SOURCE for row in baseline)
assert all(len(value['required_goals']) == 6 and set(value['states'].values()) == {'VERIFIED'}
           for row in baseline for value in row['cases'].values())

statistics = {}
def declared_unknown(row):
    return bool(row.get('intentional_unknown', row.get('intentional_unknown_expansion', False)))


def observed_unknown(row):
    return bool(row.get('unknown_scope')) or row.get('actual_state') in {'UNKNOWN', 'NO_PLAN', 'NO_PREPARATION'} or row.get('actual_classification') == 'UNKNOWN'


for group, rows in oracle_groups.items():
    partitions = {}
    for label, selected in [('known', [r for r in rows if not declared_unknown(r) and not observed_unknown(r)]),
                            ('conservative_unknown', [r for r in rows if declared_unknown(r)]),
                            ('other_observed_unknown', [r for r in rows if not declared_unknown(r) and observed_unknown(r)])]:
        values = dict(records=len(selected), expected_affected_pairs=0, actual_affected_pairs=0, missed_count=0, wrong_count=0,
                      wrong_preserved_count=0, lock_records=0, expected_locked_pairs=0, actual_locked_pairs=0, wrong_locked_count=0)
        for row in selected:
            want = set(row['expected_affected']); got = set(row['actual_affected'])
            preserve = set(row['expected_preserved']); actual_preserve = set(row['actual_preserved'])
            values['expected_affected_pairs'] += len(want); values['actual_affected_pairs'] += len(got)
            values['missed_count'] += len(want - got); values['wrong_count'] += len(got - want)
            values['wrong_preserved_count'] += len(preserve ^ actual_preserve)
            if 'expected_locked' in row:
                expected_locked = set(row['expected_locked']); actual_locked = set(row['actual_locked'])
                values['lock_records'] += 1; values['expected_locked_pairs'] += len(expected_locked); values['actual_locked_pairs'] += len(actual_locked)
                values['wrong_locked_count'] += len(expected_locked ^ actual_locked)
        assert not any(values[key] for key in ('missed_count', 'wrong_count', 'wrong_preserved_count', 'wrong_locked_count'))
        partitions[label] = values
    assert sum(value['records'] for value in partitions.values()) == len(rows)
    statistics[group] = partitions
assert len(statistics) == 4
denials = [r for r in at_results if r['scenario'] == 'actual_new_note_GET_403_before_after_no_business_write']
assert len(denials) == 2 and {r['mode'] for r in denials} == {'current_403', 'late_403'}
assert len(observations) == 5 and all(not row['remaining_changed_tables'] for row in observations)
selected = [r for r in at_results if r['scenario'] == 'selected_capacity_actual_rule_and_current_rebind']
assert len(selected) == 2 and all(row['p1_lock_exact'] and row['all_six_local_outputs_verified'] for row in selected)
private = OUT / ('redaction-' + NAME + '.private.json')
assert private.stat().st_mode & 0o777 == 0o600
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SOURCE
schema_evidence = {
    'typed_graph_schema_1': 'tests/test_typed_source_impact_independent.py::test_aggregate_baseline_stable_ids_dates_and_read_only_without_opportunity',
    'shared_projection_schema_1_and_graph_schema_1': 'tests/test_shared_source_cases.py::test_two_actual_cases_share_owner_resource_pool_and_unaffected_p1_lock',
    'service_release_preflight_schema_1': 'tests/test_service_release_preflight.py::test_actual_v4_same_release_directory_preview_and_no_business_writes',
    'note_schema_1_actual_original_ui_parser_and_wrapped_buttons': 'tests/test_at24_27_change_batch_independent.py::test_at24_26_original_html_fixed_two_case_explicit_change_loop[accept]',
    'legacy_v1_admin_fixture_compatibility_not_new_business_positive': 'tests/test_typed_source_impact.py::test_v1_source_change_history_still_uses_original_algorithm_without_graph',
}
assert all(node in passed for node in schema_evidence.values())
report = dict(source_sha=SOURCE, tests=235, modules=7, new_tests=37, design_cases=20,
    fixed_review_oracle_sha256=digest(review_oracle),
    validator_sha256=digest(Path(__file__)), coverage_design_sha256=digest(OUT / 'coverage-design.json'),
    source_paths=result['tracked_source_paths'], all_tracked_paths=result['all_tracked_paths'], source_and_all_tracked_drift=[],
    exact_collection_junit=True, duplicated_tests=0, html_flows=len(flows), new_html_modes=12,
    new_backend_response_modes=9, new_controlled_negative_modes=3,
    all_html_transport_negative_count=sum(row['negative_transport_fixture'] for row in flows),
    actual_node_http_requests=sum(row['requests'] for row in flows), actual_python_http_requests=read('-http-traffic.json')['count'],
    schema_evidence=schema_evidence,
    independent_oracle_statistics=statistics, actual_note_403_no_business_write_snapshots=2,
    original_observe_true_invalidation_separate=True, selected_capacity_repaired_cases=2,
    selected_capacity_p1_locks_preserved=2, selected_capacity_old_reservations_preserved=True,
    private_mode='0600', private_value_count=len(json.loads(private.read_text())), private_values_exported=False,
    real_model_calls=0, real_browser='NOT_RUN', Windows='NOT_RUN', production='NOT_RUN', global_AT_signoff='NOT_CLAIMED')
save('-html-summary.json', dict(source_sha=SOURCE, flows=flows))
save('-oracle-statistics.json', dict(source_sha=SOURCE, groups=statistics))
save('-validation.json', report)
print(json.dumps(report, sort_keys=True))
