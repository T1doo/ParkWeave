from pathlib import Path
import ast,collections,datetime,hashlib,json,xml.etree.ElementTree as ET
import argparse
parser=argparse.ArgumentParser(description='Read-only new frozen34 verification; writes only new frontier-oracle-v2 evidence.')
parser.add_argument('--source-sha',required=True)
parser.add_argument('--execute-final-verification',action='store_true',required=True)
args=parser.parse_args()
assert len(args.source_sha)==40 and all(c in '0123456789abcdef' for c in args.source_sha)
R=Path('/workspace/ParkWeave');O=R/'.runtime/frontier-oracle-v2';OLD=R/'.runtime/frontier-oracle';B=R/'.runtime/frontier-root/v2/final';F=R/'.runtime/frontier-root/v2/freeze.json';SHA=args.source_sha
assert not (O/'writer-cessation-v1.json').exists(),'new primary already stopped; do not reopen'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return dict(path=str(p.relative_to(R)),sha256=digest(p),bytes=p.stat().st_size)
rec=json.loads((B/'frontier-independent.json').read_text());freeze=json.loads(F.read_text());assert rec['source_sha']==freeze['source_sha']==SHA
assert rec['counts']==dict(PASS=34,FAIL=0,ERROR=0,SKIP=0) and rec['exit_code']==0
assert not any(rec[k] for k in ('source_drift','all_tracked_drift','runner_drift'))
col=json.loads((B/'frontier-independent-collection.json').read_text());assert col==rec['collected_nodes'] and len(col)==len(set(col))==34
nodes=list(ET.parse(B/'frontier-independent.xml').getroot().iter('testcase'))
jkeys=[n.attrib['classname'].replace('.','/')+'.py::'+n.attrib['name'] for n in nodes]
assert jkeys==col and len(set(jkeys))==34
assert all(not any(n.find(kind) is not None for kind in ('failure','error','skipped')) for n in nodes)
A=B/'artifacts/frontier-independent';raw=sorted(p for p in A.rglob('*') if p.is_file());imports=sorted(A.rglob('actual-imports-*.json'));assert len(imports)==34
names={'business_frontier','business_frontier_types','case_resource_delivery','service_plan_approval','plan_replacement_compatibility','service_dispatches','executor_receipts','case_lifecycle'}
for p in imports:
 d=json.loads(p.read_text());assert set(d)==names
 for name,value in d.items():
  expected=R/'src/parkweave'/(name+'.py');assert Path(value['path']).resolve()==expected and value['sha256']==freeze['source_paths']['src/parkweave/'+name+'.py']==digest(expected)
rawdocs={p:json.loads(p.read_text()) for p in raw if p.suffix=='.json' and not p.name.endswith('.private.json') and not p.name.startswith('actual-imports-')}
def artifacts(prefix,action=None):
 return [ref(p) for p,d in rawdocs.items() if p.name.startswith(prefix+'-') and (action is None or d.get('action')==action)]
