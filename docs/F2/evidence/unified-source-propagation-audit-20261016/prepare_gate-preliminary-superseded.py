# SUPERSEDED PREPARATION DRAFT; do not rerun over final_gate.py. Candidate inventory and final counts subsequently corrected.
from pathlib import Path
import json
old=Path('.runtime/fact-provenance-archive-audit');out=Path('.runtime/unified-propagation-archive-audit')
s=(old/'final_gate.py').read_text()
s=s.replace("RAW_DIRS=['fact-assertion-provenance-root','fact-provenance-backend','fact-provenance-independent','fact-provenance-review','fact-provenance-final','fact-provenance-final-v2']", "RAW_DIRS=['unified-propagation-'+name for name in ('root','oracle','backend','independent','review','final')]")
s=s.replace("assert len(source)==624 and len(tracked)==16505 and len(runners)==4", "assert len(source)==len(freeze['source_paths']) and len(tracked)==len(freeze['all_tracked_sha256']) and len(runners)==len(freeze['runner_paths'])")
s=s.replace("assert record['tracked_source_paths']==624 and record['all_tracked_paths']==16505", "assert record['tracked_source_paths']==len(freeze['source_paths']) and record['all_tracked_paths']==len(freeze['all_tracked_sha256'])")
s=s.replace('==103','==107').replace('modules=103','modules=107').replace('==61','==87').replace('new_unique_passes=61','new_unique_passes=87')
s=s.replace("new_modules={'tests/test_employees_fact_provenance.py','tests/test_employees_fact_provenance_review.py','tests/test_employees_fact_client_probes.py','tests/test_employees_fact_provenance_independent.py'}", "new_modules={'tests/test_unified_dependency_propagation.py','tests/test_unified_dependency_propagation_literal.py','tests/test_unified_dependency_propagation_independent.py','tests/test_unified_dependency_client_probes.py'}")
s=s.replace("main103_denominator_overlap=0", "main107_denominator_overlap=0")
s=s.replace("assert all(status in ('PASS','SKIP') for status in nodes.values())", "assert Counter(nodes.values())==Counter(PASS=433,SKIP=14)")
s=s.replace("FULL_ORIGINAL_HTML_EMPLOYEES_PROVENANCE_ACTUAL_HTTP_ASGI_OWNED_PG", "FULL_ORIGINAL_HTML_UNIFIED_PROPAGATION_ACTUAL_HTTP_ASGI_OWNED_PG")
s=s.replace("adopts[0]['body']['fact_provenance_scope']=='EMPLOYEES_USER_ASSERTION_V1'", "adopts[0]['body']['dependency_scope']=='BOUNDED_MULTI_SOURCE_V1'")
s=s.replace("else:assert not posts and any(c['status']==403 and '/employees-fact-impact' in c['path'] for c in calls)", "else:assert not posts and any(c['status']==403 and 'dependency_scope=BOUNDED_MULTI_SOURCE_V1' in c['path'] for c in calls)")
s=s.replace("assert recovery,'original command-recovery endpoint was not read'", "assert recovery,'original command-recovery endpoint was not read'")
# This driver records GET key headers, so missing key evidence is a blocker.
a=s.index("                if captured:");b=s.index("        else:assert not posts",a)
s=s[:a]+"                assert captured and all(c['request_key']==adopts[0]['request_key'] for c in captured)\n                row['exact_get_key_raw_binding']='CAPTURED_IDEMPOTENCY_KEY_MATCH'\n"+s[b:]
s=s.replace('EmployeesFactProvenanceOracle-20261015.json','UnifiedSourcePropagationOracle-20261016.json').replace('==40\n','==36\n').replace('design_rows=40','design_rows=36')
s=s.replace("assert row['literal_expected']==byid[row['id']]['expected']", "assert row['literal_expected']=={k:v for k,v in byid[row['id']].items() if k not in ('execution_status','intended_layer')}")
s=s.replace("freeze=load(config['freeze']);assert freeze['source_sha']==config['source_sha']==ready['source_sha']", "freeze=load(config['freeze']);assert freeze['source_sha']==ready['source_sha']\n    assert re.fullmatch('[a-f0-9]{40}',freeze['source_sha'])")
a=s.index('    preservation=dict(previous_raw=');b=s.index('\n    selection=',a)
s=s[:a]+"    preservation=dict(prior_raw=preserve(baseline['prior_raw_sha256'],config['expected_legacy_raw']))"+s[b:]
s=s.replace("[freeze['source_sha'],'103',str(regression_result['passed']),'61']", "[freeze['source_sha'],'107',str(regression_result['passed']),'87']")
s=s.replace('==79','==80').replace('baseline_ref_count=79','baseline_ref_count=80')
a=s.index("    return dict(status='PASS',source_sha=");b=s.index('\ndef main():',a)
s=s[:a]+"""    return dict(status='PASS',source_sha=freeze['source_sha'],archive_entries=len(entries),raw_bytes=total_raw,export_bytes=total_export,regression_modules=107,unique_regression_passes=regression_result['passed'],new_passes=87,native_HTTP_HTML_modes=4,native_fetches=html['native_fetches'],design_rows=36,design_classification=oracle['classification'],source_paths=len(freeze['source_paths']),tracked_paths=len(freeze['all_tracked_sha256']),runner_paths=len(freeze['runner_paths']),before_after_stable=True,baseline_remote_refs_unchanged=80,prior_raw_preserved=5070,report_sha256=sha((ROOT/config['report']).read_bytes()),archive_index_sha256=sha((archive/'index.json').read_bytes()),boundaries=['Controlled client 8 probes are not native HTTP/browser tests','36 design rows classified; never summed as executed pytest','Historical/WIP failures preserved but not included in final regression denominator','Real browser, Windows, formal AT, semantic judgment, real models, production NOT_RUN','Final delivery commit/push and Git blob audit happen after this precommit gate'])
"""+s[b:]
(out/'final_gate.py').write_text(s)
(out/'independent_transform.py').write_bytes((old/'independent_transform.py').read_bytes())
config=dict(status='PREPARED_NOT_EXECUTED_WAIT_ARCHIVE_READY',archive='docs/F2/evidence/unified-source-propagation-20261016',report='docs/F2/UnifiedSourcePropagation-20261016.md',freeze='.runtime/unified-propagation-root/freeze.json',baseline='.runtime/unified-propagation-root/baseline.json',selection='.runtime/unified-propagation-final/selection.json',formal_base='.runtime/unified-propagation-final',expected_modules=107,expected_new_tests=87,expected_legacy_raw=5070,expected_baseline_refs=80,note='Execution requires explicit root ARCHIVE_READY and actual coverage/html paths; final actual schemas must be confirmed before execution. Source SHA and all path counts resolved from actual freeze, not a prior round.')
(out/'audit-config-prepared.json').write_text(json.dumps(config,indent=2)+'\n')
