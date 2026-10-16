# Schema 33 before-receipt cancellation preimplementation review

Scope: read-only source and original tests at delivery HEAD 75adba254a6455258b36d3b3e2f5707196548ec7. No database execution or shared source/test/Git mutation.

## Minimal change

Add a dedicated eligibility helper to `case_cancellation_before_receipt.py`: original `sd._handoff_enabled` continues accepting schema 29–32; new helper accepts exactly schema 33, exact Store type, no local execution provider and none of the seven original isolated execution/access adapters. Require retained schema 29 and 31 prerequisites; existing `_source` retains schema 30/31 requirements. Use this new alternative only when `allow_manual_receipts` is false. Keep `_handoff_enabled` and reconciliation behavior unchanged. Do not let unknown future schemas, Store subclasses or managed run assignments qualify.

## Proven existing protections

The owner principal and preparation lock precede dispatch/Case/local locks. Receipt command obtains the same preparation write lock then invokes `case_write_guard` before receipt writes. Cancellation source inspects all receipt generations and rejects every non-CREATE receipt event or persisted receipt. Snapshot includes original plan and resource-link digests. Commit updates only Case/local lifecycle and appends a cancellation event; no hold release or reapproval exists. Original key lookup precedes current fence validation, allowing unchanged-key replay while rejecting changed fingerprints. Cold recovery is READ-only and retains current owner/capability checks; EXECUTE revocation permits recovery but prevents POST.

## Direct writer boundary

Original migrations 30/31/33 have no general CANCELLED business-row SQL trigger. Frontier effect triggers serialize and advance epochs; they do not reject receipt writes solely because Case is CANCELLED. Consequently direct writer evidence should invoke real original Python service commands without HTTP and expect `Conflict` from `prep.case_write_guard`, asserting no mutation. Raw database-owner SQL mutation is not refused by this contract and must not be claimed as covered.

## Required direct verification

1. Schema 33 positive cancel with exact original ACCEPT/CREATE proof; preserve offers/events/receipt steps, controlled plan, resource links and holds; fresh cold Store GET returns same committed event.
2. Both genuine preparation-lock orders: cancel wins and receipt writer receives Conflict; receipt SUBMIT wins and cancel rejects HISTORICAL_RECEIPT_SUBMISSION_NOT_SUPPORTED. No artificial only-in-memory ordering.
3. Failure inserting cancellation event rolls back Case, local lifecycle and tracked epoch.
4. Same-key exact replay, changed body/fence conflict, NOT_OBSERVED unknown key; current owner/tenant and capability revocation on POST and cold GET.
5. Schema 33 reconciliation still blocked and handoff gate still false; 34+, managed, isolated, subclass and invalid exact ACCEPT/CREATE history fail closed.
6. Actual HTML confirmation checkbox plus reason, original API commit, lost response, cold GET with no automatic POST; resources remain occupied and evidence readable.
7. Update old frontier cancellation regression to accept before_receipt while retaining reconciliation refusal and stale/missing fence refusal.