def find(*frags):return [n for n in col if any(f in n for f in frags)]
records=[]
for node,jnode in zip(col,nodes):
 module,function=node.split('::');function_name=function.split('[',1)[0]
 t=ast.parse((R/module).read_text());line=next(n.lineno for n in t.body if isinstance(n,ast.FunctionDef) and n.name==function_name)
 level=['ACTUAL_OWNED_PG_FIXTURE','TESTCLIENT_ASGI_HTTP_ORIGINAL_PRODUCT_COMMANDS'];e=[]
 if 'actual_insert_delete_aba' in node:e=artifacts('controlled-owner-effect-delete-aba');level+=['CONTROLLED_OWNER_SQL_INSERT_AND_DELETE_NOT_PUBLIC_DELETE_API']
 elif 'real_effect_and_marker_rollback' in node:e=artifacts('controlled-owner-transaction-rollback');level+=['CONTROLLED_OWNER_SQL_TRANSACTION_ROLLBACK']
 elif 'committed_late_effect_after_approve' in node:e=artifacts('controlled-late-owned-insert');level+=['CONTROLLED_OWNER_SQL_FAULT_BETWEEN_APPROVE_AND_COMMIT_NOT_P3_API']
 elif 'actual_get_old_intent' in node:e=artifacts('actual-asgi-late-intent-'+function.split('[')[1][:-1])
 elif 'pending_plan_does_not_erase' in node:e=artifacts('actual-asgi-resolved-offer-history',function.split('[')[1][:-1]);level+=['PG_COMPONENT_QUALIFY_REFUSAL_AFTER_REAL_OFFER_AND_RESOLVE']
 elif 'actual_committed_grant_false_true' in node:e=artifacts('grant-real-false-true');level+=['CONTROLLED_OWNER_TWO_COMMITTED_GRANT_TRANSITIONS']
 elif 'trigger_disable_enable_aba' in node:e=artifacts('ddl-trigger-committed-disable-enable-aba');level+=['CONTROLLED_OWNER_DDL_ABA']
 elif 'statement_truncate' in node:level+=['CONTROLLED_OWNER_SQL_TRUNCATE_REFUSED_BY_TRIGGER']
 elif 'explicit_approval_actual_five_verify' in node:e=artifacts('positive-current-history')+artifacts('full-goal-results')
 elif 'marker_cannot_be_removed' in node:level+=['CONTROLLED_OWNER_SQL_MARKER_REMOVAL_REFUSED']
 elif 'issued_protocol_missing' in node:level+=['CONTROLLED_SERVER_ATTACHMENT_UNAVAILABLE_NOT_QUERY_TRANSPORT_FAULT']
 elif 'real_pg_delivery_failure' in node:level+=['CONTROLLED_OWNER_SQL_FAULT_TRIGGER_ROLLBACK']
 elif 'two_transactions_same_captured_fence' in node:e=artifacts('p4-concurrent-original-same-fence');level+=['TWO_CONCURRENT_ORIGINAL_P4_REQUEST_TRANSACTIONS']
 records.append(dict(nodeid=node,result='PASS',junit=dict(path=str((B/'frontier-independent.xml').relative_to(R)),classname=jnode.attrib['classname'],name=jnode.attrib['name'],seconds=jnode.attrib['time']),source=dict(path=module,sha256=freeze['source_paths'][module],function_line=line),evidence_levels=level,explicit_raw_artifacts=e,common_import_evidence='final-import-provenance-v1.json; 34 unordered exact eight-module records, no fabricated per-node filename attribution'))
assert len(records)==34
# Independently bind actual raw PG observations; these are not extra test counts.
required_raw_fragments=('actual_insert_delete_aba','real_effect_and_marker_rollback','committed_late_effect_after_approve','actual_get_old_intent','pending_plan_does_not_erase','actual_committed_grant_false_true','trigger_disable_enable_aba','explicit_approval_actual_five_verify','two_transactions_same_captured_fence')
for row in records:
 if any(fragment in row['nodeid'] for fragment in required_raw_fragments):assert row['explicit_raw_artifacts'],row['nodeid']
p4=[doc for path,doc in rawdocs.items() if path.name.startswith('p4-concurrent-original-same-fence-')]
assert len(p4)==1 and p4[0]['statuses']==[200,409]
assert p4[0]['after']['counts']['service_step_receipts']==p4[0]['before']['counts']['service_step_receipts']+1
assert p4[0]['after']['counts']['service_receipt_events']==p4[0]['before']['counts']['service_receipt_events']+1
positive=[doc for path,doc in rawdocs.items() if path.name.startswith('positive-current-history-')]
goals=[doc for path,doc in rawdocs.items() if path.name.startswith('full-goal-results-')]
assert len(positive)==len(goals)==1
assert positive[0]['before']['marker']['epoch']==0 and positive[0]['before']['marker']['ever_started'] is False
assert not any(positive[0]['before']['counts'].values())
assert positive[0]['after']['marker']['epoch']>0 and positive[0]['after']['marker']['ever_started'] is True
assert goals[0]['state']=='LOCAL_OUTPUTS_VERIFIED' and len(goals[0]['results'])==6 and goals[0]['case_goal_completed'] is False
assert all(row['state']=='LOCAL_OUTPUT_VERIFIED' for row in goals[0]['results'])
expected_plugin=R/'.runtime/frontier-root/v2/runner/shared_capture.py';plugin=rec['capture_plugin_provenance']
assert Path(plugin['actual_path']).resolve()==expected_plugin==Path(plugin['expected_path']).resolve()
assert plugin['product_logic_patched'] is False and plugin['sha256']==digest(expected_plugin)==freeze['runner_paths'][str(expected_plugin.relative_to(R))]

