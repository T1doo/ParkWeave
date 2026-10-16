# Read-only P3–P5 contract scope review

Baseline 64f6068ef5bde98d2586835670be51bef178e616; shared tree clean when checked. No production, test or Git mutation performed. No PG/browser/model executed.

Existing production entrypoints implement dispatch OFFER/current executor ACCEPT, receipt SUBMIT/owner ACKNOWLEDGE, owner P3/P4/P5 VERIFY, local REVALIDATE/current GET/CLOSE_LOCAL_RECORD. Reuse only.

Minimum complete direct domain modules: test_service_dispatches.py, test_executor_receipts.py, test_service_case_steps.py, test_case_lifecycle.py. Add test_service_plan_recovery.py and test_case_lifecycle_recovery.py only if their existing read-only recovery contract is directly exercised by new tests. Business fence transport is covered by test_frontier_business_client.py; actual receipt concurrent captured-fence one-winner contract is test_frontier_p4_race.py.

New strictRelease scenario counterexamples:
- ACK new step with old Case receipt digest: 409, no write.
- P3/P4 VERIFY stale plan revision/source hash: 409, preserve original verified sources/events.
- SUBMIT then ACK captured pre-SUBMIT frontier: 409; refresh and explicit new command required.
- REVALIDATE then CLOSE needs reread revision/cycle/snapshot/frontier; stale close rejected.
- Current executor assignment and owner READ/PREPARE/EXECUTE authority precede original-key replay; revoke then deny, preserve records.
- Inject receipt/local lifecycle event persistence error after valid body: no partial state/event/snapshot write; original-key retry only after fault removed.

Recovery boundaries: /service-case-plan/command-recovery is existing plan command recovery; /local-case/recovery/{request_key} is existing local lifecycle recovery. Ordinary dispatch/receipt have current GET and same-key POST replay, no equivalent universal request-key GET. Historical replay never establishes current validity or reexecutes business side effects.

Existing direct tests cover old/current receipt mismatch and cross-step key conflict, parent revision/hash invalidity, current revocation before replay, accepted actor/event/receipt binding, P4 provenance corruption, current assignment, source checkpoint invalidation while preserving old evidence, transaction rollback and concurrent single winner. Avoid duplicating their implementation; new scenario needs only strictRelease-specific composition plus small targeted refusals.

Browser proof must identify fixture identities/setup separately. End assertions: all six requested goals LOCAL_OUTPUTS_VERIFIED; case_goal_completed=false; no external acceptance/offline fulfillment; old Case history, responsibility and resource holdings unchanged. No same accepted Case migration, cancelled Case revival or general Release migration implied.
