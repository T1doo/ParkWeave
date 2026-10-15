"""Close the independent audit and export only safe own audit artifacts."""
from pathlib import Path
import json
import shutil
from datetime import datetime, timezone

from audit_archive import (ROOT, HERE, read_json, relpath, identity, public_json,
    legacy_copies, source_inventory, source_freeze, prior_originals, known_values, residual_context)
from shared_matcher import KnownTokenRedactor


def main():
    config = read_json(HERE / 'audit-config.json')
    assert config['archive_ready'] is True
    attempt = HERE / 'archive-v1'
    mechanical = read_json(attempt / 'mechanical-gate.json')
    scope = read_json(attempt / 'execution-scope-gate.json')
    assert mechanical['status'] == 'PASS_MECHANICAL_ONLY_SCOPE_GATE_STILL_REQUIRED'
    assert scope['status'] == 'PASS_SCOPE_METRICS_PUBLIC_REPORT_REVIEW_STILL_REQUIRED'
    pairs = read_json(attempt / 'pair-reconstruction.json')
    index = read_json(relpath(config['primary']) / 'index.json')
    assert len(index['entries']) == pairs['pairs'] == 1079
    by_path = {row['raw_path']: row for row in index['entries']}
    for observed in pairs['records']:
        current = by_path[observed['raw_path']]
        for key in ['export_path','raw_sha256','raw_bytes','export_sha256','export_bytes','redactions']:
            assert current[key] == observed[key]
        assert identity(relpath(current['raw_path'])) == dict(bytes=current['raw_bytes'],sha256=current['raw_sha256'])
        assert identity(relpath(current['export_path'])) == dict(bytes=current['export_bytes'],sha256=current['export_sha256'])
    copies, legacy = legacy_copies(config)
    assert set(by_path) == source_inventory(config,copies)
    values, private_metadata = known_values(config)
    assert json.loads(json.dumps(private_metadata)) == read_json(attempt / 'private-pool-metadata.json')
    matcher = KnownTokenRedactor(values)
    assert len(values) == 44472
    frozen = source_freeze(config)
    assert frozen == read_json(attempt / 'source-Git-verification.json')
    public_json(attempt / 'source-Git-final-verification.json', frozen)
    assert prior_originals(config) == read_json(attempt / 'old1048-verification.json')
    primary = relpath(config['primary'])
    primary_expected = {row['export_path'] for row in index['entries']} | {
        str((primary/name).relative_to(ROOT)) for name in config['primary_metadata']}
    assert {str(path.relative_to(ROOT)) for path in primary.rglob('*') if path.is_file()} == primary_expected
    metadata = {name:identity(primary/name) for name in config['primary_metadata']}
    report = relpath(config['report'])
    report_id = identity(report)
    assert report_id == dict(bytes=8809,sha256='c9c4901e05419e6a841547dcf989a517b6314a57171fbe0656bbae5570cd61a9')
    report_text = report.read_text()
    assert not matcher.has_residual(report_text) and not residual_context(report_text,'.md')
    assert '既有两类共享反查、有限合成 Release/ParkInstance、第二园区冷输入及有限模板前向增强已交付' in report_text
    for text in ['92','2666','49','48','NOT_RUN','NOT_MEASURED','23命名场景','14本模块未执行','真实浏览器','Windows','真实模型','生产','正式业务 AT']:
        assert text in report_text, 'required report scope qualifier missing'
    assert 'ServiceRelease 发布/迁移/回滚仍未实施' not in report_text
    public_json(attempt / 'public-report-final-review.json', dict(status='PASS_CORRECTED_PRECISE_SCOPE',
        source_sha=config['source_sha'],report_path=config['report'],report_identity=report_id,
        old_report_identity=identity(attempt/'public-report-before-scope-correction.md'),
        scope_correction='One paragraph qualified remaining general/formal scope and explicitly retained already-delivered finite features; root sole writer.',
        source_or_primary_payload_or_index_or_README_changed=False,
        known_vs_UNKNOWN_and_lock_vs_partition_and_test_vs_trace_units_separate=True,
        formal_AT_real_browser_Windows_real_model_production_CI_NOT_RUN_retained=True,
        note_carry_semantic_merge_general_graph_and_formal_ServiceRelease_work_remaining=True))
    union = read_json(attempt/'independent-window-union.json')
    HTML = read_json(attempt/'prior41-plus-new8-HTML-denominators.json')
    new_impact = read_json(attempt/'HTML-and-precision-denominators.json')
    prior_impact = read_json(attempt/'prior77-propagation-and-lock-denominators.json')
    design = read_json(attempt/'design-denominator-review.json')
    assert union['complete_modules'] == 92 and union['unique_testcases'] == 2666
    assert HTML['total_HTML_traces'] == 49 and new_impact['known_impact_rows'] == 14
    assert prior_impact['records'] == 77 and design['immutable_designs'] == 46
    raw_bytes = sum(row['raw_bytes'] for row in index['entries'])
    export_bytes = sum(row['export_bytes'] for row in index['entries'])
    assert (raw_bytes,export_bytes) == (91500437,91483152)
    assert pairs['redactions'] == dict(exact_private_value=10,fixture_repr_line=74)
    final = dict(status='PASS',scope='LINUX_SYNTHETIC_BOUNDED_ENGINEERING_ARCHIVE_AND_SCOPED_EXECUTION_EVIDENCE',
        source_sha=config['source_sha'],utc=datetime.now(timezone.utc).isoformat(),
        primary=config['primary'],pairs=1079,raw_bytes=raw_bytes,export_bytes=export_bytes,
        exact_private_value_replacements=10,fixture_repr_line_masks=74,
        registered_synthetic_values=44472,known_value_and_fixture_context_residuals=0,
        independent_each_pair_rebuilt_bytes_hash_size_and_counters=True,
        source608_and_all13252_tracked_and_Git_blobs_unchanged=True,old1048_raw_originals_unchanged=True,
        legacy_copy_originals=87,exact_pytest_name_copy_exceptions=7,
        complete_modules=92,unique_current_source_pytest_PASS=2666,FAIL=0,ERROR=0,SKIP=0,
        raw_collection_JUnit_exact_unique_and_cross_window_disjoint=True,
        root_three_windows_full_before_grain='Startup full-freeze equality assertion and freeze snapshot; separate persisted before file covers608 source. Full13252 after map is persisted. Other independent windows retain full before maps.',
        supplemental_pytest_PASS=10,actual_API_PG_seam_lock_budget_items=8,
        successful_receipt_history_fixture_items=2,in_memory_history_refusal_checks=48,
        synthetic_extracted_function_VM_checks=4,additional_units_not_merged_into_2666=True,
        full_original_HTML_traces=49,HTML_categories=HTML['total49_categories'],
        prior41_page_fetch_records=957,new8_Node_HTML_HTTP=431,
        Python_test_body_HTTP_count=498,fixture_setup_or_control_request_total_not_claimed=True,
        new_known_impact_rows=14,new_known_affected_pairs=35,new_known_wrong_or_missed_or_wrong_preserved=0,
        new_UNKNOWN_impact_precision='NOT_MEASURED',new_UNKNOWN_continuation_refusal_nodes=4,
        prior_propagation_rows=77,prior_known_and_UNKNOWN_categories_separate=True,
        preflight_lock_rows=19,preflight_expected_locked_pairs=3,preflight_wrong_locked_pairs=0,
        selected_capacity_P1_lock_exact_cases=2,other_rows_without_lock_fields_not_lock_precision_evidence=True,
        immutable_designs=46,designs_not_pytest_denominator=True,all46_fully_executed_claimed=False,
        independent_design_kinds=design['independent_kinds'],review_partial_and_NOT_RUN_retained=True,
        product_or_test_or_driver_or_Git_writes_by_auditor=False,
        root_report_only_scope_correction_after_mechanical_gate_preserved=True,
        primary_metadata=metadata,public_report=report_id,
        shared_known_matcher_origin=config['shared_matcher_origin'],shared_matcher_sha256=config['shared_matcher_sha256'],
        producer_or_root_verifier_imported=False,algorithm_diversity_claimed=False,
        py_js_no_fixture_repr_line_mask=True,known_exact_value_replacement_all_suffixes=True,
        historical_failed_development_and_old_freeze_windows_preserved_not_migrated_to_current_score=True,
        preparation_v1_policy_and_report_scope_stop_preserved=True,
        remaining_blockers=[],whole_repository_run=False,
        Windows='NOT_RUN',real_browser='NOT_RUN',formal_business_AT='NOT_RUN',real_model_calls=0,
        production='NOT_RUN',branch_CI='NOT_RUN',deployment=False,force_push=False,
        root_Git_integration_and_normal_push_not_performed_by_auditor=True)
    public_json(HERE/'finalization-receipt.json',dict(status='READY_FOR_PUBLIC_AUDIT_COPY',
        source_sha=config['source_sha'],pairs=1079,complete_modules=92,pytest_PASS=2666,
        primary_and_raw_and_frozen_tracked_readonly=True,unindexed_active_tool_stdout='finalize-v1.log'))
    sibling = relpath(config['sibling'])
    assert (sibling/'.gitattributes').is_file()
    attrs = (sibling/'.gitattributes').read_text()
    assert '* -text -whitespace' in attrs
    excluded = {'finalize-v1.log','final-artifact-index.json','README.md','final-gate.json'}
    selected = []
    for path in sorted(HERE.rglob('*')):
        if not path.is_file() or '__pycache__' in path.parts or path.name in excluded:
            continue
        assert '.private.' not in path.name
        data = path.read_text()
        assert not matcher.has_residual(data) and not residual_context(data,path.suffix), 'unsafe audit artifact'
        relative = path.relative_to(HERE)
        target = sibling/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        assert not target.exists(), 'never overwrite a prior public audit artifact'
        shutil.copyfile(path,target)
        assert identity(path) == identity(target)
        selected.append(str(target.relative_to(ROOT)))
    (sibling/'README.md').write_text(
        '# Independent manual-content continuation audit\n\n'
        'Final gate PASS refers to source '+config['source_sha']+' and the bounded Linux synthetic engineering evidence. '
        '1079 raw/export pairs were independently enumerated and rebuilt;92 complete modules contain2666 unique current-source PASS items. '
        'Supplemental10 pytest,48 in-memory checks,4 synthetic VM checks,49 full HTML traces and46 partial design traces retain separate denominators. '
        'Windows,real browser,formal AT,real models,production and branch CI remain NOT_RUN.\n\n'
        'The known-token matcher has shared origin/hash in final-gate.json; algorithm diversity is not claimed. '
        'Inventory,traversal,byte reconstruction,scope counts and final verification do not import the producer or root verifier. '
        'Private value sets are not exported. .py/.js never receive fixture-line masks.\n\n'
        'preparation-v1 retains the pre-export mask-scope policy; the correction and synthetic checks are preserved. '
        'archive-v1/public-report-first-review.json preserves the report wording stop; root corrected one paragraph and its prior bytes/patch/receipt remain. '
        'No business test was added or rerun during this archive audit. The active finalizer stdout is excluded; finalization-receipt.json records the operation. '
        'The artifact index excludes itself to avoid self-reference; .gitattributes was installed before final indexing.\n')
    paths = [path for path in sibling.rglob('*') if path.is_file()]
    assert len(paths) == len({str(path.relative_to(sibling)) for path in paths})
    for path in paths:
        assert not matcher.has_residual(path.read_text()) and not residual_context(path.read_text(),path.suffix)
    assert identity(report) == report_id
    assert {name:identity(primary/name) for name in config['primary_metadata']} == metadata
    assert source_freeze(config)['all_tracked_hashes'] == frozen['all_tracked_hashes']
    public_json(HERE/'final-gate.json',final)
    public_json(sibling/'final-gate.json',final)
    paths.append(sibling/'final-gate.json')
    artifact_index = dict(status='PASS_PUBLIC_AUDIT_COPY_HASHES_EXACT',source_sha=config['source_sha'],
        all_files_except_self=[dict(path=str(path.relative_to(ROOT)),**identity(path)) for path in sorted(paths)],
        self_excluded=True,active_finalizer_stdout_excluded=True,private_values_exported=False,
        primary_index_sha256=metadata['index.json']['sha256'],report_sha256=report_id['sha256'])
    public_json(sibling/'final-artifact-index.json',artifact_index)
    # This private copy is the same closed index; it is not a public index entry.
    public_json(HERE/'final-artifact-index.json',artifact_index)
    for entry in artifact_index['all_files_except_self']:
        assert identity(relpath(entry['path'])) == {k:entry[k] for k in ['bytes','sha256']}
    assert identity(report) == report_id
    assert {name:identity(primary/name) for name in config['primary_metadata']} == metadata
    assert source_freeze(config)['all_tracked_hashes'] == frozen['all_tracked_hashes']
    print(json.dumps(dict(status='PASS',source_sha=config['source_sha'],pairs=1079,modules=92,pytest_PASS=2666,
        safe_public_artifacts=len(paths),sibling=config['sibling'],remaining_blockers=[])))


if __name__ == '__main__':
    main()
