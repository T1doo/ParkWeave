# Independent fourth-window findings

**BLOCKED pending the two product fixes.** This is a scoped independent review, bound to the 405-file source manifest `071ef59e5838bc64e4b2bb6cb35e867eb416bb99ce16baa42c15406bd85239e0`. Each PG/ASGI process owned its fresh fixture. No source, root test, document or Git mutation; no browser attempt.

| Window | PASS | FAIL | ERROR | SKIP | Exit | Source drift |
|---|---:|---:|---:|---:|---:|---|
| fourth-extra-probes | 22 | 2 | 0 | 0 | 1 | 0 before / 0 after |
| fourth-oracle-retest | 2 | 0 | 0 | 0 | 0 | 0 before / 0 after |
| fourth-cold-hydrate-failure | 0 | 1 | 0 | 0 | 1 | 0 before / 0 after |
| fourth-prefix-projection | 0 | 3 | 0 | 0 | 1 | 0 before / 0 after |
| fourth-rehashed-initial | 0 | 2 | 0 | 0 | 1 | 0 before / 0 after |

`fourth-extra-probes` contains two independent fixture/oracle mistakes. Holds were correctly `RELEASED`, and the fake future expiry was only 1 ms past the boundary. Both original failures are preserved; corrected assertions passed under the same two IDs in `fourth-oracle-retest`. The old 22 PASS / 2 FAIL window is not relabeled.

The six subsequent actual product failures are distinct from those oracle failures:

1. **MEDIUM, AR-UI-001**, `src/parkweave/web.html:534`: actual cold opaque REQUEST handle hydration plus the production submit capture allowed `material-reuse-form`, `request-intent-form`, `fb-form`, `opp-import`, `receipt-submit`, `receipt-local-execution-form`, and `resource-binding-confirm-form`. The ordinary evidence form was correctly blocked. No server RECONCILING bypass was observed. Cover current-Case writes while leaving history GET and independent resource releases available.
2. **MEDIUM, AR-PROOF-002**, `src/parkweave/case_cancellation_reconciliation.py:129`: three damaged current projections of a valid old REVALIDATE (`REOPENED` with no event, replaced verified snapshot, replaced verified SHA) still gave `can_request=true` and REQUEST POST200. Two fully rehashed first REQUESTs could claim cycle 2 or initial WAITING_CONFIRMATION without a prefix; GET still allowed reconciliation and original-key recovery returned200. Bind the projection to the last legitimate old event, derive initial Case state from the prefix and require cycle 1 throughout this no-close-history slice.

All original logs/JUnit, observation JSON, independent fixture snapshots and ten frozen product/test byte snapshots remain available in this directory. `FOURTH_WINDOW_FINDINGS.json` records exact hashes and failed IDs. This stage does not sign the product fix or the whole repository. The unknown historical Case0 root cause remains unconfirmed. Browser: NOT RUN, 0 attempts.
