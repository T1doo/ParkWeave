"""Independent frozen review closure, raw evidence only; no business execution."""
from collections import Counter
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET
ROOT=Path('/workspace/ParkWeave');HERE=Path(__file__).resolve().parent
SHA='f686adafe3cec9b2820c10fada51ef2f57a559a6'
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
ORACLE=ROOT/'docs/F2/NoteTemplateCarryReviewOracles-20261015.json'
ORACLE_SHA='7ab53d8465e4344a2a7a5f6cb39aacdcfdd09b306629c97687c07690ae84d14c'
# Fields: independent literal ID, dynamic extent, exact scenario limitation, node-name fragments.
MAPPINGS=[
('NC01','VARIANTS_ONLY','A six-goal title-only carry proven; identical initial B positive control not created.', ['test_literal_title_or_template_source_carry_and_original_verification[1]']),
('NC02','VARIANTS_ONLY','Title-only instead of description-only; actual P1/P3 locked whole steps exact.', ['test_complete_original_html_carry_to_six_goals_and_worklist[title_locked]']),
('NC03','NAMED_SCENARIO','Actual template source change all five invalidated, old evidence retained, original five VERIFY and six outputs.', ['test_literal_title_or_template_source_carry_and_original_verification[2]','test_complete_original_html_carry_to_six_goals_and_worklist[source_changed]']),
('NC04','VARIANTS_ONLY','Actual P1 affected lock blocks projection; downstream P3 is separately actual apply refusal.', ['test_old_apply_cannot_carry_note_and_affected_lock_still_requires_unlock']),
('NC05','NAMED_SCENARIO','Actual P3 lock refuses, original UNLOCK and fresh check/choice then succeeds.', ['test_affected_lock_requires_original_unlock_and_fresh_carry']),
('NC06','VARIANTS_ONLY','Actual new material refuses old complete carry. Separate five-goal legacy fixture executes material MERGE/localADOPT/business revalidation/VERIFY then carry.', ['test_actual_new_material_cannot_reuse_prior_carry_or_manual_decision','test_real_v2_material_continue_first_carry_then_edit_reconfirm_next_hop']),
('NC07','NOT_RUN','New carry attempted after specific KEEP_MANUAL/DEFER records not dynamically exercised; original note blockers statically retained.', []),
('NC08','VARIANTS_ONLY','Real v2 continuation, post-carry EDIT, explicit current-card REFRESH/reconfirmation, next-hop and first-key GET. No intervening carry rejection directly asserted.', ['test_real_v2_material_continue_first_carry_then_edit_reconfirm_next_hop']),
('NC09','NOT_RUN','Prior material v2 continuation plus new template-source-changing carry combination not executed; separate new-template-source and v2-title branches are not this exact combination.', []),
('NC10','VARIANTS_ONLY','Actual current catalog kind UNKNOWN refuses existing complete carry; not every material/baseline UNKNOWN variant.', ['test_actual_catalog_unknown_refuses_existing_complete_request']),
('NC11','NOT_RUN','All listed non-MANUAL/absent/multi-slot/wrong-P1/partial variants for new route not dynamically executed; static narrow _manual/full-plan gates reviewed.', []),
('NC12','VARIANTS_ONLY','Actual finite goal/step strengthening and mandatory goal removal refuse note carry; arbitrary reorder/registry variants not executed.', ['test_registered_structural_strengthening_still_refuses_manual_carry[structure_initial]','test_breaking_target_never_discards_manual']),
('NC13','NOT_RUN','Exact same/equal/older/foreign-service/scope/instance target matrix for new route not executed; forward/scope gates statically retained.', []),
('NC14','VARIANTS_ONLY','Legal actual WITHDRAW and newer published head; not unreviewed/expiry/final-wait variants.', ['test_current_target_head_cannot_reuse_old_carry[withdraw]','test_current_target_head_cannot_reuse_old_carry[supersede]']),
('NC15','VARIANTS_ONLY','Owned-PG whole note plan A-B-A fault injection, not lawful EDIT then restore command sequence.', ['test_owned_pg_aba_rejects_same_visible_state[note]']),
('NC16','VARIANTS_ONLY','Actual owned-PG material row ABA, not arbitrary SQLite restoration/catalog matrix.', ['test_owned_pg_aba_rejects_same_visible_state[material]','test_actual_committed_aba_refuses_old_carry_without_writes[material]']),
('NC17','VARIANTS_ONLY','Actual scoped action case.create grant withdraw/restore ABA; capability/preparation ABA combinations not added.', ['test_owned_pg_aba_rejects_same_visible_state[action_grant]','test_actual_committed_aba_refuses_old_carry_without_writes[action_grant]']),
('NC18','VARIANTS_ONLY','Owned-PG parent plan and preparation epoch ABA; no principal-token/UI-generation ABA new-carry HTML execution.', ['test_owned_pg_aba_rejects_same_visible_state[parent]','test_actual_committed_aba_refuses_old_carry_without_writes[preparation]']),
('NC19','VARIANTS_ONLY','Current READ/PREPARE/EXECUTE withdrawal refuses both replay and recovery403; separately persistent case.create withdrawal not executed.', ['test_current_authority_precedes_original_receipt[READ]','test_current_authority_precedes_original_receipt[PREPARE]','test_current_authority_precedes_original_receipt[EXECUTE]']),
('NC20','VARIANTS_ONLY','Other owner/org and park actors403, not same-owner cross-instance/Case key replay matrix.', ['test_carry_owner_and_tenant_boundaries[fixture-b]','test_carry_owner_and_tenant_boundaries[fixture-c]']),
('NC21','NAMED_SCENARIO','Exact same actor/key/body replay immutable event with full snapshot unchanged.', ['test_idempotency_conflict_and_cold_original_get']),
('NC22','VARIANTS_ONLY','Changed reason same-key409; no concurrent exact-key new carry race or every changed parameter.', ['test_idempotency_conflict_and_cold_original_get']),
('NC23','NAMED_SCENARIO','Actual source_changed carry commit response dropped; fresh VM GET original key validates typed proof, original five VERIFY then six goals/worklist.', ['test_complete_original_html_carry_to_six_goals_and_worklist[source_changed]']),
('NC24','VARIANTS_ONLY','Actual committed transport-loss path and cold GET only. Malformed/5xx/NOT_OBSERVED/opaque409 pending-handle variants not executed. Original409/422 clears in-memory pending but retains key input; original protocol unchanged.', ['test_complete_original_html_carry_to_six_goals_and_worklist[source_changed]']),
('NC25','NOT_RUN','New carry final-wait expiry/revocation seam not executed. Pre-send withdrawal/authorization refusals are separate narrower evidence; old generic lease regression cannot substitute exact new-route seam.', []),
('NC26','NAMED_SCENARIO','Marker confirms actual PG plan UPDATE before fault, transaction and note/history/business snapshot exact, coldNOT_OBSERVED.', ['test_real_pg_save_fault_rolls_back_note_and_migration']),
('NC27','NAMED_SCENARIO','Actual title-only63 to64 no locks.', ['test_new_carry_exact_apply_verify_unlock_budget[1-63-False-True]']),
('NC28','NAMED_SCENARIO','Actual title-only62 one lock apply63 then original UNLOCK64; title63 one lock rejects atomically.', ['test_new_carry_exact_apply_verify_unlock_budget[1-62-True-True]','test_new_carry_exact_apply_verify_unlock_budget[1-63-True-False]']),
('NC29','NAMED_SCENARIO','Actual source-changing58 apply59 plus five original VERIFY64; at59 rejects before event.', ['test_new_carry_exact_apply_verify_unlock_budget[2-58-False-True]','test_new_carry_exact_apply_verify_unlock_budget[2-59-False-False]']),
('NC30','NAMED_SCENARIO','Actual original REFRESH reaches128; carry succeeds and adds zero opportunity events, full ledger exact.', ['test_new_carry_does_not_consume_any_129th_opportunity_event']),
('NC31','NAMED_SCENARIO','Legal EDIT/next-hop and real v2 continuation/EDIT/reconfirmation paths preserve historical first carry and original-key GET.', ['test_multi_hop_history_and_first_key_survives_later_manual_edit','test_real_v2_material_continue_first_carry_then_edit_reconfirm_next_hop']),
('NC32','NAMED_SCENARIO','Current effective second compatible title/source carry with exact historical first key; not arbitrary lineage graph.', ['test_multi_hop_history_and_first_key_survives_later_manual_edit','test_old_note_history_survives_later_edit_and_next_hop_carry']),
('NC33','VARIANTS_ONLY','20 pure in-memory historical mutations after one actual carry fixture, plus seven full backend epoch/material historical cases; not20 actual HTTP negatives or all possible fields.', ['test_actual_success_receipt_strict_epoch_types_and_frozen_history','test_rehashed_nested_epoch_version_types_are_rejected_by_history','test_rehashed_forged_material_package_refused_against_original_p1']),
('NC34','STATIC_ONLY','Old Apply/StructureApply/fingerprint AST exact and old note/plan/dependency files byte exact. Actual prior nine-key/structure receipts are covered only by separately recounted old-module global windows; not converted into a new carry-specific test here.', []),
('NC35','VARIANTS_ONLY','Actual false/1/absent endpoint422 and pure float/stringtrue plus unknown/bool proof historical refusal; not every listed0/string spelling endpoint variant.', ['test_new_confirmation_is_strict_and_required','test_confirmation_requires_exact_boolean_true','test_actual_success_receipt_strict_epoch_types_and_frozen_history']),
('NC36','STATIC_ONLY','Original no-note route AST and guards reviewed; separately run old migration/structure modules supply regression, not a newly created joint positive control here.', []),
('NC37','NOT_RUN','An identically initialized second note-bearing Case B is not created by these new carry fixtures; cannot claim B-preservation literal as dynamically executed.', []),
('NC38','VARIANTS_ONLY','Two full original HTML modes display exact MANUAL note and separate explicit checkboxes/negative completion flags. No persistent opaque-handle implementation added; original key field/coldGET retained. No semantics/authorization/real-browser claim.', ['test_complete_original_html_carry_to_six_goals_and_worklist[title_locked]','test_complete_original_html_carry_to_six_goals_and_worklist[source_changed]'])]

