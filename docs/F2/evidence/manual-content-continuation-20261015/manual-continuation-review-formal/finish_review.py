"""Independent frozen-source and result closeout; writes only this review dir."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import ast
import hashlib
import json
import stat
import subprocess

ROOT = Path('/workspace/ParkWeave')
OUT = ROOT / '.runtime/manual-continuation-review-formal'
SHA = 'ef16f7c380a3d25a55bf42b208d3e579fcb0e068'
BASE = '7cfb1336bbfbf856c37808a66ec6f00067b6f966'


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def functions(raw):
    return {node.name: node for node in ast.parse(raw).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


freeze = json.loads((ROOT / '.runtime/manual-continuation-root/freeze-v1.json').read_text())
assert git('rev-parse', 'HEAD').decode().strip() == SHA == freeze['source_sha']
assert not git('status', '--porcelain', '--untracked-files=no')
entries = []
for row in git('ls-files', '-s', '-z').split(b'\0'):
    if not row:
        continue
    head, raw_path = row.split(b'\t', 1)
    mode, blob, stage = head.decode().split()
    assert stage == '0' and mode in {'100644', '100755'}
    entries.append((raw_path.decode(), blob))
assert len(entries) == 13252 and len(freeze['source_paths']) == 608
assert {path for path, _ in entries} == set(freeze['all_tracked_sha256'])
hashes = {}
git_blob_drift = []
for path, blob in entries:
    raw = (ROOT / path).read_bytes()
    hashes[path] = sha(raw)
    if hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() != blob:
        git_blob_drift.append(path)
assert not git_blob_drift
assert hashes == freeze['all_tracked_sha256']
assert {path: hashes[path] for path in freeze['source_paths']} == freeze['source_paths']
dump('final-source-verification.json', dict(status='PASS', source_sha=SHA,
    utc=datetime.now(timezone.utc).isoformat(), source_count=608, all_tracked_count=13252,
    all_tracked_hashes=hashes, source_paths=freeze['source_paths'], git_blob_drift=git_blob_drift,
    freeze_all_tracked_equal=True, freeze_source_equal=True, tracked_clean=True,
    untracked_runtime_evidence_is_outside_frozen_set=True))

old = json.loads((OUT / 'prior1048-originals-before.json').read_text())
assert len(old['records']) == 1048
after = {}
for path, expected in old['records'].items():
    data = (ROOT / path).read_bytes()
    after[path] = dict(bytes=len(data), sha256=sha(data))
    assert after[path] == expected, path
dump('prior1048-originals-after.json', dict(status='PASS_ALL_1048_ORIGINAL_BYTES_UNCHANGED',
    source_sha=SHA, utc=datetime.now(timezone.utc).isoformat(), records=after,
    exact_previous_index_and_before_equal=True, originals_modified=False))

windows = []
for prefix, expected in [('freeze-ef16f7c-extra', 404), ('freeze-ef16f7c-probes', 6),
                         ('freeze-ef16f7c-lock-budget', 4)]:
    result = json.loads((OUT / (prefix + '.json')).read_text())
    assert result['source_sha'] == result['after_source_sha'] == SHA
    assert result['exit_code'] == 0 and result['counts'] == dict(PASS=expected, FAIL=0, ERROR=0, SKIP=0)
    assert not result['source_drift'] and not result['all_tracked_drift'] and not result['tracked_status_after']
    assert result['collection_junit_exact_match'] and result['unique_junit_nodes'] and result['expected_module_set_equal']
    before = json.loads((OUT / (prefix + '-before.json')).read_text())['hashes']
    after_window = json.loads((OUT / (prefix + '-after.json')).read_text())['hashes']
    assert before == after_window == freeze['all_tracked_sha256']
    windows.append(dict(prefix=prefix, counts=result['counts'], module_count=len(result['modules']),
        elapsed_seconds=result['elapsed_seconds'], junit_seconds=result['junit_seconds'],
        actual_source_sha=SHA, source_count=608, all_tracked_count=13252,
        collection_and_JUnit_exact_and_unique=True, source_and_full_tracked_zero_drift=True,
        result_sha256=sha((OUT / (prefix + '.json')).read_bytes())))

ui = json.loads((OUT / 'frozen-ui-probe-result.json').read_text())
assert ui['checks'] == 4 and ui['web_sha256'] == hashes['src/parkweave/web.html']
assert all(r['generic_HTTP409_retains_exact_opaque_handle'] and r['NOT_OBSERVED_retains_same_handle']
    and not r['automatic_rePOST'] and not r['body_or_reason_or_token_in_handle'] for r in ui['results'])
hist = [json.loads(line) for line in (OUT / 'probes/freeze-ef16f7c-probes-history-observed.jsonl').read_text().splitlines()]
assert len(hist) == 2 and sum(row['damaged_cases'] for row in hist) == 48
assert all(row['all_refused'] and row['no_damaged_history_written_to_PG'] and row['product_business_rows_unchanged'] for row in hist)

baseline_note = functions(git('show', BASE + ':src/parkweave/plan_source_conflicts.py'))
current_note = functions((ROOT / 'src/parkweave/plan_source_conflicts.py').read_bytes())
old_validator = baseline_note['validate_embedded_event']
new_validator = current_note['validate_embedded_event_v1']
new_validator.name = 'validate_embedded_event'
assert ast.dump(old_validator, include_attributes=False) == ast.dump(new_validator, include_attributes=False)
old_service = functions(git('show', BASE + ':src/parkweave/service_case_steps.py'))
new_service = functions((ROOT / 'src/parkweave/service_case_steps.py').read_bytes())
helpers = ['_adopt_request', '_initial_adoption_proof', '_adoption_connection', 'adopt', 'command',
           '_context', '_binding', '_supported']
assert all(ast.dump(old_service[name], include_attributes=False) == ast.dump(new_service[name], include_attributes=False)
    for name in helpers)
for path in ['src/parkweave/typed_source_impact.py', 'src/parkweave/source_change_adoption.py']:
    assert git('show', BASE + ':' + path) == (ROOT / path).read_bytes()
old_plugin = (ROOT / '.runtime/at24-27-common-clear-regression/common_clear_capture.py').read_text()
new_plugin = (ROOT / '.runtime/manual-continuation-common-retry/common_clear_capture.py').read_text()
assert old_plugin.replace('.runtime/at24-27-common-clear-regression', '.runtime/manual-continuation-common-retry') == new_plugin
dump('common-retry-plugin-review.json', dict(status='PASS_ARTIFACT_DESTINATION_ONLY', source_sha=SHA,
    old_sha256=sha(old_plugin.encode()), new_sha256=sha(new_plugin.encode()),
    exact_transform='One literal artifact destination changed; same 16 exact legacy output prefixes.',
    scope='Process-local Path.open/Path.mkdir for fixed test artifact prefixes, OUT relocation, token registration and collection only.',
    business_PG_or_HTTP_or_auth_or_drivers_or_assertions_modified=False,
    old_1048_raw_originals_unchanged=True,
    root_first_common_failure='Preserved; not replaced by retry or counted as a passing window.',
    root_common_retry_result='NOT_EVALUATED_HERE; parent owns complete18 retry and result validation.'))

private_records = []
for path in sorted(OUT.rglob('*.private.json')):
    assert stat.S_IMODE(path.stat().st_mode) == 0o600, path
    raw = path.read_bytes()
    private_records.append(dict(path=str(path.relative_to(ROOT)), bytes=len(raw), sha256=sha(raw), mode='0600', publish=False))
dump('private-registry-manifest.json', dict(status='PRIVATE_VALUES_NOT_DISCLOSED', records=private_records,
    values_printed=False, public_registry_payload_allowed=False))

report = dict(status='PASS_FROZEN_SOURCE_AND_THIS_REVIEW_SCOPE', source_sha=SHA, baseline_sha=BASE,
    utc=datetime.now(timezone.utc).isoformat(), blockers=[],
    formal_complete_module_window=windows[0], supplemental_windows_with_actual_API_PG_setup=windows[1:],
    unit_separation=dict(complete_modules=14, complete_module_pytest_items=404,
        supplemental_pytest_items=10, actual_API_PG_seam_lock_budget_items=8, final_unknown_actual_API_PG_items=4,
        history_fixture_pytest_items=2, in_memory_history_refusal_checks=48,
        downstream_lock_and_real_64_128_budget_items=4, extracted_function_VM_checks=4,
        not_combined_as_full_module_or_AT_score=True),
    entire_frozen_source_and_tracked_and_Git_blob_equal=True,
    previous_1048_raw_originals_unchanged=True,
    original_v1_history_validator_AST_identical_after_rename=True,
    original_ADOPT_VERIFY_auth_scope_helpers_AST_unchanged=helpers,
    original_source_impact_and_adoption_modules_byte_unchanged=True,
    conclusions=[
        'Commands retain strict schema1 fields/fingerprint shape; two new actions use proof.version2 and preview_basis.schema2. Old proof.version1 dispatch remains frozen.',
        'B is the complete captured two-slot actual PG evidence package with exact original row epochs; M is exact current manual text; S is current actual material source. Unprovable B, UNKNOWN or stale source refuses new continuation.',
        'Frozen line_coverage_v1 uses exact nonempty splitlines and duplicate multiplicity, bounded 1..128. This only checks carriage of source text, never facts, grants, qualification or completed obligations.',
        'KEEP preserves M; MERGE requires complete continuous M and all exact S lines. Origin stays MANUAL, verified_package_sha256 remains None; no automatic ADOPT, VERIFY, unlock or new grant.',
        'Any subsequent EDIT after a new continuation invalidates that decision even if all conditions remain. Prior ACCEPT_SOURCE then ordinary EDIT retains old schema1 coordination-note semantics.',
        'Shared adoption guard protects source-preview and both original same-plan local ADOPT paths. New P3 lock probe proves a note decision may record while downstream locks remain; both ADOPT paths still require original UNLOCK.',
        'Original plan/ledger transaction, exact bidirectional history links, final source reread and current auth remain. Final UNKNOWN actual source changes now fail409 without note/ledger/business writes and cold original key remains NOT_OBSERVED.',
        'Actual new KEEP uses original event reservation: original business plus five VERIFY finishes exactly64; revision58 with one event short rejects; ledger127 permits one continuation at128 and original ADOPT uses no extra ledger slot.',
        'UI keeps opaque original key only, no token/text/reason; definitive rejection proof can release only matching lease. Generic409, unknown transport and NOT_OBSERVED retain the handle. Context/generation/draft guards and original tracked-write gates remain.',
        'Nonlocal replacement or template application carrying notes remains conservatively refused until controlled cross-plan history carry exists.'
    ],
    caveats=[
        'Linux synthetic owned PostgreSQL only. Full original HTML/actual HTTP flow evidence belongs to independent agent and is not replaced by extracted-function VM checks.',
        '48 in-memory history mutations are checks inside two pytest fixtures; no damaged history is written to PG. This does not claim protection from a malicious trusted administrator coherently rewriting all history and checksums.',
        '46 immutable designs are not a test denominator. This agent records partial/property coverage and NOT_RUN in design-trace-review-only.json; parent must combine actual completed trace without upgrading unexecuted variants.',
        'This PASS is independent frozen-source and this review scope, not overall delivery/archival gate. Other full windows and the future primary archive must be verified separately.',
        'Windows, real browser, formal business AT, real model, production and new CI remain NOT_RUN.'
    ],
    historical_failures_preserved=[
        dict(path='.runtime/manual-continuation-review/seam-probes/seam-v1-red.xml',
            result='2FAIL', cause='Actual pre-fix final basis None produced HTTP500; formal frozen4 actual seam tests now409.'),
        dict(path='.runtime/manual-continuation-review/preliminary-v1',
            result='WIP branch findings', cause='Old ACCEPT then EDIT compatibility and basis None identified; both corrected before freeze.'),
        dict(path='.runtime/manual-continuation-review/preliminary-v2/ui-probe.log',
            result='Runtime harness ReferenceError', cause='First extracted-function runner omitted new helper; old log preserved, fresh frozen helper closure passes4 checks.'),
        dict(path='.runtime/manual-continuation-root/html-preview-render-repair.json',
            result='Pre-freeze actual HTML product failure', cause='Accidental undefined box render inserted in original opportunity preview; removed before freeze.'),
        dict(path='.runtime/manual-continuation-root/common-artifact-retry.json',
            result='First root common window artifact runner failure', cause='Missing legacy output remapping. Exact old special capture relocated, no source/test/driver/assert change. Parent owns retry result.')
    ],
    source_files_modified_by_reviewer=[], Git_writes_by_reviewer=False,
    archive_independent_reconstruction='NOT_RUN_ARCHIVE_NOT_YET_GENERATED')
dump('frozen-source-independent-review.json', report)
print(json.dumps(dict(status=report['status'], source_sha=SHA, complete_modules=14,
    complete_module_pytest_items=404, supplemental_pytest_items=10,
    actual_API_PG_seam_lock_budget_items=8, in_memory_history_fixtures=2, VM_checks=4,
    source_paths=608, all_tracked_paths=13252, old_raw_originals=1048, blockers=[])))
