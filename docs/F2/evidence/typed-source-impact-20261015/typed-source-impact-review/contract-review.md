# Typed source impact: independent pre-implementation contract review

Reviewed baseline: `f353da680d919fcb4033a02ab57f4fec95335f86`. Git clean when first checked. This is read-only review; no product/Git changes. Root remains the sole integrator.

## What remains, and what already exists

Original product §5.6 and §8 and phase F3-T02/T03 (AT24–27) require actual scoped sources, stable identities/revision hashes, typed upstream→downstream edges with provenance, collection fingerprints, uncertainty, preserved decisions/history, and independent missed/incorrect impact accounting. They do not require destructive migrations to succeed: AT27 requires incompatible changes to be refused with evidence.

Already delivered: opportunity IMPORT/REFRESH/IGNORE/WITHDRAW; exact current Case source preview; original local ADOPT; original VERIFY/LOCK/UNLOCK; stable P1–P5 and six declared goals; collection-aware closure; source epochs, replay/cold GET; limited Release/ParkInstance/second-park selection; finite forward template strengthening. None should be rebuilt.

Current concrete limit: `registered_dependencies.py:12–19` declares categories and compiles only PRECEDES step edges. `source_change_adoption.py:42–47` compares whole per-step source objects, then takes registered closure. It does not identify separately typed immutable source entities or expose their causal path. `case_worklist.py:46–116` reports recorded states and safe entry links, not reverse source→Case impact discovery.

**Highest-value eventual next slice:** finite actual-source graph plus a currently authorized owner Case impact board, using the existing explicit adoption loop. This makes the origin of an impact inspectable and finds other owner Cases using a shared source. It does not claim arbitrary graphs or general semantic dependency completeness.

**Root's selected bounded implementation for this batch:** `GET /api/preparations/{id}/source-impact` for one current original owner Case, available without an opportunity; explicit worklist-per-Case button; no automatic cross-Case scan/new business event. This is useful typed per-Case causal location. It must not be described as reverse discovery of every affected authorized Case. That broader discovery remains a separately measurable key-path item.

## Proposed acceptance contract for the selected batch

1. Compile a deterministic finite graph from actual adapter reads and original persisted source proofs. Graph owns a schema/declaration version, explicit known/unknown scope, stable node identities, separate revision/content/epoch fingerprints, typed edge provenance, and exact affected/preserved stable step IDs. Scope binds actor, tenant/org, preparation/Case/Run, plan UUID/revision, goals, original verified/adopted base, and current source state.
2. Node identity must not be the current content hash. Use a scoped actual logical record identity (or deterministic identity of that scope/type/key). Revisions/hash/validity are separate. Two Cases can refer to the same resource identity without either acquiring access to the other Case. Arrays sort canonically; duplicate nodes/edges, collision, dangling endpoint, unsupported kind/provenance, cycles where not allowed, extra fields and declaration overflow are refused or explicitly UNKNOWN.
3. Supported original node kinds can be a strict subset of REQUEST/FACT/SOURCE/SERVICE_RULE/RESOURCE/CAPACITY_SNAPSHOT/PLAN_STEP/RESERVATION/MATERIAL/RECEIPT/CHECK/RELEASE. Support only those with actual data. Unknown fields remain null/UNKNOWN, not guessed dates or validity. Edge types must use the original enum and mean what their labels claim. PRECEDES comes from the registered plan; MATERIAL/CAPACITY from actual bounded source reads; VERIFIED_BY links a source/output or step to its original check; PACKAGED_IN only where an actual original immutable binding exists. Do not label a readiness input ELIGIBILITY as a real qualification result. Do not invent SEMANTIC edges; unverified/model/text candidates remain non-authorizing unknowns.
4. Read-only means no plan invalidation UPDATE, new snapshot event, opportunity REFRESH, VERIFY, permission, or business effect. A GET may serialize through existing locks, but must use observe=False for original inspectors and prove all business/authority tables unchanged. Selecting a worklist item or graph node never invokes ADOPT.
5. The new graph can explain a source impact without an opportunity. No-opportunity GET must not create a card. Existing opportunity adoption still requires the original valid pending card and explicit user action. Preview data, graph text and node titles do not grant authority.
6. New source-change events may store a deterministic **version 2** typed proof, fully included in the original request/preview/event fingerprint chain and recomputed after all waits. Version 1 events retain their exact keys/hash/recovery algorithm. Old history must not be recompiled using today's graph declaration version. Old API bodies/fingerprints without the optional extension remain supported as contracted. Save only one original ADOPT event, keep goals, contracts, IDs and historical snapshots; affected steps still require original VERIFY.
7. If typed and original adapter partitions disagree, fail closed or expand explicit UNKNOWN. Never use a more precise-looking graph to narrow the existing required invalidation/permission gate silently. Preserve old locks; affected locks still require original UNLOCK. Graph UNKNOWN is not evidence that all actual content needs rewriting. Show impacted known steps, uncertain recheck scope, protected/blocked locks and preserved history separately.
8. Keep bounded source limits inherited from original readers. If graph nodes/edges need another bound, use fixed explicit limits and a sentinel overflow; never truncate and call the graph complete. A reader lacking baseline proof may return a useful current graph plus UNKNOWN comparison, but must not issue an adoptable proof from missing before state.

## Two implementation traps found in the real baseline

