"""Independently count raw current windows; no business/source execution."""
from collections import Counter
from pathlib import Path
import argparse
import json
import re
import xml.etree.ElementTree as ET

from audit_archive import ROOT, HERE, read_json, relpath, public_json, identity, digest


def node(case, modules):
    parts = case.get('classname', '').split('.')
    position = next(i for i, part in enumerate(parts) if part.startswith('test_'))
    module = next(path for path in modules if Path(path).stem == parts[position])
    return module + '::' + '::'.join(parts[position + 1:] + [case.get('name')])


def window(folder, prefix, modules, source_sha):
    base = ROOT / '.runtime' / folder
    collection = base / (prefix + '-collection.json')
    if not collection.exists():
        collection = base / 'collection.json'
    raw_nodes = read_json(collection)
    cases = list(ET.parse(base / (prefix + '.xml')).iter('testcase'))
    assert all(case.find('failure') is None and case.find('error') is None and case.find('skipped') is None for case in cases)
    actual = [node(case, modules) for case in cases]
    assert len(raw_nodes) == len(set(raw_nodes)) == len(actual) == len(set(actual))
    assert set(actual) == set(raw_nodes)
    assert {item.split('::', 1)[0] for item in actual} == set(modules)
    record = base / (prefix + '.json')
    if record.exists():
        data = read_json(record)
        if 'source_sha' in data:
            assert data['source_sha'] == source_sha
        if 'counts' in data:
            assert data['counts'] == dict(PASS=len(actual), FAIL=0, ERROR=0, SKIP=0)
    return raw_nodes, dict(directory=folder, prefix=prefix, module_count=len(modules),
        actual_PASS=len(actual), raw_collection_JUnit_exact=True, unique_nodes=True,
        collection=identity(collection), JUnit=identity(base / (prefix + '.xml')))


def manifest_checks(config, folder, prefix):
    base = ROOT / '.runtime' / folder
    freeze = read_json(relpath(config['freeze']))
    observed = {}
    for side in ['before', 'after']:
        files = [base / (prefix + '-' + side + '.json'), base / ('source-' + side + '.json'),
                 base / (prefix + '-all-tracked-' + side + '.json'), base / ('all-tracked-' + side + '.json')]
        source = False
        full = False
        checks = []
        for path in files:
            if not path.exists():
                continue
            record = read_json(path)
            values = record.get('hashes', record)
            if values == freeze['all_tracked_sha256']:
                source = full = True
                checks.append(dict(path=str(path.relative_to(ROOT)), scope='ALL_13252_TRACKED', **identity(path)))
            elif values == freeze['source_paths']:
                source = True
                checks.append(dict(path=str(path.relative_to(ROOT)), scope='608_SOURCE', **identity(path)))
            else:
                raise AssertionError('window manifest differs from current freeze: ' + str(path.relative_to(ROOT)))
        assert source and (full or side == 'before'), 'required source/full-after manifest absent'
        observed[side] = dict(source608_equal=True, standalone_all13252_manifest=full, records=checks)
    # Root windows assert full all_before==freeze at startup but save only the
    # source-before map. State this evidence grain instead of inventing a file.
    if not observed['before']['standalone_all13252_manifest']:
        assert folder == 'manual-continuation-final'
        runner = (base / 'run_window.py').read_text()
        assert "assert all_before==freeze['all_tracked_sha256']" in runner
        observed['before']['full_before'] = 'ARCHIVED_RUNNER_STARTUP_ASSERT_PLUS_FROZEN_FULL_MANIFEST; NO_SEPARATE_FULL_BEFORE_FILE'
    return observed


