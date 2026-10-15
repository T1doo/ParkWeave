# Shared source → owned Case reverse lookup: independent scope review

Baseline delivered HEAD was independently observed as `9e8080920d906613bf61f47dd9be4218b8075856`, branch `dev/f3-shared-source-cases-20261015`, initially clean. The original source implementation is the reviewed `a5d9da25` finite typed graph. Current implementation is work in progress; this review is not frozen-source approval and no regression was started.

Original product §8 requires stable scoped source identity/revision, actual-reading provenance, query collection fingerprints, explicit unknown scope, original locks/history, and independent should-change/should-preserve answers. F3-T02/T03 and AT24–27 are broader than this finite implementation; the new contract correctly chooses explicit owner resource-query set and used service-catalog reference reverse lookup, retaining original per-Case ADOPT/VERIFY actions.

## Identity, comparison and attribution

- A typed graph node ID includes Case binding, plan UUID, adapter and facet. It is a source-group ID inside that plan and cannot be used as a shared-source identity.
- Resource collection identity is the original owner/park/org fixed resource query semantics. Its contents include all originally grant-visible optional candidates, not only currently selected resources. Filtering to selected resources silently misses the central new-resource case.
- Used service catalog is actually read through `catalog_publication.key_of(parent) = (park_id, service_id, service_version)`. If the new kind represents that row, row version belongs in identity; source.revision/cooperative head/current hash/xmin are content versions. If it represents the all-service-version query, define that as a different query identity. Do not conflate them.
- A selected source's changed relationship/affected partition must remain distinct from the entire Case's current typed graph. A material change can make whole-Case graph.affected P1–P5 while the selected resource collection changed only P2–P5, or did not change at all. Reporting the whole partition as caused by the selected source produces false positives.
- Historical before comes from original VERIFY/ADOPT evidence. Preserve old v1 source history and frozen v2 schema1 reconstruction. Never infer old per-material/per-assertion identity from current rows.
- Catalog WITHDRAWN, invalid/current unknown and source-authority loss cannot appear as a currently valid UNCHANGED source just because its content digest matches. Preserve the distinction between a known unchanged query, unknown relation/baseline, and current business blockers.

## Scope, snapshot and bounded pagination

- Candidate SQL must repeat current original owner, park/org, synthetic Case/Run namespace/source, original case.create action and coherent Case/Run/preparation relationships. Missing preparation/plan/baseline is explicitly counted UNKNOWN; an INNER JOIN plan must not hide it while claiming full scope.
- Reuse current READ/PREPARE, not EXECUTE, for the read-only lookup. Wrong owner/tenant/role, inactive identity and revoked READ/PREPARE refuse without foreign counts/titles/source contents. Each request reauthenticates under the original advisory-principal lock protocol; READ COMMITTED re-reads after waits.
- Snapshot identity needs actual source row versions and grants, the full bounded candidate set, each Case/Run/parent/plan version and relevant row epochs. Content-only hashes miss source A→B→A, delete/reinsert with same public values, and Case revision restoration. Candidate changes before or after the visible page must stale the old continuation.
- Do not retain multiple parent/resource lock sets across Cases. Existing plan readers obtain parent UPDATE and original dispatch/receipt/resource/Case locks; call each Case under a fresh original-scope transaction, then prove source/candidate/Case epochs stayed stable across the assembled result. Do not introduce REPEATABLE READ before an authorization wait or a reverse resource→parent lock order.
- Candidate hard cap and page cap must be literal bounded constants. Read N+1 to prove overflow. Unknown/overflow/unvisited Case sets are not empty effects or complete coverage. No-plan and malformed history cannot be silently skipped. A failed Case probe may yield scoped UNKNOWN or a bounded whole-query rejection; neither may authorize a patch.
- Cursor bind actor/park/org, exact anchor, source kind/identity/content epoch, complete candidate/Case manifest and position/page policy. Reject duplicates, missing/extra fields, malformed/oversized cursor, altered anchor/kind/limit/start, foreign cursor and stale A→B→A. A client-computable hash alone is not proof that preceding pages were traversed. One bounded alternative is re-evaluate all32 candidates on every request, then honestly distinguish fully inspected scope from a displayed page; otherwise use a server-checkable continuation chain and do not claim visited history from client assertions.
- Do not weaken the existing trusted administrator final-read→COMMIT boundary or claim perpetual cross-request consistency.

## UI work-in-progress review

Current code captures anchor/current/token/kind/generation and returns before interpreting stale403; current403 clears original private views. It invokes the existing unresolved-operation gate and sends GET only. No new regression was run.

Open parser guidance sent to root: retain/compare source_epoch_sha256 and scope_sha256 across pages, not merely source_sha256/candidate/Case hashes; enforce logical consistency of all_cases_checked/enumeration_complete/state/unknown_scope/count, strict UUID shape and nonnegative bounded plan revision. The present regex permits36 hyphens and the completion booleans are independently accepted. These are static malformed-response gaps, not evidence of an actual backend authorization bypass.

## Independent literal answers and regressions

Create at least two matching owner Cases, a P1-only known nondependent plan, no-plan/no-preparation Case, same-owner other catalog-version Case, foreign owner/org/park Cases, and an independently changed-material Case. A new optional owner resource must affect matching P2–P5 only, preserve P1 and all unrelated business rows/locks/history; a material-only Case change must not be attributed to an unchanged selected resource. Used catalog row changes match exactly the declared identity, never another service/version. Unknown cases stay separately counted.

Check cap32/33 and page1/10/20/21 API boundaries, stale earlier/later-page Case changes, source/grant/Case ABA, candidate insertion/deletion, altered cursor fields, authorization wait/revocation and post-refusal cold GET. Run full original HTML actual HTTP/ASGI/owned PostgreSQL modes for positive multi-Case page/open/explicit existing adoption, current403, delayed403/success after identity ABA, source-kind switch, pagination409 and original pending-write guards. Expected sets are literal Case/adapter IDs; product closure does not construct the oracle.

Frozen independent assignment is the same8 complete extra fact/material/service modules as the previous batch; root owns old52 in27/25 shards and independent testing owns old typed2+new shared2, for64 disjoint modules if exact collection proves it. This reviewer waits for an exact frozen SHA before starting its8 modules, separate /tmp PG and runtime stdout/collection/JUnit/source manifests. Windows/real browser/formal AT/models/production/remoteCI gaps remain.
