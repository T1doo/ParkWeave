"""Small WIP guard probes, not API/PG/history-proof or formal test results."""
from pathlib import Path
from copy import deepcopy
import hashlib
import importlib.util
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
name = 'parkweave._manual_continuation_preliminary_v2'
spec = importlib.util.spec_from_file_location(name, HERE / 'private-plan_source_conflicts.py')
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)

plan_id = '11111111-1111-4111-8111-111111111111'
step_id = '22222222-2222-4222-8222-222222222222'
rebased_id = '33333333-3333-4333-8333-333333333333'
edit_id = '44444444-4444-4444-8444-444444444444'
outline = dict(id='55555555-5555-4555-8555-555555555555', slot='material_outline', version=2,
               text='Literal source requirement', source_kind='USER_STATEMENT', source_label='synthetic v2',
               source_sha256=module.digest('Literal source requirement'), authenticity='UNVERIFIED')
summary = dict(id='66666666-6666-4666-8666-666666666666', slot='need_summary', version=1,
               text='Synthetic need', source_kind='USER_STATEMENT', source_label='synthetic v1',
               source_sha256=module.digest('Synthetic need'), authenticity='UNVERIFIED')
# Only the actual-source reader is isolated, with complete valid material rows.
# Actual _note validation, source-ref comparison and blocker logic execute.
module._materials = lambda connection, parent: deepcopy([outline, summary])


def run(label, previous_action, edited, text, expected):
    event_id = edit_id if edited else rebased_id
    note = dict(version=1, revision=2 if edited else 1, text=text,
                text_sha256=module.digest(text), origin='MANUAL', source_ref=module.source_ref(outline),
                source_package=[outline, summary], verified_package_sha256=None,
                event_id=event_id, plan_id=plan_id, step_id=step_id)
    events = []
    if previous_action:
        events.append(dict(action=previous_action, id=rebased_id, plan_note=dict(after_note=deepcopy(note))))
    if edited:
        events.append(dict(action='EDIT_NOTE', id=edit_id))
    actual = module.adoption_blockers(None, {}, dict(id=plan_id, owner_amendments={step_id: note}, events=events))
    return dict(case=label, expected=expected, actual=actual, matches=expected == actual)


results = [
    run('v1_ACCEPT_then_EDIT_all_conditions_carried_legacy', 'ACCEPT_SOURCE', True,
        'Literal source requirement\nManual note', []),
    run('new_CONTINUE_unchanged_note', 'KEEP_AND_CONTINUE', False,
        'Literal source requirement\nManual note', []),
    run('new_CONTINUE_then_EDIT_conditions_still_present', 'KEEP_AND_CONTINUE', True,
        'Literal source requirement\nManual note', ['OWNER_NOTE_CONTENT_EDIT_REQUIRES_RECONFIRMATION']),
    run('new_MERGE_then_EDIT_deleted_condition', 'MERGE_NOTE', True,
        'Manual note', ['OWNER_NOTE_CONTENT_EDIT_REQUIRES_RECONFIRMATION', 'OWNER_NOTE_SOURCE_LINES_NOT_CARRIED']),
    run('legacy_manual_note_same_source_no_rebase_event', None, True, 'Manual note', []),
]
try:
    module.continuation_basis(None, {}, None)
except Exception as error:
    final_read = dict(case='final_read_legitimate_unavailable_basis',
                      actual_exception=type(error).__name__, expected_exception='Conflict',
                      matches=isinstance(error, module.Conflict))
else:
    final_read = dict(case='final_read_legitimate_unavailable_basis', actual_exception=None,
                      expected_exception='Conflict', matches=False)
result = dict(status='WIP_FIXED_GUARDS_CHECK_NOT_FORMAL_REGRESSION',
              snapshot_sha256=hashlib.sha256((HERE / 'private-plan_source_conflicts.py').read_bytes()).hexdigest(),
              guard_cases=results, final_read_unavailable_basis=final_read,
              actual_API_PG_or_history_proof_executed=False,
              note_and_material_shapes_actually_validated=True,
              source_reader_isolated_with_complete_synthetic_rows=True,
              product_modules_mutated=False)
(HERE / 'probe-guards-result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