(O/'final-node-evidence-v1.json').write_text(json.dumps(dict(source_sha=SHA,actual_nodes=records,common_window_files=[ref(B/('frontier-independent'+s)) for s in ('.json','.xml','.log','-collection.json')],raw_artifact_files=[ref(p) for p in raw if not p.name.endswith('.private.json')],no_native_network_http_or_browser_credit=True),indent=2)+'\n')
(O/'final-import-provenance-v1.json').write_text(json.dumps(dict(source_sha=SHA,records=len(imports),product_modules=sorted(names),all_actual_paths_main_frozen_source=True,all_hashes_match_freeze_and_current=True,files=[ref(p) for p in imports],freeze=ref(F),runner_count=len(freeze['runner_paths']),capture=rec['capture_plugin_provenance']),indent=2)+'\n')
# Original30-row design is not a 30-test suite. Rows can overlap actual nodes.
specs=[
('F01','EXECUTED_LIMITED',find('explicit_approval_actual_five_verify'),'Actual whole new five VERIFY/six local goals/worklist/immutable consumed cold reads. Python fixture/source preparation is not all HTTP; no formal Case completion.'),
('F02','NOT_RUN_HERE',[],'No preinstallation old-preparation/no-marker actual upgrade experiment in these34.'),
('F03','VARIANT',find('marker_cannot_be_removed','missing_or_wrong_explicit_business_fence'),'Two actual marker removal attempts refuse plus wrong captured scope fields. No complete forged-birth/issuer matrix.'),
('F04','EXECUTED_LIMITED',find('pending_plan_does_not_erase'),'Actual OFFER→DECLINE/WITHDRAW leaves current plan P3-P5 pending; original PG qualify component refuses. Occurs after new delivery, not an old pre-ADOPT quote fixture.'),
('F05','NOT_RUN_HERE',[],'Actual new ACCEPT exists in positive setup; no separate original old ACCEPT/no-submit replacement refusal experiment.'),
('F06','VARIANT',find('committed_late_effect_after_approve','actual_insert_delete_aba'),'Controlled fixture owner uses original _insert_step SQL; not successful legacy CREATE API.'),
('F07','NOT_RUN_HERE',[],'No original P5 REOPEN/cancellation/reconciliation-tail qualification experiment in these34.'),
('F08','VARIANT',find('issued_protocol_missing'),'Actual ASGI refuses missing issued protocol attachment. Query denial/omission/incomplete transport/schema type matrix not executed here.'),
('F09','NOT_RUN_HERE',[],'No separate old material/offer/receipt generation scope history experiment.'),
('F10','EXECUTED_LIMITED',find('actual_insert_delete_aba'),'Actual owner INSERT/DELETE separate committed transactions restore empty rows but epoch/ever-started remains; quote and approved commit refuse. Not public deletion authority.'),
('F11','EXECUTED',find('real_effect_and_marker_rollback'),'Actual PG effect+marker rollback, exact snapshots unchanged, subsequent new delivery/cold GET succeeds.'),
('F12','NOT_RUN_HERE',[],'No real old original OFFER committed between preview and PROPOSE.'),
('F13','NOT_RUN_HERE',[],'No real original OFFER committed between PROPOSE and APPROVE.'),
('F14','VARIANT',find('committed_late_effect_after_approve'),'Actual controlled owner original receipt-step insert between APPROVE/COMMIT refuses commit with no resource/consume effects; not P3 OFFER API.'),
('F15','VARIANT',find('two_transactions_same_captured_fence'),'Actual two P4 SUBMIT transactions same GET fence, distinct keys: one200/one409 and one receipt/event. Not replacement COMMIT-vs-OFFER wait orders.'),
('F16','EXECUTED_LIMITED',find('two_transactions_same_captured_fence'),'New tracked P4 UPDATE parent path actually no deadlock/timeout. Does not test legacy SHARE-upgrade path or every lock order.'),
('F17','VARIANT',find('trigger_disable_enable_aba'),'Actual committed trigger disable→ENABLE ALWAYS identity/xmin ABA loses issued continuity. Not all missing/wrong trigger/owner/function variants.'),
('F18','VARIANT',find('statement_truncate'),'Actual service_receipt_events TRUNCATE refuses, snapshots unchanged and later approval succeeds. Other eight watched/preparation TRUNCATE targets not executed here.'),
('F19','VARIANT',find('trigger_disable_enable_aba'),'Restored current trigger appearance still denied after committed DDL ABA. No effects during disabled gap or arbitrary superuser catalog forgery test.'),
('F20','NOT_RUN_HERE',[],'OLD/NEW reparented scope UPDATE not executed.'),
('F21','EXECUTED_LIMITED',find('other_owner_tenant_and_role'),'Four actual other identities/roles denied quote/propose/commit/historical recovery. No genuine every same-org different owner/other issuer fence cloning matrix.'),
('F22','EXECUTED_LIMITED',find('current_revocation_invalidates'),'Actual READ/EXECUTE/PREPARE/HOLD revocation and READ cold denial. Assigned reviewer/Run access variants not executed here.'),
('F23','EXECUTED',find('actual_committed_grant_false_true'),'Actual two committed EXECUTE false→true transitions leave new approved commit stale, no resource/consume effects.'),
('F24','VARIANT',find('explicit_approval_actual_five_verify','real_effect_and_marker_rollback'),'Actual cold original-key GET/replay preserves committed receipt. Response-loss injection/native HTTP/page recovery is NOT in these34.'),
('F25','VARIANT',find('explicit_approval_actual_five_verify'),'Identical same-key replay actually stable; same-key changed parameter/fence conflict not executed here.'),
('F26','NOT_RUN_HERE',[],'Original fully completed old-five-VERIFY path belongs to separate regressions. No score from running parent windows.'),
('F27','VARIANT',find('no_profile_downgrade'),'Actual missing/unknown frontier profile refuses incomplete old tail. No forged P1/P2 or persisted rehash matrix.'),
('F28','EXECUTED_LIMITED',find('explicit_approval_actual_five_verify'),'Six original local goals/five nodes, old history/old receipt and confirmed resource preservation. Manual lock/note, target withdrawal and general UNKNOWN matrix not executed here.'),
('F29','EXECUTED_LIMITED',find('real_pg_delivery_failure_rolls_back'),'Three actual owner fault triggers at original effect tables roll back new delivery/ledger/marker atomically; original holds remain HELD.'),
('F30','EXECUTED',find('explicit_approval_actual_five_verify','actual_get_old_intent'),'After real new tail changes epoch, consumed original receipt/current/historical reads still work. Forged immutable consumption-anchor faults not executed here.')]
original=json.loads((OLD/'oracle-design-v1.json').read_text());assert len(original['rows'])==30
coverage=[]
for ident,status,support,limit in specs:
 design=next(row for row in original['rows'] if row['id']==ident)
 coverage.append(dict(id=ident,original_design_name=design['name'],status=status,actual_nodeids=support,scope_and_limits=limit,evidence_reference='final-node-evidence-v1.json per exact nodeid; no inferred PASS for design row'))
