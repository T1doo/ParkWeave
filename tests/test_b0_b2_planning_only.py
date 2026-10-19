"""One shared owned synthetic initial state, one fixed CLI planning-only pair."""
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from time import perf_counter
from uuid import UUID

import pytest
from parkweave import bounded_planning as bp, controlled_plans as cp
from parkweave import resource_holds, service_selection_candidates as candidates
from parkweave import service_case_steps
from parkweave.service_selection import SelectionError
from parkweave.store import Conflict
from scripts.b0_b2_planning_only import BUDGET, SERVICES, compare, judge
from test_preparation import preparation_fixture
from test_executor_receipts import receipt_fixture
from test_service_capability_catalog_actual import capability_catalog
from test_service_selection_full_chain import selection_full_chain
from test_service_selection_replay_acceptance import replay, new_confirmed_parent, adopt_selection, all_public_rows
from service_release_acceptance_support import authority_snapshot, case_history
from test_case_goal_results import complete as complete_existing_A

ROOT = Path(__file__).resolve().parents[1]


def resource_query(c, parent):
    # Exact registered_dependencies.collections resource projection, before its
    # original hash. Recomputed below against the original manifest both times.
    return c.execute('SELECT r.id,r.revision,r.source,r.capacity,r.buffer_seconds,r.open_from,r.open_until,r.enabled,g.capability,g.active FROM synthetic_resources r JOIN synthetic_resource_grants g ON g.resource_id=r.id WHERE g.principal_id=%s AND g.park_id=%s AND g.org_id=%s AND r.park_id=g.park_id ORDER BY r.id,g.capability LIMIT %s',
        (parent['owner_id'], parent['park_id'], parent['org_id'], 257)).fetchall()


