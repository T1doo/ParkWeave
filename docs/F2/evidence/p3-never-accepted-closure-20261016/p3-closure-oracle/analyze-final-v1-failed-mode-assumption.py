from pathlib import Path
import ast,datetime,hashlib,json,stat,xml.etree.ElementTree as ET
R=Path('/workspace/ParkWeave');O=R/'.runtime/p3-closure-oracle';B=R/'.runtime/p3-closure-root/v1/final';F=B.parent/'freeze.json'
SHA='c91bbea1e996c6608665bb76dd65218f2ba542c2';FH='0cb02845b4fc4d564e5e1e03a3d696b2d1200c88e660dd8803d9d6f3cda67e20'
assert not (O/'writer-cessation.json').exists()
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return dict(path=str(p.relative_to(R)),sha256=digest(p),bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns)
def write(name,value):(O/name).write_text(json.dumps(value,indent=2)+'\n')
freeze=json.loads(F.read_text());assert digest(F)==FH and freeze['source_sha']==SHA
names={'p3_never_accepted_closure','business_frontier','business_frontier_types','service_dispatches','executor_receipts','case_resource_delivery','plan_replacement_compatibility','service_plan_approval'}
records=[];windows=[];rawdocs={};private=[];imports=[];routes=[]
for window,count in [('p3-independent',35),('p3-races-solo',2)]:
 rec=json.loads((B/(window+'.json')).read_text());col=json.loads((B/(window+'-collection.json')).read_text());j=list(ET.parse(B/(window+'.xml')).getroot().iter('testcase'))
 assert rec['source_sha']==SHA and rec['counts']==dict(PASS=count,FAIL=0,ERROR=0,SKIP=0) and rec['exit_code']==0
 assert all(not rec[k] for k in ('source_drift','all_tracked_drift','runner_drift'))
 actual=[x.attrib['classname'].replace('.','/')+'.py::'+x.attrib['name'] for x in j]
 assert actual==col==rec['collected_nodes'] and len(set(col))==count
 assert all(not any(x.find(k) is not None for k in ('failure','error','skipped')) for x in j)
 A=B/'artifacts'/window;raw=sorted(p for p in A.rglob('*') if p.is_file());im=sorted((A/'p3-oracle').glob('actual-imports-*.json'));assert len(im)==count
 for p in im:
  d=json.loads(p.read_text());assert set(d)==names
  for n,row in d.items():
   expected=R/'src/parkweave'/(n+'.py');assert Path(row['path']).resolve()==expected and row['sha256']==freeze['source_paths']['src/parkweave/'+n+'.py']==digest(expected)
 imports+=im
 pfiles=[p for p in raw if p.name.endswith('.private.json')]+[B/('redaction-'+window+'.private.json')]
 registry=json.loads(pfiles[-1].read_text());assert isinstance(registry,list) and all(isinstance(v,str) for v in registry)
 for p in pfiles:
  d=json.loads(p.read_text());assert stat.S_IMODE(p.stat().st_mode)==0o600 and isinstance(d,list) and all(isinstance(v,str) for v in d)
  assert set(d)<=set(registry)
  private.append({**ref(p),'mode':'0600','registered_values_count':len(d),'all_values_in_window_capture_registry':True})
 for p in raw:
  if p.suffix=='.json' and not p.name.endswith('.private.json') and not p.name.startswith('actual-imports-'):rawdocs[p]=json.loads(p.read_text())
 plugin=rec['capture_plugin_provenance'];pp=Path(plugin['actual_path']);assert pp==Path(plugin['expected_path']) and plugin['product_logic_patched'] is False
 assert digest(pp)==plugin['sha256']==freeze['runner_paths'][str(pp.relative_to(R))]
 common=[ref(B/(window+s)) for s in ('.json','.xml','.log','-collection.json','-collection-plugin-provenance.json','-collection-artifact-paths.json')]
 for node,x in zip(col,j):
  module,func=node.split('::');tree=ast.parse((R/module).read_text());line=next(n.lineno for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==func.split('[')[0])
  levels=['ACTUAL_OWNED_POSTGRESQL_FIXTURE','TESTCLIENT_ASGI_ORIGINAL_PRODUCT_COMMANDS']
  if 'controlled_owner_history_damage' in node:levels+=['CONTROLLED_OWNER_SQL_FAULT','PG_COMPONENT_QUALIFY_REFUSAL_NOT_PUBLIC_HISTORY_EDIT_API']
  if 'original_dispatch_transaction_rolls_back' in node:levels+=['CONTROLLED_OWNER_OUTBOX_FAULT_TRIGGER_REAL_ORIGINAL_COMMAND_ROLLBACK']
  if 'parent_wait' in node:levels+=['REAL_PARENT_LOCK_WAIT_TWO_HTTP_REQUEST_TRANSACTIONS']
  if any(s in node for s in ('offered_requires','no_dispatch_history','real_reoffer_revives','any_actual_acceptance')):levels+=['PG_COMPONENT_QUALIFY_ASSERTIONS']
  records.append(dict(nodeid=node,window=window,result='PASS',junit=dict(file=str((B/(window+'.xml')).relative_to(R)),**x.attrib),source=dict(path=module,sha256=freeze['source_paths'][module],function_line=line),evidence_levels=levels,common_window_evidence=common,raw_association='Function-family artifacts below; UUID-named imports have no fabricated one-to-one node attribution'))
 windows.append(dict(name=window,receipt=ref(B/(window+'.json')),counts=rec['counts'],elapsed_seconds=rec['elapsed_seconds'],started_utc=rec['started_utc'],finished_utc=rec['finished_utc'],source_drift=[],all_tracked_drift=[],runner_drift=[],source_paths=rec['tracked_source_paths'],all_tracked_paths=rec['all_tracked_paths']))
 routes.append(dict(window=window,actual_artifact_root=str(A.relative_to(R)),oracle_route=str((A/'p3-oracle').relative_to(R)),fixture_route=str((A/'p3-closure').relative_to(R)),raw_files=len(raw),actual_import_records=len(im),collection_artifact_paths=json.loads((B/(window+'-collection-artifact-paths.json')).read_text()),externalcopyselection=[]))
