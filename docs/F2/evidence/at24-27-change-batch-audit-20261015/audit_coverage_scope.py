"""Independent read-only checks of frozen test windows and evidence units.

No root producer, verifier, validation helper, or product partition algorithm imported.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path('/workspace/ParkWeave')
OUT = ROOT / '.runtime/at24-27-audit'
SHA = '5a7eee826564426a4c36607ac038bd61e00665d7'
WINDOWS = [
    ('.runtime/at24-27-root/root-1-v2', 27, 900),
    ('.runtime/at24-27-root/root-2-v2', 25, 789),
    ('.runtime/at24-27-independent/independent-v3', 7, 235),
    ('.runtime/at24-27-review-v2/freeze-5a7eee8-extra', 13, 388),
    ('.runtime/at24-27-common-clear-regression/common-clear-v1', 18, 305),
]


def load(path):
    return json.loads((ROOT / path).read_text())


def digest(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def state(test):
    return 'FAIL' if test.find('failure') is not None else 'ERROR' if test.find('error') is not None else 'SKIP' if test.find('skipped') is not None else 'PASS'


def window_check(prefix, expected_modules, expected_count, source, tracked):
    report = load(prefix + '.json')
    assert report['source_sha'] == SHA and report['exit_code'] == 0
    assert not report['source_drift']
    modules = report['modules']
    assert len(modules) == len(set(modules)) == expected_modules
    collected = load(prefix + '-collection.json')
    if isinstance(collected, dict):
        assert collected.get('source_sha', SHA) == SHA
        collected = collected.get('nodes', collected.get('collected_nodes', collected.get('nodeids')))
    assert isinstance(collected, list) and len(collected) == len(set(collected)) == expected_count
    assert collected == report['collected_nodes']
    tests = list(ET.parse(ROOT / (prefix + '.xml')).getroot().iter('testcase'))
    module_classnames = {m[:-3].replace('/', '.'): m for m in modules}
    junit = []
    for test in tests:
        classname = test.attrib['classname']
        matches = [key for key in module_classnames if classname == key or classname.startswith(key + '.')]
        assert len(matches) == 1, classname
        key = matches[0]
        classes = classname[len(key):].lstrip('.')
        path = module_classnames[key] + '::'
        if classes:
            path += classes.replace('.', '::') + '::'
        junit.append(path + test.attrib['name'])
    assert len(junit) == len(set(junit)) == expected_count
    assert collected == junit, prefix + ': raw collection/JUnit order mismatch'
    actual = dict(Counter(state(t) for t in tests))
    assert actual == {'PASS': expected_count}
    assert report['counts'] == {'PASS': expected_count, 'FAIL': 0, 'ERROR': 0, 'SKIP': 0}
    before = load(prefix + '-before.json')
    after = load(prefix + '-after.json')
    assert before == after
    if 'hashes' in before:
        assert before['source_sha'] == SHA
        assert before['hashes'] == tracked
        assert set(before['source_paths']) == set(source)
    else:
        assert before == source
    if 'independent-v3' in prefix:
        assert load(prefix + '-all-tracked-before.json') == tracked
        assert load(prefix + '-all-tracked-after.json') == tracked
    return dict(prefix=prefix, source_sha=SHA, modules=modules, count=expected_count,
                runner_seconds=report['elapsed_seconds'], raw_collection_junit_exact=True,
                raw_nodeids_normalized=False, artifacts={suffix: digest(prefix + suffix)
                for suffix in ['.json', '.xml', '.log', '-collection.json', '-before.json', '-after.json']}), collected


def safe_node(value):
    return value.removesuffix(' (call)')


def main():
    started = datetime.now(timezone.utc).isoformat()
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SHA
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip()
    freeze = load('.runtime/at24-27-root/final-freeze-v2.json')
    source, tracked = freeze['source_paths'], freeze['all_tracked_sha256']
    assert freeze['source_sha'] == SHA and len(source) == 605 and len(tracked) == 12417
    assert all(digest(path) == value for path, value in tracked.items())
    windows = []
    all_nodes = set()
    all_modules = set()
    for prefix, modules, count in WINDOWS:
        result, nodes = window_check(prefix, modules, count, source, tracked)
        assert not all_nodes.intersection(nodes) and not all_modules.intersection(result['modules'])
        all_nodes.update(nodes)
        all_modules.update(result['modules'])
        windows.append(result)
    plan = load('.runtime/at24-27-root/planned-regression-expanded.json')
    assert plan['source_sha'] == SHA and plan['full_repository_run'] is False
    assert all_modules == set(plan['complete_modules']) and len(all_modules) == 90 and len(all_nodes) == 2617
    old_plan = load('.runtime/at24-27-root/planned-regression.json')
    old_modules = old_plan.get('complete_modules', old_plan.get('modules'))
    assert len(old_modules) == 72 and set(old_modules).issubset(all_modules)
    assert set(windows[-1]['modules']) == set(plan['added_complete_modules'])
    root_union = load('.runtime/at24-27-root/final-regression-verification.json')
    assert root_union['status'] == 'PASS' and root_union['unique_testcases'] == len(all_nodes)
    save('five-window-independent-coverage.json', dict(status='PASS', source_sha=SHA,
        complete_modules=len(all_modules), unique_testcases=len(all_nodes), counts={'PASS': len(all_nodes), 'FAIL': 0, 'ERROR': 0, 'SKIP': 0},
        actual_windows=windows, source_paths=605, tracked_paths=12417, actual_collection_junit_exact=True,
        all_nodeids_unmodified=True, complete_module_set=sorted(all_modules), full_repository_run=False,
        historical_WIP_failed_interrupted_windows_included_in_PASS=False))

    ind = '.runtime/at24-27-independent/'
    manifests = [load(ind + n) for n in ['independent-v3-own-traces.json', 'independent-v3-related-traces.json']]
    trace_records = [record for manifest in manifests for record in manifest['records']]
    assert sum(m['count'] for m in manifests) == len(trace_records) == len({r['path'] for r in trace_records})
    for record in trace_records:
        assert record['source_sha'] == SHA and digest(record['path']) == record['sha256']
    trace_paths = {record['path'] for record in trace_records}
    oracle_path = 'docs/F2/AT24-27FixedOracles-20261015.json'
    oracle = load(oracle_path)
    mapping = load(ind + 'independent-v3-fixed-case-coverage.json')
    assert mapping['source_sha'] == SHA and mapping['review_oracle_sha256'] == digest(oracle_path)
    assert len(oracle['cases']) == len(mapping['mappings']) == mapping['design_case_count'] == 20
    assert {row['id'] for row in oracle['cases']} == {row['id'] for row in mapping['mappings']}
    assert len(oracle['opportunity_dedup_oracles']) == len(oracle['security_and_recovery_oracles']) == 8
    for row in mapping['mappings']:
        assert row['execution_status'] == 'PASS_IN_FROZEN_LINUX_SYNTHETIC_SCOPE'
        assert row['test_nodes'] and set(row['test_nodes']).issubset(all_nodes)
    assert mapping['pytest_case_count'] == 37 and mapping['counts_are_different_units']
    per_at = load(ind + 'independent-v3-per-at.json')
    at_records = per_at['per_at_records']
    for at, records in at_records.items():
        for row in records:
            assert row['result'] == 'PASS' and safe_node(row['test']) in all_nodes
            assert row['trace'] in trace_paths and digest(row['trace']) == row['trace_sha256']
            raw_row = json.loads((ROOT / row['trace']).read_text().splitlines()[row['trace_line'] - 1])
            assert raw_row['source_sha'] == SHA and raw_row['scenario'] == row['scenario'] and raw_row['result'] == 'PASS'

    groups = defaultdict(lambda: defaultdict(Counter))
    oracle_records = []
    for record in trace_records:
        path = record['path']
        if not Path(path).name.startswith('oracle-'):
            continue
        name = Path(path).parent.name
        group = 'test_at24_27_change_batch_independent' if name == 'at24-27-independent' else name
        for row in map(json.loads, (ROOT / path).read_text().splitlines()):
            assert row.get('source_sha', row.get('head')) == SHA and safe_node(row['test']) in all_nodes
            intentional = row.get('intentional_unknown', row.get('intentional_unknown_expansion', False))
            # The historical typed "fact" record omits state; its original
            # test explicitly asserts actual UNKNOWN. Preserve its own group.
            other_unknown = row.get('actual_state') == 'UNKNOWN' or row.get('actual_classification') == 'UNKNOWN' or group == 'test_typed_source_impact_independent' and row['scenario'] == 'fact'
            kind = 'conservative_unknown' if intentional else 'other_observed_unknown' if other_unknown else 'known'
            count = groups[group][kind]
            count['records'] += 1
            for name in ['affected', 'preserved']:
                expected, actual = set(row['expected_' + name]), set(row['actual_' + name])
                assert len(expected) == len(row['expected_' + name]) and len(actual) == len(row['actual_' + name])
                assert expected == actual, (group, row['scenario'], name)
                if name == 'affected':
                    count['expected_affected_pairs'] += len(expected)
                    count['actual_affected_pairs'] += len(actual)
                    count['missed_count'] += len(expected - actual)
                    count['wrong_count'] += len(actual - expected)
                else:
                    count['wrong_preserved_count'] += len(actual - expected)
            count['wrong_locked_count'] += 0
            if 'actual_locked' in row:
                count['lock_records'] += 1
                assert set(row['expected_locked']) == set(row['actual_locked'])
                count['expected_locked_pairs'] += len(set(row['expected_locked']))
                count['actual_locked_pairs'] += len(set(row['actual_locked']))
            oracle_records.append(dict(group=group, partition=kind, scenario=row['scenario'], test=safe_node(row['test']), affected_pairs=len(row['expected_affected'])))
    reported_stats = load(ind + 'independent-v3-oracle-statistics.json')['groups']
    default_keys = ['records', 'expected_affected_pairs', 'actual_affected_pairs', 'expected_locked_pairs', 'actual_locked_pairs', 'lock_records', 'missed_count', 'wrong_count', 'wrong_preserved_count', 'wrong_locked_count']
    rebuilt_stats = {g: {kind: {key: groups[g][kind][key] for key in default_keys}
                     for kind in ['known', 'conservative_unknown', 'other_observed_unknown']} for g in groups}
    assert rebuilt_stats == reported_stats
    raw_results = [json.loads(line) for r in trace_records if Path(r['path']).name.startswith('at-results-') for line in (ROOT / r['path']).read_text().splitlines()]
    assert all(row['source_sha'] == SHA and row['result'] == 'PASS' and safe_node(row['test']) in all_nodes for row in raw_results)
    selected = [r for r in raw_results if r['scenario'] == 'selected_capacity_actual_rule_and_current_rebind']
    assert {r['case'] for r in selected} == {'A', 'B'}
    for row in selected:
        assert row['literal_affected'] == ['P2', 'P3', 'P4', 'P5'] and row['literal_preserved'] == ['P1']
        assert row['p1_lock_exact'] and row['original_first_delivery_approval_preserved'] and row['all_six_local_outputs_verified']
        assert row['replacement_formal_approval'] == 'NOT_IMPLEMENTED'
    denied = [r for r in raw_results if r['scenario'] == 'actual_new_note_GET_403_before_after_no_business_write']
    assert len(denied) == 2 and all(r['response_status'] == 403 and r['original_plan_observation_separate'] for r in denied)

    html = load(ind + 'independent-v3-html-summary.json')
    assert html['source_sha'] == SHA and len(html['flows']) == 41
    scopes = Counter()
    negatives = Counter()
    actual_calls = 0
    for flow in html['flows']:
        assert flow['trace'] in trace_paths and digest(flow['trace']) == flow['sha256']
        rows = [json.loads(line) for line in (ROOT / flow['trace']).read_text().splitlines()]
        assert all(set(r)=={'control'} or 'scope' in r for r in rows)
        final_rows = [r for r in rows if 'scope' in r]
        assert len(final_rows) == 1
        row = final_rows[0]
        assert row['scope'] == flow['scope'] and row['mode'] == flow['mode']
        assert row.get('real_browser', 'NOT_RUN') == 'NOT_RUN'
        assert row['checks'] == flow['checks'] and row['checks'] > 0
        assert len(row['calls']) == flow['requests']
        assert sum(c['method'] == 'POST' for c in row['calls']) == flow['posts']
        assert all({'method','path','status'} <= set(c) <= {'method','path','status','body','request_key','graph_sha256'} for c in row['calls'])
        assert flow['negative_transport_fixture'] == row.get('negative_transport_fixture', False)
        scopes[flow['scope']] += 1
        negatives[flow['scope']] += bool(flow['negative_transport_fixture'])
        actual_calls += len(row['calls'])
    assert sorted(scopes.values()) == [6, 9, 12, 14] and sum(negatives.values()) == 5 and actual_calls == 957
    new_scope = 'FULL_ORIGINAL_HTML_AT24_27_FIXED_TWO_CASE_REAL_HTTP_ASGI_OWNED_PG'
    assert scopes[new_scope] == 12 and negatives[new_scope] == 3
    http = load(ind + 'independent-v3-http-traffic.json')
    assert len(http['requests']) == http['count'] == 6109 and http['headers_or_tokens_saved'] is False
    assert all(safe_node(r['test']) in all_nodes and r['transport'] == 'ACTUAL_LOOPBACK_HTTP' for r in http['requests'])
    save('scope-oracle-html-independent.json', dict(status='PASS', source_sha=SHA,
        literal_oracle_sha256=digest(oracle_path), design_scenarios=20, new_pytest_nodes=37,
        design_ids_match=True, mapping_nodes_all_frozen_PASS=True, per_AT_trace_rows_verified=sum(map(len, at_records.values())),
        independent_precision_recomputed=rebuilt_stats, individual_oracle_rows=oracle_records,
        selected_capacity_locks_separately_verified=2, new_GET403_no_business_write_snapshots=2,
        html_flows=41, html_scope_counts=dict(scopes), negative_transport_fixture_by_scope=dict(negatives),
        new_html_backend_response_modes=9, new_html_controlled_negative_modes=3,
        node_HTTP_calls=actual_calls, python_test_body_loopback_HTTP_calls=http['count'],
        entire_fixture_setup_traffic_claimed=False, real_browser='NOT_RUN', global_AT_signoff='NOT_CLAIMED',
        scope_does_not_include_general_graph_merge_migration_or_approval=True))

    old = load('docs/F2/evidence/service-release-preflight-20261015/index.json')
    assert len(old['entries']) == 273
    for row in old['entries']:
        b = (ROOT / row['raw_path']).read_bytes()
        assert len(b) == row['raw_bytes'] and hashlib.sha256(b).hexdigest() == row['raw_sha256']
    save('previous-primary-originals-independent.json', dict(status='PASS', old_primary='service-release-preflight-20261015', private_originals_unchanged=273))
    assert all(digest(path) == value for path, value in tracked.items())
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == SHA
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip()
    save('coverage-scope-complete.json', dict(status='PASS', source_sha=SHA, started_utc=started,
        finished_utc=datetime.now(timezone.utc).isoformat(), source_paths=605, tracked_paths=12417,
        source_and_all_tracked_before_after_unchanged=True, no_root_producer_or_verifier_imported=True))
    print(json.dumps(dict(status='PASS', source_sha=SHA, modules=90, PASS=2617, design_scenarios=20,
                         html_flows=41, negative_transport_modes=5, no_product_or_test_execution=True)))


if __name__ == '__main__':
    main()
