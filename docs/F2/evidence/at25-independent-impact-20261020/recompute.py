"""Recompute this bounded AT25 execution from literal oracles, never product code."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_id(row):
    return row['test'].rsplit(' (', 1)[0]


def recompute(runtime, literal_path, run_id, source_sha):
    literal = json.loads(literal_path.read_text())
    scenarios = {'A_material_content', 'owner_optional_resource_capacity',
                 'shared_catalog_source_contract', 'shared_catalog_unavailable_unknown',
                 'selected_resource_capacity_and_revision'}
    prefix = 'tests/test_at24_27_change_batch_independent.py::'
    nodes = {scenario: prefix + 'test_at25_fixed_two_case_literal_source_partitions[' + scenario + ']'
             for scenario in scenarios if scenario != 'selected_resource_capacity_and_revision'}
    nodes['selected_resource_capacity_and_revision'] = prefix + 'test_at25_selected_capacity_two_case_old_reservations_preserved_and_explicit_rebind'
    physical_counts = {scenario: 1 if scenario in ('A_material_content', 'selected_resource_capacity_and_revision') else 2
                       for scenario in scenarios}
    paths = {kind: runtime / (kind + '-' + run_id + '.jsonl') for kind in ('baseline', 'oracle', 'at-results')}
    rows = {kind: [json.loads(line) for line in path.read_text().splitlines()] for kind, path in paths.items()}
    assert all(row['run_id'] == run_id and row['source_sha'] == source_sha for values in rows.values() for row in values)
    baselines = {}
    for row in rows['baseline']:
        key = test_id(row)
        assert key not in baselines and set(row['cases']) == {'A', 'B'}
        assert all(set(c['step_ids']) == {'P1', 'P2', 'P3', 'P4', 'P5'} for c in row['cases'].values())
        step_sets = [set(c['step_ids'].values()) for c in row['cases'].values()]
        assert all(len(ids) == 5 for ids in step_sets) and step_sets[0].isdisjoint(step_sets[1])
        baselines[key] = row
    assert set(baselines) == set(nodes.values())
    assert len(rows['oracle']) == sum(2 * count for count in physical_counts.values())
    grouped = defaultdict(list)
    for row in rows['oracle']:
        assert row['scenario'] in scenarios and row['case'] in {'A', 'B'}
        grouped[(row['scenario'], row['case'])].append(row)
    assert set(grouped) == {(scenario, case) for scenario in scenarios for case in ('A', 'B')}
    transport = {'run_id', 'source_sha', 'utc', 'test'}
    observations = []
    for (scenario, case), values in sorted(grouped.items()):
        assert len(values) == physical_counts[scenario], 'Missing or extra fixed observation'
        canonical = [{k: v for k, v in row.items() if k not in transport} for row in values]
        assert all(value == canonical[0] for value in canonical), 'Conflicting duplicate observation'
        assert {test_id(row) for row in values} == {nodes[scenario]}, 'Wrong fixed scenario/test node'
        row = values[0]; initial = baselines[test_id(row)]['cases'][case]
        ids = initial['step_ids']; expected = literal['changes'][scenario][case]
        ea = {ids[adapter] for adapter in expected['affected']}
        ep = {ids[adapter] for adapter in expected['preserved']}
        aa = set(row['actual_affected']); ap = set(row['actual_preserved'])
        assert ea == set(row['expected_affected']) and ep == set(row['expected_preserved'])
        assert len(aa) == len(row['actual_affected']) and len(ap) == len(row['actual_preserved'])
        assert ea.isdisjoint(ep) and ea | ep == set(ids.values())
        assert aa.isdisjoint(ap) and aa | ap == set(ids.values()), 'Actual partition must cover only this Case once'
        fn, fp, pd = len(ea - aa), len(aa - ea), len(ep ^ ap)
        assert (fn, fp, pd) == (row['missed_count'], row['wrong_count'], row['wrong_preserved_count'])
        unknown = literal['changes'][scenario].get('intentional_unknown', False)
        assert row['intentional_unknown'] == unknown
        observations.append(dict(scenario=scenario, case=case, case_id=initial['case_id'],
            step_ids=ids, physical_observations=len(values), expected_affected=sorted(ea), actual_affected=sorted(aa),
            expected_preserved=sorted(ep), actual_preserved=sorted(ap), missed_impact=fn, false_impact=fp,
            preserved_symmetric_difference=pd, intentional_unknown=unknown))
    def aggregate(selected):
        return dict(unique_scenario_case_observations=len(selected),
            physical_observations=sum(r['physical_observations'] for r in selected),
            expected_affected_steps=sum(len(r['expected_affected']) for r in selected),
            expected_preserved_steps=sum(len(r['expected_preserved']) for r in selected),
            actual_affected_steps=sum(len(r['actual_affected']) for r in selected),
            missed_impact=sum(r['missed_impact'] for r in selected),
            false_impact=sum(r['false_impact'] for r in selected),
            preserved_symmetric_difference=sum(r['preserved_symmetric_difference'] for r in selected))
    action = [r for r in rows['at-results'] if r['scenario'] == 'selected_capacity_actual_rule_and_current_rebind']
    assert len(action) == 2 and {r['case'] for r in action} == {'A', 'B'}
    assert all(test_id(r) == nodes['selected_resource_capacity_and_revision'] for r in action)
    assert all(r['result'] == 'PASS' and r['old_verify_status'] == 409 and r['p1_lock_exact']
               and r['all_six_local_outputs_verified'] and r['original_first_delivery_approval_preserved']
               and r['replacement_formal_approval'] == 'NOT_IMPLEMENTED' for r in action)
    return dict(source_sha=source_sha, run_id=run_id, whole_AT25='NOT_RUN',
        recompute_source_sha256=digest(Path(__file__)),
        scope='LINUX_SYNTHETIC_HTTP_ASGI_IMPACT_IDENTIFICATION_AND_EXPLICIT_CAPACITY_RECHECK',
        sample_unit='scenario x Case; fresh independent pair per scenario; repeated reads deduplicated',
        known=aggregate([r for r in observations if not r['intentional_unknown']]),
        unknown_separate=aggregate([r for r in observations if r['intentional_unknown']]),
        known_partition_only=aggregate([r for r in observations if not r['intentional_unknown'] and r['scenario'] != 'selected_resource_capacity_and_revision']),
        selected_capacity=aggregate([r for r in observations if r['scenario'] == 'selected_resource_capacity_and_revision']),
        actual_text_modification_missed_or_wrong_rate='NOT_MEASURED: impact errors are not text-edit errors',
        metric_overlap='FN/FP/preserved difference are separate diagnostics; never add them as total errors',
        action_evidence_limit='Each P2 refusal asserted in original source loop; action record old_verify_status reuses final loop variable, not separate per-Case HTTP receipt',
        action_layer=action, observations=observations,
        inputs_sha256={kind: digest(path) for kind, path in paths.items()} | {'literal_oracle': digest(literal_path)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--literal', type=Path, required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--source-sha', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = recompute(args.runtime, args.literal, args.run_id, args.source_sha)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('known', 'unknown_separate')}))