def main():
 assert hashlib.sha256(ORACLE.read_bytes()).hexdigest()==ORACLE_SHA
 full=read(HERE/'freeze-f686ada-extra-v2.json');assert full['source_sha']==SHA and full['counts']==dict(PASS=423,FAIL=0,ERROR=0,SKIP=0)
 assert full['collection_junit_exact_match'] and full['unique_junit_nodes'] and not full['source_drift'] and not full['all_tracked_drift']
 new=ROOT/'.runtime/note-template-carry-independent-formal-v2';iv=read(new/'note-carry-v2-validation.json');assert iv['source_sha']==SHA and iv['counts']==dict(PASS=28,FAIL=0,ERROR=0,SKIP=0)
 files=[HERE/'freeze-f686ada-extra-v2.xml',HERE/'freeze-f686ada-history-v1.xml',HERE/'freeze-f686ada-budget-v1.xml',new/'note-carry-v2.xml']
 observed=[]
 for p in files:
  for c in ET.parse(p).iter('testcase'):
   assert all(c.find(t) is None for t in ['failure','error','skipped'])
   observed.append((c.get('name'),str(p.relative_to(ROOT))))
 rows=[]
 assert len(MAPPINGS)==38 and len({x[0] for x in MAPPINGS})==38
 for id,kind,scope,selectors in MAPPINGS:
  hits=[]
  for selector in selectors:
   found=[dict(test_name=name,JUnit=p) for name,p in observed if selector in name]
   assert found,(id,selector)
   hits.extend(found)
  rows.append(dict(id=id,coverage_kind=kind,status='PASS_ONLY_FOR_DESCRIBED_SCOPE' if selectors else 'NO_NEW_DYNAMIC_EXECUTION',scope=scope,evidence=hits))
 trace=dict(source_sha=SHA,oracle=str(ORACLE.relative_to(ROOT)),oracle_sha256=ORACLE_SHA,design_count=38,design_count_is_not_pytest_count=True,scope='Linux synthetic ownedPG only; independent fixed literal expectations preserved',coverage_kind_counts=dict(Counter(x['coverage_kind'] for x in rows)),scenarios=rows,independent22_design_mapping='Separate note-carry-v2-design-coverage.json, not added to these38',whole_design_acceptance=False)
 write(HERE/'literal-38-actual-trace.json',trace)
 s=read(HERE/'frozen-static-review.json');s['status']='PASS_FROZEN_STATIC_AND_ASSIGNED_REGRESSION_ONLY';s['formal_extra']='16 complete modules423PASS runner '+str(full['elapsed_seconds'])+'s; original422P1F and bounded retry retained'
 s['supplemental_pytest']=8;s['pure_historical_mutation_checks']=20;s['final_archive_audit']='NOT_RUN_AWAIT_ARCHIVE_READY';write(HERE/'frozen-static-review.json',s)
 summary=dict(status='PASS_ASSIGNED_FROZEN_REVIEW_NOT_GLOBAL_ARCHIVE_GATE',source_sha=SHA,
     full_window=dict(prefix='freeze-f686ada-extra-v2',complete_modules=16,counts=full['counts'],runner_seconds=full['elapsed_seconds'],JUnit_seconds=full['junit_seconds'],raw_collection_JUnit_exact=True),
     source_paths=613,all_tracked_paths=14392,source_and_all_tracked_drift=[],
     history_supplement=read(HERE/'freeze-f686ada-history-v1.json')['counts'],budget_supplement=read(HERE/'freeze-f686ada-budget-v1.json')['counts'],
     supplement_pytest_items=8,pure_historical_mutations=20,pure_mutation_fixture_count=1,
     supplement_fixture_required_goals=5,supplement_transport='ASGI_TESTCLIENT_OWNED_PG',
     new_independent_module_reference=dict(counts=iv['counts'],new_actual_full_HTML=2,new_actual_HTML_HTTP_requests=24,six_goal_current_closures=4,executed_by_other_agent=True),
     preserved_nonpassing_history=['c376 browser collectionERROR and runner postprocessor marker error; no tests executed in that attempted17-module window','c376 16-module interrupted158PASS,265uncompleted with separate unnamed interruption marker; not complete423PASS','f686 first complete16 window422PASS1FAIL at choose precondition before targetLOCK assertion; same original node independentPG1PASS; one authorized complete retry is the present window'],
     no_product_test_assertion_permission_changes=True,no_real_browser_install_or_launch=True,
     blocked_external='tests/test_template_upgrade_browser.py',literal_design_count=38,literal_design_scope_counts=trace['coverage_kind_counts'],
     source_static_review='frozen-static-review.json',design_trace='literal-38-actual-trace.json',Git_blob_proof='frozen-Git-blob-proof.json',
     remaining_global_gate='Await other current frozen windows, final coverage and explicit ARCHIVE READY; no archive PASS issued',
     limits=['Linux synthetic engineering evidence','No Windows, real browser, formalAT, real model or production','95 affected executable modules not whole-repository coverage','38 review designs and22 independent designs are separate and not pytest denominators'])
 write(HERE/'review-summary.json',summary)
 (HERE/'review-summary.md').write_text('Frozen independent review: '+SHA+'\n\n'
     +'Assigned 16 complete modules: 423 PASS, '+str(full['elapsed_seconds'])+' runner seconds ('+str(full['junit_seconds'])+' JUnit seconds). '
     +'Raw collection/JUnit IDs are unique and exactly equal; all 613 source and 14392 tracked files match before/after.\n\n'
     +'Supplementals are separate: 2 historical-chain pytest items and 6 budget pytest items PASS. Twenty pure in-memory historical mutations occur inside one actual carry fixture; they are not20 HTTP refusals. These mature fixtures have five required goals; the separate new independent module supplies the two actual full HTML/six-goal acceptance flows.\n\n'
     +'The first same-SHA complete window remains 422 PASS / 1 FAIL: a one-second source expired before the choose precondition, before the intended LOCK assertion. The unchanged original single-node PG check passed. This second full window is the one authorized bounded retry; no old score is transferred. Earlier blocked-browser/runner/interrupted windows remain preserved.\n\n'
     +'No new frozen static blocker. Strict epoch types and full historical material-package anchoring defects were fixed before this freeze. Old note/plan/dependency files and legacy Apply/StructureApply/fingerprint AST remain unchanged.\n\n'
     +'The38 literal designs are traced by described scope, with unexecuted variants explicit; they are not an all-design acceptance claim. Windows, real browser, formalAT, real model and production remain NOT_RUN. Global coverage and independent archive reconstruction are pending their own gate.\n',encoding='utf-8')
 print(json.dumps(dict(status=s['status'],source_sha=SHA,complete_modules=16,full_pytest=423,supplemental_pytest=8,pure_checks=20,design_coverage=trace['coverage_kind_counts']),indent=2))
if __name__=='__main__':main()