def test_shared_snapshot_fixed_selection_and_two_readonly_planning_arms(replay, tmp_path):
    r = replay
    store, owner, tokens, api = r['f']
    out = tmp_path/'planning-only'
    out.mkdir()
    (out/'private-fixture-sessions.json').write_text(json.dumps(list(tokens.values())))
    started = perf_counter()
    a_parent, _, _, _ = complete_existing_A(r['f'], local=True)
    a_history = case_history(owner, a_parent['preparation_id'])
    assert any(a_history.values())
    parent, _ = new_confirmed_parent(r, 'B0-B2-FIXED-PLANNING')
    adopt_selection(r, parent)  # Common original fixture only, not either arm.
    with owner.connect() as c:
        prior = c.execute('SELECT service_case_plan FROM preparations WHERE id=%s',
                          (parent['preparation_id'],)).fetchone()['service_case_plan']
        assert not prior.get('owner_amendments')
        assert not any(service_case_steps._manual_lock(prior, s) for s in prior['steps'])
        assert [e['action'] for e in prior['events']] == ['ADOPT']
        db_parent = c.execute('SELECT * FROM preparations WHERE id=%s', (parent['preparation_id'],)).fetchone()
        original_binding = candidates.binding(prior['adoption_preview'])
        assert all(str(db_parent[key]) == original_binding[key] for key in ('case_id', 'run_id'))
        assert str(db_parent['id']) == original_binding['preparation_id']
        anchor = dict(plan_id=prior['id'], original_binding=original_binding,
            step_ids={s['adapter_id']: s['id'] for s in prior['steps']}, owner_id=db_parent['owner_id'],
            event={k: prior['events'][0][k] for k in ('id', 'actor_id', 'fingerprint')})
        query_before = resource_query(c, db_parent)
        assert prior['dependency_manifest']['collections']['resources'] == dict(
            known=True, count=len(query_before), sha256=cp._hash(cp._normal(query_before)))
        before = c.execute('SELECT * FROM synthetic_resources WHERE id=ANY(%s) ORDER BY id',
                           ([UUID(x) for x in r['a']['b_resources']],)).fetchall()
        for row in before:
            resource_holds._lock(c, row['id'])
            c.execute('UPDATE synthetic_resources SET revision=revision+1,buffer_seconds=buffer_seconds+60 WHERE id=%s', (row['id'],))
    with r['a']['catalog'].connection() as c:
        principal, current_parent = bp._context(store, c, tokens['fixture-c'], UUID(parent['preparation_id']))
        current = candidates.current(store, c, principal, current_parent, r['a']['catalog'])
        at = c.execute('SELECT clock_timestamp() now').fetchone()['now']
        after = c.execute('SELECT * FROM synthetic_resources WHERE id=ANY(%s) ORDER BY id',
                          ([UUID(x) for x in r['a']['b_resources']],)).fetchall()
        query_after = resource_query(c, current_parent)
        assert current['dependency_collections']['resources'] == dict(
            known=True, count=len(query_after), sha256=cp._hash(cp._normal(query_after)))
    assert current['catalog_snapshot'] == prior['adoption_preview']['catalog_snapshot']
    assert prior['binding']['request_intent'] == current_parent['request_intent']
    frozen_plan = dict(id=prior['id'], required_goals=prior['required_goals'],
        steps=[{k: deepcopy(s[k]) for k in ('id', 'adapter_id', 'depends_on', 'contract')} for s in prior['steps']],
        dependency_manifest=prior['dependency_manifest'], manual_locks=[], owner_amendments=[])
    frozen_plan['identity_anchor'] = anchor
    frozen_plan['identity_anchor_sha256'] = cp._hash(anchor)
    choices = []
    for service_id in SERVICES:
        available = [x for x in current['selection_context']['available_services'] if x['service_id'] == service_id]
        assert len(available) == 1
        choices.append(dict(service_id=service_id, ref=available[0]['ref']))
    value = cp._normal(dict(kind='OWNED_SYNTHETIC_V4_PLANNING_REPLAY',
        source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        as_of=at.isoformat(), catalog=current['catalog_snapshot'], request=current['selection_request'],
        context=current['selection_context'], fixed_choices=choices, existing_plan=frozen_plan,
        current_collections=current['dependency_collections'],
        resource_rows_before=before, resource_rows_after=after,
        resource_query_rows_before=query_before, resource_query_rows_after=query_after,
        identity_map=dict(plan=prior['id'], preparation=parent['preparation_id'],
            case=parent['case_id'], run=parent['run_id'],
            steps={s['adapter_id']: s['id'] for s in prior['steps']}),
        requested_slot=dict(starts_at=(at+timedelta(hours=5)).isoformat(),
                            ends_at=(at+timedelta(hours=6)).isoformat(), quantity=2),
        budget_per_arm=BUDGET, order=['FULL', 'LOCAL']))
    for old, new in zip(value['resource_rows_before'], value['resource_rows_after']):
        assert new == {**old, 'revision': 2, 'buffer_seconds': 360}
    raw = (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()
    input_path = out/'shared-input.json'
    input_path.write_bytes(raw)
    before_rows = all_public_rows(owner)
    authority = authority_snapshot(owner)
    common_seconds = perf_counter()-started
    args = [sys.executable, str(ROOT/'scripts/b0_b2_planning_only.py'),
            '--input', str(input_path), '--sha256', sha256(raw).hexdigest(),
            '--report', str(out/'comparison.json')]
    cli_start = perf_counter()
    process = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=60)
    (out/'cli.stdout').write_text(process.stdout)
    (out/'cli.stderr').write_text(process.stderr)
    (out/'cli-invocation.json').write_text(json.dumps(dict(args=args, exit_code=process.returncode,
        wall_seconds=perf_counter()-cli_start, timeout_seconds=60, automatic_retries=0), indent=2)+'\n')
    assert process.returncode == 0, process.stderr
    result = json.loads((out/'comparison.json').read_text())
    oracle = json.loads((ROOT/'tests/fixtures/b0_b2_planning_only_oracle.json').read_text())
    assert result['candidates_equal'] and result['judgement']['result'] == 'PASS'
    assert result['full_business_application'] == result['local_business_application'] == 'NOT_RUN'
    for arm in ('FULL', 'LOCAL'):
        observed = result['arms'][arm]
        assert observed['required_goals'] == oracle['required_goals']
        assert observed['contract_diff'] == []
        assert observed['witness_diff'] == oracle['should_update']
        assert observed['changed'] == oracle['should_update']
        assert observed['rebuild_returned_nodes'] == observed['final_candidate_nodes'] == 5
        assert observed['component_calls'] == dict(rebuild_selection=1, dependency_inspect=int(arm == 'LOCAL'))
        assert observed['candidate_rows_constructed'] == (5 if arm == 'FULL' else 4)
        assert observed['candidate']['P1'] == result['arms']['FULL']['candidate']['P1']
        assert observed['identity_map'] == value['identity_map']
    assert all_public_rows(owner) == before_rows
    assert authority_snapshot(owner) == authority
    assert case_history(owner, a_parent['preparation_id']) == a_history
    assert input_path.read_bytes() == raw
    # Bounded invalid-input controls; none invokes a business command or model.
    rejected = []
    for label in ('wrong_ref', 'duplicate_choice', 'wrong_binding', 'expired',
                  'unknown_mapping', 'damaged_manifest', 'extra_change',
                  'unrelated_resource', 'duplicate_resource', 'unbound_resource_hash',
                  'coordinated_identity_relabel', 'extra_binding_field'):
        bad = deepcopy(value)
        if label == 'wrong_ref': bad['fixed_choices'][0]['ref']['release_sha256'] = '0'*64
        elif label == 'duplicate_choice': bad['fixed_choices'][1] = deepcopy(bad['fixed_choices'][0])
        elif label == 'wrong_binding': bad['context']['binding']['case_id'] = 'foreign-case'
        elif label == 'expired': bad['as_of'] = '2100-01-01T00:00:00+00:00'
        elif label == 'unknown_mapping':
            group = bad['request']['mapping_states']['resources']
            group[next(iter(group))] = 'UNKNOWN'
        elif label == 'damaged_manifest': bad['existing_plan']['dependency_manifest']['sha256'] = '0'*64
        elif label == 'extra_change': bad['resource_rows_after'][0]['capacity'] = 3
        elif label == 'unrelated_resource':
            for name in ('resource_rows_before', 'resource_rows_after'):
                bad[name][0]['id'] = '00000000-0000-0000-0000-000000000001'
        elif label == 'duplicate_resource':
            for name in ('resource_rows_before', 'resource_rows_after'):
                bad[name][1] = deepcopy(bad[name][0])
        elif label == 'unbound_resource_hash': bad['resource_query_rows_after'][0]['revision'] = 99
        elif label == 'coordinated_identity_relabel':
            bad['context']['binding']['case_id'] = bad['identity_map']['case'] = '00000000-0000-0000-0000-000000000001'
        else: bad['context']['binding']['unverified_extra'] = True
        with pytest.raises((ValueError, SelectionError, Conflict)): compare(bad)
        rejected.append(label)
    score_controls = []
    for label in ('empty_arms', 'one_arm', 'bad_summary', 'bad_equality', 'bad_payload'):
        bad = deepcopy(result)
        if label == 'empty_arms': bad['arms'] = {}
        elif label == 'one_arm': bad['arms'].pop('LOCAL')
        elif label == 'bad_summary': bad['arms']['FULL']['changed'] = []
        elif label == 'bad_equality': bad['candidates_equal'] = False
        else: bad['arms']['FULL']['candidate']['P1']['source_witness'] = {}
        assert judge(bad, oracle, value)['result'] != 'PASS'
        score_controls.append(label)
    proof = dict(scope='OWNED_SYNTHETIC_COMMON_SETUP_THEN_PURE_PLANNING_REPLAY',
        common_setup=dict(original_ADOPT_count=2, new_run_assignment_count=2,
            unrelated_A_guard_goal_count=5, compared_B_goal_count=6,
            initial_fixture_resource_grant_rows=4,
            resource_rows_changed=2, fixture_mock_calls=len(r['calls']),
            fixture_usage_kind='DECLARED_MOCK_INPUT_NOT_ACTUAL_MODEL_TOKENS',
            fixture_declared_usage=[h['producer']['usage'] for h in current_parent['planning_previews']
                                   if h.get('profile') == candidates.PROFILE],
            actual_model_calls=0, measured_post_fixture_preparation_seconds=common_seconds,
            catalog_fixture_setup_seconds=None, participant_human_seconds=None),
        comparison_public_rows_unchanged=True, comparison_authority_unchanged=True,
        nonempty_other_park_A_history_sha256=cp._hash(cp._normal(a_history)),
        full_ADOPT_attempts=0, local_ADOPT_attempts=0, other_case_or_park_rows_unchanged=True,
        input_bytes_unchanged=True, bounded_invalid_controls_rejected=rejected,
        bounded_invalid_score_controls=score_controls,
        business_application='NOT_RUN', real_business=False, Windows=False, browser=False)
    (out/'setup-and-purity-proof.json').write_text(json.dumps(proof, indent=2)+'\n')
