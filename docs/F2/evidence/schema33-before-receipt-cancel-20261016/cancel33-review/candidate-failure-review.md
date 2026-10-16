# Private candidate failure review

Read-only review; no database test process started, no shared file or Git edits.

- Oracle positive-1 had a test-only plan key mismatch (`requested_goals`; original persisted key is `required_goals`). Current candidate already corrected it.
- UI fourth attempt has 3 failures and oracle nonrace-2 has 2 failures / 10 passes. The shared cause of UI 3 and oracle cold recovery is `Store.connect` returns an ordinary connection if only the frontier protocol is attached, so frontier.current cannot find connection._access_store. Root elected to preserve production Store code and reattach the original issued approval bridge as well as the original frontier protocol to each reconstructed Store. A bare Store refusal remains explicit evidence; same-process issuance reattachment is not a cross-process restart.
- Oracle rollback trigger injection changes the issued protocol's frozen trigger catalog. The resulting Denied occurs during fence verification, before the intended failing INSERT. Test must not refresh/re-sign protocol schema to hide that rejection. Root-approved replacement: wrap original case_cancellation._commit, call its real transaction writes, then raise a synthetic exception before connection context commit; assert the whole snapshot, including frontier marker, rolled back.
- Existing snapshot comparator removes candidate_business_frontier wholesale. Stronger comparator must assert old frontier event prefix unchanged, exact epoch +2 for this fresh-local fixture, and exactly appended INSERT records for case_local_lifecycles then case_local_events, preserving all other marker and preparation fields. Suggestions sent directly to oracle and UI agents at root's request.
- UI finally metadata currently hardcodes proof booleans. Set these only after their corresponding assertions succeed; failed attempts must not claim completed cold recovery. Keep cross_process_restart NOT_RUN.

No product bug was identified in the minimal before-receipt schema33 policy gate. Root will provide frozen SHA for final review.