assert len(records)==37 and len(set(x['nodeid'] for x in records))==37 and len(imports)==37

def artifacts(prefix):return [ref(p) for p in rawdocs if p.name.startswith(prefix+'-')]
def nodes(fragment):return [x['nodeid'] for x in records if fragment in x['nodeid']]
# Actual raw business observations, not additional test counts.
positive=[d for p,d in rawdocs.items() if p.name.startswith('closed-profile-full-chain-')];assert len(positive)==4
assert sorted((d['mode'],d['qualification']['dispatch']['offers_count']) for d in positive)==[('DECLINE',1),('DECLINE',3),('WITHDRAW',1),('WITHDRAW',3)]
for d in positive:
 q=d['qualification'];assert len(q)==19 and q['profile']=='P3_NEVER_ACCEPTED_CLOSED_V1' and q['ever_started'] is True and q['epoch']>0
 assert q['closure_state']=={'DECLINE':'DECLINED','WITHDRAW':'WITHDRAWN'}[d['mode']] and d['cold_get_did_not_write'] is True
 assert q['epoch']==3*q['dispatch']['revision'] and len(q['dispatch']['events'])==q['dispatch']['revision']
goals=[d for p,d in rawdocs.items() if p.name.startswith('new-six-local-goal-results-')];assert len(goals)==4
assert all(d['state']=='LOCAL_OUTPUTS_VERIFIED' and len(d['results'])==6 and d['case_goal_completed'] is False and all(g['state']=='LOCAL_OUTPUT_VERIFIED' for g in d['results']) for d in goals)
for p,d in rawdocs.items():
 if p.name.startswith('original-parent-wait-'):
  first=d['intended_first'];other='WITHDRAW' if first=='ACCEPT' else 'ACCEPT';assert d['statuses']=={first:200,other:409}
  assert set(d['observed_waits'])=={'ACCEPT','WITHDRAW'} and all(d['observed_waits'].values())
  assert all(row['blockers'] for waits in d['observed_waits'].values() for row in waits)
  assert 'captured original business frontier changed' in json.dumps(d['loser_response'])
 if p.name.startswith('original-dispatch-rollback-'):assert d['rollback_exact_snapshot'] is True and d['expected_fault']
 if p.name.startswith('newcommit-old-intent-'):assert d['status']==409 and d['read_only_cold_receipt_preserved'] is True
