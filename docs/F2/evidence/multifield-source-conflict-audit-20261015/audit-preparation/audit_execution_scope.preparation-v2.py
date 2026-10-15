"""Independent full-node/module/unit recount. No producer/verifier imports."""
from collections import Counter
from pathlib import Path
import argparse
import json
import re
import traceback
import xml.etree.ElementTree as ET

from audit_archive import ROOT, HERE, read_json, relpath, identity, public_json


def junit_nodes(path, runtime=False):
    root = ET.fromstring(path.read_bytes())
    cases = list(root.iter('testcase'))
    entries = []
    for case in cases:
        classname, name = case.get('classname'), case.get('name')
        assert isinstance(classname, str) and classname and isinstance(name, str) and name
        if runtime:
            node = ('.' + classname[1:].replace('.', '/') if classname.startswith('.') else classname.replace('.', '/')) + '.py::' + name
        else:
            # Original class-aware pytest identity; parameter text is never normalized.
            pieces = classname.split('.')
            found = [i for i, part in enumerate(pieces) if part.startswith('test_')]
            assert found, 'JUnit identity lacks test module'
            index = found[0]
            node = 'tests/' + pieces[index] + '.py::' + '::'.join(pieces[index + 1:] + [name])
        status = 'ERROR' if case.find('error') is not None else 'FAIL' if case.find('failure') is not None else 'SKIP' if case.find('skipped') is not None else 'PASS'
        entries.append((node, status))
    assert entries and len(entries) == len({node for node, _ in entries}), 'missing/duplicate JUnit identities'
    counts = dict(Counter(status for _, status in entries))
    for suite in root.iter('testsuite'):
        own = list(suite.iter('testcase'))
        if not own:
            continue
        assert int(suite.get('tests')) == len(own), 'JUnit suite count differs from cases'
        for attr, status in [('failures', 'FAIL'), ('errors', 'ERROR'), ('skipped', 'SKIP')]:
            if suite.get(attr) is not None:
                assert int(suite.get(attr)) == sum(1 for c in own if
                    ('ERROR' if c.find('error') is not None else 'FAIL' if c.find('failure') is not None else 'SKIP' if c.find('skipped') is not None else 'PASS') == status)
    return entries, counts


def frozen_window(config, freeze, base, name, chosen=None, reason=None):
    assert re.fullmatch(r'[a-z0-9_-]+', name)
    evidence = [base / (name + suffix) for suffix in ['.json', '.xml', '-collection.json', '-before.json', '-after.json', '-all-tracked-before.json', '-all-tracked-after.json']]
    identities = {str(p.relative_to(ROOT)): identity(p) for p in evidence}
    data = read_json(base / (name + '.json'))
    collected = read_json(base / (name + '-collection.json'))
    assert isinstance(collected, list) and all(isinstance(n, str) for n in collected)
    assert len(collected) == len(set(collected)), 'duplicate raw collection'
    entries, counts = junit_nodes(base / (name + '.xml'))
    assert Counter(collected) == Counter(node for node, _ in entries), 'raw full collection/JUnit differs'
    assert Counter(data['collected_nodes']) == Counter(collected)
    assert {k: v for k, v in data['counts'].items() if v} == counts, 'runner count differs from independent cases'
    assert data['source_sha'] == config['source_sha'] == freeze['source_sha']
    assert len(data['modules']) == len(set(data['modules']))
    assert set(data['modules']) == {node.split('::', 1)[0] for node, _ in entries}
    for suffix, target in [('-before.json', 'source_paths'), ('-after.json', 'source_paths'),
                           ('-all-tracked-before.json', 'all_tracked_sha256'), ('-all-tracked-after.json', 'all_tracked_sha256')]:
        assert read_json(base / (name + suffix)) == freeze[target], 'window manifest differs from frozen map'
    assert not data['source_drift'] and not data['all_tracked_drift'] and not data['runner_drift']
    modules = data['modules'] if chosen is None else chosen
    assert modules and len(modules) == len(set(modules)) and set(modules) <= set(data['modules'])
    selected = [(node, status) for node, status in entries if node.split('::', 1)[0] in modules]
    assert {node.split('::', 1)[0] for node, _ in selected} == set(modules)
    assert all(status == 'PASS' for _, status in selected), 'selected complete module has non-PASS'
    excluded = sorted(set(data['modules']) - set(modules))
    if excluded:
        assert reason and data['exit_code'] != 0, 'partial raw-window selection needs explicit whole-module exclusion reason'
    else:
        assert data['exit_code'] == 0, 'full raw window did not exit zero'
    for path, before in identities.items():
        assert identity(relpath(path)) == before, 'execution evidence changed while recounted'
    return dict(name=name, source_sha=data['source_sha'], raw_counts=counts,
                raw_pytest_exit=data['exit_code'], raw_full_node_count=len(entries),
                selected_modules=modules, excluded_whole_modules=excluded, reason=reason,
                selected_nodes=[node for node, _ in selected], selected_PASS=len(selected),
                collection_junit_exact_without_uuid_or_parameter_normalization=True, evidence=identities,
                all_tracked_and_source_before_after_exact=True)


