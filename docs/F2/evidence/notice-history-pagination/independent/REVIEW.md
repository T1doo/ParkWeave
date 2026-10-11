# Independent dispatch-notice pagination review

Frozen source: `1bccc05381b5cf1ad58149709a35720d90ea79f0`.
Parent: `c5b0a6fb7ece59f4a97e33ecfc021a1c785e6e4d`.
Candidate branch: `dev/f2-notice-history-pagination-20261011`.

## Conclusion

No blocking defect found within the approved F2-T04 / AT12/19 notification engineering subscenario. Independent new tests: **25 passed, 0 failed, 0 errors, 0 skipped**. This is a scoped pagination review, not complete AT, real browser/Windows, multiworker, mainline integration or deployment acceptance. No history registry/loader, production authorization or old execution-proof chain is enabled.

## Read-only implementation review

The source diff is limited to dispatch notice pagination, its GET route, the original notification page section and necessary tests. Existing explicit OPEN/MARK_READ paths are unchanged. Notice generation/delivery and original Case permission checks are not rewritten.

Backend rows are ordered by `(delivered_at DESC,event_id DESC)`, bounded to 100 fetched candidates, and at most 20 currently authorized projected notices are returned. The next position advances only past the last examined row, including denied rows; fetched but unexamined rows are not skipped when the 20-item bound is reached. A 100-candidate page with zero authorized notices still emits a continuation, while a short exhausted page terminates. There is no disclosed total or promise that a continuation has authorized results.

The first fetched key establishes a logical high-water ordering bound. Continuations use strict keyset `< after` plus `<= high_water`. This freezes the upper ordering boundary and excludes later higher-key deliveries; it is not a durable MVCC snapshot or a guarantee against owner backdating/reordering rows. No long-lived transaction or full dataset cache is introduced.

The process/app-local Navigation holds only position, binding, high-water and original expiration. Public handles are opaque token_urlsafe randomness. Capacity is bounded to 256, expiry to 300 seconds from the original browsing start; child positions preserve expiry and replay does not renew it. Eviction or app restart makes old handles unavailable and requires refresh. The binding includes SCOPE, principal, park/org, role and current session token hash. A position stores no notice body or permission decision. Every list/replay authenticates current principal READ and each notice's original Case/participant authority.

Cursor/query rejection returns the original generic 403; handles, filtered event/Case/preparation identifiers and private source payloads are not echoed. Successful GET list code performs only SELECT/advisory authorization checks and in-memory position updates. The existing generic Denied handler may append authorization_audit for a recognized token; that is distinct from business/outbox/OPEN/MARK_READ writes. Independent business snapshots remain unchanged across the tested GET/refusal operations.

The original web notification block stores only current page/cursor in memory. Each page transition clears prior notice cards, detail and cursor before the request. Requests use no-store; list responses check scope, fixed bounds and cursor shape. Generation/token/id checks after JSON completion invalidate late replies, including identity ABA. Previous cards capture their original context and cannot navigate after a newer page. Duplicate continuation is suppressed while loading. Current 403 clears linked private view/position and offers explicit refresh; stale 403 cannot clear newer data. The actual pre-existing token.oninput invokes clearPreparation with discardMaterialDraft=true and clears the original identity views; it is unchanged in this diff.

## Actual independent runtime evidence

Python `review-api-1bccc053.log` / `.xml`: **19 passed** in 7.08 seconds, consisting of 18 existing owned synthetic PostgreSQL fixture / in-process ASGI cases and one pure Navigation-boundary case. The existing receipt_fixture and bounded synthetic candidate seeder are reused as setup; no restricted isolated execution/receipt proof generation occurs.

Coverage:

- 123 tied delivery timestamps traverse in exact UUID secondary order with no duplicate/skip and unchanged business snapshots; later higher-key delivery appears only on refresh of the tested browsing sequence.
- 100 unauthorized newer candidates yield an empty continuable page after exactly 100 source checks; all 51 older authorized candidates remain reachable. Filtered event/Case/preparation/body identifiers are absent from the empty response.
- The exact same handle returns current empty results after assignments are revoked; old projected items are not cached as authority.
- Rotated current session token cannot use the old session handle, but fresh browsing works; cross-tenant use and app restart require refresh.
- Child/replayed handles preserve the original absolute expiry and reject at its boundary; refresh starts a new browse.
- Cache eviction rejects an old handle without changing permission/business state; direct construction bounds reject capacity 257 and ttl 301; 257 positions leave exactly 256 retained.
- Empty, exactly 20 and exactly 100 candidate sequences terminate explicitly without duplicates; an extra empty terminal page at a scan/return boundary is legal.
- Encoded duplicate cursor parameter names, duplicate cursors, cross-purpose/unknown query keys and invalid length return generic refusal without input/private echo.
- Current principal role, org and READ changes are rechecked independently of valid positions.

Node `review-vm-1bccc053.log` / `.xml`: **6 passed** in 0.21 seconds. Actual notice-section JavaScript is executed under private minimal DOM/fetch doubles in Node VM. No browser, network request, real event loop UI or whole-page DOM integration is claimed.

Coverage:

- Detail success and 403 arriving after a fresh list cannot restore old detail/cursor, overwrite the current page or clear its feedback.
- JSON body completion delayed across identity A-B-A switches invalidates old success and old 403, preserving the newer identity page.
- Three continuation/refresh requests completed in mixed order retain only the newest page; late 403 and detached old card action have no effect.
- Empty authorized page enables continuation; a duplicate continuation produces no second request; continuation clears the prior view immediately and can reach an older authorized row.
- All recorded notice fetches are GET, no-store and body-free; no automatic OPEN/MARK_READ or business navigation occurs.

The independent 25 are new measurements and are separate from the parent's 68-case scoped run. The parent's baseline two failures and earlier offline harness failures are historical evidence and are not included or relabeled green in this review.

## Execution boundary and remaining limitations

Reviewer only read repository/Git files and wrote private `/tmp/parkweave-notice-pagination-independent-review` probes/evidence. No repository/Git mutation, fetch/checkout/commit/push, credentials, proxy/security permission changes, external network, browser/listener, alternate navigation URL, real model, restricted execution or proof chain. All fixture grants/session changes and synthetic event seeding are owned test setup, not production authorization changes.

Original browser `data: ERR_BLOCKED_BY_ADMINISTRATOR` remains paused. Real browser, Windows, whole-page behavior, multiple workers, complete AT12/19, long-lived snapshot/reordered delivery and production deployment remain unverified. In particular process-local handles are not a multiworker shared navigation service; routing a cursor to another app instance can require refresh. This candidate should not be described as mainline integration or complete issuance/restart recovery.