def perform(config, attempt):
    assert read_json(attempt / 'mechanical-gate.json')['status'] == 'PASS_MECHANICAL_ONLY_SCOPE_GATE_STILL_REQUIRED'
    planned = read_json(relpath(config['planned']))
    planned_modules = [module for rows in planned['windows'].values() for module in rows]
    assert len(planned_modules) == len(set(planned_modules)) == config['complete_modules']
    all_nodes = []
    all_modules = []
    records = []
    for folder, prefix, modules_file in config['formal_windows']:
        modules = read_json(ROOT / '.runtime' / folder / modules_file)
        nodes, result = window(folder, prefix, modules, config['source_sha'])
        result['manifests'] = manifest_checks(config, folder, prefix)
        records.append(result); all_nodes += nodes; all_modules += modules
    assert len(all_modules) == len(set(all_modules)) == config['complete_modules']
    assert set(all_modules) == set(planned_modules)
    assert len(all_nodes) == len(set(all_nodes))
    root = read_json(relpath(config['coverage']))
    assert root['status'] == 'PASS' and root['source_sha'] == config['source_sha']
    assert root['complete_modules'] == len(all_modules) and root['unique_testcases'] == len(all_nodes)
    assert root['counts'] == dict(PASS=len(all_nodes), FAIL=0, ERROR=0, SKIP=0)
    supplemental = []
    extra_nodes = []
    for folder, prefix, count in config['supplemental_windows']:
        record = read_json(ROOT / '.runtime' / folder / (prefix + '.json'))
        assert record['source_sha'] == config['source_sha']
        nodes, result = window(folder, prefix, record['modules'], config['source_sha'])
        assert len(nodes) == count
        result['manifests'] = manifest_checks(config, folder, prefix)
        supplemental.append(result); extra_nodes += nodes
    assert len(extra_nodes) == len(set(extra_nodes)) == 10 and not set(extra_nodes).intersection(all_nodes)
    review = ROOT / '.runtime/manual-continuation-review-formal-v2'
    history = [json.loads(line) for line in (review / 'probes/freeze-14bc83f-probes-v2-history-observed.jsonl').read_text().splitlines()]
    assert len(history) == 2 and sum(row['damaged_cases'] for row in history) == 48
    assert all(row['all_refused'] and row['no_damaged_history_written_to_PG'] for row in history)
    vm = read_json(review / 'frozen-ui-probe-validation.json')
    assert vm['source_sha'] == config['source_sha'] and vm['checks'] == 4 and not vm['full_HTML_HTTP_PG']
    assert identity(review / 'frozen-ui-probe-result.json')['sha256'] == vm['actual_result_sha256']
    public_json(attempt / 'independent-window-union.json', dict(status='PASS_EXECUTION_COUNTS_ONLY',
        source_sha=config['source_sha'], complete_modules=len(all_modules), unique_testcases=len(all_nodes),
        counts=dict(PASS=len(all_nodes),FAIL=0,ERROR=0,SKIP=0), windows=records, supplemental_windows=supplemental,
        supplemental_pytest_items=10, history_fixture_items=2, in_memory_history_checks=48,
        extracted_function_VM_checks=4, these_units_not_added_to_complete_module_denominator=True,
        whole_repository_run=False, root_summary_compared_to_independent_raw_union=True,
        planning_source_hint=planned.get('source_to_freeze'), planning_hint_is_not_execution_proof=True))

    independent = ROOT / '.runtime/manual-continuation-independent-formal-v2'
    design = read_json(independent / 'manual-independent-v2-design-coverage.json')
    local = read_json(review / 'design-trace-review-only.json')
    oracle = read_json(relpath(config['oracle']))
    assert identity(relpath(config['oracle']))['sha256'] == config['oracle_sha256']
    ids = {row['id'] for row in oracle['cases']}
    assert len(ids) == 46 and {row['id'] for row in design['mappings']} == {row['id'] for row in local['mappings']} == ids
    assert design['executed_source_sha'] == local['source_sha'] == config['source_sha']
    assert design['oracle_sha256'] == local['oracle_sha256'] == config['oracle_sha256']
    assert design['design_is_not_execution_denominator'] and not local['all_46_executed']
    for row in design['mappings']:
        assert set(row['test_nodes']).issubset(all_nodes)
        assert 'PENDING' not in row['execution_status']
        if row['coverage_kind'] == 'NOT_RUN_IN_THIS_MODULE':
            assert not row['test_nodes'] and row['execution_status'] == 'NOT_RUN_IN_THIS_MODULE'
    for row in local['mappings']:
        assert set(row['actual_PASS_nodes']).issubset(set(all_nodes + extra_nodes))
    public_json(attempt / 'design-denominator-review.json', dict(status='PASS_SCOPED_TRACE_ONLY',
        source_sha=config['source_sha'], immutable_designs=46,
        independent_kinds=dict(Counter(row['coverage_kind'] for row in design['mappings'])),
        local_statuses=dict(Counter(row['execution_status'] for row in local['mappings'])),
        all_46_full_execution_claimed=False, each_cited_node_found_in_actual_current_PASS_collection=True,
        missing_variants_remain_NOT_RUN_or_PARTIAL=True))

    flows = read_json(independent / 'manual-independent-v2-html-summary.json')
    assert flows['source_sha'] == config['source_sha'] and len(flows['flows']) == 8
    modes = set(); request_total = 0; posts = 0; rows = []
    for summary in flows['flows']:
        trace = relpath(summary['trace'])
        assert identity(trace)['sha256'] == summary['trace_sha256']
        packets = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
        results = [packet for packet in packets if 'scope' in packet and 'calls' in packet]
        assert len(results) == 1
        result = results[0]
        assert result['scope'] == 'FULL_ORIGINAL_HTML_MANUAL_CONTINUATION_REAL_HTTP_ASGI_OWNED_PG'
        assert not result['negative_transport_fixture'] and result['real_browser'] == 'NOT_RUN'
        assert result['mode'] == summary['mode'] and result['mode'] not in modes
        modes.add(result['mode']); calls = result['calls']
        assert len(calls) == summary['requests']
        actual_posts = sum(call['method'] == 'POST' for call in calls)
        assert actual_posts == summary['posts']
        request_total += len(calls); posts += actual_posts
        rows.append(dict(mode=result['mode'], requests=len(calls), posts=actual_posts,
            observed_statuses=dict(Counter(str(call['status']) for call in calls)), trace=summary['trace']))
    validation = read_json(independent / 'manual-independent-v2-validation.json')
    assert request_total == validation['actual_html_http_requests']
    assert validation['full_html_flows'] == 8 and validation['successful_six_goal_closures'] == 5
    oracle_files = list((independent / 'artifacts/manual-independent-v2/test_manual_content_continuation_independent').glob('oracle-*.jsonl'))
    oracle_rows = [json.loads(line) for path in oracle_files for line in path.read_text().splitlines() if line.strip()]
    known = [row for row in oracle_rows if not row['intentional_unknown']]
    for row in known:
        assert row['source_sha'] == config['source_sha']
        assert set(row['actual_affected']) == set(row['expected_affected'])
        assert set(row['actual_preserved']) == set(row['expected_preserved'])
        assert row['missed_count'] == row['wrong_count'] == row['wrong_preserved_count'] == 0
    expected_pairs = sum(len(row['expected_affected']) for row in known)
    actual_pairs = sum(len(row['actual_affected']) for row in known)
    stated = validation['known_impact_oracle']
    assert len(known) == stated['records'] and expected_pairs == stated['expected_affected_pairs'] and actual_pairs == stated['actual_affected_pairs']
    unknown_nodes = validation['continuation_unknown_refusal_nodes']
    assert len(unknown_nodes) == len(set(unknown_nodes)) == 4 and set(unknown_nodes).issubset(all_nodes)
    assert validation['unknown_impact_precision'] == 'NOT_MEASURED_IN_THIS_MODULE'
    public_json(attempt / 'HTML-and-precision-denominators.json', dict(status='PASS_SCOPED_METRICS',
        source_sha=config['source_sha'], full_original_HTML_flows=8, actual_Node_HTML_HTTP=request_total,
        posts=posts, successful_six_goal_closures=5, rows=rows, known_impact_rows=len(known),
        known_affected_pairs=actual_pairs, missed=0, wrong=0, wrong_preserved=0,
        UNKNOWN_continuation_refusal_nodes=unknown_nodes, UNKNOWN_impact_precision='NOT_MEASURED',
        VM_checks_not_added_to_HTML_or_HTTP_or_precision_counts=True,
        formal_AT_Windows_real_browser_real_model_production='NOT_RUN'))
    public_json(attempt / 'execution-scope-gate.json', dict(status='PASS_SCOPE_METRICS_PUBLIC_REPORT_REVIEW_STILL_REQUIRED',
        source_sha=config['source_sha'], complete_modules=len(all_modules), unique_testcases=len(all_nodes),
        manual_public_report_review_required=True, final_gate_NOT_created=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--attempt', required=True)
    args = parser.parse_args(); config = read_json(HERE / 'audit-config.json')
    assert config['archive_ready'] is True, 'NOT_RUN: await explicit parent archive-ready message'
    assert re.fullmatch(r'[a-z0-9_-]{1,60}', args.attempt)
    perform(config, HERE / args.attempt)
