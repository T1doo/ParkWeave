from pathlib import Path
import json,hashlib,xml.etree.ElementTree as ET
root=Path('/workspace/ParkWeave');base=root/'.runtime/plan-replacement-root/v4/final';out=root/'.runtime/plan-replacement-oracle'
receipt=json.loads((base/'replacement-independent.json').read_text())
assert receipt['source_sha']=='2dd98b67d52746dcdc3f358d2d60042cbea93909'
assert receipt['counts']=={'PASS':30,'FAIL':0,'ERROR':0,'SKIP':0}
assert receipt['exit_code']==0 and receipt['collection_junit_exact_match'] and receipt['unique_junit_nodes']
assert not any(receipt[k] for k in ('source_drift','all_tracked_drift','runner_drift'))
assert len(receipt['collected_nodes'])==30
nodes=receipt['collected_nodes']
def matching(*fragments):return [n for n in nodes if any(f in n for f in fragments)]
rows=[
 ('RP01','EXECUTED','test_independent_explicit_new_approval','TestClient HTTP ASGI plus owned PG; includes six goals, worklist and exact historical receipts. No native socket/browser credit.'),
 ('RP02','EXECUTED_LIMITED','test_independent_explicit_new_approval','Three exact selected pairs; original finite COMPATIBLE/new Case NEEDS_RECHECK title-only fixture. Only original known completed business chain.'),
 ('RP03','VARIANT','test_independent_explicit_new_approval','Unapproved new delivery refused. No separate saved BREAKING observation to new approval experiment in this window.'),
 ('RP04','EXECUTED','test_independent_replacement_mode','Includes original consumed Approval reuse, bad old/new plan IDs and profile stripping.'),
 ('RP05','VARIANT','test_independent_other_current_identity','Four other identities, owner/tenant/role boundaries. Does not claim every same-owner different Case scenario.'),
 ('RP06','EXECUTED_LIMITED','test_independent_new_approved_replacement_checks_live_authority','Original READ/EXECUTE/HOLD/PREPARE revocation; READ cold result denial. Limited fixture actors.'),
 ('RP07','VARIANT','test_original_two_committed_grant_transitions','Genuine committed EXECUTE false-to-true ABA. Other module covers revision-only authority and catalog xmin variants. Material ABA not executed here.'),
 ('RP08','VARIANT','test_original_withdrawn_target','Current target withdrawal and repeated original directory/preflight/quote/approval reads cannot revive. Original opportunity REFRESH command and source validity expiry not executed here; pure contract rejection separate.'),
 ('RP09','VARIANT','test_independent_actual_saved_snapshots_finite_compare','Actual three-pair snapshots in fixtures; pure second resource contract and frozen registry fault probes. Not a forged persisted new approved target experiment.'),
 ('RP10','NOT_RUN_HERE',None,'Original active-lock and preexisting manual amendment full replacement refusals require separate original regression evidence.'),
 ('RP11','EXECUTED_LIMITED','test_independent_explicit_new_approval','Exact old stored plan except original history flattening, original ledger prefix, historical receipt and original confirmed resources preserved. New plan/steps IDs differ.'),
 ('RP12','VARIANT','test_independent_explicit_new_approval','Old three holds remain CONFIRMED; new three confirm. No dedicated new-mode concurrent capacity stealing experiment here.'),
 ('RP13','EXECUTED','test_independent_atomic_replacement_fault','Actual owned PG trigger faults in three original effect tables; original effects, HELD states and approval ledger unchanged.'),
 ('RP14','VARIANT','test_independent_explicit_new_approval','Original-key replay, four changed parameters and cold GET. Actual lost-response frontend recovery is a separate HTML/browser window.'),
 ('RP15','VARIANT','test_independent_replacement_mode','Adjacent previous/new plan and link fences. Repeated full-plan replacements not executed in this window.'),
 ('RP16','NOT_RUN_HERE',None,'Rehashed new persisted approval profile corruption across all four original reads not executed in this window; no source-profile score transfer.'),
 ('RP17','NOT_RUN_HERE',None,'Client late results/ABA need separate controlled JS/HTML/browser evidence.'),
 ('RP18','EXECUTED_LIMITED','test_independent_later_explicit_owner_note','Legal completed original tail then EDIT_NOTE preserves exact consumed receipt with exact resource CURRENT, CONFIRMED holds, actual note text, six-goal set, resource effects and raw approval ledger unchanged. Resource currentness does not claim overall Case completion. TEMPLATE_UPGRADE not executed here.'),
 ('RP19','VARIANT','test_independent_only_explicit_new_flag','Source-reapproval-only scope refuses new replacement quote; no constructor type matrix credit here.'),
 ('RP20','NOT_RUN',None,'Dedicated PG27, Windows, formal AT, real product models and production remain NOT_RUN.')]
coverage=[]
for rid,status,fragment,limit in rows:
 support=matching(fragment) if fragment else []
 assert not fragment or support,(rid,fragment)
 coverage.append(dict(id=rid,status=status,actual_nodes=support,scope_and_limits=limit))
extra=dict(original_unfinished_chain=matching('test_original_unfinished_business_chain'),grant_real_value_ABA=matching('test_original_two_committed_grant_transitions'),withdrawal_read_refresh=matching('test_original_withdrawn_target'))
assert all(extra.values())
report=dict(schema=1,status='FORMAL_V4_30_PASS_LIMITED_SCOPE',source_sha=receipt['source_sha'],receipt='plan-replacement-root/v4/final/replacement-independent.json',counts=receipt['counts'],collection_exact=True,source_paths=receipt['tracked_source_paths'],all_tracked_paths=receipt['all_tracked_paths'],drift=dict(source=receipt['source_drift'],tracked=receipt['all_tracked_drift'],runner=receipt['runner_drift']),design_oracle_unchanged='oracle-v1.json remains DESIGN_ONLY_NOT_EXECUTED; this separate map is actual evidence with explicit limits',coverage=coverage,extra=extra,failed_windows_preserved=['baseline-v1/fixture-run.log through fixture-run4.log','attempt-01 setup failure','attempt-02 interrupted first six-goal FAIL and teardown error','diagnostic setup errors and real material-proof FAIL','attempt-03 complete 26 PASS / 1 note-prerequisite fixture FAIL','plan-replacement-root/final/replacement-independent: eaa2 source complete 29 PASS / 1 helper alias FAIL','plan-replacement-root/v2/final/replacement-independent: 06fd source complete 29 PASS / 1 incorrect NEEDS_RECHECK status oracle FAIL'],actual_window_files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [base/'replacement-independent.json',base/'replacement-independent.xml',base/'replacement-independent.log',base/'replacement-independent-collection.json']})
(out/'formal-v4-result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('status','source_sha','counts','source_paths','all_tracked_paths','drift')}))
