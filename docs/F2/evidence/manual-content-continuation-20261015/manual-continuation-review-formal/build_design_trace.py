"""Map immutable design intent to this reviewer's real execution, conservatively."""
from collections import Counter
from pathlib import Path
import hashlib
import json

ROOT = Path('/workspace/ParkWeave')
OUT = ROOT / '.runtime/manual-continuation-review-formal'
ORACLE = ROOT / '.runtime/manual-continuation-review/immutable-oracle-v1/literal-oracle-v1.json'
expected_hash = '9455b88d9c83771b9e627094aa5f249b6e0bc434c4bbe862561e9cc62b9221e5'
assert hashlib.sha256(ORACLE.read_bytes()).hexdigest() == expected_hash
design = json.loads(ORACLE.read_text())
nodes = []
for prefix in ['freeze-ef16f7c-extra', 'freeze-ef16f7c-probes', 'freeze-ef16f7c-lock-budget']:
    value = json.loads((OUT / (prefix + '.json')).read_text())
    assert value['exit_code'] == 0 and value['counts']['FAIL'] == value['counts']['ERROR'] == 0
    nodes += value['collected_nodes']


def matching(*functions):
    result = [node for node in nodes if any(('::' + name) in node for name in functions)]
    assert result, functions
    return result


# These are hand-written mappings from design premises, not product-generated answers.
spec = {
0: ('OLD_ACTION_REGRESSION_ONLY', ['test_keep_defer_unlock_accept_changes_only_note_and_real_source_adopt_still_required'],
    'Actual old KEEP leaves note and lock exact and refuses original local adoption; new-action contrast is not an additional direct assertion in this node.'),
1: ('OLD_ACTION_REGRESSION_ONLY', ['test_keep_defer_unlock_accept_changes_only_note_and_real_source_adopt_still_required'],
    'Actual old DEFER remains pending. Uses synthetic source wording rather than immutable Chinese literal.'),
3: ('PARTIAL_PROPERTY_EXECUTED', ['test_keep_requires_exact_conditions_then_edit_requires_explicit_reconfirmation'],
    'Actual new KEEP missing exact source lines rejects409; uses independent repeated/space-sensitive synthetic source, not exact MC03 text.'),
4: ('PARTIAL_PROPERTY_EXECUTED', ['test_keep_requires_exact_conditions_then_edit_requires_explicit_reconfirmation',
    'test_downstream_P3_lock_survives_continue_and_refuses_both_adopt_routes'],
    'Actual successful KEEP preserves M and MANUAL origin, no automatic ADOPT; distinct synthetic M/S.'),
5: ('PARTIAL_PROPERTY_EXECUTED', ['test_real_append_merge_preserves_manual_and_allows_only_original_source_adopt'],
    'Actual MERGE M+newline+S retains continuous M, MANUAL origin and no verified package. Does not use immutable literal MC string.'),
9: ('PARTIAL_PROPERTY_EXECUTED', ['test_keep_requires_exact_conditions_then_edit_requires_explicit_reconfirmation'],
    'Actual old KEEP then EDIT appends S, followed by fresh explicit KEEP continuation; edit alone cannot rebind.'),
10: ('PARTIAL_VARIANTS_EXECUTED', ['test_keep_requires_exact_conditions_then_edit_requires_explicit_reconfirmation'],
    'New KEEP then EDIT retaining all conditions or deleting conditions blocks adoption and permits fresh decision. Same-text EDIT and post-MERGE variants NOT_RUN by this agent.'),
11: ('PARTIAL_VARIANTS_EXECUTED', ['test_keep_requires_exact_conditions_then_edit_requires_explicit_reconfirmation'],
    'Actual P1 locked preview disables both new actions; original UNLOCK enables. New-action locked POST rejection not directly exercised here.'),
12: ('SCENARIO_EXECUTED_NEW_KEEP', ['test_downstream_P3_lock_survives_continue_and_refuses_both_adopt_routes'],
    'Actual complete six-goal plan: P1 unlocked/P3 locked. New KEEP records without unlocking, both original ADOPT entries409 and lock exact; original UNLOCK then201. MERGE variant NOT_RUN.'),
13: ('PARTIAL_OLD_NOTE_REGRESSION', ['test_unchanged_source_manual_text_difference_does_not_block_capacity_patch'],
    'Actual source anchor unchanged, capacity-only patch succeeds despite ordinary note differing from source. No two-Case/preserved-P1-lock literal assertion in this review window.'),
14: ('PARTIAL_VARIANTS_EXECUTED', ['test_missing_old_second_slot_refuses_new_continuation_without_rewriting_history'],
    'Owned historical second slot actually changed; no exact two-slot baseline proof, both new actions disabled. Other B absence shapes NOT_RUN.'),
15: ('PARTIAL_VARIANTS_EXECUTED', ['test_final_source_read_unknown_rolls_back_and_retains_original_key',
    'test_actual_owned_catalog_change_before_final_read_is_409_not_500'],
    'Both new actions final UNKNOWN basis via controlled reader Conflict and actual separately committed PG catalog change;409/zero business-plan-ledger writes/cold NOT_OBSERVED. Material query overflow NOT_RUN.'),
19: ('PARTIAL_VARIANTS_EXECUTED', ['test_historical_source_row_aba_stales_only_new_exact_continuation_preview'],
    'Actual historical B row A-B-A increments xmin; old new MERGE basis409 even ordinary old preview hash same. Current S ABA is not this node.'),
27: ('PARTIAL_OLD_ACTION_REGRESSION', ['test_note_key_idempotency_lost_response_cold_read_and_parameter_conflict'],
    'Original note action same-key exact receipt and no duplicate event. New-action exact POST replay is not directly asserted by this reviewer.'),
28: ('PARTIAL_OLD_ACTION_REGRESSION', ['test_note_key_idempotency_lost_response_cold_read_and_parameter_conflict'],
    'Original note parameter conflict; not every new-action field/parameter variant.'),
30: ('LAYERED_API_AND_SYNTHETIC_VM_ONLY', ['test_final_source_read_unknown_rolls_back_and_retains_original_key',
    'test_actual_owned_catalog_change_before_final_read_is_409_not_500'],
    'Real two-action failed-write cold GET is NOT_OBSERVED, and separate four extracted-function VM checks retain exact opaque handle. No full HTML/HTTP cold NOT_OBSERVED transport chain claimed here.'),
32: ('PRE_WRITE_FINAL_REFUSAL_ONLY', ['test_final_source_read_unknown_rolls_back_and_retains_original_key',
    'test_actual_owned_catalog_change_before_final_read_is_409_not_500'],
    'Actual final source reread refusal causes no plan/ledger/business writes. Injected failure between append/update/commit NOT_RUN; this is not equivalent to mid-persistence rollback.'),
34: ('PARTIAL_NEW_KEEP_BUSINESS_CLOSURE', ['test_new_keep_continuation_actual_business_and_VERIFY_finish_at_revision_64'],
    'Actual new KEEP→ADOPT→original REVIEW/CONFIRM/resources/dispatch/receipt/local REVALIDATE/five VERIFY and six goals. Worklist read and second Case isolation are not this node.'),
35: ('SCENARIO_EXECUTED_NEW_KEEP', ['test_new_keep_continuation_actual_business_and_VERIFY_finish_at_revision_64',
    'test_new_keep_continuation_refuses_one_event_short_plan_budget',
    'test_new_keep_uses_128th_ledger_slot_and_original_ADOPT_needs_no_extra_slot'],
    'Actual original commands fill54; new continue58→ADOPT59→business plus five VERIFY ends64. At58 one event short refuses409, no writes. Real NO_CHANGE REFRESH fills127, new KEEP128; ADOPT does not need slot129. Next command expected128 gets original typed422, explicitly not business-validator proof. MERGE variant NOT_RUN.'),
36: ('PARTIAL_COMPATIBILITY_REGRESSION', ['test_original_source_accept_then_plain_edit_retains_schema_one_behavior',
    'test_original_edit_note_is_real_exact_text_and_old_source_events_unchanged'],
    'Actual old ACCEPT→EDIT keeps schema1 coordination behavior; original event fingerprints remain. Static v1 validator AST identical after rename; no claim every old serialized fixture was rerun.'),
37: ('PARTIAL_OLD_NOTE_ONLY', ['test_binding_replacement_cannot_silently_drop_current_note',
    'test_template_apply_cannot_reinterpret_or_drop_annotation_history'],
    'Existing note-bearing nonlocal replacement/template apply refusals run unchanged. Direct new proof.version2 post-continuation replacement/apply variant NOT_RUN here.'),
38: ('PARTIAL_LITERAL_RULE_VARIANTS', ['test_frozen_line_carriage_is_exact_bounded_and_counts_duplicates',
    'test_keep_requires_exact_conditions_then_edit_requires_explicit_reconfirmation'],
    'Literal duplicate counts tested independently in pure fixtures and actual new-action path; source wording differs immutable SR.'),
39: ('PARTIAL_LITERAL_RULE_VARIANTS', ['test_frozen_line_carriage_is_exact_bounded_and_counts_duplicates',
    'test_real_append_merge_preserves_manual_and_allows_only_original_source_adopt'],
    'Pure exact leading-space mismatch and actual preservation of manual leading/trailing whitespace; not all source outer-whitespace HTTP input variants.'),
40: ('PARTIAL_PURE_BOUNDARY_ONLY', ['test_frozen_line_carriage_is_exact_bounded_and_counts_duplicates'],
    'Pure frozen rule has128 known/129 unknown/blank-only unknown. Actual HTTP128/129 source boundary belongs to independent agent, not claimed here.'),
41: ('PARTIAL_PURE_LINE_ENDING_ONLY', ['test_frozen_line_carriage_is_exact_bounded_and_counts_duplicates'],
    'Pure CRLF/LF and case-sensitive variants. Explicit NFC/NFD variant NOT_RUN.'),
43: ('PARTIAL_ACTUAL_CATALOG_UNKNOWN', ['test_actual_catalog_becomes_unknown_at_final_reread_refuses_without_new_event',
    'test_actual_owned_catalog_change_before_final_read_is_409_not_500'],
    'Actual registered catalog kind UNKNOWN final reread, both new actions409. Unsupported graph/compiler schema new-action variant NOT_RUN.'),
44: ('PARTIAL_TWO_SLOT_HISTORY_VARIANTS', ['test_missing_old_second_slot_refuses_new_continuation_without_rewriting_history',
    'test_rehashed_duplicate_slot_history_is_rejected_without_server_error',
    'test_actual_receipt_v2_history_refuses_literal_damage_matrix'],
    'Actual captured second slot damage disables new continuation; old duplicate-slot proof refusal and new v2 in-memory epoch slot/link damage refuse. Current second-slot id/version/kind/label permutation set NOT_RUN.'),
45: ('PARTIAL_NEW_KEEP_IDENTITY_HISTORY', ['test_downstream_P3_lock_survives_continue_and_refuses_both_adopt_routes',
    'test_new_keep_continuation_actual_business_and_VERIFY_finish_at_revision_64',
    'test_actual_receipt_v2_history_refuses_literal_damage_matrix'],
    'Actual six-goal/step UUID/M and54-event prefix checks plus v2 success receipt history; second Case isolation, all old reservations and worklist invariants belong to separate independent chain.')
}
rows = []
for case in design['cases']:
    number = int(case['id'][2:4])
    entry = dict(id=case['id'], immutable_expected_decision=case['expected_decision'],
        immutable_oracle_sha256=expected_hash, exact_immutable_text_fixture_executed_by_this_agent=False,
        other_agent_evidence_counted_here=False)
    if number in spec:
        status, names, scope = spec[number]
        entry.update(execution_status=status, actual_PASS_nodes=matching(*names), scope=scope)
        if number == 30:
            entry['supplemental_artifact'] = 'frozen-ui-probe-result.json'
    else:
        entry.update(execution_status='NOT_RUN_BY_THIS_AGENT', actual_PASS_nodes=[],
            scope='No direct new-action execution of this complete design scenario in this reviewer window. Do not infer execution from static review or older action tests.')
    rows.append(entry)
assert len(rows) == 46
record = dict(status='TRACE_ONLY_NOT_GLOBAL_DESIGN_SIGNOFF', source_sha='ef16f7c380a3d25a55bf42b208d3e579fcb0e068',
    design_count=46, design_count_is_not_pytest_or_AT_denominator=True,
    oracle_sha256=expected_hash, mappings=rows,
    status_counts=dict(Counter(row['execution_status'] for row in rows)),
    other_agent_final_trace='NOT_IMPORTED; parent must separately validate completed raw collection/JUnit and exact design fixtures.',
    all_46_executed=False)
(OUT / 'design-trace-review-only.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(status=record['status'], mappings=len(rows), status_counts=record['status_counts'])))
