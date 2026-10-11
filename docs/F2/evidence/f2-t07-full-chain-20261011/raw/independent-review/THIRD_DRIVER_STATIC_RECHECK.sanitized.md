# T07 current driver: independent static recheck

Conclusion: LIMITED_STATIC_REVIEW. No confirmed new production defect was found in this bounded static review. This phase executed no PG, HTTP, worker, Node or browser test.

The prior product manifest (405 paths, source `796b41ad8939ba1d067f84f137a4d2a1861f06d4`) has 0 current byte differences. The complete-chain 406-path window manifest has 1 current byte differences at this review timestamp. These are filesystem comparisons; no Git operation was performed.

The original formal AT requirements remain unchanged. Ordinary A exposes missing production new-Run assignment authorization; B requires an explicit owner-only synthetic assignment setup before actual API business work. Its manual review/submit/ack/verify actions are test-driven synthetic local records. This is not formal AT35, natural-person trial or external fulfillment.

Actual root windows, separately preserved and read from original JUnit/log/run metadata:

| Window | PASS | FAIL | ERROR | SKIP | Exit | Process seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| first | 0 | 10 | 0 | 0 | 1 | 27.473 |
| second | 9 | 1 | 0 | 0 | 1 | 71.271 |
| third | 1 | 9 | 0 | 0 | 1 | 21.305 |
| proof-check | 1 | 2 | 0 | 0 | 1 | 21.442 |
| proof-check-second | 2 | 0 | 0 | 0 | 0 | 28.096 |
| complete-chain | 10 | 0 | 0 | 0 | 0 | 92.302 |

All six windows have unique testcase identities and zero recorded source drift. Original failures are retained; later PASS does not relabel those windows. First recovery projection, second cancellation nesting, third absent setup column and proof-check raw-hold join failures are driver oracles. Plan current events belong to `events`, whereas `history` holds earlier plans. The corrected current driver uses exact membership joins and current VERIFY event source SHA.

The ten complete-chain traces record 23 actual independent CLI worker launches, all exit 0. One configured_app cold API process belongs to the successful repeated-input case and exits -15 after fixture-directed termination. No independent child execution is claimed here.

Remaining oracle and coverage suggestions:

- S01 (EVIDENCE_IMPROVEMENT), `tests/test_f2_t07_full_chain.py::Chain.cold_api`: Health readiness checks only HTTP 200; use the existing health process_id, schema, data and execution_mode to bind the response to the owned configured_app child. communicate timeout should terminate/kill only that owned child and preserve diagnostics.
- S02 (EVIDENCE_IMPROVEMENT), `tests/test_f2_t07_full_chain.py::Chain.assert_outputs`: P1 individually checks projected evidence rows but does not require output evidence IDs to be unique and exactly equal to all two current preparation materials. Review/confirm event payload source/case/run revisions and snapshot hash can be independently asserted.
- S03 (EVIDENCE_IMPROVEMENT), `tests/test_f2_t07_full_chain.py::test_failure_correction_delivery_feedback_and_explicit_local_reopen_preserve_history`: After closing the local record, explicitly assert P5 NEEDS_RECHECK before VERIFY and P1-P4 still current. Bind P5 revalidation event preparation_id and snapshot SHA to the same current local record.
- S04 (COVERAGE_LIMIT), `tests/test_f2_t07_full_chain.py::test_current_owner_revocation_blocks_cold_original_material_key_and_delivery_read`: The revocation scenario performs fresh requests on the original HTTP server; the separate configured_app process currently covers only successful whole-chain read, not this revocation case.
- S05 (FORMAL_BLOCKER), `src/parkweave/store.py::Store.assign_status; src/parkweave/api.py::access_bridge`: Ordinary new Run has no production assignment writer. A correctly proves default 403; B uses precisely documented owner-only synthetic setup assignment. Neither result is formal zero-setup AT35.

The `driver_sha256` in root run metadata hashes the capture helper `run_window.py`; the test-driver hashes are separately present in each source manifest. Final source commit and full related regression have not been independently reviewed in this stage.

Machine record: `third-driver-static-recheck.json`, SHA256 `b3bc16df151c3b3ab6472878b43583a70c73bad588d9ee13f1013f333e2e4325`. Original input hashes, actual root XML/log paths and hashes, stage counts and testcase trace summaries are included there. Earlier signed independent reports remain unmodified. Browser attempts: 0; historical navigation denial is preserved; no credentials, external app, model, deployment, Git write or permission creation was performed.