def supplement(config, freeze):
    base = relpath(config['supplemental_prefix'])
    validation = read_json(base / 'validation.json')
    assert validation['source_sha'] == config['source_sha'] and validation['status'] == 'PASS'
    for suffix in ['before', 'after']:
        manifest = read_json(base / ('alltracked-' + suffix + '.json'))
        assert manifest['source_sha'] == config['source_sha'] and manifest['all_tracked_sha256'] == freeze['all_tracked_sha256']
    collection = read_json(base / 'pytest-collection.json')['nodeids']
    entries, counts = junit_nodes(base / 'supplement.xml', runtime=True)
    assert Counter(collection) == Counter(node for node, _ in entries)
    assert len(collection) == len(set(collection)) == 4 and counts == {'PASS': 4}
    matrix = read_json(base / 'history-matrix-result.json')
    assert matrix['units'] == 37 and len(matrix['results']) == 37
    assert all(row['actual_rejected'] is True and row['expected_rejected'] is True for row in matrix['results'])
    vm = read_json(base / 'vm-29/probe-result.json')
    assert vm['units'] == 29 and validation['vm_exit'] == 0
    budget = read_json(base / 'budget-six-checks.json')
    assert budget['units'] == 6 and validation['budget_is_pure_known_basis_stub'] is True
    imports = read_json(base / 'execution-source-resolution.json')
    assert imports['unchanged'] is True and imports['actual_imports_before'] == imports['actual_imports_after']
    plugin = Path(imports['plugin_path'])
    assert plugin.parent == base and identity(plugin)['sha256'] == imports['plugin_sha256']
    for row in imports['actual_imports_before'].values():
        path = Path(row['path'])
        assert path.is_relative_to(ROOT / 'src/parkweave') and identity(path)['sha256'] == row['sha256']
    assert read_json(base / 'probe-hashes-before.json') == read_json(base / 'probe-hashes-after.json')
    return dict(status='PASS_SUPPLEMENT_ONLY', source_sha=config['source_sha'], pytest=4,
                pure_history_mutations_in_one_pytest=37, VM_DTO_transport_mechanics=29,
                pure_budget_stub_checks_in_one_pytest=6, full_module_union_member=False,
                real_browser=False, five_goal_carry_compatibility_supplement_not_six_goal_main=True,
                final_UNKNOWN_is_controlled_availability_seam_not_real_clock_expiry=True,
                collection_junit_exact_without_normalization=True,
                unique_plugin=dict(path=str(plugin.relative_to(ROOT)), sha256=imports['plugin_sha256']))


def perform(config, out):
    freeze = read_json(relpath(config['freeze']))
    plan = read_json(relpath(config['planned']))
    selected = read_json(relpath(config['selected_windows']))
    expected_list = [m for group in plan['windows'].values() for m in group]
    assert len(expected_list) == len(set(expected_list)) == config['complete_modules'] == 97
    assert plan['complete_modules'] == 97 and plan['full_repository_run'] is False
    assert len(selected) == len({row['name'] for row in selected})
    records = [frozen_window(config, freeze, relpath(config['execution_base']), row['name'],
                             row.get('selected_modules'), row.get('reason')) for row in selected]
    modules = [m for row in records for m in row['selected_modules']]
    nodes = [n for row in records for n in row['selected_nodes']]
    assert len(modules) == len(set(modules)) == 97 and set(modules) == set(expected_list)
    assert len(nodes) == len(set(nodes)), 'overlapping selected raw nodes'
    reported = read_json(relpath(config['coverage']))
    assert reported['source_sha'] == config['source_sha'] and reported['status'] == 'PASS'
    assert reported['complete_modules'] == 97 and reported['unique_testcases'] == len(nodes)
    assert reported['counts'] == dict(PASS=len(nodes), FAIL=0, ERROR=0, SKIP=0)
    assert reported['full_repository_run'] is False and reported['supplemental_review_not_in_union'] is True
    ci = None
    if config.get('ci_metadata_window_prefix'):
        ci_modules = read_json(relpath(config['ci_metadata_modules']))
        ci = frozen_window(config, freeze, relpath(config['execution_base']), config['ci_metadata_window_prefix'])
        assert set(ci['selected_modules']) == set(ci_modules) and len(ci_modules) == len(set(ci_modules)) == 12
        assert not set(ci_modules).intersection(modules)
        ci['scope'] = 'SEPARATE_COMPLETE_CI_METADATA_MODULES_NOT_IN97'
    else:
        raise AssertionError('final CI12 execution prefix not yet provided; preparation cannot sign final scope')
    result = dict(status='PASS_EXECUTION_SCOPE_ONLY_OTHER_GATES_STILL_REQUIRED', source_sha=config['source_sha'],
                  complete_modules=97, selected_unique_pytest_nodes=len(nodes), selected_PASS=len(nodes),
                  complete_repository=False, windows=records, raw_failed_or_interrupted_historical_windows_counted=False,
                  supplemental=supplement(config, freeze), CI_metadata_supplement=ci,
                  blocked_external_modules=plan['blocked_external_modules'])
    public_json(out / 'independent-window-union.json', result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--archive-ready', action='store_true')
    args = parser.parse_args()
    config = read_json(HERE / 'audit-config.json')
    assert args.archive_ready and config['archive_ready'] is True, 'NOT_RUN: explicit archive-ready required'
    assert re.fullmatch(r'[a-z0-9_-]+', args.attempt)
    out = HERE / args.attempt
    assert out.is_dir() and not (out / 'independent-window-union.json').exists()
    try:
        perform(config, out)
    except BaseException as exc:
        public_json(out / 'execution-audit-failure.json', dict(status='FAIL_OR_STOP_NOT_FINAL_PASS',
                    error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc()))
        raise


if __name__ == '__main__':
    main()
