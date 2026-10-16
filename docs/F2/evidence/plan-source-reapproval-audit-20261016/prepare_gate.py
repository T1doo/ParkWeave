"""Prepare only. No archive gate or product test executes here."""
from pathlib import Path
import json
old=Path('.runtime/unified-propagation-archive-audit/final_gate.py').read_text();s=old
s=s.replace("RAW_DIRS=['unified-propagation-'+name", "RAW_DIRS=['plan-reapproval-'+name")
s=s.replace("'source_sha']==ready['source_sha']", "'source_sha']==ready['source_sha']")
s=s.replace("==config['expected_modules']==freeze['expected_main_modules']==107", "==freeze['expected_main_modules']")
s=s.replace("==107 and set(modules)==set(planned)", "==freeze['expected_main_modules'] and set(modules)==set(planned)")
s=s.replace("new_modules={'tests/test_unified_dependency_propagation.py','tests/test_unified_dependency_propagation_literal.py','tests/test_unified_dependency_propagation_independent.py','tests/test_unified_dependency_client_probes.py'}", "new_modules={m for m in planned if Path(m).name.startswith(('test_plan_source_reapproval','test_plan_reapproval_client'))};assert len(new_modules)==4")
s=s.replace("assert len(new)==freeze['expected_new_tests']==88", "assert len(new)==freeze['expected_new_tests']")
s=s.replace("return dict(modules=107,", "return dict(modules=len(modules),")
a=s.index("    replacement=None\n");b=s.index('\ndef html_traces(',a)
s=s[:a]+"    return dict(window=name,modules=len(record['modules']),counts=dict(Counter(nodes.values())),skip_reasons=skips,main_denominator_overlap=0)\n"+s[b:]
s=s.replace("'ci-metadata');record", "'ci-metadata-solo');record")
s=s.replace("FULL_ORIGINAL_HTML_UNIFIED_PROPAGATION_ACTUAL_HTTP_ASGI_OWNED_PG", "FULL_ORIGINAL_HTML_PLAN_SOURCE_REAPPROVAL_ACTUAL_HTTP_ASGI_OWNED_PG")
a=s.index("        if mode in ('positive','lost_ack'):");b=s.index("        found[mode]=row",a)
s=s[:a]+"""        if mode in ('positive','lost_ack'):
            adopted=[c for c in posts if c['path'].endswith('/service-case-plan') and c['status']==201]
            proposals=[c for c in posts if c['path'].endswith('/plan-approval/proposals')]
            approvals=[c for c in posts if c['path'].endswith('/plan-approval/commands') and c.get('body',{}).get('action')=='APPROVE']
            commits=[c for c in posts if c['path'].endswith('/resource-delivery')]
            verify=[c for c in posts if c['path'].endswith('/service-case-plan/commands') and c.get('body',{}).get('action')=='VERIFY']
            assert len(adopted)==1 and adopted[0]['body'].get('local_revision') is True and adopted[0]['body'].get('opportunity_proof')
            assert len(proposals)==1 and proposals[0]['status']==201 and proposals[0]['body']['delivery']['expected_link_revision']>=1
            assert len(approvals)==1 and approvals[0]['status']==200
            assert len(commits)==1 and commits[0]['status']==201 and commits[0]['body']['expected_link_revision']==proposals[0]['body']['delivery']['expected_link_revision']
            assert len(verify)==5 and len({c['body']['step_id'] for c in verify})==5 and all(c['status']==200 for c in verify)
            assert any(c['path'].endswith('/goal-results') and c['status']==200 for c in calls)
            assert any(c.get('worklist_items') for c in calls)
            if mode=='lost_ack':
                recovery=[c for c in calls if c['method']=='GET' and c['path'].endswith('/resource-delivery/recovery/'+commits[0]['request_key']) and c['status']==200]
                assert recovery,'actual original commit key must be recovered from original keyed URL'
                row['exact_get_key_raw_binding']='CAPTURED_ORIGINAL_KEY_IN_GET_PATH'
        else:assert not posts and any(c['status']==403 and c['path'].endswith('/plan-approval') for c in calls)
"""+s[b:]
# Final analyzer schemas require explicit adaptation from completed actual evidence;
# initial gate remains deliberately blocked if its schema is not agreed.
a=s.index('def coverage(');b=s.index('\ndef gate(',a)
s=s[:a]+"""def coverage(mapping,all_nodes):
    oracle=load('docs/F2/PlanReapprovalOracle-20261016.json')
    assert mapping['oracle_sha256']==sha((ROOT/'docs/F2/PlanReapprovalOracle-20261016.json').read_bytes())
    assert len(mapping['rows'])==len(oracle['rows']) and oracle['status']=='DESIGN_ONLY_NOT_EXECUTED'
    assert mapping['design_status_unchanged']==oracle['status']
    assert {r['id'] for r in mapping['rows']}=={r['id'] for r in oracle['rows']}
    originals={r['id']:r for r in oracle['rows']};counts=Counter()
    for row in mapping['rows']:
        assert row['literal_expected']==originals[row['id']]
        if row['execution'] in ('PASS_WITH_SCOPE_LIMIT','PASS'):
            assert row['evidence'] and row['note']
            for evidence in row['evidence']:assert evidence['status']=='PASS' and all_nodes.get(evidence['identity'])=='PASS'
            for variant in row.get('variants',[]):
                assert variant['note'] and variant['evidence']
                for evidence in variant['evidence']:assert evidence['status']=='PASS' and all_nodes.get(evidence['identity'])=='PASS'
            counts[row['coverage_kind']]+=1
        else:assert row['execution']=='NOT_RUN';counts['NOT_RUN']+=1
    assert dict(counts)==mapping['counts']
    for path,h in mapping['raw_sha256'].items():assert sha((ROOT/path).read_bytes())==h
    return dict(design_rows=len(oracle['rows']),classification=dict(counts),additional_pytest_count=0,all_design_rows_are_browser=False)

def validate_classification_manifest(value,source):
    assert value['source_sha']==source and value['raw_sha256']
    for path,h in value['raw_sha256'].items():assert sha((ROOT/path).read_bytes())==h

def closure_checks(config,ready,freeze):
    value=load(ready.get('closure',str(Path(ready['coverage_map']).with_name('closure.json'))))
    validate_classification_manifest(value,freeze['source_sha'])
    assert value['status']=='LIMITED_PASS' and value['records_are_not_unique_cases'] is True
    return value

def browser_checks(ready,freeze,main_nodes):
    # Exact final schema and actual modes are intentionally required before execution.
    assert ready['browser_classification'],'real Chrome evidence must have an actual classification'
    value=load(ready['browser_classification']);validate_classification_manifest(value,freeze['source_sha'])
    assert value['status']=='LIMITED_PASS' and value['browser_executable']=='/usr/bin/chromium'
    assert value['schema_review_complete'] is True,'adapt exact sealed analyzer schema before ARCHIVE_READY'
    assert len(value['modes'])==4 and len({m['mode'] for m in value['modes']})==4
    for row in value['modes']:
        assert row['evidence'] and row['real_browser'] is True
        for evidence in row['evidence']:assert evidence['status']=='PASS' and main_nodes.get(evidence['identity'])=='PASS'
    return value

def prior_pairs(config,baseline):
    path=config['prior_archive_index'];raw=(ROOT/path).read_bytes();assert sha(raw)==baseline['all_tracked_sha256'][path]
    index=json.loads(raw);assert len(index['entries'])==config['expected_prior_pairs']
    for e in index['entries']:
        before=(ROOT/e['raw_path']).read_bytes();after=(ROOT/e['export_path']).read_bytes()
        assert len(before)==e['raw_bytes'] and sha(before)==e['raw_sha256']
        assert len(after)==e['export_bytes'] and sha(after)==e['export_sha256']
        structure(before,Path(e['raw_path']).suffix);structure(after,Path(e['export_path']).suffix)
    return dict(entries=len(index['entries']),all_raw_export_pairs_preserved=True,index_sha256=sha(raw))
"""+s[b:]
s=s.replace("preservation=dict(prior_raw=preserve(baseline['prior_raw_sha256'],config['expected_legacy_raw']))", "preservation=dict(prior_raw=preserve(baseline['prior_raw_sha256'],config['expected_legacy_raw']),prior_pairs=prior_pairs(config,baseline))")
s=s.replace("oracle=coverage(mapping,regression_result['nodes'])", "oracle=coverage(mapping,regression_result['nodes'])\n    browser=browser_checks(ready,freeze,regression_result['nodes'])")
s=s.replace("[freeze['source_sha'],'107',str(regression_result['passed']),str(regression_result['new_unique_passes'])]", "[freeze['source_sha'],str(regression_result['modules']),str(regression_result['passed']),str(regression_result['new_unique_passes'])]")
s=s.replace("==config['expected_baseline_refs']==80", "==config['expected_baseline_refs']==81").replace('baseline_ref_count=80','baseline_ref_count=81')
s=s.replace("save(out,'closure-classification.json',closure)", "save(out,'closure-classification.json',closure)\n    save(out,'browser-classification.json',browser)")
a=s.index("    return dict(status='PASS',source_sha=freeze['source_sha'],archive_entries=");b=s.index('\ndef main():',a)
s=s[:a]+"""    return dict(status='PASS',source_sha=freeze['source_sha'],archive_entries=len(entries),raw_bytes=total_raw,export_bytes=total_export,regression_modules=regression_result['modules'],unique_regression_passes=regression_result['passed'],new_passes=regression_result['new_unique_passes'],separate_ci=ci['counts'],native_HTTP_HTML_modes=len(html['modes']),native_fetches=html['native_fetches'],bounded_Chrome_modes=len(browser['modes']),design_rows=oracle['design_rows'],design_classification=oracle['classification'],source_paths=len(freeze['source_paths']),tracked_paths=len(freeze['all_tracked_sha256']),runner_paths=len(freeze['runner_paths']),before_after_stable=True,baseline_remote_refs_unchanged=len(baseline['refs']),prior_raw_preserved=len(baseline['prior_raw_sha256']),prior_pairs_preserved=preservation['prior_pairs']['entries'],report_sha256=sha((ROOT/config['report']).read_bytes()),archive_index_sha256=sha((archive/'index.json').read_bytes()),boundaries=['Controlled client probes are not native HTTP or browser tests','Design rows classified by actual evidence; never summed as executed pytest','Historical/WIP failures preserved but not included in final regression denominator','Only explicitly recorded Chrome modes exercised; no all-browser or formal AT claim','Windows, formal AT, real models, production NOT_RUN','Final delivery commit/push and Git blob audit happen after this precommit gate'])
"""+s[b:]
Path('.runtime/plan-reapproval-archive-audit/final_gate.py').write_text(s)
config=dict(status='PREPARED_NOT_EXECUTED_REQUIRES_FINAL_SCHEMAS',archive='docs/F2/evidence/plan-source-reapproval-20261016',report='docs/F2/PlanSourceReapproval-20261016.md',freeze='.runtime/plan-reapproval-root/freeze.json',baseline='.runtime/plan-reapproval-root/baseline.json',selection='.runtime/plan-reapproval-final/selection.json',formal_base='.runtime/plan-reapproval-final',ci_window='ci-metadata-solo',prior_archive_index='docs/F2/evidence/unified-source-propagation-20261016/index.json',expected_prior_pairs=639,expected_legacy_raw=5749,expected_baseline_refs=81,note='All final module/new-item/source counts from actual freeze and complete collection/JUnit. Oracle and HTML/browser/closure analyzer exact schemas must be reviewed before explicit ARCHIVE_READY. No gate execution yet.')
Path('.runtime/plan-reapproval-archive-audit/audit-config-prepared.json').write_text(json.dumps(config,indent=2)+'\n')