**Historical granularity.** `controlled_plans.binding_p1` stores preparation/review digest and opaque fact descriptor. The old P1 VERIFY does not contain per-slot evidence refs. `preparation.command` stores a snapshot hash in original events, not an exact historical slot mapping. `preparation.fact_descriptor:162–175` deliberately excludes assertion IDs, values and excerpts. Therefore a legacy aggregate MATERIAL_PACKAGE/FACT_PURPOSE_BINDING node can be sound; reconstructing exact old material slots/selected assertions by inspecting current rows is unsound. If exact bounded reconstruction is implemented, require its original proof and unique match; ambiguity is UNKNOWN. A graph may truthfully expose an aggregate node with a subtype; do not claim complete fine-grained material/fact lineage.

**Collection membership.** `registered_dependencies.collections` fingerprints every existing resource currently readable by the owner, including optional alternatives. Inserting an eligible optional resource or changing the owner grant collection can affect all that owner's Cases with P2, even when that resource was not selected. Conversely, a different owner/tenant's resource with no authorized collection membership must not affect this owner. A lookup using selected resource IDs alone would miss these changes. Run-access collections are scoped to the original Run; use that narrower actual scope.

## Refusal and privacy boundaries

- Current READ/PREPARE/owner/tenant/Case/Run scope is checked before private lookup and after waits. EXECUTE remains a write permission, not a newly required read grant. Revocation/identity/owner/Case changes cause refusal; stale/ABA data cannot authorize a new ADOPT. No secret-bearing query-by-arbitrary-table/source-ID route.
- Fact values/IDs/excerpts remain behind the original field-purpose contract. The owner graph/worklist may show opaque scoped status/hash/type, not newly expose a shared global fact source or another Case's detail. A shared resource node is not permission to list other owners' Cases or reservations.
- Unsupported contract/registry/plan/Case-goal changes, partial-plan ambiguity, absent/corrupt original proof, withdrawn/expired/UNKNOWN sources, overflow and current affected locks do not gain a new write path. Current graph visibility and adoptability are distinct.
- No new grant, public publisher, background watcher, real model, deployment, source-maintainer permission or cost. Existing SELECT-only administrator final-read→COMMIT trust boundary remains explicit; the graph alone cannot claim a new linearizable publication protocol.

## Independent literal oracles

Use frozen six-goal P1–P5 test data and literal expected sets, not the graph's own closure to generate the expected answer.

| Controlled change | Expected affected steps | Expected preserved behavior |
| --- | --- | --- |
| This Case material package changes | P1,P2,P3,P4,P5 | all original facts/history remain; old review/confirmation is not current evidence |
| Owner's optional resource collection changes | P2,P3,P4,P5 | P1 and its entire lock/check proof stay exact |
| Original Run access collection changes | P3,P4,P5 | P1,P2 stay exact; no new assignment is granted |
| Actual receipt version/output changes | P4,P5 | P1,P2,P3, prior receipt facts and stable receipt-step ID remain |
| Local lifecycle evidence changes | P5 | P1–P4 stay exact |
| Prompt/title/note only | none | no actual source node revision/edge/partition changes, no adoptable patch |
| Foreign owner/tenant unrelated change | none visible | no IDs, membership counts or private values leak |
| Unknown/missing original before proof | no asserted complete exact diff | current graph can show known records; adoption denied and uncertainty scoped to this Case |
| Affected locked P3 vs unaffected locked P1 | P3 conflict blocks, P1 preserved | original explicit UNLOCK required, never automatic unlock/reverify |
| v1 proof then v2 proof then template strengthening, and inverse order | literal affected sets per each original action | exact recovery/history/goal output reads and cold GET survive each order |

For each scenario count missed updates as expected_affected minus actual_affected and wrong impact as actual_affected minus expected_affected; report preserved-content byte changes separately from recheck breadth. Do not call an intentionally conservative UNKNOWN expansion an accurate exact diff; present its reason and expanded scope separately. For a future cross-Case board, require distinct Cases A/B sharing one owner resource collection, C with material-only plan, D another owner and E another tenant: material A affects only A; optional owner resource affects A/B only; D/E remain undisclosed. The selected per-Case reader does not yet satisfy that future discovery oracle.

## Complete regression scope

Retain the previous 52 complete related modules in `.runtime/source-adoption/root-modules.json`, plus new typed reader/backend/independent full HTML modules. Their proof validation is shared by original plan reads, goal results, gates, recovery, locks, template history and replay, so isolated unit tests alone are insufficient.

Add complete modules newly touched by typed source extraction and not in that old list: `test_case_fact_clarifications`, `test_case_fact_clarifications_integration`, `test_case_fact_bundle`, `test_material_preparation_drafts`, `test_plan_source_trace`, `test_service_capability_contract`, `test_service_capability_catalog_actual`, `test_service_selection_source_safe`. At minimum the fact-purpose/bundle/material-summary modules must run even when using opaque descriptors, to preserve privacy and historical/current semantics.

Run original `test_case_worklist`, `test_case_worklist_offline`, `test_worklist_real_entries_offline` and prior original-HTML source-adoption independent flows after page changes. Add actual original HTML→HTTP→ASGI→owned PostgreSQL flows for no-card GET, precise typed partition, explicit card adoption/VERIFY/goal/worklist, rejected source/authority/late identity cases. Do not use a real browser while the earlier refusal stands.

Keep `test_ci_diagnostics` and exact AST ID registry checks after adding tests; unchanged 512KiB bound has headroom and must not be lowered/disabled. Satisfy the inherited `.runtime/template-hold-20261014` output-directory prerequisite before running its unchanged module. Retain every failed/skip/interrupted window and bind final independent review to the precise frozen SHA and before/after file manifest. Separate Windows/browser/AT/model/production NOT_RUN gaps.