late=[('LI01','NOT_RUN_HERE',[]),('LI02','EXECUTED_LIMITED',find('actual_get_old_intent_after_new_commit_p2_is_refused_but_fresh_allowed[old_plan_before_adopt]')),('LI03','VARIANT',find('actual_get_old_intent')),('LI04','EXECUTED_LIMITED',find('actual_get_old_intent_after_new_commit_p2_is_refused_but_fresh_allowed[new_plan_before_p2]')),('LI05','NOT_RUN_HERE',[]),('LI06','NOT_RUN_HERE',[]),('LI07','EXECUTED',find('actual_get_old_intent','explicit_approval_actual_five_verify')),('LI08','EXECUTED_LIMITED',find('missing_or_wrong_explicit_business_fence')),('LI09','NOT_RUN_HERE',[]),('LI10','NOT_RUN_HERE',[]),('LI11','NOT_RUN_HERE',[]),('LI12','VARIANT',find('missing_or_wrong_explicit_business_fence','other_owner_tenant_and_role'))]
(O/'final-design-coverage-v1.json').write_text(json.dumps(dict(source_sha=SHA,actual_test_count=34,design_status='Old primary original30 and late12 remain historical DESIGN_ONLY. Every supported node/raw/JUnit/import in this new map is independently rebound to this new V2 SHA/window; rows overlap and are not test counts.',original_design=ref(OLD/'oracle-design-v1.json'),coverage=coverage,status_counts=dict(collections.Counter(r['status'] for r in coverage)),late_intent_coverage=[dict(id=i,status=s,actual_nodeids=ns,limit='LI03 supports after-P2 only, no double-send before/after. LI12 arbitrary field mismatches and identity refusal, not real other-issuer forgery.') for i,s,ns in late],static_only=[ref(OLD/'evidence-contract-v1.md'),ref(OLD/'late-intent-fence-v1.md'),ref(OLD/'dispatch-get-cause-correction-v1.json'),ref(OLD/'static-adaptation-v1.json')],pure_standalone_tests_in_this34=0,not_run=['native socket HTTP or browser from these34','preexisting prep frontier support','Windows','formal AT','special PG27','real models','production','general in-flight migration','backup restore']),indent=2)+'\n')
# Preserve paths/hashes/modes for all private registrations in this producer and this completed window only.
shared=B/'redaction-frontier-independent.private.json';shared_values=set(json.loads(shared.read_text()));private=sorted(set([shared,*A.rglob('*.private.json')]))
private_rows=[]
assert len(list(A.rglob('*.private.json')))==34,'all34 fixture private registrations required'
for p in private:
 data=json.loads(p.read_text());assert isinstance(data,list);assert p.stat().st_mode&0o777==0o600
 formal=p==shared or A in p.parents
 if formal:assert set(data)<=shared_values
 else:raise AssertionError('unexpected private scope')
 private_rows.append(dict(**ref(p),mode='0600',entries=len(data),scope='FINAL34' if formal else 'PRIVATE_DEVELOPMENT1_NOT_TRANSFERRED',fully_registered=True))
