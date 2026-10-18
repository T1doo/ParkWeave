from pathlib import Path
import collections,hashlib,json,subprocess,xml.etree.ElementTree as ET
r=Path(__file__).resolve().parent
p=json.loads((r/'preparation.json').read_text());repo=Path(p['repository']);mirror=Path(p['mirror']);outer=Path(p['outer']);parent=r.parent.parent
result=json.loads((r/'run-result.json').read_text());expected=json.loads((r/'expected-inputs.json').read_text());expected_nodes=json.loads((r/'expected-2-nodes.json').read_text())
def save(name,value):(r/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def xml_ids(path):
    cases=ET.parse(path).findall('.//testcase')
    ids=[c.get('classname').replace('.','/')+'.py::'+c.get('name') for c in cases]
    return cases,ids
cases,ids=xml_ids(r/'independent.xml');maincases,mainids=xml_ids(parent/'frozen.xml')
collected=json.loads((r/'actual-collected-nodeids.json').read_text());assert ids==collected==expected_nodes and len(ids)==len(set(ids))==2
assert len(mainids)==len(set(mainids))==6 and set(ids)<=set(mainids)
assert not any(c.find(tag) is not None for c in cases for tag in ('failure','error','skipped'))
overlap=dict(independent_ids=ids,expected_ids=expected_nodes,main_ids=mainids,independent_unique=2,main_unique=6,all_independent_ids_overlap_main=True,missing_from_main=[],extra_independent=[],not_additive=True,main_xml=str(parent/'frozen.xml'),main_xml_sha256=digest(parent/'frozen.xml'),independent_xml_sha256=digest(r/'independent.xml'))
save('actual-overlap-validation.json',overlap)
origins=json.loads((r/'actual-pytest-module-origins.json').read_text());origin_bad=[]
for name,row in origins.items():
    path=Path(row['file']);rel=path.relative_to(mirror).as_posix()
    if not row['inside_mirror_src'] or rel not in expected or row['sha256']!=expected.get(rel):origin_bad.append(name)
assert origins and not origin_bad
origin_validation=dict(parkweave_modules=len(origins),all_actual_paths_inside_mirror_src=True,all_actual_hashes_equal_frozen_inputs=True,mismatches=origin_bad,child_api_not_additionally_instrumented=True,child_api_configured_source='unchanged ordinary_demo helper sets PYTHONPATH to its own mirror/src and cwd to mirror')
save('module-origin-validation.json',origin_validation)
state_keys=['generation','busy','operationActive','recoverDisabled','releaseDisabled','proof','handle','stored','detailHidden','draft','source','view','context','error']
proofs=[]
for path in sorted((r/'case-artifacts').rglob('refresh-proof.json')):
    d=json.loads(path.read_text());phases={x['label']:x for x in d['phases']};before=phases['new-recovery-fully-settled-before-old-delivery'];late=phases['old-recovery-fully-settled-after-new'];released=phases['explicit-current-read-release-complete'];trace=d['handler_trace']['calls']
    old=next(x for x in trace if x['id']=='receipt-submit-recover' and x['ordinal']==1);new=next(x for x in trace if x['id']=='receipt-submit-recover' and x['ordinal']==2);release=next(x for x in trace if x['id']=='receipt-submit-release')
    assert new['end']==5<old['end']==6<release['end']==8
    assert all(x['returnedPromise'] and x['settled'] and x['outcome']=='fulfilled' for x in trace)
    assert all(before[k]==late[k] for k in state_keys) and late['current_reference_identity_unchanged'] is True
    assert before['proof']['status']=='COMMITTED' and not before['busy'] and not before['operationActive'] and not before['releaseDisabled']
    assert before['handle'] and len(before['stored'])==1 and released['handle'] is None and released['stored']==[] and released['proof'] is None and not released['busy'] and not released['operationActive']
    assert released['draft']==before['draft'] and released['source']==before['source'] and not d['errors']
    page_posts=[x for x in d['traffic'] if x['method']=='POST'];forward_posts=[x for x in d['forwarded'] if x['method']=='POST'];forward_gets=[x for x in d['forwarded'] if x['method']=='GET']
    assert len(page_posts)==len(forward_posts)==1 and [x['status'] for x in forward_gets]==[d['old_status'],200]
    proofs.append(dict(old_status=d['old_status'],file=str(path.relative_to(r)),sha256=digest(path),handler_sequence=trace,new_end=new['end'],old_end=old['end'],release_end=release['end'],new_completed_before_old=True,old_unsettled_before_delivery='asserted in actual passing browser test immediately before old fulfill',late_phase_reference_identity_unchanged=True,all_serialized_state_fields_unchanged=True,serialized_state_keys=state_keys,current_proof_status='COMMITTED',proof_equals_actual_new_reply='asserted in actual passing browser test',raw_handle_unchanged_before_explicit_release=True,explicit_release_only_then_clears_handle_and_proof=True,body_and_source_drafts_retained=True,browser_posts=len(page_posts),forwarded_posts=len(forward_posts),forwarded_recovery_statuses=[x['status'] for x in forward_gets],page_errors=d['errors'],case_history_and_authority_unchanged='actual original assertions passed; full DB snapshots not separately exported by this test',submit_event_count=1,ack_event_count=0,service_case_plan=None,limitations='Only named state fields, disabled properties, receipt-error and receipt-detail hidden are compared; not all visible text or button hidden properties.'))
assert len(proofs)==2 and {x['old_status'] for x in proofs}=={200,403}
save('handler-sequence-validation.json',proofs)
api=[]
for path in sorted((r/'case-artifacts').rglob('ordinary-startup.jsonl')):
    rows=[json.loads(x) for x in path.read_text().splitlines()];ready=[x for x in rows if x['event']=='ready'];ends=[x for x in rows if x['event']=='stop_end']
    assert len(ready)==len(ends)==1 and ends[0]['child_exit'] is not None
    api.append(dict(file=str(path.relative_to(r)),child_pid=ends[0]['child_pid'],ready=True,stop_end=True,exit_code=ends[0]['child_exit'],normal_helper_terminated_owned_child=True))
connpath=r/'owned-connection-diagnostics/connections.jsonl';rows=[json.loads(x) for x in connpath.read_text().splitlines()];counts=dict(collections.Counter(x['kind'] for x in rows));finish=next(x for x in reversed(rows) if x['kind']=='diagnostic_finish')
assert counts.get('connect_failed',0)==0 and finish['successful_connections_without_observed_close']==[]
pgpaths=list((outer/'pytest').glob('parkweave-pg*/data'));pidpaths=list((outer/'pytest').glob('parkweave-pg*/data/postmaster.pid'))
assert not pgpaths and not pidpaths
observer=json.loads((r/'observer-settlement.json').read_text());assert observer['pytest_exitstatus']==0 and not observer['resident_observer'] and result['owned_pytest_process_exited']
settlement=dict(owned_pytest_pid=observer['process_id'],owned_pytest_exit_code=result['child_process_exit_code'],runner_tool_session=62879,runner_tool_exit_code=0,in_process_observer_exited=True,no_resident_observer=True,api_children=api,api_count=len(api),owned_connection_diagnostics_counts=counts,connect_failures=counts.get('connect_failed',0),successful_connections_without_observed_close=[],owned_pg_data_directories_remaining=[str(x) for x in pgpaths],owned_pg_postmaster_pid_files_remaining=[str(x) for x in pidpaths],limits='Owned subprocess helper stop_end and exited pytest only; no global or cross-namespace process inventory or signalling. PG bytes excluded from export.')
assert len(api)==2
save('owned-process-settlement.json',settlement)
post={str(base):{n:digest(base/n) for n in expected} for base in (repo,mirror)}
assert all(values==expected for values in post.values())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==p['source_sha']
save('final-settlement-POST-inputs.json',post)
assert result['passed']==2 and result['exit_code']==0 and all(not result[k] for k in ('shared_pre_drift','mirror_pre_drift','shared_post_drift','mirror_post_drift'))
report=dict(source_sha=p['source_sha'],source_tree=p['source_tree'],tests_tree=p['tests_tree'],passed=2,failures=0,errors=0,skipped=0,blockers=0,P1=0,P2=0,static_blockers=0,automatic_retries=0,pytest_exit_code=0,outer_elapsed_seconds=result['elapsed_seconds'],pytest_reported_seconds=24.42,pytest_warnings=4,expected_nodes=expected_nodes,actual_unique_ids=ids,overlap_in_main6=2,all_two_overlap_main=True,counts_not_added_to_parent=True,input_count=762,shared_and_mirror_PREPOST_zero_drift=True,post_settlement_zero_drift=True,contracts=p['contracts'],module_origins=origin_validation,actual_handler_sequences=proofs,owned_settlement=settlement,static_review=dict(product_src_equal_baseline_c66=True,original_nonrace_test_prefix_equal=True,original_four_node_ids_and_old_first_semantics_preserved=True,observer_calls_original_once_with_this_and_event_and_returns_original_result=True,handler_promise_settlement_covers_awaited_recovery_catch_finally=True),scope=dict(actual='exact-byte Linux mirror, original tests, own isolated synthetic PG, ordinary configured_app subprocess, loopback HTTP, Chromium width320; one invocation of exactly two authorized nodes',synthetic_authority='fixture preparation/materials/review/confirm/exact Run assignment and receipt step before ordinary startup; not real authorities or zero-business whole chain',old403='existing wrong-fixture token transport injection into only old captured GET; not current executor revocation',state_observed=state_keys,state_not_observed=['all visible status/summary texts','recover/release button hidden properties','serialized context token'],context_identity='closure compares exact original object references without serializing token',post_trace='Browser request trace and route.fetch forwarded POST trace separately counted, one each; route.fetch is not in browser trace',business='Actual passed original assertions: Case history and authority unchanged, one SUBMIT, no ACK, service_case_plan absent; no adopted-P4 positive claim',budget='Original 2s connection, 5s DROP, 15s ordinary startup loop/15s HTTP health budgets and assertions unchanged',not_run=['Windows','real model/provider/source','real authority/identity','formal AT','adopted P4 positive','full browser module or historical full regression','real current revocation in these two nodes'],historical_unknowns='Prior startup UNKNOWNs from earlier slices retained; this passing bounded run does not explain them'),evidence_directory=str(r),temporary_directory=str(outer),raw_evidence=dict(invocation=str(r/'invocation.json'),stdout=str(r/'stdout.txt'),stderr=str(r/'stderr.txt'),junit=str(r/'independent.xml'),result=str(r/'run-result.json'),actual_ids=str(r/'actual-collected-nodeids.json'),phase_reports=str(r/'actual-phase-reports.json'),module_origins=str(r/'actual-pytest-module-origins.json'),overlap=str(r/'actual-overlap-validation.json'),handler_validation=str(r/'handler-sequence-validation.json'),process_settlement=str(r/'owned-process-settlement.json'),artifact_manifest=str(r/'case-artifact-manifest.json'),case_artifacts=str(r/'case-artifacts'),owned_pg_log=str(r/'owned-connection-diagnostics/postgres.log'),owned_connections=str(connpath)))
save('independent-final-review.json',report)
print(json.dumps(dict(report=str(r/'independent-final-review.json'),sha256=digest(r/'independent-final-review.json'),source_sha=p['source_sha'],passed=2,failures=0,errors=0,skipped=0,blockers=0,outer_elapsed_seconds=result['elapsed_seconds'],origin_modules=len(origins),overlap=2,independent_not_additive=True,shared_mirror_inputs=762,drift=0,contracts=6,owned_api_stopped=len(api),pg_data_remaining=len(pgpaths),observer_exited=True),indent=2))
