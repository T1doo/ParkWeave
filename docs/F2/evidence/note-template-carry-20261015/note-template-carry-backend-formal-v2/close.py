"""Mechanical closure of this formal window; never edits tested or prior evidence."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
import hashlib
import json
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/ParkWeave')
OUT = ROOT / '.runtime/note-template-carry-backend-formal-v2'


def read(name):
    return json.loads((OUT / name).read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


result = read('result.json')
html = read('html-summary.json')
oracle = read('oracle-statistics.json')
collection = read('collection.json')
nodes = read('junit-nodeids.json')
progress = [json.loads(line) for line in (OUT / 'progress.jsonl').read_text().splitlines()]
assert result['exit_code'] == 0 and result['counts'] == dict(PASS=235, FAIL=0, ERROR=0, SKIP=0)
assert result['collected'] == 235 and result['collection_junit_exact_match']
assert result['unique_collection_nodes'] and result['unique_junit_nodes']
assert not result['non_test_cases'] and result['raw_junit_cases'] == 235
assert not result['source_drift'] and not result['tracked_drift'] and not result['status_after']
assert result['head_after'] == result['source_sha'] and result['tracked_list_after_unchanged']
assert len(progress) == 235 and [r['nodeid'] for r in progress] == collection
assert all(r['when'] == 'call' and r['outcome'] == 'passed' for r in progress)
assert sorted(nodes) == sorted(collection)
assert html['exact_41'] and not html['trace_errors']
assert all(row['source_sha'] == result['source_sha'] for row in oracle['rows'])
assert all(not row[key] for row in oracle['rows'] for key in
           ['missed', 'wrongly_affected', 'wrongly_preserved', 'missing_preserved'])

module_counts = dict(Counter(node.split('::', 1)[0] for node in nodes))
categories = defaultdict(lambda: dict(traces=0, page_driver_fetch_records=0))
for trace in html['traces']:
    item = categories[trace['response_evidence']]
    item['traces'] += 1
    item['page_driver_fetch_records'] += trace['http_call_records']

prior_path = ROOT / '.runtime/note-template-carry-root/prior-raw-pre-final.json'
prior = json.loads(prior_path.read_text())
prior_drift = []
for entry in prior['entries']:
    path = ROOT / entry['path']
    actual = digest(path) if path.is_file() else None
    if actual != entry['sha256']:
        prior_drift.append(dict(path=entry['path'], expected_sha256=entry['sha256'], actual_sha256=actual))
prior_check = dict(utc=datetime.now(timezone.utc).isoformat(), phase='FINAL',
                   reference_path=str(prior_path), reference_sha256=digest(prior_path),
                   count=len(prior['entries']), drift=prior_drift, writes_to_prior_files=False)
save('prior-raw-final.json', prior_check)
assert not prior_drift

junit = ET.parse(OUT / 'formal.xml')
junit_suite_seconds = sum(float(s.get('time', '0')) for s in junit.iter('testsuite'))
summary = dict(
    source_sha=result['source_sha'], status='PASS', modules=module_counts,
    complete_modules=len(module_counts), collected=235, named_passed=235,
    named_failed=0, named_errors=0, skipped=0, unnamed_non_test_cases=0,
    exact_collection_junit=True, progress_call_order_matches_collection=True,
    started_utc=result['started_utc'], finished_utc=result['finished_utc'],
    runner_elapsed_seconds=result['elapsed_seconds'], junit_suite_seconds=junit_suite_seconds,
    source_files_checked=result['source_count'], tracked_files_checked=result['tracked_count'],
    source_drift=[], tracked_drift=[], git_status_after='', head_after=result['head_after'],
    prior_inventory=dict(count=prior_check['count'], drift=[], reference_sha256=prior_check['reference_sha256']),
    html=dict(total=html['total'], per_suite=html['actual_per_group'],
              page_driver_test_body_fetch_records=html['total_node_call_records'],
              fixture_setup_http_count=None, fixture_setup_http_count_status='NOT_COUNTED',
              response_evidence_categories=html['response_evidence_categories'],
              response_evidence_fetch_groups=dict(categories),
              real_browser='NOT_RUN',
              execution='Original HTML in Node VM/DOM shim -> real loopback HTTP/ASGI -> owned PostgreSQL',
              scope_note=html['http_call_record_scope']),
    oracle=dict(records=len(oracle['rows']), groups=oracle['groups'],
                current_sha_in_every_raw_record=True,
                missed=0, wrongly_affected=0, wrongly_preserved=0, missing_preserved=0,
                extra_unknown_must_be_reported=True,
                lock_field_records=sum(row['lock_comparison_recorded'] for row in oracle['rows']),
                expected_locked_pairs=sum(row.get('expected_locked_pairs', 0) for row in oracle['rows']),
                wrong_lock_pairs=sum(row.get('wrong_lock_pairs', 0) for row in oracle['rows']),
                selected_capacity_p1_lock_preservation=oracle['selected_capacity_p1_lock_preservation'],
                limits=[oracle['unknown_note'], oracle['missing_lock_fields_note']]),
    evidence=dict(result='result.json', collection='collection.json', junit='formal.xml',
                  nodeids='junit-nodeids.json', progress='progress.jsonl',
                  html='html-summary.json', oracle='oracle-statistics.json',
                  artifacts='artifacts-index.json', prior='prior-raw-final.json'),
    limits=['Seven complete modules only; repository-wide aggregation belongs to root',
            'Linux synthetic engineering evidence; formal business acceptance not signed off',
            'Windows, real browser, real model, production, and real governance NOT_RUN',
            'Private synthetic fixture registries are retained for root exact-value redaction, never exported here'])
# Keep the previous formal summary DTO consumed by root; new measurements above are additive.
launch = read('launch.json')
old_partial_path = ROOT / '.runtime/note-template-carry-backend-formal/interrupted-closure.json'
old_partial = json.loads(old_partial_path.read_text())
legacy_records_path = OUT / 'artifact-legacy/fixed-test-artifact-redirections.json'
legacy_records = json.loads(legacy_records_path.read_text()) if legacy_records_path.exists() else []
summary.update(
    elapsed_seconds=result['elapsed_seconds'], counts=result['counts'],
    exact_collection_junit_nodes=True, progress_junit_order_equal=True,
    source_files_unchanged=result['source_count'], all_tracked_files_unchanged=result['tracked_count'],
    working_tree_clean=True,
    legacy_capture=dict(enabled=True, script_sha256=launch['legacy_capture_sha256'],
                        roots_sha256=launch['legacy_roots_sha256'], destination_precreated=True,
                        actual_matched_redirection_records=len(legacy_records),
                        artifact_files=sum(p.is_file() for p in (OUT / 'artifact-legacy').rglob('*')),
                        meaning='Matched legacy fixed paths alone are redirected; module OUT bindings use shared_capture. Product, auth and assertions are unchanged.'),
    old_partial=dict(source_sha=old_partial['source_sha'],
                     executed_pass=old_partial['actual_named_completed_count'],
                     unexecuted=old_partial['actual_uncompleted_count'],
                     raw_junit_cases=old_partial['raw_junit_cases'],
                     unnamed_placeholder_count=len(old_partial['unnamed_synthetic_cases']),
                     reason=old_partial['reason'], included_in_final_counts=False,
                     path=str(old_partial_path)),
    evidence_files=['result.json', 'formal.xml', 'formal.log', 'collection.json', 'junit-nodeids.json',
                    'progress.jsonl', 'source-before.json', 'source-after.json',
                    'all-tracked-before.json', 'all-tracked-after.json', 'html-summary.json',
                    'oracle-statistics.json', 'artifacts-index.json', 'prior-raw-final.json'])
summary['html'].update(traces=html['total'], page_driver_fetch_records=html['total_node_call_records'],
                       http_count_scope=html['http_call_record_scope'], groups=html['actual_per_group'],
                       originals=str(OUT / 'html-summary.json') + ' (per-trace raw path, hash, mode, calls, evidence category)')
summary['oracle'].update(all_record_source_sha=result['source_sha'],
                         preflight_lock_fields=dict(
                             records=sum(row['lock_comparison_recorded'] for row in oracle['rows']),
                             expected_locked_pairs=sum(row.get('expected_locked_pairs', 0) for row in oracle['rows']),
                             wrong_lock_pairs=sum(row.get('wrong_lock_pairs', 0) for row in oracle['rows'])),
                         selected_capacity_p1_lock_preservation_cases=len(oracle['selected_capacity_p1_lock_preservation']))
save('report-summary.json', summary)

lines = [f"Frozen SHA `{result['source_sha']}`: **235/235 named PASS**, seven complete modules.",
         '', f"Collection, JUnit and progress nodes match exactly; no unnamed placeholders. "
         f"{result['source_count']} source files and {result['tracked_count']} tracked files retain their hashes; "
         f"HEAD and clean Git status are unchanged. Prior {prior_check['count']}-file inventory has no drift.",
         '', f"41 original-HTML traces ({'+'.join(str(v) for v in html['actual_per_group'].values())}); "
         f"{html['total_node_call_records']} page-driver test-body fetch records. Python fixture/setup HTTP is not counted. "
         'Node VM/DOM shim -> actual HTTP/ASGI -> owned PostgreSQL; real browser NOT_RUN.', '',
         '| Response evidence | Traces | Page-driver fetch records |', '|---|---:|---:|']
for name, value in categories.items():
    lines.append(f"| {name} | {value['traces']} | {value['page_driver_fetch_records']} |")
lines.extend(['', '| Oracle suite | Known records / affected pairs | Declared UNKNOWN records / pairs | Extra observed UNKNOWN records / pairs |',
              '|---|---:|---:|---:|'])
for group, groups in oracle['groups'].items():
    cells = [f"{groups[key]['records']} / {groups[key]['expected_affected_step_pairs']}" for key in
             ['known_partition_by_record', 'declared_unknown', 'additional_graph_unknown']]
    lines.append(f"| {group} | " + ' | '.join(cells) + ' |')
lines.extend(['', 'All recorded affected/preserved comparisons match the literal oracle. '
              'UNKNOWN expansions are reported separately from definite impact precision. '
              'Absent lock fields do not imply a zero-lock-test result.', '',
              'Raw hashes, modes, node IDs and limits are in report-summary.json, html-summary.json, '
              'oracle-statistics.json and artifacts-index.json. No Windows, real browser, formal AT, '
              'real model, production or real governance claim is made.'])
(OUT / 'report-summary.md').write_text('\n'.join(lines) + '\n')
print(json.dumps(dict(source_sha=summary['source_sha'], named_passed=235,
                      html=summary['html'], oracle_groups=summary['oracle']['groups'],
                      prior_files=prior_check['count'], prior_drift=len(prior_drift)), ensure_ascii=False))