# Bind function-family raw records; parameter-specific raw UUIDs are not guessed.
family=[('actual_mode_history','closed-profile-full-chain'),('actual_mode_history','new-six-local-goal-results'),('offered_requires','offered-explicit-withdraw'),('real_reoffer_revives','real-reoffer-then-explicit-reclosure'),('new_adopt_p1','new-plan-p2-pending-original-gate'),('any_actual_acceptance','actual-acceptance-refuses-closure-with-receipt-preserved')]
for row in records:
 e=[]
 for f,prefix in family:
  if f in row['nodeid']:e+=artifacts(prefix)
 for val in ('delete_event','delete_restore_event','payload_fence_boolean','request_key'):
  if 'controlled_owner_history_damage' in row['nodeid'] and '['+val+'-' in row['nodeid']:e+=artifacts('controlled-owner-history-'+val)
 for val in ('OFFER','REOFFER','WITHDRAW'):
  if 'original_dispatch_transaction_rolls_back' in row['nodeid'] and '-'+val+']' in row['nodeid']:e+=artifacts('original-dispatch-rollback-'+val.lower())
 for val in ('old_offer','old_accept','old_resolution','newplan_preP2_offer'):
  if 'old_actual_captured_intents' in row['nodeid'] and '['+val+']' in row['nodeid']:e+=artifacts('newcommit-old-intent-'+val)
 for val in ('ACCEPT','WITHDRAW'):
  if 'parent_wait' in row['nodeid'] and '['+val+'-' in row['nodeid']:e+=artifacts('original-parent-wait-'+val.lower())
 row['explicit_raw_artifacts']=e
write('final-node-evidence-v1.json',dict(source_sha=SHA,nodes=records,raw_nonprivate_files=[ref(p) for p in rawdocs],scope='Exactly37; Python fixture/catalog setup is not browser/native socket HTTP evidence'))
write('final-import-provenance-v1.json',dict(source_sha=SHA,records=37,modules_each=8,names=sorted(names),all_actual_paths_main_frozen_source=True,all_hashes_match_current_and_freeze=True,files=[ref(p) for p in imports]))
write('final-private-registration-manifest-v1.json',dict(source_sha=SHA,files=private,all_private_600=True,token_values_printed=False,scope='Only the two final independent windows; no unrelated running parent window registries'))
# Design rows overlap; never add 32 design rows to the37 nodes.
mapdata={
'PC01':('EXECUTED_LIMITED','actual_mode_history','WITHDRAW cycles1/3; Python source setup, original TestClient commands.'),
'PC02':('EXECUTED_LIMITED','actual_mode_history','DECLINE cycles1/3 retains literal state/action.'),
'PC03':('EXECUTED_LIMITED','actual_mode_history','One and three cycles only, not max bound.'),
'PC04':('EXECUTED_LIMITED','offered_requires','Real OFFER then explicit WITHDRAW; qualification component refusal.'),
'PC05':('EXECUTED_LIMITED','no_dispatch_history','Zero dispatch closure claim refused by PG component.'),
'PC06':('VARIANT','any_actual_acceptance','Actual ACCEPT preserved receipt and refusal; no later resolved/deleted receipt variant.'),
'PC07':('VARIANT','any_actual_acceptance','Actual ACCEPT/CREATE refusal; no independent SUBMIT/P5-only/deleted-tail matrix.'),
'PC08':('EXECUTED_LIMITED','controlled_owner_history_damage','Owner delete-event fault; component refusal.'),
'PC09':('NOT_RUN_HERE','','No missing-offer/root/foreign-membership mutation in these37.'),
'PC10':('VARIANT','controlled_owner_history_damage','Actual raw xmin/payload/marker replay in positives; fence bool/request-key mutations only, not all actor/action axes.'),
'PC11':('EXECUTED_LIMITED','actual_mode_history','Exact19/15/14 shape and raw native marker/event checks; not every individual checkpoint independently fault-injected.'),
'PC12':('EXECUTED_LIMITED','delete_restore_event','Owner actual delete+restore committed ABA, component refuses.'),
'PC13':('NOT_RUN_HERE','','No protocol DDL/replication/TRUNCATE ABA experiment in these37.'),
'PC14':('NOT_RUN_HERE','','Positive dual pre-birth installation is not negative backfill/resnapshot test.'),
'PC15':('EXECUTED_LIMITED','parent_wait_accept_withdraw_both_orders[ACCEPT','Real queued parent lock; ACCEPT200/WITHDRAW409; receipt preserved.'),
'PC16':('EXECUTED_LIMITED','parent_wait_accept_withdraw_both_orders[WITHDRAW','Real queued parent lock; WITHDRAW200/ACCEPT409; no receipt; qualifies.'),
'PC17':('EXECUTED_LIMITED','real_reoffer_revives','Real REOFFER before adoption then explicit new WITHDRAW digest.'),
'PC18':('EXECUTED_LIMITED','new_adopt_p1','New ADOPT/P1, pendingP2 original REOFFER409 no writes.'),
'PC19':('EXECUTED_LIMITED','old_actual_captured_intents','Four captured stale bodies409 after newCOMMIT/P2; fresh tail in positive nodes.'),
'PC20':('VARIANT','wrong_preview_summary_binding','Wrong expected source SHA/plan revision refused, not actual post-approval source/epoch writer.'),
'PC21':('EXECUTED_LIMITED','rolls_back_after_real_event_before_notice[closure_case2-WITHDRAW','Outbox post-event fault; actual original WITHDRAW rollback.'),
'PC22':('EXECUTED_LIMITED','original_dispatch_transaction_rolls_back','OFFER/REOFFER post-event fault; real rollback.'),
'PC23':('NOT_RUN_HERE','','No resource COMMIT/nativeanchor fault rollback in these37.'),
'PC24':('EXECUTED_LIMITED','actual_mode_history','Old/new resource keys and Approval cold GET exact readonly; no generic P3 request-key GET invented.'),
'PC25':('EXECUTED_LIMITED','actual_mode_history','Original resource samekey replay and four changed-parameter conflicts.'),
'PC26':('EXECUTED_LIMITED','actual_mode_history','Old native closed prefix remains readable after fresh new ACCEPT/fulltail.'),
'PC27':('EXECUTED_LIMITED','other_identity','Other fixture principals/wrong reviewer/executor quote/propose/COMMIT/oldreceipt deny.'),
'PC28':('VARIANT','current_revocation','Six current capability revocations; no false-true ABA/Run authority experiment.'),
'PC29':('EXECUTED_LIMITED','profile_never_downgrades','None/KNS/UNKNOWN profile requests refuse.'),
'PC30':('EXECUTED_LIMITED','actual_mode_history','Six local goals/worklist/old confirmed holds/events preserved; no complete manual-decision mutation matrix.'),
'PC31':('VARIANT','controlled_owner_history_damage','Actual missing event and full positive bounded history; no overflow/query-denied/incomplete transport tests.'),
'PC32':('NOT_RUN_HERE','','Root separate regressions excluded; original zero/full5 modules are not these37.')}
original=json.loads((O/'oracle-design-v1.json').read_text());coverage=[]
for d in original['rows']:
 status,fragment,note=mapdata[d['id']];ns=nodes(fragment) if fragment else []
 assert ns or status=='NOT_RUN_HERE',(d['id'],fragment)
 coverage.append(dict(id=d['id'],name=d['name'],design_status='DESIGN_ONLY_SPECIFICATION_UNCHANGED',actual_status=status,nodeids=ns,limits=note))
