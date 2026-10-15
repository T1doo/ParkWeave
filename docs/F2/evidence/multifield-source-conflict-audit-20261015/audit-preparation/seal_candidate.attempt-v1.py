"""Seal a public independent audit appendix only after every bounded gate passes."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import ast
import hashlib
import json
import re
import shutil
import subprocess

from audit_archive import ROOT, HERE, read_json, identity, source_inventory, known_values, residual_context, source_freeze
from shared_matcher import KnownTokenRedactor


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + '\n')


def inventories(path):
    return {str(p.relative_to(path)): identity(p) for p in path.rglob('*') if p.is_file()}


def main():
    config = read_json(HERE / 'audit-config.json'); assert config['archive_ready'] is True
    current = source_freeze(config)
    freeze = read_json(ROOT / config['freeze'])
    assert all(identity(ROOT / p)['sha256'] == h for p, h in freeze['runner_paths'].items())
    mechanical = read_json(HERE / 'attempt-v1/mechanical-gate.json')
    union = read_json(HERE / 'attempt-v1/independent-window-union.json')
    claims = read_json(HERE / 'claims-v2/independent-claims-audit.json')
    backend = read_json(HERE / 'claims-v2/independent-backend-HTML41.json')
    report = read_json(HERE / 'public-report-and-metadata-audit.json')
    assert mechanical['status'].startswith('PASS') and union['status'].startswith('PASS') and claims['status'].startswith('PASS') and backend['status'].startswith('PASS') and report['status'].startswith('PASS')
    assert all(v['source_sha'] == config['source_sha'] for v in [current, mechanical, union, claims, backend, report])
    primary = ROOT / config['primary']; before_primary = inventories(primary)
    index = read_json(primary / 'index.json'); rows = index['entries']
    assert len(rows) == 1006 and source_inventory(config, set()) == {r['raw_path'] for r in rows}
    assert sum(r['raw_bytes'] for r in rows) == 114760126 and sum(r['export_bytes'] for r in rows) == 114754212
    assert len(before_primary) == 1010
    assert identity(ROOT / report['report']['path'])['sha256'] == report['report']['sha256']
    for row in rows:
        assert identity(ROOT / row['raw_path']) == dict(sha256=row['raw_sha256'], bytes=row['raw_bytes'])
        assert identity(ROOT / row['export_path']) == dict(sha256=row['export_sha256'], bytes=row['export_bytes'])
    baseline = read_json(ROOT / config['baseline'])
    for key, count in [('prior_raw_sha256', 3101), ('prior_audit_raw_sha256', 79)]:
        assert len(baseline[key]) == count
        assert all(identity(Path(path))['sha256'] == value for path, value in baseline[key].items())
    values, private_metadata = known_values(config)
    assert private_metadata == read_json(HERE / 'attempt-v1/private-pool-metadata.json')
    matcher = KnownTokenRedactor(values)
    new_analysis = ROOT / '.runtime/multifield-source-final/independent-new-v2-analysis'
    success = read_json(new_analysis / 'success.json')
    assert success['status'] == 'PASS' and success['source_sha'] == config['source_sha']
    for name, key in [('validate_window.py', 'validator_sha256'), ('mapping-input.json', 'mapping_input_sha256'), ('validation.json', 'validation_sha256')]:
        assert identity(new_analysis / name)['sha256'] == success[key]
    # The producer's generic pytest-* exclusion also excludes this raw four-node collection.
    annex_source = ROOT / config['supplemental_prefix'] / 'pytest-collection.json'
    annex_raw = annex_source.read_bytes()
    assert str(annex_source.relative_to(ROOT)) not in {r['raw_path'] for r in rows}
    annex_nodes = json.loads(annex_raw)['nodeids']; assert len(annex_nodes) == len(set(annex_nodes)) == 4
    all_main_collections = [ROOT / config['execution_base'] / (w['name'] + '-collection.json') for w in union['windows']]
    assert all(str(p.relative_to(ROOT)) in {r['raw_path'] for r in rows} for p in all_main_collections)
    candidate = HERE / 'public-candidate'; candidate.mkdir(mode=0o700, exist_ok=False)
    (candidate / '.gitattributes').write_text('* -text -whitespace\n')
    copied = []
    def copy(source, target):
        destination = candidate / target; destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        assert identity(destination) == identity(source)
        copied.append(dict(public_path=target, origin=str(source.relative_to(ROOT)), **identity(source)))
    for path in sorted(HERE.iterdir()):
        if path.is_file() and path.suffix in {'.py', '.json', '.md', '.log'} and path.name not in {'seal-v1.log', 'sealed-candidate-manifest.json'}:
            copy(path, 'audit-preparation/' + path.name)
    for source_dir, target_dir in [('attempt-v1', 'mechanical-and-scope'), ('claims-v2', 'claims')]:
        for path in sorted((HERE / source_dir).glob('*.json')):
            copy(path, target_dir + '/' + path.name)
    for name in ['source-review.json', 'source-review.md', 'validation.json', 'collection-junit-full-identity.json', 'unit-identity-closeout.json', 'allowlist-delta-review.json']:
        copy(ROOT / config['supplemental_prefix'] / name, 'source-review/' + name)
    copy(annex_source, 'annex/supplement-original-collection.json')
    write(candidate / 'annex/supplement-collection-provenance.json', dict(origin=str(annex_source.relative_to(ROOT)),
        raw_sha256=hashlib.sha256(annex_raw).hexdigest(), raw_bytes=len(annex_raw), nodes=4,
        excluded_from_primary_by_generic_pytest_prefix=True, original_bytes_copied_without_transformation=True,
        full_identity_reconstructed_in='source-review/collection-junit-full-identity.json',
        separate_supplement_not_main97=True, main97_all_raw_collections_indexed_in_primary=True,
        primary_pairs_and_index_unchanged=1006))
    (candidate / 'README.md').write_text('''# Independent audit: multifield source package confirmation

Source: `30e8a60f8bffeb5f0b41bd3abb222526127c5433`. This is bounded Linux synthetic engineering evidence; it does not sign formal business AT or production readiness.

The independent audit rebuilt all 1006 primary raw/export pairs, including exact replacements and fixture-line masking, without importing the producer or root verifier. Known-token matching uses shared helper code; algorithm diversity is not claimed. Raw originals, primary metadata and report remained unchanged. All 617 source paths and 15418 tracked paths matched frozen Git blobs. The earlier 3101 raw originals, 79 audit originals and 87 bounded historical copies remained intact.

The main selection is seven complete same-SHA windows: 97 disjoint complete modules and 2756 unique PASS nodes, zero FAIL/ERROR/SKIP. This is not the whole repository. CI metadata is separate: 12 complete modules, 433 PASS and 14 original Windows/PowerShell environment SKIP, 447 identities. Those skipped native capabilities remain NOT_RUN. Reviewer supplements are separate: four pytest PASS, 37 pure history mutations within one test, 29 extracted-function VM/DTO/transport checks, and six pure budget stub checks within one test. They are not added to the main denominator.

The original frozen literal oracle independently gives 18 known observations with 42 affected/48 preserved pairs and no mismatches; two conservative UNKNOWN observations affect all ten Case-step pairs and preserve none. The 40 designs map to 18 bounded PASS scopes, 15 variants and seven NOT_RUN; 40 is not a pytest count. New package four HTML traces, two prior carry traces, and eight prior MANUAL traces are separate. Forty-one earlier backend HTML modes separately divide into 29 ordinary real-response scenarios, seven actual backend commits with controlled client receipt discard, and five controlled client mechanics. Driver fetch counts are not all untouched backend HTTP. No real browser ran.

The legacy ADOPT recovery GET puts its key in an Idempotency-Key header. The frozen trace did not capture GET headers: raw GET plus original frozen handler validation and executed driver assertions are the evidence, not an invented header trace. The new package recovery key appears explicitly in its GET path. Controlled response discard is not real network packet loss.

The primary producer's generic pytest-* filter also excluded the reviewer's four-node pytest-collection.json. Its exact raw bytes and hash are provided in annex/supplement-original-collection.json and the companion provenance file. All main97 raw collections are in the primary. This appendix does not alter the primary1006 index or move four supplementary nodes into the main selection.

Historical failures remain preserved: first source freeze899P/1F for missing diagnostic IDs, interrupted backend190 named PASS plus64 unexecuted and an unnamed placeholder, interrupted review143 named PASS plus280 unexecuted, and old independent52PASS are not migrated to final scores. Reviewer preparation had a leading-.runtime identity selfcheck correction; the first claims parser attempt stopped on an absent optional asserted field for NOT_RUN input and was corrected with one limited retry preserving the original script and failure. Tool-wrapper serialization/syntax stops are preserved separately; no product source, raw evidence or business tests were changed by these audit corrections.

This feature is explicit opt-in for one existing Case P1 MANUAL note and its two captured/current material slots. It preserves original ADOPT, UNLOCK, VERIFY, UUIDs, history and unaffected locks. Summary is context only; exact outline carriage does not prove facts, business approval, qualification or fulfillment. Local goal output verification is not real Case completion. Windows/Win11, real browser, formal AT, real product models/B0-B2, formal governance/fulfillment, production and untriggered branch CI remain unexecuted. Product model calls: zero.

final-artifact-index.json lists all other files and intentionally omits itself to avoid self-reference. Evidence-local .gitattributes preserves file bytes; no product or global attributes were changed.
''')
    # Fast bounded scan: full tokens through shared matcher, prefixes via fixed-width lookahead/set.
    prefixes = {v[:16] for v in values}
    prefix_re = re.compile(r'(?=([A-Za-z0-9_-]{16}))')
    scans = []
    for path in sorted(candidate.rglob('*')):
        if not path.is_file():
            continue
        text = path.read_text()
        assert not matcher.has_residual(text), 'known private full value in candidate: ' + str(path.relative_to(candidate))
        assert not any(m.group(1) in prefixes for m in prefix_re.finditer(text)), 'known private prefix16 in candidate'
        assert not residual_context(text, path.suffix), 'fixture/session context in candidate'
        if path.suffix == '.json':
            json.loads(text)
        elif path.suffix == '.py':
            ast.parse(text, filename=str(path))
        scans.append(dict(path=str(path.relative_to(candidate)), **identity(path)))
    write(candidate / 'publicability.json', dict(status='PASS_PUBLIC_APPENDIX_KNOWN_VALUE_AND_CONTEXT_SCAN',
        files_scanned=len(scans), known_synthetic_values=len(values), known_full_value_residuals=0,
        known_prefix16_residuals=0, fixture_or_Bearer_context_residuals=0,
        primary_full_value_and_fixture_context_residuals=0,
        primary_prefix16_rescan_claimed=False, private_values_disclosed=False,
        matcher_shared_algorithm_diversity=False, prefix_scan_fixed_width_set_not_values_times_bytes=True))
    assert inventories(primary) == before_primary and identity(ROOT / report['report']['path'])['sha256'] == report['report']['sha256']
    assert source_inventory(config, set()) == {r['raw_path'] for r in rows}
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() == config['source_sha']
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT)
    gate = dict(status='PASS', scope='BOUNDED_LINUX_SYNTHETIC_ENGINEERING_INDEPENDENT_AUDIT',
        source_sha=config['source_sha'], source_paths=617, all_tracked_paths=15418,
        source_and_all_tracked_frozen_Git_blobs_exact=True, frozen_runner_helpers_exact=True,
        primary_pairs=1006, primary_raw_bytes=114760126, primary_export_bytes=114754212,
        primary_and_report_stable=True, original_raw_inventory_stable=True,
        exact_private_replacements=30, fixture_line_masks=26, known_private_values=36897,
        primary_known_full_value_and_fixture_context_residuals=0,
        independent_reconstruction_imported_producer_or_root_verifier=False, shared_matcher_algorithm_diversity=False,
        main_complete_modules=97, main_unique_PASS=2756, main_FAIL=0, main_ERROR=0, main_SKIP=0,
        whole_repository=False, main_complete_windows=7, source_SHA_shared_by_all_selected_executions=True,
        CI_supplement=dict(complete_modules=12, PASS=433, SKIP=14, FAIL=0, ERROR=0,
                           external_skip_NOT_RUN=True, identities=447, in_main_union=False),
        reviewer_supplement=dict(pytest_PASS=4, pure_mutations=37, VM=29, pure_budget_stub_checks=6, in_main_union=False),
        design40=dict(bounded_PASS=18, VARIANT=15, NOT_RUN=7, all40_execution_claimed=False),
        literal_known=dict(rows=18, affected=42, preserved=48, missed=0, wrong=0, wrong_preserved=0),
        literal_UNKNOWN_conservative=dict(rows=2, affected=10, preserved=0, known_precision_member=False),
        older_backend_HTML=dict(modes=41, real_response=29, controlled_receipt_loss=7, controlled_client_mechanics=5),
        new_package_HTML=dict(modes=4, actual_HTTP=188), prior_carry_HTML=dict(modes=2, actual_HTTP=24),
        prior_MANUAL_HTML=dict(modes=8, actual_HTTP=431, original_ADOPT=5, VERIFY=25, local_six_goal_closures=5),
        prior_GET_header_not_captured_limit_preserved=True, five_goal_carry_probe_not_six_goal_main=True,
        prior_raw_originals_unchanged=3101, prior_audit_originals_unchanged=79, prior_bounded_copies_unchanged=87,
        supplemental_collection_generic_pytest_filter_exclusion_disclosed=True, supplemental_collection_original_bytes_in_annex=True,
        main97_collection_files_all_in_primary=True, primary_metadata={p: before_primary[p] for p in config['primary_metadata']},
        report=report['report'], actual_primary_CRLF_files=sum((ROOT / r['export_path']).read_bytes().count(b'\r\n') > 0 for r in rows),
        source_blockers=[], archive_blockers=[], audit_parser_correction_and_first_failure_preserved=True,
        formal_AT_accepted=False, production_ready=False, real_browser=False, real_product_model_calls=0,
        NOT_RUN=['Windows/Win11', 'real browser', 'formal business AT', 'real product models/B0-B2', 'formal governance/approval/fulfillment', 'production', 'untriggered branch CI'],
        post_gate_allowed_root_actions='Only now prefix4 history documents, docs-only commit/normal push, then outside8 delivery verification',
        utc=datetime.now(timezone.utc).isoformat())
    write(candidate / 'final-gate.json', gate)
    write(candidate / 'copy-provenance.json', dict(original_files_copied=copied, source_values_disclosed=False,
          primary_and_source_raws_not_written=True, sibling_destination=config['sibling']))
    indexed = inventories(candidate)
    write(candidate / 'final-artifact-index.json', dict(status='SEALED_PUBLIC_INDEPENDENT_AUDIT_APPENDIX',
          source_sha=config['source_sha'], index_omits_itself=True, files=indexed, count=len(indexed)))
    # Final tiny additions contain fixed labels/counts/hashes, still scan them before export.
    for name in ['final-gate.json', 'publicability.json', 'copy-provenance.json', 'final-artifact-index.json']:
        text = (candidate / name).read_text(); assert not matcher.has_residual(text)
        assert not any(m.group(1) in prefixes for m in prefix_re.finditer(text))
    sibling = ROOT / config['sibling']; assert not sibling.exists(), 'do not overwrite existing public audit'
    shutil.copytree(candidate, sibling)
    assert inventories(candidate) == inventories(sibling)
    assert inventories(primary) == before_primary
    record = dict(status='PASS_SEALED_STOPPED', source_sha=config['source_sha'], candidate=str(candidate.relative_to(ROOT)),
                  public_sibling=config['sibling'], files=len(inventories(candidate)),
                  gate_sha256=identity(candidate / 'final-gate.json')['sha256'],
                  artifact_index_sha256=identity(candidate / 'final-artifact-index.json')['sha256'],
                  candidate_and_public_exact=True, primary1006_and_metadata_unchanged=True,
                  report_unchanged=True, all8_primary_raw_producers_stopped=True,
                  primary_and_independent_audit_final_outputs_stopped=True,
                  manifest= inventories(candidate))
    write(HERE / 'sealed-candidate-manifest.json', record)
    print(json.dumps({k: record[k] for k in ['status', 'source_sha', 'public_sibling', 'files', 'gate_sha256', 'artifact_index_sha256']}))


if __name__ == '__main__':
    main()
