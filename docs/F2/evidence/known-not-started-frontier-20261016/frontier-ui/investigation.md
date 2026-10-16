# UI investigation — KNOWN_NOT_STARTED frontier

Actual baseline HEAD: `c2263edd889c2b9b4ada9f502b3a41b32eb9341f`.
No shared source, Git, or sealed runtime changes. No implementation or tests yet.

## Existing strict contract

`web.html:2135 approvalReplacementBinding` currently validates outer proof exactly 14 keys and compatibility exactly 14 keys, schema 1 and profile `ORIGINAL_V4_SERVICE_RELEASE_PLAN_REPLACEMENT_V1`, exactly 3 pairs and 5 distinct affected steps, preserved=[], and automatic flags all false. Pair/reference/comparison shapes are independently checked. Unknown/additional keys are rejected. Stable case/run/owner/service identity and old/new plan/definition identity are bound. This existing validator must remain unchanged for old full-five-VERIFY eligibility.

`web.html:2142 approvalBaseDeliveryBody` invokes that validator for explicit whole replacement mode, preserving the original expected_previous_plan_id + expected_link_revision request. `planApprovalRender` reconstructs an available quote through the same validator (line 2168). New profile therefore needs support in this one common validation entry, not a separate bypass in recovery/history.

`deliveryRender` currently renders compatibility and affected count only. A new qualified frontier needs explicit displayed old P1/P2 historical VERIFY vs P3-P5 qualified not-started states, described as bounded original-protocol qualification and not approval or permanent absence of work. It must never derive negative facts from missing UI fields or old empty events.

## Minimal compatible extension, pending exact backend contract

1. Keep old schema/profile/key sets and validator behavior intact. Add an explicitly named separate validator for the new version, dispatched only by its exact new schema/profile. No fallback, optional-key union, generic state allowlist, or retroactive reinterpretation of old evidence.
2. Validate exact new qualification keys and all closed literals, marker identity/issuance timing/owner-Case scope, bounded epoch/history evidence references, and two old verified adapters plus exact three qualified not-started adapters. UUID/hash/state/type and cross-field linkage must match the backend contract. Existing/no-marker records remain UNKNOWN and cannot qualify via UI defaults.
3. Reuse explicit whole replacement checkbox and original new Approval flow unless the backend requires an additional explicit profile selector. No automatic mode switch or automatic approval. Preview remains GET old link then original POST preview; proposed/approved delivery body remains bound to the same quote and original purpose.
4. `approvalBaseDeliveryBody` and `planApprovalRender` both call the new dispatch; render qualified evidence separately from user consent. Cold delivery GET retains only actor/id/key opaque descriptor and remains read-only even when default mode is first delivery. Cold Approval GET can show history but does not restore an available quote until original explicit replacement mode and exact members are selected.
5. Preserve all original `deliveryGeneration`, resource identity epoch, Case, mode and member guards, including mode/identity/Case A-B-A. Late old responses cannot replace a new quote. Persisted handles do not gain qualification, epoch, body, token or approval content.

## Exact contract required before implementation

- New schema/profile literals and version discriminator location.
- Complete outer proof and compatibility exact-key sets; whether qualification is an extra outer key or nested under the new compatibility version.
- Qualification exact-key sets (including nested marker/issuance/epoch/history/events/adapters), fixed literal values, bounds, hash definitions, and explicit link to old plan and actor/preparation/Case/run.
- Historical eligibility-at-adoption evidence versus fresh current preview/PROPOSE/APPROVE/COMMIT qualification, including how epoch equality is represented and when stale/unknown values must refuse.
- Default-off status flag and how it relates to existing plan_replacement_enabled. Purpose/body changes, if any. Explicit UI action needed beyond existing whole-replacement consent, if any.
- Whether old P1/P2 proof event revisions may vary independently and whether any post-qualification note/UNLOCK/coordination events are accepted; UI must not infer them.

## Planned strict client tests, NOT_EXECUTED

Old schema/profile regressions and unknown/additional keys must still reject. New valid closed fixture; omitted/extra marker/qualification/epoch/history fields; old-no-marker; wrong issuance timing or scope; P1/P2 not VERIFIED; P3-P5 any UNKNOWN/STARTED/FAILED/VERIFIED or subset/duplicate; stale/cross-owner/cross-Case/plan/event/epoch references; new schema with old profile and reverse; profile downgrade; history reconstruction; different prior plan/body cannot reuse approval; mode/Case/identity/member A-B-A; cold GET unavailable until explicit original selection; no automatic POST. Product backend remains authority for actual PG locking, full history and marker issuance, never client fields alone.
