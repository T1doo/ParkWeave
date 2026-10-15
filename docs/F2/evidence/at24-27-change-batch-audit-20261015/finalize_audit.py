"""Close independent evidence gate; writes only the new audit directories."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

from audit_archive_pairs import frozen, known_private, record
from fast_known_redaction import KnownTokenRedactor
from scan_fixture_contexts import scan_fixture_contexts

ROOT = Path('/workspace/ParkWeave')
OUT = ROOT / '.runtime/at24-27-audit'
PUBLIC = ROOT / 'docs/F2/evidence/at24-27-change-batch-audit-20261015'
PRIMARY = ROOT / 'docs/F2/evidence/at24-27-change-batch-20261015'
SHA = '5a7eee826564426a4c36607ac038bd61e00665d7'


def load(path):
    return json.loads(path.read_text())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    pairs = load(OUT / 'archive-independent-pairs.json')
    assert pairs['status'] == 'PAIR_REBUILD_PASS_FINAL_COVERAGE_GATE_PENDING'
    assert pairs['checks'] == {'files': 775, 'bytes': 50568287, 'python': 70, 'json': 298, 'xml': 41, 'jsonl': 164, 'javascript': 14}
    assert pairs['redactions'] == {'exact_private_value': 20, 'fixture_repr_line': 52}
    assert pairs['known_private_values'] == 38362 and pairs['known_private_residuals'] == 0
    assert all(x['exit_code'] == 0 for x in pairs['javascript_syntax'])
    assert load(OUT / 'coverage-scope-complete.json')['status'] == 'PASS'
    assert load(OUT / 'initial-literal-and-observation-independent.json')['status'] == 'PASS'
    assert load(OUT / 'previous-primary-originals-independent.json')['private_originals_unchanged'] == 273
    assert load(OUT / 'redaction-differential-result.json')['tests'] == 17
    assert '7 passed' in (OUT / 'fixture-scanner-v2.log').read_text()
    for filename in ['independent-pairs-v1.log', 'coverage-scope-v1.log', 'coverage-scope-v2.log']:
        assert 'AssertionError' in (OUT / filename).read_text()
    correction = load(OUT / 'read-observation-report-correction.json')
    for row in correction['entries']:
        before = (ROOT / row['before_copy']).read_bytes()
        after = (ROOT / row['path']).read_bytes()
        assert hashlib.sha256(before).hexdigest() == row['before_sha256']
        assert hashlib.sha256(after).hexdigest() == row['after_sha256']
        assert before.decode().count(row['change_from']) == 1
        assert before.decode().replace(row['change_from'], row['change_to']).encode() == after
        assert (OUT / ('historical-' + Path(row['before_copy']).name)).read_bytes() == before
    report = ROOT / 'docs/F2/AT24-27ChangeBatch-20261015.md'
    expected = 'ae0d756f1ef04f2f912f236c1a1d96bb3cfe88557694dbc47eff079f6e16b924'
    assert record(report)['sha256'] == expected
    text = report.read_text()
    assert not any(x in text for x in ['@@', 'ROOT_RESULT', 'REVIEW_RESULT'])
    required = ['2617', '90', '不是全仓', '20', 'known27', 'UNKNOWN8', '100', '40', '41', '5条DOM/transport',
                '9真实后端响应模式', '3受控客户端', '957', '6109', '15/62', '4/20',
                '5条读取前后差异观测', 'late_403一条有3项', '其余4条无变化',
                'KEEP_MANUAL', 'DEFER', '继续待办', 'NOT_IMPLEMENTED', 'MIGRATE422',
                'Windows', '真实浏览器', '正式业务 AT', '真实产品模型', '生产未执行', 'NOT_RUN']
    for item in required:
        assert item in text, item
    pending_links = []
    for link in re.findall(r'\]\(([^)]+)\)', text):
        if '://' not in link:
            target = report.parent / link.split('#')[0]
            if not target.exists():
                pending_links.append(target)
    assert {p.name for p in pending_links} <= {'final-gate.json', 'final-artifact-index.json'}
    assert all(p.parent == PUBLIC for p in pending_links)
    save('public-report-independent-review.json', dict(status='PASS', source_sha=SHA,
        report_path=str(report.relative_to(ROOT)), report_sha256=expected,
        primary_README_sha256=record(PRIMARY / 'README.md')['sha256'],
        exact_observation_wording_corrected=True, historical_wording_and_correction_preserved=True,
        original_775_payloads_and_index_unchanged=True, global_AT_signoff=False,
        bounded_P1_note_not_general_merge=True, KEEP_MANUAL_and_DEFER_remain_pending=True,
        replaced_formal_Approval_not_implemented=True, breaking_migration_execution_not_claimed=True,
        NOT_RUN=['Windows', 'real browser', 'formal business AT', 'real product models/B0-B2', 'production', 'this branch CI'],
        scope_statistics_match_rebuilt_evidence=True))
    before = frozen(SHA)
    assert len(before) == 12417
    freeze = load(ROOT / '.runtime/at24-27-root/final-freeze-v2.json')
    assert len(freeze['source_paths']) == 605
    assert {p: item['sha256'] for p, item in before.items()} == freeze['all_tracked_sha256']
    assert all(before[p]['sha256'] == value for p, value in freeze['source_paths'].items())
    for name, old in pairs['supplemental_metadata'].items():
        assert record(PRIMARY / name) == old
    for index_name in ['raw-snapshot.json', 'export-snapshot.json']:
        for path, old in load(OUT / index_name).items():
            assert record(ROOT / path) == old
    values, private_sets = known_private()
    assert pairs['private_sets'] == private_sets
    assert all((ROOT / item['path']).stat().st_mode & 0o777 == 0o600 for item in private_sets)
    save('final-frozen-Git-bytes.json', dict(source_sha=SHA, source_paths=605, all_tracked_paths=12417, files=before))
    (OUT / '.gitattributes').write_text('# Keep independently audited evidence byte-for-byte.\n* -text -whitespace\n')
    (OUT / 'README.md').write_text('''# AT24–27 independent final audit

Source `5a7eee826564426a4c36607ac038bd61e00665d7`. Independent reconstruction and final scope gate passed. The primary root checkpoint deliberately remains PENDING; this separate sibling supplies the later gate without altering the 775 historical payload pairs.

Rebuilt every pair from the unchanged private original, independently selected eight-directory inventory, structured JSON/JSONL/XML sanitization, hashes, byte sizes, fixture-context and known-value residual scans. 775 pairs / 50,568,287 export bytes; 20 exact synthetic-value replacements / 52 fixture repr lines; 38,362 known synthetic values, zero residual. 298 JSON, 164 JSONL, 41 XML, 70 Python and 14 JavaScript files parse/compile; all JavaScript syntax checks exit 0. Known-token matcher shares an explicitly declared prior helper lineage; no algorithm-provenance diversity is claimed. Producer or root verifier was never imported. The 158 private registries were mode 0600 and were not exported.

Five original, unnormalized raw collection/JUnit windows at the same source independently yield 90 complete affected modules / 2617 unique PASS, no FAIL/ERROR/SKIP; not the whole repository. The original 72 plan and disjoint additional 18 consumers remain separate. 20 fixed design scenarios, 37 new pytest nodes, precision records/step pairs, complete HTML flows and 20 supplemental extracted-function VM probes have different units and are not added together. New precision: known 27 records/100 pairs, conservative UNKNOWN 8/40; no misses/wrong impacts/wrong preservation. Two selected-capacity P1 lock/old-reservation cases are separately verified. 41 HTML traces include 5 controlled DOM/transport negatives; new 12 comprise 9 actual backend-response modes and 3 controlled client negative modes. Captured 957 Node HTTP calls and 6109 Python test-body loopback calls do not claim every fixture setup request.

Five read-difference observations are not five changes: only late_403 has three original invalidated-object differences; four observations have none, and remaining business/history tables have no differences. The original overbroad report/README sentences, exact hashes and two one-sentence replacements are retained as historical files. The current report and primary README were rechecked after correction; source, 775 pairs, index, root audit and primary attributes never changed.

Audit tool stops are retained: helper unittest initially collected zero because these seven helpers use pytest functions; the bounded pytest retry passed seven. Pair v1 stopped on an overstrict literal attributes check (valid `* -text -whitespace`); semantic attributes v2 passed. Coverage v1/v2 stopped on overstrict assumptions about streamed control frames and legitimate request-log fields; the exact-format bounded v3 passed. All stopped scripts/logs remain alongside the final files. The matcher differential suite passed 17 helper tests (including 200 deterministic generated cases). These helper counts are not product regressions. Product historical WIP/failed/interrupted windows stay in the primary; none supplies final PASS counts.

P1 note is owner coordination history, not source facts, compiled contract, authorization or general content merge. KEEP_MANUAL/DEFER remain pending; ACCEPT_SOURCE still requires original UNLOCK, ADOPT, real business work and explicit affected VERIFY. Note-bearing replacement/template apply refuses until controlled carry exists. Formal replacement Approval and incompatible migration/rollback execution are not implemented by this batch. Only Linux synthetic engineering scope is signed; Windows, real browser, formal business AT, real product models, production and this-branch CI remain NOT_RUN.

`final-artifact-index.json` includes every public file except itself to avoid self-reference. Its gate includes this README and the preserved failure history through the attachment index. No private registry, database, cache or raw credential is exported. Sources and all 12417 frozen tracked files were checked against actual Git blobs before integration of later documentation.
''')
    save('final-gate.json', dict(status='PASS', source_sha=SHA, utc=datetime.now(timezone.utc).isoformat(),
        scope='LINUX_SYNTHETIC_BOUNDED_AT24_27_ENGINEERING_AND_ARCHIVE_AUDIT_NOT_FORMAL_AT_SIGNOFF',
        primary_pairs=775, export_bytes=50568287, independent_exact_rebuild=True,
        exact_private_redactions=20, fixture_line_redactions=52, known_values=38362, private_sets=158,
        known_private_and_fixture_residuals=0, primary_metadata=4, original_source_paths=605,
        original_tracked_files_matching_Git_blobs=12417, source_or_tracked_drift=[],
        complete_affected_modules=90, unique_actual_pytest_PASS=2617, FAIL=0, ERROR=0, SKIP=0,
        collection_JUnit_exact=True, raw_nodeids_normalized=False, whole_repository_run=False,
        design_scenarios=20, new_pytest_nodes=37, supplemental_VM_probes=20,
        complete_HTML_flows=41, complete_HTML_controlled_negatives=5,
        new_HTML_actual_backend_response_modes=9, new_HTML_controlled_negative_modes=3,
        read_difference_observations=5, changed_observation_records=1, invalidated_object_differences=3,
        observation_records_without_change=4, report_wording_correction_verified=True,
        report_sha256=expected, primary_README_sha256=record(PRIMARY / 'README.md')['sha256'],
        prior_primary_originals_unchanged=273, no_producer_verifier_imported=True,
        shared_matcher_provenance_disclosed=True, failures_retained=True,
        product_raw_primary_or_Git_mutation_by_reviewer=False,
        declared_new_metadata_correction_by_root=['one report sentence', 'one primary README sentence'],
        remaining_implementation_limits=['KEEP_MANUAL/DEFER remain pending', 'controlled note carry and general content merge', 'general graph propagation', 'formal replacement Approval', 'ServiceRelease publish/migrate/rollback execution'],
        NOT_RUN=['Windows', 'real browser', 'formal business AT', 'real product models/B0-B2', 'production', 'this branch CI'],
        attachment_index='final-artifact-index.json', self_referential_index=False))
    # Check every candidate attachment before indexing/copying. No private values
    # are copied; the known registry is used in-memory only for detection.
    redactor = KnownTokenRedactor(values)
    candidates = sorted(p for p in OUT.iterdir() if p.is_file() and p.name not in {'final-artifact-index.json', 'publicability.json'})
    for path in candidates:
        data = path.read_bytes()
        assert '.private.' not in path.name and not redactor.has_residual(data.decode())
        assert not scan_fixture_contexts(data, path.suffix)
        if path.suffix == '.json':
            json.loads(data)
        elif path.suffix == '.py':
            ast.parse(data)
            compile(data, str(path), 'exec')
    save('publicability.json', dict(status='PASS', source_sha=SHA, checked_artifacts=len(candidates),
        known_private_residuals=0, fixture_context_residuals=0, known_values=38362,
        private_registries_exported=0, structured_artifacts_parse=True,
        stdout_assertion_failures_retained=True, primary_or_raw_touched=False))
    candidates = sorted(p for p in OUT.iterdir() if p.is_file() and p.name != 'final-artifact-index.json')
    save('final-artifact-index.json', dict(source_sha=SHA, status='PUBLIC_INDEPENDENT_AUDIT_ATTACHMENTS',
        files={p.name: record(p) for p in candidates}, artifact_count=len(candidates),
        index_self_excluded=True, excludes=['__pycache__', 'private registries', 'databases'],
        primary_reference='at24-27-change-batch-20261015/index.json'))
    PUBLIC.mkdir(parents=True, exist_ok=False)
    for path in OUT.iterdir():
        if path.is_file():
            shutil.copyfile(path, PUBLIC / path.name)
            assert (PUBLIC / path.name).read_bytes() == path.read_bytes()
    for name, old in load(PUBLIC / 'final-artifact-index.json')['files'].items():
        assert record(PUBLIC / name) == old
    assert all(path.exists() for path in pending_links)
    assert before == frozen(SHA)
    assert not subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=ROOT, text=True).strip()
    print(json.dumps(dict(status='PASS', source_sha=SHA, public_sibling=str(PUBLIC.relative_to(ROOT)),
                         public_files=len(list(PUBLIC.iterdir())), audit_directories_stopped_after_exit=True)))


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        import traceback
        (OUT / 'finalizer-v1-failure.log').write_text(traceback.format_exc())
        raise
