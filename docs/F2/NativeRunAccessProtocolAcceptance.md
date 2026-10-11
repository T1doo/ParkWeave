# Ordinary PostgreSQL Run access decision protocol

Source: `213a6b9083a4f0f10f6b71bcd0da10d826c78a46`.
The 411-file source manifest is
`0e0a325123aa404483b1184e1dd50cec98cc25b37477f6700900e2c3eca3cfa9`.

## Delivered scope

The ordinary PostgreSQL protocol persists REQUEST, APPROVE, REJECT, CANCEL and
REVOKE with strict UTC DTOs, exact Run/material/current-permission bindings,
actor-key idempotency, original-key GET recovery, immutable event/lease history
and atomic rollback. Cold owner reads are read-only and do not invalidate plans.
The workbench shows pending activation and uses GET only after a lost response.
Cancelled Cases reject new requests/approval while preserving authorized history,
original receipts and request cancellation/revocation.

Approval and proposed leases always remain **NON_EFFECTIVE**. Production command
writes are closed. This slice does not implement an effective native access
provider or an assignment activation entry. Any native-marked assignment is
denied by the shared predicate, including cold stores, unknown markers and JSON
null; legacy assignments retain their behavior. Dispatch, receipts, notices and
dependency collections retain that shared boundary. The existing isolated
SQLite/PG provider remains distinct and cannot be combined with this provider.

The additive SQL is an **unenabled delivery file**, outside automatic migrations.
Only issued fresh owned synthetic PostgreSQL fixtures install it during tests.
The application uses its existing table permissions; this feature does not write
authority, Grant or assignment rows. Run success, material history, resources,
reservations and cancellation/handoff schema gates remain independent.

## Validation

The root complete 44-module window finished with 1,720 unique IDs: 1,709 clean
PASS, 0 FAIL, 10 ERROR, 1 SKIP, exit 1. All ten errors came from the full-chain
fixture's teardown refusing to overwrite an earlier exploratory evidence file.
The console's 1,719 passed includes those ten successful call phases and is not
the clean JUnit result. The original output and XML remain unchanged.

Only those ten IDs were rerun, using a fresh evidence directory and the same
frozen source: 10 PASS, 0 FAIL/ERROR/SKIP, exit 0. The exact ID sets match and all
411 source hashes remain unchanged. Combining the two root windows by ID gives
1,719 PASS, 0 FAIL/ERROR, 1 SKIP. This is not a claim of one clean 44-module run.
The sole skip is the existing native Windows file-backend gate, requiring
Windows 11 x64 for reparse points, ADS, ACL and clean lifecycle validation.

The independent frozen window completed with 56 PASS, 0 FAIL/ERROR/SKIP, exit 0,
411 source files unchanged and byte-equal to the source commit. It comprises the
two complete new modules (42 IDs) and 14 independent probes; the 42 overlap the
root scope and must not be counted twice. Its report signs only the finite
decision protocol and denial boundary, not actual native assignment activation.
After deduplication the root and independent windows contain 1,734 unique IDs:
1,733 PASS, 0 FAIL/ERROR, 1 SKIP. The independent review is LIMITED_PASS with no
remaining blockers within this finite scope.

Original root failures and independent counterexamples, including the independent
probe's own SQL-parameter Oracle failure, are retained with their original logs,
JUnit and a same-ID final repair mapping. Development windows are not added to the
frozen unique test total.

The whole staged `git diff --check` reports trailing whitespace in unchanged
original failure XML/logs. Their bytes are preserved as required. The authored
files pass the whitespace check with only raw XML/log evidence excluded; the
original whole-check output is retained in the archive.

Evidence: [archive](evidence/native-run-access-protocol-20261011/),
[independent report](evidence/native-run-access-protocol-20261011/independent/REVIEW.md),
[exact combined results](evidence/native-run-access-protocol-20261011/root/final-combined-results.json),
[contract](NativeRunAccessContract.md).

## NOT RUN and next step

Production storage installation; real authority/Grant/assignment and SQL privilege
changes; adopted named approver/beneficiary/Run/TTL policy; effective native lease
end-to-end activation; native Windows PostgreSQL; browser startup/navigation;
models, deployment and formal complete AT35 acceptance are NOT RUN. The historical
Chromium `data:` navigation `ERR_BLOCKED_BY_ADMINISTRATOR` was not retried.

Daytime activation needs an explicit decision on exact approvers, beneficiary,
Run scope, TTL and revocation responsibility. Four/eight hours remain a proposal.
Then separately implement and review the restricted activation entry and effective
provider, validate them in the authorized environment, and only enable production
after approval. This delivery does not assert a complete Case/access lifecycle.
