"""Frozen literal fixture and initial-profile checks, without product imports."""
from pathlib import Path
import hashlib
import json
import ast

ROOT = Path('/workspace/ParkWeave')
OUT = ROOT / '.runtime/at24-27-audit'
SHA = '5a7eee826564426a4c36607ac038bd61e00665d7'


def load(path):
    return json.loads((ROOT / path).read_text())


def main():
    oracle = load('docs/F2/AT24-27FixedOracles-20261015.json')
    fixture = load('tests/fixtures/at24_27_literal_oracle.json')
    cases = {r['id']: r for r in oracle['cases']}
    aliases = {
        'A_material_content': 'C25_MATERIAL_A',
        'owner_optional_resource_capacity': 'C25_OPTIONAL_CAPACITY',
        'selected_resource_capacity_and_revision': 'C25_SELECTED_CAPACITY',
        'shared_catalog_source_contract': 'C25_CATALOG_CONTRACT',
        'shared_catalog_unavailable_unknown': 'C25_UNKNOWN_REAL_BOUND',
    }
    assert fixture['expectations_derived_from_product_impact_code'] is False
    for scenario, case_id in aliases.items():
        for label in ['A', 'B']:
            for field in ['affected', 'preserved']:
                assert fixture['changes'][scenario][label][field] == cases[case_id][label][field]
    test = ROOT / 'tests/test_at24_27_change_batch_independent.py'
    tree = ast.parse(test.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'assert_literal_partition')
    source = ast.get_source_segment(test.read_text(), fn)
    # The expected answer comes from literal JSON; only step UUID substitution
    # follows. Product impact sets are used solely as the actual value.
    assert "answer = ORACLE['changes'][scenario][label]" in source
    assert "want_a = {ids[x] for x in answer['affected']}" in source
    assert "want_p = {ids[x] for x in answer['preserved']}" in source
    assert 'got_a == want_a and got_p == want_p' in source
    traces = load('.runtime/at24-27-independent/independent-v3-own-traces.json')['records']
    def rows(prefix):
        found = [r for r in traces if Path(r['path']).name.startswith(prefix)]
        assert len(found) == 1
        return [json.loads(line) for line in (ROOT / found[0]['path']).read_text().splitlines()]
    baselines = rows('baseline-')
    assert len(baselines) == 37
    required = oracle['fixed_required_goals_literal']
    for row in baselines:
        assert row['source_sha'] == SHA and row['scope'] == 'FIXED_TWO_CASE_REAL_SIX_GOAL_INITIAL_STATE'
        assert row['same_owner'] and row['same_org'] and row['same_park']
        assert set(row['cases']) == {'A', 'B'} and len(row['common_resource_manifests']) == 2
        for case in row['cases'].values():
            assert case['required_goals'] == required and len(required) == 6
            assert case['states'] == {p: 'VERIFIED' for p in ['P1', 'P2', 'P3', 'P4', 'P5']}
            assert set(case['step_ids']) == set(case['states']) and len(set(case['step_ids'].values())) == 5
        assert row['cases']['A']['case_id'] != row['cases']['B']['case_id']
        assert row['cases']['A']['plan_id'] != row['cases']['B']['plan_id']
    observations = rows('read-observations-')
    assert len(observations) == 5
    assert all(r['source_sha'] == SHA and not r['remaining_changed_tables'] for r in observations)
    changed = [(r['mode'], len(r['original_observe_true_invalidation_only'])) for r in observations if r['original_observe_true_invalidation_only']]
    assert changed == [('late_403', 3)]
    result = dict(status='PASS', source_sha=SHA, literal_answers_match_independent_design=True,
        literal_scenario_aliases=aliases, baseline_profile_records=37, cases_per_record=2,
        original_required_goals=required, original_steps=['P1', 'P2', 'P3', 'P4', 'P5'],
        every_case_original_steps_verified=True, scenarios_reconstruct_same_profile_not_one_shared_mutating_history=True,
        original_read_observation_records=5, observation_records_with_invalidated_change=1,
        changed_mode='late_403', original_observed_invalidated_objects=3,
        observation_records_with_no_change=4, remaining_business_or_history_changed_tables=0,
        no_product_algorithm_used_for_expected_partition=True,
        test_source_sha256=hashlib.sha256(test.read_bytes()).hexdigest())
    (OUT / 'initial-literal-and-observation-independent.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if not isinstance(v, (list, dict))}))


if __name__ == '__main__':
    main()