(O/'final-private-registration-manifest-v1.json').write_text(json.dumps(dict(status='PRIVATE_VALUES_NOT_PRINTED_NO_VALUES_IN_THIS_MANIFEST',source_sha=SHA,files=private_rows,final_fixture_private_files=len(list(A.rglob('*.private.json'))),original_private_development_files=0),indent=2)+'\n')
# Check known legacy/default helper routes without manufacturing any external copies.
baseline=json.loads((R/'.runtime/frontier-root/baseline.json').read_text());stamp=datetime.datetime.fromisoformat(baseline['utc']).timestamp();oldcount=0;newer=[]
for root in (R/'.runtime').glob('plan-replacement*'):
 for p in root.rglob('*'):
  if p.is_file():
   oldcount+=1
   if p.stat().st_mtime>stamp:newer.append(str(p.relative_to(R)))
assert newer==[]
start=datetime.datetime.fromisoformat(rec['started_utc']).timestamp();end=datetime.datetime.fromisoformat(rec['finished_utc']).timestamp();external=[]
for root in (R/'.runtime/frontier-fixture',OLD/'artifacts',O/'artifacts'):
 if root.exists():
  for p in root.rglob('*'):
   if p.is_file() and start<=p.stat().st_mtime<=end:external.append(str(p.relative_to(R)))
assert not external
route=dict(source_sha=SHA,window_started_utc=rec['started_utc'],window_finished_utc=rec['finished_utc'],actual_artifact_root=str(A.relative_to(R)),artifact_files=len(raw),actual_import_records=len(imports),collection_artifact_paths=json.loads((B/'frontier-independent-collection-artifact-paths.json').read_text()),externalcopyselection=[],external_copy_files_created=0,external_helper_default_paths_searched=['.runtime/frontier-fixture','.runtime/frontier-oracle/artifacts','.runtime/frontier-oracle-v2/artifacts','.runtime/plan-replacement*'],external_files_found=external,old_planreplacement_files_checked=oldcount,old_planreplacement_newer_than_baseline=[],baseline_utc=baseline['utc'],limitation='Search concerns this independent window and known helper routes, not unrelated running parent windows or the entire machine.')
(O/'final-artifact-routing-v1.json').write_text(json.dumps(route,indent=2)+'\n')
result=dict(status='FRESH_V2_FROZEN_FINAL_INDEPENDENT34_PASS_LIMITED_SCOPE',source_sha=SHA,receipt=ref(B/'frontier-independent.json'),counts=rec['counts'],elapsed_seconds=rec['elapsed_seconds'],started_utc=rec['started_utc'],finished_utc=rec['finished_utc'],source_paths=rec['tracked_source_paths'],all_tracked_paths=rec['all_tracked_paths'],runner_paths=len(freeze['runner_paths']),source_drift=[],all_tracked_drift=[],runner_drift=[],junit_unique_exact=True,actual_import_records=34,product_imports_each_record=8,all_imports_actual_frozen_hash_current=True,evidence_files=[ref(O/n) for n in ['final-node-evidence-v1.json','final-import-provenance-v1.json','final-design-coverage-v1.json','final-private-registration-manifest-v1.json','final-artifact-routing-v1.json']],private_race1='OLD_PRIVATE_DEVELOPMENT_AND_B1_RESULTS_NOT_USED_OR_ADDED_TO_NEW34',parent_other_windows='RUNNING_RESULTS_NOT_IMPORTED',externalcopyselection=[],active_tests_owned_by_oracle=0)
(O/'final-independent-result-v1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['status','source_sha','counts','elapsed_seconds','source_paths','all_tracked_paths','runner_paths','junit_unique_exact','actual_import_records','externalcopyselection']}))