write('final-design-coverage-v1.json',dict(source_sha=SHA,design=ref(O/'oracle-design-v1.json'),rows=coverage,actual_unique_nodes=37,design_rows_not_added_to_test_counts=True,scope='Finite37 only; no backend/core/HTML/Chrome/development/old frontier scores transferred'))
external=[]
for p in (O/'artifacts',R/'.runtime/p3-closure-root/dev-artifacts'):
 if p.exists():
  for f in p.rglob('*'):
   if f.is_file() and any(datetime.datetime.fromisoformat(w['started_utc']).timestamp()<=f.stat().st_mtime<=datetime.datetime.fromisoformat(w['finished_utc']).timestamp() for w in windows):external.append(str(f.relative_to(R)))
assert not external
write('final-artifact-routing-v1.json',dict(source_sha=SHA,windows=routes,externalcopyselection=[],external_copy_files_created=0,known_default_paths_searched=[str(O.relative_to(R))+'/artifacts','.runtime/p3-closure-root/dev-artifacts'],external_files_found=[],scope='Only known output routes for these37; all actual raw stays in root primary; no fabricated external copy'))
write('final-independent-result-v1.json',dict(status='FRESH_FROZEN_37_PASS_LIMITED_SCOPE',source_sha=SHA,freeze=ref(F),counts=dict(PASS=37,FAIL=0,ERROR=0,SKIP=0),windows=windows,unique_collection_junit_match=True,actual_import_records=37,product_imports_each_record=8,all_imports_actual_frozen_current=True,private_registration_files=len(private),all_private_600=True,externalcopyselection=[],active_tests_owned_by_oracle=0,parent_other_windows='RUNNING_EXCLUDED',development_results='NOT_TRANSFERRED'))
print(json.dumps(dict(status='VERIFIED_EXACT37',source_sha=SHA,actual_import_records=len(imports),private_registries=len(private),externalcopyselection=[])))
