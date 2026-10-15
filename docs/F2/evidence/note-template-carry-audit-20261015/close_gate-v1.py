"""Freeze a private public-safe audit candidate; root alone integrates docs/Git."""
from pathlib import Path
import hashlib, json, shutil, traceback
from audit_archive import HERE, ROOT, KnownTokenRedactor, identity, read_json, public_json, source_freeze, source_inventory, known_values, check_structure, residual_context

def main():
    config=read_json(HERE/'audit-config.json');attempt=HERE/'attempt-v1'
    assert config['archive_ready'] is True
    assert read_json(attempt/'claim-scope-gate.json')['status']=='PASS_MECHANICAL_EXECUTION_AND_CLAIM_SCOPE'
    union=read_json(attempt/'independent-window-union.json')
    assert (union['complete_modules'],union['unique_testcases'])==(95,2713)
    pairs=read_json(attempt/'pair-reconstruction.json')['records'];assert len(pairs)==974
    assert sum(x['raw_bytes'] for x in pairs)==141924930 and sum(x['export_bytes'] for x in pairs)==141916443
    for item in pairs:
        assert identity(ROOT/item['raw_path'])==dict(bytes=item['raw_bytes'],sha256=item['raw_sha256'])
        assert identity(ROOT/item['export_path'])==dict(bytes=item['export_bytes'],sha256=item['export_sha256'])
    old=read_json(attempt/'old2127-verification.json')
    assert len(old['records'])==2127
    assert all(identity(ROOT/p)==value for p,value in old['records'].items())
    preserved=read_json(attempt/'legacy-copy-verification.json')
    for item in preserved['records']:
        assert identity(ROOT/item['original'])==identity(ROOT/item['copy'])==dict(bytes=item['bytes'],sha256=item['sha256'])
    primary=ROOT/config['primary'];metadata={name:identity(primary/name) for name in config['primary_metadata']}
    assert {str(p.relative_to(ROOT)) for p in primary.rglob('*') if p.is_file()}=={x['export_path'] for x in pairs}|{str((primary/n).relative_to(ROOT)) for n in metadata}
    assert source_inventory(config,set())=={x['raw_path'] for x in pairs}
    current_source=source_freeze(config)
    assert current_source==read_json(attempt/'source-Git-verification.json')
    public_json(attempt/'final-source-Git-verification.json',current_source)
    values,pool=known_values(config);assert pool==read_json(attempt/'private-pool-metadata.json')
    matcher=KnownTokenRedactor(values)
    report=ROOT/config['report'];report_identity=identity(report)
    assert report_identity['sha256']=='4d5fccaf23805915653fed581b9cd3cd2d561e71c47be4bf2833939498902745'
    for name in metadata:
        data=(primary/name).read_text();assert not matcher.has_residual(data) and not residual_context(data,(primary/name).suffix)
    assert not matcher.has_residual(report.read_text()) and not residual_context(report.read_text(),report.suffix)
    closure=dict(status='PASS_FINAL_UNCHANGED_ORIGINALS_METADATA_SOURCE',source_sha=config['source_sha'],raw_export_pairs=974,raw_bytes=141924930,export_bytes=141916443,
        raw_and_export_hashes_unchanged_after_all_checks=True,primary_metadata=metadata,report=report_identity,all_tracked14392_Git_blobs_and_hashes_still_frozen=True,source_paths613_still_frozen=True,old_raw2127_still_unchanged=True,legacy87_original_copy_pairs_still_unchanged=True,private_pool34045_hashes_still_stable=True,
        parent_declared_all11_producers_stopped=True,independently_observed_inventory_and_raw_stability=True,no_product_primary_old_documents_or_Git_writes=True)
    public_json(attempt/'final-stability-check.json',closure)
    candidate=HERE/'candidate';candidate.mkdir(exist_ok=False)
    # Install byte-preservation attributes before freezing any candidate index.
    (candidate/'.gitattributes').write_text('# Preserve audit evidence raw bytes.\n* -text -whitespace\n')
    for name in ['audit_archive.py','audit_execution_scope.py','audit_scope_claims.py','close_gate.py','shared_matcher.py','selfcheck_prepare.py','audit-config.json','archive-ready-receipt.json','eight-window-schema-preflight.json','module-selection-preparation.json','execution-audit-prepared.json','README-preparation.md','preparation-selfcheck-v1.log','preparation-selfcheck-v2.json','report-before-count-wording-correction.md','attempt-v1.log','attempt-v1-execution.log','attempt-v1-claims.log']:
        shutil.copyfile(HERE/name,candidate/name)
    (candidate/'attempt-v1').mkdir()
    for path in sorted(attempt.iterdir()):
        assert path.is_file() and path.suffix=='.json'
        shutil.copyfile(path,candidate/'attempt-v1'/path.name)
    wording=ROOT/'.runtime/note-template-carry-delivery/report-wording-fix.json'
    if wording.is_file():shutil.copyfile(wording,candidate/'root-report-wording-fix-receipt.json')
    (candidate/'README.md').write_text('Independent final archive audit for frozen source '+config['source_sha']+'.\n\n'
        '974 raw/export pairs independently reconstructed byte for byte, with15 exact synthetic-session replacements and36 fixture-repr line masks; private originals unchanged. The34045 registered synthetic values and fixture/bearer contexts leave zero residuals. JSON/XML/JSONL/Python/JavaScript structure checks passed. Known-token matching is a byte-identical shared helper; inventory, traversal, reconstruction and scope checks are independent. No algorithm diversity is claimed.\n\n'
        'The selected regression union is95 complete affected modules/2713 unique PASS from eight execution windows. The original root2 raw window remains788PASS/1FAIL. Its entire44-item module, including43 originalPASS, is excluded from the selected union; a complete same-source44PASS retry replaces it. The other24 modules are selected as complete745PASS. The separate original reviewer423-item window remains422PASS/1FAIL; the one authorized complete16-module retry is423PASS. Both short source-expiry failures occurred in preconditions before their intended target seams; no product/test/clock/assertion/permission change. Prior failed, interrupted and collection-blocked windows remain in primary evidence.\n\n'
        'Additional units stay separate:2 historical pytest and6 budget pytest PASS,20 pure historical mutations inside one actual fixture; mature fixtures and new19 backend cases have five required goals. New28 independent cases supply two full original HTML modes and four actual six-goal closures. All51 current original-HTML traces are grouped as36 real-backend scenarios,10 actual commits with controlled receipt loss and5 controlled client negatives;1412 page-driver fetch records are not fixture/setup or injected-response counts.\n\n'
        'The22 independent designs map to9 named/8 variant/5NOT_RUN;38 independent review designs map to11 named/19 variant/6NOT_RUN/2static. Neither design count is a pytest denominator or complete formal acceptance. UNKNOWN impact precision of new carry/manual windows is not measured; old source UNKNOWN expansion, known partitions and recorded lock fields are separate.\n\n'
        'All613 source paths and14392 tracked files/Git blobs remain frozen;2127 previous originals and87 earlier original/copy pairs remain unchanged. The only report correction before the mechanical snapshot replaced an erroneous44-module phrase with44 items in one failed module; its original text/hash receipt is preserved here. No audit failure was hidden or primary/raw rewritten.\n\n'
        'Linux synthetic owned PostgreSQL only. Windows, real browser/blockedPlaywright module, formal business AT, real model/B0-B2, formal governance/real fulfillment, production and branchCI without existing trigger remain NOT_RUN. These are bounded engineering gates, not whole-repository or production acceptance. Root alone will copy this immutable candidate into the public sibling and then perform documentation/Git integration.\n\n'
        '[Final gate](final-gate.json) · [Artifact index](final-artifact-index.json) · [Mechanical reconstruction](attempt-v1/pair-reconstruction.json) · [Selected execution union](attempt-v1/independent-window-union.json)\n',encoding='utf-8')
    gate=dict(status='PASS_INDEPENDENT_BOUNDED_FINAL_GATE',source_sha=config['source_sha'],primary=config['primary'],pairs=974,raw_bytes=141924930,export_bytes=141916443,
        independent_exact_byte_reconstruction=True,exact_private_value_replacements=15,fixture_repr_line_masks=36,registered_synthetic_values=34045,known_private_and_fixture_context_residuals=0,
        source_paths=613,all_tracked_paths=14392,Git_blobs_and_worktree_hashes_exact=True,old2127_originals_unchanged=True,legacy87_original_copy_pairs_unchanged=True,
        complete_selected_modules=95,unique_selected_PASS=2713,execution_windows=8,raw_windows_all_PASS_claimed=False,failed_root2_entire44_module_excluded_and_replaced_by_complete_retry=True,review_first422PASS1FAIL_preserved=True,
        supplementary_pytest_PASS=8,pure_history_mutations=20,supplement_fixture_required_goals=5,new_independent_pytest=28,new_six_goal_closures=4,new_original_HTML=2,total_current_original_HTML=51,total_page_driver_fetch_records=1412,
        HTML_evidence_categories=dict(REAL_BACKEND_RESPONSE_SCENARIO=36,REAL_BACKEND_COMMIT_WITH_CONTROLLED_RECEIPT_LOSS=10,CONTROLLED_CLIENT_NEGATIVE=5),
        review38_design_counts=dict(NAMED_SCENARIO=11,VARIANTS_ONLY=19,NOT_RUN=6,STATIC_ONLY=2),independent22_design_counts=dict(NAMED_SCENARIO=9,VARIANTS_ONLY=8,NOT_RUN_IN_THIS_MODULE=5),all_designs_executed_claimed=False,
        new_manual_carry_UNKNOWN_impact_precision='NOT_MEASURED',primary_metadata=metadata,report=report_identity,
        product_or_root_producer_or_verifier_imported=False,shared_token_matcher_algorithm_diversity_claimed=False,primary_or_raw_or_shared_source_or_Git_modified=False,
        NOT_RUN=['Windows','real browser/Playwright module','formal business AT','real model/B0-B2','formal governance or real fulfillment','production','branch CI without existing trigger'],
        source_and_primary_stable_at_final_check=True,artifact_manifest='final-artifact-index.json',audit_candidate_integration='Parent root sole writer; subsequent docs commit/push outside this frozen audit snapshot')
    public_json(candidate/'final-gate.json',gate)
    safe=[];types={}
    for path in sorted(candidate.rglob('*')):
        if not path.is_file():continue
        assert '.private.' not in path.name and '__pycache__' not in path.parts
        text=path.read_text();assert not matcher.has_residual(text) and not residual_context(text,path.suffix),'candidate unsafe context: '+path.name
        check_structure(path);types[path.suffix]=types.get(path.suffix,0)+1
        safe.append(dict(path=str(path.relative_to(candidate)),**identity(path)))
    public_json(candidate/'final-artifact-index.json',dict(status='PASS_PUBLIC_SAFE_FROZEN_AUDIT_ARTIFACTS',source_sha=config['source_sha'],artifacts=safe,artifact_count_excluding_this_index=len(safe),this_index_self_hash_omitted=True,private_values_disclosed=False,known_pool_and_fixture_context_residuals=0,byte_preservation_attributes='.gitattributes',structured_counts=types))
    entries=[dict(relative_path=str(p.relative_to(candidate)),source=str(p.relative_to(ROOT)),**identity(p)) for p in sorted(candidate.rglob('*')) if p.is_file()]
    manifest=dict(status='IMMUTABLE_PUBLIC_SAFE_AUDIT_CANDIDATE_READY_FOR_ROOT_COPY',source_sha=config['source_sha'],candidate=str(candidate.relative_to(ROOT)),destination=config['sibling'],artifact_count=len(entries),artifacts=entries,include_exact_bytes_and_relative_paths=True,root_only_shared_Git_integration=True,all_audit_output_stops_after_this_manifest=True)
    public_json(HERE/'candidate-manifest.json',manifest)
    print(json.dumps(dict(status=gate['status'],candidate=manifest['candidate'],manifest=str((HERE/'candidate-manifest.json').relative_to(ROOT)),artifacts=len(entries),manifest_sha256=identity(HERE/'candidate-manifest.json')['sha256'],final_gate_sha256=identity(candidate/'final-gate.json')['sha256']),indent=2))

if __name__=='__main__':
    try:main()
    except BaseException as error:
        public_json(HERE/'closure-failure.json',dict(status='FAIL_NO_PUBLISH_CANDIDATE',error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc(),source_primary_raw_modified=False));raise
